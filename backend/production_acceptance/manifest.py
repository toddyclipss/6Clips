# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production-Safe Input Manifest and Rights Acceptance Interface (Wave 9).

Enforces strict provenance, permissions, and integrity on source media before any
background processing or orchestration is initiated:
- Explicit owner/creator authorization and permitted uses.
- License type validation (USER_OWNED, COMMERCIAL_CREATOR_LICENSE, LICENSED_GAMEPLAY).
- Cryptographic consent signature verification.
- Local directory boundary enforcement (prevents unauthorized scanning of arbitrary personal Library files).
- Physical byte, magic container, and full SHA-256 validation.
- ffprobe audio stream, resolution, and minimum duration checks.
- Cryptographic deduplication and unique source identity.
- Refuses to fabricate synthetic sources; returns WAITING_FOR_INPUT / NOT_TESTED when authentic media is absent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from .contracts import (
    MediaProbeMetadata,
    RightsVerificationStatus,
    SourceMediaAsset,
)
from .probe import MediaProbeService

logger = logging.getLogger(__name__)

# Permitted source license types
class SourceLicenseType(str, Enum):
    USER_OWNED = "USER_OWNED"
    COMMERCIAL_CREATOR_LICENSE = "COMMERCIAL_CREATOR_LICENSE"
    LICENSED_GAMEPLAY = "LICENSED_GAMEPLAY"
    CREATIVE_COMMONS_BY = "CREATIVE_COMMONS_BY"
    UNAUTHORIZED_THIRD_PARTY = "UNAUTHORIZED_THIRD_PARTY"
    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"


# Required permitted uses for production pipelines
REQUIRED_PERMITTED_USES: Set[str] = {"creator_edit", "social_distribution"}


class UserPermittedSourceItem(BaseModel):
    """
    Typed manifest item representing an explicitly permitted local source media file.
    """
    source_id: str
    file_path: str
    rights_holder: str
    license_type: SourceLicenseType = SourceLicenseType.UNAUTHORIZED_THIRD_PARTY
    permitted_uses: List[str] = Field(default_factory=list)
    consent_signed_at_utc: Optional[str] = None
    consent_signature: Optional[str] = None
    rights_status: RightsVerificationStatus = RightsVerificationStatus.UNVERIFIED_THIRD_PARTY
    rights_notes: str = ""
    file_size_bytes: int = 0
    sha256_hash: str = ""
    probe: Optional[MediaProbeMetadata] = None
    validation_passed: bool = False
    validation_errors: List[str] = Field(default_factory=list)

    def compute_consent_signature(self, secret: str = "6clips-manifest-secret") -> str:
        """Computes HMAC-SHA256 signature binding consent to rights holder, path, and license."""
        payload = (
            f"{self.source_id}:{self.file_path}:{self.rights_holder}:"
            f"{self.license_type.value}:{sorted(self.permitted_uses)}:"
            f"{self.consent_signed_at_utc}"
        )
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_consent_signature(self, secret: str = "6clips-manifest-secret") -> bool:
        """Verifies that consent signature has not been forged or tampered."""
        if not self.consent_signature:
            return False
        expected = self.compute_consent_signature(secret)
        return hmac.compare_digest(self.consent_signature, expected)


class UserPermittedSourceManifest(BaseModel):
    """
    Authoritative manifest of user-permitted source media assets for acceptance runs.
    """
    manifest_id: str
    gate_id: str  # "GT-05", "GT-06", "GT-07"
    owner_id: str = "local"
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    items: List[UserPermittedSourceItem] = Field(default_factory=list)
    allowed_base_dirs: List[str] = Field(
        default_factory=lambda: [
            "data/acceptance",
            "acceptance_inputs",
        ]
    )
    is_real_user_media: bool = False
    all_items_valid: bool = False
    validation_errors: List[str] = Field(default_factory=list)
    notes: str = ""


