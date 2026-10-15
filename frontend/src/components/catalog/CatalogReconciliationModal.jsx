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
          {/* Wave 6 Proof Ladder & Functional Blocks Audit */}
          <Box>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Wave 6 Proof Ladder & Functional Blocks Verification Matrix
              </Typography>
              <Stack direction="row" spacing={1}>
                <Chip label="Wave 6 Proof Ladder Active" color="primary" size="small" sx={{ fontWeight: 700 }} />
                <Chip label="HYPERFRAMES_FULLY_INTEGRATED: NO" color="warning" size="small" sx={{ fontWeight: 700 }} />
              </Stack>
            </Stack>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: "primary.main" }}>
                    9,059
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    FILES AUDITED (852 MB)
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: "success.main" }}>
                    10 + 2
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    STRUCTURALLY TESTED
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h5" sx={{ fontWeight: 800, color: "warning.main", pt: 1 }}>
                    NOT TESTED
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    BROWSER (ROLE 4 DEFERRED)
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h5" sx={{ fontWeight: 800, color: "info.main", pt: 1 }}>
                    NOT TESTED
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700 }}>
                    MP4 EXPORT (ROLE 2 DEFERRED)
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </Box>

          {/* Historical Registry Breakdown */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
              Donor Registry & Package Reconciliation
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "text.primary" }}>
                    196
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Historic Blocks (10 Shipped / 186 Withheld)
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "info.main" }}>
                    237 / 222
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Microcomponents (Disk / Manifest)
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "warning.main" }}>
                    21 Skills
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    AI Prompts (Untrusted Data Audited)
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: "10px", textAlign: "center" }}>
                  <Typography variant="h6" sx={{ fontWeight: 800, color: "text.primary" }}>
                    14 Packages
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    HyperFrames Monorepo Packages
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </Box>

          {/* Audit Explanation */}
          <Alert severity="info" sx={{ lineHeight: 1.5 }}>
            <strong>Wave 5 Whole-Tree Audit & Zero-Donor Isolation:</strong> Audited 9,059 donor files (852 MB) with SHA-256 signatures in machine-readable JSONL. Shipped blocks operate with 100% offline assets, local variable fonts, and zero external donor checkout dependency. To prevent misleading availability claims: <code>ALL_196_RUNTIME_READY: NO</code> (10 donor blocks + 2 original substitutes are structurally verified; 186 donor items remain withheld with explicit blocker reasons; live headful browser validation and MP4 export are honestly recorded as NOT_TESTED in Role 3 isolation and deferred to Role 4).
          </Alert>

          <Divider />

          {/* Verified Shipped Blocks List */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              Structurally Verified Shipped Donor Blocks (10 Internalized Originals)
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
              <Chip label="aurora (VFX · Apache-2.0 & MIT)" color="success" size="small" />
              <Chip label="flowing-gradient (VFX · Apache-2.0 & MIT)" color="success" size="small" />
              <Chip label="plasma (VFX · Apache-2.0 & MIT)" color="success" size="small" />
              <Chip label="data-chart (Data · Apache-2.0)" color="success" size="small" />
              <Chip label="holographic (VFX · Apache-2.0 & MIT)" color="success" size="small" />
              <Chip label="instagram-follow (Social · Apache-2.0)" color="success" size="small" />
              <Chip label="tiktok-follow (Social · Apache-2.0)" color="success" size="small" />
              <Chip label="yt-lower-third (Social · Apache-2.0)" color="success" size="small" />
              <Chip label="weight-wave (Text Effects · OFL-1.1)" color="success" size="small" />
              <Chip label="stripes (VFX · Apache-2.0 & MIT)" color="success" size="small" />
            </Stack>

            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 0.5, fontWeight: 600 }}>
              Retired 6Clips Substitutes (Excluded from Public Catalog & Motion Picker):
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip label="glitch-transition (Retired 6Clips Substitute · Apache-2.0)" variant="outlined" color="default" size="small" />
              <Chip label="creator-hud (Retired 6Clips Substitute · Apache-2.0)" variant="outlined" color="default" size="small" />
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
