# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog Manifest Service: provides typed, cached access to the canonical 196-block catalog manifest."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).parent / "manifest.json"


class CatalogManifestError(Exception):
    """Raised on invalid catalog requests or malformed manifest state."""
    pass


class CatalogManifestService:
    """Manages the canonical 6Clips HyperFrames block catalog manifest."""

    _cached_data: Optional[Dict[str, Any]] = None
    _items_by_id: Optional[Dict[str, Dict[str, Any]]] = None

    @classmethod
    def _load_manifest(cls) -> Dict[str, Any]:
        if cls._cached_data is not None:
            return cls._cached_data

        if not MANIFEST_PATH.exists():
            raise CatalogManifestError(f"Canonical catalog manifest not found at {MANIFEST_PATH}")

        try:
            raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            cls._cached_data = raw
            items = raw.get("items", [])
            cls._items_by_id = {it["id"]: it for it in items if "id" in it}
            return raw
        except Exception as e:
            logger.error("Failed to parse catalog manifest.json: %s", e)
            raise CatalogManifestError(f"Corrupt manifest: {e}") from e

    @classmethod
    def invalidate_cache(cls) -> None:
        """Force reload of the manifest on next access."""
        cls._cached_data = None
        cls._items_by_id = None

    @classmethod
    def validate_block_id(cls, block_id: str) -> None:
        """Reject invalid block identifiers, path traversal attempts, and injection payloads."""
        if not block_id or not isinstance(block_id, str):
            raise CatalogManifestError("Block ID must be a non-empty string.")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", block_id) or ".." in block_id or "/" in block_id or "\\" in block_id:
            raise CatalogManifestError(f"Disallowed block identifier: '{block_id}'")

    @classmethod
    def get_all_items(cls) -> List[Dict[str, Any]]:
        """Return all catalog blocks from the manifest."""
        data = cls._load_manifest()
        return list(data.get("items", []))

    @classmethod
    def get_item(cls, block_id: str) -> Optional[Dict[str, Any]]:
        """Return single catalog item by ID, or None if not found."""
        cls.validate_block_id(block_id)
        cls._load_manifest()
        if cls._items_by_id is None:
            return None
        return cls._items_by_id.get(block_id)

    @classmethod
    def list_items(
        cls,
        category: Optional[str] = None,
        search: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        disposition: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Faceted listing over the catalog items.
        Filters:
          - category: call-to-action, typography, lower-thirds, charts, transitions, backgrounds, mock-ui, general
          - search: case-insensitive query over id, title, description, tags
          - aspect_ratio: "9:16" or "16:9" (filters for blocks that support it with NATIVE or ADAPTED)
          - disposition: "SHIP", "FIX", "UNSUPPORTED"
        """
        items = cls.get_all_items()

        # Category filter
        if category and category.lower() != "all":
            c_lower = category.lower()
            items = [it for it in items if it.get("category", "").lower() == c_lower]

        # Search filter
        if search:
            q = search.lower().strip()
            items = [
                it for it in items
                if q in it.get("id", "").lower()
                or q in it.get("title", "").lower()
                or q in it.get("description", "").lower()
                or any(q in t.lower() for t in it.get("tags", []))
            ]

        # Aspect ratio filter
        if aspect_ratio:
            aspect_key = "aspect_9_16" if aspect_ratio == "9:16" else "aspect_16_9"
            items = [
                it for it in items
                if it.get(aspect_key) in ("NATIVE", "ADAPTED", "CONTAINED_ONLY")
            ]

        # Disposition filter
        if disposition and disposition.upper() != "ALL":
            d_upper = disposition.upper()
            items = [it for it in items if it.get("disposition", "").upper() == d_upper]

        total = len(items)
        paged = items[offset:offset + limit]

        # Facet counts
        all_items = cls.get_all_items()
        categories: Dict[str, int] = {}
        dispositions: Dict[str, int] = {}
        for it in all_items:
            cat = it.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1
            disp = it.get("disposition", "SHIP")
            dispositions[disp] = dispositions.get(disp, 0) + 1

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": paged,
            "facets": {
                "categories": categories,
                "dispositions": dispositions,
                "total_catalog_blocks": len(all_items),
            },
        }

    @classmethod
    def get_reconciliation_summary(cls) -> Dict[str, Any]:
        """
        Returns the evidence-backed inventory reconciliation metrics:
        196 block directories, 170 aggregate items, 26 unbundled items,
        236/222 microcomponents, and 8 examples.
        """
        data = cls._load_manifest()
        recon = data.get("reconciliation", {})
        items = cls.get_all_items()

        ship_count = sum(1 for it in items if it.get("disposition") == "SHIP")
        fix_count = sum(1 for it in items if it.get("disposition") == "FIX")
        unsupported_count = sum(1 for it in items if it.get("disposition") == "UNSUPPORTED")

        return {
            "reconciliation": recon,
            "block_inventory": {
                "total_blocks": len(items),
                "ship": ship_count,
                "fix": fix_count,
                "unsupported": unsupported_count,
            },
            "unbundled_blocks": [it["id"] for it in items if not it.get("in_aggregate_manifest")],
            "aspect_support_9_16": {
                "native": sum(1 for it in items if it.get("aspect_9_16") == "NATIVE"),
                "adapted": sum(1 for it in items if it.get("aspect_9_16") == "ADAPTED"),
                "contained_only": sum(1 for it in items if it.get("aspect_9_16") == "CONTAINED_ONLY"),
            },
            "aspect_support_16_9": {
                "native": sum(1 for it in items if it.get("aspect_16_9") == "NATIVE"),
                "contained_only": sum(1 for it in items if it.get("aspect_16_9") == "CONTAINED_ONLY"),
            },
        }

    @classmethod
    def get_license_inventory(cls) -> List[Dict[str, Any]]:
        """Return license attribution and dependency inventory for all blocks."""
        items = cls.get_all_items()
        inventory = []
        for it in items:
            inventory.append({
                "id": it["id"],
                "title": it["title"],
                "license": it.get("license", "Apache-2.0"),
                "author": it.get("author", "HyperFrames"),
                "deps": it.get("deps", []),
                "disposition": it.get("disposition", "SHIP"),
            })
        return inventory
