// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Catalog — HyperFrames feature catalog with single source-of-truth state machine:
 * LOADING, READY_ITEMS, EMPTY_FILTER, ERROR_RETRYABLE, OFFLINE_BLOCKED, INVENTORY_UNAVAILABLE.
 * Truthfully exposes:
 * - 196 original donor entries as metadata when backend v1 manifest is present.
 * - Exactly 10 internalized donor blocks + 2 separate 6Clips-original blocks = 12 operational blocks.
 * - Explicit views: Available now (12), All original HyperFrames (196 verified), Needs work, Blocked.
 * - Honest error & disclosure if backend inventory is pending Agent 1 integration.
 */
import React, { useState, useEffect, useCallback, useMemo, useRef } from "react"
import {
  Box,
  Container,
  Typography,
  Stack,
  Button,
  Grid,
  CircularProgress,
  Pagination,
  Alert,
  AlertTitle,
  Chip,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconReportAnalytics,
  IconFilter,
  IconRotateClockwise,
  IconWifiOff,
  IconArchive,
  IconAlertTriangle,
  IconDatabase,
} from "@tabler/icons-react"
import http from "../api/http"
import useDocumentTitle from "../hooks/useDocumentTitle"
import PageHero from "../components/PageHero"
import CatalogFacetBar from "../components/catalog/CatalogFacetBar"
import CatalogCard from "../components/catalog/CatalogCard"
import CatalogDrawer from "../components/catalog/CatalogDrawer"
import CatalogReconciliationModal from "../components/catalog/CatalogReconciliationModal"
import {
  fetchBackendInventory,
  getStage1Fixture,
  reconcileCatalog,
  SIXCLIPS_ORIGINAL_BLOCKS,
} from "../utils/catalogInventory"

const ITEMS_PER_PAGE = 24

