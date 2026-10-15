// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState } from "react"
import {
  Box,
  Stack,
  Typography,
  Button,
  IconButton,
  Slider,
  Chip,
  Tooltip,
  Divider,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from "@mui/material"
import {
  IconScissors,
  IconCrop,
  IconGauge,
  IconSubtitles,
  IconVolume,
  IconVolumeOff,
  IconAdjustments,
  IconSparkles,
  IconCopy,
  IconTrash,
  IconArrowsExchange,
  IconZoomIn,
  IconLayersIntersect,
  IconWaveSine,
  IconInfoCircle,
} from "@tabler/icons-react"

const SPEED_PRESETS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

const FRAMING_PRESETS = [
  { id: "default", label: "Default (Full Frame)", desc: "Original composition framing" },
  { id: "center_916", label: "Center Crop (9:16)", desc: "Centered vertical crop for Shorts/Reels" },
  { id: "hud_safe", label: "Safe HUD Margins", desc: "Keep radar, crosshair, and UI safe" },
  { id: "split_stack", label: "Split Stack (Reaction)", desc: "Stacked facecam and content" },
]

/**
 * Context-Sensitive Native Tools Inspector for Motion Graphics.
 * Sits directly alongside Properties and Variables in the right-hand panel.
 * Every action directly mutates the authoritative ProjectRevision CAS document.
 */
export default function StudioToolsInspector({
  selectedElement = null,
  tracks = [],
  currentTime = 0,
  duration = 15,
  onUpdateElement = null,
  onCommitElement = null,
  onApplyOperation = null,
  onSplitClip = null,
  onDeleteClip = null,
  onDuplicateClip = null,
  onSlipClip = null,
  onSpeedChangeClip = null,
}) {
  const isSelected = Boolean(selectedElement)
  const isVideoOrAudio = selectedElement && (
    selectedElement.type === "video" ||
    selectedElement.type === "audio" ||
    selectedElement.asset_file ||
    selectedElement.asset_id
  )
  const isVideo = selectedElement && (selectedElement.type === "video" || (!selectedElement.type && !selectedElement.isInternal))

  // State for quick adjustments
  const [activeFraming, setActiveFraming] = useState("default")

  // Split handler
  const handleSplit = () => {
    if (!selectedElement) return
    if (onSplitClip) {
      onSplitClip(selectedElement, currentTime)
    } else if (onApplyOperation) {
      onApplyOperation("split_clip", {
        clip_id: selectedElement.id,
        split_time: currentTime,
      })
    }
  }

  // Speed handler
  const handleSpeedChange = (newSpeed) => {
    if (!selectedElement) return
    const curSpeed = Number(selectedElement.speed || 1.0)
    const curDur = Number(selectedElement.duration_seconds || 1.0)
    const newDur = Math.max(0.1, Number(((curDur * curSpeed) / newSpeed).toFixed(2)))
    const updated = {
      ...selectedElement,
      speed: newSpeed,
      duration_seconds: newDur,
    }
    if (onSpeedChangeClip) {
      onSpeedChangeClip(selectedElement, newSpeed)
    } else {
      if (onUpdateElement) onUpdateElement(updated)
      if (onCommitElement) onCommitElement(updated)
    }
  }

  // Slip handler
  const handleSlip = (deltaSec) => {
    if (!selectedElement) return
    if (onSlipClip) {
      onSlipClip(selectedElement, deltaSec)
    } else {
      const curTrimStart = Number(selectedElement.trim_start || 0)
      const curDur = Number(selectedElement.duration_seconds || 1.0)
      const nextTrimStart = Math.max(0, Number((curTrimStart + deltaSec).toFixed(2)))
      const nextTrimEnd = Number((nextTrimStart + curDur).toFixed(2))
      const updated = {
        ...selectedElement,
        trim_start: nextTrimStart,
        trim_end: nextTrimEnd,
      }
      if (onUpdateElement) onUpdateElement(updated)
      if (onCommitElement) onCommitElement(updated)
    }
  }

  // Trim In/Out nudge
  const handleTrimNudge = (field, deltaSec) => {
    if (!selectedElement) return
    const curVal = Number(selectedElement[field] || 0)
    const updated = {
      ...selectedElement,
      [field]: Math.max(0, Number((curVal + deltaSec).toFixed(2))),
    }
    if (onUpdateElement) onUpdateElement(updated)
    if (onCommitElement) onCommitElement(updated)
  }

  // Framing preset handler
  const handleFramingSelect = (presetId) => {
    setActiveFraming(presetId)
    if (!selectedElement) return
    const updated = {
      ...selectedElement,
      framing_preset: presetId,
    }
    if (onUpdateElement) onUpdateElement(updated)
    if (onCommitElement) onCommitElement(updated)
  }

  // Captions generator operation
  const handleGenerateCaptions = () => {
    if (onApplyOperation) {
      onApplyOperation("generate_captions", {
        clip_id: selectedElement?.id,
        style: "karaoke_pop",
      })
    }
  }

  // Volume handler
  const handleVolumeChange = (newVol) => {
    if (!selectedElement) return
    const updated = {
      ...selectedElement,
      volume: newVol,
    }
    if (onUpdateElement) onUpdateElement(updated)
    if (onCommitElement) onCommitElement(updated)
  }

  return (
    <Box
      data-testid="studio-tools-inspector"
      sx={{
        width: "100%",
        height: "100%",
        overflowY: "auto",
        p: 2,
        display: "flex",
        flexDirection: "column",
        gap: 2,
        bgcolor: "#ffffff",
      }}
    >
      {/* Context Badge */}
      <Stack direction="row" alignItems="center" justifyContent="space-between">
        <Typography variant="subtitle2" sx={{ fontWeight: 800, color: "text.primary", fontSize: "0.8rem" }}>
          Native Timeline Tools
        </Typography>
        <Chip
          size="small"
          label={isSelected ? `${selectedElement.title || selectedElement.name || selectedElement.id}` : "No Selection"}
          color={isSelected ? "primary" : "default"}
          sx={{ height: 20, fontSize: "0.68rem", fontWeight: 700, maxWidth: 160 }}
        />
      </Stack>

      {!isSelected && (
        <Alert
          severity="info"
          icon={<IconInfoCircle size={16} />}
          sx={{ py: 0.5, px: 1.5, fontSize: "0.72rem", "& .MuiAlert-message": { p: 0.2 } }}
        >
          Select any video, audio, or caption clip on the timeline to enable contextual split, trim, speed, crop, and reframe actions.
        </Alert>
      )}

      {/* 1. Trimming & In/Out Range */}
      <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5, bgcolor: "#f8fafc" }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <IconScissors size={16} color="#6366f1" />
          <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
            Trim & Subclip Bounds
          </Typography>
          <Chip label="[ / ]" size="small" sx={{ height: 16, fontSize: "0.6rem", fontFamily: "monospace", ml: "auto" }} />
        </Stack>

        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem" }}>
              In Point ({Number(selectedElement?.trim_start || 0).toFixed(2)}s):
            </Typography>
            <Stack direction="row" spacing={0.5}>
              <Button
                size="small"
                variant="outlined"
                disabled={!isSelected}
                onClick={() => handleTrimNudge("trim_start", -0.5)}
                sx={{ minWidth: 28, height: 22, px: 0.8, fontSize: "0.68rem", textTransform: "none" }}
              >
                -0.5s
              </Button>
              <Button
                size="small"
                variant="outlined"
                disabled={!isSelected}
                onClick={() => handleTrimNudge("trim_start", 0.5)}
                sx={{ minWidth: 28, height: 22, px: 0.8, fontSize: "0.68rem", textTransform: "none" }}
              >
                +0.5s
              </Button>
            </Stack>
          </Stack>

          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem" }}>
              Out Point ({Number(selectedElement?.trim_end || selectedElement?.duration_seconds || 0).toFixed(2)}s):
            </Typography>
            <Stack direction="row" spacing={0.5}>
              <Button
                size="small"
                variant="outlined"
                disabled={!isSelected}
                onClick={() => handleTrimNudge("trim_end", -0.5)}
                sx={{ minWidth: 28, height: 22, px: 0.8, fontSize: "0.68rem", textTransform: "none" }}
              >
                -0.5s
              </Button>
              <Button
                size="small"
                variant="outlined"
                disabled={!isSelected}
                onClick={() => handleTrimNudge("trim_end", 0.5)}
                sx={{ minWidth: 28, height: 22, px: 0.8, fontSize: "0.68rem", textTransform: "none" }}
              >
                +0.5s
              </Button>
            </Stack>
          </Stack>

          {/* Slip Media Timing */}
          <Divider sx={{ my: 0.5 }} />
          <Stack data-testid="tool-slip-media" direction="row" spacing={1} alignItems="center" justifyContent="space-between">
            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem" }}>
              Slip Offset:
            </Typography>
            <Stack direction="row" spacing={0.5}>
              <Button
                size="small"
                variant="outlined"
                disabled={!isSelected}
                onClick={() => handleSlip(-0.25)}
                sx={{ minWidth: 28, height: 22, px: 0.8, fontSize: "0.68rem", textTransform: "none" }}
              >
                ◀ Slip -0.25s
              </Button>
              <Button
                size="small"
                variant="outlined"
                disabled={!isSelected}
                onClick={() => handleSlip(0.25)}
                sx={{ minWidth: 28, height: 22, px: 0.8, fontSize: "0.68rem", textTransform: "none" }}
              >
                Slip +0.25s ▶
              </Button>
            </Stack>
          </Stack>
        </Stack>
      </Box>

      {/* 2. Split at Playhead */}
      <Box data-testid="tool-split-clip" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5, bgcolor: "#f8fafc" }}>
        <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Stack direction="row" spacing={0.8} alignItems="center">
            <IconScissors size={16} color="#0284c7" />
            <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
              Split at Playhead
            </Typography>
          </Stack>
          <Chip label="S" size="small" sx={{ height: 16, fontSize: "0.6rem", fontFamily: "monospace" }} />
        </Stack>
        <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem", display: "block", mb: 1 }}>
          Cut selected clip at playhead time ({Number(currentTime || 0).toFixed(2)}s) into two independent editable timeline clips.
        </Typography>
        <Button
          data-testid="tool-split-clip-btn"
          size="small"
          variant="contained"
          fullWidth
          disabled={!isSelected}
          onClick={handleSplit}
          startIcon={<IconScissors size={14} />}
          sx={{
            py: 0.4,
            fontSize: "0.72rem",
            fontWeight: 700,
            textTransform: "none",
            bgcolor: "primary.main",
          }}
        >
          Split Selected Clip
        </Button>
      </Box>

      {/* 3. Speed & PTS Retime */}
      <Box data-testid="tool-speed-presets" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5, bgcolor: "#f8fafc" }}>
        <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Stack direction="row" spacing={0.8} alignItems="center">
            <IconGauge size={16} color="#d97706" />
            <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
              Speed & Retime
            </Typography>
          </Stack>
          <Typography variant="caption" sx={{ fontWeight: 700, fontFamily: "monospace", color: "primary.main" }}>
            {Number(selectedElement?.speed || 1.0).toFixed(2)}x
          </Typography>
        </Stack>

        <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
          {SPEED_PRESETS.map((spd) => {
            const isCur = Number(selectedElement?.speed || 1.0) === spd
            return (
              <Chip
                key={spd}
                label={`${spd}x`}
                size="small"
                clickable={isSelected}
                disabled={!isSelected}
                color={isCur ? "primary" : "default"}
                onClick={() => handleSpeedChange(spd)}
                sx={{ height: 22, fontSize: "0.68rem", fontWeight: isCur ? 800 : 500 }}
              />
            )
          })}
        </Stack>
      </Box>

      {/* 4. Crop & Reframe */}
      <Box data-testid="tool-reframe" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5, bgcolor: "#f8fafc" }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <IconCrop size={16} color="#10b981" />
          <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
            Crop & Vertical Reframe
          </Typography>
        </Stack>

        <FormControl size="small" fullWidth disabled={!isSelected}>
          <InputLabel sx={{ fontSize: "0.72rem" }}>Framing Preset</InputLabel>
          <Select
            value={activeFraming}
            label="Framing Preset"
            onChange={(e) => handleFramingSelect(e.target.value)}
            sx={{ fontSize: "0.72rem", height: 32 }}
          >
            {FRAMING_PRESETS.map((p) => (
              <MenuItem key={p.id} value={p.id} sx={{ fontSize: "0.72rem" }}>
                <Box>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: "block" }}>{p.label}</Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.65rem" }}>{p.desc}</Typography>
                </Box>
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {/* 5. Subtitles & Captions */}
      <Box data-testid="tool-captions" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5, bgcolor: "#f8fafc" }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <IconSubtitles size={16} color="#8b5cf6" />
          <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
            Speech & Captions
          </Typography>
        </Stack>
        <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem", display: "block", mb: 1 }}>
          Synchronize word-level subtitles directly to this clip using Whisper speech recognition.
        </Typography>
        <Button
          size="small"
          variant="outlined"
          fullWidth
          disabled={!isSelected || !isVideoOrAudio}
          onClick={handleGenerateCaptions}
          startIcon={<IconSparkles size={14} />}
          sx={{
            py: 0.4,
            fontSize: "0.72rem",
            fontWeight: 700,
            textTransform: "none",
          }}
        >
          Generate Word Captions
        </Button>
      </Box>

      {/* 6. Volume & Audio Filter */}
      {isVideoOrAudio && (
        <Box data-testid="tool-volume" sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.5, bgcolor: "#f8fafc" }}>
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Stack direction="row" spacing={0.8} alignItems="center">
              <IconVolume size={16} color="#ec4899" />
              <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
                Audio Volume
              </Typography>
            </Stack>
            <Typography variant="caption" sx={{ fontWeight: 700, fontFamily: "monospace" }}>
              {Math.round((selectedElement?.volume !== undefined ? selectedElement.volume : 1.0) * 100)}%
            </Typography>
          </Stack>
          <Slider
            size="small"
            value={selectedElement?.volume !== undefined ? selectedElement.volume : 1.0}
            min={0}
            max={2.0}
            step={0.05}
            disabled={!isSelected}
            onChange={(_, val) => handleVolumeChange(val)}
            sx={{ py: 0.5 }}
          />
        </Box>
      )}

      {/* 7. Clip Management */}
      <Stack direction="row" spacing={1} sx={{ mt: "auto", pt: 1 }}>
        <Button
          size="small"
          variant="outlined"
          fullWidth
          disabled={!isSelected}
          onClick={() => onDuplicateClip && onDuplicateClip(selectedElement)}
          startIcon={<IconCopy size={14} />}
          sx={{ py: 0.4, fontSize: "0.72rem", fontWeight: 700, textTransform: "none" }}
        >
          Duplicate
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="error"
          fullWidth
          disabled={!isSelected}
          onClick={() => onDeleteClip && onDeleteClip(selectedElement?.id)}
          startIcon={<IconTrash size={14} />}
          sx={{ py: 0.4, fontSize: "0.72rem", fontWeight: 700, textTransform: "none" }}
        >
          Delete
        </Button>
      </Stack>
    </Box>
  )
}
