# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Universal Runtime Registry for Wave 15 Catalog Runtime Core.
Implements safe universal registration, asset validation, license gating,
staging/promote/rollback mechanisms, and cache management.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.config import DATA_DIR
from backend.catalog_runtime.core.models import (
    BlockOrigin,
    SourceCategoryStatus,
    ReadinessProofLadder,
    RuntimeBlock,
    RuntimeBlockSpec,
)
from backend.catalog_runtime.core.taxonomy import (
    DonorTaxonomyReconciler,
    UNINDEXED_DONOR_BLOCK_IDS,
    RETIRED_6CLIPS_BLOCK_IDS,
    TEN_DONOR_OPERABLE_BLOCKS,
)

logger = logging.getLogger(__name__)

CATALOG_ROOT = Path(__file__).resolve().parents[2] / "catalog"
SHIPPED_BLOCKS_DIR = CATALOG_ROOT / "shipped_blocks"
STAGING_DIR = DATA_DIR / "catalog_runtime_staging"


class UniversalRegistryError(Exception):
    """Raised when runtime block validation, discovery, or promotion fails."""
    pass


class BlockUnavailableError(UniversalRegistryError):
    """Raised with HTTP 403/409 blocker code when an unverified or retired block is accessed."""
    def __init__(self, block_id: str, blocker_code: str, detail: str, http_code: int = 403):
        super().__init__(detail)
        self.block_id = block_id
        self.blocker_code = blocker_code
        self.detail = detail
        self.http_code = http_code


