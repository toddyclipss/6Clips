// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useRef, useState, useEffect, useMemo, useCallback } from "react"
import {
  Box, Stack, Typography, IconButton, Tooltip, Menu, MenuItem,
  ListItemIcon, ListItemText, Chip, InputBase, Dialog,
  DialogTitle, DialogContent, DialogContentText, DialogActions, Button,
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
  IconArrowUp,
  IconArrowDown,
  IconEdit,
  IconHeadphones,
  IconAlertTriangle,
  IconGauge,
  IconArrowsExchange,
} from "@tabler/icons-react"

const HEADER_WIDTH = 220
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
 * Validate type compatibility between a clip and a destination track.
 * Enforces strict content-safety boundaries:
 * - Captions/text cannot be dropped onto audio tracks
 * - Audio cannot be dropped onto video or captions tracks
 * - Transitions and effects cannot cross into audio or captions
 * - Locked tracks always reject drops
 */
function isDropTargetValid(clip, targetTrack) {
  if (!clip || !targetTrack) return false
  if (targetTrack.locked) return false
  const destType = (targetTrack.type || "video").toLowerCase()
  const cType = (clip.type || clip.mediaType || "").toLowerCase()
  const isAudioClip = cType === "audio" || Boolean(clip.audio_file)
  const isCaptionClip = cType === "captions" || cType === "caption" || cType === "text" || Boolean(clip.caption_text)
  const isTransitionClip = cType === "transition" || cType === "transitions"
  const isEffectClip = cType === "effect" || cType === "filter" || cType === "effects"

  if (isAudioClip) return destType === "audio"
  if (destType === "audio") return isAudioClip
  if (isCaptionClip) return destType === "captions" || destType === "text"
  if (destType === "captions" || destType === "text") return isCaptionClip
  if (isTransitionClip) return destType === "transition" || destType === "transitions"
  if (destType === "transition" || destType === "transitions") return isTransitionClip
  if (isEffectClip) return destType === "effects" || destType === "effect"
  if (destType === "effects" || destType === "effect") return isEffectClip
  return ["video", "media", "image", "graphics", "components"].includes(destType)
}

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
 * Video filmstrip canvas rendering decoded video contact-sheet thumbnails
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
    const img = new Image()
    img.crossOrigin = "anonymous"
    img.src = `/api/projects/filmstrip/${videoId}`

    img.onload = () => {
      if (cancelled) return
      const dpr = window.devicePixelRatio || 1
      canvas.width = width * dpr
      canvas.height = height * dpr
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, width, height)

      const tileWidth = 60
      const totalTiles = Math.max(1, Math.ceil(width / tileWidth))
      const totalSourceFrames = 10
      const effectiveSourceDur = sourceDuration || duration || 10
      const startFraction = Math.max(0, Math.min(1, trimStart / effectiveSourceDur))
      const endFraction = Math.max(startFraction, Math.min(1, (trimEnd || (trimStart + duration)) / effectiveSourceDur))
      const frameSpan = endFraction - startFraction

      for (let i = 0; i < totalTiles; i++) {
        const localFraction = startFraction + (i / totalTiles) * frameSpan
        const frameIndex = Math.min(totalSourceFrames - 1, Math.max(0, Math.floor(localFraction * totalSourceFrames)))
        const sx = frameIndex * (img.naturalWidth / totalSourceFrames)
        const sw = img.naturalWidth / totalSourceFrames
        const sy = 0
        const sh = img.naturalHeight
        const dx = i * tileWidth
        const dw = tileWidth
        const dy = 0
        const dh = height

        ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh)
        ctx.fillStyle = "rgba(0,0,0,0.18)"
        ctx.fillRect(dx + dw - 1, dy, 1, dh)
      }
    }

    return () => {
      cancelled = true
    }
  }, [videoId, width, height, trimStart, trimEnd, duration, sourceDuration])

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
        opacity: 0.85,
      }}
    />
  )
}

/**
 * Top Timeline Ruler Component with scrubbing
 */
function TimelineRuler({ duration = 15, currentTime = 0, pixelsPerSecond = 40, contentWidth = 900, fps = 30, onSeek }) {
  const rulerRef = useRef(null)
  const isScrubbingRef = useRef(false)

  const { majorStep, minorStep } = useMemo(() => {
    if (pixelsPerSecond >= 80) return { majorStep: 1, minorStep: 0.2 }
    if (pixelsPerSecond >= 40) return { majorStep: 2, minorStep: 0.5 }
    if (pixelsPerSecond >= 20) return { majorStep: 5, minorStep: 1 }
    return { majorStep: 10, minorStep: 2 }
  }, [pixelsPerSecond])

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
    </Box>
  )
}

/**
 * Sticky Track Header Column for an individual track.
 * Supports inline rename, mute, solo, lock, visibility, reordering up/down, and deletion.
 */
