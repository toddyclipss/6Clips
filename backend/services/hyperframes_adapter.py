# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""HyperFrames Adapter: translates between ViralMint versioned Project document and HyperFrames composition HTML."""
import json
import logging
import re
import shutil
from typing import Optional, Tuple
from pathlib import Path

from backend.services.project_service import ProjectService
from backend.services.studio_service import StudioService
from backend.services.asset_resolver import resolve_asset_record_and_path, AssetNotFoundError
from backend.core.exceptions import RevisionConflictError, ProjectError

logger = logging.getLogger(__name__)


class HyperFramesAdapter:
    """Boundary adapter between ViralMint Project document and HyperFrames composition engine."""

    @staticmethod
    def project_doc_to_html(doc: dict) -> str:
        """Convert a ViralMint versioned Project document into valid HyperFrames HTML."""
        title = doc.get("title", "ViralMint Composition")
        aspect = doc.get("aspect_ratio", "9:16")
        timeline = doc.get("timeline", {})
        duration = float(timeline.get("duration_seconds", 15.0) or 15.0)
        fps = int(doc.get("fps") or timeline.get("fps") or 30)
        tracks = timeline.get("tracks", [])

        # Dimensions
        if aspect == "16:9":
            w, h = 1920, 1080
        elif aspect == "1:1":
            w, h = 1080, 1080
        else:
            w, h = 1080, 1920

        # Build elements HTML and timeline definitions
        elements_html = []
        gsap_tweens = []
        timelines_data = {
            "duration": duration,
            "fps": fps,
            "elements": {}
        }

        # Build element visibility map with parent hierarchy inheritance
        clip_vis = {}
        for t in tracks:
            t_vis = t.get("visible", True) is not False
            for c in t.get("clips", []):
                cid = c.get("id") or "clip_elem"
                c_vis = t_vis and (c.get("visible", True) is not False)
                clip_vis[cid] = c_vis

        # Ancestor propagation: if any parent is invisible, children are invisible
        for t in tracks:
            for c in t.get("clips", []):
                cid = c.get("id") or "clip_elem"
                pid = c.get("parent_id")
                visited = set()
                while pid and pid not in visited:
                    visited.add(pid)
                    if not clip_vis.get(pid, True):
                        clip_vis[cid] = False
                        break
                    parent = next((item for tr in tracks for item in tr.get("clips", []) if item.get("id") == pid), None)
                    pid = parent.get("parent_id") if parent else None

        # Collect visible non-group clips
        visible_clips = []
        for t in tracks:
            t_type = t.get("type", "video")
            for c in t.get("clips", []):
                cid = c.get("id") or "clip_elem"
                if not clip_vis.get(cid, True):
                    continue
                if c.get("type") == "group":
                    continue
                visible_clips.append((t_type, c))

        # Sort by layer_order ascending (lower rendered first, higher on top)
        visible_clips.sort(key=lambda item: int(item[1].get("layer_order", 0) or 0))

        for t_type, c in visible_clips:
            cid = c.get("id") or "clip_elem"
            c_start = float(c.get("start_seconds", 0.0) or 0.0)
            c_dur = float(c.get("duration_seconds", 5.0) or 5.0)
            trim_start = float(c.get("trim_start", 0.0) or 0.0)
            trim_end = float(c.get("trim_end", 0.0) or (trim_start + c_dur))
            caption_text = c.get("caption_text") or c.get("text") or ""
            asset_file = c.get("file") or c.get("asset_file") or ""
            layer_order = int(c.get("layer_order", 0) or 0)
            custom_style = c.get("style") or ""
            fit_mode = c.get("fit") or "contain"
            z_style = f' style="z-index: {layer_order}; {custom_style}"'

            if c.get("type") == "block" or c.get("block_id"):
                vars_val = c.get("variables") or {}
                vars_json = json.dumps(vars_val).replace("'", "&#39;")
                elements_html.append(
                    f'  <div data-hf-id="{cid}" id="{cid}" class="component-block"{z_style} data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{c_start}" data-duration="{c_dur}" data-variable-values=\'{vars_json}\'>'
                    f'<iframe class="subcomp-frame" src="compositions/{cid}.html" title="{cid}" loading="eager"></iframe></div>'
                )
            elif t_type == "captions" or caption_text:
                pos = c.get("position") or "bottom"
                pos_class = f"caption-block caption-pos-{pos}"
                elements_html.append(
                    f'  <div data-hf-id="{cid}" id="{cid}" class="{pos_class}"{z_style} data-start="{c_start}" data-duration="{c_dur}">'
                    f'<span>{caption_text}</span></div>'
                )
            elif t_type == "audio":
                src_attr = f' src="./assets/{asset_file}"' if asset_file else ''
                elements_html.append(
                    f'  <audio data-hf-id="{cid}" id="{cid}"{src_attr} data-start="{c_start}" data-duration="{c_dur}" data-playback-start="{trim_start}" data-media-start="{trim_start}"></audio>'
                )
            elif t_type == "image" or c.get("type") == "image":
                src_attr = f' src="./assets/{asset_file}"' if asset_file else ''
                obj_pos = c.get("object_position") or c.get("crop_position") or "center center"
                combined_style = f'style="z-index: {layer_order}; object-fit: {fit_mode}; object-position: {obj_pos}; {custom_style}"'.strip()
                elements_html.append(
                    f'  <img data-hf-id="{cid}" id="{cid}" class="image-block" {combined_style}{src_attr} data-start="{c_start}" data-duration="{c_dur}" />'
                )
            elif t_type == "video" or c.get("type") == "video":
                src_attr = f' src="./assets/{asset_file}"' if asset_file else ''
                obj_pos = c.get("object_position") or c.get("crop_position") or "center center"
                combined_style = f'style="z-index: {layer_order}; object-fit: {fit_mode}; object-position: {obj_pos}; {custom_style}"'.strip()
                elements_html.append(
                    f'  <video data-hf-id="{cid}" id="{cid}" {combined_style}{src_attr} data-start="{c_start}" data-duration="{c_dur}" data-playback-start="{trim_start}" data-media-start="{trim_start}" data-trim-start="{trim_start}" data-trim-end="{trim_end}" playsinline webkit-playsinline muted preload="auto"></video>'
                )
            else:
                elements_html.append(
                    f'  <div data-hf-id="{cid}" id="{cid}" class="generic-block"{z_style} data-start="{c_start}" data-duration="{c_dur}"></div>'
                )
            timelines_data["elements"][cid] = {
                "start": c_start,
                "duration": c_dur,
                "playback_start": trim_start,
                "trim_start": trim_start,
                "trim_end": trim_end,
            }

            # Deterministically project keyframes into GSAP timeline tweens
            anims = c.get("animations") or []
            if anims:
                by_prop = {}
                for a in anims:
                    p = a.get("property")
                    if p:
                        by_prop.setdefault(p, []).append(a)

                for prop_name, kfs in by_prop.items():
                    kfs.sort(key=lambda x: float(x.get("time", 0.0) or 0.0))
                    if len(kfs) == 1:
                        kf = kfs[0]
                        k_time = round(c_start + float(kf.get("time", 0.0) or 0.0), 3)
                        val = json.dumps(kf.get("value"))
                        gsap_tweens.append(f'      tl.set("#{cid}", {{ {prop_name}: {val} }}, {k_time});')
                    else:
                        first_kf = kfs[0]
                        first_time = round(c_start + float(first_kf.get("time", 0.0) or 0.0), 3)
                        first_val = json.dumps(first_kf.get("value"))
                        gsap_tweens.append(f'      tl.set("#{cid}", {{ {prop_name}: {first_val} }}, {first_time});')
                        for idx in range(1, len(kfs)):
                            prev = kfs[idx - 1]
                            curr = kfs[idx]
                            prev_time = round(c_start + float(prev.get("time", 0.0) or 0.0), 3)
                            curr_time = round(c_start + float(curr.get("time", 0.0) or 0.0), 3)
                            dur = max(0.001, round(curr_time - prev_time, 3))
                            curr_val = json.dumps(curr.get("value"))
                            ease = curr.get("ease") or "none"
                            gsap_tweens.append(f'      tl.to("#{cid}", {{ {prop_name}: {curr_val}, duration: {dur}, ease: "{ease}" }}, {prev_time});')

        inner_content = "\n".join(elements_html) if elements_html else "  <!-- empty canvas -->"
        timelines_json = json.dumps(timelines_data)
        gsap_tweens_code = "\n".join(gsap_tweens)

        # Standard HyperFrames HTML template satisfying composition issue validator
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <!-- GSAP vendored locally in assets/ for offline timeline animation -->
  <script src="assets/gsap.min.js"></script>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background: #000;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      position: relative;
    }}
    #stage {{
      position: absolute;
      left: 50%;
      top: 50%;
      width: {w}px;
      height: {h}px;
      transform-origin: center center;
      background: #0b0f19;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: sans-serif;
      overflow: hidden;
    }}
    .component-block {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: auto;
    }}
    .component-block iframe.subcomp-frame {{
      width: 100%;
      height: 100%;
      border: 0;
      background: transparent;
      display: block;
      pointer-events: auto;
    }}
    video, img.image-block {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }}
    .caption-block {{
      position: absolute;
      left: 10%;
      right: 10%;
      text-align: center;
      font-size: 48px;
      font-weight: 800;
      color: #ffeb3b;
      text-shadow: 2px 2px 8px rgba(0,0,0,0.8);
      pointer-events: auto;
    }}
    .caption-pos-bottom {{
      bottom: 20%;
    }}
    .caption-pos-top {{
      top: 10%;
    }}
    .caption-pos-center {{
      top: 50%;
      transform: translateY(-50%);
    }}
    .caption-pos-header {{
      top: 60px;
      font-size: 40px;
    }}
  </style>
