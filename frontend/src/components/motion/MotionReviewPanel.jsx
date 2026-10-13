// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import {
  Box,
  Card,
  CardContent,
  Typography,
  Stack,
  Chip,
  Button,
  IconButton,
  Tooltip,
  Divider,
  TextField,
} from "@mui/material"
import {
  IconCheck,
  IconDownload,
  IconEdit,
  IconAlertTriangle,
  IconPlayerPlay,
  IconVideo,
  IconNotes,
  IconSparkles,
} from "@tabler/icons-react"

export default function MotionReviewPanel({
  outputs = [],
  selectedOutputIndex = 0,
  onSelectOutput,
  onApproveOutput,
  onExportOutput,
  onRefineOutput,
  approvedOutputs = new Set(),
  reviewNotes = {},
  onChangeReviewNotes,
}) {
  if (!outputs || outputs.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: "center", color: "text.secondary" }}>
        <Typography variant="body2">No rendered outputs available for review.</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 2, height: "100%", overflowY: "auto", bgcolor: "#f8fafc" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "text.primary" }}>
          Production Outputs Review ({outputs.length})
        </Typography>
        <Chip
          label={`${approvedOutputs.size}/${outputs.length} Approved`}
          size="small"
          color={approvedOutputs.size === outputs.length && outputs.length > 0 ? "success" : "default"}
          sx={{ fontWeight: 700, fontSize: "0.7rem" }}
        />
      </Stack>

      <Stack spacing={1.5}>
        {outputs.map((out, idx) => {
          const outId = out.output_id || `output_${idx + 1}`
          const isSelected = selectedOutputIndex === idx
          const isApproved = approvedOutputs.has(out.output_id) || approvedOutputs.has(outId)
          const probe = out.media_probe || {}
          const dur = probe.duration_seconds || out.duration_seconds || 0
          const resolution = probe.width && probe.height ? `${probe.width}×${probe.height}` : "1080×1920"
          const state = out.state || (out.video_url || out.preview_ref ? "SUCCEEDED" : "PENDING")
          const isFailed = state === "FAILED"
          const noteText = reviewNotes[out.output_id] ?? reviewNotes[outId] ?? ""
          const framingPreset = out.framing_preset || out.framingPreset

          return (
            <Card
              key={out.output_id || idx}
              data-testid={`review-output-card-${idx}`}
              onClick={() => onSelectOutput && onSelectOutput(idx)}
              sx={{
                cursor: "pointer",
                borderRadius: 2,
                border: "2px solid",
                borderColor: isSelected ? "primary.main" : isApproved ? "success.light" : "divider",
                bgcolor: isSelected ? "#ffffff" : isApproved ? "#f0fdf4" : "#ffffff",
                boxShadow: isSelected ? "0 4px 12px rgba(139, 92, 246, 0.15)" : "none",
                transition: "all 0.15s ease-in-out",
                "&:hover": {
                  borderColor: isSelected ? "primary.main" : "primary.light",
                },
              }}
            >
              <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
                {/* Header row */}
                <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                  <Stack direction="row" spacing={0.8} alignItems="center">
                    <Box
                      sx={{
                        width: 22,
                        height: 22,
                        borderRadius: "50%",
                        bgcolor: isSelected ? "primary.main" : "grey.200",
                        color: isSelected ? "#ffffff" : "text.secondary",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                      }}
                    >
                      {idx + 1}
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 700, color: "text.primary" }}>
                      {out.output_id ? `Clip: ${out.output_id}` : `Output ${idx + 1}`}
                    </Typography>
                  </Stack>

                  <Stack direction="row" spacing={0.5}>
                    <Chip
                      data-testid={`editorial-status-badge-${idx}`}
                      label={isFailed ? "FAILED" : isApproved ? "EDITORIAL: APPROVED" : "EDITORIAL: NOT_ASSESSED"}
                      size="small"
                      color={isFailed ? "error" : isApproved ? "success" : "default"}
                      sx={{ height: 20, fontSize: "0.65rem", fontWeight: 700 }}
                    />
                  </Stack>
                </Stack>

                {/* Technical Probe Specs & Framing */}
                <Typography variant="caption" sx={{ fontFamily: "monospace", color: "text.secondary", display: "block", mb: 0.8 }}>
                  9:16 ({resolution}) • {dur.toFixed(2)}s • {probe.video_codec || "h264"}/{probe.audio_codec || "aac"}
                </Typography>

                {framingPreset && (
                  <Chip
                    size="small"
                    icon={<IconSparkles size={12} />}
                    label={`Framing: ${framingPreset}`}
                    sx={{ height: 18, fontSize: "0.65rem", fontWeight: 600, mb: 0.8, bgcolor: "#ede9fe", color: "#6d28d9" }}
                  />
                )}

                {/* Editorial Reason if present */}
                {out.source_ranges?.[0]?.editorial_reason && (
                  <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1, fontStyle: "italic", fontSize: "0.72rem" }}>
                    "{out.source_ranges[0].editorial_reason}"
                  </Typography>
                )}

                {/* Warnings */}
                {out.warnings && out.warnings.length > 0 && (
                  <Box sx={{ mb: 1 }}>
                    {out.warnings.map((w, wIdx) => (
                      <Stack key={wIdx} direction="row" spacing={0.5} alignItems="center" sx={{ color: "warning.dark", fontSize: "0.68rem" }}>
                        <IconAlertTriangle size={12} />
                        <span>{w}</span>
                      </Stack>
                    ))}
                  </Box>
                )}

                {/* Freeform Review Notes per Output */}
                <Box sx={{ mt: 1, mb: 1 }} onClick={(e) => e.stopPropagation()}>
                  <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 0.5 }}>
                    <IconNotes size={13} color="#64748b" />
                    <Typography variant="caption" sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.68rem" }}>
                      Editorial Review Notes
                    </Typography>
                  </Stack>
                  <TextField
                    fullWidth
                    multiline
                    minRows={1}
                    maxRows={3}
                    size="small"
                    placeholder="Enter clip feedback or approval notes..."
                    value={noteText}
                    data-testid={`review-notes-input-${idx}`}
                    onChange={(e) => {
                      if (onChangeReviewNotes) {
                        onChangeReviewNotes(out.output_id || outId, e.target.value)
                      }
                    }}
                    sx={{
                      bgcolor: "#f8fafc",
                      "& .MuiInputBase-input": { fontSize: "0.72rem", py: 0.5 },
                    }}
                  />
                </Box>

                <Divider sx={{ my: 1 }} />

                {/* Action buttons */}
                <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                  <Button
                    size="small"
                    variant={isApproved ? "outlined" : "contained"}
                    color={isApproved ? "success" : "primary"}
                    startIcon={isApproved ? <IconCheck size={14} /> : undefined}
                    data-testid={`approve-output-btn-${idx}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onApproveOutput && onApproveOutput(out.output_id || outId)
                    }}
                    sx={{ fontSize: "0.7rem", py: 0.3, px: 1, textTransform: "none", fontWeight: 700 }}
                  >
                    {isApproved ? "Approved" : "Approve Clip"}
                  </Button>

                  <Stack direction="row" spacing={0.5}>
                    <Tooltip title="Refine this clip in Timeline without altering others" arrow>
                      <IconButton
                        size="small"
                        color="primary"
                        data-testid={`refine-output-btn-${idx}`}
                        onClick={(e) => {
                          e.stopPropagation()
                          onRefineOutput && onRefineOutput(out)
                        }}
                        sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}
                      >
                        <IconEdit size={14} />
                      </IconButton>
                    </Tooltip>

                    <Tooltip title="Export MP4" arrow>
                      <IconButton
                        size="small"
                        data-testid={`export-output-btn-${idx}`}
                        onClick={(e) => {
                          e.stopPropagation()
                          onExportOutput && onExportOutput(out)
                        }}
                        sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}
                      >
                        <IconDownload size={14} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          )
        })}
      </Stack>
    </Box>
  )
}
