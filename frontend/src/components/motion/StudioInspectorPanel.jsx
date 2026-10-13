// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import {
  Box, Stack, Typography, TextField, Slider, Select, MenuItem,
  Switch, FormControlLabel, Divider, Tooltip, IconButton, Chip, Button,
  FormControl, InputLabel,
} from "@mui/material"
import {
  IconAdjustments,
  IconTypography,
  IconVolume,
  IconPalette,
  IconLayersSubtract,
  IconPin,
  IconPinnedOff,
  IconSparkles,
  IconCode,
  IconGauge,
  IconArrowsExchange,
  IconCrop,
  IconInfoCircle,
} from "@tabler/icons-react"

const FRAMING_PRESETS_LIST = [
  { id: "none", label: "Default (Full Frame)", desc: "Untouched original media framing" },
  { id: "gameplay_reticle", label: "Gameplay Reticle (Safe HUD)", desc: "Safe margins for HUD radar, crosshair, and ammo counters" },
  { id: "hud_aware_blur", label: "HUD-Aware Blur (Vertical 9:16)", desc: "Blurred wings masking HUD borders for clean vertical Shorts/Reels" },
  { id: "split_facecam_gameplay", label: "Split Facecam + Gameplay", desc: "Reaction camera stacked above gameplay footage" },
  { id: "center_crop", label: "Center Crop (9:16)", desc: "Standard centered 9:16 extraction" },
]

const SPEED_PRESETS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 4.0]

/**
 * Right Property & Layer Inspector.
 * Contextual properties for selected elements, typography, transform, timing, keyframes,
 * framing presets, slip offsets, and speed retime.
 */
