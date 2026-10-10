// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useRef, useState, useEffect, useImperativeHandle, forwardRef } from "react"
import {
  Box, Stack, Typography, IconButton, Slider, Tooltip, CircularProgress,
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
} from "@tabler/icons-react"

/**
 * Central Stage & Video Preview using HyperFrames Player integration.
 * Respects 9:16 and 16:9 aspect ratios without distortion.
 * Uses Light theme canvas surrounding with crisp composition stage.
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
}, ref) {
  const iframeRef = useRef(null)
  const [muted, setMuted] = useState(false)
  const lastPostedPlayRef = useRef(null)

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
      postControl("seek", { time: validTime })
    },
    play: () => {
      postControl("play")
    },
    pause: () => {
      postControl("pause")
    },
  }))

  // Synchronize external isPlaying state (e.g. from Timeline or Spacebar) to iframe runtime
  useEffect(() => {
    if (isPlaying !== lastPostedPlayRef.current) {
      lastPostedPlayRef.current = isPlaying
      postControl(isPlaying ? "play" : "pause")
    }
  }, [isPlaying])

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
    postControl(nextState ? "play" : "pause")
    if (onTogglePlay) onTogglePlay()
  }

  const handleSeek = (time) => {
    postControl("seek", { time })
    if (onSeek) onSeek(time)
  }

  const handleToggleMute = () => {
    const nextMuted = !muted
    setMuted(nextMuted)
    postControl("mute", { muted: nextMuted })
  }

  // Aspect ratio styling
  const isPortrait = aspectRatio === "9:16"
  // For portrait 9:16, maximum height bounding; for landscape 16:9, maximum width bounding
  const stageAspectRatio = isPortrait ? 9 / 16 : 16 / 9

  return (
    <Box
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
          {previewUrl ? (
            <iframe
              id="studio-preview-iframe"
              ref={iframeRef}
              src={previewUrl}
              title="Composition Stage"
              sandbox="allow-scripts"
              style={{
                width: "100%",
                height: "100%",
                border: 0,
                display: "block",
                backgroundColor: "#0b0f19",
              }}
            />
          ) : (
            <Stack alignItems="center" spacing={1} sx={{ color: "#94a3b8" }}>
              <CircularProgress size={24} color="inherit" />
              <Typography variant="caption">Loading composition…</Typography>
            </Stack>
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