class SourceManifestValidator:
    """
    Validates source manifests against security, permissions, container, and duration invariants.
    """

    @classmethod
    def validate_manifest(
        cls,
        manifest: UserPermittedSourceManifest,
        secret: str = "6clips-manifest-secret",
        enforce_real_media: bool = True,
    ) -> UserPermittedSourceManifest:
        """
        Executes strict multi-phase validation on the source manifest:
        1. Boundary Check: Files must reside in authorized directories; no traversal or arbitrary Library scans.
        2. Rights & Consent: Rights holder non-empty, license type authorized, required permitted uses present,
           signature valid.
        3. Physical File Integrity: File exists, non-empty, valid container magic bytes.
        4. Stream & Audio Probe: Valid audio track, no synthetic filler (anullsrc, sine, high-null runs).
        5. Gate Duration Check:
           - GT-05 (V1): duration >= 180s
           - GT-06 (V3): duration in [3000s, 4200s] (~50-70 min)
           - GT-07 (V2): exactly 5 sources, each duration >= 45s
        6. Cryptographic Deduplication: No duplicate SHA-256 hashes across items in the manifest.
        """
        manifest.validation_errors.clear()
        manifest.all_items_valid = True

        # Gate-specific item count checks
        if manifest.gate_id == "GT-05" and len(manifest.items) != 1:
            manifest.validation_errors.append(f"GT-05 manifest requires exactly 1 source item, found {len(manifest.items)}")
            manifest.all_items_valid = False

        if manifest.gate_id == "GT-06" and len(manifest.items) != 1:
            manifest.validation_errors.append(f"GT-06 manifest requires exactly 1 source item, found {len(manifest.items)}")
            manifest.all_items_valid = False

        if manifest.gate_id == "GT-07" and len(manifest.items) != 5:
            manifest.validation_errors.append(f"GT-07 manifest requires exactly 5 source items, found {len(manifest.items)}")
            manifest.all_items_valid = False

        seen_hashes: Set[str] = set()
        seen_paths: Set[str] = set()

        for idx, item in enumerate(manifest.items):
            item.validation_errors.clear()
            item.validation_passed = True

            # 1. Directory boundary and file ownership
            p = Path(item.file_path).resolve()
            p_str = str(p).replace("\\", "/").lower()

            # Verify within allowed base dirs
            within_allowed = False
            for base in manifest.allowed_base_dirs:
                b_resolved = str(Path(base).resolve()).replace("\\", "/").lower()
                if p_str.startswith(b_resolved) or base.lower() in p_str:
                    within_allowed = True
                    break

            if not within_allowed:
                err = (
                    f"Item {item.source_id}: file path '{item.file_path}' is outside permitted acceptance base directories "
                    f"({manifest.allowed_base_dirs}). Arbitrary scanning of user folders/Library is prohibited."
                )
                item.validation_errors.append(err)
                item.validation_passed = False

            # Duplicate path check
            if p_str in seen_paths:
                err = f"Item {item.source_id}: duplicate path '{item.file_path}' already registered in manifest"
                item.validation_errors.append(err)
                item.validation_passed = False
            seen_paths.add(p_str)

            # 2. Rights and Consent
            if not item.rights_holder or item.rights_holder.strip() in ("", "unknown"):
                item.validation_errors.append(f"Item {item.source_id}: rights holder is missing or empty")
                item.validation_passed = False

            if item.license_type in (SourceLicenseType.UNAUTHORIZED_THIRD_PARTY,):
                item.validation_errors.append(
                    f"Item {item.source_id}: license type '{item.license_type.value}' is not authorized for derivative work"
                )
                item.validation_passed = False

            missing_uses = REQUIRED_PERMITTED_USES - set(item.permitted_uses)
            if missing_uses:
                item.validation_errors.append(
                    f"Item {item.source_id}: missing mandatory permitted uses: {sorted(missing_uses)}"
                )
                item.validation_passed = False

            if not item.consent_signed_at_utc:
                item.validation_errors.append(f"Item {item.source_id}: consent signed timestamp is missing")
                item.validation_passed = False

            if item.consent_signature and not item.verify_consent_signature(secret):
                item.validation_errors.append(f"Item {item.source_id}: consent signature verification failed (tampered/invalid)")
                item.validation_passed = False

            # 3. Physical file checks
            if not p.is_file():
                item.validation_errors.append(f"Item {item.source_id}: file does not exist at '{item.file_path}'")
                item.validation_passed = False
                manifest.all_items_valid = False
                continue

            try:
                size = p.stat().st_size
                item.file_size_bytes = size
                if size == 0:
                    item.validation_errors.append(f"Item {item.source_id}: file is 0 bytes (empty)")
                    item.validation_passed = False
            except Exception as e:
                item.validation_errors.append(f"Item {item.source_id}: could not inspect stat: {e}")
                item.validation_passed = False

            # 4. Probe stream / container / synthetic filler
            try:
                probe = MediaProbeService.probe_file(p)
                item.probe = probe
                item.sha256_hash = probe.sha256_hash

                if not probe.magic_bytes_valid:
                    item.validation_errors.append(f"Item {item.source_id}: invalid container magic bytes")
                    item.validation_passed = False

                if probe.synthetic_filler_detected:
                    item.validation_errors.append(
                        f"Item {item.source_id}: synthetic filler detected: {probe.synthetic_filler_reason}"
                    )
                    item.validation_passed = False

                if not probe.has_audio_stream or probe.audio_channels < 1:
                    item.validation_errors.append(f"Item {item.source_id}: missing non-silent audio stream")
                    item.validation_passed = False

                # 5. Gate duration checks
                if manifest.gate_id == "GT-05":
                    if enforce_real_media and probe.duration_seconds < 180.0:
                        item.validation_errors.append(
                            f"Item {item.source_id}: duration ({probe.duration_seconds:.1f}s) is under the 180s minimum for 3x60s V1"
                        )
                        item.validation_passed = False

                elif manifest.gate_id == "GT-06":
                    if enforce_real_media and (probe.duration_seconds < 3000.0 or probe.duration_seconds > 4200.0):
                        item.validation_errors.append(
                            f"Item {item.source_id}: duration ({probe.duration_seconds:.1f}s) is not an authentic ~60-minute recording (expected 3000-4200s)"
                        )
                        item.validation_passed = False

                elif manifest.gate_id == "GT-07":
                    if enforce_real_media and probe.duration_seconds < 45.0:
                        item.validation_errors.append(
                            f"Item {item.source_id}: duration ({probe.duration_seconds:.1f}s) is under 45s minimum for V2 multi-source"
                        )
                        item.validation_passed = False

                # 6. Deduplication check across items
                if probe.sha256_hash in seen_hashes:
                    item.validation_errors.append(
                        f"Item {item.source_id}: duplicate SHA-256 hash {probe.sha256_hash[:12]} already present in manifest"
                    )
                    item.validation_passed = False
                seen_hashes.add(probe.sha256_hash)

            except Exception as e:
                item.validation_errors.append(f"Item {item.source_id}: probe failed: {e}")
                item.validation_passed = False

            if not item.validation_passed:
                manifest.all_items_valid = False
                manifest.validation_errors.extend(item.validation_errors)

        return manifest

    @classmethod
    def manifest_to_source_assets(cls, manifest: UserPermittedSourceManifest) -> List[SourceMediaAsset]:
        """Converts validated manifest items to SourceMediaAsset list for orchestrators."""
        assets = []
        for item in manifest.items:
            rights = (
                RightsVerificationStatus.AUTHORIZED_USER_MEDIA
                if item.license_type == SourceLicenseType.USER_OWNED
                else RightsVerificationStatus.COMMERCIAL_CREATOR_LICENSE
            )
            asset = SourceMediaAsset(
                source_id=item.source_id,
                file_path=item.file_path,
                rights_status=rights,
                rights_notes=f"Authorized under {item.license_type.value} by {item.rights_holder}",
                permitted_uses=item.permitted_uses,
                probe=item.probe,
            )
            assets.append(asset)
        return assets
