// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogDrawer: detailed inspector for a selected catalog block.
 * Enforces truthful inspection:
 * - Operable blocks get interactive preview, variable customization, and Insert into Motion.
 * - Inventory-only metadata entries have preview, insert, customize, and export disabled with real blocker reasons.
 */
import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
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
  Tooltip,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconX,
  IconDeviceMobile,
  IconDeviceTv,
  IconExternalLink,
  IconPlus,
  IconAlertTriangle,
  IconShieldLock,
  IconLock,
  IconSend,
  IconMovie,
  IconClockHour4,
} from "@tabler/icons-react"
import http from "../../api/http"
import { DONOR_INTERNALIZED_IDS, UNINDEXED_DONOR_IDS, HYPERFRAMES_CATEGORIES } from "../../utils/catalogOriginals"

export default function CatalogDrawer({
  item,
  open,
  onClose,
  initialAspect = "9:16",
}) {
  const theme = useTheme()
  const navigate = useNavigate()
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
  const isDonorInternalized = DONOR_INTERNALIZED_IDS.has(item.id) || item.integration_status === "INTERNALIZED"
  const isOperational = isDonorInternalized || Boolean(item.isOperational)
  const isUnindexed = UNINDEXED_DONOR_IDS.has(item.id) || Boolean(item.isUnindexed)
  const is6ClipsOriginal = Boolean(item.is6ClipsOriginal) || item.origin === "6CLIPS_ORIGINAL"

  const previewUrl = isOperational
    ? `/api/catalog/blocks/${item.id}/preview?aspect_ratio=${aspect}`
    : null

  let readinessLabel = "QUARANTINED"
  let readinessColor = "warning"
  if (isOperational) {
    readinessLabel = "OPERATIONAL (INTERNALIZED)"
    readinessColor = "success"
  } else if (item.integration_status === "ELIGIBLE_NOT_PORTED") {
    readinessLabel = "VETTED (NOT PORTED)"
    readinessColor = "warning"
  } else if (item.integration_status === "NEEDS_ADAPTATION") {
    readinessLabel = "NEEDS ADAPTATION"
    readinessColor = "warning"
  } else if (item.integration_status === "BLOCKED_DEPENDENCY") {
    readinessLabel = "BLOCKED DEPENDENCY"
    readinessColor = "error"
  } else if (item.integration_status === "BLOCKED_LICENSE" || item.license_status === "RESTRICTED") {
    readinessLabel = "BLOCKED LICENSE"
    readinessColor = "error"
  }

  const handleCustomVarChange = (name, val) => {
    setCustomVars((prev) => ({ ...prev, [name]: val }))
  }

  const handleDispatchAddIntent = async () => {
    if (!isOperational) return
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

  const handleInsertIntoMotion = () => {
    if (!isOperational) return
    navigate(`/motion?insertBlock=${encodeURIComponent(item.id)}&aspect=${aspect}`)
  }

  return (
    <Drawer
      data-testid="catalog-drawer"
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: {
          "data-testid": "catalog-drawer-paper",
          sx: {
            width: { xs: "100%", sm: 680 },
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
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5, flexWrap: "wrap", gap: 0.5 }}>
                <Chip
                  label={item.category?.toUpperCase() || "SCENES"}
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
                <Chip
                  label={isDonorInternalized ? "HyperFrames (Internalized)" : "HyperFrames Donor Original"}
                  size="small"
                  variant="outlined"
                  sx={{ height: 20, fontSize: "0.68rem", fontWeight: 600 }}
                />
                {isUnindexed && (
                  <Chip
                    label="Unindexed Dir"
                    size="small"
                    color="info"
                    variant="outlined"
                    sx={{ height: 20, fontSize: "0.68rem", fontWeight: 600 }}
                  />
                )}
                {item.source_category_missing && (
                  <Chip
                    label="Tags Resolved"
                    size="small"
                    color="warning"
                    variant="outlined"
                    sx={{ height: 20, fontSize: "0.68rem", fontWeight: 600, borderStyle: "dashed" }}
                  />
                )}
              </Stack>

              <Typography variant="h6" sx={{ fontWeight: 800, letterSpacing: "-0.02em" }}>
                {item.title || item.id}
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

        {/* Preview Stage: Operational iframe OR Truthful Quarantine Notice */}
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
              {isOperational ? "STANDALONE PREVIEW" : "PREVIEW QUARANTINED (INVENTORY ONLY)"}
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

          {/* Stage Container */}
          <Box
            sx={{
              width: "100%",
              height: is9x16 ? 320 : 210,
              maxHeight: "40vh",
              borderRadius: "8px",
              overflow: "hidden",
              border: 1,
              borderColor: alpha("#fff", 0.1),
              bgcolor: isOperational ? "#090d16" : "#0f172a",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {isOperational ? (
              <Box
                component="iframe"
                src={previewUrl}
                title={item.title || item.id}
                sx={{
                  width: "100%",
                  height: "100%",
                  border: 0,
                }}
              />
            ) : (
              <Box sx={{ p: 3, textAlign: "center", maxWidth: 440 }}>
                <IconShieldLock size={36} style={{ color: theme.palette.warning.main, marginBottom: 8 }} />
                <Typography variant="subtitle2" sx={{ color: "#f8fafc", fontWeight: 700 }}>
                  Live Preview Disabled
                </Typography>
                <Typography variant="caption" sx={{ color: "#94a3b8", display: "block", mt: 0.5, lineHeight: 1.4 }}>
                  This block is an inventoried donor entry that has not passed offline internalization gates.
                  No untrusted donor code is executed in the browser.
                </Typography>
                {item.blocker_reason && (
                  <Alert severity="warning" sx={{ mt: 1.5, py: 0.5, textAlign: "left", fontSize: "0.75rem" }}>
                    {item.blocker_reason}
                  </Alert>
                )}
              </Box>
            )}
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
              label="Insert into Motion"
              icon={<IconPlus size={14} />}
              iconPosition="start"
              sx={{ color: isOperational ? "primary.main" : "text.disabled" }}
            />
          </Tabs>
        </Box>

        {/* Tab Body */}
        <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
          {tab === 0 && (
            <Stack spacing={2}>
              {!isOperational && (
                <Alert severity={item.integration_status?.includes("BLOCKED") ? "error" : "warning"}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    {item.integration_status || "QUARANTINED"}
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                    {item.blocker_reason || "This block is retained as untrusted donor metadata and is withheld from production execution."}
                  </Typography>
                </Alert>
              )}

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Description
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.5 }}>
                  {item.description || "Self-contained motion block for video compositions."}
                </Typography>
              </Box>

              <Divider />

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                  Contract Disposition & Readiness
                </Typography>
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600, width: 200 }}>Block ID</TableCell>
                        <TableCell><code>{item.id}</code></TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Origin</TableCell>
                        <TableCell>
                          {is6ClipsOriginal ? "6Clips Original Work" : "HyperFrames Donor Original"}
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Integration Status</TableCell>
                        <TableCell>
                          <Chip
                            label={item.integration_status || (isOperational ? "INTERNALIZED" : "UNVERIFIED")}
                            color={isOperational ? "success" : "warning"}
                            size="small"
                            sx={{ height: 18, fontSize: "0.68rem", fontWeight: 700 }}
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>License Status</TableCell>
                        <TableCell>
                          <Chip
                            label={item.license_status || (isOperational ? "VERIFIED_PERMISSIVE" : "UNVERIFIED")}
                            color={item.license_status?.startsWith("VERIFIED") ? "success" : "warning"}
                            size="small"
                            sx={{ height: 18, fontSize: "0.68rem", fontWeight: 700 }}
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 600 }}>Runtime Execution</TableCell>
                        <TableCell>
                          {isOperational
                            ? "Enabled (100% Offline Shipped Package)"
                            : "Disabled (Withheld from Client Execution)"}
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            </Stack>
          )}

          {tab === 1 && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Composition Variables Schema
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  {isOperational
                    ? "Declared variables configurable for independent timeline instances."
                    : "Declared variables metadata from donor manifest (inspection only; binding disabled)."}
                </Typography>
              </Box>

              {item.variables && item.variables.length > 0 ? (
                <TableContainer component={Paper} variant="outlined">
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Variable</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Default</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Description</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {item.variables.map((v) => (
                        <TableRow key={v.name}>
                          <TableCell sx={{ fontWeight: 600 }}><code>{v.name}</code></TableCell>
                          <TableCell>{String(v.default ?? "")}</TableCell>
                          <TableCell sx={{ color: "text.secondary" }}>{v.description || "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" sx={{ color: "text.secondary", py: 2 }}>
                  This block has no customizable variable parameters declared.
                </Typography>
              )}
            </Stack>
          )}

          {tab === 2 && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Legal Provenance & License Review
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  Audited license evidence and source provenance tracking.
                </Typography>
              </Box>

              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableBody>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600, width: 200 }}>Declared License</TableCell>
                      <TableCell>{item.license || "Apache-2.0"}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>License Status</TableCell>
                      <TableCell><code>{item.license_status || "UNVERIFIED"}</code></TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>License Evidence</TableCell>
                      <TableCell>{item.license_evidence || "Awaiting formal review."}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Relative Source Path</TableCell>
                      <TableCell><code>{item.relative_source_path || `registry/blocks/${item.id}`}</code></TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>Source SHA-256</TableCell>
                      <TableCell sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                        {item.source_sha256 || "—"}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Stack>
          )}

          {tab === 3 && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Aspect Ratio Parity (GT-13)
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  Layout compatibility for 9:16 vertical shorts and 16:9 landscape video.
                </Typography>
              </Box>

              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableBody>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600, width: 200 }}>9:16 Vertical</TableCell>
                      <TableCell>
                        <Chip
                          label={item.aspect_9_16 || "CONTAINED_ONLY"}
                          size="small"
                          color={item.aspect_9_16 === "NATIVE" ? "primary" : "default"}
                          sx={{ fontWeight: 700 }}
                        />
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 600 }}>16:9 Landscape</TableCell>
                      <TableCell>
                        <Chip
                          label={item.aspect_16_9 || "CONTAINED_ONLY"}
                          size="small"
                          color={item.aspect_16_9 === "NATIVE" ? "primary" : "default"}
                          sx={{ fontWeight: 700 }}
                        />
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Stack>
          )}

          {tab === 4 && (
            <Stack spacing={2.5}>
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Insert Block into Motion Timeline
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  Dispatches an atomic block insertion into the Motion Studio timeline via the canonical Project/CAS revision pipeline.
                </Typography>
              </Box>

              {!isOperational ? (
                <Alert severity="error" icon={<IconLock size={20} />}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                    Insertion Disabled (Inventory Only Entry)
                  </Typography>
                  <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>
                    {item.blocker_reason || "This block is not verified for runtime distribution and cannot be inserted into project compositions."}
                  </Typography>
                </Alert>
              ) : (
                <Stack spacing={2}>
                  <Button
                    variant="contained"
                    color="primary"
                    size="large"
                    startIcon={<IconMovie size={18} />}
                    onClick={handleInsertIntoMotion}
                    sx={{ fontWeight: 700 }}
                  >
                    Open and Insert in Motion Studio
                  </Button>

                  <Divider sx={{ my: 1 }}>OR DISPATCH CAS INTENT</Divider>

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
                    variant="outlined"
                    color="primary"
                    onClick={handleDispatchAddIntent}
                    disabled={intentLoading}
                    startIcon={intentLoading ? <CircularProgress size={16} /> : <IconSend size={16} />}
                    sx={{ fontWeight: 700 }}
                  >
                    {intentLoading ? "Validating Intent..." : "Dispatch Add-to-Project Intent"}
                  </Button>
                </Stack>
              )}

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
                </Alert>
              )}
            </Stack>
          )}
        </Box>

        {/* Footer Actions */}
        <Box sx={{ p: 2, borderTop: 1, borderColor: "divider" }}>
          <Stack direction="row" spacing={1.5} justifyContent="flex-end">
            {isOperational && previewUrl && (
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
            )}

            {isOperational ? (
              tab !== 4 && (
                <Button
                  variant="contained"
                  size="small"
                  color="primary"
                  startIcon={<IconPlus size={16} />}
                  onClick={() => setTab(4)}
                >
                  Insert into Motion
                </Button>
              )
            ) : (
              <Tooltip title="Actions are disabled for inventory-only blocks until rights-cleared.">
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    disabled
                    startIcon={<IconLock size={16} />}
                  >
                    Insert Disabled
                  </Button>
                </span>
              </Tooltip>
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
