// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogDrawer: detailed inspector for a selected catalog block.
 * Provides interactive 9:16 vs 16:9 preview toggle, variable schema inspector,
 * and comprehensive license and legal provenance attribution.
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
} from "@tabler/icons-react"

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

  if (!item) return null

  const is9x16 = aspect === "9:16"
  const previewUrl = `/api/catalog/blocks/${item.id}/preview?aspect_ratio=${aspect}`
  const posterUrl = `/api/catalog/blocks/${item.id}/poster?aspect_ratio=${aspect}`

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: {
          sx: {
            width: { xs: "100%", sm: 640 },
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
                  label={item.disposition}
                  size="small"
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
              height: is9x16 ? 380 : 240,
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
                    Native Resolution:{" "}
                    <strong>
                      {item.dimensions?.width || 1920} × {item.dimensions?.height || 1080}
                    </strong>
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Dependencies:{" "}
                    <strong>
                      {(item.deps || []).length > 0 ? item.deps.join(", ") : "None (Pure CSS/HTML)"}
                    </strong>
                  </Typography>
                </Stack>
              </Box>
            </Stack>
          )}

          {tab === 1 && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                Configurable Template Variables
              </Typography>
              {(!item.variables || item.variables.length === 0) ? (
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  This block has no external variables. It renders with static or responsive styles.
                </Typography>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: "8px" }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Variable ID</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Label</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Role</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {item.variables.map((v) => (
                        <TableRow key={v.id}>
                          <TableCell sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                            {v.id}
                          </TableCell>
                          <TableCell>{v.type || "string"}</TableCell>
                          <TableCell>{v.label || v.id}</TableCell>
                          <TableCell>{v.role || "content"}</TableCell>
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
                  Software License
                </Typography>
                <Chip
                  label={item.license || "Apache-2.0"}
                  color="success"
                  size="small"
                  sx={{ fontWeight: 700 }}
                />
              </Box>

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Legal Attribution & Provenance
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.5 }}>
                  This component is distributed under the {item.license || "Apache 2.0 License"}.
                  Authored by {item.author || "HyperFrames Authors"}. All trademarks, fonts, and
                  upstream libraries retain their respective original notices.
                </Typography>
              </Box>

              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Vendor Dependencies & Notices
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.5 }}>
                  {(item.deps || []).includes("three.js") && (
                    <div>• <strong>Three.js</strong>: Licensed under the MIT License.</div>
                  )}
                  {(item.deps || []).includes("gsap") && (
                    <div>• <strong>GSAP</strong>: Licensed under GSAP Standard License.</div>
                  )}
                  {(item.deps || []).includes("shaders.iife.js") && (
                    <div>• <strong>Shader Effects</strong>: Licensed under MIT License.</div>
                  )}
                  {(item.deps || []).length === 0 && (
                    <div>• Zero external binary dependencies. Pure web standards.</div>
                  )}
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
            <Button
              variant="contained"
              size="small"
              onClick={onClose}
              color="primary"
            >
              Done
            </Button>
          </Stack>
        </Box>
      </Box>
    </Drawer>
  )
}