</head>
<body>
  <div id="stage" data-composition-id="viralmint_stage" data-width="{w}" data-height="{h}" data-start="0" data-duration="{duration}">
{inner_content}
  </div>
  <script id="vm-timelines">
    window.__timelines = window.__timelines || {{}};
    window.__timelines_data = {timelines_json};
    if (window.gsap) {{
      var tl = gsap.timeline({{ paused: true }});
      tl.set({{}}, {{}}, {duration});
{gsap_tweens_code}
      window.__timelines["viralmint_stage"] = tl;
    }}
  </script>
  <script id="vm-stage-scale">
    (function() {{
      function fitStage() {{
        var stage = document.getElementById("stage");
        if (!stage) return;
        var w = parseFloat(stage.getAttribute("data-width")) || {w};
        var h = parseFloat(stage.getAttribute("data-height")) || {h};
        var winW = window.innerWidth || document.documentElement.clientWidth || w;
        var winH = window.innerHeight || document.documentElement.clientHeight || h;
        var scale = Math.min(winW / w, winH / h);
        stage.style.transform = "translate(-50%, -50%) scale(" + scale + ")";
      }}
      window.addEventListener("resize", fitStage);
      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", fitStage);
      }} else {{
        fitStage();
      }}
    }})();
  </script>
  <script id="vm-preview-bridge">
    (function() {{
      var compTime = 0;
      var totalDuration = {duration};
      var isPlaying = false;
      var isMuted = false;
      var lastRafTime = null;
      var lastPostTime = 0;
      var rafId = null;
      var rAF = (typeof requestAnimationFrame === "function") ? requestAnimationFrame : (typeof setTimeout === "function" ? function(cb) {{ return setTimeout(function() {{ cb(Date.now()); }}, 16); }} : function(cb) {{ return null; }});
      var cAF = (typeof cancelAnimationFrame === "function") ? cancelAnimationFrame : (typeof clearTimeout === "function" ? function(id) {{ clearTimeout(id); }} : function() {{}});

      function getMasterTl() {{
        return (window.__timelines && window.__timelines["viralmint_stage"]) ? window.__timelines["viralmint_stage"] : null;
      }}

      function getChildTimeline(frame) {{
        try {{
          var win = frame.contentWindow;
          if (!win) return null;
          var hfId = frame.parentElement ? frame.parentElement.getAttribute("data-hf-id") : null;
          var tls = win.__timelines;
          if (tls) {{
            if (hfId && tls[hfId]) return tls[hfId];
            var keys = Object.keys(tls);
            if (keys.length > 0 && tls[keys[0]]) return tls[keys[0]];
          }}
          if (win.tl && typeof win.tl.seek === "function") return win.tl;
        }} catch(e) {{}}
        return null;
      }}

      function updateComposition(time, playing, forceSeek) {{
        // 1. Root Master GSAP Timeline
        var master = getMasterTl();
        if (master && typeof master.seek === "function") {{
          master.pause();
          master.seek(time);
        }}

        // 2. Child Subcomposition Iframes
        var frames = document.querySelectorAll("iframe.subcomp-frame");
        if (frames && frames.forEach) {{
          frames.forEach(function(f) {{
            try {{
              var pEl = f.parentElement;
              var start = pEl ? (parseFloat(pEl.getAttribute("data-start")) || 0) : 0;
              var dur = pEl ? (parseFloat(pEl.getAttribute("data-duration")) || totalDuration) : totalDuration;
              var cTl = getChildTimeline(f);

              if (time < start) {{
                if (pEl) {{ pEl.style.visibility = "hidden"; }}
                if (cTl && typeof cTl.seek === "function") {{
                  cTl.pause();
                  cTl.seek(0);
                }}
              }} else if (time >= start && time <= (start + dur)) {{
                if (pEl) {{ pEl.style.visibility = "visible"; }}
                var localTime = Math.max(0, Math.min(dur, time - start));
                if (cTl && typeof cTl.seek === "function") {{
                  cTl.pause();
                  cTl.seek(localTime);
                }}
              }} else {{
                if (pEl) {{ pEl.style.visibility = "hidden"; }}
                if (cTl && typeof cTl.seek === "function") {{
                  cTl.pause();
                  cTl.seek(dur);
                }}
              }}
            }} catch(e) {{}}
          }});
        }}

        // 3. Media elements (video & audio)
        var mediaList = document.querySelectorAll("video, audio");
        if (mediaList && mediaList.forEach) {{
          mediaList.forEach(function(m) {{
            try {{
              var ds = m.dataset || {{}};
              var startVal = ds.start != null ? ds.start : (m.getAttribute ? m.getAttribute("data-start") : null);
              var cStart = parseFloat(startVal) || 0;
              var durVal = ds.duration != null ? ds.duration : (m.getAttribute ? m.getAttribute("data-duration") : null);
              var cDur = durVal != null ? (parseFloat(durVal) || totalDuration) : totalDuration;
              var trimVal = ds.mediaStart != null ? ds.mediaStart : (ds.playbackStart != null ? ds.playbackStart : (ds.trimStart != null ? ds.trimStart : (m.getAttribute ? (m.getAttribute("data-media-start") || m.getAttribute("data-playback-start") || m.getAttribute("data-trim-start")) : null)));
              var trimStart = parseFloat(trimVal) || 0;

              m.playsInline = true;
              if (isMuted) {{ m.muted = true; }}

              var isActive = (time >= cStart && time < (cStart + cDur));
              if (isActive) {{
                var targetLocal = trimStart + (time - cStart);
                if (m.style) {{
                  m.style.visibility = "visible";
                  m.style.display = "";
                }}
                if (playing) {{
                  if (m.paused) {{
                    m.currentTime = targetLocal;
                    var p = m.play();
                    if (p && p.catch) p.catch(function() {{}});
                  }} else if (forceSeek || Math.abs(m.currentTime - targetLocal) > 0.35) {{
                    m.currentTime = targetLocal;
                  }}
                }} else {{
                  if (!m.paused) {{
                    try {{ m.pause(); }} catch(e) {{}}
                  }}
                  if (forceSeek || Math.abs(m.currentTime - targetLocal) > 0.04) {{
                    m.currentTime = targetLocal;
                  }}
                }}
              }} else {{
                if (!m.paused) {{
                  try {{ m.pause(); }} catch(e) {{}}
                }}
                if (m.style) {{
                  m.style.visibility = "hidden";
                  m.style.display = "none";
                }}
                if (time < cStart) {{
                  m.currentTime = trimStart;
                }} else {{
                  m.currentTime = trimStart + cDur;
                }}
              }}
            }} catch(e) {{}}
          }});
        }}
      }}

      function emitRuntimeState() {{
        try {{
          window.parent.postMessage({{
            source: "vm-runtime",
            currentTime: compTime,
            duration: totalDuration,
            paused: !isPlaying
          }}, "*");
        }} catch(e) {{}}
      }}

      function emitRuntimeStateThrottled(now) {{
        if (!lastPostTime || (now - lastPostTime) > 60) {{
          lastPostTime = now;
          emitRuntimeState();
        }}
      }}

      function tick(rafNow) {{
        if (!isPlaying) return;
        if (!lastRafTime) lastRafTime = rafNow;
        var delta = (rafNow - lastRafTime) / 1000.0;
        lastRafTime = rafNow;

        compTime = Math.min(totalDuration, compTime + delta);

        if (compTime >= totalDuration) {{
          compTime = totalDuration;
          isPlaying = false;
          updateComposition(compTime, false);
          emitRuntimeState();
          return;
        }}

        updateComposition(compTime, true);
        emitRuntimeStateThrottled(rafNow);
        rafId = rAF(tick);
      }}

      function startPlayback() {{
        if (compTime >= totalDuration - 0.05) {{
          compTime = 0;
        }}
        isPlaying = true;
        lastRafTime = null;
        updateComposition(compTime, true, true);
        emitRuntimeState();
        if (rafId) cAF(rafId);
        rafId = rAF(tick);
      }}

      function pausePlayback() {{
        isPlaying = false;
        if (rafId) {{ cAF(rafId); rafId = null; }}
        updateComposition(compTime, false);
        emitRuntimeState();
      }}

      function seekTo(targetTime) {{
        compTime = Math.max(0, Math.min(Number(targetTime) || 0, totalDuration));
        updateComposition(compTime, isPlaying, true);
        emitRuntimeState();
      }}

      if (typeof document !== "undefined" && document.addEventListener) {{
        document.addEventListener("click", function(ev) {{
          var target = ev.target;
          while (target && target !== document.body && (!target.getAttribute || !target.getAttribute("data-hf-id"))) {{
            target = target.parentElement;
          }}
          if (target && target.getAttribute && target.getAttribute("data-hf-id")) {{
            var hfId = target.getAttribute("data-hf-id");
            try {{
              window.parent.postMessage({{
                source: "vm-runtime",
                action: "element_selected",
                id: hfId
              }}, "*");
            }} catch(e) {{}}
          }}
        }}, true);
      }}

      function hookSubcompFrames() {{
        var frames = document.querySelectorAll("iframe.subcomp-frame");
        if (frames && frames.forEach) {{
          frames.forEach(function(f) {{
            if (!f || f.__vmHooked || typeof f.addEventListener !== "function") return;
            f.__vmHooked = true;
            f.addEventListener("load", function() {{
              updateComposition(compTime, isPlaying, true);
              try {{
                var cDoc = f.contentDocument || (f.contentWindow && f.contentWindow.document);
                var hfId = f.parentElement ? f.parentElement.getAttribute("data-hf-id") : null;
                if (cDoc && hfId) {{
                  cDoc.addEventListener("click", function() {{
                    window.parent.postMessage({{
                      source: "vm-runtime",
                      action: "element_selected",
                      id: hfId
                    }}, "*");
                  }}, true);
                }}
              }} catch(e) {{}}
            }});
          }});
        }}
      }}

      function syncFrames(action, timeVal) {{
        if (action === "play") startPlayback();
        else if (action === "pause") pausePlayback();
        else if (action === "seek") seekTo(timeVal);
        else updateComposition(timeVal != null ? timeVal : compTime, isPlaying);
      }}

      hookSubcompFrames();
      setInterval(function() {{
        hookSubcompFrames();
        emitRuntimeState();
      }}, 250);

      window.addEventListener("message", function(ev) {{
        if (!ev.data) return;
        if (ev.data.source === "vm-subcomp-ready") {{
          updateComposition(compTime, isPlaying, true);
          return;
        }}
        if (ev.data.source !== "vm-parent") return;
        var a = ev.data.action;
        if (a === "play") {{
          startPlayback();
        }} else if (a === "pause") {{
          pausePlayback();
        }} else if (a === "seek") {{
          var t = ev.data.time != null ? ev.data.time : ev.data.seconds;
          seekTo(t);
        }} else if (a === "mute") {{
          isMuted = !!ev.data.muted;
          var mediaList = document.querySelectorAll("video, audio");
          if (mediaList && mediaList.forEach) {{
            mediaList.forEach(function(el) {{ el.muted = isMuted; }});
          }}
        }}
      }});

      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", function() {{
          updateComposition(0, false, true);
          emitRuntimeState();
        }});
      }} else {{
        updateComposition(0, false, true);
        emitRuntimeState();
      }}
    }})();
  </script>
