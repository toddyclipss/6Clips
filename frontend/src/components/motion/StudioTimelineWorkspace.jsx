// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useRef, useState, useEffect, useMemo, useCallback } from "react"
import {
  Box, Stack, Typography, IconButton, Tooltip, Menu, MenuItem,
  ListItemIcon, ListItemText, Chip, Slider,
} from "@mui/material"
import {
  IconScissors,
  IconPlus,
  IconTrash,
  IconMagnet,
  IconPlayerPlay,
  IconPlayerPause,
  IconZoomIn,
  IconZoomOut,
  IconEye,
  IconEyeOff,
  IconLock,
  IconLockOpen,
  IconVolume,
  IconVolumeOff,
  IconChevronDown,
  IconChevronRight,
  IconCopy,
  IconDiamond,
  IconDiamonds,
  IconVideo,
  IconMusic,
  IconTypography,
  IconComponents,
  IconPhoto,
} from "@tabler/icons-react"

const HEADER_WIDTH = 190
const TRACK_NORMAL_HEIGHT = 50
const TRACK_COLLAPSED_HEIGHT = 28
const PROPERTY_LANE_HEIGHT = 26
const ANIMATABLE_PROPERTIES = [
  { key: "opacity", label: "Opacity", default: 1.0, min: 0, max: 1, step: 0.05 },
  { key: "scale", label: "Scale", default: 1.0, min: 0.1, max: 3, step: 0.05 },
  { key: "x", label: "Position X", default: 0, min: -1000, max: 1000, step: 10 },
  { key: "y", label: "Position Y", default: 0, min: -1000, max: 1000, step: 10 },
  { key: "rotation", label: "Rotation", default: 0, min: -360, max: 360, step: 5 },
]

/**
 * Waveform canvas rendering simulated/decoded audio amplitude bars
 */
function AudioWaveformCanvas({ clipId, width, height, isMuted }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, width, height)

    // Synthesize pseudo-random but deterministic waveform peaks from clipId
    let hash = 0
    for (let i = 0; i < clipId.length; i++) {
      hash = (hash << 5) - hash + clipId.charCodeAt(i)
      hash |= 0
    }

    const barWidth = 3
    const barGap = 1.5
    const totalBars = Math.floor(width / (barWidth + barGap))
    const centerY = height / 2

    ctx.fillStyle = isMuted ? "rgba(148, 163, 184, 0.5)" : "rgba(16, 185, 129, 0.85)"

    for (let b = 0; b < totalBars; b++) {
      const pseudo = Math.abs(Math.sin((b + hash) * 0.45) * 0.7 + Math.cos((b * 2 + hash) * 0.2) * 0.3)
      const barH = Math.max(3, pseudo * (height - 8))
      const x = b * (barWidth + barGap)
      const y = centerY - barH / 2

      ctx.beginPath()
      ctx.roundRect ? ctx.roundRect(x, y, barWidth, barH, 1.5) : ctx.rect(x, y, barWidth, barH)
      ctx.fill()
    }
  }, [clipId, width, height, isMuted])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: `${width}px`,
        height: `${height}px`,
        pointerEvents: "none",
        zIndex: 1,
      }}
    />
  )
}

/**
 * Video filmstrip canvas rendering decoded video contact-sheet thumbnails from backend
 */
function VideoFilmstripCanvas({ videoId, width, height, trimStart = 0, trimEnd = 0, duration = 5, sourceDuration = null }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!videoId || width <= 0 || height <= 0) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let cancelled = false
    const cells = Math.max(8, Math.min(64, Math.round(width / 32 / 4) * 4))
    const url = `/api/downloaded/${videoId}/filmstrip?n=${cells}&h=${Math.round(height)}`

    const img = new Image()
    img.crossOrigin = "anonymous"
    img.src = url
    img.onload = () => {
      if (cancelled) return
      const dpr = window.devicePixelRatio || 1
      canvas.width = width * dpr
      canvas.height = height * dpr
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, width, height)

      // Calculate slice of the contact sheet corresponding to [trimStart, trimStart + duration]
      const totalSrcDur = (sourceDuration && sourceDuration > 0) ? sourceDuration : (trimEnd > trimStart ? trimEnd : duration)
      const startFrac = Math.max(0, Math.min(1, totalSrcDur > 0 ? trimStart / totalSrcDur : 0))
      const endFrac = Math.max(startFrac, Math.min(1, totalSrcDur > 0 ? (trimStart + duration) / totalSrcDur : 1))
      const srcWFrac = Math.max(0.01, endFrac - startFrac)

      const sx = startFrac * img.width
      const sw = srcWFrac * img.width
      ctx.drawImage(img, sx, 0, sw, img.height, 0, 0, width, height)
    }

    return () => {
      cancelled = true
    }
  }, [videoId, width, height, trimStart, trimEnd, duration, sourceDuration])

  return (
    <canvas
      ref={canvasRef}
      className="video-filmstrip-canvas"
      data-filmstrip="video"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: `${width}px`,
        height: `${height}px`,
        pointerEvents: "none",
        zIndex: 1,
        opacity: 0.85,
      }}
    />
  )
}

/**
 * Adaptive Timeline Ruler with frame/second ticks and draggable playhead scrub
 */
