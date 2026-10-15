// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useRef, useState, useEffect, useImperativeHandle, forwardRef } from "react"
import {
  Box, Stack, Typography, IconButton, Slider, Tooltip, CircularProgress, Chip, Button,
  TextField,
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
  project = null,
  previewUrl,
  aspectRatio = "9:16",
  isLoading = false,
  error = null,
  onRetry = null,
  stageState = null,
  loadingMessage = "Loading composition…",
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
  onStartGoal = null,
  onNewProject = null,
}, ref) {
  // Determine Stage Finite State Machine (FSM) state
  // Supported states: NO_PROJECT, LOADING_EXISTING_PROJECT, EMPTY_PROJECT, READY, FAILED, CANCELLED
  const resolvedState = (() => {
    if (stageState) return stageState
    if (error) return "FAILED"
    if (workspaceMode === "review" && (renderedVideo?.video_url || renderedVideo?.preview_ref)) {
      return "READY"
    }
    if (previewUrl) {
      return "READY"
    }
    if (isLoading) {
      if (project) {
        return "LOADING_EXISTING_PROJECT"
      }
      return "NO_PROJECT"
    }
    if (project) {
      const tracks = project.document?.timeline?.tracks || []
      const hasClips = tracks.some((t) => t.clips && t.clips.length > 0) || (project.document?.clips && project.document?.clips?.length > 0)
      if (!hasClips) {
        return "EMPTY_PROJECT"
      }
      return "READY"
    }
    return "NO_PROJECT"
  })()

  const iframeRef = useRef(null)
  const videoRef = useRef(null)
  const [muted, setMuted] = useState(false)
  const lastPostedPlayRef = useRef(null)
  const [ghostFrameLoaded, setGhostFrameLoaded] = useState(false)
  const [videoDimensions, setVideoDimensions] = useState({ width: 0, height: 0 })
  const [goalPrompt, setGoalPrompt] = useState("")

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
      const maxDur = typeof duration === "number" && duration > 0 ? duration : 3600
      const validTime = typeof time === "number" && Number.isFinite(time) ? Math.max(0, Math.min(time, maxDur)) : 0
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
    const maxDur = typeof duration === "number" && duration > 0 ? duration : 3600
    const validTime = typeof time === "number" && Number.isFinite(time) ? Math.max(0, Math.min(time, maxDur)) : 0
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
          data-testid="motion-player"
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
          {/* Stage FSM Rendering */}
          {resolvedState === "READY" && workspaceMode === "review" && (renderedVideo?.video_url || renderedVideo?.preview_ref) ? (
            <>
              <video
                id="studio-rendered-video"
                data-testid="studio-rendered-video"
                ref={videoRef}
                src={renderedVideo.preview_ref || renderedVideo.video_url}
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
                  <Chip
                    label={renderedVideo.output_id ? `Clip: ${renderedVideo.output_id}` : `Render: Rev ${renderedVideo.project_revision || 1}`}
                    color="success"
                    size="small"
                    sx={{ height: 20, fontSize: "0.68rem", fontWeight: 700 }}
                  />
                  <Typography variant="caption" sx={{ color: "#e2e8f0", fontFamily: "monospace", fontSize: "0.72rem" }}>
                    {videoDimensions.width ? `${videoDimensions.width}×${videoDimensions.height}` : "1080×1920"} • {Number(duration || 10).toFixed(2)}s
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
          ) : resolvedState === "READY" && previewUrl ? (
            <iframe
              id="studio-preview-iframe"
              data-testid="studio-preview-iframe"
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
          ) : resolvedState === "LOADING_EXISTING_PROJECT" ? (
            <Stack
              data-testid="studio-stage-loading"
              alignItems="center"
              justifyContent="center"
              spacing={1.5}
              sx={{ color: "#94a3b8", height: "100%", width: "100%", p: 2, textAlign: "center" }}
            >
              <CircularProgress size={28} sx={{ color: "primary.main" }} />
              <Typography variant="caption" sx={{ color: "#cbd5e1", fontSize: "0.75rem", fontWeight: 500 }}>
                {loadingMessage || "Loading composition…"}
              </Typography>
            </Stack>
          ) : resolvedState === "EMPTY_PROJECT" ? (
            <Box
              data-testid="studio-stage-empty-project"
              sx={{
                width: "100%",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "#475569",
                userSelect: "none",
                p: 3,
                textAlign: "center",
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: "#94a3b8",
                  fontWeight: 600,
                  fontSize: "0.78rem",
                  letterSpacing: "0.05em",
                  textTransform: "uppercase",
                  mb: 0.5,
                }}
              >
                Empty Timeline
              </Typography>
              <Typography variant="caption" sx={{ color: "#64748b", fontSize: "0.72rem", maxWidth: 220 }}>
                Drop media clips or catalog blocks to start composing
              </Typography>
            </Box>
          ) : resolvedState === "FAILED" ? (
            <Box
              data-testid="studio-stage-failed"
              sx={{
                width: "100%",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                p: 3,
                textAlign: "center",
                gap: 1.5,
              }}
            >
              <Typography variant="caption" sx={{ color: "#f87171", fontSize: "0.75rem", fontWeight: 600 }}>
                {typeof error === "string" ? error : (error?.message || "Failed to load composition")}
              </Typography>
              {onRetry && (
                <Button
                  data-testid="studio-player-retry-btn"
                  variant="outlined"
                  size="small"
                  onClick={onRetry}
                  sx={{
                    fontSize: "0.72rem",
                    color: "#f87171",
                    borderColor: "rgba(248,113,113,0.5)",
                    textTransform: "none",
                    "&:hover": { borderColor: "#f87171" },
                  }}
                >
                  Retry
                </Button>
              )}
            </Box>
          ) : resolvedState === "CANCELLED" ? (
            <Box
              data-testid="studio-stage-cancelled"
              sx={{
                width: "100%",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                p: 3,
                textAlign: "center",
              }}
            >
              <Typography variant="caption" sx={{ color: "#94a3b8", fontSize: "0.75rem" }}>
                Operation Cancelled
              </Typography>
            </Box>
          ) : (
            // Default: NO_PROJECT - Main Agent Goal Composer immediately visible on first load
            <Box
              data-testid="studio-stage-no-project"
              sx={{
                width: "100%",
                height: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                p: { xs: 2, md: 3 },
                textAlign: "center",
                color: "#f8fafc",
                userSelect: "none",
              }}
            >
              <Box
                data-testid="main-agent-goal-composer"
                sx={{
                  maxWidth: 380,
                  width: "100%",
                  bgcolor: "rgba(15, 23, 42, 0.88)",
                  backdropFilter: "blur(12px)",
                  borderRadius: 2.5,
                  p: 2.5,
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  boxShadow: "0 12px 36px rgba(0, 0, 0, 0.4)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 1.5,
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" justifyContent="center">
                  <Box sx={{ width: 26, height: 26, borderRadius: 1.5, bgcolor: "primary.main", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <IconSparkles size={16} color="#ffffff" />
                  </Box>
                  <Typography variant="subtitle2" sx={{ fontWeight: 800, color: "#ffffff", letterSpacing: "-0.01em" }}>
                    Main Agent Goal
                  </Typography>
                </Stack>
                <Typography variant="caption" sx={{ color: "#94a3b8", fontSize: "0.72rem", lineHeight: 1.3 }}>
                  OAAS: Enter your target video goal to generate an automated motion project with zero manual setup.
                </Typography>
                <TextField
                  data-testid="main-agent-goal-input"
                  fullWidth
                  multiline
                  rows={2}
                  size="small"
                  placeholder="e.g. 9:16 vertical viral video analyzing AI agent trends with dynamic charts and captions..."
                  value={goalPrompt}
                  onChange={(e) => setGoalPrompt(e.target.value)}
                  inputProps={{ "data-testid": "main-agent-goal-input" }}
                  sx={{
                    "& .MuiOutlinedInput-root": {
                      color: "#ffffff",
                      fontSize: "0.78rem",
                      bgcolor: "rgba(0, 0, 0, 0.3)",
                      borderRadius: 1.5,
                      "& fieldset": { borderColor: "rgba(255, 255, 255, 0.15)" },
                      "&:hover fieldset": { borderColor: "primary.main" },
                    },
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      if (onStartGoal && goalPrompt.trim()) {
                        onStartGoal(goalPrompt)
                      }
                    }
                  }}
                />
                <Stack direction="row" spacing={1}>
                  <Button
                    fullWidth
                    variant="contained"
                    size="small"
                    data-testid="main-agent-goal-submit"
                    disabled={!goalPrompt.trim()}
                    onClick={() => {
                      if (onStartGoal && goalPrompt.trim()) onStartGoal(goalPrompt)
                    }}
                    sx={{
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      py: 0.6,
                      textTransform: "none",
                      bgcolor: "primary.main",
                      borderRadius: 1.5,
                    }}
                  >
                    Run Goal →
                  </Button>
                  {onNewProject && (
                    <Button
                      variant="outlined"
                      size="small"
                      data-testid="main-agent-blank-project"
                      onClick={onNewProject}
                      sx={{
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        py: 0.6,
                        textTransform: "none",
                        color: "#cbd5e1",
                        borderColor: "rgba(255, 255, 255, 0.2)",
                        borderRadius: 1.5,
                        whiteSpace: "nowrap",
                        "&:hover": { borderColor: "#ffffff" },
                      }}
                    >
                      Blank Project
                    </Button>
                  )}
                </Stack>
                {/* OAAS Preset Suggestion Chips */}
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, justifyContent: "center", pt: 0.5 }}>
                  {[
                    "Viral AI Breakdown (9:16)",
                    "Tech Trend Commentary (9:16)",
                    "Product Reveal (16:9)",
                  ].map((preset) => (
                    <Chip
                      key={preset}
                      label={preset}
                      size="small"
                      onClick={() => {
                        setGoalPrompt(preset)
                        if (onStartGoal) onStartGoal(preset)
                      }}
                      sx={{
                        height: 20,
                        fontSize: "0.62rem",
                        fontWeight: 600,
                        bgcolor: "rgba(255, 255, 255, 0.08)",
                        color: "#cbd5e1",
                        cursor: "pointer",
                        "&:hover": { bgcolor: "primary.dark", color: "#ffffff" },
                      }}
                    />
                  ))}
                </Box>
              </Box>
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
          <IconButton size="small" onClick={() => handleSeek(0)} disabled={resolvedState !== "READY"}>
            <IconPlayerSkipBack size={16} />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleTogglePlay}
            disabled={resolvedState !== "READY"}
            sx={{
              bgcolor: resolvedState === "READY" ? "primary.main" : "action.disabledBackground",
              color: resolvedState === "READY" ? "#ffffff" : "action.disabled",
              width: 30,
              height: 30,
              "&:hover": { bgcolor: resolvedState === "READY" ? "primary.dark" : "action.disabledBackground" },
            }}
          >
            {isPlaying ? <IconPlayerPause size={16} stroke={2.5} /> : <IconPlayerPlay size={16} stroke={2.5} />}
          </IconButton>
          <IconButton size="small" onClick={() => handleSeek(duration)} disabled={resolvedState !== "READY"}>
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
            disabled={resolvedState !== "READY"}
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