function TimelineTrackHeader({
  track,
  clipCount,
  trackIndex,
  totalTracks,
  onToggleState,
  onRenameTrack,
  onDeleteTrack,
  onReorderTrack,
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [nameVal, setNameVal] = useState(track.name || track.id)

  useEffect(() => {
    setNameVal(track.name || track.id)
  }, [track.name, track.id])

  const handleSaveName = () => {
    setIsEditing(false)
    const trimmed = nameVal.trim()
    if (trimmed && trimmed !== (track.name || track.id)) {
      if (onRenameTrack) onRenameTrack(track.id, trimmed)
    } else {
      setNameVal(track.name || track.id)
    }
  }

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
  const isSolo = track.solo === true
  const isCollapsed = track.collapsed === true
  const isBaseTrack = track.id === "track_video_main"

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
      {/* Left section: expand chevron, type icon, editable name & clip count */}
      <Stack direction="row" spacing={0.5} alignItems="center" sx={{ minWidth: 0, flex: 1, mr: 0.5 }}>
        <IconButton
          size="small"
          onClick={() => onToggleState(track.id, { collapsed: !isCollapsed })}
          sx={{ width: 16, height: 16, p: 0, color: "text.secondary", flexShrink: 0 }}
        >
          {isCollapsed ? <IconChevronRight size={13} /> : <IconChevronDown size={13} />}
        </IconButton>

        <IconComp size={15} color="#64748b" style={{ flexShrink: 0 }} />

        {isEditing ? (
          <InputBase
            autoFocus
            value={nameVal}
            onChange={(e) => setNameVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSaveName()
              if (e.key === "Escape") {
                setIsEditing(false)
                setNameVal(track.name || track.id)
              }
            }}
            onBlur={handleSaveName}
            sx={{
              fontSize: "0.72rem",
              fontWeight: 700,
              p: 0,
              m: 0,
              width: "100%",
              "& input": { p: 0, height: 18 },
            }}
          />
        ) : (
          <Typography
            variant="caption"
            onDoubleClick={() => !isLocked && setIsEditing(true)}
            title="Double-click to rename"
            sx={{
              fontWeight: 700,
              fontSize: "0.72rem",
              color: "text.primary",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              cursor: isLocked ? "default" : "text",
            }}
          >
            {track.name || track.id}
          </Typography>
        )}

        <Chip
          label={clipCount}
          size="small"
          sx={{
            height: 15,
            fontSize: "0.58rem",
            fontWeight: 700,
            bgcolor: "#e2e8f0",
            color: "#475569",
            px: 0.2,
            flexShrink: 0,
          }}
        />
      </Stack>

      {/* Right section: Track actions (Solo, Mute, Lock, Visibility, Reorder, Delete) */}
      <Stack direction="row" spacing={0.25} alignItems="center" sx={{ flexShrink: 0 }}>
        {/* Solo (S) */}
        {(isAudio || isVideo) && (
          <Tooltip title={isSolo ? "Unsolo Track" : "Solo Track"} arrow>
            <IconButton
              size="small"
              onClick={() => onToggleState(track.id, { solo: !isSolo })}
              sx={{
                width: 17,
                height: 17,
                p: 0,
                fontSize: "0.58rem",
                fontWeight: 800,
                color: isSolo ? "#ffffff" : "text.secondary",
                bgcolor: isSolo ? "primary.main" : "transparent",
                border: "1px solid",
                borderColor: isSolo ? "primary.main" : "divider",
                "&:hover": { bgcolor: isSolo ? "primary.dark" : "rgba(0,0,0,0.05)" },
              }}
            >
              S
            </IconButton>
          </Tooltip>
        )}

        {/* Mute (M) */}
        {(isAudio || isVideo) && (
          <Tooltip title={isMuted ? "Unmute Track" : "Mute Track"} arrow>
            <IconButton
              size="small"
              onClick={() => onToggleState(track.id, { muted: !isMuted })}
              sx={{
                width: 17,
                height: 17,
                p: 0,
                fontSize: "0.58rem",
                fontWeight: 800,
                color: isMuted ? "#ffffff" : "text.secondary",
                bgcolor: isMuted ? "error.main" : "transparent",
                border: "1px solid",
                borderColor: isMuted ? "error.main" : "divider",
                "&:hover": { bgcolor: isMuted ? "error.dark" : "rgba(0,0,0,0.05)" },
              }}
            >
              M
            </IconButton>
          </Tooltip>
        )}

        {/* Lock */}
        <Tooltip title={isLocked ? "Unlock Track" : "Lock Track"} arrow>
          <IconButton
            size="small"
            onClick={() => onToggleState(track.id, { locked: !isLocked })}
            sx={{ width: 17, height: 17, p: 0, color: isLocked ? "warning.main" : "text.secondary" }}
          >
            {isLocked ? <IconLock size={12} /> : <IconLockOpen size={12} />}
          </IconButton>
        </Tooltip>

        {/* Visibility */}
        <Tooltip title={isVisible ? "Hide Track" : "Show Track"} arrow>
          <IconButton
            size="small"
            onClick={() => onToggleState(track.id, { visible: !isVisible })}
            sx={{ width: 17, height: 17, p: 0, color: isVisible ? "text.secondary" : "text.disabled" }}
          >
            {isVisible ? <IconEye size={12} /> : <IconEyeOff size={12} />}
          </IconButton>
        </Tooltip>

        {/* Reorder Up */}
        {trackIndex > 0 && onReorderTrack && (
          <Tooltip title="Move Track Up" arrow>
            <IconButton
              size="small"
              onClick={() => onReorderTrack(track.id, -1)}
              sx={{ width: 15, height: 15, p: 0, color: "text.secondary" }}
            >
              <IconArrowUp size={11} />
            </IconButton>
          </Tooltip>
        )}

        {/* Reorder Down */}
        {trackIndex < totalTracks - 1 && onReorderTrack && (
          <Tooltip title="Move Track Down" arrow>
            <IconButton
              size="small"
              onClick={() => onReorderTrack(track.id, 1)}
              sx={{ width: 15, height: 15, p: 0, color: "text.secondary" }}
            >
              <IconArrowDown size={11} />
            </IconButton>
          </Tooltip>
        )}

        {/* Delete Track */}
        {onDeleteTrack && (
          <Tooltip title={isBaseTrack ? "Base video track cannot be deleted" : "Delete Track"} arrow>
            <span>
              <IconButton
                size="small"
                disabled={isBaseTrack || isLocked}
                onClick={() => onDeleteTrack(track.id)}
                sx={{
                  width: 16,
                  height: 16,
                  p: 0,
                  color: isBaseTrack ? "text.disabled" : "error.light",
                  "&:hover": { color: "error.main" },
                }}
              >
                <IconTrash size={12} />
              </IconButton>
            </span>
          </Tooltip>
        )}
      </Stack>
    </Box>
  )
}

