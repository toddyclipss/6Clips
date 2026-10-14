# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Catalog Poster Service: generates, caches, and serves truthful visual posters for catalog blocks."""
from __future__ import annotations

import hashlib
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from backend.config import DATA_DIR, settings
from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError

logger = logging.getLogger(__name__)

POSTER_CACHE_DIR = settings.STORAGE_ROOT / "catalog_posters"
POSTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

CATEGORY_PALETTES = {
    "call-to-action": ((255, 61, 113), (120, 10, 50)),
    "typography": ((13, 148, 136), (15, 23, 42)),
    "lower-thirds": ((59, 130, 246), (15, 23, 42)),
    "charts": ((16, 185, 129), (6, 78, 59)),
    "transitions": ((168, 85, 247), (76, 29, 149)),
    "backgrounds": ((236, 72, 153), (30, 27, 75)),
    "mock-ui": ((245, 158, 11), (69, 26, 3)),
    "general": ((100, 116, 139), (15, 23, 42)),
}


class CatalogPosterError(Exception):
    """Raised when poster resolution fails or inputs are invalid."""
    pass


class CatalogPosterService:
    """Provides authentic, cached posters with deterministic invalidation."""

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Return and ensure poster cache directory exists."""
        POSTER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return POSTER_CACHE_DIR

    @classmethod
    def compute_variable_fingerprint(cls, variables: Optional[Dict[str, Any]]) -> Optional[str]:
        """Compute deterministic 8-char fingerprint from variable dictionary."""
        if not variables:
            return None
        serialized = json.dumps(variables, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()[:8]

    @classmethod
    def get_poster_path(
        cls,
        block_id: str,
        version_hash: Optional[str] = None,
        aspect_ratio: str = "9:16",
        variable_fingerprint: Optional[str] = None,
    ) -> Path:
        """
        Return the on-disk Path to a truthful cached poster image (PNG).
        Generates and caches on demand if not present.
        """
        CatalogManifestService.validate_block_id(block_id)
        item = CatalogManifestService.get_item(block_id)
        if not item:
            raise CatalogPosterError(f"Catalog block '{block_id}' not found.")

        aspect_norm = "9:16" if aspect_ratio in ("9:16", "9x16", "vertical") else "16:9"
        aspect_tag = "9x16" if aspect_norm == "9:16" else "16x9"
        ver = version_hash or "v1"
        vfp = f"_{variable_fingerprint}" if variable_fingerprint else ""
        cache_key = f"{block_id}_{ver}_{aspect_tag}{vfp}.png"

        cache_dir = cls.get_cache_dir().resolve()
        target_file = (cache_dir / cache_key).resolve()
        if not str(target_file).startswith(str(cache_dir)):
            raise CatalogPosterError("Path traversal violation in poster cache path.")

        if target_file.is_file() and target_file.stat().st_size > 0:
            return target_file

        w, h = (360, 640) if aspect_norm == "9:16" else (640, 360)

        # 1. Check if shipped block has local image
        shipped_dir = Path(__file__).parent / "shipped_blocks" / block_id
        if shipped_dir.exists():
            for cand in ["poster.png", "poster.jpg", "preview.png", "thumbnail.png"]:
                p = shipped_dir / cand
                if p.is_file():
                    try:
                        with Image.open(p) as im:
                            resized = im.convert("RGB").resize((w, h), Image.Resampling.LANCZOS)
                            resized.save(target_file, format="PNG")
                            return target_file
                    except Exception as e:
                        logger.debug("Failed resizing shipped poster %s: %s", p, e)

        # 2. Offline-only enforcement: zero external egress (P0 idle guardrail)
        # Upstream remote downloads are strictly disabled to prevent network activity during catalog operations.

        # 3. Generate high-quality truthful graphical representation card offline
        cls._generate_card_poster(target_file, item, w, h, aspect_norm)
        return target_file

    @classmethod
    def _generate_card_poster(
        cls,
        target_path: Path,
        item: dict,
        w: int,
        h: int,
        aspect_ratio: str,
    ) -> None:
        """Draw an authentic, branded vector/raster card identifying the block without deceptive claims."""
        cat = item.get("category", "general")
        accent_color, bg_color = CATEGORY_PALETTES.get(cat, ((100, 116, 139), (15, 23, 42)))

        img = Image.new("RGB", (w, h), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Draw subtle diagonal accent stripes
        for i in range(-h, w + h, 40):
            draw.line([(i, 0), (i + h, h)], fill=(bg_color[0] + 8, bg_color[1] + 8, bg_color[2] + 12), width=18)

        # Header accent bar
        draw.rectangle([(0, 0), (w, 8)], fill=accent_color)

        # Load default font or draw readable text
        title = item.get("title", item.get("id", "Block"))
        author = item.get("author", "HyperFrames")
        license_name = item.get("license", "Apache-2.0")

        # Aspect badge & Category badge
        draw.rectangle([(16, 20), (16 + len(cat) * 9 + 16, 42)], fill=accent_color)
        draw.text((22, 24), cat.upper(), fill=(255, 255, 255))

        draw.rectangle([(w - 74, 20), (w - 16, 42)], fill=(30, 41, 59))
        draw.text((w - 66, 24), aspect_ratio, fill=(148, 163, 184))

        # Block Title
        # Simple word wrap
        words = title.split()
        lines = []
        cur = []
        for word in words:
            if len(" ".join(cur + [word])) > (22 if w < 400 else 36):
                lines.append(" ".join(cur))
                cur = [word]
            else:
                cur.append(word)
        if cur:
            lines.append(" ".join(cur))

        y_offset = (h // 2) - (len(lines) * 16)
        for line in lines[:3]:
            draw.text((20, y_offset), line, fill=(248, 250, 252))
            y_offset += 28

        # Footer metadata
        draw.line([(16, h - 44), (w - 16, h - 44)], fill=(51, 65, 85), width=1)
        draw.text((20, h - 34), f"{author} · {license_name}", fill=(148, 163, 184))

        disp = item.get("disposition", "SHIP")
        disp_color = (34, 197, 94) if disp == "SHIP" else (234, 179, 8) if disp == "FIX" else (239, 68, 68)
        draw.text((w - 60, h - 34), disp, fill=disp_color)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(target_path, format="PNG")

    @classmethod
    def invalidate_block_poster(cls, block_id: str) -> int:
        """Remove all cached posters for the given block. Returns count of deleted files."""
        CatalogManifestService.validate_block_id(block_id)
        cache_dir = cls.get_cache_dir()
        deleted = 0
        for f in cache_dir.glob(f"{block_id}_*.png"):
            try:
                f.unlink(missing_ok=True)
                deleted += 1
            except OSError as e:
                logger.warning("Could not delete poster file %s: %s", f, e)
        return deleted

    @classmethod
    def clear_all_posters(cls) -> int:
        """Clear the entire poster cache."""
        cache_dir = cls.get_cache_dir()
        deleted = 0
        for f in cache_dir.glob("*.png"):
            try:
                f.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                pass
        return deleted
