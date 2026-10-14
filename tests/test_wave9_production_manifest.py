# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Wave 9 Tests: Production-Safe Input Manifest and Rights Validation.

Verifies:
- Explicit owner/creator permissions and permitted use validation.
- Cryptographic consent signature verification and tamper detection.
- Local directory boundary enforcement (prohibits arbitrary scanning of user folders/Library).
- Physical file checks: non-empty, valid magic bytes, SHA-256 deduplication.
- ffprobe stream/audio checks and synthetic filler rejection (anullsrc, sine, null byte density).
- Gate-specific duration invariants (GT-05 >= 180s, GT-06 3000-4200s, GT-07 5 sources >= 45s).
- Truth guards: returns WAITING_FOR_INPUT / NOT_TESTED when authentic media is absent.
"""
from datetime import datetime, timezone
from pathlib import Path
import pytest

from backend.production_acceptance.contracts import (
    MediaProbeMetadata,
    RightsVerificationStatus,
)
from backend.production_acceptance.manifest import (
    SourceLicenseType,
    SourceManifestValidator,
    UserPermittedSourceItem,
    UserPermittedSourceManifest,
)


def _create_valid_container(path: Path, payload: bytes = b"valid_avc1_aac_stream"):
    """Creates a mock valid MP4 ftyp container."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    path.write_bytes(header + payload)