function TimelineRuler({
  duration,
  currentTime,
  pixelsPerSecond,
  contentWidth,
  fps = 30,
  onSeek,
}) {
  const rulerRef = useRef(null)
  const isScrubbingRef = useRef(false)

  // Determine tick intervals based on zoom / pixelsPerSecond
  let majorStep = 1.0 // seconds
  let minorStep = 0.2
  if (pixelsPerSecond < 20) {
    majorStep = 5.0
    minorStep = 1.0
  } else if (pixelsPerSecond < 50) {
    majorStep = 2.0
    minorStep = 0.5
  } else if (pixelsPerSecond > 100) {
    majorStep = 0.5
    minorStep = 0.1
  }

  const ticks = useMemo(() => {
    const list = []
    const totalSecs = Math.max(duration, 30)
    for (let t = 0; t <= totalSecs; t += minorStep) {
      const isMajor = Math.abs(Math.round(t / majorStep) * majorStep - t) < 0.001
      list.push({ time: Number(t.toFixed(2)), isMajor })
    }
    return list
  }, [duration, majorStep, minorStep])

  const handlePointerDown = (e) => {
    e.preventDefault()
    isScrubbingRef.current = true
    const target = rulerRef.current
    if (target && target.setPointerCapture) {
      target.setPointerCapture(e.pointerId)
    }
    updateTimeFromEvent(e)
  }

  const handlePointerMove = (e) => {
    if (!isScrubbingRef.current) return
    updateTimeFromEvent(e)
  }

  const handlePointerUp = (e) => {
    if (!isScrubbingRef.current) return
    isScrubbingRef.current = false
    const target = rulerRef.current
    if (target && target.releasePointerCapture) {
      try { target.releasePointerCapture(e.pointerId) } catch {}
    }
  }

  const updateTimeFromEvent = (e) => {
    if (!rulerRef.current) return
    const rect = rulerRef.current.getBoundingClientRect()
    const offsetX = e.clientX - rect.left
    const newTime = Math.max(0, Math.min(duration, offsetX / pixelsPerSecond))
    if (onSeek) onSeek(Number(newTime.toFixed(3)))
  }

  const formatTimeLabel = (sec) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    const frames = Math.floor((sec % 1) * fps)
    return `${m}:${s < 10 ? "0" : ""}${s}.${frames < 10 ? "0" : ""}${frames}`
  }

  return (
    <Box
      ref={rulerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      sx={{
        height: 28,
        minHeight: 28,
        width: `${contentWidth}px`,
        position: "relative",
        bgcolor: "#f1f5f9",
        borderBottom: "1px solid",
        borderColor: "divider",
        cursor: "pointer",
        userSelect: "none",
      }}
    >
      {ticks.map((tick) => {
        const left = tick.time * pixelsPerSecond
        if (left > contentWidth + 100) return null
        return (
          <Box
            key={tick.time}
            sx={{
              position: "absolute",
              left: `${left}px`,
              bottom: 0,
              width: "1px",
              height: tick.isMajor ? 14 : 7,
              bgcolor: tick.isMajor ? "rgba(100, 116, 139, 0.7)" : "rgba(148, 163, 184, 0.4)",
              pointerEvents: "none",
            }}
          >
            {tick.isMajor && (
              <Typography
                variant="caption"
                sx={{
                  position: "absolute",
                  left: 4,
                  top: -15,
                  fontSize: "0.62rem",
                  fontFamily: "monospace",
                  fontWeight: 600,
                  color: "text.secondary",
                  whiteSpace: "nowrap",
                }}
              >
                {formatTimeLabel(tick.time)}
              </Typography>
            )}
          </Box>
        )
      })}

      {/* Playhead Grabber on Ruler */}
      <Box
        sx={{
          position: "absolute",
          left: `${currentTime * pixelsPerSecond}px`,
          top: 0,
          bottom: 0,
          transform: "translateX(-50%)",
          zIndex: 40,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          pointerEvents: "none",
        }}
      >
        <Box
          sx={{
            width: 12,
            height: 12,
            bgcolor: "#8b5cf6",
            clipPath: "polygon(0 0, 100% 0, 100% 60%, 50% 100%, 0 60%)",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
          }}
        />
      </Box>
    </Box>
  )
}

/**
 * Professional Sticky Track Header
 */
