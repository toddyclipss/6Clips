// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useRef, useState, useEffect, useImperativeHandle, forwardRef } from "react"
import {
  Box, Stack, Typography, IconButton, Slider, Tooltip, CircularProgress, Chip, Button,
} from "@mui/material"
import {
  IconPlayerPlay,
  IconPlayerPause,
  IconPlayerSkipBack,
  IconPlayerSkipForward,
  IconVolume,
  IconVolumeOff,
  IconMaximize,
  IconRefresh,
  IconX,
  IconSparkles,
} from "@tabler/icons-react"

/**
 * Central Stage & Video Preview using HyperFrames Player integration.
 * Respects 9:16 and 16:9 aspect ratios without distortion.
 * Uses Light theme canvas surrounding with crisp composition stage.
 * Supports temporary non-destructive Ghost Preview for HyperFrames Catalog blocks.
 */
const StudioPreviewStage = forwardRef(function StudioPreviewStage({
  previewUrl,
  aspectRatio = "9:16",
  isLoading = false,
  currentTime = 0,
  duration = 15,
  isPlaying = false,
  onTogglePlay,
  onPlaybackStateChange,
  onTimeUpdate,
  onSeek,
  onRefresh,
  onSelectElementId,
  ghostPreview = null,
  onDismissGhostPreview,
  onInsertGhostBlock,
  workspaceMode = "create",
  renderedVideo = null,
  onProceedToRefine = null,
  onDurationChange = null,
}, ref) {
  const iframeRef = useRef(null)
  const videoRef = useRef(null)
  const [muted, setMuted] = useState(false)
  const lastPostedPlayRef = useRef(null)
  const [ghostFrameLoaded, setGhostFrameLoaded] = useState(false)
  const [videoDimensions, setVideoDimensions] = useState({ width: 0, height: 0 })

  // Listen to Escape key to dismiss temporary ghost preview immediately
  useEffect(() => {
    if (!ghostPreview) {
      setGhostFrameLoaded(false)
      return
    }
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        if (onDismissGhostPreview) onDismissGhostPreview()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [ghostPreview, onDismissGhostPreview])

  const ALLOWED_OUTBOUND_ACTIONS = new Set(["play", "pause", "seek", "mute"])

  const postControl = (action, extra = {}) => {
    if (!ALLOWED_OUTBOUND_ACTIONS.has(action)) return
    try {
      if (iframeRef.current && iframeRef.current.contentWindow) {
        // Sandboxed iframe without allow-same-origin has an opaque origin ("null").
        // Outbound command targetOrigin must be "*" to reach the opaque frame window.
        iframeRef.current.contentWindow.postMessage(
          { source: "vm-parent", action, ...extra },
          "*"
        )
      }
    } catch {
      // ignore
    }
  }

  // Expose imperative methods to parent (e.g. for scrubbing from timeline)
  useImperativeHandle(ref, () => ({
    seek: (time) => {
      const validTime = typeof time === "number" && Number.isFinite(time) ? Math.max(0, time) : 0
      if (workspaceMode === "review" && videoRef.current) {
        videoRef.current.currentTime = validTime
      } else {
        postControl("seek", { time: validTime })
      }
    },
    play: () => {
      if (workspaceMode === "review" && videoRef.current) {
        videoRef.current.play().catch(() => {})
      } else {
        postControl("play")
      }
    },
    pause: () => {
      if (workspaceMode === "review" && videoRef.current) {
        videoRef.current.pause()
      } else {
        postControl("pause")
      }
    },
  }))

  // Synchronize external isPlaying state (e.g. from Timeline or Spacebar) to iframe/video runtime
  useEffect(() => {
    if (workspaceMode === "review" && videoRef.current) {
      if (isPlaying && videoRef.current.paused) {
        videoRef.current.play().catch(() => {})
      } else if (!isPlaying && !videoRef.current.paused) {
        videoRef.current.pause()
      }
    } else if (isPlaying !== lastPostedPlayRef.current) {
      lastPostedPlayRef.current = isPlaying
      postControl(isPlaying ? "play" : "pause")
    }
  }, [isPlaying, workspaceMode])

  // Listen to bidirectional playback events from composition runtime
  useEffect(() => {
    const handleRuntimeMessage = (ev) => {
      // 1. Strict sending window check: only accept messages from our exact composition iframe
      if (!iframeRef.current || !iframeRef.current.contentWindow) return
      if (ev.source !== iframeRef.current.contentWindow) return

      // 2. Sandboxed iframe with allow-scripts and without allow-same-origin evaluates to origin "null".
      // Verify origin is either "null" (opaque sandbox) or matches current window origin
      if (ev.origin !== "null" && ev.origin !== window.location.origin) return

      // 3. Message shape validation
      const data = ev.data
      if (!data || typeof data !== "object") return
      if (data.source !== "vm-runtime") return

      // 4. Runtime state playback time & paused validation
      if (typeof data.currentTime === "number") {
        if (!Number.isFinite(data.currentTime) || data.currentTime < 0) return
        const maxTime = typeof duration === "number" && Number.isFinite(duration) && duration > 0 ? duration + 60 : 3600
        if (data.currentTime > maxTime) return

        if (onTimeUpdate) {
          onTimeUpdate(data.currentTime)
        } else if (onSeek) {
          onSeek(data.currentTime)
        }
      }

      if (typeof data.paused === "boolean" && onPlaybackStateChange) {
        lastPostedPlayRef.current = !data.paused
        onPlaybackStateChange(!data.paused)
      }

      // 5. Permitted action allowlist and identifier validation
      if (data.action === "element_selected") {
        const id = data.id
        // Ensure id is a safe, non-empty string identifier (alphanumeric, dashes, underscores, colons, slashes)
        if (typeof id === "string" && id.length > 0 && id.length <= 128 && /^[a-zA-Z0-9_\-:\/.]+$/.test(id)) {
          if (onSelectElementId) onSelectElementId(id)
        }
      }
    }
    window.addEventListener("message", handleRuntimeMessage)
    return () => window.removeEventListener("message", handleRuntimeMessage)
  }, [duration, onTimeUpdate, onSeek, onPlaybackStateChange, onSelectElementId])

  const handleTogglePlay = () => {
    const nextState = !isPlaying
    lastPostedPlayRef.current = nextState
    if (workspaceMode === "review" && videoRef.current) {
      if (nextState) {
        videoRef.current.play().catch(() => {})
      } else {
        videoRef.current.pause()
      }
    } else {
      postControl(nextState ? "play" : "pause")
    }
    if (onTogglePlay) onTogglePlay()
  }

  const handleSeek = (time) => {
    const validTime = typeof time === "number" && Number.isFinite(time) ? Math.max(0, time) : 0
    if (workspaceMode === "review" && videoRef.current) {
      videoRef.current.currentTime = validTime
    } else {
      postControl("seek", { time: validTime })
    }
    if (onSeek) onSeek(validTime)
  }

  const handleToggleMute = () => {
    const nextMuted = !muted
    setMuted(nextMuted)
    if (workspaceMode === "review" && videoRef.current) {
      videoRef.current.muted = nextMuted
    } else {
      postControl("mute", { muted: nextMuted })
    }
  }

  // Aspect ratio styling
  const isPortrait = aspectRatio === "9:16"
  // For portrait 9:16, maximum height bounding; for landscape 16:9, maximum width bounding
  const stageAspectRatio = isPortrait ? 9 / 16 : 16 / 9

  return (
    <Box
      data-testid="studio-preview-stage"
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#f8fafc",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Central Viewport */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          p: 2,
          minHeight: 0,
          position: "relative",
        }}
      >
        {/* Composition Canvas Box */}
        <Box
          sx={{
            height: isPortrait ? "100%" : "auto",
            width: isPortrait ? "auto" : "100%",
            maxHeight: "100%",
            maxWidth: "100%",
            aspectRatio: `${stageAspectRatio}`,
            bgcolor: "#000000",
            borderRadius: 2,
            boxShadow: "0 8px 30px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
            overflow: "hidden",
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {workspaceMode === "review" && renderedVideo?.video_url ? (
            <>
              <video
                id="studio-rendered-video"
                data-testid="studio-rendered-video"
                ref={videoRef}
                src={renderedVideo.video_url}
                playsInline
                preload="auto"
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                  display: "block",
                  backgroundColor: "#000000",
                }}
                onLoadedMetadata={(e) => {
                  setVideoDimensions({ width: e.target.videoWidth, height: e.target.videoHeight })
                  if (e.target.duration && onDurationChange) onDurationChange(e.target.duration)
                }}
                onTimeUpdate={(e) => {
                  if (onTimeUpdate) onTimeUpdate(e.target.currentTime)
                }}
                onPlay={() => {
                  lastPostedPlayRef.current = true
                  if (onPlaybackStateChange) onPlaybackStateChange(true)
                }}
                onPause={() => {
                  lastPostedPlayRef.current = false
                  if (onPlaybackStateChange) onPlaybackStateChange(false)
                }}
                onEnded={() => {
                  lastPostedPlayRef.current = false
                  if (onPlaybackStateChange) onPlaybackStateChange(false)
                }}
              />
              <Box
                data-testid="studio-review-header"
                sx={{
                  position: "absolute",
                  top: 12,
                  left: 14,
                  right: 14,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  zIndex: 6,
                  pointerEvents: "none",
                }}
              >
                <Stack direction="row" spacing={0.8} alignItems="center" sx={{ bgcolor: "rgba(15,23,42,0.85)", px: 1.2, py: 0.4, borderRadius: 1.5, backdropFilter: "blur(4px)", pointerEvents: "auto" }}>
                  <Chip label={`Render: Rev ${renderedVideo.project_revision || 5}`} color="success" size="small" sx={{ height: 20, fontSize: "0.68rem", fontWeight: 700 }} />
                  <Typography variant="caption" sx={{ color: "#e2e8f0", fontFamily: "monospace", fontSize: "0.72rem" }}>
                    {videoDimensions.width ? `${videoDimensions.width}×${videoDimensions.height}` : "1080×1920"} • {Number(duration || 14.88).toFixed(2)}s
                  </Typography>
                </Stack>
                {onProceedToRefine && (
                  <Button
                    data-testid="proceed-to-refine-btn"
                    variant="contained"
                    size="small"
                    onClick={onProceedToRefine}
                    sx={{
                      pointerEvents: "auto",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      textTransform: "none",
                      bgcolor: "primary.main",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
                    }}
                  >
                    Proceed to Refine →
                  </Button>
                )}
              </Box>
            </>
          ) : previewUrl ? (
            <iframe
              id="studio-preview-iframe"
              ref={iframeRef}
              src={previewUrl}
              title="Composition Stage"
              allow="autoplay"
              sandbox="allow-scripts allow-same-origin"
              style={{
                width: "100%",
                height: "100%",
                border: 0,
                display: "block",
                backgroundColor: "#0b0f19",
              }}
            />
          ) : isLoading ? (
            <Stack alignItems="center" spacing={1} sx={{ color: "#94a3b8" }}>
              <CircularProgress size={24} color="inherit" />
              <Typography variant="caption">Loading composition…</Typography>
            </Stack>
          ) : (
            <Box
              sx={{
                width: "100%",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "#475569",
                userSelect: "none",
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: "#64748b",
                  fontWeight: 500,
                  fontSize: "0.75rem",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                No Project Loaded
              </Typography>
            </Box>
          )}

          {isLoading && (
            <Box
              sx={{
                position: "absolute",
                inset: 0,
                bgcolor: "rgba(15,23,42,0.4)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 2,
              }}
            >
              <CircularProgress size={28} sx={{ color: "#ffffff" }} />
            </Box>
          )}

          {/* Ghost Preview Stage Frame (Pure visual preview, zero overlay clutter) */}
          {ghostPreview && (
            <Box
              id="studio-ghost-preview-stage"
              data-testid="studio-ghost-preview-stage"
              sx={{
                position: "absolute",
                inset: 0,
                zIndex: 10,
                bgcolor: "#000000",
                overflow: "hidden",
              }}
            >
              {ghostPreview.posterUrl && !ghostFrameLoaded && (
                <Box
                  component="img"
                  src={ghostPreview.posterUrl}
                  alt={ghostPreview.title || ghostPreview.block_id}
                  sx={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    objectFit: "contain",
                    zIndex: 1,
                  }}
                />
              )}
              {ghostPreview.previewUrl && (
                <iframe
                  id="studio-ghost-preview-iframe"
                  src={ghostPreview.previewUrl}
                  title={`Ghost Preview: ${ghostPreview.title || ghostPreview.block_id}`}
                  sandbox="allow-scripts"
                  onLoad={() => setGhostFrameLoaded(true)}
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    border: 0,
                    display: "block",
                    backgroundColor: "#0b0f19",
                    zIndex: 2,
                  }}
                />
              )}
            </Box>
          )}
        </Box>
      </Box>

      {/* Floating Bottom Playback Controls */}
      <Box
        sx={{
          height: 44,
          minHeight: 44,
          bgcolor: "#ffffff",
          borderTop: "1px solid",
          borderColor: "divider",
          px: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        {/* Transport Buttons */}
        <Stack direction="row" alignItems="center" spacing={0.5}>
          <IconButton size="small" onClick={() => handleSeek(0)}>
            <IconPlayerSkipBack size={16} />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleTogglePlay}
            sx={{
              bgcolor: "primary.main",
              color: "#ffffff",
              width: 30,
              height: 30,
              "&:hover": { bgcolor: "primary.dark" },
            }}
          >
            {isPlaying ? <IconPlayerPause size={16} stroke={2.5} /> : <IconPlayerPlay size={16} stroke={2.5} />}
          </IconButton>
          <IconButton size="small" onClick={() => handleSeek(duration)}>
            <IconPlayerSkipForward size={16} />
          </IconButton>
          <Tooltip title="Refresh stage" arrow>
            <IconButton size="small" onClick={onRefresh} sx={{ ml: 0.5 }}>
              <IconRefresh size={15} />
            </IconButton>
          </Tooltip>
        </Stack>

        {/* Scrubbing slider */}
        <Box sx={{ flex: 1, mx: 2, display: "flex", alignItems: "center" }}>
          <Slider
            size="small"
            data-testid="studio-transport-scrubber"
            min={0}
            max={duration || 15}
            step={0.05}
            value={typeof currentTime === "number" ? Math.min(currentTime, duration || 15) : 0}
            onChange={(_, val) => handleSeek(val)}
            sx={{
              color: "primary.main",
              height: 4,
              "& .MuiSlider-thumb": {
                width: 10,
                height: 10,
              },
            }}
          />
        </Box>

        {/* Timecode Readout */}
        <Typography variant="caption" sx={{ fontFamily: "monospace", fontWeight: 700, fontSize: "0.75rem", color: "text.primary" }}>
          {Number(currentTime || 0).toFixed(2)}s / {Number(duration || 0).toFixed(2)}s
        </Typography>

        {/* Volume & Fullscreen */}
        <Stack direction="row" alignItems="center" spacing={1}>
          <IconButton size="small" onClick={handleToggleMute}>
            {muted ? <IconVolumeOff size={16} /> : <IconVolume size={16} />}
          </IconButton>
        </Stack>
      </Box>
    </Box>
  )
})

export default StudioPreviewStage