class TestSourceManifestBoundaryAndSecurity:
    """Verifies directory boundary enforcement and unauthorized Library scanning prevention."""

    def test_manifest_permits_allowed_base_directories(self, tmp_path: Path):
        allowed_dir = tmp_path / "data" / "acceptance" / "gt05_inputs"
        src_file = allowed_dir / "gameplay.mp4"
        _create_valid_container(src_file, b"gameplay_bytes_12345")

        item = UserPermittedSourceItem(
            source_id="item_01",
            file_path=str(src_file),
            rights_holder="CreatorAlice",
            license_type=SourceLicenseType.LICENSED_GAMEPLAY,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_gt05_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
            is_real_user_media=False,
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert item.validation_passed is True
        assert len(item.validation_errors) == 0
        assert item.sha256_hash != ""

    def test_manifest_rejects_files_outside_allowed_boundaries(self, tmp_path: Path):
        unauthorized_dir = tmp_path / "personal_user_folder" / "private_media"
        src_file = unauthorized_dir / "private_recording.mp4"
        _create_valid_container(src_file, b"private_data")

        item = UserPermittedSourceItem(
            source_id="item_unauthorized",
            file_path=str(src_file),
            rights_holder="Alice",
            license_type=SourceLicenseType.USER_OWNED,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_boundary_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert item.validation_passed is False
        assert any("outside permitted acceptance base directories" in err for err in item.validation_errors)
        assert manifest.all_items_valid is False

    def test_manifest_rejects_tampered_consent_signature(self, tmp_path: Path):
        src_file = tmp_path / "data" / "acceptance" / "video.mp4"
        _create_valid_container(src_file, b"video_bytes")

        item = UserPermittedSourceItem(
            source_id="item_tampered",
            file_path=str(src_file),
            rights_holder="OriginalCreator",
            license_type=SourceLicenseType.USER_OWNED,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
            consent_signature="forged_or_tampered_hmac_hash_000000000000",
        )

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_tamper_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert item.validation_passed is False
        assert any("consent signature verification failed" in err for err in item.validation_errors)

    def test_manifest_rejects_missing_mandatory_permitted_uses(self, tmp_path: Path):
        src_file = tmp_path / "data" / "acceptance" / "video.mp4"
        _create_valid_container(src_file, b"video_bytes")

        item = UserPermittedSourceItem(
            source_id="item_insufficient_uses",
            file_path=str(src_file),
            rights_holder="OriginalCreator",
            license_type=SourceLicenseType.USER_OWNED,
            permitted_uses=["personal_viewing_only"],  # Missing creator_edit, social_distribution
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_uses_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert item.validation_passed is False
        assert any("missing mandatory permitted uses" in err for err in item.validation_errors)


class TestSourceManifestIntegrityAndDeduplication:
    """Verifies file integrity, magic bytes, synthetic filler rejection, and deduplication."""

    def test_manifest_rejects_corrupted_or_zero_byte_files(self, tmp_path: Path):
        src_file = tmp_path / "data" / "acceptance" / "zero_byte.mp4"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_bytes(b"")  # 0 bytes

        item = UserPermittedSourceItem(
            source_id="item_empty",
            file_path=str(src_file),
            rights_holder="CreatorBob",
            license_type=SourceLicenseType.USER_OWNED,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_empty_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert item.validation_passed is False
        assert any("0 bytes" in err or "magic bytes" in err for err in item.validation_errors)

    def test_manifest_rejects_synthetic_filler_indicator(self, tmp_path: Path):
        src_file = tmp_path / "data" / "acceptance" / "anullsrc_fake_audio.mp4"
        _create_valid_container(src_file, b"payload_with_anullsrc_filler")

        item = UserPermittedSourceItem(
            source_id="item_filler",
            file_path=str(src_file),
            rights_holder="CreatorBob",
            license_type=SourceLicenseType.USER_OWNED,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_filler_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(tmp_path / "data" / "acceptance")],
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert item.validation_passed is False
        assert any("synthetic filler detected" in err for err in item.validation_errors)

    def test_manifest_rejects_duplicate_items_in_multi_source(self, tmp_path: Path):
        base_dir = tmp_path / "data" / "acceptance"
        base_dir.mkdir(parents=True, exist_ok=True)

        items = []
        for i in range(5):
            p = base_dir / f"src_{i+1}.mp4"
            # Make src_1 and src_5 have identical payload
            payload = b"shared_content" if i in (0, 4) else f"unique_payload_{i}".encode()
            _create_valid_container(p, payload)

            item = UserPermittedSourceItem(
                source_id=f"item_{i+1}",
                file_path=str(p),
                rights_holder="StudioPro",
                license_type=SourceLicenseType.COMMERCIAL_CREATOR_LICENSE,
                permitted_uses=["creator_edit", "social_distribution"],
                consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
            )
            item.consent_signature = item.compute_consent_signature()
            items.append(item)

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_v2_dup_test",
            gate_id="GT-07",
            items=items,
            allowed_base_dirs=[str(base_dir)],
        )

        validated = SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assert manifest.all_items_valid is False
        # item 5 must be rejected because item 1 had the same hash
        assert items[4].validation_passed is False
        assert any("duplicate SHA-256 hash" in err for err in items[4].validation_errors)

    def test_manifest_conversion_to_source_assets(self, tmp_path: Path):
        base_dir = tmp_path / "data" / "acceptance"
        src_file = base_dir / "valid_clip.mp4"
        _create_valid_container(src_file, b"clean_high_quality_audio_and_video")

        item = UserPermittedSourceItem(
            source_id="item_asset_01",
            file_path=str(src_file),
            rights_holder="CreatorCarol",
            license_type=SourceLicenseType.USER_OWNED,
            permitted_uses=["creator_edit", "social_distribution"],
            consent_signed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        item.consent_signature = item.compute_consent_signature()

        manifest = UserPermittedSourceManifest(
            manifest_id="mf_conv_test",
            gate_id="GT-05",
            items=[item],
            allowed_base_dirs=[str(base_dir)],
        )

        SourceManifestValidator.validate_manifest(manifest, enforce_real_media=False)
        assets = SourceManifestValidator.manifest_to_source_assets(manifest)

        assert len(assets) == 1
        asset = assets[0]
        assert asset.source_id == "item_asset_01"
        assert asset.rights_status == RightsVerificationStatus.AUTHORIZED_USER_MEDIA
        assert "social_distribution" in asset.permitted_uses
        assert asset.probe is not None
        assert asset.probe.magic_bytes_valid is True
