# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""ViralMint Registry Adapter: normalizes HyperFrames blocks into versioned, immutable project objects."""
import hashlib
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

from backend.config import DATA_DIR, settings

logger = logging.getLogger(__name__)

# Default location for the local HyperFrames registry
_DEFAULT_REGISTRY_DIR = Path(r"C:\Users\toddy\Desktop\hyperframes\registry\blocks")


def get_registry_dir() -> Path:
    """Return the active registry blocks directory."""
    env_dir = os.getenv("HYPERFRAMES_REGISTRY_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p
    if _DEFAULT_REGISTRY_DIR.exists():
        return _DEFAULT_REGISTRY_DIR
    # Fallback to local data dir if vendored
    fallback = DATA_DIR / "registry" / "blocks"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_registry_cache_dir() -> Path:
    """Directory where immutable block version snapshots are frozen and preserved."""
    p = DATA_DIR / "motion_registry_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


class RegistryAdapter:
    """Stateless adapter and cache manager for HyperFrames blocks."""

    @classmethod
    def compute_block_hash(cls, block_dir: Path) -> str:
        """Compute deterministic SHA-256 content hash across all files in block directory."""
        if not block_dir.exists() or not block_dir.is_dir():
            return "0000000000000000"
        h = hashlib.sha256()
        for f in sorted(block_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(block_dir).as_posix()
                h.update(rel.encode("utf-8"))
                try:
                    h.update(f.read_bytes())
                except Exception as e:
                    logger.warning("Error reading file %s for hashing: %s", f, e)
        return h.hexdigest()[:16]

    @classmethod
    def normalize_manifest(cls, raw_manifest: Dict[str, Any], block_name: str, block_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Normalize heterogeneous registry manifests into a uniform ViralMint catalog item."""
        title = raw_manifest.get("title") or block_name.replace("-", " ").title()
        description = raw_manifest.get("description") or ""
        tags = list(raw_manifest.get("tags") or [])
        
        # Categorize logically from tags or name
        category = "general"
        tags_lower = [t.lower() for t in tags]
        if any(t in tags_lower for t in ["typography", "kinetic-type", "text", "title", "title-card", "handwritten"]):
            category = "typography"
        elif any(t in tags_lower for t in ["lower-third", "broadcast", "news"]):
            category = "lower-thirds"
        elif any(t in tags_lower for t in ["chart", "data-chart", "charts", "bar-chart-race"]):
            category = "charts"
        elif any(t in tags_lower for t in ["mock-ui", "notification", "chat", "app-showcase", "social"]):
            category = "mock-ui"
        elif any(t in tags_lower for t in ["shader", "webgpu", "webgpu-shader", "background", "particles"]):
            category = "backgrounds"
        elif any(t in tags_lower for t in ["transition", "wipe", "dissolve"]):
            category = "transitions"
        elif any(t in tags_lower for t in ["cta", "ad-template", "badge"]):
            category = "call-to-action"

        dims = raw_manifest.get("dimensions") or {"width": 1080, "height": 1920}
        width = int(dims.get("width") or 1080)
        height = int(dims.get("height") or 1920)

        duration = float(raw_manifest.get("duration") or 5.0)

        # Normalize variables
        raw_vars = raw_manifest.get("variables") or []
        # If manifest has no variables, attempt to parse from main html data-composition-variables
        if not raw_vars and block_dir:
            for html_file in block_dir.glob("*.html"):
                try:
                    content = html_file.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r'data-composition-variables=([\'"])(.*?)\1', content, re.DOTALL)
                    if m:
                        raw_vars = json.loads(m.group(2))
                        break
                except Exception:
                    pass

        normalized_vars = []
        for v in raw_vars:
            vid = str(v.get("id") or "")
            if not vid:
                continue
            v_type = str(v.get("type") or "string").lower()
            if v_type not in ["string", "number", "color", "enum", "image", "video", "boolean"]:
                v_type = "string"
            norm_v = {
                "id": vid,
                "type": v_type,
                "label": v.get("label") or vid.replace("_", " ").title(),
                "description": v.get("description") or "",
                "default": v.get("default"),
            }
            if v_type == "number":
                if "min" in v: norm_v["min"] = v["min"]
                if "max" in v: norm_v["max"] = v["max"]
                if "step" in v: norm_v["step"] = v["step"]
                if "unit" in v: norm_v["unit"] = v["unit"]
            elif v_type == "enum":
                norm_v["options"] = v.get("options") or []
            elif v_type == "string" and "maxLength" in v:
                norm_v["maxLength"] = v["maxLength"]
            normalized_vars.append(norm_v)

        files = list(raw_manifest.get("files") or [])
        preview = dict(raw_manifest.get("preview") or {})
        
        version_hash = cls.compute_block_hash(block_dir) if block_dir else "0000000000000000"

        return {
            "id": block_name,
            "name": block_name,
            "title": title,
            "category": category,
            "description": description,
            "tags": tags,
            "dimensions": {"width": width, "height": height},
            "duration": duration,
            "variables": normalized_vars,
            "files": files,
            "preview": preview,
            "version_hash": version_hash,
        }

    @classmethod
    def list_catalog_items(
        cls,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List and normalize available catalog blocks."""
        reg_dir = get_registry_dir()
        if not reg_dir.exists():
            return []

        items = []
        for bdir in sorted(reg_dir.iterdir()):
            if not bdir.is_dir():
                continue
            manifest_file = bdir / "registry-item.json"
            if not manifest_file.exists():
                continue
            try:
                raw_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                item = cls.normalize_manifest(raw_manifest, bdir.name, bdir)
                
                # Filter category
                if category and category.lower() != "all" and item["category"].lower() != category.lower():
                    continue
                # Filter search
                if search:
                    q = search.lower()
                    haystack = f"{item['title']} {item['description']} {' '.join(item['tags'])}".lower()
                    if q not in haystack:
                        continue
                items.append(item)
                if len(items) >= limit:
                    break
            except Exception as e:
                logger.error("Error reading registry block %s: %s", bdir.name, e)
        return items

    @classmethod
    def get_catalog_item(cls, block_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve single normalized catalog item by name."""
        reg_dir = get_registry_dir()
        bdir = reg_dir / block_name
        if not bdir.exists() or not bdir.is_dir():
            return None
        manifest_file = bdir / "registry-item.json"
        if not manifest_file.exists():
            return None
        try:
            raw_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            return cls.normalize_manifest(raw_manifest, block_name, bdir)
        except Exception as e:
            logger.error("Error reading block %s: %s", block_name, e)
            return None

    @classmethod
    def freeze_block_snapshot(cls, block_name: str, expected_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Freeze and snapshot an immutable version of a registry block into the cache.
        Returns the snapshot directory and metadata.
        """
        reg_dir = get_registry_dir()
        bdir = reg_dir / block_name
        cache_base = get_registry_cache_dir()

        # If expected_version is provided and exists in cache, use cached version (reproducibility guarantee)
        if expected_version:
            cached_dir = cache_base / f"{block_name}_{expected_version}"
            if cached_dir.exists():
                meta_file = cached_dir / "_snapshot_meta.json"
                if meta_file.exists():
                    return json.loads(meta_file.read_text(encoding="utf-8"))

        if not bdir.exists():
            raise FileNotFoundError(f"Registry block '{block_name}' not found at {bdir}")

        curr_hash = cls.compute_block_hash(bdir)
        snapshot_dir = cache_base / f"{block_name}_{curr_hash}"

        if not snapshot_dir.exists():
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            for item in bdir.iterdir():
                dest = snapshot_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        raw_manifest = json.loads((snapshot_dir / "registry-item.json").read_text(encoding="utf-8"))
        normalized = cls.normalize_manifest(raw_manifest, block_name, snapshot_dir)
        normalized["snapshot_dir"] = str(snapshot_dir)
        normalized["version_hash"] = curr_hash

        (snapshot_dir / "_snapshot_meta.json").write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        return normalized

    @classmethod
    def stage_block_instance(
        cls,
        block_name: str,
        version_hash: str,
        instance_id: str,
        dest_compositions_dir: Path,
        variables: Optional[Dict[str, Any]] = None,
        aspect_ratio: Optional[str] = None,
        stage_dimensions: Optional[Tuple[int, int]] = None,
    ) -> Path:
        """
        Materialize an isolated composition file for this block instance.
        Rewrites composition IDs, timelines keys, injects variables, and adapts geometry/typography
        responsively to parent canvas aspect ratio.
        Guarantees independent DOM and timeline isolation.
        """
        dest_compositions_dir.mkdir(parents=True, exist_ok=True)
        snapshot = cls.freeze_block_snapshot(block_name, expected_version=version_hash)
        snapshot_dir = Path(snapshot["snapshot_dir"])

        # Locate main html
        manifest = json.loads((snapshot_dir / "registry-item.json").read_text(encoding="utf-8"))
        comp_file = None
        for f in manifest.get("files", []):
            if f.get("type") == "hyperframes:composition":
                comp_file = snapshot_dir / f.get("path")
                break
        if not comp_file or not comp_file.exists():
            # fallback to block_name.html or any html
            candidates = list(snapshot_dir.glob("*.html"))
            if not candidates:
                raise FileNotFoundError(f"No composition HTML found in snapshot for '{block_name}'")
            comp_file = candidates[0]

        # Copy any assets / fonts folders into dest_compositions_dir
        for folder_name in ["assets", "lib"]:
            src_folder = snapshot_dir / folder_name
            if src_folder.exists() and src_folder.is_dir():
                target_folder = dest_compositions_dir / folder_name
                target_folder.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src_folder, target_folder, dirs_exist_ok=True)

        html_content = comp_file.read_text(encoding="utf-8")

        # 1. Scope and isolate data-composition-id
        # Replace original composition id with instance_id
        orig_comp_id = manifest.get("name") or block_name
        html_content = re.sub(
            r'data-composition-id="[^"]+"',
            f'data-composition-id="{instance_id}"',
            html_content,
            count=1
        )

        # 2. Scope timeline dictionary key: window.__timelines["..."] = tl;
        html_content = re.sub(
            r'window\.__timelines\[[\'"][^\'"]+[\'"]\]',
            f'window.__timelines["{instance_id}"]',
            html_content
        )

        stage_w, stage_h = stage_dimensions if stage_dimensions else ((1080, 1920) if aspect_ratio == "9:16" else (1920, 1080))
        is_vertical = (aspect_ratio == "9:16") or (stage_w < stage_h)

        if is_vertical:
            # Adapt hardcoded 1920 canvas coordinates to vertical stage (1080px width)
            # Available width with safe margins: 1080 - 120 = 960px
            max_line_w = max(400, stage_w - 120)
            html_content = re.sub(r'var LINE_MAX_WIDTH\s*=\s*\d+;', f'var LINE_MAX_WIDTH = {max_line_w};', html_content)
            html_content = re.sub(r'width:\s*1760px;', f'width: {max_line_w}px;', html_content)
            html_content = re.sub(r'width:\s*1920px;', f'width: {stage_w}px;', html_content)
            html_content = re.sub(r'data-width="1920"', f'data-width="{stage_w}"', html_content)

        # 3. Inject responsive viewport and variable overrides
        vars_dict = variables or {}
        vars_json = json.dumps(vars_dict)

        override_script = f"""
<script>
  window.__hfVariables = {vars_json};
  window.__hyperframes = window.__hyperframes || {{}};
  var origGetVars = window.__hyperframes.getVariables;
  window.__hyperframes.getVariables = function() {{
    var base = (origGetVars ? origGetVars() : {{}});
    var injected = window.__hfVariables || {{}};
    var merged = {{}};
    for (var k in base) {{ merged[k] = base[k]; }}
    for (var k in injected) {{ merged[k] = injected[k]; }}
    return merged;
  }};
  function __applyHfVars() {{
    try {{
      var v = window.__hfVariables || {{}};
      for (var k in v) {{
        document.documentElement.style.setProperty("--" + k, v[k]);
        if (document.body) {{ document.body.style.setProperty("--" + k, v[k]); }}
        var textEls = document.querySelectorAll('[data-var-text="' + k + '"]');
        if (textEls && textEls.forEach) {{
          textEls.forEach(function(el) {{ el.textContent = v[k]; }});
        }}
        var srcEls = document.querySelectorAll('[data-var-src="' + k + '"]');
        if (srcEls && srcEls.forEach) {{
          srcEls.forEach(function(el) {{ el.src = v[k]; }});
        }}
      }}
    }} catch(e) {{}}
  }}

  // Responsive stage & typography layout adaptation
  function __adaptBlockGeometry() {{
    try {{
      var isVert = {json.dumps(is_vertical)};
      var stageW = {stage_w};
      var stageH = {stage_h};

      // Ensure root containers adapt to actual parent iframe size
      if (document.body) {{
        document.body.style.width = "100%";
        document.body.style.maxWidth = "100vw";
      }}
      var rootEl = document.getElementById("ww-root") || document.getElementById("lb-root") || document.querySelector("[data-composition-id]");
      if (rootEl) {{
        rootEl.style.width = "100%";
        rootEl.style.maxWidth = "100vw";
      }}

      // Specific adaptation for weight-wave kinetic typography in vertical / narrow compositions
      var wwLine = document.getElementById("ww-line");
      if (wwLine) {{
        var maxW = Math.min(1760, stageW - 80);
        wwLine.style.width = maxW + "px";
        wwLine.style.maxWidth = "calc(100vw - 80px)";
        wwLine.style.margin = "0 auto";
        wwLine.style.textAlign = "center";
        wwLine.style.wordBreak = "break-word";

        // If line is wider than maxW, scale down font-size proportionally
        var currentFont = parseFloat(window.getComputedStyle(wwLine).fontSize);
        if (currentFont && isVert) {{
          // In 9:16 (1080px wide), ratio of available width (1000px) to native (1760px) is ~0.57
          var scaleRatio = Math.min(1.0, maxW / 1760.0);
          var fittedFont = Math.max(36, Math.floor(currentFont * scaleRatio));
          wwLine.style.fontSize = fittedFont + "px";
        }}
      }}
    }} catch(e) {{}}
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", function() {{
      __applyHfVars();
      __adaptBlockGeometry();
    }});
  }} else {{
    __applyHfVars();
    __adaptBlockGeometry();
  }}
</script>
"""
        if "</head>" in html_content:
            html_content = html_content.replace("</head>", f"{override_script}\n</head>")
        elif "<body" in html_content:
            html_content = html_content.replace("<body", f"{override_script}\n<body")

        # 4. Inject subcomposition ready handshake notification script
        ready_script = f"""
<script>
  (function() {{
    try {{
      window.__timelines = window.__timelines || {{}};
      if (!window.__timelines["{instance_id}"] && typeof tl !== "undefined") {{
        window.__timelines["{instance_id}"] = tl;
      }}
      window.parent.postMessage({{
        source: "vm-subcomp-ready",
        id: "{instance_id}"
      }}, "*");
    }} catch(e) {{}}
  }})();
</script>
"""
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{ready_script}\n</body>")
        else:
            html_content += ready_script

        dest_html_file = dest_compositions_dir / f"{instance_id}.html"
        dest_html_file.write_text(html_content, encoding="utf-8")
        return dest_html_file
