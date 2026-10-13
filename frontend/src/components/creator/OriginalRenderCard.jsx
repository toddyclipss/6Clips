// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 ViralMint Contributors
import React, { useState } from "react"
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  Stack,
  Alert,
  CircularProgress,
  Divider,
} from "@mui/material"
import {
  IconMovie,
  IconMicrophone,
  IconSparkles,
  IconCheck,
  IconAlertCircle,
  IconPlayerPlay,
} from "@tabler/icons-react"

export default function OriginalRenderCard({ spec, onRenderComplete }) {
  const [rendering, setRendering] = useState(false)
  const [renderError, setRenderError] = useState(null)
  const [renderResult, setRenderResult] = useState(spec?.rendered_result || null)
  const [currentSpec, setCurrentSpec] = useState(spec)

  const handleRenderWithTTS = async () => {
    setRendering(true)
    setRenderError(null)
    try {
      // Authorize procedural TTS and trigger render
      const updatedSpec = {
        ...currentSpec,
        voice_requirement: "PROCEDURAL_SYNTHESIS_ALLOWED",
      }
      const response = await fetch("/api/original/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec: updatedSpec }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Failed to render composition")
      }
      setCurrentSpec(data.spec)
      if (data.spec?.rendered_result) {
        setRenderResult(data.spec.rendered_result)
        if (onRenderComplete) onRenderComplete(data.spec)
      } else if (data.status === "WAITING_FOR_INPUT") {
        setRenderError(data.status_reason)
      }
    } catch (err) {
      setRenderError(err.message)
    } finally {
      setRendering(false)
    }
  }

  const isRendered = currentSpec?.status === "RENDERED" && renderResult

  return (
    <Card sx={{ mt: 2, border: "1px solid", borderColor: isRendered ? "success.main" : "divider" }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
          <Typography variant="h6" sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <IconMovie size={20} />
            Original Video Production
          </Typography>
          <Chip
            label={currentSpec?.status || "PLANNING_ARTIFACT_DRAFT"}
            color={
              isRendered
                ? "success"
                : currentSpec?.status === "WAITING_FOR_INPUT"
                ? "warning"
                : "default"
            }
            size="small"
            sx={{ fontWeight: 700 }}
          />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={2}>
          {currentSpec?.status_reason}
        </Typography>

        {renderError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {renderError}
          </Alert>
        )}

        {isRendered ? (
          <Box sx={{ p: 2, bgcolor: "background.default", borderRadius: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" mb={1}>
              <IconCheck size={18} color="#10B981" />
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                Authentic MP4 Render Complete
              </Typography>
            </Stack>
            <Typography variant="caption" display="block" color="text.secondary">
              Resolution: {renderResult.width}x{renderResult.height} ({renderResult.aspect_ratio})
            </Typography>
            <Typography variant="caption" display="block" color="text.secondary">
              Duration: {renderResult.duration_seconds}s | Audio:{" "}
              {renderResult.probe_stats?.has_audio ? "Present" : "Muted"}
            </Typography>
            <Typography variant="caption" display="block" color="text.secondary" sx={{ wordBreak: "break-all" }}>
              Path: {renderResult.video_path}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<IconPlayerPlay size={16} />}
              sx={{ mt: 1.5, textTransform: "none" }}
              onClick={() => {
                // Navigate to Motion Review
                window.location.hash = `#/motion?spec_id=${currentSpec.spec_id}`
              }}
            >
              Open in Motion Review
            </Button>
          </Box>
        ) : (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button
              variant="contained"
              color="primary"
              size="small"
              startIcon={rendering ? <CircularProgress size={16} color="inherit" /> : <IconSparkles size={16} />}
              disabled={rendering}
              onClick={handleRenderWithTTS}
              sx={{ textTransform: "none", fontWeight: 600 }}
            >
              {rendering ? "Rendering MP4..." : "Authorize TTS & Render Video"}
            </Button>
            <Typography variant="caption" color="text.secondary">
              Or upload voice narration audio to maintain 100% creator voice.
            </Typography>
          </Stack>
        )}
      </CardContent>
    </Card>
  )
}