/**
 * Keyframe Diamond Glyph Strip rendered directly over clip card
 */
function TimelineClipDiamonds({
  clip,
  clipDuration,
  currentTime,
  onSelectKeyframe,
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
        height: 10,
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
                width: 6,
                height: 6,
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
 * Dedicated, ruler-aligned Property Subtrack Row rendered underneath the parent track.
 * Extracted from clip card so properties span the full timeline width with full accuracy.
 */
function TimelinePropertySubtrackRow({
  propertyDef,
  clip,
  contentWidth,
  pixelsPerSecond,
  currentTime,
  onAddKeyframe,
  onRemoveKeyframe,
  onSelectKeyframe,
}) {
  const clipStart = Number(clip.start_seconds || 0)
  const clipDur = Number(clip.duration_seconds || 5)
  const clipEnd = clipStart + clipDur
  const animList = (clip.animations || []).filter((a) => a.property === propertyDef.key)
  const relTime = Math.max(0, Math.min(clipDur, Number((currentTime - clipStart).toFixed(2))))
  const activeKf = animList.find((a) => Math.abs(Number(a.time) - relTime) < 0.05)
  const displayValue = activeKf ? activeKf.value : propertyDef.default

  return (
    <Box
      sx={{
        display: "flex",
        minHeight: PROPERTY_LANE_HEIGHT,
        height: PROPERTY_LANE_HEIGHT,
        borderBottom: "1px dashed rgba(226, 232, 240, 0.9)",
        bgcolor: "#f8fafc",
      }}
    >
      {/* Sticky Left Subtrack Header */}
      <Box
        sx={{
          width: HEADER_WIDTH,
          minWidth: HEADER_WIDTH,
          height: "100%",
          bgcolor: "#f1f5f9",
          borderRight: "1px solid",
          borderColor: "divider",
          pl: 3.5,
          pr: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxSizing: "border-box",
          position: "sticky",
          left: 0,
          zIndex: 11,
        }}
      >
        <Stack direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0 }}>
          <Typography
            variant="caption"
            sx={{
              fontSize: "0.68rem",
              fontWeight: 600,
              color: "#475569",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            ↳ {propertyDef.label}
          </Typography>
          <Typography variant="caption" sx={{ fontSize: "0.62rem", color: "#6366f1", fontFamily: "monospace" }}>
            {displayValue}
          </Typography>
        </Stack>

        <Tooltip title={activeKf ? `Remove keyframe at ${relTime.toFixed(2)}s` : `Add keyframe at playhead (${relTime.toFixed(2)}s)`} arrow>
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation()
              if (activeKf) {
                if (onRemoveKeyframe) onRemoveKeyframe(clip.id, propertyDef.key, activeKf.time)
              } else {
                if (onAddKeyframe) {
                  onAddKeyframe(clip.id, {
                    property: propertyDef.key,
                    time: relTime,
                    value: propertyDef.default,
                    ease: "power2.out",
                  })
                }
              }
            }}
            sx={{
              width: 18,
              height: 18,
              p: 0,
              color: activeKf ? "#facc15" : "#94a3b8",
              bgcolor: activeKf ? "rgba(250, 204, 21, 0.2)" : "transparent",
              "&:hover": { color: "#eab308" },
            }}
          >
            <IconDiamond size={12} stroke={2} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Full-width Timeline Canvas Lane */}
      <Box
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const clickTime = (e.clientX - rect.left) / pixelsPerSecond
          if (clickTime >= clipStart && clickTime <= clipEnd) {
            const kfTime = Number((clickTime - clipStart).toFixed(2))
            if (onAddKeyframe) {
              onAddKeyframe(clip.id, {
                property: propertyDef.key,
                time: kfTime,
                value: propertyDef.default,
                ease: "power2.out",
              })
            }
          }
        }}
        sx={{
          width: `${contentWidth}px`,
          position: "relative",
          bgcolor: "#faf5ff",
          height: "100%",
        }}
      >
        {/* Clip range boundary indicator */}
        <Box
          sx={{
            position: "absolute",
            left: `${clipStart * pixelsPerSecond}px`,
            width: `${clipDur * pixelsPerSecond}px`,
            top: 0,
            bottom: 0,
            bgcolor: "rgba(168, 85, 247, 0.08)",
            borderLeft: "1px dashed rgba(168, 85, 247, 0.4)",
            borderRight: "1px dashed rgba(168, 85, 247, 0.4)",
            pointerEvents: "none",
          }}
        />

        {/* Keyframe Diamond Markers */}
        {animList.map((anim, idx) => {
          const animTime = Number(anim.time || 0)
          const absTime = clipStart + animTime
          const leftPx = absTime * pixelsPerSecond
          const isAtPlayhead = Math.abs(currentTime - absTime) < 0.08

          return (
            <Tooltip
              key={`${anim.property}_${animTime}_${idx}`}
              title={`${propertyDef.label}: ${anim.value} at ${animTime.toFixed(2)}s (${anim.ease || "none"})`}
              arrow
            >
              <Box
                data-keyframe-diamond={propertyDef.key}
                onClick={(e) => {
                  e.stopPropagation()
                  if (onSelectKeyframe) onSelectKeyframe(anim)
                }}
                sx={{
                  position: "absolute",
                  left: `${leftPx}px`,
                  top: "50%",
                  transform: "translate(-50%, -50%) rotate(45deg)",
                  width: 9,
                  height: 9,
                  bgcolor: isAtPlayhead ? "#facc15" : "#9333ea",
                  border: "1.5px solid #ffffff",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                  cursor: "pointer",
                  zIndex: 10,
                  "&:hover": {
                    transform: "translate(-50%, -50%) rotate(45deg) scale(1.3)",
                    bgcolor: "#facc15",
                  },
                }}
              />
            </Tooltip>
          )
        })}
      </Box>
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
  onRippleDeleteClip,
  onSlipClip,
  onSpeedChangeClip,
  onUpdateClipTiming,
  onDuplicateClip,
  onSplitClip,
  onAddKeyframe,
  onUpdateKeyframe,
  onRemoveKeyframe,
  onToggleTrackState,
  onAddTrack,
  onDeleteTrack,
  onReorderTracks,
  onRenameTrack,
  onMoveClip,
  onDropExternalClip,
  onDropRejected = null,
}) {
  const containerRef = useRef(null)
  const [zoom, setZoom] = useState(1.0)
  const [snap, setSnap] = useState(true)
  const [expandedLanes, setExpandedLanes] = useState(new Set())
  const [contextMenu, setContextMenu] = useState(null)
  const [snapGuideTime, setSnapGuideTime] = useState(null)

  // Add Track menu anchor
  const [addTrackAnchorEl, setAddTrackAnchorEl] = useState(null)

  // Delete Track Confirmation Dialog
  const [deleteTrackCandidate, setDeleteTrackCandidate] = useState(null)

  // Drag / Trim State
  // { mode: 'move'|'trim-left'|'trim-right', clipId, sourceTrackId, clip, startX, startY, origStart, origDur, origTrimStart, currentStart, currentDur, currentTrimStart, hoverTrackId }
  const [dragState, setDragState] = useState(null)

  // External Native Drag & Drop State (from Resources: Assets, Sources, Catalog)
  // { hoverTrackId: string, dropTime: number, isValid: boolean, title: string, duration: number, item: any }
  const [externalDrag, setExternalDrag] = useState(null)

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

  const snapValue = useCallback((candidateTime, targets, pxPerSec) => {
    const thresholdSec = 8 / pxPerSec
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
    const frameDur = 1 / fps
    const nearestFrame = Math.round(candidateTime / frameDur) * frameDur
    if (Math.abs(nearestFrame - candidateTime) < thresholdSec * 0.6) {
      return { time: Number(nearestFrame.toFixed(3)), target: { time: nearestFrame, type: "frame" } }
    }
    return { time: candidateTime, target: null }
  }, [fps])

  // External item compatibility checker for destination track
  const isExternalItemValidForTrack = useCallback((item, track) => {
    if (!track || track.locked) return false
    // Validate rights and permitted uses contract
    if (item?.permitted_uses && Array.isArray(item.permitted_uses)) {
      if (!item.permitted_uses.includes("timeline_motion")) {
        return false
      }
    }
    const destType = (track.type || "video").toLowerCase()
    const blockData = item?.data || item?.item || item
    const rawMediaType = (item?.media_type || item?.mediaType || item?.kind || blockData?.type || "").toLowerCase()

    const category = (blockData?.category || item?.category || "").toLowerCase()
    const tags = Array.isArray(blockData?.tags) ? blockData.tags.map((t) => String(t).toLowerCase()) : []
    const isBlock = rawMediaType === "block" || item?.kind === "catalog" || item?.type === "block"

    // Captions / Typography
    const isCaptionBlock = isBlock && (
      category === "text-captions" ||
      category === "captions" ||
      category === "typography" ||
      tags.includes("captions") ||
      tags.includes("caption-style") ||
      tags.includes("typography")
    )
    const isCaption = rawMediaType === "caption" || rawMediaType === "captions" || isCaptionBlock

    // Audio
    const isAudioBlock = isBlock && (category === "audio" || category === "music" || tags.includes("audio") || tags.includes("music"))
    const isAudio = rawMediaType === "audio" || isAudioBlock || item?.data?.media === "audio" ||
      (item?.data?.ext && ["mp3", "wav", "aac", "ogg"].includes(item.data.ext.toLowerCase())) ||
      item?.data?.source === "music"

    // Transitions
    const isTransition = (isBlock && (category === "transitions" || tags.includes("transition") || tags.includes("transitions"))) || rawMediaType === "transition"

    if (isAudio) {
      return destType === "audio"
    }
    if (destType === "audio") {
      return isAudio
    }
    if (isCaption) {
      return destType === "captions" || destType === "text"
    }
    if (destType === "captions" || destType === "text") {
      return isCaption
    }
    if (isTransition) {
      return destType === "transition" || destType === "transitions"
    }
    if (destType === "transition" || destType === "transitions") {
      return isTransition
    }

    if (isBlock) {
      return ["video", "media", "graphics", "components"].includes(destType)
    }

    return ["video", "media", "image"].includes(destType)
  }, [])

  // Window listeners for Escape cancellation and dragend cleanup
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        if (externalDrag) {
          setExternalDrag(null)
          setSnapGuideTime(null)
        }
        if (dragState) {
          setDragState(null)
          setSnapGuideTime(null)
        }
      }
    }
    const handleDragEnd = () => {
      setExternalDrag(null)
      setSnapGuideTime(null)
    }
    window.addEventListener("keydown", handleKeyDown)
    window.addEventListener("dragend", handleDragEnd)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("dragend", handleDragEnd)
    }
  }, [externalDrag, dragState])

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
          const startSnap = snapValue(rawStart, snapTargets, pixelsPerSecond)
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

        // Identify hover track under cursor
        const elem = document.elementFromPoint(e.clientX, e.clientY)
        const laneEl = elem?.closest("[data-track-lane-id]")
        const hoverTid = laneEl?.dataset?.trackLaneId || dragState.sourceTrackId

        setDragState((prev) => prev ? {
          ...prev,
          currentStart: Math.max(0, Number(snapped.toFixed(2))),
          hoverTrackId: hoverTid,
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
      if (dragState) {
        const finalStart = dragState.currentStart != null ? dragState.currentStart : dragState.origStart
        const finalDur = dragState.currentDur != null ? dragState.currentDur : dragState.origDur

        if (dragState.mode === "move") {
          const targetTrack = tracks.find((t) => t.id === dragState.hoverTrackId)
          const isDiffTrack = targetTrack && targetTrack.id !== dragState.sourceTrackId
          const valid = isDropTargetValid(dragState.clip, targetTrack)

          if (isDiffTrack && valid && onMoveClip) {
            onMoveClip(dragState.clipId, targetTrack.id, finalStart)
          } else if (onUpdateClipTiming) {
            const patch = {}
            if (finalStart !== dragState.origStart) patch.start_seconds = finalStart
            if (Object.keys(patch).length > 0) {
              onUpdateClipTiming(dragState.clipId, patch)
            }
          }
        } else if (onUpdateClipTiming) {
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
      }
      setDragState(null)
    }

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [dragState, pixelsPerSecond, snap, snapTargets, snapValue, onUpdateClipTiming, onMoveClip, tracks])

  // Keyboard Shortcuts: Space (Play/Pause), Delete (Remove), Ctrl+D (Duplicate), S (Split)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return

      if (e.code === "Space") {
        e.preventDefault()
        if (onTogglePlay) onTogglePlay()
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedElementId) {
          const sel = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
          if (sel) {
            if (e.shiftKey && onRippleDeleteClip) {
              e.preventDefault()
              onRippleDeleteClip(sel)
            } else if (onDeleteClip) {
              onDeleteClip(sel)
            }
          }
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") {
        e.preventDefault()
        if (selectedElementId) {
          const sel = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
          if (sel && onDuplicateClip) onDuplicateClip(sel)
        }
      } else if (e.key.toLowerCase() === "s" && !e.ctrlKey && !e.metaKey) {
        if (selectedElementId) {
          const sel = tracks.flatMap((t) => t.clips || []).find((c) => c.id === selectedElementId)
          if (sel && onSplitClip) onSplitClip(sel, currentTime)
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [selectedElementId, tracks, currentTime, onTogglePlay, onDeleteClip, onRippleDeleteClip, onDuplicateClip, onSplitClip])

  // Context Menu handlers
  const handleContextMenu = (e, clip) => {
    e.preventDefault()
    e.stopPropagation()
    setContextMenu({ mouseX: e.clientX, mouseY: e.clientY, clip })
  }

  const handleCloseContextMenu = () => {
    setContextMenu(null)
  }

  // Track reordering helper
  const handleReorderTrackByIndex = (trackId, direction) => {
    const idx = tracks.findIndex((t) => t.id === trackId)
    if (idx === -1) return
    const targetIdx = idx + direction
    if (targetIdx < 0 || targetIdx >= tracks.length) return
    const newTrackIds = tracks.map((t) => t.id)
    const temp = newTrackIds[idx]
    newTrackIds[idx] = newTrackIds[targetIdx]
    newTrackIds[targetIdx] = temp
    if (onReorderTracks) onReorderTracks(newTrackIds)
  }

  // Delete track prompt
  const handleDeleteTrackRequested = (trackId) => {
    const target = tracks.find((t) => t.id === trackId)
    if (!target) return
    const clips = target.clips || []
    if (clips.length > 0) {
      setDeleteTrackCandidate(target)
    } else {
      if (onDeleteTrack) onDeleteTrack(trackId, false)
    }
  }

  const handleConfirmDeleteTrack = () => {
    if (deleteTrackCandidate && onDeleteTrack) {
      onDeleteTrack(deleteTrackCandidate.id, true)
    }
    setDeleteTrackCandidate(null)
  }

  return (
    <Box
      data-testid="studio-timeline-workspace"
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
          {/* Timeline Title: strictly "Timeline" per product requirements */}
          <Typography variant="caption" sx={{ fontWeight: 800, fontSize: "0.75rem", color: "#334155" }}>
            Timeline
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

          {/* Add Track Action Button */}
          {onAddTrack && (
            <Tooltip title="Add Track" arrow>
              <Button
                size="small"
                startIcon={<IconPlus size={13} />}
                onClick={(e) => setAddTrackAnchorEl(e.currentTarget)}
                sx={{
                  height: 24,
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  px: 1,
                  py: 0,
                  bgcolor: "#ffffff",
                  color: "#475569",
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 1,
                  "&:hover": { bgcolor: "#f1f5f9" },
                }}
              >
                Add Track
              </Button>
            </Tooltip>
          )}

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
              justifyContent: "space-between",
              position: "sticky",
              left: 0,
              zIndex: 35,
            }}
          >
            <Typography variant="caption" sx={{ fontSize: "0.65rem", fontWeight: 800, color: "text.secondary", textTransform: "uppercase" }}>
              Tracks ({tracks.length})
            </Typography>
            {onAddTrack && (
              <Tooltip title="Add Track" arrow>
                <IconButton
                  size="small"
                  onClick={(e) => setAddTrackAnchorEl(e.currentTarget)}
                  sx={{ width: 18, height: 18, p: 0, color: "primary.main" }}
                >
                  <IconPlus size={13} />
                </IconButton>
              </Tooltip>
            )}
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
            tracks.map((track, trackIndex) => {
              const isCollapsed = track.collapsed === true
              const isVisible = track.visible !== false
              const isLocked = track.locked === true
              const isMuted = track.muted === true
              const clips = track.clips || []

              // Check if currently dragging a clip over this track
              const isDragHover = dragState?.mode === "move" && dragState.hoverTrackId === track.id
              const isDragSource = dragState?.sourceTrackId === track.id
              const isTargetValid = isDragHover ? isDropTargetValid(dragState?.clip, track) : true

              // External drag hover and validity
              const isExtHover = externalDrag?.hoverTrackId === track.id
              const isExtValid = externalDrag ? externalDrag.isValid : true

              // Clips on this track with expanded animation lanes
              const expandedClips = isCollapsed ? [] : clips.filter((c) => expandedLanes.has(c.id))

              return (
                <Box key={track.id} sx={{ display: "flex", flexDirection: "column" }}>
                  {/* Main Track Row */}
                  <Box
                    sx={{
                      display: "flex",
                      minHeight: isCollapsed ? TRACK_COLLAPSED_HEIGHT : TRACK_NORMAL_HEIGHT,
                      height: isCollapsed ? TRACK_COLLAPSED_HEIGHT : TRACK_NORMAL_HEIGHT,
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
                        trackIndex={trackIndex}
                        totalTracks={tracks.length}
                        onToggleState={onToggleTrackState || (() => {})}
                        onRenameTrack={onRenameTrack}
                        onDeleteTrack={handleDeleteTrackRequested}
                        onReorderTrack={handleReorderTrackByIndex}
                      />
                    </Box>

                    {/* Track Clips Canvas Lane */}
                    <Box
                      data-track-lane-id={track.id}
                      data-track-id={track.id}
                      onDragOver={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        e.dataTransfer.dropEffect = "copy"

                        const rect = e.currentTarget.getBoundingClientRect()
                        const offsetX = e.clientX - rect.left
                        let rawTime = Math.max(0, offsetX / pixelsPerSecond)
                        let snappedTime = rawTime
                        let guide = null
                        if (snap) {
                          const s = snapValue(rawTime, snapTargets, pixelsPerSecond)
                          if (s.target) {
                            snappedTime = s.time
                            guide = s.time
                          }
                        }
                        setSnapGuideTime(guide)

                        let itemData = externalDrag?.item || null
                        if (!itemData) {
                          try {
                            const raw6Clips = e.dataTransfer.getData("application/x-6clips-asset")
                            if (raw6Clips) {
                              itemData = JSON.parse(raw6Clips)
                            } else {
                              const raw = e.dataTransfer.getData("application/viralmint-clip") || e.dataTransfer.getData("application/json")
                              if (raw) itemData = JSON.parse(raw)
                            }
                          } catch {}
                        }

                        const valid = !track.locked && (itemData ? isExternalItemValidForTrack(itemData, track) : true)

                        setExternalDrag((prev) => ({
                          hoverTrackId: track.id,
                          dropTime: Number(snappedTime.toFixed(2)),
                          isValid: valid,
                          title: itemData?.title || prev?.title || "New Clip",
                          duration: itemData?.duration_seconds || itemData?.duration || prev?.duration || 3.0,
                          item: itemData || prev?.item,
                        }))
                      }}
                      onDragLeave={(e) => {
                        const related = e.relatedTarget
                        if (!e.currentTarget.contains(related)) {
                          if (externalDrag?.hoverTrackId === track.id) {
                            setExternalDrag(null)
                            setSnapGuideTime(null)
                          }
                        }
                      }}
                      onDrop={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setSnapGuideTime(null)

                        let itemData = externalDrag?.item || null
                        if (!itemData) {
                          try {
                            const raw6Clips = e.dataTransfer.getData("application/x-6clips-asset")
                            if (raw6Clips) {
                              itemData = JSON.parse(raw6Clips)
                            } else {
                              const raw = e.dataTransfer.getData("application/viralmint-clip") || e.dataTransfer.getData("application/json")
                              if (raw) itemData = JSON.parse(raw)
                            }
                          } catch {}
                        }

                        const droppedItem = itemData || externalDrag?.item
                        const targetDropTime = externalDrag?.dropTime != null
                          ? externalDrag.dropTime
                          : (droppedItem?.target_start_time_seconds != null ? droppedItem.target_start_time_seconds : 0.0)

                        setExternalDrag(null)

                        if (!droppedItem) return
                        if (track.locked) return
                        if (!isExternalItemValidForTrack(droppedItem, track)) {
                          if (onDropRejected) {
                            onDropRejected({
                              item: droppedItem,
                              track,
                              reason: track.locked ? "TRACK_LOCKED" : "INCOMPATIBLE_TRACK",
                            })
                          }
                          return
                        }

                        if (onDropExternalClip) {
                          onDropExternalClip({
                            item: droppedItem,
                            targetTrackId: track.id,
                            startSeconds: targetDropTime,
                          })
                        }
                      }}
                      sx={{
                        width: `${contentWidth}px`,
                        position: "relative",
                        bgcolor: isCollapsed
                          ? "#f8fafc"
                          : isExtHover
                          ? isExtValid
                            ? "rgba(139, 92, 246, 0.08)"
                            : "rgba(239, 68, 68, 0.08)"
                          : isDragHover && !isDragSource
                          ? isTargetValid
                            ? "rgba(139, 92, 246, 0.06)"
                            : "rgba(239, 68, 68, 0.06)"
                          : "#ffffff",
                        border: isExtHover
                          ? isExtValid
                            ? "2px dashed #8b5cf6"
                            : "2px dashed #ef4444"
                          : isDragHover && !isDragSource
                          ? isTargetValid
                            ? "2px dashed #8b5cf6"
                            : "2px dashed #ef4444"
                          : "none",
                        overflow: "hidden",
                        transition: "background-color 0.1s ease",
                      }}
                    >
                      {/* External Drag Placement Ghost Indicator */}
                      {isExtHover && (
                        <Box
                          data-testid="external-drag-ghost"
                          sx={{
                            position: "absolute",
                            left: `${(externalDrag?.dropTime || 0) * pixelsPerSecond}px`,
                            width: `${Math.max(36, (externalDrag?.duration || 3) * pixelsPerSecond)}px`,
                            top: 4,
                            bottom: 4,
                            borderRadius: 1,
                            bgcolor: isExtValid ? "rgba(139, 92, 246, 0.22)" : "rgba(239, 68, 68, 0.22)",
                            border: isExtValid ? "2px dashed #8b5cf6" : "2px dashed #ef4444",
                            zIndex: 25,
                            pointerEvents: "none",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            px: 1,
                            boxShadow: isExtValid ? "0 0 10px rgba(139, 92, 246, 0.3)" : "none",
                          }}
                        >
                          <Typography
                            sx={{
                              fontSize: "0.68rem",
                              fontWeight: 800,
                              color: isExtValid ? "#5b21b6" : "#991b1b",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {externalDrag?.title || "Drop Clip"}
                          </Typography>
                          <Chip
                            size="small"
                            label={`${(externalDrag?.dropTime || 0).toFixed(2)}s`}
                            sx={{
                              height: 16,
                              fontSize: "0.58rem",
                              fontWeight: 700,
                              bgcolor: isExtValid ? "#7c3aed" : "#dc2626",
                              color: "#ffffff",
                            }}
                          />
                        </Box>
                      )}
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

                        const isVideo = track.type === "video" || clip.type === "video"
                        const isAudio = track.type === "audio" || clip.type === "audio"
                        const isBlock = clip.type === "block" || !!clip.block_id
                        const isCaption = track.type === "captions" || !!clip.caption_text
                        const isImage = track.type === "image" || clip.type === "image"

                        let bgGradient = isSelected
                          ? "linear-gradient(135deg, #7c3aed 0%, #6366f1 100%)"
                          : "linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)"

                        if (isAudio) {
                          bgGradient = isSelected
                            ? "linear-gradient(135deg, #059669 0%, #10b981 100%)"
                            : "linear-gradient(135deg, #047857 0%, #065f46 100%)"
                        } else if (isBlock) {
                          bgGradient = isSelected
                            ? "linear-gradient(135deg, #c026d3 0%, #9333ea 100%)"
                            : "linear-gradient(135deg, #a21caf 0%, #7e22ce 100%)"
                        } else if (isCaption) {
                          bgGradient = isSelected
                            ? "linear-gradient(135deg, #d97706 0%, #b45309 100%)"
                            : "linear-gradient(135deg, #b45309 0%, #92400e 100%)"
                        } else if (isImage) {
                          bgGradient = isSelected
                            ? "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)"
                            : "linear-gradient(135deg, #0369a1 0%, #075985 100%)"
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
                                sourceTrackId: track.id,
                                clip: clip,
                                mode: "move",
                                startX: e.clientX,
                                startY: e.clientY,
                                origStart: Number(clip.start_seconds || 0),
                                origDur: Number(clip.duration_seconds || 5),
                                origTrimStart: Number(clip.trim_start || 0),
                                currentStart: Number(clip.start_seconds || 0),
                                currentDur: Number(clip.duration_seconds || 5),
                                currentTrimStart: Number(clip.trim_start || 0),
                                hoverTrackId: track.id,
                              })
                            }}
                            sx={{
                              position: "absolute",
                              left: `${leftPx}px`,
                              width: `${widthPx}px`,
                              top: 4,
                              height: TRACK_NORMAL_HEIGHT - 8,
                              background: bgGradient,
                              color: "#ffffff",
                              borderRadius: 1.5,
                              p: 0.75,
                              cursor: isLocked ? "not-allowed" : (isDraggingThis ? "grabbing" : "grab"),
                              boxShadow: isSelected ? "0 0 0 2px #c4b5fd, 0 4px 6px -1px rgba(0,0,0,0.15)" : "0 1px 3px rgba(0,0,0,0.1)",
                              opacity: isDraggingThis ? 0.9 : 1,
                              overflow: "hidden",
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
                                    sourceTrackId: track.id,
                                    clip: clip,
                                    mode: "trim-left",
                                    startX: e.clientX,
                                    startY: e.clientY,
                                    origStart: Number(clip.start_seconds || 0),
                                    origDur: Number(clip.duration_seconds || 5),
                                    origTrimStart: Number(clip.trim_start || 0),
                                    currentStart: Number(clip.start_seconds || 0),
                                    currentDur: Number(clip.duration_seconds || 5),
                                    currentTrimStart: Number(clip.trim_start || 0),
                                    hoverTrackId: track.id,
                                  })
                                }}
                                sx={{
                                  position: "absolute",
                                  left: 0,
                                  top: 0,
                                  bottom: 0,
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

                            {/* Bottom Row: In/Out Duration indicator + Keyframe Diamonds Toggle */}
                            <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ zIndex: 4 }}>
                              <Typography variant="caption" sx={{ fontSize: "0.58rem", opacity: 0.85, fontFamily: "monospace" }}>
                                {clipDur.toFixed(1)}s
                              </Typography>

                              {/* Keyframe Subtracks toggle button */}
                              <Tooltip title={lanesOpen ? "Hide Animation Subtracks" : "Expand Animation Subtracks"} arrow>
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

                            {/* Keyframe Diamonds on Clip Card */}
                            <TimelineClipDiamonds
                              clip={clip}
                              clipDuration={clipDur}
                              currentTime={currentTime}
                              onSelectKeyframe={() => {
                                if (onSelectElement) onSelectElement(clip)
                              }}
                            />

                            {/* Right Trim Handle */}
                            {!isLocked && (
                              <Box
                                data-handle="trim-right"
                                onMouseDown={(e) => {
                                  e.stopPropagation()
                                  setDragState({
                                    clipId: clip.id,
                                    sourceTrackId: track.id,
                                    clip: clip,
                                    mode: "trim-right",
                                    startX: e.clientX,
                                    startY: e.clientY,
                                    origStart: Number(clip.start_seconds || 0),
                                    origDur: Number(clip.duration_seconds || 5),
                                    origTrimStart: Number(clip.trim_start || 0),
                                    currentStart: Number(clip.start_seconds || 0),
                                    currentDur: Number(clip.duration_seconds || 5),
                                    currentTrimStart: Number(clip.trim_start || 0),
                                    hoverTrackId: track.id,
                                  })
                                }}
                                sx={{
                                  position: "absolute",
                                  right: 0,
                                  top: 0,
                                  bottom: 0,
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

                  {/* Expandable Dedicated Property Subtracks (Underneath Parent Track) */}
                  {expandedClips.map((expClip) => (
                    <Box key={`subtracks_${expClip.id}`} sx={{ borderBottom: "1px solid", borderColor: "divider" }}>
                      {ANIMATABLE_PROPERTIES.map((propDef) => (
                        <TimelinePropertySubtrackRow
                          key={`${expClip.id}_${propDef.key}`}
                          propertyDef={propDef}
                          clip={expClip}
                          contentWidth={contentWidth}
                          pixelsPerSecond={pixelsPerSecond}
                          currentTime={currentTime}
                          onAddKeyframe={onAddKeyframe}
                          onRemoveKeyframe={onRemoveKeyframe}
                          onSelectKeyframe={(kf) => {
                            if (onSelectElement) onSelectElement(expClip)
                          }}
                        />
                      ))}
                    </Box>
                  ))}
                </Box>
              )
            })
          )}
        </Box>
      </Box>

      {/* 3. Add Track Dropdown Menu */}
      <Menu
        anchorEl={addTrackAnchorEl}
        open={Boolean(addTrackAnchorEl)}
        onClose={() => setAddTrackAnchorEl(null)}
      >
        <MenuItem
          onClick={() => {
            setAddTrackAnchorEl(null)
            if (onAddTrack) onAddTrack("video", "Video Track")
          }}
        >
          <ListItemIcon><IconVideo size={16} /></ListItemIcon>
          <ListItemText primary="Video Track" secondary="Clips, video overlays & cutaways" />
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAddTrackAnchorEl(null)
            if (onAddTrack) onAddTrack("audio", "Audio Track")
          }}
        >
          <ListItemIcon><IconMusic size={16} /></ListItemIcon>
          <ListItemText primary="Audio Track" secondary="Music, narration & sound effects" />
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAddTrackAnchorEl(null)
            if (onAddTrack) onAddTrack("captions", "Captions Track")
          }}
        >
          <ListItemIcon><IconTypography size={16} /></ListItemIcon>
          <ListItemText primary="Captions Track" secondary="Subtitles, lower thirds & captions" />
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAddTrackAnchorEl(null)
            if (onAddTrack) onAddTrack("graphics", "Graphics & Blocks")
          }}
        >
          <ListItemIcon><IconComponents size={16} /></ListItemIcon>
          <ListItemText primary="Graphics Track" secondary="HyperFrames interactive components" />
        </MenuItem>
      </Menu>

      {/* 4. Delete Track Confirmation Dialog */}
      <Dialog
        open={Boolean(deleteTrackCandidate)}
        onClose={() => setDeleteTrackCandidate(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <IconAlertTriangle color="#ef4444" size={20} />
          Delete Track
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Track <strong>{deleteTrackCandidate?.name}</strong> contains{" "}
            <strong>{deleteTrackCandidate?.clips?.length || 0}</strong> active clip(s).
            Deleting this track will remove all clips on it. Are you sure?
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteTrackCandidate(null)} color="inherit">
            Cancel
          </Button>
          <Button onClick={handleConfirmDeleteTrack} color="error" variant="contained">
            Delete Track
          </Button>
        </DialogActions>
      </Dialog>

      {/* 5. Context Menu on Clip */}
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
          <ListItemText primary="Toggle Animation Subtracks" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onSlipClip) onSlipClip(contextMenu.clip, -0.5)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconArrowsExchange size={16} /></ListItemIcon>
          <ListItemText primary="Slip Earlier (-0.5s)" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onSlipClip) onSlipClip(contextMenu.clip, 0.5)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconArrowsExchange size={16} /></ListItemIcon>
          <ListItemText primary="Slip Later (+0.5s)" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onSpeedChangeClip) onSpeedChangeClip(contextMenu.clip, 2.0)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconGauge size={16} /></ListItemIcon>
          <ListItemText primary="Speed: 2x (Double)" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onSpeedChangeClip) onSpeedChangeClip(contextMenu.clip, 0.5)
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconGauge size={16} /></ListItemIcon>
          <ListItemText primary="Speed: 0.5x (Slow-mo)" />
        </MenuItem>

        <MenuItem
          onClick={() => {
            if (contextMenu?.clip && onRippleDeleteClip) onRippleDeleteClip(contextMenu.clip)
            handleCloseContextMenu()
          }}
          sx={{ color: "warning.main" }}
        >
          <ListItemIcon sx={{ color: "warning.main" }}><IconTrash size={16} /></ListItemIcon>
          <ListItemText primary="Ripple Delete" secondary="Shift+Del" />
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
