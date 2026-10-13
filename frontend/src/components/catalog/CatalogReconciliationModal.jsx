// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogReconciliationModal: displays the evidence-backed inventory
 * audit across 196 historical blocks, 170 aggregate items, 222 microcomponents,
 * 8 examples, and Wave 3 factual readiness counts.
 */
import React from "react"
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Stack,
  Button,
  Grid,
  Paper,
  Chip,
  Divider,
  Alert,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconReportAnalytics,
  IconShieldCheck,
  IconCheck,
  IconAlertCircle,
  IconDeviceTv,
  IconDeviceMobile,
} from "@tabler/icons-react"

export default function CatalogReconciliationModal({
  open,
  onClose,
  reconciliationData,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const recon = reconciliationData?.reconciliation || {
    historical_block_dirs: 196,
    aggregate_manifest_blocks: 170,
    unbundled_block_dirs: 26,
    historical_component_dirs: 236,
    aggregate_components: 222,
    historical_example_dirs: 8,
    aggregate_examples: 8,
  }

  const wave3 = reconciliationData?.wave3_reconciliation || {
    inventoried: 196,
    internalized: 6,
    render_tested: 6,
    browser_verified: 6,
    license_blocked: 165,
    ready: 6,
    not_ready: 190,
  }

  const factual = reconciliationData?.factual_counts || {
    INVENTORIED: 196,
    INTERNALIZED: 6,
    RENDER_TESTED: 6,
    BROWSER_VERIFIED: 6,
    LICENSE_BLOCKED: 165,
    READY: 6,
    NOT_READY: 190,
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            borderRadius: "16px",
            bgcolor: "background.paper",
          },
        },
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box
            sx={{
              p: 1,
              borderRadius: "10px",
              bgcolor: alpha(theme.palette.primary.main, 0.1),
              color: "primary.main",
              display: "flex",
            }}
          >
            <IconReportAnalytics size={24} />
          </Box>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              HyperFrames Catalog Inventory Reconciliation & Audit
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Evidence-backed reconciliation of historical assets, microcomponents, and Wave 3 runtime readiness
            </Typography>
          </Box>
        </Stack>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 3 }}>
        <Stack spacing={3}>
          {/* Wave 3 Factual Readiness Cards */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
              Wave 3 Factual Readiness Audit
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: "primary.main" }}>
                    {factual.INVENTORIED}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    INVENTORIED
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: "success.main" }}>
                    {factual.READY}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    READY (Internalized)
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: "warning.main" }}>
                    {factual.LICENSE_BLOCKED}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    LICENSE / CDN BLOCKED
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: "error.main" }}>
                    {factual.NOT_READY}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    NOT READY
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </Box>

          {/* Historical Reconciliation */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
              Historical Registry Breakdown
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "text.primary" }}>
                    {recon.historical_block_dirs}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Block Directories
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "info.main" }}>
                    {recon.aggregate_manifest_blocks}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    In Donor Registry.json
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "warning.main" }}>
                    {recon.unbundled_block_dirs}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Unbundled Shaders
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "text.primary" }}>
                    {recon.aggregate_components}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Microcomponents
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </Box>

          {/* Audit Explanation */}
          <Alert severity="info" sx={{ lineHeight: 1.5 }}>
            <strong>Why 171 were labeled SHIP in Wave 2:</strong> In Wave 2, blocks present in the donor <code>registry.json</code> were given a blanket "SHIP" label. However, only 6 core blocks were truly internalized into <code>backend/catalog/shipped_blocks/</code> with offline dependencies and pinned licenses. The remaining 165 blocks depend on live <code>cdn.jsdelivr.net</code> GSAP scripts or unverified licenses and cannot render offline. Wave 3 reclassifies them as <strong>UNVERIFIED</strong> to guarantee truthful runtime claims.
          </Alert>

          <Divider />

          {/* Internalized Blocks List */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              6 Internalized, Shipped Blocks (100% Offline Capable)
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label="aurora (WebGL/Shader)" color="success" size="small" />
              <Chip label="data-chart (SVG Charts)" color="success" size="small" />
              <Chip label="instagram-follow (CTA)" color="success" size="small" />
              <Chip label="tiktok-follow (CTA)" color="success" size="small" />
              <Chip label="weight-wave (Kinetic Type)" color="success" size="small" />
              <Chip label="yt-lower-third (Broadcast)" color="success" size="small" />
            </Stack>
          </Box>
        </Stack>
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} variant="contained" color="primary">
          Close Report
        </Button>
      </DialogActions>
    </Dialog>
  )
}
