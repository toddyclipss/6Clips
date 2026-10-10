// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState } from "react"
import {
  Box, Stack, Typography, Button, IconButton, TextField,
  Select, MenuItem, FormControl, InputLabel, Chip, CircularProgress,
} from "@mui/material"
import {
  IconScissors,
  IconCrop,
  IconGauge,
  IconArrowsMinimize,
  IconAdjustments,
  IconVolume,
  IconPlayerPlay,
} from "@tabler/icons-react"
import http from "../../api/http"
import useAppStore from "../../store/appStore"

/**
 * Contextual Deterministic Media Tools Workspace.
 * Exposes Trim, Crop, Speed, Reframe, Compress directly in the unified creation workspace.
 */
export default function StudioToolsWorkspace({
  activeAsset,
  onToolSuccess,
}) {
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const [activeTool, setActiveTool] = useState("trim")
  const [running, setRunning] = useState(false)

  // Trim parameters
  const [trimStart, setTrimStart] = useState(0)
  const [trimEnd, setTrimEnd] = useState(5)

  // Speed parameters
  const [speedVal, setSpeedVal] = useState(1.5)

  // Crop / Reframe
  const [aspect, setAspect] = useState("9:16")

  const handleExecute = async () => {
    if (!activeAsset) {
      showSnackbar("Please select a video asset first", "warning")
      return
    }

    setRunning(true)
    try {
      let endpoint = ""
      let payload = { video_id: activeAsset.id }

      if (activeTool === "trim") {
        endpoint = "/api/tools/trim/from-asset"
        payload = { ...payload, start_seconds: trimStart, end_seconds: trimEnd }
      } else if (activeTool === "speed") {
        endpoint = "/api/tools/speed/from-asset"
        payload = { ...payload, speed: speedVal, keep_pitch: true }
      } else if (activeTool === "reframe") {
        endpoint = "/api/tools/reframe/from-asset"
        payload = { ...payload, aspect_ratio: aspect }
      } else {
        endpoint = "/api/tools/compress/from-asset"
        payload = { ...payload, resolution: "original", level: "high" }
      }

      const res = await http.post(endpoint, payload)
      showSnackbar(`Tool job queued: ${res.data?.job_id || "Success"}`, "success")
      if (onToolSuccess) onToolSuccess(res.data)
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    } finally {
      setRunning(false)
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
        borderTop: "1px solid",
        borderColor: "divider",
        p: 2,
        overflowY: "auto",
      }}
    >
      {/* Header & Tool Tabs */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
        <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", color: "text.secondary" }}>
          Deterministic Media Tools
        </Typography>

        <Stack direction="row" spacing={0.5}>
          {[
            { id: "trim", label: "Trim", icon: <IconScissors size={14} /> },
            { id: "speed", label: "Speed", icon: <IconGauge size={14} /> },
            { id: "reframe", label: "Reframe", icon: <IconCrop size={14} /> },
            { id: "compress", label: "Compress", icon: <IconArrowsMinimize size={14} /> },
          ].map((tool) => (
            <Button
              key={tool.id}
              size="small"
              variant={activeTool === tool.id ? "contained" : "outlined"}
              startIcon={tool.icon}
              onClick={() => setActiveTool(tool.id)}
              sx={{
                height: 26,
                fontSize: "0.72rem",
                px: 1.2,
                borderRadius: 1.5,
              }}
            >
              {tool.label}
            </Button>
          ))}
        </Stack>
      </Stack>

      {/* Tool Parameters */}
      <Box sx={{ flex: 1, bgcolor: "#f8fafc", p: 1.5, borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
        <Stack direction="row" spacing={2} alignItems="center">
          {activeTool === "trim" && (
            <>
              <TextField
                size="small"
                type="number"
                label="Start (sec)"
                value={trimStart}
                onChange={(e) => setTrimStart(Number(e.target.value))}
                sx={{ width: 120, "& .MuiInputBase-input": { fontSize: "0.78rem" } }}
              />
              <TextField
                size="small"
                type="number"
                label="End (sec)"
                value={trimEnd}
                onChange={(e) => setTrimEnd(Number(e.target.value))}
                sx={{ width: 120, "& .MuiInputBase-input": { fontSize: "0.78rem" } }}
              />
            </>
          )}

          {activeTool === "speed" && (
            <FormControl size="small" sx={{ width: 140 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Playback Speed</InputLabel>
              <Select
                value={speedVal}
                label="Playback Speed"
                onChange={(e) => setSpeedVal(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value={0.5}>0.5x (Slow)</MenuItem>
                <MenuItem value={1.0}>1.0x (Normal)</MenuItem>
                <MenuItem value={1.25}>1.25x (Fast)</MenuItem>
                <MenuItem value={1.5}>1.5x (Accelerated)</MenuItem>
                <MenuItem value={2.0}>2.0x (Double)</MenuItem>
              </Select>
            </FormControl>
          )}

          {activeTool === "reframe" && (
            <FormControl size="small" sx={{ width: 140 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Target Aspect</InputLabel>
              <Select
                value={aspect}
                label="Target Aspect"
                onChange={(e) => setAspect(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value="9:16">9:16 (Vertical)</MenuItem>
                <MenuItem value="16:9">16:9 (Horizontal)</MenuItem>
              </Select>
            </FormControl>
          )}

          {activeTool === "compress" && (
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              High-efficiency H.264 compression targeting ~25MB ceiling with audio normalization.
            </Typography>
          )}

          <Button
            size="small"
            variant="contained"
            disabled={running}
            startIcon={running ? <CircularProgress size={14} color="inherit" /> : <IconPlayerPlay size={15} />}
            onClick={handleExecute}
            sx={{
              height: 32,
              px: 2,
              fontSize: "0.75rem",
              fontWeight: 700,
              borderRadius: 1.5,
              ml: "auto",
            }}
          >
            {running ? "Processing…" : `Run ${activeTool}`}
          </Button>
        </Stack>
      </Box>
    </Box>
  )
}
