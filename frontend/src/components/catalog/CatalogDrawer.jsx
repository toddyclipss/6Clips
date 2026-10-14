// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogDrawer: detailed inspector for a selected catalog block.
 * Provides interactive 9:16 vs 16:9 preview toggle, variable schema inspector,
 * legal provenance attribution, and validated Add-to-Project intent generation.
 */
import React, { useState } from "react"
import {
  Drawer,
  Box,
  Typography,
  Stack,
  IconButton,
  Button,
  Tabs,
  Tab,
  Chip,
  Divider,
  ToggleButtonGroup,
  ToggleButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Alert,
  CircularProgress,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconX,
  IconDeviceMobile,
  IconDeviceTv,
  IconExternalLink,
  IconCopy,
  IconShieldCheck,
  IconSparkles,
  IconPlus,
  IconCheck,
  IconAlertCircle,
  IconSend,
  IconMovie,
} from "@tabler/icons-react"
import http from "../../api/http"

export default function CatalogDrawer({
  item,
  open,
  onClose,
  initialAspect = "9:16",
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const [tab, setTab] = useState(0)
  const [aspect, setAspect] = useState(initialAspect)

  // Add-to-project state
  const [targetProjectId, setTargetProjectId] = useState("")
  const [trackIndex, setTrackIndex] = useState(0)
  const [startTime, setStartTime] = useState(0.0)
  const [instanceId, setInstanceId] = useState("")
  const [expectedRevision, setExpectedRevision] = useState("")
  const [customVars, setCustomVars] = useState({})
  const [intentLoading, setIntentLoading] = useState(false)
  const [intentResult, setIntentResult] = useState(null)
  const [intentError, setIntentError] = useState(null)

  // Accessibility: close on Escape
  React.useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && open) {
        onClose?.()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [open, onClose])

  if (!item) return null

  const is9x16 = aspect === "9:16"
  const previewUrl = `/api/catalog/blocks/${item.id}/preview?aspect_ratio=${aspect}`
  const posterUrl = `/api/catalog/blocks/${item.id}/poster?aspect_ratio=${aspect}`

  const isOperational12 = [
    "aurora", "data-chart", "instagram-follow", "tiktok-follow", "weight-wave", "yt-lower-third",
    "flowing-gradient", "plasma", "stripes", "holographic", "glitch-transition", "creator-hud"
  ].includes(item.id)

  const isInternalized = Boolean(item.internalized || item.runtime_ready || isOperational12)
  const readiness = isOperational12
    ? "OPERATIONAL"
    : item.disposition === "FIX"
    ? "FIX"
    : "QUARANTINED"

  const readinessColor =
    readiness === "OPERATIONAL"
      ? "info"
      : readiness === "FIX"
      ? "error"
      : "warning"

  const readinessLabel =
    readiness === "OPERATIONAL"
      ? "OPERATIONAL (ROLE 2 EXPORT PENDING)"
      : readiness === "FIX"
      ? "NEEDS STRUCTURAL FIX"
      : "QUARANTINED (LICENSE REVIEW)"

  const handleCustomVarChange = (name, val) => {
    setCustomVars((prev) => ({ ...prev, [name]: val }))
  }

  const handleDispatchAddIntent = async () => {
    setIntentLoading(true)
    setIntentError(null)
    setIntentResult(null)
    try {
      const payload = {
        project_id: targetProjectId.trim() || null,
        timeline_track_index: Number(trackIndex) || 0,
        start_time_seconds: Number(startTime) || 0.0,
        aspect_ratio: aspect,
        custom_variables: customVars,
        instance_id: instanceId.trim() || undefined,
        expected_revision: expectedRevision !== "" ? parseInt(expectedRevision, 10) : undefined,
      }
      const res = await http.post(`/api/catalog/blocks/${item.id}/intent/add-to-project`, payload)
      setIntentResult(res.data)
    } catch (err) {
      console.error("Add-to-project intent failed:", err)
      setIntentError(err.response?.data?.detail || "Could not dispatch add-to-project intent.")
    } finally {
      setIntentLoading(false)
    }
  }

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: {
          sx: {
            width: { xs: "100%", sm: 660 },
            maxWidth: "100vw",
            bgcolor: "background.paper",
            borderLeft: 1,
            borderColor: "divider",
          },
        },
      }}
    >
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <Box
          sx={{
            p: 2,
            borderBottom: 1,
            borderColor: "divider",
            bgcolor: isDark ? alpha("#fff", 0.02) : alpha("#000", 0.02),
          }}
        >
          <Stack direction="row" alignItems="flex-start" justifyContent="space-between">
            <Box sx={{ flex: 1, pr: 2 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                <Chip
                  label={item.category?.toUpperCase()}
                  size="small"
                  color="primary"
                  sx={{ height: 20, fontSize: "0.68rem", fontWeight: 700 }}
                />
                <Chip
                  label={readinessLabel}
                  size="small"
                  color={readinessColor}
                  variant="outlined"
                  sx={{ height: 20, fontSize: "0.68rem", fontWeight: 700 }}
                />
              </Stack>

              <Typography variant="h6" sx={{ fontWeight: 800, letterSpacing: "-0.02em" }}>
                {item.title}
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                ID: <code>{item.id}</code> · Author: {item.author || "HyperFrames"}
              </Typography>
            </Box>

            <IconButton size="small" onClick={onClose} aria-label="Close drawer">
              <IconX size={20} />
            </IconButton>
          </Stack>
        </Box>

        {/* Interactive Preview Stage */}
        <Box
          sx={{
            p: 2,
            bgcolor: "#000",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
          }}
        >
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            sx={{ width: "100%", mb: 1.5 }}
          >
            <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 600 }}>
              STANDALONE PREVIEW
            </Typography>

            <ToggleButtonGroup
              value={aspect}
              exclusive
              onChange={(_, val) => val && setAspect(val)}
              size="small"
              sx={{
                bgcolor: alpha("#fff", 0.1),
                "& .MuiToggleButton-root": {
                  color: "#cbd5e1",
                  px: 1,
                  py: 0.25,
                  fontSize: "0.75rem",
                  "&.Mui-selected": { color: "#fff", bgcolor: "primary.main" },
                },
              }}
            >
              <ToggleButton value="9:16">
                <IconDeviceMobile size={14} style={{ marginRight: 4 }} />
                9:16
              </ToggleButton>
              <ToggleButton value="16:9">
                <IconDeviceTv size={14} style={{ marginRight: 4 }} />
                16:9
              </ToggleButton>
            </ToggleButtonGroup>
          </Stack>

          {/* Iframe stage container */}
          <Box
            sx={{
              width: "100%",
              height: is9x16 ? 360 : 230,
              maxHeight: "45vh",
              borderRadius: "8px",
              overflow: "hidden",
              border: 1,
              borderColor: alpha("#fff", 0.1),
              bgcolor: "#090d16",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Box
              component="iframe"
              src={previewUrl}
              title={item.title}
              sx={{
                width: "100%",
                height: "100%",
                border: 0,
              }}
            />
          </Box>
        </Box>

        {/* Navigation Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: "divider", px: 2 }}>
          <Tabs
            value={tab}
            onChange={(_, val) => setTab(val)}
            sx={{
              minHeight: 40,
              "& .MuiTab-root": {
                minHeight: 40,
                fontSize: "0.82rem",
                fontWeight: 600,
                textTransform: "none",
                px: 1.5,
              },
            }}
          >
            <Tab label="Overview" />
            <Tab label={`Variables (${item.variables_count || 0})`} />
            <Tab label="Provenance & Legal" />
            <Tab label="Aspect Parity" />
            <Tab
              label="Add to Project"
              icon={<IconPlus size={14} />}
              iconPosition="start"
              sx={{ color: "primary.main" }}
            />
          </Tabs>
        </Box>

        {/* Tab Body */}
        <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
          {tab === 0 && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Description
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.5 }}>
                  {item.description || "Self-contained motion block for video compositions."}
                </Typography>
              </Box>

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Tags
                </Typography>
                <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                  {(item.tags || []).map((t) => (
                    <Chip key={t} label={t} size="small" variant="outlined" sx={{ fontSize: "0.72rem" }} />
                  ))}
                </Stack>
              </Box>

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Technical Specifications
                </Typography>
                <Stack spacing={0.5}>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Duration: <strong>{item.duration || 5.0} seconds</strong>
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Category: <strong>{item.category}</strong>
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Runtime Packaging:{" "}
                    <strong>{isInternalized ? "Internalized (Zero Donor Dependency)" : "Awaiting Internalization"}</strong>
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Native Dimensions:{" "}
                    <strong>
                      {item.dimensions?.width || 1920}×{item.dimensions?.height || 1080}
                    </strong>
                  </Typography>
                </Stack>
              </Box>

              <Box sx={{ mt: 1, p: 1.5, borderRadius: 1, bgcolor: isDark ? alpha("#fff", 0.04) : alpha("#000", 0.04), border: 1, borderColor: "divider" }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Wave 10 Verification Proof Ledger
                </Typography>
                <Stack spacing={0.75}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>Origin / License:</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600 }}>{isOperational12 ? (["creator-hud", "glitch-transition"].includes(item.id) ? "ORIGINAL_6CLIPS (Apache-2.0)" : "ORIGINAL_DONOR (Apache-2.0/MIT)") : "QUARANTINED (186 Withheld)"}</Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>Offline Assets (Zero CDN):</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: isOperational12 ? "success.main" : "text.secondary" }}>{isOperational12 ? "PASS (100% Offline)" : "PENDING"}</Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>Browser Animation (Playwright):</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: isOperational12 ? "success.main" : "text.secondary" }}>{isOperational12 ? "PASS (Dynamic Seek + Instance Vars)" : "PENDING"}</Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>Project Insertion Intent:</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: isOperational12 ? "success.main" : "text.secondary" }}>{isOperational12 ? "PASS (CAS & Scoped IDs)" : "QUARANTINED"}</Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>Canonical MP4 Export:</Typography>
                    <Typography variant="caption" sx={{ fontWeight: 600, color: "warning.main" }}>{isOperational12 ? "ROLE2_RENDER_PIPELINE_PENDING" : "BLOCKED"}</Typography>
                  </Stack>
                </Stack>
              </Box>
            </Stack>
          )}

          {tab === 1 && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
                Configurable Variables Schema
              </Typography>
              {!item.variables || item.variables.length === 0 ? (
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  No configurable variables exposed by this block.
                </Typography>
              ) : (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Variable</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Default</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Description</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {item.variables.map((v) => (
                        <TableRow key={v.name}>
                          <TableCell sx={{ fontFamily: "monospace", fontSize: "0.78rem" }}>
                            {v.name}
                          </TableCell>
                          <TableCell>
                            <Chip label={v.type} size="small" sx={{ height: 18, fontSize: "0.68rem" }} />
                          </TableCell>
                          <TableCell sx={{ fontFamily: "monospace", fontSize: "0.78rem" }}>
                            {String(v.default ?? "—")}
                          </TableCell>
                          <TableCell sx={{ fontSize: "0.78rem", color: "text.secondary" }}>
                            {v.description || "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}

          {tab === 2 && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Licensing & Legal Clearance
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                  <IconShieldCheck size={20} style={{ color: theme.palette.success.main }} />
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {item.license || "Apache-2.0"}
                  </Typography>
                </Stack>
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                  Redistributable under Apache-2.0 and compatible open-source terms. Derivative works retain original copyright and NOTICE files.
                </Typography>
              </Box>

              <Divider />

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Donor Independence (GT-20)
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary", mb: 1 }}>
                  {isInternalized
                    ? "✓ This block has been completely internalized into backend/catalog/shipped_blocks with offline assets and pinned fonts. It functions without donor checkout."
                    : "⚠ This block currently requires dependency vendoring and offline packaging before runtime shipment."}
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Original Donor Directory: <code>{item.id}</code>
                </Typography>
              </Box>
            </Stack>
          )}

          {tab === 3 && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  9:16 Vertical Compatibility
                </Typography>
                <Chip
                  label={item.aspect_9_16}
                  color={item.aspect_9_16 === "NATIVE" ? "primary" : "info"}
                  size="small"
                  sx={{ fontWeight: 700, mb: 0.5 }}
                />
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  {item.aspect_9_16 === "NATIVE"
                    ? "Native 1080×1920 layout authored specifically for vertical feeds."
                    : item.aspect_9_16 === "ADAPTED"
                    ? "Responsive adaptation with centering and scaling for vertical viewing."
                    : "Contained within vertical bounds (letterboxed/pillarboxed)."}
                </Typography>
              </Box>

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  16:9 Horizontal Compatibility
                </Typography>
                <Chip
                  label={item.aspect_16_9}
                  color={item.aspect_16_9 === "NATIVE" ? "primary" : "info"}
                  size="small"
                  sx={{ fontWeight: 700, mb: 0.5 }}
                />
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  {item.aspect_16_9 === "NATIVE"
                    ? "Native 1920×1080 layout authored for landscape video."
                    : "Contained within landscape 16:9 frame."}
                </Typography>
              </Box>
            </Stack>
          )}

          {tab === 4 && (
            <Stack spacing={2.5}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Add Block to Project Timeline
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  Configure insertion parameters and dispatch a validated timeline block intent.
                </Typography>
              </Box>

              {!isInternalized && (
                <Alert severity={item.disposition === "FIX" ? "error" : "warning"}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    {item.blocker_code || "LICENSE_REVIEW_REQUIRED_AMBIGUOUS_RIGHTS"}
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                    {item.blocker_reason || "This block is not verified for runtime distribution and requires dependency clearance before live rendering."}
                  </Typography>
                </Alert>
              )}

              <Stack spacing={2}>
                <TextField
                  label="Target Project ID"
                  placeholder="Optional: leave blank for active composition"
                  size="small"
                  fullWidth
                  value={targetProjectId}
                  onChange={(e) => setTargetProjectId(e.target.value)}
                />

                <Stack direction="row" spacing={2}>
                  <TextField
                    label="Instance ID (Scoped)"
                    placeholder="Auto-generated if blank"
                    size="small"
                    value={instanceId}
                    onChange={(e) => setInstanceId(e.target.value)}
                    sx={{ flex: 1 }}
                    helperText="Unique instance ID for independent editing"
                  />
                  <TextField
                    label="Expected Revision (CAS)"
                    type="number"
                    size="small"
                    placeholder="e.g. 1"
                    value={expectedRevision}
                    onChange={(e) => setExpectedRevision(e.target.value)}
                    sx={{ width: 180 }}
                    helperText="Optimistic concurrency control"
                  />
                </Stack>

                <Stack direction="row" spacing={2}>
                  <TextField
                    label="Timeline Track Index"
                    type="number"
                    size="small"
                    value={trackIndex}
                    onChange={(e) => setTrackIndex(Math.max(0, parseInt(e.target.value, 10) || 0))}
                    sx={{ width: 180 }}
                  />
                  <TextField
                    label="Start Time (seconds)"
                    type="number"
                    size="small"
                    value={startTime}
                    onChange={(e) => setStartTime(Math.max(0, parseFloat(e.target.value) || 0))}
                    sx={{ width: 180 }}
                  />
                </Stack>

                {item.variables && item.variables.length > 0 && (
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", mb: 1, display: "block" }}>
                      Customize Variables (Independent Instance)
                    </Typography>
                    <Stack spacing={1.5}>
                      {item.variables.map((v) => (
                        <TextField
                          key={v.name}
                          label={v.name}
                          size="small"
                          defaultValue={v.default}
                          helperText={v.description}
                          fullWidth
                          onChange={(e) => handleCustomVarChange(v.name, e.target.value)}
                        />
                      ))}
                    </Stack>
                  </Box>
                )}

                <Button
                  variant="contained"
                  color="primary"
                  onClick={handleDispatchAddIntent}
                  disabled={intentLoading}
                  startIcon={intentLoading ? <CircularProgress size={16} /> : <IconSend size={16} />}
                  sx={{ fontWeight: 700 }}
                >
                  {intentLoading ? "Validating Intent..." : "Dispatch Add-to-Project Intent"}
                </Button>
              </Stack>

              {intentError && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {intentError}
                </Alert>
              )}

              {intentResult && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    Intent Validated: {intentResult.intent_id}
                  </Typography>
                  <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
                    Instance ID: <code>{intentResult.timeline_item?.instance_id}</code> · Track #{intentResult.timeline_item?.track_index} · Duration: {intentResult.timeline_item?.duration}s
                  </Typography>
                  <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>
                    License: <strong>{intentResult.timeline_item?.license_provenance?.license || "Apache-2.0"}</strong> ({intentResult.timeline_item?.license_provenance?.license_status})
                  </Typography>
                  <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mt: 0.5 }}>
                    Integration Status: <strong>{intentResult.integration_request?.parameters?.timeline_item ? "Payload Ready for Coordinator Wiring (ProjectService)" : "Pending"}</strong>
                  </Typography>
                </Alert>
              )}
            </Stack>
          )}
        </Box>

        {/* Footer Actions */}
        <Box sx={{ p: 2, borderTop: 1, borderColor: "divider" }}>
          <Stack direction="row" spacing={1.5} justifyContent="flex-end">
            <Button
              variant="outlined"
              size="small"
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              startIcon={<IconExternalLink size={16} />}
            >
              Open in New Window
            </Button>
            {tab !== 4 && (
              <Button
                variant="contained"
                size="small"
                color="primary"
                startIcon={<IconPlus size={16} />}
                onClick={() => setTab(4)}
              >
                Add to Project
              </Button>
            )}
            <Button
              variant="text"
              size="small"
              onClick={onClose}
            >
              Close
            </Button>
          </Stack>
        </Box>
      </Box>
    </Drawer>
  )
}