function TimelineTrackHeader({
  track,
  clipCount,
  onToggleState,
}) {
  const isVideo = track.type === "video"
  const isAudio = track.type === "audio"
  const isCaptions = track.type === "captions"
  const isGraphics = track.type === "graphics" || track.type === "components"
  const isImage = track.type === "image"

  const IconComp = isVideo
    ? IconVideo
    : isAudio
    ? IconMusic
    : isCaptions
    ? IconTypography
    : isGraphics
    ? IconComponents
    : IconPhoto

  const isVisible = track.visible !== false
  const isLocked = track.locked === true
  const isMuted = track.muted === true
  const isCollapsed = track.collapsed === true

  return (
    <Box
      sx={{
        width: HEADER_WIDTH,
        minWidth: HEADER_WIDTH,
        height: isCollapsed ? TRACK_COLLAPSED_HEIGHT : TRACK_NORMAL_HEIGHT,
        bgcolor: "#f8fafc",
        borderRight: "1px solid",
        borderBottom: "1px solid",
        borderColor: "divider",
        px: 1,
        py: 0.5,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        boxSizing: "border-box",
        zIndex: 10,
      }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0, flex: 1 }}>
        <IconButton
          size="small"
          onClick={() => onToggleState(track.id, { collapsed: !isCollapsed })}
          sx={{ width: 18, height: 18, p: 0, color: "text.secondary" }}
        >
          {isCollapsed ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
        </IconButton>
        <IconComp size={15} color="#64748b" />
        <Typography
          variant="caption"
          sx={{
            fontWeight: 700,
            fontSize: "0.72rem",
            color: "text.primary",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {track.name || track.id}
        </Typography>
        <Chip
          label={clipCount}
          size="small"
          sx={{
            height: 16,
            fontSize: "0.6rem",
            fontWeight: 700,
            bgcolor: "#e2e8f0",
            color: "#475569",
            px: 0.25,
          }}
        />
      </Stack>

      {/* Track Quick Actions: Mute / Lock / Visibility */}
      <Stack direction="row" spacing={0.25} alignItems="center">
        {(isAudio || isVideo) && (
          <Tooltip title={isMuted ? "Unmute Track" : "Mute Track"} arrow>
            <IconButton
              size="small"
              onClick={() => onToggleState(track.id, { muted: !isMuted })}
              sx={{ width: 20, height: 20, p: 0, color: isMuted ? "error.main" : "text.secondary" }}
            >
              {isMuted ? <IconVolumeOff size={13} /> : <IconVolume size={13} />}
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title={isLocked ? "Unlock Track" : "Lock Track"} arrow>
          <IconButton
            size="small"
            onClick={() => onToggleState(track.id, { locked: !isLocked })}
            sx={{ width: 20, height: 20, p: 0, color: isLocked ? "warning.main" : "text.secondary" }}
          >
            {isLocked ? <IconLock size={13} /> : <IconLockOpen size={13} />}
          </IconButton>
        </Tooltip>
        <Tooltip title={isVisible ? "Hide Track" : "Show Track"} arrow>
          <IconButton
            size="small"
            onClick={() => onToggleState(track.id, { visible: !isVisible })}
            sx={{ width: 20, height: 20, p: 0, color: isVisible ? "text.secondary" : "text.disabled" }}
          >
            {isVisible ? <IconEye size={13} /> : <IconEyeOff size={13} />}
          </IconButton>
        </Tooltip>
      </Stack>
    </Box>
  )
}

/**
 * Keyframe Diamond Glyph Strip rendered over clip
 */
function TimelineClipDiamonds({
  clip,
  clipDuration,
  widthPx,
  currentTime,
  onSelectKeyframe,
  onDragKeyframe,
}) {
  const anims = clip.animations || []
  if (anims.length === 0 || clipDuration <= 0) return null

  return (
    <Box
      sx={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 2,
        height: 12,
        pointerEvents: "none",
        zIndex: 5,
      }}
    >
      {anims.map((anim, idx) => {
        const animTime = Number(anim.time || 0)
        const pct = Math.max(0, Math.min(100, (animTime / clipDuration) * 100))
        const absTime = Number(clip.start_seconds || 0) + animTime
        const isNearPlayhead = Math.abs(currentTime - absTime) < 0.08

        return (
          <Tooltip
            key={`${anim.property}_${animTime}_${idx}`}
            title={`${anim.property}: ${anim.value} at ${animTime.toFixed(2)}s (${anim.ease || "none"})`}
            arrow
          >
            <Box
              data-keyframe-diamond={anim.property}
              onClick={(e) => {
                e.stopPropagation()
                if (onSelectKeyframe) onSelectKeyframe(anim)
              }}
              sx={{
                position: "absolute",
                left: `${pct}%`,
                top: 0,
                transform: "translateX(-50%) rotate(45deg)",
                width: 7,
                height: 7,
                bgcolor: isNearPlayhead ? "#facc15" : "#ffffff",
                border: "1px solid",
                borderColor: isNearPlayhead ? "#eab308" : "#9333ea",
                boxShadow: "0 1px 2px rgba(0,0,0,0.3)",
                pointerEvents: "auto",
                cursor: "pointer",
                "&:hover": {
                  transform: "translateX(-50%) rotate(45deg) scale(1.3)",
                  bgcolor: "#facc15",
                },
              }}
            />
          </Tooltip>
        )
      })}
    </Box>
  )
}

/**
 * Expandable Property Lanes beneath selected clip
 */
function TimelinePropertyLanes({
  clip,
  pixelsPerSecond,
  currentTime,
  onAddKeyframe,
  onUpdateKeyframe,
  onRemoveKeyframe,
}) {
  const clipStart = Number(clip.start_seconds || 0)
  const clipDur = Number(clip.duration_seconds || 5)
  const relTime = Math.max(0, Math.min(clipDur, Number((currentTime - clipStart).toFixed(2))))

  return (
    <Box
      sx={{
        mt: 0.5,
        borderTop: "1px dashed rgba(255,255,255,0.2)",
        pt: 0.5,
      }}
    >
      {ANIMATABLE_PROPERTIES.map((propDef) => {
        const propKey = propDef.key
        const animList = (clip.animations || []).filter((a) => a.property === propKey)
        const activeKf = animList.find((a) => Math.abs(Number(a.time) - relTime) < 0.05)

        return (
          <Box
            key={propKey}
            sx={{
              height: PROPERTY_LANE_HEIGHT,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              bgcolor: "rgba(0,0,0,0.25)",
              borderRadius: 0.75,
              mb: 0.25,
              px: 1,
            }}
          >
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="caption" sx={{ fontSize: "0.65rem", fontWeight: 700, color: "rgba(255,255,255,0.8)" }}>
                {propDef.label}
              </Typography>
              <Typography variant="caption" sx={{ fontSize: "0.62rem", color: "#a5b4fc", fontFamily: "monospace" }}>
                {activeKf ? `${activeKf.value} (kf)` : `${propDef.default} (base)`}
              </Typography>
            </Stack>

            <Tooltip title={`Add keyframe for ${propDef.label} at ${relTime.toFixed(2)}s`} arrow>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation()
                  if (onAddKeyframe) {
                    onAddKeyframe(clip.id, {
                      property: propKey,
                      time: relTime,
                      value: activeKf ? activeKf.value : propDef.default,
                      ease: "power2.out",
                    })
                  }
                }}
                sx={{
                  width: 18,
                  height: 18,
                  p: 0,
                  color: activeKf ? "#facc15" : "rgba(255,255,255,0.6)",
                  bgcolor: activeKf ? "rgba(250,204,21,0.2)" : "transparent",
                }}
              >
                <IconDiamond size={12} />
              </IconButton>
            </Tooltip>
          </Box>
        )
      })}
    </Box>
  )
}

/**
 * Main Professional Motion Timeline Workspace
 */
export default function StudioTimelineWorkspace({
  tracks = [],
  currentTime = 0,
  duration = 15,
  fps = 30,
  isPlaying = false,
  onTogglePlay,
  onSeek,
  selectedElementId,
  onSelectElement,
  onDeleteClip,
  onUpdateClipTiming,
  onDuplicateClip,
  onSplitClip,
  onAddKeyframe,
  onUpdateKeyframe,
  onRemoveKeyframe,
  onToggleTrackState,
}) {
  const containerRef = useRef(null)
  const [zoom, setZoom] = useState(1.0)
  const [snap, setSnap] = useState(true)
  const [expandedLanes, setExpandedLanes] = useState(new Set()) // Set of clipIds with expanded lanes
  const [contextMenu, setContextMenu] = useState(null) // { mouseX, mouseY, clip }
  const [snapGuideTime, setSnapGuideTime] = useState(null)

  // Drag / Trim State
  // { mode: 'move'|'trim-left'|'trim-right', clipId, startX, origStart, origDur, origTrimStart, currentStart, currentDur, currentTrimStart }
  const [dragState, setDragState] = useState(null)

  const pixelsPerSecond = 40 * zoom
  const contentWidth = Math.max(900, (duration + 5) * pixelsPerSecond)

  // Toggle Keyframe Lanes expansion for a clip
  const handleToggleLanes = (clipId) => {
    setExpandedLanes((prev) => {
      const next = new Set(prev)
      if (next.has(clipId)) next.delete(clipId)
      else next.add(clipId)
      return next
    })
  }

  // Snapping targets collector
  const snapTargets = useMemo(() => {
    if (!snap) return []
    const targets = [{ time: currentTime, type: "playhead" }]
    tracks.forEach((t) => {
      (t.clips || []).forEach((c) => {
        if (dragState && c.id === dragState.clipId) return
        const s = Number(c.start_seconds || 0)
        const d = Number(c.duration_seconds || 5)
        targets.push({ time: s, type: "clip-edge" })
        targets.push({ time: s + d, type: "clip-edge" })
      })
    })
    return targets
  }, [snap, tracks, currentTime, dragState])

  // Snapping logic with visible snap guide
  const snapValue = useCallback((candidateTime, targets, pps) => {
    const thresholdSec = 10 / Math.max(pps, 1)
    let best = null
    let bestDist = thresholdSec
    for (const tgt of targets) {
      const dist = Math.abs(tgt.time - candidateTime)
      if (dist < bestDist) {
        bestDist = dist
        best = tgt
      }
    }
    if (best) {
      return { time: best.time, target: best }
    }
    // Snap to frame boundary
    const frameDur = 1 / fps
    const nearestFrame = Math.round(candidateTime / frameDur) * frameDur
    if (Math.abs(nearestFrame - candidateTime) < thresholdSec * 0.6) {
      return { time: Number(nearestFrame.toFixed(3)), target: { time: nearestFrame, type: "frame" } }
    }
    return { time: candidateTime, target: null }
  }, [fps])

  // Drag / Trim Mouse Move & Mouse Up
  useEffect(() => {
    if (!dragState) return

    const handleMouseMove = (e) => {
      const deltaPx = e.clientX - dragState.startX
      const deltaTime = deltaPx / pixelsPerSecond

      if (dragState.mode === "move") {
        let rawStart = Math.max(0, dragState.origStart + deltaTime)
        let snapped = rawStart
        let guide = null

        if (snap) {
          // Check snap on start edge
          const startSnap = snapValue(rawStart, snapTargets, pixelsPerSecond)
          // Check snap on end edge
          const endSnap = snapValue(rawStart + dragState.origDur, snapTargets, pixelsPerSecond)

          if (startSnap.target) {
            snapped = startSnap.time
            guide = startSnap.time
          } else if (endSnap.target) {
            snapped = endSnap.time - dragState.origDur
            guide = endSnap.time
          }
        }
        setSnapGuideTime(guide)
        setDragState((prev) => prev ? {
          ...prev,
          currentStart: Math.max(0, Number(snapped.toFixed(2))),
        } : null)
      } else if (dragState.mode === "trim-left") {
        let rawStart = Math.max(0, Math.min(dragState.origStart + dragState.origDur - 0.2, dragState.origStart + deltaTime))
        let snapped = rawStart
        let guide = null
        if (snap) {
          const s = snapValue(rawStart, snapTargets, pixelsPerSecond)
          if (s.target) {
            snapped = s.time
            guide = s.time
          }
        }
        setSnapGuideTime(guide)
        const nextDur = Math.max(0.2, dragState.origDur - (snapped - dragState.origStart))
        const deltaTrim = snapped - dragState.origStart
        setDragState((prev) => prev ? {
          ...prev,
          currentStart: Number(snapped.toFixed(2)),
          currentDur: Number(nextDur.toFixed(2)),
          currentTrimStart: Math.max(0, Number((dragState.origTrimStart + deltaTrim).toFixed(2))),
        } : null)
      } else if (dragState.mode === "trim-right") {
        let rawDur = Math.max(0.2, dragState.origDur + deltaTime)
        let rawEnd = dragState.origStart + rawDur
        let snappedEnd = rawEnd
        let guide = null
        if (snap) {
          const s = snapValue(rawEnd, snapTargets, pixelsPerSecond)
          if (s.target) {
            snappedEnd = s.time
            guide = s.time
          }
        }
        setSnapGuideTime(guide)
        const nextDur = Math.max(0.2, snappedEnd - dragState.origStart)
        setDragState((prev) => prev ? {
          ...prev,
          currentDur: Number(nextDur.toFixed(2)),
        } : null)
      }
    }

    const handleMouseUp = () => {
      setSnapGuideTime(null)
      if (dragState && onUpdateClipTiming) {
        const finalStart = dragState.currentStart != null ? dragState.currentStart : dragState.origStart
        const finalDur = dragState.currentDur != null ? dragState.currentDur : dragState.origDur
        const patch = {}
        if (finalStart !== dragState.origStart) patch.start_seconds = finalStart
        if (finalDur !== dragState.origDur) patch.duration_seconds = finalDur
        if (dragState.currentTrimStart != null && dragState.currentTrimStart !== dragState.origTrimStart) {
          patch.trim_start = dragState.currentTrimStart
        }
        if (Object.keys(patch).length > 0) {
          onUpdateClipTiming(dragState.clipId, patch)
        }
      }
      setDragState(null)
    }

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [dragState, pixelsPerSecond, snap, snapTargets, snapValue, onUpdateClipTiming])

  // Keyboard Shortcuts: Space (Play/Pause), Delete (Remove), Ctrl+D (Duplicate), S (Split)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't intercept when user is typing in an input
      if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return

      if (e.code === "Space") {
        e.preventDefault()
        if (onTogglePlay) onTogglePlay()
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedElementId) {
          const selectedClip = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
          if (selectedClip && onDeleteClip) {
            e.preventDefault()
            onDeleteClip(selectedClip)
          }
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") {
        if (selectedElementId) {
          const selectedClip = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
          if (selectedClip && onDuplicateClip) {
            e.preventDefault()
            onDuplicateClip(selectedClip)
          }
        }
      } else if (e.key.toLowerCase() === "s" && !e.ctrlKey && !e.metaKey) {
        if (selectedElementId) {
          const selectedClip = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
          if (selectedClip && onSplitClip) {
            const cStart = Number(selectedClip.start_seconds || 0)
            const cDur = Number(selectedClip.duration_seconds || 5)
            if (currentTime > cStart + 0.1 && currentTime < cStart + cDur - 0.1) {
              e.preventDefault()
              onSplitClip(selectedClip, currentTime)
            }
          }
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [selectedElementId, tracks, currentTime, onTogglePlay, onDeleteClip, onDuplicateClip, onSplitClip])

  // Context Menu handlers
  const handleContextMenu = (e, clip) => {
    e.preventDefault()
    e.stopPropagation()
    if (onSelectElement) onSelectElement(clip)
    setContextMenu({
      mouseX: e.clientX,
      mouseY: e.clientY,
      clip,
    })
  }

  const handleCloseContextMenu = () => {
    setContextMenu(null)
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#ffffff",
        borderTop: "1px solid",
        borderColor: "divider",
        userSelect: "none",
        overflow: "hidden",
      }}
    >
      {/* 1. Timeline Controls Header */}
      <Box
        sx={{
          height: 38,
          minHeight: 38,
          px: 1.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          bgcolor: "#f8fafc",
          borderBottom: "1px solid",
          borderColor: "divider",
          zIndex: 20,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="caption" sx={{ fontWeight: 800, fontSize: "0.72rem", textTransform: "uppercase", color: "#475569" }}>
            Professional Timeline
          </Typography>

          <Tooltip title={isPlaying ? "Pause (Space)" : "Play (Space)"} arrow>
            <IconButton
              size="small"
              onClick={onTogglePlay}
              sx={{ width: 26, height: 26, color: isPlaying ? "primary.main" : "text.secondary" }}
            >
              {isPlaying ? <IconPlayerPause size={16} /> : <IconPlayerPlay size={16} />}
            </IconButton>
          </Tooltip>

          <Tooltip title={snap ? "Magnetic Snapping: Enabled (Edge/Frame)" : "Magnetic Snapping: Disabled"} arrow>
            <IconButton
              size="small"
              onClick={() => setSnap(!snap)}
              sx={{
                width: 26,
                height: 26,
                color: snap ? "primary.main" : "text.secondary",
                bgcolor: snap ? "#ede9fe" : "transparent",
              }}
            >
              <IconMagnet size={15} />
            </IconButton>
          </Tooltip>

          {selectedElementId && (
            <Tooltip title="Split at Playhead (S)" arrow>
              <IconButton
                size="small"
                onClick={() => {
                  const sel = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
                  if (sel && onSplitClip) onSplitClip(sel, currentTime)
                }}
                sx={{ width: 26, height: 26, color: "text.secondary" }}
              >
                <IconScissors size={15} />
              </IconButton>
            </Tooltip>
          )}

          {selectedElementId && (
            <Tooltip title="Duplicate Clip (Ctrl+D)" arrow>
              <IconButton
                size="small"
                onClick={() => {
                  const sel = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
                  if (sel && onDuplicateClip) onDuplicateClip(sel)
                }}
                sx={{ width: 26, height: 26, color: "text.secondary" }}
              >
                <IconCopy size={15} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>

        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography variant="caption" sx={{ fontSize: "0.7rem", fontWeight: 700, color: "text.secondary", fontFamily: "monospace" }}>
            {currentTime.toFixed(2)}s / {duration.toFixed(2)}s
          </Typography>

          <Stack direction="row" spacing={0.5} alignItems="center">
            <IconButton size="small" onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}>
              <IconZoomOut size={15} />
            </IconButton>
            <Typography variant="caption" sx={{ fontSize: "0.7rem", fontWeight: 700, width: 36, textAlign: "center" }}>
              {Math.round(zoom * 100)}%
            </Typography>
            <IconButton size="small" onClick={() => setZoom(Math.min(4.0, zoom + 0.25))}>
              <IconZoomIn size={15} />
            </IconButton>
          </Stack>
        </Stack>
      </Box>

      {/* 2. Main Scrollable Timeline Content (Headers + Tracks Grid) */}
      <Box
        ref={containerRef}
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflowX: "auto",
          overflowY: "auto",
          position: "relative",
          bgcolor: "#ffffff",
        }}
      >
        {/* Ruler Row: Sticky Header Corner + Ruler Ticks */}
        <Box sx={{ display: "flex", width: `${HEADER_WIDTH + contentWidth}px`, position: "sticky", top: 0, zIndex: 30 }}>
          <Box
            sx={{
              width: HEADER_WIDTH,
              minWidth: HEADER_WIDTH,
              height: 28,
              bgcolor: "#f1f5f9",
              borderRight: "1px solid",
              borderBottom: "1px solid",
              borderColor: "divider",
              px: 1.5,
              display: "flex",
              alignItems: "center",
              position: "sticky",
              left: 0,
              zIndex: 35,
            }}
          >
            <Typography variant="caption" sx={{ fontSize: "0.65rem", fontWeight: 800, color: "text.secondary", textTransform: "uppercase" }}>
              Tracks
            </Typography>
          </Box>
          <TimelineRuler
            duration={duration}
            currentTime={currentTime}
            pixelsPerSecond={pixelsPerSecond}
            contentWidth={contentWidth}
            fps={fps}
            onSeek={onSeek}
          />
        </Box>

        {/* Playhead Vertical Guideline across full tracks height */}
        <Box
          data-timeline-playhead-guide=""
          sx={{
            position: "absolute",
            top: 28,
            bottom: 0,
            left: `${HEADER_WIDTH + currentTime * pixelsPerSecond}px`,
            width: "2px",
            bgcolor: "#8b5cf6",
            zIndex: 25,
            pointerEvents: "none",
          }}
        />

        {/* Vertical Magnetic Snap Guideline */}
        {snapGuideTime != null && (
          <Box
            data-timeline-snap-guide=""
            sx={{
              position: "absolute",
              top: 28,
              bottom: 0,
              left: `${HEADER_WIDTH + snapGuideTime * pixelsPerSecond}px`,
              width: "1.5px",
              bgcolor: "#eab308",
              boxShadow: "0 0 6px rgba(234, 179, 8, 0.8)",
              zIndex: 26,
              pointerEvents: "none",
            }}
          />
        )}

        {/* Tracks List */}
        <Box sx={{ width: `${HEADER_WIDTH + contentWidth}px`, flex: 1, position: "relative" }}>
          {tracks.length === 0 ? (
            <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 6 }}>
              No tracks in project composition. Add media or blocks to start.
            </Typography>
          ) : (
            tracks.map((track) => {
              const isCollapsed = track.collapsed === true
              const isVisible = track.visible !== false
              const isLocked = track.locked === true
              const isMuted = track.muted === true
              const clips = track.clips || []

              // Compute track row height including expanded animation property lanes
              const hasExpandedClips = clips.some((c) => expandedLanes.has(c.id))
              const dynamicRowHeight = isCollapsed
                ? TRACK_COLLAPSED_HEIGHT
                : (TRACK_NORMAL_HEIGHT + (hasExpandedClips ? ANIMATABLE_PROPERTIES.length * (PROPERTY_LANE_HEIGHT + 3) : 0))

              return (
                <Box
                  key={track.id}
                  sx={{
                    display: "flex",
                    minHeight: dynamicRowHeight,
                    borderBottom: "1px solid",
                    borderColor: "divider",
                    bgcolor: isVisible ? "#ffffff" : "#f8fafc",
                    opacity: isVisible ? 1 : 0.5,
                  }}
                >
                  {/* Sticky Track Header Column */}
                  <Box sx={{ position: "sticky", left: 0, zIndex: 12, bgcolor: "#f8fafc" }}>
                    <TimelineTrackHeader
                      track={track}
                      clipCount={clips.length}
                      onToggleState={onToggleTrackState || (() => {})}
                    />
                  </Box>

                  {/* Track Clips Canvas Lane */}
                  <Box
                    sx={{
                      width: `${contentWidth}px`,
                      position: "relative",
                      bgcolor: isCollapsed ? "#f8fafc" : "#ffffff",
                      overflow: "hidden",
                    }}
                  >
                    {!isCollapsed && clips.map((clip) => {
                      const isDraggingThis = dragState?.clipId === clip.id
                      const clipStart = isDraggingThis && dragState.currentStart != null
                        ? dragState.currentStart
                        : Number(clip.start_seconds || 0)
                      const clipDur = isDraggingThis && dragState.currentDur != null
                        ? dragState.currentDur
                        : Number(clip.duration_seconds || 5)
                      const isSelected = selectedElementId === clip.id
                      const leftPx = clipStart * pixelsPerSecond
                      const widthPx = Math.max(36, clipDur * pixelsPerSecond)
                      const lanesOpen = expandedLanes.has(clip.id)

                      // Type specific styling
                      const isVideo = track.type === "video" || clip.type === "video"
                      const isAudio = track.type === "audio" || clip.type === "audio"
                      const isBlock = clip.type === "block" || !!clip.block_id
                      const isCaption = track.type === "captions" || !!clip.caption_text
                      const isImage = track.type === "image" || clip.type === "image"

                      let bgGradient = isSelected
                        ? "linear-gradient(135deg, #7c3aed 0%, #6366f1 100%)"
                        : "linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)"
                      let badgeColor = "#818cf8"

                      if (isAudio) {
                        bgGradient = isSelected
                          ? "linear-gradient(135deg, #059669 0%, #10b981 100%)"
                          : "linear-gradient(135deg, #047857 0%, #065f46 100%)"
                        badgeColor = "#34d399"
                      } else if (isBlock) {
                        bgGradient = isSelected
                          ? "linear-gradient(135deg, #c026d3 0%, #9333ea 100%)"
                          : "linear-gradient(135deg, #a21caf 0%, #7e22ce 100%)"
                        badgeColor = "#e879f9"
                      } else if (isCaption) {
                        bgGradient = isSelected
                          ? "linear-gradient(135deg, #d97706 0%, #b45309 100%)"
                          : "linear-gradient(135deg, #b45309 0%, #92400e 100%)"
                        badgeColor = "#fbbf24"
                      } else if (isImage) {
                        bgGradient = isSelected
                          ? "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)"
                          : "linear-gradient(135deg, #0369a1 0%, #075985 100%)"
                        badgeColor = "#38bdf8"
                      }

                      return (
                        <Box
                          key={clip.id}
                          data-clip-id={clip.id}
                          data-clip-title={clip.title || clip.id}
                          onClick={(e) => {
                            e.stopPropagation()
                            if (onSelectElement) onSelectElement(clip)
                          }}
                          onContextMenu={(e) => handleContextMenu(e, clip)}
                          onMouseDown={(e) => {
                            if (isLocked || e.target.dataset.handle || e.target.dataset.keyframeDiamond) return
                            e.stopPropagation()
                            if (onSelectElement) onSelectElement(clip)
                            setDragState({
                              clipId: clip.id,
                              mode: "move",
                              startX: e.clientX,
                              origStart: Number(clip.start_seconds || 0),
                              origDur: Number(clip.duration_seconds || 5),
                              origTrimStart: Number(clip.trim_start || 0),
                              currentStart: Number(clip.start_seconds || 0),
                              currentDur: Number(clip.duration_seconds || 5),
                              currentTrimStart: Number(clip.trim_start || 0),
                            })
                          }}
                          sx={{
                            position: "absolute",
                            left: `${leftPx}px`,
                            width: `${widthPx}px`,
                            top: 4,
                            bottom: lanesOpen ? "auto" : 4,
                            background: bgGradient,
                            color: "#ffffff",
                            borderRadius: 1.5,
                            p: 0.75,
                            cursor: isLocked ? "not-allowed" : (isDraggingThis ? "grabbing" : "grab"),
                            boxShadow: isSelected ? "0 0 0 2px #c4b5fd, 0 4px 6px -1px rgba(0,0,0,0.15)" : "0 1px 3px rgba(0,0,0,0.1)",
                            opacity: isDraggingThis ? 0.9 : 1,
                            overflow: lanesOpen ? "visible" : "hidden",
                            zIndex: isDraggingThis ? 18 : (isSelected ? 10 : 5),
                            display: "flex",
                            flexDirection: "column",
                            justifyContent: "space-between",
                          }}
                        >
                          {/* Video Filmstrip Canvas */}
                          {isVideo && (
                            <VideoFilmstripCanvas
                              videoId={clip.asset_id || clip.video_id}
                              width={widthPx}
                              height={TRACK_NORMAL_HEIGHT - 8}
                              trimStart={Number(clip.trim_start || 0)}
                              trimEnd={Number(clip.trim_end || 0)}
                              duration={Number(clip.duration_seconds || 5)}
                              sourceDuration={Number(clip.source_duration || 0)}
                            />
                          )}

                          {/* Audio Waveform Canvas */}
                          {isAudio && (
                            <AudioWaveformCanvas
                              clipId={clip.id}
                              width={widthPx}
                              height={TRACK_NORMAL_HEIGHT - 8}
                              isMuted={isMuted}
                            />
                          )}

                          {/* Left Trim Handle */}
                          {!isLocked && (
                            <Box
                              data-handle="trim-left"
                              onMouseDown={(e) => {
                                e.stopPropagation()
                                setDragState({
                                  clipId: clip.id,
                                  mode: "trim-left",
                                  startX: e.clientX,
                                  origStart: Number(clip.start_seconds || 0),
                                  origDur: Number(clip.duration_seconds || 5),
                                  origTrimStart: Number(clip.trim_start || 0),
                                  currentStart: Number(clip.start_seconds || 0),
                                  currentDur: Number(clip.duration_seconds || 5),
                                  currentTrimStart: Number(clip.trim_start || 0),
                                })
                              }}
                              sx={{
                                position: "absolute",
                                left: 0,
                                top: 0,
                                bottom: lanesOpen ? "auto" : 0,
                                height: lanesOpen ? TRACK_NORMAL_HEIGHT - 8 : "100%",
                                width: 8,
                                cursor: "ew-resize",
                                bgcolor: "rgba(255,255,255,0.2)",
                                zIndex: 12,
                                "&:hover": { bgcolor: "rgba(255,255,255,0.7)" },
                              }}
                            />
                          )}

                          {/* Top Row: Clip Title & Badges */}
                          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ zIndex: 4, minWidth: 0 }}>
                            {isBlock && <IconComponents size={13} color="#f5d0fe" />}
                            {isAudio && <IconMusic size={13} color="#a7f3d0" />}
                            {isVideo && <IconVideo size={13} color="#c7d2fe" />}
                            {isCaption && <IconTypography size={13} color="#fef08a" />}
                            {isImage && <IconPhoto size={13} color="#bae6fd" />}

                            <Typography
                              variant="caption"
                              sx={{
                                fontWeight: 700,
                                fontSize: "0.68rem",
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              {clip.title || clip.caption_text || clip.asset_file || clip.block_id || clip.id}
                            </Typography>
                          </Stack>

                          {/* Block Variables Summary Pill */}
                          {isBlock && clip.variables && Object.keys(clip.variables).length > 0 && (
                            <Box sx={{ zIndex: 4, display: "flex", gap: 0.5, flexWrap: "wrap", mt: 0.25 }}>
                              {Object.entries(clip.variables).slice(0, 2).map(([k, v]) => (
                                <Chip
                                  key={k}
                                  label={`${k}: ${String(v).slice(0, 10)}`}
                                  size="small"
                                  sx={{
                                    height: 14,
                                    fontSize: "0.55rem",
                                    bgcolor: "rgba(0,0,0,0.3)",
                                    color: "#f5d0fe",
                                  }}
                                />
                              ))}
                            </Box>
                          )}

                          {/* Bottom Row: In/Out Duration indicator + Keyframe Diamonds Toggle */}
                          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ zIndex: 4, mt: 0.25 }}>
                            <Typography variant="caption" sx={{ fontSize: "0.58rem", opacity: 0.85, fontFamily: "monospace" }}>
                              {clipDur.toFixed(1)}s
                            </Typography>

                            {/* Keyframe Lanes toggle button */}
                            <Tooltip title={lanesOpen ? "Hide Animation Lanes" : "Show Animation Lanes"} arrow>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleToggleLanes(clip.id)
                                }}
                                sx={{
                                  width: 16,
                                  height: 16,
                                  p: 0,
                                  color: lanesOpen ? "#facc15" : "rgba(255,255,255,0.7)",
                                }}
                              >
                                <IconDiamonds size={12} />
                              </IconButton>
                            </Tooltip>
                          </Stack>

                          {/* Keyframe Diamonds on Clip */}
                          <TimelineClipDiamonds
                            clip={clip}
                            clipDuration={clipDur}
                            widthPx={widthPx}
                            currentTime={currentTime}
                            onSelectKeyframe={(kf) => {
                              if (onSelectElement) onSelectElement(clip)
                            }}
                          />

                          {/* Expandable Property Lanes (when open) */}
                          {lanesOpen && (
                            <TimelinePropertyLanes
                              clip={clip}
                              pixelsPerSecond={pixelsPerSecond}
                              currentTime={currentTime}
                              onAddKeyframe={onAddKeyframe}
                              onUpdateKeyframe={onUpdateKeyframe}
                              onRemoveKeyframe={onRemoveKeyframe}
                            />
                          )}

                          {/* Right Trim Handle */}
                          {!isLocked && (
                            <Box
                              data-handle="trim-right"
                              onMouseDown={(e) => {
                                e.stopPropagation()
                                setDragState({
                                  clipId: clip.id,
                                  mode: "trim-right",
                                  startX: e.clientX,
                                  origStart: Number(clip.start_seconds || 0),
                                  origDur: Number(clip.duration_seconds || 5),
                                  origTrimStart: Number(clip.trim_start || 0),
                                  currentStart: Number(clip.start_seconds || 0),
                                  currentDur: Number(clip.duration_seconds || 5),
                                  currentTrimStart: Number(clip.trim_start || 0),
                                })
                              }}
                              sx={{
                                position: "absolute",
                                right: 0,
                                top: 0,
                                bottom: lanesOpen ? "auto" : 0,
                                height: lanesOpen ? TRACK_NORMAL_HEIGHT - 8 : "100%",
                                width: 8,
                                cursor: "ew-resize",
                                bgcolor: "rgba(255,255,255,0.2)",
                                zIndex: 12,
                                "&:hover": { bgcolor: "rgba(255,255,255,0.7)" },
                              }}
                            />
                          )}
                        </Box>
                      )
                    })}
                  </Box>
                </Box>
              )
            })
          )}
        </Box>
      </Box>

      {/* 3. Context Menu on Clip */}
      <Menu
        open={contextMenu !== null}
        onClose={handleCloseContextMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu !== null
            ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
            : undefined
        }
      >
        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onDuplicateClip) onDuplicateClip(contextMenu.clip)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconCopy size={16} /></ListItemIcon>
          <ListItemText primary="Duplicate Clip" secondary="Ctrl+D" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onSplitClip) onSplitClip(contextMenu.clip, currentTime)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconScissors size={16} /></ListItemIcon>
          <ListItemText primary="Split at Playhead" secondary="S" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip) handleToggleLanes(contextMenu.clip.id)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconDiamonds size={16} /></ListItemIcon>
          <ListItemText primary="Toggle Animation Lanes" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onDeleteClip) onDeleteClip(contextMenu.clip)
            handleCloseContextMenu()
          }}
          sx={{ color: "error.main" }}
        >
          <ListItemIcon sx={{ color: "error.main" }}><IconTrash size={16} /></ListItemIcon>
          <ListItemText primary="Delete Clip" secondary="Del" />
        </MenuItem>
      </Menu>
    </Box>
  )
}
