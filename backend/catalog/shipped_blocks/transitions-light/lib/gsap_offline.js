/* SPDX-License-Identifier: AGPL-3.0-only
 * Offline Deterministic GSAP Compatibility Layer for ViralMint Wave 17.
 * Zero external CDN dependencies; zero telemetry; fully sandboxed.
 */
(function (global) {
  "use strict";

  function parseEasing(spec) {
    if (!spec || spec === "none" || spec === "linear") {
      return function (p) { return p; };
    }
    var powerMatch = /^power([1-4])\.(in|out|inOut)$/.exec(spec);
    if (powerMatch) {
      var n = Number(powerMatch[1]) + 1;
      var mode = powerMatch[2];
      return function (p) {
        if (mode === "in") return Math.pow(p, n);
        if (mode === "out") return 1 - Math.pow(1 - p, n);
        return p < 0.5 ? Math.pow(2 * p, n) / 2 : 1 - Math.pow(2 * (1 - p), n) / 2;
      };
    }
    var sineMatch = /^sine\.(in|out|inOut)$/.exec(spec);
    if (sineMatch) {
      var smode = sineMatch[1];
      return function (p) {
        if (smode === "in") return 1 - Math.cos((p * Math.PI) / 2);
        if (smode === "out") return Math.sin((p * Math.PI) / 2);
        return -(Math.cos(Math.PI * p) - 1) / 2;
      };
    }
    var backMatch = /^back\.(in|out|inOut)(?:\(([^)]+)\))?$/.exec(spec);
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
    return function (p) { return p; };
  }

  function resolveTargets(target) {
    if (!target) return [];
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
    if (Array.isArray(target)) {
      var res = [];
      target.forEach(function (t) {
        res = res.concat(resolveTargets(t));
      });
      return res;
    }
    if (target.nodeType || typeof target === "object") {
      return [target];
    }
    return [];
  }

  function interpolate(startVal, endVal, p) {
    if (typeof startVal === "number" && typeof endVal === "number") {
      return startVal + (endVal - startVal) * p;
    }
    if (typeof endVal === "string" && endVal.startsWith("inset(")) {
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
      } else {
        state[k] = cs[k] || 0;
      }
    }
    return state;
  }

  function Timeline(options) {
    options = options || {};
    this.paused = !!options.paused;
    this.onUpdate = typeof options.onUpdate === "function" ? options.onUpdate : null;
    this._tweens = [];
    this._calls = [];
    this._currentTime = 0;
    this._duration = 0;
    this._repeat = 0;
    this._rafId = null;
    this._startTime = 0;
  }

  Timeline.prototype.addTween = function (targets, fromVars, toVars, startTime, dur, easeFunc, repeat, yoyo) {
    var targetList = resolveTargets(targets);
    var propKeys = [];
    var k;
    for (k in toVars) {
      if (["duration", "ease", "repeat", "yoyo", "delay"].indexOf(k) === -1) {
        propKeys.push(k);
      }
    }
    for (k in fromVars) {
      if (propKeys.indexOf(k) === -1 && ["duration", "ease", "repeat", "yoyo", "delay"].indexOf(k) === -1) {
        propKeys.push(k);
      }
    }

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
    var dur = Number(vars.duration !== undefined ? vars.duration : 1);
    var startTime = this._calcPosition(position);
    var easeFn = parseEasing(vars.ease);
    this.addTween(target, null, vars, startTime, dur, easeFn, vars.repeat, vars.yoyo);
    return this;
  };

  Timeline.prototype.fromTo = function (target, fromVars, toVars, position) {
    var dur = Number(toVars.duration !== undefined ? toVars.duration : 1);
    var startTime = this._calcPosition(position);
    var easeFn = parseEasing(toVars.ease);
    this.addTween(target, fromVars, toVars, startTime, dur, easeFn, toVars.repeat, toVars.yoyo);
    return this;
  };

  Timeline.prototype.set = function (target, vars, position) {
    var startTime = this._calcPosition(position);
    this.addTween(target, null, vars, startTime, 0, parseEasing("none"), 0, false);
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

  Timeline.prototype.pause = function () {
    this.paused = true;
    if (this._rafId !== null) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    return this;
  };

  Timeline.prototype.play = function (fromTime) {
    this.paused = false;
    if (fromTime !== undefined) {
      this.seek(fromTime);
    }
    var self = this;
    this._startTime = performance.now() - this._currentTime * 1000;
    function tick(now) {
      if (self.paused) return;
      var elapsed = (now - self._startTime) / 1000;
      self.seek(elapsed);
      if (elapsed < self._duration) {
        self._rafId = requestAnimationFrame(tick);
      } else {
        self._rafId = null;
      }
    }
    this._rafId = requestAnimationFrame(tick);
    return this;
  };

  var gsap = {
    timeline: function (options) {
      return new Timeline(options);
    },
    set: function (target, props) {
      var list = resolveTargets(target);
      for (var i = 0; i < list.length; i++) {
        applyProps(list[i], props);
      }
    },
    to: function (target, props) {
      var tl = new Timeline();
      tl.to(target, props, 0);
      tl.play();
      return tl;
    },
    fromTo: function (target, fromProps, toProps) {
      var tl = new Timeline();
      tl.fromTo(target, fromProps, toProps, 0);
      tl.play();
      return tl;
    },
    parseEase: parseEasing,
  };

  global.gsap = gsap;
  global.__timelines = global.__timelines || {};
})(typeof window !== "undefined" ? window : this);
