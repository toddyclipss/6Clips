# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Repair shader fallback timelines and autoplay across all shipped shader blocks.
Ensures:
1. shader_fallback.js starts play() by default for preview animation.
2. shader_fallback.js listens to 'hf-seek' custom events.
3. window.tl is always defined and points to window.__timelines[blockKey].
4. Inline HTML scripts delegate seek and play to the real canvas fallback engine.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_BLOCKS = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

TARGET_SHADERS = [
    "aurora",
    "blob",
    "flowing-gradient",
    "fractal-noise",
    "frost",
    "godrays",
    "goo",
    "holographic",
    "lens-flare",
    "liquid-metal",
    "marble",
    "mesh-gradient",
    "nebula",
    "plasma",
    "prism",
    "sine-wave",
    "strands",
    "stripes",
    "swirl",
    "voronoi",
    "water",
    "waveform",
]


def update_shader_fallback_js(fb_path: Path) -> bool:
    """Ensure shader_fallback.js autoplays and hooks seek."""
    if not fb_path.exists():
        return False

    content = fb_path.read_text(encoding="utf-8")
    modified = False

    # 1. Ensure hf-seek event listener is attached
    if "window.addEventListener('hf-seek'" not in content and 'window.addEventListener("hf-seek"' not in content:
        needle = "renderShader(cvs, shaderType, 0.0, vars);"
        addition = """renderShader(cvs, shaderType, 0.0, vars);

        // Wave 19: listen to hf-seek event and start autoplay for standalone preview
        window.addEventListener("hf-seek", function(e) {
          if (e.detail && typeof e.detail.time === "number") {
            renderShader(cvs, shaderType, e.detail.time, vars);
          }
        });
        if (!window.tl) window.tl = window.__timelines[blockKey];
        try {
          window.__timelines[blockKey].play();
        } catch(e) {}"""
        if needle in content:
            content = content.replace(needle, addition)
            modified = True

    if modified:
        fb_path.write_text(content, encoding="utf-8")
    return modified


def update_shader_html(html_path: Path, slug: str) -> bool:
    """Ensure shader html has working play/seek delegation in inline script."""
    if not html_path.exists():
        return False

    content = html_path.read_text(encoding="utf-8")
    modified = False

    # Replace dummy play: function() {} with real delegating play
    dummy_pattern = r"play:\s*function\(\)\s*\{\s*\},?\s*pause:\s*function\(\)\s*\{\s*\}"
    if re.search(dummy_pattern, content):
        replacement = f"""play: function() {{
            var self = this;
            if (self._raf) cancelAnimationFrame(self._raf);
            var start = performance.now() - (self.currentTime * 1000);
            function loop() {{
              var elapsed = (performance.now() - start) / 1000;
              self.seek(elapsed % self.duration());
              self._raf = requestAnimationFrame(loop);
            }}
            self._raf = requestAnimationFrame(loop);
          }},
          pause: function() {{
            if (this._raf) cancelAnimationFrame(this._raf);
          }}"""
        content = re.sub(dummy_pattern, replacement, content)
        modified = True

    # Make sure seek also calls existing fallback seek if present
    old_seek = "window.dispatchEvent(new CustomEvent('hf-seek', { detail: { time: this.currentTime } }));"
    if old_seek in content and "existing.seek" not in content:
        new_seek = f"""var existing = (window.__timelines && window.__timelines['{slug}'] && window.__timelines['{slug}'] !== shaderTl) ? window.__timelines['{slug}'] : null;
            if (existing && typeof existing.seek === 'function') {{
              existing.seek(this.currentTime);
            }}
            window.dispatchEvent(new CustomEvent('hf-seek', {{ detail: {{ time: this.currentTime }} }}));"""
        content = content.replace(old_seek, new_seek)
        modified = True

    # Ensure shaderTl.play() is invoked
    if "shaderTl.play();" not in content and "window.tl = shaderTl;" in content:
        content = content.replace("window.tl = shaderTl;", "window.tl = shaderTl;\n        shaderTl.play();")
        modified = True

    if modified:
        html_path.write_text(content, encoding="utf-8")
    return modified


def run_repairs():
    repaired_js = 0
    repaired_html = 0

    for slug in TARGET_SHADERS:
        bdir = SHIPPED_BLOCKS / slug
        if not bdir.exists():
            continue

        fb_file = bdir / "lib" / "shader_fallback.js"
        if update_shader_fallback_js(fb_file):
            repaired_js += 1

        for cand in [bdir / f"{slug}.html", bdir / "index.html"]:
            if cand.exists():
                if update_shader_html(cand, slug):
                    repaired_html += 1

    print(f"Repairs complete: {repaired_js} shader_fallback.js files, {repaired_html} HTML files updated.")


if __name__ == "__main__":
    run_repairs()
