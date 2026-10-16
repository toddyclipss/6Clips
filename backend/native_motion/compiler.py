# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Native Motion Compiler.

Transforms a NativeMotionSpec into:
1. A deterministic, offline HTML5/Canvas/JS playback bundle with frame-stepping APIs,
   supporting multi-scene timelines, true frame-motion scene transitions, kinetic
   typography with per-word/per-glyph animations, technical data diagrams, reframed
   video viewports, and safe-zone anchored speech captions.
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

      // Offscreen buffers for scene transition composition
      const offCanvasA = document.createElement('canvas');
      offCanvasA.width = W;
      offCanvasA.height = H;
      const offCtxA = offCanvasA.getContext('2d');

      const offCanvasB = document.createElement('canvas');
      offCanvasB.width = W;
      offCanvasB.height = H;
      const offCtxB = offCanvasB.getContext('2d');

      // Comprehensive easing curves
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

        const scenes = SPEC.scenes || [];
        if (scenes.length === 0) return;

        // Check if current time falls within a transition between adjacent scenes
        let activeIdx = -1;
        for (let i = 0; i < scenes.length; i++) {{
          const s = scenes[i];
          const sEnd = s.start_time + s.duration;
          if (t >= s.start_time && t <= sEnd) {{
            activeIdx = i;
            break;
          }}
        }}

        if (activeIdx === -1) {{
          // Beyond end or before start: clamp to last scene
          activeIdx = scenes.length - 1;
        }}

        const curScene = scenes[activeIdx];
        const nextScene = (activeIdx + 1 < scenes.length) ? scenes[activeIdx + 1] : null;
        const trans = curScene.transition;

        if (trans && trans.type !== 'none' && trans.duration > 0 && nextScene) {{
          const transStart = curScene.start_time + curScene.duration - trans.duration;
          if (t >= transStart) {{
            // We are in the transition zone between curScene and nextScene
            const pRaw = (t - transStart) / trans.duration;
            const p = Math.max(0, Math.min(1, pRaw));
            const easeFn = EASING[trans.easing] || EASING.ease_in_out;
            const ep = easeFn(p);

            // Render current scene to offCanvasA
            offCtxA.clearRect(0, 0, W, H);
            renderSceneToContext(offCtxA, curScene, t - curScene.start_time);

            // Render next scene to offCanvasB
            offCtxB.clearRect(0, 0, W, H);
            renderSceneToContext(offCtxB, nextScene, Math.max(0, t - nextScene.start_time));

            // Blend on main canvas with true frame motion
            renderTransition(trans.type, offCanvasA, offCanvasB, ep);
            return;
          }}
        }}

        // Normal scene playback without active transition
        renderSceneToContext(ctx, curScene, t - curScene.start_time);
      }}

      function renderTransition(type, cvA, cvB, p) {{
        ctx.save();
        if (type === 'crossfade') {{
          ctx.globalAlpha = 1.0 - p;
          ctx.drawImage(cvA, 0, 0);
          ctx.globalAlpha = p;
          ctx.drawImage(cvB, 0, 0);
        }} else if (type === 'slide_left') {{
          ctx.drawImage(cvA, -W * p, 0);
          ctx.drawImage(cvB, W * (1 - p), 0);
        }} else if (type === 'slide_right') {{
          ctx.drawImage(cvA, W * p, 0);
          ctx.drawImage(cvB, -W * (1 - p), 0);
        }} else if (type === 'slide_up') {{
          ctx.drawImage(cvA, 0, -H * p);
          ctx.drawImage(cvB, 0, H * (1 - p));
        }} else if (type === 'slide_down') {{
          ctx.drawImage(cvA, 0, H * p);
          ctx.drawImage(cvB, 0, -H * (1 - p));
        }} else if (type === 'wipe_horizontal') {{
          ctx.drawImage(cvA, 0, 0);
          ctx.save();
          ctx.beginPath();
          ctx.rect(0, 0, W * p, H);
          ctx.clip();
          ctx.drawImage(cvB, 0, 0);
          ctx.restore();
        }} else if (type === 'wipe_radial') {{
          ctx.drawImage(cvA, 0, 0);
          ctx.save();
          ctx.beginPath();
          const rMax = Math.hypot(W / 2, H / 2);
          ctx.arc(W / 2, H / 2, rMax * p, 0, Math.PI * 2);
          ctx.clip();
          ctx.drawImage(cvB, 0, 0);
          ctx.restore();
        }} else if (type === 'zoom_in') {{
          ctx.save();
          ctx.globalAlpha = 1.0 - p;
          const sA = 1.0 + 0.3 * p;
          ctx.translate(W / 2, H / 2);
          ctx.scale(sA, sA);
          ctx.translate(-W / 2, -H / 2);
          ctx.drawImage(cvA, 0, 0);
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = p;
          const sB = 0.8 + 0.2 * p;
          ctx.translate(W / 2, H / 2);
          ctx.scale(sB, sB);
          ctx.translate(-W / 2, -H / 2);
          ctx.drawImage(cvB, 0, 0);
          ctx.restore();
        }} else if (type === 'zoom_out') {{
          ctx.save();
          ctx.globalAlpha = 1.0 - p;
          const sA = 1.0 - 0.2 * p;
          ctx.translate(W / 2, H / 2);
          ctx.scale(sA, sA);
          ctx.translate(-W / 2, -H / 2);
          ctx.drawImage(cvA, 0, 0);
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = p;
          const sB = 1.25 - 0.25 * p;
          ctx.translate(W / 2, H / 2);
          ctx.scale(sB, sB);
          ctx.translate(-W / 2, -H / 2);
          ctx.drawImage(cvB, 0, 0);
          ctx.restore();
        }} else {{
          // Default cut
          ctx.drawImage(p < 0.5 ? cvA : cvB, 0, 0);
        }}
        ctx.restore();
      }}

      function renderSceneToContext(targetCtx, scene, localTime) {{
        targetCtx.save();
        // Camera projection
        const cam = scene.camera || {{ zoom: 1.0, pan_x: 0, pan_y: 0, rotation_z: 0 }};
        const zoom = cam.zoom || 1.0;
        const panX = cam.pan_x || 0.0;
        const panY = cam.pan_y || 0.0;
        const rotZ = (cam.rotation_z || 0.0) * Math.PI / 180;

        if (zoom !== 1.0 || panX !== 0 || panY !== 0 || rotZ !== 0) {{
          targetCtx.translate(W / 2 + panX, H / 2 + panY);
          if (rotZ !== 0) targetCtx.rotate(rotZ);
          if (zoom !== 1.0) targetCtx.scale(zoom, zoom);
          targetCtx.translate(-W / 2, -H / 2);
        }}

        // Scene background
        targetCtx.fillStyle = scene.background_color || '#000000';
        targetCtx.fillRect(0, 0, W, H);

        const elements = (scene.elements || []).slice().sort((a, b) => (a.z_index || 0) - (b.z_index || 0));

        for (const elem of elements) {{
          if (localTime < elem.start_time || localTime > elem.start_time + elem.duration) {{
            continue;
          }}
          const elemTime = localTime - elem.start_time;
          renderElementToContext(targetCtx, elem, elemTime);
        }}
        targetCtx.restore();
      }}

      function getAnimatedProps(elem, elemTime) {{
        const props = Object.assign({{}}, elem.transform || {{}});
        if (!elem.keyframes || elem.keyframes.length === 0) return props;

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

      function renderElementToContext(targetCtx, elem, elemTime) {{
        const props = getAnimatedProps(elem, elemTime);
        const opacity = props.opacity !== undefined ? props.opacity : 1.0;
        if (opacity <= 0) return;

        targetCtx.save();
        targetCtx.globalAlpha = Math.max(0, Math.min(1, opacity));

        const x = props.x || 0;
        const y = props.y || 0;
        const w = props.width || 100;
        const h = props.height || 100;
        const rot = (props.rotation_deg || 0) * Math.PI / 180;
        const sx = props.scale_x !== undefined ? props.scale_x : 1.0;
        const sy = props.scale_y !== undefined ? props.scale_y : 1.0;
        const ax = props.anchor_x !== undefined ? props.anchor_x : 0.5;
        const ay = props.anchor_y !== undefined ? props.anchor_y : 0.5;

        targetCtx.translate(x, y);
        if (rot !== 0) targetCtx.rotate(rot);
        if (sx !== 1.0 || sy !== 1.0) targetCtx.scale(sx, sy);
        targetCtx.translate(-w * ax, -h * ay);

        if (elem.type === 'gradient' && elem.gradient_config) {{
          renderGradient(targetCtx, elem.gradient_config, w, h, elemTime);
        }} else if (elem.type === 'shape' && elem.shape_config) {{
          renderShape(targetCtx, elem.shape_config, w, h);
        }} else if (elem.type === 'text' && elem.text_config) {{
          renderText(targetCtx, elem.text_config, w, h, elemTime, elem.duration);
        }} else if (elem.type === 'data_chart' && elem.chart_config) {{
          renderChart(targetCtx, elem.chart_config, w, h, elemTime, elem.duration);
        }} else if (elem.type === 'particles' && elem.particles_config) {{
          renderParticles(targetCtx, elem.particles_config, w, h, elemTime);
        }} else if (elem.type === 'shader_effect' && elem.shader_config) {{
          renderShader(targetCtx, elem.shader_config, w, h);
        }} else if (elem.type === 'captions' && elem.captions_config) {{
          renderCaptions(targetCtx, elem.captions_config, w, h, elemTime);
        }} else if (elem.type === 'video_layer' && elem.video_config) {{
          renderVideoLayer(targetCtx, elem.video_config, w, h, elemTime, elem.duration);
        }}

        targetCtx.restore();
      }}

      function renderGradient(tCtx, cfg, w, h, time) {{
        let grad;
        if (cfg.type === 'linear') {{
          const angle = ((cfg.angle_degrees || 135) + (cfg.animated ? time * 20 * (cfg.animation_speed || 1.0) : 0)) * Math.PI / 180;
          const x1 = w / 2 - Math.cos(angle) * w / 2;
          const y1 = h / 2 - Math.sin(angle) * h / 2;
          const x2 = w / 2 + Math.cos(angle) * w / 2;
          const y2 = h / 2 + Math.sin(angle) * h / 2;
          grad = tCtx.createLinearGradient(x1, y1, x2, y2);
        }} else {{
          const shiftX = cfg.animated ? Math.sin(time * 1.5 * (cfg.animation_speed || 1.0)) * (w * 0.15) : 0;
          const shiftY = cfg.animated ? Math.cos(time * 1.5 * (cfg.animation_speed || 1.0)) * (h * 0.15) : 0;
          grad = tCtx.createRadialGradient(w/2 + shiftX, h/2 + shiftY, 20, w/2, h/2, Math.max(w, h) / 1.3);
        }}
        for (const stop of cfg.stops || []) {{
          grad.addColorStop(stop.position, stop.color);
        }}
        tCtx.fillStyle = grad;
        tCtx.fillRect(0, 0, w, h);
      }}

      function renderShape(tCtx, cfg, w, h) {{
        tCtx.fillStyle = cfg.fill || '#2563EB';
        if (cfg.shape_type === 'rounded_rect') {{
          const r = Math.min(cfg.corner_radius || 16, w/2, h/2);
          tCtx.beginPath();
          tCtx.roundRect(0, 0, w, h, r);
          tCtx.fill();
          if (cfg.stroke && cfg.stroke_width > 0) {{
            tCtx.strokeStyle = cfg.stroke;
            tCtx.lineWidth = cfg.stroke_width;
            tCtx.stroke();
          }}
        }} else if (cfg.shape_type === 'circle') {{
          tCtx.beginPath();
          tCtx.arc(w/2, h/2, Math.min(w, h)/2, 0, Math.PI * 2);
          tCtx.fill();
        }} else {{
          tCtx.fillRect(0, 0, w, h);
        }}
      }}

      function renderText(tCtx, cfg, w, h, elemTime, duration) {{
        const typo = cfg.typography || {{}};
        tCtx.font = `${{typo.font_weight || 700}} ${{typo.font_size || 48}}px ${{typo.font_family || 'sans-serif'}}`;
        tCtx.fillStyle = typo.fill || '#FFFFFF';
        tCtx.textAlign = typo.text_align || 'center';
        tCtx.textBaseline = 'middle';

        const rawContent = cfg.content || '';
        const animType = cfg.animation_type || 'none';

        if (animType === 'typewriter') {{
          const stagger = cfg.stagger_delay || 0.04;
          const charCount = Math.floor(elemTime / stagger);
          let visibleStr = rawContent.slice(0, Math.min(rawContent.length, charCount));
          if (charCount < rawContent.length && Math.floor(elemTime * 3) % 2 === 0) {{
            visibleStr += '|';
          }}
          const alignX = typo.text_align === 'left' ? 0 : typo.text_align === 'right' ? w : w / 2;
          tCtx.fillText(visibleStr, alignX, h / 2);
        }} else if (animType === 'word_pop' || animType === 'fade_slide_up' || animType === 'kinetic_scale') {{
          const words = rawContent.split(' ');
          const stagger = cfg.stagger_delay || 0.08;
          const totalWords = words.length;

          // Compute word widths
          const wordMetrics = words.map(w => tCtx.measureText(w).width);
          const spaceWidth = tCtx.measureText(' ').width;
          const totalTextW = wordMetrics.reduce((a, b) => a + b, 0) + spaceWidth * (totalWords - 1);

          let curX = (w - totalTextW) / 2;
          const cy = h / 2;

          for (let i = 0; i < totalWords; i++) {{
            const wStr = words[i];
            const wW = wordMetrics[i];
            const wStart = i * stagger;

            if (elemTime >= wStart) {{
              const p = Math.min(1.0, (elemTime - wStart) / 0.35);
              tCtx.save();
              if (animType === 'word_pop') {{
                const s = EASING.back_out(p);
                tCtx.translate(curX + wW / 2, cy);
                tCtx.scale(s, s);
                tCtx.translate(-(curX + wW / 2), -cy);
              }} else if (animType === 'fade_slide_up') {{
                const dy = (1.0 - EASING.power4_out(p)) * 25.0;
                tCtx.globalAlpha *= p;
                tCtx.translate(0, dy);
              }} else if (animType === 'kinetic_scale') {{
                const s = 1.0 + (1.0 - EASING.power4_out(p)) * 0.6;
                tCtx.translate(curX + wW / 2, cy);
                tCtx.scale(s, s);
                tCtx.translate(-(curX + wW / 2), -cy);
              }}

              // Highlight check
              const isHighlight = (cfg.highlight_words || []).some(hw => hw.toLowerCase() === wStr.toLowerCase().replace(/[^a-z0-9]/g, ''));
              if (isHighlight) {{
                tCtx.fillStyle = cfg.highlight_color || '#38BDF8';
                tCtx.shadowColor = cfg.highlight_color || '#38BDF8';
                tCtx.shadowBlur = 12;
              }} else {{
                tCtx.fillStyle = typo.fill || '#FFFFFF';
              }}

              tCtx.fillText(wStr, curX + wW / 2, cy);
              tCtx.restore();
            }}
            curX += wW + spaceWidth;
          }}
        }} else {{
          // Standard full-text render
          const alignX = typo.text_align === 'left' ? 0 : typo.text_align === 'right' ? w : w / 2;
          tCtx.fillText(rawContent, alignX, h / 2);
        }}

        // Draw source attribution badge if present
        if (cfg.source_attribution) {{
          tCtx.save();
          const badgeText = `SOURCE: ${{cfg.source_attribution}}`;
          tCtx.font = '500 14px JetBrains Mono, monospace';
          const bW = tCtx.measureText(badgeText).width + 24;
          const bH = 26;
          const bX = (w - bW) / 2;
          const bY = h - bH - 4;

          tCtx.fillStyle = 'rgba(15, 23, 42, 0.75)';
          tCtx.beginPath();
          tCtx.roundRect(bX, bY, bW, bH, 6);
          tCtx.fill();

          tCtx.strokeStyle = 'rgba(148, 163, 184, 0.4)';
          tCtx.lineWidth = 1;
          tCtx.stroke();

          tCtx.fillStyle = '#94A3B8';
          tCtx.textAlign = 'center';
          tCtx.textBaseline = 'middle';
          tCtx.fillText(badgeText, w / 2, bY + bH / 2);
          tCtx.restore();
        }}
      }}

      function renderChart(tCtx, cfg, w, h, elemTime, duration) {{
        const cType = cfg.chart_type || 'bar';

        if (cType === 'counter') {{
          // Dynamic Numeric Metric Counter
          const prog = Math.min(1.0, elemTime / Math.max(0.4, duration * 0.65));
          const eased = EASING.power4_out(prog);
          const startVal = cfg.counter_start !== undefined ? cfg.counter_start : 0.0;
          const endVal = cfg.counter_end !== undefined ? cfg.counter_end : 100.0;
          const curVal = startVal + (endVal - startVal) * eased;
          const decimals = cfg.counter_decimals !== undefined ? cfg.counter_decimals : 0;
          const numStr = curVal.toFixed(decimals);
          const displayStr = `${{cfg.counter_prefix || ''}}${{numStr}}${{cfg.counter_suffix || ''}}`;

          tCtx.save();
          tCtx.textAlign = 'center';
          tCtx.textBaseline = 'middle';
          tCtx.font = '900 84px Outfit, sans-serif';
          tCtx.fillStyle = '#38BDF8';
          tCtx.shadowColor = 'rgba(56, 189, 248, 0.5)';
          tCtx.shadowBlur = 24;
          tCtx.fillText(displayStr, w / 2, h / 2 - 20);

          if (cfg.title) {{
            tCtx.font = '600 22px JetBrains Mono, monospace';
            tCtx.fillStyle = '#94A3B8';
            tCtx.shadowBlur = 0;
            tCtx.fillText(cfg.title.toUpperCase(), w / 2, h / 2 + 50);
          }}
          tCtx.restore();
          return;
        }}

        if (cType === 'diagram_attention') {{
          // Multi-Stage Transformer Attention Infographic
          renderAttentionDiagram(tCtx, cfg, w, h, elemTime, duration);
          return;
        }}

        if (cType === 'donut') {{
          // Circular Donut Progress Ring
          const prog = cfg.animated_progress ? Math.min(1.0, elemTime / (duration * 0.5)) : 1.0;
          const eased = EASING.power4_out(prog);
          const cx = w / 2;
          const cy = h / 2;
          const r = Math.min(w, h) * 0.35;
          const strokeW = 20;

          // Track
          tCtx.save();
          tCtx.beginPath();
          tCtx.arc(cx, cy, r, 0, Math.PI * 2);
          tCtx.strokeStyle = 'rgba(30, 41, 59, 0.8)';
          tCtx.lineWidth = strokeW;
          tCtx.stroke();

          // Progress Arc
          tCtx.beginPath();
          tCtx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + (Math.PI * 2 * eased), false);
          tCtx.strokeStyle = '#38BDF8';
          tCtx.lineWidth = strokeW;
          tCtx.lineCap = 'round';
          tCtx.shadowColor = '#38BDF8';
          tCtx.shadowBlur = 16;
          tCtx.stroke();

          // Center Text
          tCtx.font = '800 48px Outfit, sans-serif';
          tCtx.fillStyle = '#F8FAFC';
          tCtx.textAlign = 'center';
          tCtx.textBaseline = 'middle';
          tCtx.fillText(`${{Math.round(eased * 100)}}%`, cx, cy);
          tCtx.restore();
          return;
        }}

        // Default 'bar' chart
        const progress = cfg.animated_progress ? Math.min(1.0, elemTime / (duration * 0.45)) : 1.0;
        const easedProgress = EASING.power4_out(progress);
        const dataset = cfg.dataset || [];
        if (dataset.length === 0) return;

        const barWidth = (w / dataset.length) * 0.65;
        const gap = (w / dataset.length) * 0.35;
        const maxVal = Math.max(...dataset.map(d => d.value), 1.0);

        for (let i = 0; i < dataset.length; i++) {{
          const d = dataset[i];
          const barH = (d.value / maxVal) * (h * 0.7) * easedProgress;
          const x = i * (barWidth + gap) + gap / 2;
          const y = h - barH - 35;

          tCtx.fillStyle = d.color || '#38BDF8';
          tCtx.beginPath();
          tCtx.roundRect(x, y, barWidth, barH, [8, 8, 0, 0]);
          tCtx.fill();

          if (cfg.show_values) {{
            tCtx.font = '600 20px JetBrains Mono, monospace';
            tCtx.fillStyle = '#FFFFFF';
            tCtx.textAlign = 'center';
            tCtx.fillText(Math.round(d.value * easedProgress).toString(), x + barWidth / 2, y - 10);
          }}

          tCtx.font = '500 16px Inter, sans-serif';
          tCtx.fillStyle = '#94A3B8';
          tCtx.textAlign = 'center';
          tCtx.fillText(d.label, x + barWidth / 2, h - 8);
        }}
      }}

      function renderAttentionDiagram(tCtx, cfg, w, h, elemTime, duration) {{
        // Detailed Transformer Scaled Dot-Product & Multi-Head Attention Infographic
        tCtx.save();
        const tokens = ['The', 'neural', 'attention', 'layer'];
        const heads = cfg.attention_heads || 4;
        const matrix = cfg.attention_matrix || [
          [0.72, 0.14, 0.08, 0.06],
          [0.10, 0.68, 0.15, 0.07],
          [0.05, 0.12, 0.76, 0.07],
          [0.04, 0.08, 0.12, 0.76]
        ];

        // Header Title
        tCtx.font = '700 26px Outfit, sans-serif';
        tCtx.fillStyle = '#F8FAFC';
        tCtx.textAlign = 'left';
        tCtx.fillText('TRANSFORMER ATTENTION MECHANISM', 40, 48);

        tCtx.font = '400 16px JetBrains Mono, monospace';
        tCtx.fillStyle = '#38BDF8';
        tCtx.fillText('Attention(Q, K, V) = softmax(Q·K^T / √d_k) · V', 40, 80);

        // Stage 1: Input Tokens (Left column)
        const leftX = 60;
        const startY = 130;
        const tokenH = 44;
        const gapY = 20;

        for (let i = 0; i < tokens.length; i++) {{
          const y = startY + i * (tokenH + gapY);
          tCtx.fillStyle = 'rgba(30, 41, 59, 0.85)';
          tCtx.beginPath();
          tCtx.roundRect(leftX, y, 140, tokenH, 8);
          tCtx.fill();
          tCtx.strokeStyle = '#38BDF8';
          tCtx.lineWidth = 1.5;
          tCtx.stroke();

          tCtx.font = '600 17px Inter, sans-serif';
          tCtx.fillStyle = '#FFFFFF';
          tCtx.textAlign = 'center';
          tCtx.fillText(`X[${{i}}]: "${{tokens[i]}}"`, leftX + 70, y + tokenH / 2 + 5);
        }}

        // Stage 2: Q, K, V Projections (Middle-left)
        const projX = 260;
        const projBlocks = [
          {{ label: 'Query (Q)', color: '#818CF8' }},
          {{ label: 'Key (K)', color: '#38BDF8' }},
          {{ label: 'Value (V)', color: '#34D399' }}
        ];

        for (let i = 0; i < projBlocks.length; i++) {{
          const b = projBlocks[i];
          const y = startY + i * 85;
          tCtx.fillStyle = 'rgba(15, 23, 42, 0.9)';
          tCtx.beginPath();
          tCtx.roundRect(projX, y, 130, 58, 8);
          tCtx.fill();
          tCtx.strokeStyle = b.color;
          tCtx.lineWidth = 2;
          tCtx.stroke();

          tCtx.font = '700 15px JetBrains Mono, monospace';
          tCtx.fillStyle = b.color;
          tCtx.textAlign = 'center';
          tCtx.fillText(b.label, projX + 65, y + 34);

          // Flow pulses
          const pulse = (elemTime * 3 + i) % 1;
          tCtx.beginPath();
          tCtx.arc(leftX + 140 + (projX - (leftX + 140)) * pulse, y + 29, 3, 0, Math.PI * 2);
          tCtx.fillStyle = b.color;
          tCtx.fill();
        }}

        // Stage 3: Scaled Dot-Product Attention Heatmap Matrix (Center)
        const matX = 450;
        const matY = 130;
        const cellSize = 54;

        tCtx.font = '600 15px JetBrains Mono, monospace';
        tCtx.fillStyle = '#94A3B8';
        tCtx.textAlign = 'center';
        tCtx.fillText('ATTENTION WEIGHTS (Q·K^T / √d_k)', matX + (cellSize * 4) / 2, matY - 15);

        for (let r = 0; r < 4; r++) {{
          for (let c = 0; c < 4; c++) {{
            const val = matrix[r][c];
            const cx = matX + c * cellSize;
            const cy = matY + r * cellSize;

            // Heatmap color intensity
            const alpha = Math.max(0.15, Math.min(1.0, val));
            tCtx.fillStyle = `rgba(56, 189, 248, ${{alpha}})`;
            tCtx.fillRect(cx, cy, cellSize - 2, cellSize - 2);

            tCtx.font = '600 13px JetBrains Mono, monospace';
            tCtx.fillStyle = val > 0.4 ? '#090D16' : '#E2E8F0';
            tCtx.textAlign = 'center';
            tCtx.fillText(val.toFixed(2), cx + cellSize / 2, cy + cellSize / 2 + 5);
          }}
        }}

        // Stage 4: Multi-Head Projection Arcs & Output Z (Right)
        const outX = 730;
        const outY = 150;
        tCtx.fillStyle = 'rgba(15, 23, 42, 0.95)';
        tCtx.beginPath();
        tCtx.roundRect(outX, outY, 180, 160, 12);
        tCtx.fill();
        tCtx.strokeStyle = '#FBBF24';
        tCtx.lineWidth = 2;
        tCtx.stroke();

        tCtx.font = '700 16px Outfit, sans-serif';
        tCtx.fillStyle = '#FBBF24';
        tCtx.textAlign = 'center';
        tCtx.fillText('MULTI-HEAD CONTEXT Z', outX + 90, outY + 36);

        tCtx.font = '500 14px JetBrains Mono, monospace';
        tCtx.fillStyle = '#94A3B8';
        tCtx.fillText(`Heads: ${{heads}} // d_k: 64`, outX + 90, outY + 68);
        tCtx.fillText('Z = Concat(head_i)W^O', outX + 90, outY + 98);

        // Animated Attention Flow indicator
        const flowTime = (elemTime * 1.5) % 1;
        tCtx.fillStyle = '#34D399';
        tCtx.beginPath();
        tCtx.arc(outX + 90, outY + 130, 6 + Math.sin(elemTime * 4) * 2, 0, Math.PI * 2);
        tCtx.fill();

        tCtx.restore();
      }}

      function renderVideoLayer(tCtx, cfg, w, h, elemTime, duration) {{
        // Dynamic Reframed Video Viewport Simulation
        tCtx.save();
        // Base viewport background
        tCtx.fillStyle = '#0F172A';
        tCtx.fillRect(0, 0, w, h);

        // Presentation frame outline
        tCtx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
        tCtx.lineWidth = 2;
        tCtx.strokeRect(20, 20, w - 40, h - 40);

        // Dynamic 9:16 Reframe Tracking Box
        const crop = cfg.crop_rect || {{ x: 0.25, y: 0.1, w: 0.5, h: 0.8 }};
        const rx = crop.x * w;
        const ry = crop.y * h;
        const rw = crop.w * w;
        const rh = crop.h * h;

        // Draw camera HUD crosshairs
        tCtx.strokeStyle = '#38BDF8';
        tCtx.lineWidth = 2;
        // Corner brackets
        const bLen = 24;
        // Top-left
        tCtx.beginPath();
        tCtx.moveTo(rx, ry + bLen); tCtx.lineTo(rx, ry); tCtx.lineTo(rx + bLen, ry);
        tCtx.stroke();
        // Top-right
        tCtx.beginPath();
        tCtx.moveTo(rx + rw - bLen, ry); tCtx.lineTo(rx + rw, ry); tCtx.lineTo(rx + rw, ry + bLen);
        tCtx.stroke();
        // Bottom-left
        tCtx.beginPath();
        tCtx.moveTo(rx, ry + rh - bLen); tCtx.lineTo(rx, ry + rh); tCtx.lineTo(rx + bLen, ry + rh);
        tCtx.stroke();
        // Bottom-right
        tCtx.beginPath();
        tCtx.moveTo(rx + rw - bLen, ry + rh); tCtx.lineTo(rx + rw, ry + rh); tCtx.lineTo(rx + rw, ry + rh - bLen);
        tCtx.stroke();

        // Viewport label
        tCtx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        tCtx.beginPath();
        tCtx.roundRect(rx + 10, ry + 10, 180, 28, 6);
        tCtx.fill();

        tCtx.font = '600 13px JetBrains Mono, monospace';
        tCtx.fillStyle = '#38BDF8';
        tCtx.textAlign = 'left';
        tCtx.fillText('AUTO-REFRAME // 9:16', rx + 20, ry + 28);

        // Audio VU meter simulation
        const vuY = ry + rh - 25;
        const vuW = 120;
        tCtx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        tCtx.fillRect(rx + 10, vuY, vuW, 12);
        const vuLevel = Math.max(0.1, (Math.sin(elemTime * 8) + 1.0) / 2.0);
        tCtx.fillStyle = vuLevel > 0.8 ? '#EF4444' : vuLevel > 0.6 ? '#FBBF24' : '#10B981';
        tCtx.fillRect(rx + 10, vuY, vuW * vuLevel, 12);

        tCtx.restore();
      }}

      function renderParticles(tCtx, cfg, w, h, elemTime) {{
        tCtx.fillStyle = cfg.color || '#60A5FA';
        const count = Math.min(cfg.count || 50, 100);
        for (let i = 0; i < count; i++) {{
          const seed = i * 137.5;
          const speed = cfg.speed_range[0] + (seed % (cfg.speed_range[1] - cfg.speed_range[0]));
          const px = (seed * 97) % w;
          const py = (h - ((elemTime * speed + seed * 13) % h));
          const size = cfg.size_range[0] + (seed % (cfg.size_range[1] - cfg.size_range[0]));
          tCtx.beginPath();
          tCtx.arc(px, py, size, 0, Math.PI * 2);
          tCtx.fill();
        }}
      }}

      function renderShader(tCtx, cfg, w, h) {{
        if (cfg.effect_type === 'vignette') {{
          const grad = tCtx.createRadialGradient(w / 2, h / 2, w * 0.3, w / 2, h / 2, w * 0.7);
          grad.addColorStop(0, 'rgba(0,0,0,0)');
          grad.addColorStop(1, `rgba(0,0,0,${{cfg.intensity || 0.5}})`);
          tCtx.fillStyle = grad;
          tCtx.fillRect(0, 0, w, h);
        }}
      }}

      function renderCaptions(tCtx, cfg, w, h, elemTime) {{
        const words = cfg.words || [];
        if (words.length === 0) return;

        // Background veil
        if (cfg.background_veil) {{
          tCtx.fillStyle = cfg.veil_color || 'rgba(15, 23, 42, 0.75)';
          tCtx.beginPath();
          tCtx.roundRect(0, 0, w, h, 16);
          tCtx.fill();
        }}

        const typo = cfg.typography || {{}};
        tCtx.font = `${{typo.font_weight || 800}} ${{typo.font_size || 38}}px ${{typo.font_family || 'sans-serif'}}`;
        tCtx.textAlign = 'center';
        tCtx.textBaseline = 'middle';

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
          const wordWidth = tCtx.measureText(word).width;
          line.push({{ idx: i, word, width: wordWidth, isCurrent: i === activeIdx }});
          totalLineWidth += wordWidth + spacing;
        }}

        let startX = (w - totalLineWidth + spacing) / 2;
        const cy = h / 2;

        for (const item of line) {{
          if (item.isCurrent) {{
            tCtx.fillStyle = cfg.active_color || '#FBBF24';
            tCtx.save();
            tCtx.translate(startX + item.width / 2, cy);
            tCtx.scale(1.15, 1.15);
            tCtx.shadowColor = cfg.active_color || '#FBBF24';
            tCtx.shadowBlur = 12;
            tCtx.fillText(item.word, 0, 0);
            tCtx.restore();
          }} else {{
            tCtx.fillStyle = cfg.inactive_color || '#94A3B8';
            tCtx.fillText(item.word, startX + item.width / 2, cy);
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
                                "name": scene.name or f"Scene {idx+1}",
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
                                "name": audio.audio_type.replace("_", " ").title(),
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