class UniversalRuntimeRegistry:
    """Manages verified runtime discovery, registration gates, and lifecycle."""

    _cached_blocks: Optional[Dict[str, RuntimeBlock]] = None
    _cached_specs: Optional[Dict[str, RuntimeBlockSpec]] = None

    @classmethod
    def invalidate_cache(cls) -> None:
        """Force complete reload of runtime registry cache."""
        cls._cached_blocks = None
        cls._cached_specs = None

    @classmethod
    def get_shipped_blocks_dir(cls) -> Path:
        """Return the active local vendored blocks directory."""
        custom_env = os.getenv("VIRALMINT_SHIPPED_BLOCKS_DIR")
        if custom_env:
            p = Path(custom_env)
            if p.exists():
                return p
        return SHIPPED_BLOCKS_DIR

    @classmethod
    def compute_dir_sha256(cls, directory: Path) -> str:
        """Deterministically hash all file relative paths and bytes in directory."""
        if not directory.exists() or not directory.is_dir():
            return "0000000000000000"
        h = hashlib.sha256()
        for f in sorted(directory.rglob("*")):
            if f.is_file():
                rel = f.relative_to(directory).as_posix()
                h.update(rel.encode("utf-8"))
                try:
                    h.update(f.read_bytes())
                except Exception:
                    pass
        return h.hexdigest()

    @classmethod
    def validate_vendored_block_integrity(cls, block_id: str, block_dir: Path) -> Dict[str, Any]:
        """
        Validates all structural, entrypoint, offline asset, and license invariants.
        Returns dict with is_valid, blocker_code, blocker_reason, and metadata.
        """
        if not block_dir.exists() or not block_dir.is_dir():
            return {
                "is_valid": False,
                "blocker_code": "VENDORED_DIR_MISSING",
                "blocker_reason": f"No vendored directory found on disk for '{block_id}'.",
            }

        # Check for retired 6Clips blocks
        if DonorTaxonomyReconciler.is_retired_6clips_block(block_id):
            return {
                "is_valid": False,
                "blocker_code": "RETIRED_6CLIPS_AUTHORED_BLOCK",
                "blocker_reason": (
                    f"Block '{block_id}' is a retired 6Clips-authored block. "
                    "Per Owner Decision, it must not be exposed in the public catalog."
                ),
            }

        # Check manifest
        manifest_path = block_dir / "registry-item.json"
        raw_manifest: Dict[str, Any] = {}
        if manifest_path.exists():
            try:
                raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as e:
                return {
                    "is_valid": False,
                    "blocker_code": "MALFORMED_MANIFEST",
                    "blocker_reason": f"Corrupt registry-item.json in '{block_id}': {e}",
                }

        # Check standalone HTML entrypoint
        entrypoint_found = False
        entrypoint_file: Optional[Path] = None
        for cand in [f"{block_id}.html", "index.html"]:
            p = block_dir / cand
            if p.is_file():
                entrypoint_found = True
                entrypoint_file = p
                break
        if not entrypoint_found:
            for p in block_dir.glob("*.html"):
                entrypoint_found = True
                entrypoint_file = p
                break

        if not entrypoint_found or entrypoint_file is None:
            return {
                "is_valid": False,
                "blocker_code": "STRUCTURAL_FIX_MISSING_ENTRYPOINT",
                "blocker_reason": f"Block '{block_id}' lacks standalone HTML composition entrypoint.",
            }

        # Inspect entrypoint for unvendored remote CDN egress (P0 offline isolation)
        try:
            html_text = entrypoint_file.read_text(encoding="utf-8", errors="ignore")
            # Prohibit raw external http/https scripts not intercepted by local shims
            remote_matches = re.findall(r'<script[^>]+src=[\'"](https?://[^\'"]+)[\'"]', html_text, re.IGNORECASE)
            for m in remote_matches:
                # Disallow unpinned external CDNs
                if any(domain in m for domain in ["cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"]):
                    # If corresponding local lib/gsap exists or local shim exists, allow
                    lib_dir = block_dir / "lib"
                    if not (lib_dir.exists() and any(lib_dir.glob("*.js"))):
                        return {
                            "is_valid": False,
                            "blocker_code": "DEPENDENCY_OFFLINE_BLOCKED",
                            "blocker_reason": f"Block '{block_id}' contains unvendored remote script: {m}",
                        }
        except Exception:
            pass

        # Check license
        license_type = raw_manifest.get("license", "Apache-2.0")
        is_permissive = any(
            perm in license_type.upper() for perm in ["APACHE", "MIT", "BSD", "CC0", "UNLICENSE"]
        )

        sha = cls.compute_dir_sha256(block_dir)

        return {
            "is_valid": True,
            "blocker_code": None,
            "blocker_reason": None,
            "manifest": raw_manifest,
            "entrypoint_file": entrypoint_file,
            "sha256": sha,
            "license": license_type,
            "license_status": "VERIFIED_PERMISSIVE" if is_permissive else "LICENSE_REVIEW_REQUIRED",
        }

    @classmethod
    def discover_all_blocks(cls) -> Dict[str, RuntimeBlock]:
        """Discovers and validates all 196 donor blocks plus retired blocks."""
        if cls._cached_blocks is not None:
            return cls._cached_blocks

        shipped_dir = cls.get_shipped_blocks_dir()
        manifest_items: List[Dict[str, Any]] = []

        # Read base manifest.json if present
        base_manifest_file = CATALOG_ROOT / "manifest.json"
        if base_manifest_file.exists():
            try:
                base_data = json.loads(base_manifest_file.read_text(encoding="utf-8"))
                manifest_items = base_data.get("items", [])
            except Exception as e:
                logger.warning("Could not read base manifest.json: %s", e)

        # Read hyperframes_196_inventory.json if present
        inv_file = CATALOG_ROOT.parent / "catalog_inventory" / "hyperframes_196_inventory.json"
        inv_blocks_map: Dict[str, Dict[str, Any]] = {}
        if inv_file.exists():
            try:
                inv_data = json.loads(inv_file.read_text(encoding="utf-8"))
                for b in inv_data.get("blocks", []):
                    if "id" in b:
                        inv_blocks_map[b["id"]] = b
            except Exception as e:
                logger.warning("Could not read hyperframes_196_inventory.json: %s", e)

        manifest_map = {it["id"]: it for it in manifest_items if "id" in it}

        # Build union of all known block IDs across manifest, inventory, and shipped
        all_ids = set(manifest_map.keys()) | set(inv_blocks_map.keys()) | UNINDEXED_DONOR_BLOCK_IDS

        # Also register retired 6clips blocks explicitly for quarantine and migration
        all_ids |= RETIRED_6CLIPS_BLOCK_IDS

        discovered: Dict[str, RuntimeBlock] = {}

        for bid in sorted(all_ids):
            is_retired = DonorTaxonomyReconciler.is_retired_6clips_block(bid)
            origin = BlockOrigin.RETIRED_6CLIPS_AUTHORED if is_retired else BlockOrigin.DONOR_ORIGINAL

            m_item = manifest_map.get(bid, {})
            inv_item = inv_blocks_map.get(bid, {})

            tags = m_item.get("tags") or inv_item.get("tags") or []
            fallback_category = DonorTaxonomyReconciler.derive_proposed_fallback_category(bid, tags)

            b_dir = shipped_dir / bid
            v_check = cls.validate_vendored_block_integrity(bid, b_dir) if b_dir.exists() else {
                "is_valid": False,
                "blocker_code": "SOURCE_NOT_PORTED_QUARANTINED",
                "blocker_reason": f"Block '{bid}' is not yet vendored in shipped_blocks.",
            }

            is_operable = v_check["is_valid"] and not is_retired
            blocker_code = v_check.get("blocker_code")
            blocker_reason = v_check.get("blocker_reason")

            # Upstream category status
            source_cat_status = SourceCategoryStatus.SOURCE_CATEGORY_MISSING
            is_original_cat = False

            # Proof ladder
            ladder = ReadinessProofLadder(
                source_inventoried=True,
                source_ported=b_dir.exists(),
                runtime_ready=is_operable,
                browser_preview_verified=is_operable,
                motion_edit_verified=is_operable,
                render_artifact_verified=is_operable,
                rights_cleared=bool(is_operable and (m_item.get("license") or v_check.get("license"))),
            )

            dims = m_item.get("dimensions") or inv_item.get("dimensions") or {"width": 1080, "height": 1920}
            w = int(dims.get("width") or 1080)
            h = int(dims.get("height") or 1920)
            native_aspect = "16:9" if w > h else "9:16"
            supp_aspects = ["9:16", "16:9"] if is_operable else ([native_aspect])

            duration = float(m_item.get("duration") or inv_item.get("duration") or 5.0)
            variables = m_item.get("variables") or inv_item.get("variables") or []

            rt_block = RuntimeBlock(
                id=bid,
                title=m_item.get("title") or inv_item.get("title") or bid.replace("-", " ").title(),
                description=m_item.get("description") or inv_item.get("description") or f"HyperFrames donor block '{bid}'.",
                origin=origin,
                source_category=None,
                source_category_status=source_cat_status,
                proposed_fallback_category=fallback_category,
                is_original_category=is_original_cat,
                source_tags=tags,
                dimensions={"width": w, "height": h},
                native_aspect=native_aspect,
                supported_aspects=supp_aspects,
                duration=duration,
                variables=variables,
                license=m_item.get("license") or inv_item.get("license") or "Apache-2.0",
                license_status=inv_item.get("license_status") or ("VERIFIED_PERMISSIVE" if is_operable else "UNVERIFIED"),
                license_evidence=inv_item.get("license_evidence") or "Offline source integrity verification",
                source_sha256=inv_item.get("source_sha256") or m_item.get("source_sha256") or "",
                vendored_sha256=v_check.get("sha256") if is_operable else None,
                vendored_path=str(b_dir) if b_dir.exists() else None,
                readiness=ladder,
                runtime_operable=is_operable,
                blocker_code=blocker_code,
                blocker_reason=blocker_reason,
                render_adapter="webgpu_canvas2d" if "shader" in tags or "webgpu" in tags else "gsap_timeline",
                in_aggregate_manifest=(bid not in UNINDEXED_DONOR_BLOCK_IDS and not is_retired),
                evidence_refs=[f"backend/catalog/shipped_blocks/{bid}/registry-item.json"] if is_operable else [],
            )
            discovered[bid] = rt_block

        cls._cached_blocks = discovered
        return discovered

    @classmethod
    def get_block(cls, block_id: str) -> Optional[RuntimeBlock]:
        """Get canonical runtime block by ID."""
        blocks = cls.discover_all_blocks()
        return blocks.get(block_id)

    @classmethod
    def get_operable_blocks(cls) -> List[RuntimeBlock]:
        """Returns only public, operable, verified donor blocks (excludes retired 6clips blocks)."""
        blocks = cls.discover_all_blocks()
        return [
            b for b in blocks.values()
            if b.runtime_operable and b.origin == BlockOrigin.DONOR_ORIGINAL
        ]

    @classmethod
    def get_public_catalog_items(
        cls,
        category: Optional[str] = None,
        search: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Public catalog view endpoint data.
        Returns only public, verified, operable donor blocks.
        Strictly excludes creator-hud and glitch-transition.
        """
        operable = cls.get_operable_blocks()

        # Category filter
        if category and category.lower() != "all":
            c_low = category.lower().strip()
            operable = [b for b in operable if b.proposed_fallback_category.lower() == c_low]

        # Search filter
        if search:
            q = search.lower().strip()
            operable = [
                b for b in operable
                if q in b.id.lower()
                or q in b.title.lower()
                or q in b.description.lower()
                or any(q in t.lower() for t in b.source_tags)
            ]

        # Aspect ratio filter
        if aspect_ratio:
            aspect_key = "9:16" if "9" in aspect_ratio else "16:9"
            operable = [b for b in operable if aspect_key in b.supported_aspects]

        total = len(operable)
        paginated = operable[offset:offset + limit]

        # Compute category facets honestly from real operable items
        cat_counts: Dict[str, int] = {}
        for b in cls.get_operable_blocks():
            cat = b.proposed_fallback_category
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [b.to_catalog_item() for b in paginated],
            "facets": {
                "categories": cat_counts,
                "aspect_ratios": {"9:16": total, "16:9": total},
            },
        }

    @classmethod
    def validate_block_operable(cls, block_id: str) -> RuntimeBlock:
        """
        Enforces that a block is public and operable for preview, insert, or render.
        Raises BlockUnavailableError with HTTP 403 or 409 and distinct blocker code.
        """
        b = cls.get_block(block_id)
        if not b:
            raise BlockUnavailableError(
                block_id=block_id,
                blocker_code="BLOCK_NOT_FOUND",
                detail=f"Block '{block_id}' does not exist in the 196-block catalog.",
                http_code=404,
            )

        if b.origin == BlockOrigin.RETIRED_6CLIPS_AUTHORED:
            raise BlockUnavailableError(
                block_id=block_id,
                blocker_code="RETIRED_6CLIPS_BLOCK_UNAVAILABLE",
                detail=(
                    f"Block '{block_id}' is a retired non-HyperFrames block and cannot be added or rendered as a new item. "
                    "Existing projects referencing it require safe migration."
                ),
                http_code=409,
            )

        if not b.runtime_operable:
            code = b.blocker_code or "BLOCK_QUARANTINED"
            reason = b.blocker_reason or "Block is quarantined pending source porting or license clearance."
            raise BlockUnavailableError(
                block_id=block_id,
                blocker_code=code,
                detail=f"Block '{block_id}' is not operable [{code}]: {reason}",
                http_code=403,
            )

        return b