</body>
</html>"""
        return html

    @staticmethod
    async def _resolve_asset_path(asset_id: str, must_exist: bool = True) -> Optional[Path]:
        """Resolve asset ID to filesystem Path using universal asset resolver."""
        try:
            _, p, _ = await resolve_asset_record_and_path(asset_id, must_exist=must_exist)
            return p
        except AssetNotFoundError:
            if must_exist:
                raise
            return None

    @classmethod
    async def sync_project_to_studio(cls, project_id: str, revision: Optional[int] = None) -> dict:
        """
        Sync a versioned project to the local Motion Studio index.html for interactive UI editing.
        Preserves revision metadata and assets manifest.
        """
        rev, doc = await ProjectService.freeze_for_render(project_id, revision)
        proj_dir = StudioService.project_dir()
        proj_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = proj_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        aspect = doc.get("aspect_ratio", "9:16")
        stage_dims = (1920, 1080) if aspect == "16:9" else ((1080, 1080) if aspect == "1:1" else (1080, 1920))

        # Resolve and stage any library assets or catalog block instances
        manifest_data = {}
        tracks = doc.get("timeline", {}).get("tracks", [])
        for t in tracks:
            for c in t.get("clips", []):
                if c.get("type") == "block" or c.get("block_id"):
                    block_name = c.get("block_id")
                    block_ver = c.get("block_version")
                    cid = c.get("id")
                    if block_name and cid:
                        try:
                            from backend.services.registry_adapter import RegistryAdapter
                            RegistryAdapter.stage_block_instance(
                                block_name=block_name,
                                version_hash=block_ver,
                                instance_id=cid,
                                dest_compositions_dir=proj_dir / "compositions",
                                variables=c.get("variables"),
                                aspect_ratio=aspect,
                                stage_dimensions=stage_dims,
                            )
                        except Exception as e:
                            logger.error("Failed staging block instance %s in studio: %s", cid, e)
                else:
                    aid = c.get("asset_id") or c.get("video_id")
                    if aid:
                        src_path = await cls._resolve_asset_path(aid, must_exist=True)
                        if src_path and src_path.is_file():
                            staged = StudioService.stage_asset_from_path(
                                src=src_path,
                                display_name=c.get("title") or src_path.name,
                                asset_id=aid,
                            )
                            c["file"] = staged["file"]
                            manifest_data[staged["file"]] = {
                                "asset_id": aid,
                                "display_name": c.get("title") or src_path.name,
                                "file": staged["file"],
                            }

        html = cls.project_doc_to_html(doc)

        # Write index.html, project_meta.json, and assets_manifest.json
        (proj_dir / "index.html").write_text(html, encoding="utf-8")
        (proj_dir / "project_meta.json").write_text(json.dumps({
            "project_id": project_id,
            "revision": rev,
            "title": doc.get("title", "Project"),
        }), encoding="utf-8")
        (proj_dir / "assets_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        return {
            "project_id": project_id,
            "revision": rev,
            "html_path": str(proj_dir / "index.html"),
        }

    @classmethod
    async def stage_project_for_render(cls, project_id: str, revision: Optional[int] = None, dest_dir: Optional[Path] = None) -> Tuple[int, Path]:
        """Create an isolated staging directory for an immutable render run.
        
        Guarantees that jobs for different projects or revisions do not collide
        or overwrite one another's assets or index.html.
        """
        from uuid import uuid4
        rev, doc = await ProjectService.freeze_for_render(project_id, revision)
        work_dir = dest_dir or (StudioService.project_dir().parent / f"render_{project_id}_{rev}_{uuid4().hex[:6]}")
        work_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = work_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        aspect = doc.get("aspect_ratio", "9:16")
        stage_dims = (1920, 1080) if aspect == "16:9" else ((1080, 1080) if aspect == "1:1" else (1080, 1920))

        # Resolve and stage any library assets or catalog block instances
        manifest_data = {}
        tracks = doc.get("timeline", {}).get("tracks", [])
        for t in tracks:
            for c in t.get("clips", []):
                if c.get("type") == "block" or c.get("block_id"):
                    block_name = c.get("block_id")
                    block_ver = c.get("block_version")
                    cid = c.get("id")
                    if block_name and cid:
                        try:
                            from backend.services.registry_adapter import RegistryAdapter
                            RegistryAdapter.stage_block_instance(
                                block_name=block_name,
                                version_hash=block_ver,
                                instance_id=cid,
                                dest_compositions_dir=work_dir / "compositions",
                                variables=c.get("variables"),
                                aspect_ratio=aspect,
                                stage_dimensions=stage_dims,
                            )
                        except Exception as e:
                            logger.error("Failed staging block instance %s for render: %s", cid, e)
                else:
                    aid = c.get("asset_id") or c.get("video_id")
                    if aid:
                        src_path = await cls._resolve_asset_path(aid, must_exist=True)
                        if not src_path or not src_path.is_file():
                            raise AssetNotFoundError(f"Required asset '{aid}' not found on disk for project render staging.")
                        clean_aid = re.sub(r"[^a-zA-Z0-9_-]", "_", str(aid))
                        staged_name = f"{clean_aid}_{src_path.name}"
                        dest_file = assets_dir / staged_name
                        if not dest_file.exists():
                            shutil.copyfile(src_path, dest_file)
                        c["file"] = staged_name
                        manifest_data[staged_name] = {
                            "asset_id": aid,
                            "title": c.get("title") or src_path.name,
                            "file": staged_name,
                        }

        html = cls.project_doc_to_html(doc)
        (work_dir / "index.html").write_text(html, encoding="utf-8")
        (work_dir / "project_meta.json").write_text(json.dumps({
            "project_id": project_id,
            "revision": rev,
            "title": doc.get("title", "Project"),
            "aspect_ratio": doc.get("aspect_ratio", "9:16"),
        }), encoding="utf-8")
        (work_dir / "assets_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
        
        return rev, work_dir
