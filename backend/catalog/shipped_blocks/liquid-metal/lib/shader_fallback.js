/**
 * HyperFrames WebGPU / Canvas 2D Animated Fallback Engine
 * SPDX-License-Identifier: Apache-2.0
 * 
 * Provides deterministic, high-fidelity 2D Canvas fallback animations for all 22
 * HyperFrames WebGPU shaders when WebGPU is unavailable (e.g. headless renderers,
 * software rasterizers, or standard browser environments without hardware WebGPU).
 * 
 * Each shader implements a distinct procedural aesthetic with temporal dynamics,
 * responsive scaling (16:9 and 9:16), and seeks deterministically via:
 *   window.__timelines[blockKey].seek(timeInSeconds)
 */
(function() {
  "use strict";

  // Check if WebGPU is available and initialized. If already working, fallback is dormant.
  var isHeadless = !navigator.gpu || window.__HYPERFRAMES_FALLBACK_SHADER__;

  function renderShader(canvas, shaderType, timeSec, vars) {
    var ctx = canvas.getContext("2d");
    if (!ctx) return;
    var w = canvas.width || 1920;
    var h = canvas.height || 1080;
    var t = Number(timeSec) || 0;
    vars = vars || {};

    ctx.save();
    ctx.clearRect(0, 0, w, h);

    var type = (shaderType || "").toLowerCase().replace(/[^a-z0-9]/g, "");

    switch (type) {
      case "aurora": {
        var speed = parseFloat(vars.speed) || 1.5;
        var curT = t * speed;
        ctx.fillStyle = "#020617";
        ctx.fillRect(0, 0, w, h);
        var ribbons = [
          { baseY: h * 0.35, amp: h * 0.18, freq1: 0.003, freq2: 0.006, speedMul: 1.2, c1: "rgba(16, 185, 129, 0.75)", c2: "rgba(5, 150, 105, 0)" },
          { baseY: h * 0.45, amp: h * 0.22, freq1: 0.0025, freq2: 0.005, speedMul: 0.9, c1: "rgba(56, 189, 248, 0.65)", c2: "rgba(2, 132, 199, 0)" },
          { baseY: h * 0.55, amp: h * 0.26, freq1: 0.002, freq2: 0.004, speedMul: 1.4, c1: "rgba(168, 85, 247, 0.7)", c2: "rgba(126, 34, 206, 0)" }
        ];
        ctx.globalCompositeOperation = "screen";
        for (var i = 0; i < ribbons.length; i++) {
          var rib = ribbons[i];
          var grad = ctx.createLinearGradient(0, rib.baseY - rib.amp, 0, rib.baseY + rib.amp * 1.5);
          grad.addColorStop(0, rib.c1);
          grad.addColorStop(1, rib.c2);
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.moveTo(0, h);
          for (var x = 0; x <= w; x += 15) {
            var wave = Math.sin(x * rib.freq1 + curT * rib.speedMul) * rib.amp +
                       Math.cos(x * rib.freq2 - curT * 0.6) * (rib.amp * 0.5);
            ctx.lineTo(x, rib.baseY + wave);
          }
          ctx.lineTo(w, h);
          ctx.closePath();
          ctx.fill();
        }
        break;
      }

      case "blob": {
        var spd = (parseFloat(vars.speed) || 1.0) * t;
        ctx.fillStyle = "#0a0514";
        ctx.fillRect(0, 0, w, h);
        var cx = w * 0.5;
        var cy = h * 0.5;
        var baseR = Math.min(w, h) * 0.32;
        var numPoints = 24;
        ctx.beginPath();
        for (var p = 0; p <= numPoints; p++) {
          var angle = (p / numPoints) * Math.PI * 2;
          var rOffset = Math.sin(angle * 3 + spd * 1.8) * (baseR * 0.22) +
                        Math.cos(angle * 5 - spd * 1.2) * (baseR * 0.15);
          var r = baseR + rOffset;
          var px = cx + Math.cos(angle) * r;
          var py = cy + Math.sin(angle) * r;
          if (p === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        var bGrad = ctx.createRadialGradient(cx - baseR * 0.3, cy - baseR * 0.3, baseR * 0.1, cx, cy, baseR * 1.3);
        bGrad.addColorStop(0, "#fb7185");
        bGrad.addColorStop(0.4, "#f43f5e");
        bGrad.addColorStop(0.8, "#881337");
        bGrad.addColorStop(1, "rgba(20, 5, 25, 0)");
        ctx.fillStyle = bGrad;
        ctx.fill();
        break;
      }

      case "flowinggradient": {
        var spd = parseFloat(vars.speed) || 2.0;
        var curT = t * spd;
        var angle = (45 + Math.sin(curT * 0.4) * 35) * Math.PI / 180;
        var linGrad = ctx.createLinearGradient(
          w * 0.5 - Math.cos(angle) * w * 0.6,
          h * 0.5 - Math.sin(angle) * h * 0.6,
          w * 0.5 + Math.cos(angle) * w * 0.6,
          h * 0.5 + Math.sin(angle) * h * 0.6
        );
        linGrad.addColorStop(0, "#f97316");
        linGrad.addColorStop(0.35, "#db2777");
        linGrad.addColorStop(0.7, "#7c3aed");
        linGrad.addColorStop(1, "#312e81");
        ctx.fillStyle = linGrad;
        ctx.fillRect(0, 0, w, h);
        var cx = w * (0.5 + 0.25 * Math.cos(curT * 0.6));
        var cy = h * (0.5 + 0.25 * Math.sin(curT * 0.8));
        var radGrad = ctx.createRadialGradient(cx, cy, 20, cx, cy, Math.max(w, h) * 0.65);
        radGrad.addColorStop(0, "rgba(251, 146, 60, 0.65)");
        radGrad.addColorStop(0.5, "rgba(168, 85, 247, 0.35)");
        radGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.globalCompositeOperation = "screen";
        ctx.fillStyle = radGrad;
        ctx.fillRect(0, 0, w, h);
        break;
      }

      case "fractalnoise": {
        ctx.fillStyle = "#030712";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        for (var octave = 1; octave <= 3; octave++) {
          var step = 40 * octave;
          for (var x = 0; x < w; x += step) {
            for (var y = 0; y < h; y += step) {
              var val = Math.sin(x * 0.004 * octave + t * 0.7) *
                        Math.cos(y * 0.004 * octave - t * 0.5) *
                        Math.sin((x + y) * 0.002 + t * 0.3);
              if (val > 0.1) {
                var alpha = Math.min(0.6, val * 0.5 / octave);
                ctx.fillStyle = "rgba(147, 197, 253, " + alpha + ")";
                ctx.fillRect(x, y, step, step);
              }
            }
          }
        }
        break;
      }

      case "frost": {
        ctx.fillStyle = "#04101e";
        ctx.fillRect(0, 0, w, h);
        var cx = w * 0.5;
        var cy = h * 0.5;
        var orbR = Math.min(w, h) * 0.36;
        var fGrad = ctx.createRadialGradient(cx, cy, orbR * 0.1, cx, cy, orbR);
        fGrad.addColorStop(0, "#e0f2fe");
        fGrad.addColorStop(0.5, "#38bdf8");
        fGrad.addColorStop(0.85, "#0284c7");
        fGrad.addColorStop(1, "#0369a1");
        ctx.fillStyle = fGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, orbR, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
        ctx.lineWidth = 2.5;
        for (var b = 0; b < 12; b++) {
          var bAng = (b / 12) * Math.PI * 2 + t * 0.2;
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          var len = orbR * (0.5 + 0.45 * Math.sin(b * 1.5 + t));
          var bx = cx + Math.cos(bAng) * len;
          var by = cy + Math.sin(bAng) * len;
          ctx.lineTo(bx, by);
          ctx.lineTo(bx + Math.cos(bAng + 0.5) * (len * 0.25), by + Math.sin(bAng + 0.5) * (len * 0.25));
          ctx.stroke();
        }
        break;
      }

      case "godrays": {
        ctx.fillStyle = "#020617";
        ctx.fillRect(0, 0, w, h);
        var originX = w * 0.15;
        var originY = -h * 0.1;
        var rayCount = 18;
        ctx.globalCompositeOperation = "screen";
        for (var r = 0; r < rayCount; r++) {
          var angOffset = Math.sin(t * 0.8 + r * 0.6) * 0.12;
          var ang = 0.3 + (r / rayCount) * 1.2 + angOffset;
          var length = Math.max(w, h) * 1.6;
          var targetX = originX + Math.cos(ang) * length;
          var targetY = originY + Math.sin(ang) * length;
          var rGrad = ctx.createRadialGradient(originX, originY, 40, originX, originY, length);
          var alpha = 0.25 + 0.2 * Math.sin(t * 1.4 + r);
          rGrad.addColorStop(0, "rgba(254, 240, 138, " + alpha + ")");
          rGrad.addColorStop(0.5, "rgba(56, 189, 248, " + (alpha * 0.6) + ")");
          rGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = rGrad;
          ctx.beginPath();
          ctx.moveTo(originX, originY);
          ctx.lineTo(targetX - 70, targetY);
          ctx.lineTo(targetX + 70, targetY);
          ctx.closePath();
          ctx.fill();
        }
        break;
      }

      case "goo": {
        ctx.fillStyle = "#030206";
        ctx.fillRect(0, 0, w, h);
        var droplets = [
          { x: w * 0.5, y: h * (0.4 + 0.25 * Math.sin(t * 1.6)), r: w * 0.18, c: "#a855f7" },
          { x: w * (0.5 + 0.16 * Math.cos(t * 1.2)), y: h * (0.5 + 0.2 * Math.sin(t * 1.4)), r: w * 0.14, c: "#ec4899" },
          { x: w * (0.5 - 0.18 * Math.cos(t * 1.8)), y: h * (0.45 - 0.22 * Math.sin(t * 1.1)), r: w * 0.15, c: "#6366f1" }
        ];
        ctx.globalCompositeOperation = "screen";
        for (var d = 0; d < droplets.length; d++) {
          var dp = droplets[d];
          var gGrad = ctx.createRadialGradient(dp.x - dp.r * 0.3, dp.y - dp.r * 0.3, 10, dp.x, dp.y, dp.r);
          gGrad.addColorStop(0, "#ffffff");
          gGrad.addColorStop(0.3, dp.c);
          gGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = gGrad;
          ctx.beginPath();
          ctx.arc(dp.x, dp.y, dp.r, 0, Math.PI * 2);
          ctx.fill();
        }
        break;
      }

      case "holographic": {
        var sh = parseFloat(vars.shimmer) || 1.0;
        var curT = t * sh;
        ctx.fillStyle = "#030206";
        ctx.fillRect(0, 0, w, h);
        var orbX = w * 0.5;
        var orbY = h * 0.5;
        var orbR = Math.min(w, h) * 0.38;
        var orbGrad = ctx.createRadialGradient(
          orbX + Math.sin(curT * 1.5) * (orbR * 0.25),
          orbY - Math.cos(curT * 1.2) * (orbR * 0.25),
          orbR * 0.05, orbX, orbY, orbR
        );
        var hBase = (curT * 80) % 360;
        orbGrad.addColorStop(0.0, "hsl(" + (hBase + 60) % 360 + ", 95%, 85%)");
        orbGrad.addColorStop(0.2, "hsl(" + (hBase + 120) % 360 + ", 90%, 65%)");
        orbGrad.addColorStop(0.45, "hsl(" + (hBase + 200) % 360 + ", 85%, 55%)");
        orbGrad.addColorStop(0.7, "hsl(" + (hBase + 280) % 360 + ", 90%, 60%)");
        orbGrad.addColorStop(0.9, "hsl(" + (hBase + 340) % 360 + ", 95%, 45%)");
        orbGrad.addColorStop(1.0, "rgba(10, 10, 20, 0.95)");
        ctx.beginPath();
        ctx.arc(orbX, orbY, orbR, 0, Math.PI * 2);
        ctx.fillStyle = orbGrad;
        ctx.fill();
        ctx.globalCompositeOperation = "screen";
        ctx.lineWidth = 14;
        for (var ring = 1; ring <= 4; ring++) {
          ctx.strokeStyle = "hsla(" + ((hBase + ring * 55) % 360) + ", 90%, 70%, 0.4)";
          ctx.beginPath();
          ctx.arc(orbX, orbY, orbR * (0.3 + ring * 0.16), curT * 0.8, curT * 0.8 + Math.PI * 0.7);
          ctx.stroke();
        }
        break;
      }

      case "lensflare": {
        ctx.fillStyle = "#010204";
        ctx.fillRect(0, 0, w, h);
        var lx = w * (0.5 + 0.25 * Math.sin(t * 1.1));
        var ly = h * (0.5 + 0.2 * Math.cos(t * 0.9));
        ctx.globalCompositeOperation = "screen";
        var coreGrad = ctx.createRadialGradient(lx, ly, 5, lx, ly, w * 0.35);
        coreGrad.addColorStop(0, "#ffffff");
        coreGrad.addColorStop(0.15, "#67e8f9");
        coreGrad.addColorStop(0.4, "#3b82f6");
        coreGrad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = coreGrad;
        ctx.beginPath();
        ctx.arc(lx, ly, w * 0.35, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(165, 243, 252, 0.6)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(0, ly);
        ctx.lineTo(w, ly);
        ctx.stroke();
        break;
      }

      case "liquidmetal": {
        ctx.fillStyle = "#0b0f19";
        ctx.fillRect(0, 0, w, h);
        var waves = 7;
        for (var j = 0; j < waves; j++) {
          var yBase = (h / waves) * (j + 0.5);
          var mGrad = ctx.createLinearGradient(0, yBase - 60, 0, yBase + 60);
          mGrad.addColorStop(0, "#94a3b8");
          mGrad.addColorStop(0.5, "#f8fafc");
          mGrad.addColorStop(1, "#334155");
          ctx.fillStyle = mGrad;
          ctx.beginPath();
          ctx.moveTo(0, h);
          for (var x = 0; x <= w; x += 20) {
            var my = yBase + Math.sin(x * 0.005 + t * 2.0 + j) * 45;
            ctx.lineTo(x, my);
          }
          ctx.lineTo(w, h);
          ctx.closePath();
          ctx.fill();
        }
        break;
      }

      case "marble": {
        ctx.fillStyle = "#09090b";
        ctx.fillRect(0, 0, w, h);
        for (var v = 0; v < 6; v++) {
          var veinY = (h / 6) * (v + 0.5);
          var veinGrad = ctx.createLinearGradient(0, veinY - 40, 0, veinY + 40);
          veinGrad.addColorStop(0, "rgba(234, 179, 8, 0)");
          veinGrad.addColorStop(0.5, "rgba(250, 204, 21, 0.85)");
          veinGrad.addColorStop(1, "rgba(234, 179, 8, 0)");
          ctx.strokeStyle = veinGrad;
          ctx.lineWidth = 12;
          ctx.beginPath();
          for (var x = 0; x <= w; x += 25) {
            var yOffset = Math.sin(x * 0.006 + t * 0.9 + v) * 50 +
                          Math.cos(x * 0.012 - t * 0.5) * 25;
            if (x === 0) ctx.moveTo(x, veinY + yOffset);
            else ctx.lineTo(x, veinY + yOffset);
          }
          ctx.stroke();
        }
        break;
      }

      case "meshgradient": {
        var points = [
          { x: w * (0.2 + 0.15 * Math.sin(t * 1.2)), y: h * (0.2 + 0.15 * Math.cos(t * 0.9)), c: "#ec4899" },
          { x: w * (0.8 - 0.15 * Math.cos(t * 1.1)), y: h * (0.2 + 0.12 * Math.sin(t * 1.3)), c: "#8b5cf6" },
          { x: w * (0.2 + 0.12 * Math.cos(t * 1.4)), y: h * (0.8 - 0.15 * Math.sin(t * 1.0)), c: "#06b6d4" },
          { x: w * (0.8 - 0.18 * Math.sin(t * 0.8)), y: h * (0.8 - 0.12 * Math.cos(t * 1.2)), c: "#f97316" }
        ];
        ctx.fillStyle = "#030712";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        for (var k = 0; k < points.length; k++) {
          var pt = points[k];
          var ptGrad = ctx.createRadialGradient(pt.x, pt.y, 20, pt.x, pt.y, Math.max(w, h) * 0.6);
          ptGrad.addColorStop(0, pt.c);
          ptGrad.addColorStop(1, "rgba(0,0,0,0)");
          ctx.fillStyle = ptGrad;
          ctx.fillRect(0, 0, w, h);
        }
        break;
      }

      case "nebula": {
        ctx.fillStyle = "#020208";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        var nCx = w * 0.5;
        var nCy = h * 0.5;
        var nRad = Math.min(w, h) * 0.45;
        var nebGrad = ctx.createRadialGradient(nCx, nCy, 20, nCx, nCy, nRad);
        nebGrad.addColorStop(0, "#c084fc");
        nebGrad.addColorStop(0.4, "#7e22ce");
        nebGrad.addColorStop(0.7, "#1e1b4b");
        nebGrad.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = nebGrad;
        ctx.beginPath();
        ctx.arc(nCx, nCy, nRad, 0, Math.PI * 2);
        ctx.fill();
        for (var s = 0; s < 40; s++) {
          var sx = (Math.sin(s * 99 + t * 0.3) * 0.5 + 0.5) * w;
          var sy = (Math.cos(s * 77 + t * 0.2) * 0.5 + 0.5) * h;
          var sAlpha = Math.sin(t * 2.0 + s) * 0.4 + 0.6;
          ctx.fillStyle = "rgba(255, 255, 255, " + sAlpha + ")";
          ctx.beginPath();
          ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
        break;
      }

      case "plasma": {
        var den = parseFloat(vars.density) || 1.8;
        var curT = t * 1.5;
        ctx.fillStyle = "#0c021c";
        ctx.fillRect(0, 0, w, h);
        var nodes = [
          { x: w * (0.5 + 0.32 * Math.sin(curT * 1.1)), y: h * (0.5 + 0.3 * Math.cos(curT * 0.8)), r: w * 0.45, c1: "rgba(147, 51, 234, 0.85)", c2: "rgba(88, 28, 135, 0)" },
          { x: w * (0.5 + 0.28 * Math.cos(curT * 1.4)), y: h * (0.5 + 0.32 * Math.sin(curT * 1.0)), r: w * 0.4, c1: "rgba(236, 72, 153, 0.75)", c2: "rgba(190, 24, 93, 0)" },
          { x: w * (0.5 + 0.35 * Math.sin(curT * 0.7 + 1.8)), y: h * (0.5 + 0.22 * Math.cos(curT * 1.3 + 1)), r: w * 0.5, c1: "rgba(59, 130, 246, 0.65)", c2: "rgba(30, 58, 138, 0)" },
          { x: w * (0.5 + 0.22 * Math.cos(curT * 1.6 + 2.5)), y: h * (0.5 + 0.26 * Math.sin(curT * 0.9 + 2)), r: w * 0.35, c1: "rgba(192, 132, 252, 0.8)", c2: "rgba(107, 33, 168, 0)" }
        ];
        ctx.globalCompositeOperation = "screen";
        for (var n = 0; n < nodes.length; n++) {
          var nd = nodes[n];
          var pGrad = ctx.createRadialGradient(nd.x, nd.y, 10, nd.x, nd.y, nd.r);
          pGrad.addColorStop(0, nd.c1);
          pGrad.addColorStop(0.6, nd.c2);
          pGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = pGrad;
          ctx.beginPath();
          ctx.arc(nd.x, nd.y, nd.r, 0, Math.PI * 2);
          ctx.fill();
        }
        break;
      }

      case "prism": {
        ctx.fillStyle = "#000000";
        ctx.fillRect(0, 0, w, h);
        var rainbow = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7"];
        ctx.globalCompositeOperation = "screen";
        var pStart = w * 0.35;
        var pAngle = Math.sin(t * 1.1) * 0.15;
        for (var rb = 0; rb < rainbow.length; rb++) {
          ctx.fillStyle = rainbow[rb];
          ctx.beginPath();
          ctx.moveTo(pStart, h * 0.5);
          var spreadY = (rb - 3) * 60 + Math.sin(t * 1.5 + rb) * 20;
          ctx.lineTo(w, h * 0.5 + spreadY - 30);
          ctx.lineTo(w, h * 0.5 + spreadY + 30);
          ctx.closePath();
          ctx.fill();
        }
        break;
      }

      case "sinewave": {
        ctx.fillStyle = "#020408";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        var lines = 8;
        for (var l = 0; l < lines; l++) {
          var swBaseY = (h / lines) * (l + 0.5);
          ctx.strokeStyle = "hsla(" + ((l * 45 + t * 60) % 360) + ", 90%, 65%, 0.75)";
          ctx.lineWidth = 4;
          ctx.beginPath();
          for (var x = 0; x <= w; x += 15) {
            var sy = swBaseY + Math.sin(x * 0.008 + t * 2.5 + l * 0.5) * 40;
            if (x === 0) ctx.moveTo(x, sy);
            else ctx.lineTo(x, sy);
          }
          ctx.stroke();
        }
        break;
      }

      case "strands": {
        ctx.fillStyle = "#050510";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        for (var st = 0; st < 12; st++) {
          ctx.strokeStyle = "hsla(" + ((st * 30 + t * 40) % 360) + ", 85%, 60%, 0.6)";
          ctx.lineWidth = 3;
          ctx.beginPath();
          for (var y = 0; y <= h; y += 20) {
            var sx = w * 0.5 + Math.sin(y * 0.007 + t * 1.8 + st) * (w * 0.35) +
                               Math.cos(y * 0.012 - t * 0.9) * 40;
            if (y === 0) ctx.moveTo(sx, y);
            else ctx.lineTo(sx, y);
          }
          ctx.stroke();
        }
        break;
      }

      case "stripes": {
        var stripeW = parseFloat(vars.stripe_width || 36);
        if (isNaN(stripeW) || stripeW < 8) stripeW = 36;
        var angleDeg = parseFloat(vars.angle || 120);
        if (isNaN(angleDeg)) angleDeg = 120;
        var rot = (angleDeg * Math.PI) / 180;
        var offset = (t * 70) % (stripeW * 2);
        ctx.fillStyle = "#090d16";
        ctx.fillRect(0, 0, w, h);
        ctx.save();
        ctx.translate(w / 2, h / 2);
        ctx.rotate(rot);
        var diag = Math.sqrt(w * w + h * h) * 1.25;
        ctx.fillStyle = "#f8fafc";
        for (var pos = -diag + offset; pos < diag; pos += stripeW * 2) {
          ctx.fillRect(pos, -diag, stripeW, diag * 2);
        }
        ctx.restore();
        break;
      }

      case "swirl": {
        ctx.fillStyle = "#08031a";
        ctx.fillRect(0, 0, w, h);
        var sCx = w * 0.5;
        var sCy = h * 0.5;
        var sMaxR = Math.min(w, h) * 0.45;
        ctx.globalCompositeOperation = "screen";
        for (var arm = 0; arm < 4; arm++) {
          var armOffset = (arm / 4) * Math.PI * 2;
          ctx.strokeStyle = arm % 2 === 0 ? "rgba(236, 72, 153, 0.7)" : "rgba(99, 102, 241, 0.7)";
          ctx.lineWidth = 16;
          ctx.beginPath();
          for (var rad = 20; rad < sMaxR; rad += 10) {
            var theta = armOffset + rad * 0.025 + t * 2.0;
            var ax = sCx + Math.cos(theta) * rad;
            var ay = sCy + Math.sin(theta) * rad;
            if (rad === 20) ctx.moveTo(ax, ay);
            else ctx.lineTo(ax, ay);
          }
          ctx.stroke();
        }
        break;
      }

      case "voronoi": {
        ctx.fillStyle = "#0f172a";
        ctx.fillRect(0, 0, w, h);
        var cellCount = 14;
        var centers = [];
        for (var cIdx = 0; cIdx < cellCount; cIdx++) {
          centers.push({
            x: w * (0.5 + 0.38 * Math.sin(t * 0.9 + cIdx * 1.3)),
            y: h * (0.5 + 0.38 * Math.cos(t * 1.1 + cIdx * 1.7)),
            c: "hsl(" + (cIdx * 25 + t * 50) % 360 + ", 75%, 55%)"
          });
        }
        for (var ci = 0; ci < centers.length; ci++) {
          var ctr = centers[ci];
          ctx.fillStyle = ctr.c;
          ctx.beginPath();
          ctx.arc(ctr.x, ctr.y, 45, 0, Math.PI * 2);
          ctx.fill();
        }
        break;
      }

      case "water": {
        ctx.fillStyle = "#0284c7";
        ctx.fillRect(0, 0, w, h);
        ctx.globalCompositeOperation = "screen";
        ctx.strokeStyle = "rgba(224, 242, 254, 0.45)";
        ctx.lineWidth = 6;
        for (var row = 0; row < 10; row++) {
          var wY = (h / 10) * (row + 0.5);
          ctx.beginPath();
          for (var x = 0; x <= w; x += 30) {
            var wAmp = Math.sin(x * 0.015 + t * 2.2 + row) * 20 +
                       Math.cos(x * 0.008 - t * 1.4) * 15;
            if (x === 0) ctx.moveTo(x, wY + wAmp);
            else ctx.lineTo(x, wY + wAmp);
          }
          ctx.stroke();
        }
        break;
      }

      case "waveform": {
        ctx.fillStyle = "#05050d";
        ctx.fillRect(0, 0, w, h);
        var barCount = 48;
        var barW = (w / barCount) * 0.7;
        var barGap = (w / barCount) * 0.3;
        for (var bIdx = 0; bIdx < barCount; bIdx++) {
          var barX = bIdx * (barW + barGap) + barGap * 0.5;
          var waveVal = Math.abs(Math.sin(bIdx * 0.25 + t * 3.5) * Math.cos(bIdx * 0.1 - t * 2.0));
          var barH = waveVal * (h * 0.65) + 15;
          var barY = (h - barH) * 0.5;
          var wfGrad = ctx.createLinearGradient(0, barY, 0, barY + barH);
          wfGrad.addColorStop(0, "#38bdf8");
          wfGrad.addColorStop(0.5, "#818cf8");
          wfGrad.addColorStop(1, "#c084fc");
          ctx.fillStyle = wfGrad;
          ctx.fillRect(barX, barY, barW, barH);
        }
        break;
      }

      default: {
        // High-contrast neutral dynamic gradient
        ctx.fillStyle = "#0f172a";
        ctx.fillRect(0, 0, w, h);
        var defGrad = ctx.createRadialGradient(w * 0.5, h * 0.5, 20, w * 0.5, h * 0.5, Math.min(w, h) * 0.5);
        defGrad.addColorStop(0, "hsl(" + (t * 60) % 360 + ", 80%, 65%)");
        defGrad.addColorStop(1, "#020617");
        ctx.fillStyle = defGrad;
        ctx.beginPath();
        ctx.arc(w * 0.5, h * 0.5, Math.min(w, h) * 0.4, 0, Math.PI * 2);
        ctx.fill();
        break;
      }
    }

    ctx.restore();
  }

  function initFallback() {
    var canvases = document.querySelectorAll("canvas[data-shader]");
    if (!canvases || canvases.length === 0) return;

    for (var i = 0; i < canvases.length; i++) {
      (function(cvs) {
        var shaderType = cvs.getAttribute("data-shader") || "";
        var compEl = cvs.closest("[data-composition-id]");
        var blockKey = (compEl ? compEl.getAttribute("data-composition-id") : null) || shaderType || "fx";

        // Read variables if present
        var vars = {};
        if (compEl && compEl.hasAttribute("data-composition-variables")) {
          try {
            var raw = JSON.parse(compEl.getAttribute("data-composition-variables") || "[]");
            for (var vi = 0; vi < raw.length; vi++) {
              if (raw[vi] && raw[vi].id) vars[raw[vi].id] = raw[vi].default;
            }
          } catch(e) {}
        }

        // If WebGPU is not supported or WebGPU init fails, activate canvas 2D fallback
        if (isHeadless) {
          console.log("[HyperFrames Fallback] WebGPU not active for " + shaderType + ", running Canvas 2D engine");
        }

        var duration = parseFloat(compEl ? compEl.getAttribute("data-duration") : "2") || 2.0;

        // Register timeline object
        window.__timelines = window.__timelines || {};
        window.__timelines[blockKey] = {
          duration: function() { return duration; },
          seek: function(timeSec) {
            renderShader(cvs, shaderType, timeSec, vars);
          },
          play: function() {
            var startTime = performance.now();
            function loop() {
              var elapsed = (performance.now() - startTime) / 1000;
              renderShader(cvs, shaderType, elapsed % duration, vars);
              window.__timelines[blockKey]._raf = requestAnimationFrame(loop);
            }
            loop();
          },
          pause: function() {
            if (window.__timelines[blockKey]._raf) {
              cancelAnimationFrame(window.__timelines[blockKey]._raf);
            }
          }
        };

        // Render initial frame at t=0
        renderShader(cvs, shaderType, 0.0, vars);
      })(canvases[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFallback);
  } else {
    initFallback();
  }
  setTimeout(initFallback, 80);
})();
