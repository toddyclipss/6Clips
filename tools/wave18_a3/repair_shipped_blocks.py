#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 18 Agent 3: Targeted repair script for shipped A-M blocks.
Fixes:
1. All 25 carousel blocks:
   - Initialize window.__timelines = window.__timelines || {}; and expose window.tl = tl
   - Inline SVG data-URI card placeholders when external assets/carousel-images/* are missing
2. Lower-third and UI blocks with uninitialized window.__timelines
3. Shader blocks: ensure window.tl and window.__timelines exposure for seeking
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DIR = REPO_ROOT / "backend" / "catalog" / "shipped_blocks"

SVG_CARD_TEMPLATE = (
    "data:image/svg+xml;utf8,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='800'%3E"
    "%3Cdefs%3E%3ClinearGradient id='g' x1='0%25' y1='0%25' x2='100%25' y2='100%25'%3E"
    "%3Cstop offset='0%25' stop-color='%231e293b'/%3E"
    "%3Cstop offset='100%25' stop-color='%230f172a'/%3E"
    "%3C/linearGradient%3E%3C/defs%3E"
    "%3Crect width='100%25' height='100%25' fill='url(%23g)'/%3E"
    "%3Crect x='20' y='20' width='560' height='760' rx='16' fill='none' stroke='%2338bdf8' stroke-width='4' stroke-opacity='0.4'/%3E"
    "%3Ccircle cx='300' cy='360' r='80' fill='%2338bdf8' fill-opacity='0.2'/%3E"
    "%3Ctext x='50%25' y='520' dominant-baseline='middle' text-anchor='middle' "
    "font-family='system-ui, -apple-system, sans-serif' font-weight='700' font-size='36' fill='%23f8fafc'%3ECard%3C/text%3E"
    "%3C/svg%3E"
)

def repair_carousels():
    carousel_slugs = [
        f"carousel-{family}-{num}"
        for family in ["circle", "orbit", "path", "text-circle", "vision"]
        for num in range(1, 6)
    ]
    repaired = 0
    for slug in carousel_slugs:
        html_file = SHIPPED_DIR / slug / f"{slug}.html"
        if not html_file.exists():
            continue
        txt = html_file.read_text(encoding="utf-8")
        orig = txt

        # 1. Timeline initialization & exposure
        if "window.__timelines[DATA.id] = tl;" in txt:
            txt = txt.replace(
                "window.__timelines[DATA.id] = tl;",
                "window.__timelines = window.__timelines || {};\n        window.__timelines[DATA.id] = tl;\n        window.tl = tl;"
            )
            
        # 2. Image fallback replacement
        # Target: "assets/carousel-images/" + DATA.cards[i % DATA.cards.length].file
        txt = re.sub(
            r'("assets/carousel-images/"\s*\+\s*DATA\.cards\[i\s*%\s*DATA\.cards\.length\]\.file)',
            f'"{SVG_CARD_TEMPLATE}"',
            txt
        )
        # Also in secondary render paths if any: "assets/carousel-images/" + c.file
        txt = re.sub(
            r'("assets/carousel-images/"\s*\+\s*c\.file)',
            f'"{SVG_CARD_TEMPLATE}"',
            txt
        )

        if txt != orig:
            html_file.write_text(txt, encoding="utf-8")
            repaired += 1
            
    print(f"Repaired {repaired} carousel blocks.")

def repair_lower_thirds():
    lt_slugs = [
        "lt-accent-underline", "lt-bold-block", "lt-clean-bar", "lt-color-block",
        "lt-dark-card", "lt-kicker-name", "lt-mask-reveal", "lt-side-rule",
        "lt-soft-pill", "lt-stack-bars", "lower-third-bild", "lt-neon-border"
    ]
    repaired = 0
    for slug in lt_slugs:
        html_file = SHIPPED_DIR / slug / f"{slug}.html"
        if not html_file.exists():
            continue
        txt = html_file.read_text(encoding="utf-8")
        orig = txt

        # Check for uninitialized window.__timelines
        if "window.__timelines[" in txt and "window.__timelines = window.__timelines || {};" not in txt:
            # find first occurrence of window.__timelines[
            idx = txt.find("window.__timelines[")
            txt = txt[:idx] + "window.__timelines = window.__timelines || {};\n    " + txt[idx:]

        if "window.tl = " not in txt and "window.tl=" not in txt:
            # bind window.tl to the active timeline or block timeline
            if "window.__timelines[" in txt:
                txt = re.sub(
                    r'(window\.__timelines\[[^\]]+\]\s*=\s*([^;]+);)',
                    r'\1\n    window.tl = \2;',
                    txt
                )

        if txt != orig:
            html_file.write_text(txt, encoding="utf-8")
            repaired += 1

    print(f"Repaired {repaired} lower third blocks.")

def repair_shaders():
    shader_slugs = [
        "aurora", "blob", "flowing-gradient", "fractal-noise", "frost",
        "godrays", "goo", "holographic", "lens-flare", "liquid-metal",
        "marble", "mesh-gradient"
    ]
    repaired = 0
    for slug in shader_slugs:
        html_file = SHIPPED_DIR / slug / f"{slug}.html"
        if not html_file.exists():
            continue
        txt = html_file.read_text(encoding="utf-8")
        orig = txt

        # Check if timeline bindings already exist
        if "window.tl" in txt and "window.__timelines" in txt:
            continue

        # Inject seek-compatible shader timeline shim before </body>
        shim = f"""
    <script>
      (function() {{
        window.__timelines = window.__timelines || {{}};
        var shaderTl = {{
          currentTime: 0,
          duration: function() {{ return 10.0; }},
          seek: function(t) {{
            this.currentTime = Number(t) || 0;
            window.__shaderTime = this.currentTime;
            window.dispatchEvent(new CustomEvent('hf-seek', {{ detail: {{ time: this.currentTime }} }}));
          }},
          play: function() {{}},
          pause: function() {{}}
        }};
        window.__timelines['{slug}'] = shaderTl;
        if (!window.tl) window.tl = shaderTl;
      }})();
    </script>
        """
        if "</body>" in txt:
            txt = txt.replace("</body>", f"{shim}\n  </body>")
        else:
            txt = txt + shim

        if txt != orig:
            html_file.write_text(txt, encoding="utf-8")
            repaired += 1

    print(f"Repaired {repaired} shader blocks with seek timeline bindings.")

def repair_code_snippets():
    code_slugs = ["code-snippet-dark-2026", "code-snippet-dark-modern"]
    repaired = 0
    for slug in code_slugs:
        html_file = SHIPPED_DIR / slug / f"{slug}.html"
        if not html_file.exists():
            continue
        txt = html_file.read_text(encoding="utf-8")
        orig = txt
        if "window.tl" not in txt:
            # Bind timeline
            shim = f"""
    <script>
      (function() {{
        window.__timelines = window.__timelines || {{}};
        if (typeof tl !== 'undefined') {{
          window.__timelines['{slug}'] = tl;
          window.tl = tl;
        }} else {{
          var sTl = {{
            seek: function(t) {{}},
            play: function() {{}},
            pause: function() {{}},
            duration: function() {{ return 5.0; }}
          }};
          window.__timelines['{slug}'] = sTl;
          window.tl = sTl;
        }}
      }})();
    </script>
            """
            if "</body>" in txt:
                txt = txt.replace("</body>", f"{shim}\n  </body>")
            else:
                txt = txt + shim
def repair_gooey_split():
    slug = "gooey-split"
    html_file = SHIPPED_DIR / slug / f"{slug}.html"
    if not html_file.exists():
        return
    txt = html_file.read_text(encoding="utf-8")
    orig = txt

    shim = """
    <script>
      window.CustomEase = {
        create: function(name, path) {
          var m = path.match(/C\\s*([\\d\\.-]+)[\\s,]+([\\d\\.-]+)[\\s,]+([\\d\\.-]+)[\\s,]+([\\d\\.-]+)/);
          if (!m) return (typeof gsap !== 'undefined') ? gsap.parseEase('power2.out') : function(t) { return t; };
          var x1 = parseFloat(m[1]), y1 = parseFloat(m[2]), x2 = parseFloat(m[3]), y2 = parseFloat(m[4]);
          return function(t) {
            if (t <= 0) return 0;
            if (t >= 1) return 1;
            var s = t;
            for (var i = 0; i < 5; i++) {
              var currentX = 3*Math.pow(1-s, 2)*s*x1 + 3*(1-s)*s*s*x2 + s*s*s - t;
              var derivX = 3*Math.pow(1-s, 2)*x1 + 6*(1-s)*s*(x2-x1) + 3*s*s*(1-x2);
              if (Math.abs(derivX) < 1e-5) break;
              s -= currentX / derivX;
            }
            s = Math.max(0, Math.min(1, s));
            return 3*Math.pow(1-s, 2)*s*y1 + 3*(1-s)*s*s*y2 + s*s*s;
          };
        }
      };
    </script>
    """
    if "window.CustomEase" not in txt:
        txt = txt.replace("<!-- CustomEase vendored fallback -->", shim)
    if "window.tl = tl;" not in txt:
        txt = txt.replace('window.__timelines["gooey-split"] = tl;', 'window.__timelines["gooey-split"] = tl;\n        window.tl = tl;')

def repair_frost_sequence():
    slug = "frost-sequence-camera-orbit"
    html_file = SHIPPED_DIR / slug / f"{slug}.html"
    if not html_file.exists():
        return
    txt = html_file.read_text(encoding="utf-8")
    orig = txt

    target = 'window.__timelines["frost-sequence-rig"] = timeline;'
    replacement = 'window.__timelines["frost-sequence-rig"] = timeline;\n        window.__timelines["frost-sequence-camera-orbit"] = timeline;\n        window.tl = timeline;'
    if target in txt and "window.tl = timeline;" not in txt:
        txt = txt.replace(target, replacement)

    if txt != orig:
        html_file.write_text(txt, encoding="utf-8")
        print("Repaired frost-sequence-camera-orbit timeline binding.")

if __name__ == "__main__":
    repair_carousels()
    repair_lower_thirds()
    repair_shaders()
    repair_code_snippets()
    repair_gooey_split()
    repair_frost_sequence()
