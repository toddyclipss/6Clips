/* SPDX-License-Identifier: AGPL-3.0-only
 * Offline Deterministic GSAP Compatibility Layer for ViralMint Wave 18.
 * Zero external CDN dependencies; zero telemetry; fully sandboxed.
 */
(function (global) {
  "use strict";

  function parseEasing(spec) {
    if (!spec || spec === "none" || spec === "linear") {
      return function (p) { return p; };
    }
    if (typeof spec === "function") return spec;

    var powerMatch = /^(?:power([1-4])|quad|cubic|quart|quint)\.(in|out|inOut)$/i.exec(spec);
    if (powerMatch) {
      var n = 2;
      var name = spec.split(".")[0].toLowerCase();
      if (name === "power1" || name === "quad") n = 2;
      else if (name === "power2" || name === "cubic") n = 3;
      else if (name === "power3" || name === "quart") n = 4;
      else if (name === "power4" || name === "quint") n = 5;
      var mode = powerMatch[1] || powerMatch[2];
      mode = spec.split(".")[1];
      return function (p) {
        if (mode === "in") return Math.pow(p, n);
        if (mode === "out") return 1 - Math.pow(1 - p, n);
        return p < 0.5 ? Math.pow(2 * p, n) / 2 : 1 - Math.pow(2 * (1 - p), n) / 2;
      };
    }
    var sineMatch = /^sine\.(in|out|inOut)$/i.exec(spec);
    if (sineMatch) {
      var smode = sineMatch[1];
      return function (p) {
        if (smode === "in") return 1 - Math.cos((p * Math.PI) / 2);
        if (smode === "out") return Math.sin((p * Math.PI) / 2);
        return -(Math.cos(Math.PI * p) - 1) / 2;
      };
    }
    var expoMatch = /^expo\.(in|out|inOut)$/i.exec(spec);
    if (expoMatch) {
      var emode = expoMatch[1];
      return function (p) {
        if (p <= 0) return 0;
        if (p >= 1) return 1;
        if (emode === "in") return Math.pow(2, 10 * (p - 1));
        if (emode === "out") return 1 - Math.pow(2, -10 * p);
        return p < 0.5
          ? Math.pow(2, 10 * (2 * p - 1)) / 2
          : (2 - Math.pow(2, -10 * (2 * p - 1))) / 2;
      };
    }
    var circMatch = /^circ\.(in|out|inOut)$/i.exec(spec);
    if (circMatch) {
      var cmode = circMatch[1];
      return function (p) {
        if (cmode === "in") return 1 - Math.sqrt(1 - p * p);
        if (cmode === "out") return Math.sqrt(1 - Math.pow(p - 1, 2));
        return p < 0.5
          ? (1 - Math.sqrt(1 - 4 * p * p)) / 2
          : (Math.sqrt(1 - Math.pow(-2 * p + 2, 2)) + 1) / 2;
      };
    }
    var backMatch = /^back\.(in|out|inOut)(?:\(([^)]+)\))?$/i.exec(spec);
    if (backMatch) {
      var bmode = backMatch[1];
      var s = backMatch[2] ? Number(backMatch[2]) : 1.70158;
      return function (p) {
        if (bmode === "in") return p * p * ((s + 1) * p - s);
        if (bmode === "out") {
          var q = p - 1;
          return 1 + q * q * ((s + 1) * q + s);
        }
        var sp = s * 1.525;
        return (p *= 2) < 1
          ? 0.5 * (p * p * ((sp + 1) * p - sp))
          : 0.5 * ((p -= 2) * p * ((sp + 1) * p + sp) + 2);
      };
    }
    var elasticMatch = /^elastic\.(in|out|inOut)(?:\(([^)]+)\))?$/i.exec(spec);
    if (elasticMatch) {
      var emode = elasticMatch[1];
      return function (p) {
        if (p <= 0) return 0;
        if (p >= 1) return 1;
        var pPeriod = 0.3;
        var s = pPeriod / 4;
        if (emode === "out") {
          return Math.pow(2, -10 * p) * Math.sin(((p - s) * (2 * Math.PI)) / pPeriod) + 1;
        }
        if (emode === "in") {
          return -(Math.pow(2, 10 * (p - 1)) * Math.sin(((p - 1 - s) * (2 * Math.PI)) / pPeriod));
        }
        return p < 0.5
          ? 0.5 * (-(Math.pow(2, 10 * (2 * p - 1)) * Math.sin(((2 * p - 1 - s) * (2 * Math.PI)) / pPeriod)))
          : 0.5 * (Math.pow(2, -10 * (2 * p - 1)) * Math.sin(((2 * p - 1 - s) * (2 * Math.PI)) / pPeriod)) + 1;
      };
    }
    return function (p) { return p; };
  }

  function resolveTargets(target) {
    if (!target) return [];
    if (Array.isArray(target)) {
      var out = [];
      for (var a = 0; a < target.length; a++) {
        var sub = resolveTargets(target[a]);
        for (var b = 0; b < sub.length; b++) out.push(sub[b]);
      }
      return out;
    }
    if (typeof target === "string") {
      try {
        var nodeList = document.querySelectorAll(target);
        var arr = [];
        for (var i = 0; i < nodeList.length; i++) arr.push(nodeList[i]);
        return arr;
      } catch (e) {
        return [];
      }
    }
    if (target.nodeType || typeof target === "object") {
      return [target];
    }
    return [];
  }

  function parseColor(val) {
    if (typeof val !== "string") return null;
    val = val.trim();
    if (val.startsWith("#")) {
      var hex = val.slice(1);
      if (hex.length === 3) {
        return [
          parseInt(hex[0] + hex[0], 16),
          parseInt(hex[1] + hex[1], 16),
          parseInt(hex[2] + hex[2], 16),
          1,
        ];
      }
      if (hex.length === 6) {
        return [
          parseInt(hex.slice(0, 2), 16),
          parseInt(hex.slice(2, 4), 16),
          parseInt(hex.slice(4, 6), 16),
          1,
        ];
      }
    }
    var rgbMatch = /^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/.exec(val);
    if (rgbMatch) {
      return [
        Number(rgbMatch[1]),
        Number(rgbMatch[2]),
        Number(rgbMatch[3]),
        rgbMatch[4] !== undefined ? Number(rgbMatch[4]) : 1,
      ];
    }
    return null;
  }

  function interpolate(startVal, endVal, p) {
    if (typeof startVal === "number" && typeof endVal === "number") {
      return startVal + (endVal - startVal) * p;
    }
    if (typeof endVal === "number" && typeof startVal === "string") {
      var parsedStart = parseFloat(startVal);
      if (!isNaN(parsedStart)) {
        return parsedStart + (endVal - parsedStart) * p;
      }
    }
    var c1 = parseColor(startVal);
    var c2 = parseColor(endVal);
    if (c1 && c2) {
      var r = Math.round(c1[0] + (c2[0] - c1[0]) * p);
      var g = Math.round(c1[1] + (c2[1] - c1[1]) * p);
      var b = Math.round(c1[2] + (c2[2] - c1[2]) * p);
      var a = c1[3] + (c2[3] - c1[3]) * p;
      return "rgba(" + r + ", " + g + ", " + b + ", " + a.toFixed(3) + ")";
    }
    if (typeof endVal === "string" && endVal.indexOf("inset(") === 0) {
      var sv = String(startVal).match(/-?\d+(?:\.\d+)?/g);
      var ev = endVal.match(/-?\d+(?:\.\d+)?/g);
      if (sv && ev && sv.length === 4 && ev.length === 4) {
        return (
          "inset(" +
          ev
            .map(function (v, i) {
              var snum = Number(sv[i]);
              var enum_ = Number(v);
              return snum + (enum_ - snum) * p + "%";
            })
            .join(" ") +
          ")"
        );
      }
    }
    if (typeof endVal === "string" && endVal.indexOf("blur(") !== -1) {
      var sblurMatch = String(startVal).match(/blur\((\d+(?:\.\d+)?)(px|rem|em)?\)/);
      var eblurMatch = endVal.match(/blur\((\d+(?:\.\d+)?)(px|rem|em)?\)/);
      var sval = sblurMatch ? Number(sblurMatch[1]) : 0;
      var eval_ = eblurMatch ? Number(eblurMatch[1]) : 0;
      var unit = (eblurMatch && eblurMatch[2]) || "px";
      var currentBlur = sval + (eval_ - sval) * p;
      return "blur(" + currentBlur.toFixed(2) + unit + ")";
    }
    if (typeof endVal === "string" && endVal.endsWith("%")) {
      var sPct = typeof startVal === "string" && startVal.endsWith("%") ? parseFloat(startVal) : (typeof startVal === "number" ? startVal : 0);
      var ePct = parseFloat(endVal);
      return (sPct + (ePct - sPct) * p) + "%";
    }
    return p >= 1 ? endVal : startVal;
  }

  function applyProps(target, props) {
    if (!target) return;
    target._gsapProps = target._gsapProps || {};
    for (var propKey in props) {
      target._gsapProps[propKey] = props[propKey];
    }

    if (!target.nodeType && typeof target === "object") {
      for (var k in props) {
        if (Object.prototype.hasOwnProperty.call(props, k)) {
          target[k] = props[k];
        }
      }
      return;
    }

    var style = target.style;
    if (!style) return;

    var transformParts = [];
    var x = target._gsapProps.x !== undefined ? target._gsapProps.x : null;
    var y = target._gsapProps.y !== undefined ? target._gsapProps.y : null;
    var xPercent = target._gsapProps.xPercent !== undefined ? target._gsapProps.xPercent : null;
    var yPercent = target._gsapProps.yPercent !== undefined ? target._gsapProps.yPercent : null;

    if (xPercent !== null || yPercent !== null) {
      transformParts.push(
        "translate(" + (xPercent || 0) + "%, " + (yPercent || 0) + "%)"
      );
    }
    if (x !== null || y !== null) {
      transformParts.push(
        "translate(" + (x || 0) + "px, " + (y || 0) + "px)"
      );
    }
    if (target._gsapProps.scale !== undefined) {
      transformParts.push("scale(" + target._gsapProps.scale + ")");
    }
    if (target._gsapProps.scaleX !== undefined) {
      transformParts.push("scaleX(" + target._gsapProps.scaleX + ")");
    }
    if (target._gsapProps.scaleY !== undefined) {
      transformParts.push("scaleY(" + target._gsapProps.scaleY + ")");
    }
    if (target._gsapProps.rotation !== undefined) {
      transformParts.push("rotate(" + target._gsapProps.rotation + "deg)");
    }
    if (target._gsapProps.rotationX !== undefined) {
      transformParts.push("rotateX(" + target._gsapProps.rotationX + "deg)");
    }
    if (target._gsapProps.rotationY !== undefined) {
      transformParts.push("rotateY(" + target._gsapProps.rotationY + "deg)");
    }
    if (target._gsapProps.skewX !== undefined) {
      transformParts.push("skewX(" + target._gsapProps.skewX + "deg)");
    }
    if (target._gsapProps.skewY !== undefined) {
      transformParts.push("skewY(" + target._gsapProps.skewY + "deg)");
    }

    if (transformParts.length > 0) {
      style.transform = transformParts.join(" ");
    }

    if (props.autoAlpha !== undefined) {
      style.opacity = String(props.autoAlpha);
      style.visibility = Number(props.autoAlpha) > 0 ? "visible" : "hidden";
    }
    if (props.opacity !== undefined) style.opacity = String(props.opacity);
    if (props.visibility !== undefined) style.visibility = props.visibility;
    if (props.clipPath !== undefined) style.clipPath = props.clipPath;
    if (props.boxShadow !== undefined) style.boxShadow = props.boxShadow;
    if (props.backgroundColor !== undefined) style.backgroundColor = props.backgroundColor;
    if (props.color !== undefined) style.color = props.color;
    if (props.filter !== undefined) style.filter = props.filter;
    if (props.zIndex !== undefined) style.zIndex = String(props.zIndex);
    if (props.textContent !== undefined) target.textContent = String(props.textContent);

    // SVG Attributes and Styles
    if (props.strokeDashoffset !== undefined || props["stroke-dashoffset"] !== undefined) {
      var sdo = props.strokeDashoffset !== undefined ? props.strokeDashoffset : props["stroke-dashoffset"];
      style.strokeDashoffset = String(sdo);
      if (typeof target.setAttribute === "function") {
        target.setAttribute("stroke-dashoffset", String(sdo));
      }
    }
    if (props.strokeDasharray !== undefined || props["stroke-dasharray"] !== undefined) {
      var sda = props.strokeDasharray !== undefined ? props.strokeDasharray : props["stroke-dasharray"];
      style.strokeDasharray = String(sda);
      if (typeof target.setAttribute === "function") {
        target.setAttribute("stroke-dasharray", String(sda));
      }
    }
    if (props.strokeWidth !== undefined || props["stroke-width"] !== undefined) {
      var sw = props.strokeWidth !== undefined ? props.strokeWidth : props["stroke-width"];
      style.strokeWidth = String(sw);
      if (typeof target.setAttribute === "function") {
        target.setAttribute("stroke-width", String(sw));
      }
    }
    if (props.stroke !== undefined) {
      style.stroke = props.stroke;
      if (typeof target.setAttribute === "function") target.setAttribute("stroke", props.stroke);
    }
    if (props.fill !== undefined) {
      style.fill = props.fill;
      if (typeof target.setAttribute === "function") target.setAttribute("fill", props.fill);
    }
    if (props.offsetDistance !== undefined || props["offset-distance"] !== undefined) {
      var od = props.offsetDistance !== undefined ? props.offsetDistance : props["offset-distance"];
      style.offsetDistance = String(od);
      if (style.webkitOffsetDistance !== undefined) style.webkitOffsetDistance = String(od);
    }
  }

  function extractInitialState(target, propKeys) {
    var state = {};
    if (!target) return state;
    target._gsapProps = target._gsapProps || {};

    if (!target.nodeType && typeof target === "object") {
      for (var i = 0; i < propKeys.length; i++) {
        var key = propKeys[i];
        state[key] = target[key] !== undefined ? target[key] : (target._gsapProps[key] !== undefined ? target._gsapProps[key] : 0);
      }
      return state;
    }

    var cs = window.getComputedStyle ? window.getComputedStyle(target) : {};
    for (var j = 0; j < propKeys.length; j++) {
      var k = propKeys[j];
      if (target._gsapProps[k] !== undefined) {
        state[k] = target._gsapProps[k];
      } else if (k === "opacity" || k === "autoAlpha") {
        state[k] = cs.opacity !== undefined ? Number(cs.opacity) : 1;
      } else if (k === "x" || k === "y" || k === "xPercent" || k === "yPercent" || k === "rotation" || k === "rotationX" || k === "rotationY" || k === "skewX" || k === "skewY") {
        state[k] = 0;
      } else if (k === "scale" || k === "scaleX" || k === "scaleY") {
        state[k] = 1;
      } else if (k === "clipPath") {
        state[k] = cs.clipPath && cs.clipPath !== "none" ? cs.clipPath : "inset(0% 0% 0% 0%)";
      } else if (k === "filter") {
        state[k] = cs.filter && cs.filter !== "none" ? cs.filter : "none";
      } else if (k === "strokeDashoffset" || k === "stroke-dashoffset") {
        var attrVal = typeof target.getAttribute === "function" ? target.getAttribute("stroke-dashoffset") : null;
        state[k] = attrVal !== null ? parseFloat(attrVal) : (cs.strokeDashoffset ? parseFloat(cs.strokeDashoffset) : 0);
      } else {
        state[k] = cs[k] || 0;
      }
    }
    return state;
  }

  function Timeline(opts) {
    opts = opts || {};
    this._paused = !!opts.paused;
    this._repeat = opts.repeat || 0;
    this._defaults = opts.defaults || {};
    this._currentTime = 0;
    this._duration = 0;
    this._tweens = [];
    this._calls = [];
    this.onUpdate = opts.onUpdate || null;
  }

  Timeline.prototype.addTween = function (target, fromVars, toVars, startTime, dur, easeFunc, repeat, yoyo) {
    var targetList = resolveTargets(target);
    var allKeys = {};
    var propKeys = [];
    var excluded = {
      duration: true,
      ease: true,
      repeat: true,
      yoyo: true,
      onUpdate: true,
      stagger: true,
      overwrite: true,
    };

    if (fromVars) {
      for (var fk in fromVars) {
        if (!excluded[fk]) allKeys[fk] = true;
      }
    }
    if (toVars) {
      for (var tk in toVars) {
        if (!excluded[tk]) allKeys[tk] = true;
      }
    }
    for (var k in allKeys) propKeys.push(k);

    for (var i = 0; i < targetList.length; i++) {
      var t = targetList[i];
      var isFirst = !this._tweens.some(function (existing) { return existing.target === t; });
      var baseFrom = fromVars ? Object.assign({}, fromVars) : extractInitialState(t, propKeys);
      var endTo = Object.assign({}, toVars);
      this._tweens.push({
        target: t,
        from: baseFrom,
        to: endTo,
        keys: propKeys,
        start: startTime,
        duration: dur,
        ease: easeFunc,
        repeat: repeat || 0,
        yoyo: !!yoyo,
        isFirst: isFirst,
        onUpdate: typeof toVars.onUpdate === "function" ? toVars.onUpdate : (fromVars && typeof fromVars.onUpdate === "function" ? fromVars.onUpdate : null),
      });
      var endTime = startTime + dur * ((repeat || 0) + 1);
      if (endTime > this._duration) this._duration = endTime;
    }
  };

  Timeline.prototype.to = function (target, vars, position) {
    vars = Object.assign({}, this._defaults, vars);
    var dur = Number(vars.duration !== undefined ? vars.duration : 1);
    var startTime = this._calcPosition(position);
    var easeFn = parseEasing(vars.ease);
    this.addTween(target, null, vars, startTime, dur, easeFn, vars.repeat, vars.yoyo);
    return this;
  };

  Timeline.prototype.fromTo = function (target, fromVars, toVars, position) {
    toVars = Object.assign({}, this._defaults, toVars);
    var dur = Number(toVars.duration !== undefined ? toVars.duration : 1);
    var startTime = this._calcPosition(position);
    var easeFn = parseEasing(toVars.ease);
    this.addTween(target, fromVars, toVars, startTime, dur, easeFn, toVars.repeat, toVars.yoyo);
    return this;
  };

  Timeline.prototype.set = function (target, vars, position) {
    vars = Object.assign({}, this._defaults, vars);
    var startTime = this._calcPosition(position);
    this.addTween(target, null, vars, startTime, 0, parseEasing("none"), 0, false);
    return this;
  };

  Timeline.prototype.clear = function () {
    this._tweens = [];
    this._calls = [];
    this._duration = 0;
    this._currentTime = 0;
    return this;
  };

  Timeline.prototype.from = function (target, fromVars, position) {
    fromVars = Object.assign({}, this._defaults, fromVars);
    var dur = Number(fromVars.duration !== undefined ? fromVars.duration : 1);
    var startTime = this._calcPosition(position);
    var easeFn = parseEasing(fromVars.ease);
    var targets = resolveTargets(target);
    var allKeys = {};
    for (var k in fromVars) {
      if (k !== "duration" && k !== "ease" && k !== "repeat" && k !== "yoyo" && k !== "onUpdate" && k !== "stagger" && k !== "overwrite") {
        allKeys[k] = true;
      }
    }
    var propKeys = Object.keys(allKeys);
    for (var i = 0; i < targets.length; i++) {
      var t = targets[i];
      var currentEnd = extractInitialState(t, propKeys);
      this.addTween(t, fromVars, currentEnd, startTime, dur, easeFn, fromVars.repeat, fromVars.yoyo);
    }
    return this;
  };

  Timeline.prototype.eventCallback = function (type, callback, params) {
    if (type === "onUpdate") {
      this.onUpdate = callback;
    }
    return this;
  };

  Timeline.prototype.call = function (fn, params, position) {
    var startTime = this._calcPosition(position);
    this._calls.push({ fn: fn, params: params || [], time: startTime });
    if (startTime > this._duration) this._duration = startTime;
    return this;
  };

  Timeline.prototype.repeat = function (val) {
    if (val === undefined) return this._repeat;
    this._repeat = val;
    return this;
  };

  Timeline.prototype._calcPosition = function (pos) {
    if (pos === undefined || pos === null) return this._duration;
    if (typeof pos === "number") return pos;
    if (typeof pos === "string") {
      if (pos.startsWith("+=")) return this._duration + Number(pos.slice(2));
      if (pos.startsWith("-=")) return Math.max(0, this._duration - Number(pos.slice(2)));
      var num = Number(pos);
      if (!isNaN(num)) return num;
    }
    return this._duration;
  };

  Timeline.prototype.seek = function (t) {
    if (!Number.isFinite(t)) return this;
    t = Math.max(0, Math.min(this._duration, t));
    this._currentTime = t;

    for (var i = 0; i < this._tweens.length; i++) {
      var tw = this._tweens[i];
      var currentProps = {};
      var p;

      if (t < tw.start) {
        if (tw.isFirst) {
          applyProps(tw.target, tw.from);
        }
        continue;
      } else if (tw.duration === 0 || t >= tw.start + tw.duration) {
        for (var e = 0; e < tw.keys.length; e++) {
          var ek = tw.keys[e];
          currentProps[ek] = tw.to[ek];
        }
      } else {
        var rawP = (t - tw.start) / tw.duration;
        p = tw.ease(Math.max(0, Math.min(1, rawP)));
        for (var k = 0; k < tw.keys.length; k++) {
          var pk = tw.keys[k];
          var sv = tw.from[pk];
          var ev = tw.to[pk];
          currentProps[pk] = interpolate(sv, ev, p);
        }
      }
      applyProps(tw.target, currentProps);
      if (tw.onUpdate) {
        try {
          tw.onUpdate();
        } catch (err) {}
      }
    }

    for (var c = 0; c < this._calls.length; c++) {
      var callItem = this._calls[c];
      if (t >= callItem.time && typeof callItem.fn === "function") {
        try {
          callItem.fn.apply(null, callItem.params);
        } catch (err) {}
      }
    }

    if (this.onUpdate) {
      this.onUpdate();
    }
    return this;
  };

  Timeline.prototype.totalTime = function (val) {
    if (val === undefined) return this._currentTime;
    return this.seek(val);
  };

  Timeline.prototype.time = function (val) {
    if (val === undefined) {
      return this._currentTime;
    }
    return this.seek(val);
  };

  Timeline.prototype.duration = function () {
    return this._duration;
  };

  Timeline.prototype.play = function (from) {
    if (from !== undefined) this.seek(from);
    this._paused = false;
    return this;
  };

  Timeline.prototype.pause = function (at) {
    if (at !== undefined) this.seek(at);
    this._paused = true;
    return this;
  };

  Timeline.prototype.restart = function () {
    this.seek(0);
    this._paused = false;
    return this;
  };

  var gsap = {
    timeline: function (opts) {
      return new Timeline(opts);
    },
    to: function (target, vars) {
      var tl = new Timeline();
      tl.to(target, vars, 0);
      tl.seek(0);
      return tl;
    },
    from: function (target, vars) {
      var tl = new Timeline();
      tl.from(target, vars, 0);
      tl.seek(0);
      return tl;
    },
    fromTo: function (target, fromVars, toVars) {
      var tl = new Timeline();
      tl.fromTo(target, fromVars, toVars, 0);
      tl.seek(0);
      return tl;
    },
    set: function (target, vars) {
      var tl = new Timeline();
      tl.set(target, vars, 0);
      tl.seek(0);
      return tl;
    },
    parseEase: parseEasing,
    utils: {
      toArray: resolveTargets,
      clamp: function (min, max, value) {
        return Math.max(min, Math.min(max, value));
      },
      interpolate: interpolate,
    },
  };

  global.gsap = gsap;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = gsap;
  }
})(typeof window !== "undefined" ? window : globalThis);