export default function StudioInspectorPanel({
  selectedElement,
  onUpdateElement,
  onCommitElement,
  tracks = [],
  isPinned = false,
  onTogglePin,
  onNavigateToCode,
  onSlipClip,
  onSpeedChangeClip,
}) {
  const isVideoOrAudio = selectedElement && (selectedElement.type === "video" || selectedElement.type === "audio" || selectedElement.asset_file || selectedElement.asset_id)
  const isVideo = selectedElement && (selectedElement.type === "video" || (!selectedElement.type && !selectedElement.isInternal))

  const handleSpeedSelect = (newSpeed) => {
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

  const handleSlipStep = (deltaSec) => {
    if (!selectedElement) return
    const curTrimStart = Number(selectedElement.trim_start || 0)
    const curDur = Number(selectedElement.duration_seconds || 1.0)
    const nextTrimStart = Math.max(0, Number((curTrimStart + deltaSec).toFixed(2)))
    const nextTrimEnd = Number((nextTrimStart + curDur).toFixed(2))
    const updated = {
      ...selectedElement,
      trim_start: nextTrimStart,
      trim_end: nextTrimEnd,
    }
    if (onSlipClip) {
      onSlipClip(selectedElement, deltaSec)
    } else {
      if (onUpdateElement) onUpdateElement(updated)
      if (onCommitElement) onCommitElement(updated)
    }
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#ffffff",
        borderLeft: "1px solid",
        borderColor: "divider",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Box sx={{ p: 1.5, pb: 1, borderBottom: "1px solid", borderColor: "divider" }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography
            variant="caption"
            sx={{
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "text.secondary",
            }}
          >
            Inspector & Properties
          </Typography>
          <Tooltip title={isPinned ? "Unpin panel" : "Pin panel"} arrow>
            <IconButton
              size="small"
              onClick={onTogglePin}
              sx={{ width: 22, height: 22, color: isPinned ? "primary.main" : "text.secondary" }}
            >
              {isPinned ? <IconPin size={14} /> : <IconPinnedOff size={14} />}
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 1.5 }}>
        {selectedElement ? (
          selectedElement.isInternal ? (
            <Stack spacing={2}>
              {/* Internal DOM Element Card */}
              <Box sx={{ p: 1.5, borderRadius: 1.5, border: "1px solid", borderColor: "primary.light", bgcolor: "#fdf4ff" }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Typography variant="caption" sx={{ fontWeight: 800, color: "primary.main", display: "flex", alignItems: "center", gap: 0.5 }}>
                    <IconSparkles size={14} /> Block DOM Layer
                  </Typography>
                  <Chip
                    size="small"
                    label={`<${selectedElement.tagName}>`}
                    sx={{ height: 18, fontSize: "0.68rem", fontFamily: "monospace", fontWeight: 700, bgcolor: "#ede9fe", color: "#6d28d9" }}
                  />
                </Stack>

                <Stack spacing={1} sx={{ mt: 1 }}>
                  <Box>
                    <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem", fontWeight: 600 }}>
                      Element ID:
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: "monospace", fontWeight: 700, fontSize: "0.78rem", color: "#4f46e5" }}>
                      {selectedElement.nodeId ? `#${selectedElement.nodeId}` : "(none)"}
                    </Typography>
                  </Box>

                  {selectedElement.className && (
                    <Box>
                      <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem", fontWeight: 600 }}>
                        Class Name:
                      </Typography>
                      <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.72rem", color: "text.primary" }}>
                        .{selectedElement.className}
                      </Typography>
                    </Box>
                  )}

                  {selectedElement.text && (
                    <Box>
                      <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem", fontWeight: 600 }}>
                        Text Preview:
                      </Typography>
                      <Typography variant="body2" sx={{ fontSize: "0.75rem", color: "text.secondary", fontStyle: "italic" }}>
                        "{selectedElement.text}"
                      </Typography>
                    </Box>
                  )}

                  <Box>
                    <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem", fontWeight: 600 }}>
                      Parent Block:
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontSize: "0.75rem", color: "text.primary" }}>
                      {selectedElement.parentClip?.title || selectedElement.parentClip?.name || selectedElement.parentClip?.block_id || "Block Clip"}
                    </Typography>
                  </Box>
                </Stack>

                <Divider sx={{ my: 1.5 }} />

                <Button
                  fullWidth
                  variant="contained"
                  size="small"
                  data-testid="inspector-open-code-btn"
                  onClick={() => onNavigateToCode && onNavigateToCode(selectedElement.sourceFile, selectedElement.parentClip?.id)}
                  startIcon={<IconCode size={14} />}
                  sx={{
                    py: 0.5,
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    borderRadius: 1.5,
                    bgcolor: "primary.main",
                  }}
                >
                  Open in CodeMirror 6
                </Button>
              </Box>

              {/* Parent Block Parameters / Variables */}
              {selectedElement.parentClip?.variables && Object.keys(selectedElement.parentClip.variables).length > 0 && (
                <Box sx={{ p: 1.5, borderRadius: 1.5, border: "1px solid", borderColor: "divider", bgcolor: "#f8fafc" }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mb: 1, color: "text.secondary" }}>
                    Parent Block Parameters
                  </Typography>
                  <Stack spacing={1}>
                    {Object.entries(selectedElement.parentClip.variables).map(([varKey, varVal]) => (
                      <Box key={varKey}>
                        <Typography variant="caption" sx={{ fontSize: "0.68rem", fontWeight: 700, color: "text.secondary", display: "block", mb: 0.25 }}>
                          {varKey}
                        </Typography>
                        <TextField
                          fullWidth
                          size="small"
                          value={varVal ?? ""}
                          onChange={(e) => {
                            const updatedParent = {
                              ...selectedElement.parentClip,
                              variables: { ...(selectedElement.parentClip.variables || {}), [varKey]: e.target.value },
                            }
                            onUpdateElement && onUpdateElement(updatedParent)
                          }}
                          onBlur={() => onCommitElement && onCommitElement(selectedElement.parentClip)}
                          sx={{ "& .MuiInputBase-input": { fontSize: "0.75rem", py: 0.5 } }}
                        />
                      </Box>
                    ))}
                  </Stack>
                </Box>
              )}
            </Stack>
          ) : (
            <Stack spacing={2}>
              {/* Element Identity */}
              <Box sx={{ p: 1, borderRadius: 1.5, bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider" }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "text.primary" }}>
                    {selectedElement.title || selectedElement.name || selectedElement.id}
                  </Typography>
                  <Chip size="small" label={selectedElement.type || "clip"} sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700 }} />
                </Stack>
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                  Start: {Number(selectedElement.start_seconds || 0).toFixed(1)}s • Duration: {Number(selectedElement.duration_seconds || 0).toFixed(1)}s
                  {selectedElement.speed ? ` • ${selectedElement.speed}x` : ""}
                </Typography>
              </Box>

              {/* Media Framing & Safe-Region Presets (for Video Clips) */}
              {isVideo && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "primary.light", bgcolor: "#fdf4ff" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.75 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.5, color: "primary.main" }}>
                      <IconCrop size={14} /> Framing & Safe Region
                    </Typography>
                    <Tooltip title="Preset stored in clip metadata. Worker hardware pipeline applies corresponding crop/filter chain." arrow>
                      <IconButton size="small" sx={{ p: 0.25, color: "primary.main" }}>
                        <IconInfoCircle size={13} />
                      </IconButton>
                    </Tooltip>
                  </Stack>

                  <FormControl fullWidth size="small">
                    <InputLabel id="framing-preset-label" sx={{ fontSize: "0.75rem" }}>Preset</InputLabel>
                    <Select
                      labelId="framing-preset-label"
                      label="Preset"
                      value={selectedElement.framing_preset || "none"}
                      onChange={(e) => {
                        const updated = {
                          ...selectedElement,
                          framing_preset: e.target.value,
                        }
                        if (onUpdateElement) onUpdateElement(updated)
                        if (onCommitElement) onCommitElement(updated)
                      }}
                      sx={{ fontSize: "0.75rem", bgcolor: "#ffffff" }}
                    >
                      {FRAMING_PRESETS_LIST.map((p) => (
                        <MenuItem key={p.id} value={p.id} sx={{ fontSize: "0.75rem" }}>
                          <Stack>
                            <Typography variant="caption" sx={{ fontWeight: 700 }}>{p.label}</Typography>
                            <Typography variant="caption" sx={{ fontSize: "0.65rem", color: "text.secondary" }}>{p.desc}</Typography>
                          </Stack>
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {(() => {
                    const preset = selectedElement.framing_preset || "none"
                    const knownPresets = ["center_crop", "none", "hud_aware_blur", "gameplay_reticle", "split_facecam_gameplay"]
                    const isSupported = knownPresets.includes(preset)
                    return (
                      <Stack direction="row" spacing={0.6} alignItems="center" sx={{ mt: 0.75 }}>
                        <Chip
                          size="small"
                          label={isSupported ? `Worker Status: Active (${preset === "none" ? "center_crop" : preset})` : `Worker Status: PENDING (${preset})`}
                          color={isSupported ? "success" : "warning"}
                          variant="outlined"
                          sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700 }}
                        />
                      </Stack>
                    )
                  })()}
                </Box>
              )}

              {/* Speed & Retime Controls */}
              {isVideoOrAudio && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "divider", bgcolor: "#f8fafc" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.75 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.5 }}>
                      <IconGauge size={14} /> Speed / Retime Multiplier
                    </Typography>
                    <Chip
                      size="small"
                      label={`${Number(selectedElement.speed || 1.0)}x`}
                      sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700 }}
                    />
                  </Stack>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap">
                    {SPEED_PRESETS.map((spd) => {
                      const isActive = Number(selectedElement.speed || 1.0) === spd
                      return (
                        <Button
                          key={spd}
                          size="small"
                          variant={isActive ? "contained" : "outlined"}
                          onClick={() => handleSpeedSelect(spd)}
                          sx={{
                            minWidth: 36,
                            px: 0.75,
                            py: 0.25,
                            fontSize: "0.68rem",
                            fontWeight: 700,
                            borderRadius: 1,
                            mb: 0.5,
                          }}
                        >
                          {spd}x
                        </Button>
                      )
                    })}
                  </Stack>
                </Box>
              )}

              {/* Slip Edit Control */}
              {isVideoOrAudio && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "divider", bgcolor: "#f8fafc" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.75 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.5 }}>
                      <IconArrowsExchange size={14} /> Slip Offset (Source Window)
                    </Typography>
                    <Typography variant="caption" sx={{ fontFamily: "monospace", fontSize: "0.7rem", fontWeight: 700 }}>
                      Trim: {Number(selectedElement.trim_start || 0).toFixed(2)}s
                    </Typography>
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <Button
                      fullWidth
                      size="small"
                      variant="outlined"
                      onClick={() => handleSlipStep(-0.5)}
                      sx={{ fontSize: "0.68rem", fontWeight: 700, py: 0.25 }}
                    >
                      Slip Earlier (-0.5s)
                    </Button>
                    <Button
                      fullWidth
                      size="small"
                      variant="outlined"
                      onClick={() => handleSlipStep(0.5)}
                      sx={{ fontSize: "0.68rem", fontWeight: 700, py: 0.25 }}
                    >
                      Slip Later (+0.5s)
                    </Button>
                  </Stack>
                </Box>
              )}

              {/* Audio & Volume Controls */}
              {isVideoOrAudio && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "divider", bgcolor: "#f8fafc" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.75 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.5 }}>
                      <IconVolume size={14} /> Audio & Gain
                    </Typography>
                    <Typography variant="caption" sx={{ fontFamily: "monospace", fontSize: "0.7rem", fontWeight: 700 }}>
                      {selectedElement.muted ? "MUTED" : `${Math.round((Number(selectedElement.volume !== undefined ? selectedElement.volume : 1.0)) * 100)}%`}
                    </Typography>
                  </Stack>
                  <Stack spacing={1}>
                    <Slider
                      size="small"
                      min={0}
                      max={2.0}
                      step={0.05}
                      value={selectedElement.muted ? 0 : Number(selectedElement.volume !== undefined ? selectedElement.volume : 1.0)}
                      disabled={Boolean(selectedElement.muted)}
                      onChange={(_, val) => onUpdateElement && onUpdateElement({ ...selectedElement, volume: val })}
                      onChangeCommitted={(_, val) => onCommitElement && onCommitElement({ ...selectedElement, volume: val })}
                    />
                    <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="center">
                      <Button
                        size="small"
                        variant={selectedElement.muted ? "contained" : "outlined"}
                        color={selectedElement.muted ? "error" : "primary"}
                        onClick={() => {
                          const updated = { ...selectedElement, muted: !selectedElement.muted }
                          if (onUpdateElement) onUpdateElement(updated)
                          if (onCommitElement) onCommitElement(updated)
                        }}
                        sx={{ fontSize: "0.68rem", fontWeight: 700, py: 0.2 }}
                      >
                        {selectedElement.muted ? "Unmute Audio" : "Mute (-an)"}
                      </Button>
                      <Button
                        size="small"
                        variant={selectedElement.audio_enhance ? "contained" : "outlined"}
                        color="secondary"
                        onClick={() => {
                          const updated = { ...selectedElement, audio_enhance: !selectedElement.audio_enhance }
                          if (onUpdateElement) onUpdateElement(updated)
                          if (onCommitElement) onCommitElement(updated)
                        }}
                        sx={{ fontSize: "0.68rem", fontWeight: 700, py: 0.2 }}
                      >
                        {selectedElement.audio_enhance ? "Enhanced (Active)" : "Enhance Voice"}
                      </Button>
                    </Stack>
                  </Stack>
                </Box>
              )}

              {/* Transform & Orientation Controls */}
              {isVideo && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "divider", bgcolor: "#f8fafc" }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.5, mb: 0.75 }}>
                    <IconAdjustments size={14} /> Transform & Orientation
                  </Typography>
                  <Stack direction="row" spacing={0.5}>
                    <Button
                      fullWidth
                      size="small"
                      variant={selectedElement.transform?.flip_h ? "contained" : "outlined"}
                      onClick={() => {
                        const cur = selectedElement.transform || {}
                        const updated = { ...selectedElement, transform: { ...cur, flip_h: !cur.flip_h } }
                        if (onUpdateElement) onUpdateElement(updated)
                        if (onCommitElement) onCommitElement(updated)
                      }}
                      sx={{ fontSize: "0.65rem", fontWeight: 700, py: 0.25 }}
                    >
                      Flip H
                    </Button>
                    <Button
                      fullWidth
                      size="small"
                      variant={selectedElement.transform?.flip_v ? "contained" : "outlined"}
                      onClick={() => {
                        const cur = selectedElement.transform || {}
                        const updated = { ...selectedElement, transform: { ...cur, flip_v: !cur.flip_v } }
                        if (onUpdateElement) onUpdateElement(updated)
                        if (onCommitElement) onCommitElement(updated)
                      }}
                      sx={{ fontSize: "0.65rem", fontWeight: 700, py: 0.25 }}
                    >
                      Flip V
                    </Button>
                    <Button
                      fullWidth
                      size="small"
                      variant="outlined"
                      onClick={() => {
                        const cur = selectedElement.transform || {}
                        const nextRot = ((cur.rotation || 0) + 90) % 360
                        const updated = { ...selectedElement, transform: { ...cur, rotation: nextRot } }
                        if (onUpdateElement) onUpdateElement(updated)
                        if (onCommitElement) onCommitElement(updated)
                      }}
                      sx={{ fontSize: "0.65rem", fontWeight: 700, py: 0.25 }}
                    >
                      Rot {selectedElement.transform?.rotation ? `${selectedElement.transform.rotation}°` : "90°"}
                    </Button>
                  </Stack>
                </Box>
              )}


              {/* Caption / Text Properties with Line Break Preservation */}
              {(selectedElement.type === "captions" || selectedElement.caption_text !== undefined) && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "warning.light", bgcolor: "#fffbeb" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, display: "flex", alignItems: "center", gap: 0.5, color: "warning.dark" }}>
                      <IconTypography size={14} /> Captions & Typography
                    </Typography>
                    {selectedElement.manual_transcript_override && (
                      <Chip
                        size="small"
                        label="Manual Override (Authoritative)"
                        color="warning"
                        variant="filled"
                        sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700 }}
                      />
                    )}
                  </Stack>
                  <TextField
                    fullWidth
                    multiline
                    minRows={2}
                    maxRows={6}
                    size="small"
                    label="Caption Content (Preserves Line Breaks)"
                    value={selectedElement.caption_text || ""}
                    onChange={(e) => onUpdateElement && onUpdateElement({
                      ...selectedElement,
                      caption_text: e.target.value,
                      manual_transcript_override: true,
                    })}
                    onBlur={() => onCommitElement && onCommitElement({
                      ...selectedElement,
                      manual_transcript_override: true,
                    })}
                    sx={{
                      "& .MuiInputBase-input": { fontSize: "0.78rem", whiteSpace: "pre-wrap" },
                      bgcolor: "#ffffff",
                    }}
                  />
                  <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.65rem", display: "block", mt: 0.5 }}>
                    Manual corrections preserve line breaks and override Whisper reanalysis.
                  </Typography>
                </Box>
              )}

              {/* Timing & Position */}
              <Box>
                <Typography variant="caption" sx={{ fontWeight: 700, mb: 1, display: "flex", alignItems: "center", gap: 0.5 }}>
                  <IconAdjustments size={14} /> Timing & Scale
                </Typography>
                <Stack spacing={1}>
                  <Box>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem" }}>Start Offset</Typography>
                      <Typography variant="caption" sx={{ fontWeight: 700, fontSize: "0.7rem" }}>
                        {Number(selectedElement.start_seconds || 0).toFixed(1)}s
                      </Typography>
                    </Stack>
                    <Slider
                      size="small"
                      min={0}
                      max={60}
                      step={0.1}
                      value={Number(selectedElement.start_seconds || 0)}
                      onChange={(_, val) => onUpdateElement && onUpdateElement({ ...selectedElement, start_seconds: val })}
                      onChangeCommitted={(_, val) => onCommitElement && onCommitElement({ ...selectedElement, start_seconds: val })}
                    />
                  </Box>
                  <Box>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem" }}>Clip Duration</Typography>
                      <Typography variant="caption" sx={{ fontWeight: 700, fontSize: "0.7rem" }}>
                        {Number(selectedElement.duration_seconds || 1).toFixed(1)}s
                      </Typography>
                    </Stack>
                    <Slider
                      size="small"
                      min={0.2}
                      max={60}
                      step={0.1}
                      value={Number(selectedElement.duration_seconds || 1)}
                      onChange={(_, val) => onUpdateElement && onUpdateElement({ ...selectedElement, duration_seconds: val })}
                      onChangeCommitted={(_, val) => onCommitElement && onCommitElement({ ...selectedElement, duration_seconds: val })}
                    />
                  </Box>
                </Stack>
              </Box>

              {/* Keyframe & Transitions Animation */}
              <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "divider" }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "text.primary", display: "block", mb: 0.5 }}>
                  Animation & Easing
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem", display: "block" }}>
                  GSAP ease: power2.out • Spring bounce: 0.15 • Smooth scrub enabled
                </Typography>
              </Box>
            </Stack>
          )
        ) : (
          /* Track Layer Tree when no element is selected */
          <Stack spacing={1.5}>
            <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>
              Composition Tracks ({tracks.length})
            </Typography>
            {tracks.length === 0 ? (
              <Typography variant="caption" sx={{ color: "text.disabled", textAlign: "center", display: "block", mt: 4 }}>
                No active tracks. Add assets from the left panel.
              </Typography>
            ) : (
              tracks.map((track) => (
                <Box
                  key={track.id}
                  sx={{
                    p: 1,
                    borderRadius: 1.5,
                    border: "1px solid",
                    borderColor: "divider",
                    bgcolor: "#f8fafc",
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>
                      {track.name || track.id}
                    </Typography>
                    <Chip size="small" label={`${(track.clips || []).length} clips`} sx={{ height: 18, fontSize: "0.65rem" }} />
                  </Stack>
                </Box>
              ))
            )}
          </Stack>
        )}
      </Box>
    </Box>
  )
}
