# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Native Motion Compiler.

Transforms a NativeMotionSpec into:
1. A deterministic, offline HTML5/Canvas/JS playback bundle with frame-stepping APIs.
2. A 6Clips ProjectDocument (schema_version 2) with tracks, clips, and code references.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from backend.native_motion.schema import NativeMotionSpec


class NativeMotionCompiler:
    """Compiles typed native_motion_v1 specifications into playable documents."""

    @classmethod
    def compile_to_html(cls, spec: NativeMotionSpec) -> str:
        """Compile spec into a standalone, offline, zero-network HTML/JS playback file."""
        spec_dict = spec.model_dump()
        spec_json_str = json.dumps(spec_dict)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{spec.title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    #viewport {{
      position: relative;
      width: {spec.width}px;
      height: {spec.height}px;
      background: {spec.scenes[0].background_color if spec.scenes else "#0A0A0C"};
      overflow: hidden;
    }}
    canvas {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
    }}
  </style>
</head>
<body>
  <div id="viewport">
    <canvas id="motionCanvas" width="{spec.width}" height="{spec.height}"></canvas>
  </div>

  <script>
    (function() {{
      const SPEC = {spec_json_str};
      const canvas = document.getElementById('motionCanvas');
      const ctx = canvas.getContext('2d');
      const W = {spec.width};
      const H = {spec.height};
      const FPS = {spec.fps};
      const TOTAL_DURATION = {spec.duration_seconds};

      // Easing functions
      const EASING = {{
        linear: t => t,
        ease_in: t => t * t,
        ease_out: t => t * (2 - t),
        ease_in_out: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
        power2_in_out: t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t,
        power4_out: t => 1 - Math.pow(1 - t, 4),
        back_out: t => {{
          const c1 = 1.70158;
          const c3 = c1 + 1;
          return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
        }},
        elastic_out: t => {{
          if (t === 0) return 0;
          if (t === 1) return 1;
          return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * ((2 * Math.PI) / 3)) + 1;
        }},
        bounce_out: t => {{
          const n1 = 7.5625;
          const d1 = 2.75;
          if (t < 1 / d1) return n1 * t * t;
          if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
          if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
          return n1 * (t -= 2.625 / d1) * t + 0.984375;
        }},
        steps_4: t => Math.floor(t * 4) / 4
      }};

      function interpolate(v1, v2, p, easeName) {{
        const ease = EASING[easeName] || EASING.linear;
        const ep = ease(Math.max(0, Math.min(1, p)));
        if (typeof v1 === 'number' && typeof v2 === 'number') {{
          return v1 + (v2 - v1) * ep;
        }}
        return ep >= 1.0 ? v2 : v1;
      }}

      function renderFrameAt(timeSeconds) {{
        ctx.clearRect(0, 0, W, H);
        const t = Math.max(0, Math.min(TOTAL_DURATION, timeSeconds));

        // Find active scene
        for (const scene of SPEC.scenes) {{
          if (t >= scene.start_time && t <= scene.start_time + scene.duration) {{
            renderScene(scene, t - scene.start_time);
            break;
          }}
        }}
      }}

      function renderScene(scene, localTime) {{
        // Fill scene background
        ctx.fillStyle = scene.background_color || '#000000';
        ctx.fillRect(0, 0, W, H);

        const elements = (scene.elements || []).slice().sort((a, b) => (a.z_index || 0) - (b.z_index || 0));

        for (const elem of elements) {{
          if (localTime < elem.start_time || localTime > elem.start_time + elem.duration) {{
            continue;
          }}
          const elemTime = localTime - elem.start_time;
          renderElement(elem, elemTime);
        }}
      }}

      function getAnimatedProps(elem, elemTime) {{
        const props = Object.assign({{}}, elem.transform || {{}});
        if (!elem.keyframes || elem.keyframes.length === 0) return props;

        // Apply keyframes
        for (let i = 0; i < elem.keyframes.length; i++) {{
          const kf = elem.keyframes[i];
          if (elemTime >= kf.time) {{
            const nextKf = elem.keyframes[i + 1];
            if (!nextKf) {{
              Object.assign(props, kf.properties);
            }} else if (elemTime < nextKf.time) {{
              const p = (elemTime - kf.time) / (nextKf.time - kf.time);
              for (const key of Object.keys(nextKf.properties)) {{
                const v1 = kf.properties[key] !== undefined ? kf.properties[key] : props[key];
                const v2 = nextKf.properties[key];
                props[key] = interpolate(v1, v2, p, nextKf.easing);
              }}
              break;
            }}
          }}
        }}
        return props;
      }}

      function renderElement(elem, elemTime) {{
        const props = getAnimatedProps(elem, elemTime);
        const opacity = props.opacity !== undefined ? props.opacity : 1.0;
        if (opacity <= 0) return;

        ctx.save();
        ctx.globalAlpha = Math.max(0, Math.min(1, opacity));

        const x = props.x || 0;
        const y = props.y || 0;
        const w = props.width || 100;
        const h = props.height || 100;
        const rot = (props.rotation_deg || 0) * Math.PI / 180;
        const sx = props.scale_x !== undefined ? props.scale_x : 1.0;
        const sy = props.scale_y !== undefined ? props.scale_y : 1.0;
        const ax = props.anchor_x !== undefined ? props.anchor_x : 0.5;
        const ay = props.anchor_y !== undefined ? props.anchor_y : 0.5;

        ctx.translate(x, y);
        if (rot !== 0) ctx.rotate(rot);
        if (sx !== 1.0 || sy !== 1.0) ctx.scale(sx, sy);
        ctx.translate(-w * ax, -h * ay);

        if (elem.type === 'gradient' && elem.gradient_config) {{
          renderGradient(elem.gradient_config, w, h, elemTime);
        }} else if (elem.type === 'shape' && elem.shape_config) {{
          renderShape(elem.shape_config, w, h);
        }} else if (elem.type === 'text' && elem.text_config) {{
          renderText(elem.text_config, w, h);
        }} else if (elem.type === 'data_chart' && elem.chart_config) {{
          renderChart(elem.chart_config, w, h, elemTime, elem.duration);
        }} else if (elem.type === 'particles' && elem.particles_config) {{
          renderParticles(elem.particles_config, w, h, elemTime);
        }} else if (elem.type === 'shader_effect' && elem.shader_config) {{
          renderShader(elem.shader_config, w, h);
        }} else if (elem.type === 'captions' && elem.captions_config) {{
          renderCaptions(elem.captions_config, w, h, elemTime);
        }}

        ctx.restore();
      }}

      function renderGradient(cfg, w, h, time) {{
        let grad;
        if (cfg.type === 'linear') {{
          const angle = ((cfg.angle_degrees || 135) + (cfg.animated ? time * 20 * cfg.animation_speed : 0)) * Math.PI / 180;
          const x1 = w / 2 - Math.cos(angle) * w / 2;
          const y1 = h / 2 - Math.sin(angle) * h / 2;
          const x2 = w / 2 + Math.cos(angle) * w / 2;
          const y2 = h / 2 + Math.sin(angle) * h / 2;
          grad = ctx.createLinearGradient(x1, y1, x2, y2);
        }} else {{
          const shiftX = cfg.animated ? Math.sin(time * 1.5 * (cfg.animation_speed || 1.0)) * (w * 0.15) : 0;
          const shiftY = cfg.animated ? Math.cos(time * 1.5 * (cfg.animation_speed || 1.0)) * (h * 0.15) : 0;
          grad = ctx.createRadialGradient(w/2 + shiftX, h/2 + shiftY, 20, w/2, h/2, Math.max(w, h) / 1.3);
        }}
        for (const stop of cfg.stops || []) {{
          grad.addColorStop(stop.position, stop.color);
        }}
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);
      }}

      function renderShape(cfg, w, h) {{
        ctx.fillStyle = cfg.fill || '#2563EB';
        if (cfg.shape_type === 'rounded_rect') {{
          const r = Math.min(cfg.corner_radius || 16, w/2, h/2);
          ctx.beginPath();
          ctx.roundRect(0, 0, w, h, r);
          ctx.fill();
          if (cfg.stroke && cfg.stroke_width > 0) {{
            ctx.strokeStyle = cfg.stroke;
            ctx.lineWidth = cfg.stroke_width;
            ctx.stroke();
          }}
        }} else if (cfg.shape_type === 'circle') {{
          ctx.beginPath();
          ctx.arc(w/2, h/2, Math.min(w, h)/2, 0, Math.PI * 2);
          ctx.fill();
        }} else {{
          ctx.fillRect(0, 0, w, h);
        }}
      }}

      function renderText(cfg, w, h) {{
        const typo = cfg.typography || {{}};
        ctx.font = `${{typo.font_weight || 700}} ${{typo.font_size || 48}}px ${{typo.font_family || 'sans-serif'}}`;
        ctx.fillStyle = typo.fill || '#FFFFFF';
        ctx.textAlign = typo.text_align || 'center';
        ctx.textBaseline = 'middle';

        const alignX = typo.text_align === 'left' ? 0 : typo.text_align === 'right' ? w : w / 2;
        ctx.fillText(cfg.content || '', alignX, h / 2);
      }}

      function renderChart(cfg, w, h, elemTime, duration) {{
        const progress = cfg.animated_progress ? Math.min(1.0, elemTime / (duration * 0.4)) : 1.0;
        const easedProgress = EASING.power4_out(progress);

        if (cfg.chart_type === 'bar') {{
          const dataset = cfg.dataset || [];
          if (dataset.length === 0) return;
          const barWidth = (w / dataset.length) * 0.65;
          const gap = (w / dataset.length) * 0.35;
          const maxVal = Math.max(...dataset.map(d => d.value), 1.0);

          for (let i = 0; i < dataset.length; i++) {{
            const d = dataset[i];
            const barH = (d.value / maxVal) * (h * 0.7) * easedProgress;
            const x = i * (barWidth + gap) + gap / 2;
            const y = h - barH - 30;

            // Bar background
            ctx.fillStyle = d.color || '#38BDF8';
            ctx.beginPath();
            ctx.roundRect(x, y, barWidth, barH, [8, 8, 0, 0]);
            ctx.fill();

            // Value text
            if (cfg.show_values) {{
              ctx.font = '600 20px JetBrains Mono, monospace';
              ctx.fillStyle = '#FFFFFF';
              ctx.textAlign = 'center';
              ctx.fillText(Math.round(d.value * easedProgress).toString(), x + barWidth/2, y - 10);
            }}

            // Label text
            ctx.font = '500 16px Inter, sans-serif';
            ctx.fillStyle = '#94A3B8';
            ctx.textAlign = 'center';
            ctx.fillText(d.label, x + barWidth/2, h - 8);
          }}
        }}
      }}

      function renderParticles(cfg, w, h, elemTime) {{
        ctx.fillStyle = cfg.color || '#60A5FA';
        const count = Math.min(cfg.count || 50, 100);
        for (let i = 0; i < count; i++) {{
          const seed = i * 137.5;
          const speed = cfg.speed_range[0] + (seed % (cfg.speed_range[1] - cfg.speed_range[0]));
          const px = (seed * 97) % w;
          const py = (h - ((elemTime * speed + seed * 13) % h));
          const size = cfg.size_range[0] + (seed % (cfg.size_range[1] - cfg.size_range[0]));
          ctx.beginPath();
          ctx.arc(px, py, size, 0, Math.PI * 2);
          ctx.fill();
        }}
      }}

      function renderShader(cfg, w, h) {{
        if (cfg.effect_type === 'vignette') {{
          const grad = ctx.createRadialGradient(w/2, h/2, w * 0.3, w/2, h/2, w * 0.7);
          grad.addColorStop(0, 'rgba(0,0,0,0)');
          grad.addColorStop(1, `rgba(0,0,0,${{cfg.intensity || 0.5}})`);
          ctx.fillStyle = grad;
          ctx.fillRect(0, 0, w, h);
        }}
      }}

      function renderCaptions(cfg, w, h, elemTime) {{
        const words = cfg.words || [];
        if (words.length === 0) return;

        // Background veil
        if (cfg.background_veil) {{
          ctx.fillStyle = cfg.veil_color || 'rgba(15, 23, 42, 0.75)';
          ctx.beginPath();
          ctx.roundRect(0, 0, w, h, 16);
          ctx.fill();
        }}

        const typo = cfg.typography || {{}};
        ctx.font = `${{typo.font_weight || 800}} ${{typo.font_size || 38}}px ${{typo.font_family || 'sans-serif'}}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Find active word
        let activeIdx = -1;
        for (let i = 0; i < words.length; i++) {{
          if (elemTime >= words[i].start && elemTime <= words[i].end) {{
            activeIdx = i;
            break;
          }}
        }}

        // Layout words horizontally with word-wrap
        const spacing = 18;
        let line = [];
        let totalLineWidth = 0;
        for (let i = 0; i < words.length; i++) {{
          const word = words[i].word;
          const wordWidth = ctx.measureText(word).width;
          line.push({{ idx: i, word, width: wordWidth, isCurrent: i === activeIdx }});
          totalLineWidth += wordWidth + spacing;
        }}

        let startX = (w - totalLineWidth + spacing) / 2;
        const cy = h / 2;

        for (const item of line) {{
          if (item.isCurrent) {{
            ctx.fillStyle = cfg.active_color || '#FBBF24';
            ctx.save();
            ctx.translate(startX + item.width / 2, cy);
            ctx.scale(1.15, 1.15);
            ctx.fillText(item.word, 0, 0);
            ctx.restore();
          }} else {{
            ctx.fillStyle = cfg.inactive_color || '#94A3B8';
            ctx.fillText(item.word, startX + item.width / 2, cy);
          }}
          startX += item.width + spacing;
        }}
      }}

      // Frame stepping API for external playback & headless render
      window.__seekTime = renderFrameAt;
      window.__seekFrame = function(frameIndex, totalFrames) {{
        const time = (frameIndex / FPS);
        renderFrameAt(time);
      }};

      // Render initial frame at t = 0
      renderFrameAt(0.0);
    }})();
  </script>
</body>
</html>"""
        return html

    @classmethod
    def compile_to_project_document(cls, spec: NativeMotionSpec) -> Dict[str, Any]:
        """Compile NativeMotionSpec into canonical 6Clips ProjectDocument (schema_version=2)."""
        doc = {
            "schema_version": 2,
            "title": spec.title,
            "aspect_ratio": spec.constraints.aspect_ratio,
            "timeline": {
                "fps": spec.fps,
                "duration_seconds": spec.duration_seconds,
                "tracks": [
                    {
                        "id": "track_native_motion",
                        "type": "video",
                        "name": "Native Motion",
                        "visible": True,
                        "locked": False,
                        "muted": False,
                        "solo": False,
                        "clips": [
                            {
                                "id": f"clip_{scene.id}",
                                "type": "native_motion",
                                "name": f"Scene {idx+1}",
                                "start_time": scene.start_time,
                                "duration": scene.duration,
                                "source_scene_id": scene.id,
                                "visible": True,
                                "locked": False,
                            }
                            for idx, scene in enumerate(spec.scenes)
                        ],
                    },
                    {
                        "id": "track_native_audio",
                        "type": "audio",
                        "name": "Audio Track",
                        "visible": True,
                        "locked": False,
                        "muted": False,
                        "solo": False,
                        "clips": [
                            {
                                "id": f"clip_{audio.id}",
                                "type": "audio",
                                "name": "Speech / BGM",
                                "start_time": audio.start_time,
                                "duration": audio.duration,
                                "source_path": audio.file_path,
                                "volume": audio.volume,
                            }
                            for audio in spec.audio_tracks
                        ],
                    },
                ],
            },
            "code": {
                "files": [
                    {
                        "id": f"file_{spec.id}",
                        "path": "native_motion/spec.json",
                        "name": "spec.json",
                        "content": spec.model_dump_json(indent=2),
                        "read_only": False,
                        "provenance": "native_motion_v1",
                    }
                ]
            },
            "metadata": {
                "native_motion_id": spec.id,
                "creative_brief": spec.brief.model_dump(),
                "knowledge_refs": [ref.model_dump() for ref in spec.knowledge_refs],
                "safe_zones": spec.safe_zones.model_dump(),
            },
        }
        return doc
