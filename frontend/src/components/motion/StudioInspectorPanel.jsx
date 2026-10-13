// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import {
  Box, Stack, Typography, TextField, Slider, Select, MenuItem,
  Switch, FormControlLabel, Divider, Tooltip, IconButton, Chip, Button,
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
} from "@tabler/icons-react"

/**
 * Right Property & Layer Inspector.
 * Contextual properties for selected elements, typography, transform, timing, keyframes.
 */
export default function StudioInspectorPanel({
  selectedElement,
  onUpdateElement,
  onCommitElement,
  tracks = [],
  isPinned = false,
  onTogglePin,
  onNavigateToCode,
}) {
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
                </Typography>
              </Box>

              {/* Block Identity & Dynamic Variables */}
              {(selectedElement.type === "block" || selectedElement.block_id) && (
                <Box sx={{ p: 1, borderRadius: 1.5, border: "1px solid", borderColor: "primary.light", bgcolor: "#fdf4ff" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="caption" sx={{ fontWeight: 800, color: "primary.main", display: "flex", alignItems: "center", gap: 0.5 }}>
                      <IconSparkles size={14} /> HyperFrames Block
                    </Typography>
                    <Chip
                      size="small"
                      label={selectedElement.block_version ? selectedElement.block_version.slice(0, 8) : "v1"}
                      sx={{ height: 16, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#ede9fe", color: "#6d28d9" }}
                    />
                  </Stack>

                  <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mb: 1, color: "text.secondary" }}>
                    Parameters & Variables
                  </Typography>

                  {Object.keys(selectedElement.variables || {}).length === 0 ? (
                    <Typography variant="caption" sx={{ color: "text.disabled", fontSize: "0.7rem", fontStyle: "italic" }}>
                      No configurable variables declared.
                    </Typography>
                  ) : (
                    <Stack spacing={1}>
                      {Object.entries(selectedElement.variables || {}).map(([varKey, varVal]) => (
                        <Box key={varKey}>
                          <Typography variant="caption" sx={{ fontSize: "0.68rem", fontWeight: 700, color: "text.secondary", display: "block", mb: 0.25 }}>
                            {varKey}
                          </Typography>
                          {typeof varVal === "boolean" ? (
                            <FormControlLabel
                              control={
                                <Switch
                                  size="small"
                                  checked={Boolean(varVal)}
                                  onChange={(e) => {
                                    const updated = {
                                      ...selectedElement,
                                      variables: { ...(selectedElement.variables || {}), [varKey]: e.target.checked },
                                    }
                                    onUpdateElement && onUpdateElement(updated)
                                    onCommitElement && onCommitElement(updated)
                                  }}
                                />
                              }
                              label={<Typography variant="caption">{varKey}</Typography>}
                            />
                          ) : typeof varVal === "number" ? (
                            <TextField
                              fullWidth
                              size="small"
                              type="number"
                              value={varVal}
                              onChange={(e) => {
                                onUpdateElement && onUpdateElement({
                                  ...selectedElement,
                                  variables: { ...(selectedElement.variables || {}), [varKey]: Number(e.target.value) },
                                })
                              }}
                              onBlur={() => onCommitElement && onCommitElement(selectedElement)}
                              sx={{ "& .MuiInputBase-input": { fontSize: "0.75rem", py: 0.5 } }}
                            />
                          ) : (
                            <TextField
                              fullWidth
                              size="small"
                              value={varVal ?? ""}
                              onChange={(e) => {
                                onUpdateElement && onUpdateElement({
                                  ...selectedElement,
                                  variables: { ...(selectedElement.variables || {}), [varKey]: e.target.value },
                                })
                              }}
                              onBlur={() => onCommitElement && onCommitElement(selectedElement)}
                              sx={{ "& .MuiInputBase-input": { fontSize: "0.75rem", py: 0.5 } }}
                            />
                          )}
                        </Box>
                      ))}
                    </Stack>
                  )}
                </Box>
              )}

              {/* Caption / Text Properties */}
              {(selectedElement.type === "captions" || selectedElement.caption_text) && (
                <Box>
                  <Typography variant="caption" sx={{ fontWeight: 700, mb: 1, display: "flex", alignItems: "center", gap: 0.5 }}>
                    <IconTypography size={14} /> Typography
                  </Typography>
                  <TextField
                    fullWidth
                    multiline
                    rows={2}
                    size="small"
                    label="Caption Content"
                    value={selectedElement.caption_text || ""}
                    onChange={(e) => onUpdateElement && onUpdateElement({ ...selectedElement, caption_text: e.target.value })}
                    onBlur={() => onCommitElement && onCommitElement(selectedElement)}
                    sx={{ "& .MuiInputBase-input": { fontSize: "0.78rem" } }}
                  />
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
                      min={0.5}
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