export default function Catalog() {
  useDocumentTitle("Catalog")
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const [search, setSearch] = useState("")
  const [category, setCategory] = useState("all")
  const [aspectRatio, setAspectRatio] = useState("9:16")
  const [viewMode, setViewMode] = useState("AVAILABLE_NOW") // AVAILABLE_NOW | ALL_ORIGINAL_196 | NEEDS_WORK | BLOCKED
  const [page, setPage] = useState(1)

  // Manifest & Backend Inventory state
  const [manifestState, setManifestState] = useState({
    status: "LOADING", // LOADING | VERIFIED_LIVE | STAGE1_FIXTURE | UNAVAILABLE_BACKEND_PENDING | BLOCKED_INVENTORY_RECONCILIATION | OFFLINE_BLOCKED
    manifest: null,
    error: null,
    disclosure: null,
  })

  // Selected item for drawer
  const [selectedBlock, setSelectedBlock] = useState(null)
  const [showReconModal, setShowReconModal] = useState(false)
  const [reconciliationData, setReconciliationData] = useState(null)

  const abortControllerRef = useRef(null)

  // Initial load of backend inventory
  const loadInventory = useCallback(async () => {
    // Check if offline
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setManifestState({
        status: "OFFLINE_BLOCKED",
        manifest: null,
        error: "Network connection is offline. Please check your connectivity.",
        disclosure: null,
      })
      return
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller

    setManifestState((prev) => ({ ...prev, status: "LOADING", error: null }))

    try {
      const result = await fetchBackendInventory(controller.signal)
      if (result.status === "VERIFIED_LIVE") {
        setManifestState({
          status: "VERIFIED_LIVE",
          manifest: result.manifest,
          error: null,
          disclosure: null,
        })
      } else if (result.status === "BLOCKED_INVENTORY_RECONCILIATION") {
        setManifestState({
          status: "BLOCKED_INVENTORY_RECONCILIATION",
          manifest: null,
          error: result.error,
          disclosure: null,
        })
      } else {
        // Backend unavailable (pending Agent 1 merge). Check query param ?fixture=1
        const urlParams = new URLSearchParams(window.location.search)
        if (urlParams.get("fixture") === "1" || urlParams.get("fixture") === "true") {
          const fixture = getStage1Fixture()
          setManifestState(fixture)
        } else {
          setManifestState({
            status: "UNAVAILABLE_BACKEND_PENDING",
            manifest: null,
            error: result.error,
            disclosure: null,
          })
        }
      }
    } catch (err) {
      if (controller.signal.aborted) return
      console.warn("Catalog inventory fetch notice:", err)
      setManifestState({
        status: "UNAVAILABLE_BACKEND_PENDING",
        manifest: null,
        error: "Backend inventory manifest is pending Agent 1 integration merge.",
        disclosure: null,
      })
    }
  }, [])

  useEffect(() => {
    loadInventory()
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [loadInventory])

  // Fetch reconciliation audit summary once
  useEffect(() => {
    http.get("/api/catalog/reconciliation")
      .then((res) => setReconciliationData(res.data))
      .catch((err) => console.debug("Reconciliation fetch error:", err))
  }, [])

  const handleActivateStage1Fixture = () => {
    const fixture = getStage1Fixture()
    setManifestState(fixture)
  }

  // Reconcile items based on current manifest & filters
  const { filteredItems, counts } = useMemo(() => {
    if (manifestState.manifest) {
      const res = reconcileCatalog({
        manifest: manifestState.manifest,
        viewMode,
        category,
        aspectRatio,
        search,
      })
      return { filteredItems: res.items, counts: res.counts }
    }

    // Fallback when manifest is not yet loaded: operational blocks only
    // 10 donor internalized + 2 6Clips original = 12 total
    const operationalFallback = [
      {
        id: "aurora",
        title: "Aurora",
        category: "backgrounds",
        description: "Green and violet aurora curtains ripple across a starfield with realistic atmospheric shimmer.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 8.0,
      },
      {
        id: "data-chart",
        title: "Data Chart",
        category: "charts",
        description: "Clean animated data line/bar chart for financial and metric videos.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 5.0,
      },
      {
        id: "flowing-gradient",
        title: "Flowing Gradient",
        category: "backgrounds",
        description: "Smooth multi-color mesh gradient animation with organic motion.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 6.0,
      },
      {
        id: "holographic",
        title: "Holographic",
        category: "backgrounds",
        description: "Iridescent holographic foil animation with dynamic sheen and color shifts.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 7.0,
      },
      {
        id: "instagram-follow",
        title: "Instagram Follow",
        category: "call-to-action",
        description: "Instagram follow card with profile avatar, username, and animated tap action.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 4.0,
      },
      {
        id: "plasma",
        title: "Plasma",
        category: "backgrounds",
        description: "Retro demoscene plasma field shader with smooth sinusoidal color palette.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 6.0,
      },
      {
        id: "stripes",
        title: "Stripes",
        category: "backgrounds",
        description: "Dynamic diagonal animated stripes background with configurable palette.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 5.0,
      },
      {
        id: "tiktok-follow",
        title: "TikTok Follow",
        category: "call-to-action",
        description: "TikTok follow CTA card with plus button tap animation and username badge.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 3.5,
      },
      {
        id: "weight-wave",
        title: "Weight Wave",
        category: "typography",
        description: "Kinetic typography block with variable font weight modulation waves.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "OFL-1.1",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 4.0,
      },
      {
        id: "yt-lower-third",
        title: "YouTube Lower Third",
        category: "lower-thirds",
        description: "YouTube broadcast lower third bar with avatar, channel name, and subscribe badge.",
        integration_status: "INTERNALIZED",
        license_status: "VERIFIED_PERMISSIVE",
        license: "Apache-2.0",
        origin: "HYPERFRAMES_DONOR",
        isOperational: true,
        aspect_9_16: "NATIVE",
        aspect_16_9: "NATIVE",
        duration: 4.5,
      },
      ...SIXCLIPS_ORIGINAL_BLOCKS.map((b) => ({ ...b, isOperational: true })),
    ]

    const baseList = viewMode === "AVAILABLE_NOW" ? operationalFallback : []
    const q = search.trim().toLowerCase()
    const filtered = baseList.filter((b) => {
      if (category !== "all" && (b.category || "").toLowerCase() !== category.toLowerCase()) {
        return false
      }
      if (q) {
        const match =
          (b.title || "").toLowerCase().includes(q) ||
          (b.id || "").toLowerCase().includes(q) ||
          (b.description || "").toLowerCase().includes(q)
        if (!match) return false
      }
      return true
    })

    return {
      filteredItems: filtered,
      counts: {
        AVAILABLE_NOW: 12,
        ALL_ORIGINAL_196: 196,
        NEEDS_WORK: 67,
        BLOCKED: 119,
      },
    }
  }, [manifestState.manifest, viewMode, category, aspectRatio, search])

  // Pagination slice
  const totalCount = filteredItems.length
  const pageCount = Math.ceil(totalCount / ITEMS_PER_PAGE) || 1
  const paginatedItems = useMemo(() => {
    const start = (page - 1) * ITEMS_PER_PAGE
    return filteredItems.slice(start, start + ITEMS_PER_PAGE)
  }, [filteredItems, page])

  const handleSearchChange = (val) => {
    setSearch(val)
    setPage(1)
  }

  const handleCategoryChange = (val) => {
    setCategory(val)
    setPage(1)
  }

  const handleAspectChange = (val) => {
    setAspectRatio(val)
    setPage(1)
  }

  const handleViewModeChange = (val) => {
    setViewMode(val)
    setPage(1)
  }

  // Header Hero badge label
  let heroBadge = "Wave 14 Truthful Catalog (12 Operational / 186 Withheld)"
  if (manifestState.status === "VERIFIED_LIVE") {
    heroBadge = "Wave 14 Verified Live Catalog (196 Verified Donor Blocks / 12 Operational)"
  } else if (manifestState.status === "STAGE1_FIXTURE") {
    heroBadge = "STAGE 1 FIXTURE: Simulated Agent 1 v1 Manifest (196 Verified Originals)"
  } else if (manifestState.status === "UNAVAILABLE_BACKEND_PENDING") {
    heroBadge = "Stage 1 Isolated Catalog (12 Operational / Live 196 Manifest Pending Agent 1 Merge)"
  }

  return (
    <Box sx={{ minHeight: "100vh", pb: 8 }}>
      {/* Page Header */}
      <PageHero
        title="Motion Graphics Catalog"
        subtitle="196 verified original donor blocks + 2 separate 6Clips-original blocks. Only rights-cleared, internalized blocks can be rendered or inserted into Motion compositions. Non-internalized entries are strictly quarantined metadata."
        badge={heroBadge}
        action={
          <Stack direction="row" spacing={1.5} alignItems="center">
            {manifestState.status === "UNAVAILABLE_BACKEND_PENDING" && (
              <Button
                variant="contained"
                color="secondary"
                size="small"
                startIcon={<IconDatabase size={16} />}
                onClick={handleActivateStage1Fixture}
                sx={{ borderRadius: "8px", fontWeight: 700 }}
              >
                Load Stage 1 Test Fixture
              </Button>
            )}
            <Button
              variant="outlined"
              size="small"
              startIcon={<IconReportAnalytics size={18} />}
              onClick={() => setShowReconModal(true)}
              sx={{
                borderRadius: "8px",
                borderColor: alpha(theme.palette.primary.main, 0.4),
                fontWeight: 600,
              }}
            >
              Inventory Audit & Reconciliation
            </Button>
          </Stack>
        }
      />

      <Container
        maxWidth="xl"
        role="region"
        aria-label="Catalog Block Directory"
        aria-busy={manifestState.status === "LOADING"}
        sx={{ mt: 3, px: { xs: 2, sm: 3, md: 4 } }}
      >
        {/* Stage 1 Fixture Disclosure Alert */}
        {manifestState.status === "STAGE1_FIXTURE" && (
          <Alert
            severity="info"
            variant="outlined"
            icon={<IconArchive size={20} />}
            sx={{ mb: 3, borderRadius: "10px" }}
          >
            <AlertTitle sx={{ fontWeight: 700 }}>Stage 1 Test Fixture Active</AlertTitle>
            Displaying the full 196 original donor block inventory from local verified fixture (<code>hyperframes_196_fixture.json</code>).
            Live backend inventory endpoint (<code>/api/catalog/inventory</code>) is pending Agent 1 integration merge.
          </Alert>
        )}

        {/* Backend Manifest Pending Notice */}
        {manifestState.status === "UNAVAILABLE_BACKEND_PENDING" && (
          <Alert
            severity="warning"
            variant="outlined"
            icon={<IconAlertTriangle size={20} />}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={handleActivateStage1Fixture}
                sx={{ fontWeight: 700 }}
              >
                Inspect 196 Fixture
              </Button>
            }
            sx={{ mb: 3, borderRadius: "10px" }}
          >
            <AlertTitle sx={{ fontWeight: 700 }}>Backend Inventory Manifest Pending Agent 1 Merge</AlertTitle>
            The live backend endpoint <code>/api/catalog/inventory</code> is not yet integrated.
            The 12 operational blocks (10 donor + 2 6Clips original) remain fully usable in "Available now".
            Click "Inspect 196 Fixture" to preview all 196 original donor metadata entries.
          </Alert>
        )}

        {/* Reconciliation Blocked Alert */}
        {manifestState.status === "BLOCKED_INVENTORY_RECONCILIATION" && (
          <Alert
            severity="error"
            icon={<IconAlertTriangle size={20} />}
            sx={{ mb: 3, borderRadius: "10px" }}
          >
            <AlertTitle sx={{ fontWeight: 700 }}>Inventory Reconciliation Error</AlertTitle>
            {manifestState.error || "The manifest supplied by the backend failed v1 contract verification. Refusing to fabricate inventory entries."}
          </Alert>
        )}

        {/* Network Disconnected / Offline */}
        {manifestState.status === "OFFLINE_BLOCKED" && (
          <Alert
            severity="warning"
            icon={<IconWifiOff size={20} />}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={loadInventory}
                startIcon={<IconRotateClockwise size={16} />}
              >
                Reconnect
              </Button>
            }
            sx={{ mb: 3, borderRadius: "10px" }}
          >
            {manifestState.error || "Network connection is offline. Reconnect and retry."}
          </Alert>
        )}

        {/* Facet and Filtering Bar */}
        <CatalogFacetBar
          search={search}
          onSearchChange={handleSearchChange}
          category={category}
          onCategoryChange={handleCategoryChange}
          aspectRatio={aspectRatio}
          onAspectRatioChange={handleAspectChange}
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
          counts={counts}
          totalCount={totalCount}
        />

        {/* State Machine: Single Loading Spinner */}
        {manifestState.status === "LOADING" && (
          <Stack
            data-testid="catalog-loading-indicator"
            alignItems="center"
            justifyContent="center"
            sx={{ py: 12 }}
          >
            <CircularProgress size={36} thickness={4} />
            <Typography variant="body2" sx={{ color: "text.secondary", mt: 2, fontWeight: 600 }}>
              Verifying catalog inventory and authentic block metadata...
            </Typography>
          </Stack>
        )}

        {/* Empty State: Missing Manifest when non-available view requested */}
        {manifestState.status === "UNAVAILABLE_BACKEND_PENDING" && viewMode !== "AVAILABLE_NOW" && (
          <Box
            sx={{
              textAlign: "center",
              py: 10,
              px: 3,
              borderRadius: "16px",
              border: "1px dashed",
              borderColor: "divider",
              bgcolor: isDark ? alpha("#fff", 0.01) : alpha("#000", 0.01),
            }}
          >
            <IconArchive size={48} style={{ color: theme.palette.warning.main, marginBottom: 16 }} />
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              Full 196 Donor Inventory Pending Backend Integration
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary", mt: 1, mb: 3, maxWidth: 540, mx: "auto" }}>
              In isolated Stage 1, the backend endpoint <code>/api/catalog/inventory</code> has not yet been merged by Agent 1.
              Load the validated Stage 1 fixture to evaluate all 196 original donor entries.
            </Typography>
            <Button
              variant="contained"
              color="primary"
              onClick={handleActivateStage1Fixture}
              startIcon={<IconDatabase size={18} />}
              sx={{ fontWeight: 700 }}
            >
              Load Stage 1 Test Fixture (196 Verified Originals)
            </Button>
          </Box>
        )}

        {/* Empty State: No blocks match filter */}
        {manifestState.status !== "LOADING" &&
          !(manifestState.status === "UNAVAILABLE_BACKEND_PENDING" && viewMode !== "AVAILABLE_NOW") &&
          paginatedItems.length === 0 && (
            <Box
              data-testid="catalog-empty-filter"
              sx={{
                textAlign: "center",
                py: 12,
                px: 2,
                borderRadius: "16px",
                border: "1px dashed",
                borderColor: "divider",
                bgcolor: isDark ? alpha("#fff", 0.01) : alpha("#000", 0.01),
              }}
            >
              <IconFilter size={40} style={{ color: theme.palette.text.disabled, marginBottom: 12 }} />
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                No catalog blocks match your filter
              </Typography>
              <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5, mb: 2 }}>
                Try adjusting your search query, selecting another category, or resetting filters.
              </Typography>
              <Button
                variant="outlined"
                size="small"
                onClick={() => {
                  setSearch("")
                  setCategory("all")
                  setViewMode("AVAILABLE_NOW")
                }}
              >
                Reset Filters
              </Button>
            </Box>
          )}

        {/* Ready Items Grid */}
        {paginatedItems.length > 0 && (
          <>
            <Grid container spacing={2.5} data-testid="catalog-grid">
              {paginatedItems.map((item) => (
                <Grid
                  item
                  key={item.id}
                  xs={12}
                  sm={6}
                  md={aspectRatio === "9:16" ? 3 : 4}
                  lg={aspectRatio === "9:16" ? 3 : 4}
                  xl={aspectRatio === "9:16" ? 2.4 : 3}
                >
                  <CatalogCard
                    item={item}
                    aspectRatio={aspectRatio}
                    onSelect={(block) => setSelectedBlock(block)}
                  />
                </Grid>
              ))}
            </Grid>

            {/* Pagination */}
            {pageCount > 1 && (
              <Stack alignItems="center" sx={{ mt: 5 }}>
                <Pagination
                  count={pageCount}
                  page={page}
                  onChange={(_, p) => {
                    setPage(p)
                    window.scrollTo({ top: 300, behavior: "smooth" })
                  }}
                  color="primary"
                  shape="rounded"
                />
              </Stack>
            )}
          </>
        )}
      </Container>

      {/* Block Details Drawer */}
      <CatalogDrawer
        item={selectedBlock}
        open={Boolean(selectedBlock)}
        onClose={() => setSelectedBlock(null)}
        initialAspect={aspectRatio}
      />

      {/* Reconciliation Modal */}
      <CatalogReconciliationModal
        open={showReconModal}
        onClose={() => setShowReconModal(false)}
        reconciliationData={reconciliationData}
      />
    </Box>
  )
}
