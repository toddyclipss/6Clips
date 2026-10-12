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
        
        # Categorize logically into the 8 canonical categories
        category = "general"
        tags_lower = [t.lower() for t in tags]
        bname_lower = block_name.lower()
        if block_name in ["instagram-follow", "tiktok-follow", "heygen-avatar-promo-card", "vpn-youtube-spot", "logo-outro"]:
            category = "call-to-action"
        elif any(t in tags_lower for t in ["typography", "kinetic-type", "text", "title", "title-card", "handwritten"]) or "wave" in bname_lower or "type" in bname_lower or block_name.startswith("hw-"):
            category = "typography"
        elif any(t in tags_lower for t in ["lower-third", "broadcast", "news"]) or block_name.startswith("lt-") or "lower-third" in bname_lower:
            category = "lower-thirds"
        elif any(t in tags_lower for t in ["chart", "data-chart", "charts", "bar-chart-race", "flowchart"]) or "chart" in bname_lower:
            category = "charts"
        elif any(t in tags_lower for t in ["transition", "wipe", "dissolve", "cut", "flash", "pan"]) or block_name.startswith("transitions-") or "transition" in bname_lower:
            category = "transitions"
        elif any(t in tags_lower for t in ["shader", "webgpu", "webgpu-shader", "background", "particles", "aurora", "frost", "glitch", "liquid-metal"]) or "shader" in bname_lower or "bg" in bname_lower:
            category = "backgrounds"
        elif any(t in tags_lower for t in ["mock-ui", "notification", "chat", "app-showcase", "social", "ios", "vision", "carousel", "macos"]) or "ui" in bname_lower or "chat" in bname_lower:
            category = "mock-ui"
        else:
            category = "general"

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

        is_vert_native = (width < height)
        if is_vert_native:
            aspect_compat_9x16 = "NATIVE"
            aspect_compat_16x9 = "CONTAINED_ONLY"
        else:
            aspect_compat_16x9 = "NATIVE"
            aspect_compat_9x16 = "ADAPTED" if block_name == "weight-wave" else "CONTAINED_ONLY"

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
            "aspect_compat_9x16": aspect_compat_9x16,
            "aspect_compat_16x9": aspect_compat_16x9,
        }

    @classmethod
    def list_catalog_items(
        cls,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = 300,
        offset: int = 0,
        query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List and normalize available catalog blocks with full discovery and pagination support."""
        search_query = search or query
        reg_dir = get_registry_dir()
        if not reg_dir.exists():
            return []

        all_matching = []
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
                if search_query:
                    q = search_query.lower().strip()
                    haystack = f"{item['title']} {item['description']} {' '.join(item['tags'])} {item['name']}".lower()
                    if q not in haystack:
                        # Fallback to keyword matching excluding generic search qualifiers
                        stop_words = {"blocks", "block", "template", "templates", "element", "elements", "items", "item"}
                        keywords = [w for w in re.findall(r'\w+', q) if w not in stop_words]
                        if not keywords or not all(k in haystack for k in keywords):
                            continue
                all_matching.append(item)
            except Exception as e:
                logger.error("Error reading registry block %s: %s", bdir.name, e)

        # Apply offset and limit
        if offset > 0:
            all_matching = all_matching[offset:]
        if limit is not None and limit > 0:
            all_matching = all_matching[:limit]

        return all_matching

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
    def read_block_source(cls, block_name: str, file_rel_path: Optional[str] = None, version_hash: Optional[str] = None) -> Dict[str, Any]:
        """Read original immutable source file from pinned block snapshot without mutating disk."""
        snapshot = cls.freeze_block_snapshot(block_name, expected_version=version_hash)
        snapshot_dir = Path(snapshot["snapshot_dir"])

        target_file = None
        if file_rel_path:
            p = (snapshot_dir / file_rel_path).resolve()
            if p.is_file() and p.is_relative_to(snapshot_dir):
                target_file = p

        if not target_file:
            # Check manifest for composition file
            manifest_file = snapshot_dir / "registry-item.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    for f in manifest.get("files", []):
                        if f.get("type") == "hyperframes:composition":
                            cand = snapshot_dir / f.get("path")
                            if cand.exists():
                                target_file = cand
                                break
                except Exception:
                    pass
        if not target_file:
            # Fallback to block_name.html or any html
            candidates = list(snapshot_dir.glob("*.html"))
            if candidates:
                target_file = candidates[0]

        if not target_file or not target_file.is_file():
            raise FileNotFoundError(f"File '{file_rel_path or 'composition'}' not found in block '{block_name}'")

        rel_name = target_file.relative_to(snapshot_dir).as_posix()
        return {
            "block_name": block_name,
            "version_hash": snapshot.get("version_hash"),
            "path": rel_name,
            "content": target_file.read_text(encoding="utf-8"),
            "read_only": True,
        }

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
        override_content: Optional[str] = None,
    ) -> Path:
        """
        Materialize an isolated composition file for this block instance.
        Rewrites composition IDs, timelines keys, injects variables, and adapts geometry/typography
        responsively to parent canvas aspect ratio.
        Guarantees independent DOM and timeline isolation.
        Allows explicit project-owned override_content to take precedence over immutable template HTML.
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

        if override_content is not None:
            html_content = override_content
        else:
            html_content = comp_file.read_text(encoding="utf-8")

        # 1. Scope and isolate data-composition-id
        # Replace original composition id with instance_id across all HTML elements and CSS selectors
        orig_comp_id = manifest.get("name") or block_name
        found_comp_ids = set(re.findall(r'data-composition-id=[\'"]([^\'"]+)[\'"]', html_content))
        found_comp_ids.add(orig_comp_id)
        if block_name:
            found_comp_ids.add(block_name)

        for cid in found_comp_ids:
            if not cid:
                continue
            pattern = r'data-composition-id=([\'"])' + re.escape(cid) + r'\1'
            replacement = r'data-composition-id=\1' + instance_id + r'\1'
            html_content = re.sub(pattern, replacement, html_content)

        # 2. Scope timeline dictionary key: window.__timelines["..."] = tl;
        html_content = re.sub(
            r'window\.__timelines\[[\'"][^\'"]+[\'"]\]',
            f'window.__timelines["{instance_id}"]',
            html_content
        )

        stage_w, stage_h = stage_dimensions if stage_dimensions else ((1080, 1920) if aspect_ratio == "9:16" else (1920, 1080))
        is_vertical = (aspect_ratio == "9:16") or (stage_w < stage_h)

        is_ww_or_text_block = (block_name == "weight-wave") or ("Recursive Wave" in html_content) or ("#ww-line" in html_content)
        if is_vertical and is_ww_or_text_block:
            # Adapt hardcoded 1920 canvas coordinates to vertical stage (1080px width x 1920px height)
            # Available width with safe margins: 1080 - 120 = 960px
            max_line_w = max(400, stage_w - 120)
            target_center_y = int(round(stage_h * 0.302))  # Y ~ 580px
            elevate_y = target_center_y - (stage_h // 2)   # -380px in 1920h
            html_content = re.sub(r'var LINE_MAX_WIDTH\s*=\s*\d+;', f'var LINE_MAX_WIDTH = {max_line_w};', html_content)
            html_content = re.sub(r'width:\s*1760px;', f'width: {max_line_w}px;', html_content)
            html_content = re.sub(r'width:\s*1920px;', f'width: {stage_w}px;', html_content)
            html_content = re.sub(r'height:\s*1080px;', f'height: {stage_h}px;', html_content)
            html_content = re.sub(r'data-width="1920"', f'data-width="{stage_w}"', html_content)
            html_content = re.sub(r'data-height="1080"', f'data-height="{stage_h}"', html_content)

            # Static CSS rewriting for headless HyperFrames render compiler:
            # 1. Update #ww-line static CSS cleanly replacing font-size, line-height, width and white-space
            clean_ww_line_css = f"""#ww-line {{
        display: block;
        width: 800px;
        max-width: 800px;
        margin: 0 auto;
        text-align: center;
        white-space: pre-wrap;
        word-break: normal;
        overflow-wrap: normal;
        font-family: "Recursive Wave", sans-serif;
        font-size: 72px;
        line-height: 1.2;
        letter-spacing: 0.005em;
        color: var(--color, #f5f5f7);
        font-variation-settings:
          "wght" 400,
          "slnt" 0;
      }}"""
            html_content = re.sub(
                r'#ww-line\s*\{[^}]+?font-variation-settings:[^}]+?\}',
                clean_ww_line_css,
                html_content
            )

            # 2. Update #ww-stage static CSS to place headline in upper focal zone (Y ~ 580px)
            html_content = re.sub(
                r'(#ww-stage\s*\{[^}]*?justify-content:\s*center;)',
                r'\1\n        transform: translateY(' + str(elevate_y) + 'px);',
                html_content
            )

            # 3. Prevent mid-word splitting & group text into non-breaking words without duplicating elements:
            span_replacement_pattern = r'var chars = Array\.prototype\.slice\.call\(TEXT\);[\s\S]*?var N = spans\.length;'
            new_span_create = '''var chars = Array.prototype.slice.call(TEXT);
          var spans = [];
          line.innerHTML = "";
          var currentWord = null;
          for (var ci = 0; ci < chars.length; ci++) {
            var ch = chars[ci];
            if (ch.charCodeAt(0) === 10 || ch.charCodeAt(0) === 13) {
              currentWord = null;
              var br = document.createElement("br");
              line.appendChild(br);
            } else if (ch === " " || ch.charCodeAt(0) === 9) {
              currentWord = null;
              var spaceEl = document.createElement("span");
              spaceEl.className = "ww-ch";
              spaceEl.textContent = ch;
              line.appendChild(spaceEl);
              spans.push(spaceEl);
            } else {
              if (!currentWord) {
                currentWord = document.createElement("span");
                currentWord.className = "ww-word";
                currentWord.style.display = "inline-block";
                currentWord.style.whiteSpace = "nowrap";
                line.appendChild(currentWord);
              }
              var charEl = document.createElement("span");
              charEl.className = "ww-ch";
              charEl.textContent = ch;
              currentWord.appendChild(charEl);
              spans.push(charEl);
            }
          }
          var N = spans.length;'''
            html_content = re.sub(span_replacement_pattern, lambda _: new_span_create, html_content, count=1)

            # 4. In vertical mode, pin font size to 72px rather than single-line shrink-down
            html_content = re.sub(
                r'line\.style\.fontSize\s*=\s*fontSize\s*\+\s*"px";',
                f'line.style.fontSize = "72px"; line.style.lineHeight = "1.2"; line.style.whiteSpace = "pre-wrap"; line.style.width = "800px";',
                html_content
            )
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

      // Ensure root containers adapt to actual stage dimensions
      if (document.documentElement) {{
        document.documentElement.style.width = stageW + "px";
        document.documentElement.style.height = stageH + "px";
        document.documentElement.style.margin = "0";
        document.documentElement.style.padding = "0";
        document.documentElement.style.overflow = "hidden";
      }}
      if (document.body) {{
        document.body.style.width = stageW + "px";
        document.body.style.height = stageH + "px";
        document.body.style.margin = "0";
        document.body.style.padding = "0";
        document.body.style.overflow = "hidden";
      }}
      var rootEl = document.getElementById("ww-root") || document.getElementById("lb-root") || document.querySelector("[data-composition-id]");
      if (rootEl) {{
        rootEl.style.width = stageW + "px";
        rootEl.style.height = stageH + "px";
        rootEl.style.maxWidth = "100vw";
        rootEl.style.maxHeight = "100vh";
        rootEl.style.position = "relative";
        rootEl.style.overflow = "hidden";
      }}

      // Specific adaptation for weight-wave kinetic typography in vertical / narrow compositions
      var wwStage = document.getElementById("ww-stage");
      var wwLine = document.getElementById("ww-line");
      if (wwLine) {{
        if (isVert) {{
          var maxW = Math.min(800, stageW - 120);
          wwLine.style.width = maxW + "px";
          wwLine.style.maxWidth = "calc(100vw - 120px)";
          wwLine.style.margin = "0 auto";
          wwLine.style.textAlign = "center";
          wwLine.style.whiteSpace = "pre-wrap";
          wwLine.style.wordBreak = "normal";
          wwLine.style.overflowWrap = "normal";
          wwLine.style.lineHeight = "1.2";

          // Prominent headline scale (72px) for 9:16 vertical canvas
          wwLine.style.fontSize = "72px";

          // Intentional placement in upper focal zone (Y ~ 580px, well above lower caption area)
          if (wwStage) {{
            wwStage.style.display = "flex";
            wwStage.style.alignItems = "center";
            wwStage.style.justifyContent = "center";
            wwStage.style.paddingTop = "0";
            // In 1920px height, center is at 960px; translateY(-380px) elevates center to Y = 580px
            var targetCenterY = Math.round(stageH * 0.302);
            var elevateY = targetCenterY - Math.round(stageH / 2);
            wwStage.style.transform = "translateY(" + elevateY + "px)";
          }}
        }} else {{
          wwLine.style.whiteSpace = "pre";
          if (wwStage) {{
            wwStage.style.transform = "";
          }}
        }}
      }}
    }} catch(e) {{}}
  }}

  window.addEventListener("message", function(e) {{
    if (!e.data) return;
    var a = e.data.action;
    var tls = window.__timelines || {{}};
    var allKeys = Object.keys(tls);

    if (a === "seek") {{
      var t = e.data.time != null ? Number(e.data.time) : 0;
      for (var i = 0; i < allKeys.length; i++) {{
        var tlObj = tls[allKeys[i]];
        if (tlObj && typeof tlObj.seek === "function") {{
          tlObj.seek(t, false);
        }}
      }}
      if (window.tl && typeof window.tl.seek === "function") {{
        window.tl.seek(t, false);
      }}
    }} else if (a === "play") {{
      for (var i = 0; i < allKeys.length; i++) {{
        var tlObj = tls[allKeys[i]];
        if (tlObj && typeof tlObj.play === "function") {{
          tlObj.play();
        }}
      }}
      if (window.tl && typeof window.tl.play === "function") {{
        window.tl.play();
      }}
    }} else if (a === "pause") {{
      for (var i = 0; i < allKeys.length; i++) {{
        var tlObj = tls[allKeys[i]];
        if (tlObj && typeof tlObj.pause === "function") {{
          tlObj.pause();
        }}
      }}
      if (window.tl && typeof window.tl.pause === "function") {{
        window.tl.pause();
      }}
    }}
  }});

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
      var allKeys = Object.keys(window.__timelines);
      if (!window.__timelines["{instance_id}"] && allKeys.length > 0) {{
        window.__timelines["{instance_id}"] = window.__timelines[allKeys[0]];
      }} else if (!window.__timelines["{instance_id}"] && typeof tl !== "undefined") {{
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
