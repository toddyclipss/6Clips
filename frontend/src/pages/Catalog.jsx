// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Catalog — HyperFrames feature catalog with single source-of-truth state machine:
 * LOADING, READY_ITEMS, EMPTY_FILTER, ERROR_RETRYABLE, OFFLINE_BLOCKED.
 * Prevents perpetual skeletons, aborts superseded queries, and truthfully displays
 * 196 inventoried (10 donor + 2 original = 12 operational, 186 withheld).
 */
import React, { useState, useEffect, useCallback, useRef } from "react"
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
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconReportAnalytics,
  IconSparkles,
  IconDeviceMobile,
  IconDeviceTv,
  IconFilter,
  IconRotateClockwise,
  IconWifiOff,
} from "@tabler/icons-react"
import http from "../api/http"
import useDocumentTitle from "../hooks/useDocumentTitle"
import PageHero from "../components/PageHero"
import CatalogFacetBar from "../components/catalog/CatalogFacetBar"
import CatalogCard from "../components/catalog/CatalogCard"
import CatalogDrawer from "../components/catalog/CatalogDrawer"
import CatalogReconciliationModal from "../components/catalog/CatalogReconciliationModal"

const ITEMS_PER_PAGE = 24

export default function Catalog() {
  useDocumentTitle("Catalog")
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const [search, setSearch] = useState("")
  const [category, setCategory] = useState("all")
  const [aspectRatio, setAspectRatio] = useState("9:16")
  const [disposition, setDisposition] = useState("ALL")
  const [page, setPage] = useState(1)

  // Single source of truth Catalog state machine
  const [status, setStatus] = useState("LOADING") // LOADING | READY_ITEMS | EMPTY_FILTER | ERROR_RETRYABLE | OFFLINE_BLOCKED
  const [items, setItems] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [errorMessage, setErrorMessage] = useState(null)

  const [selectedBlock, setSelectedBlock] = useState(null)
  const [showReconModal, setShowReconModal] = useState(false)
  const [reconciliationData, setReconciliationData] = useState(null)

  const abortControllerRef = useRef(null)
  const requestIdRef = useRef(0)

  // Fetch catalog items with cancellation and race guard
  const fetchCatalog = useCallback(async () => {
    // Offline pre-check
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setStatus("OFFLINE_BLOCKED")
      setErrorMessage("Network connection is offline. Please check your connectivity.")
      return
    }

    // Cancel any in-flight superseded request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller

    const currentReqId = ++requestIdRef.current
    setStatus("LOADING")
    setErrorMessage(null)

    try {
      const offset = (page - 1) * ITEMS_PER_PAGE
      const res = await http.get("/api/catalog/items", {
        params: {
          category: category !== "all" ? category : undefined,
          search: search.trim() || undefined,
          aspect_ratio: aspectRatio,
          disposition: disposition !== "ALL" ? disposition : undefined,
          limit: ITEMS_PER_PAGE,
          offset,
        },
        signal: controller.signal,
      })

      // Guard against stale response
      if (currentReqId !== requestIdRef.current) return

      const fetchedItems = res.data?.items || []
      const total = res.data?.total || 0
      setItems(fetchedItems)
      setTotalCount(total)

      if (fetchedItems.length === 0) {
        setStatus("EMPTY_FILTER")
      } else {
        setStatus("READY_ITEMS")
      }
    } catch (err) {
      if (controller.signal.aborted) return
      if (currentReqId !== requestIdRef.current) return

      console.error("Failed to load catalog items:", err)
      const isOffline = typeof navigator !== "undefined" && !navigator.onLine
      if (isOffline) {
        setStatus("OFFLINE_BLOCKED")
        setErrorMessage("Network disconnected while loading catalog items.")
      } else {
        setStatus("ERROR_RETRYABLE")
        setErrorMessage("Could not load catalog blocks. Please verify backend service and retry.")
      }
    }
  }, [category, search, aspectRatio, disposition, page])

  useEffect(() => {
    fetchCatalog()
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [fetchCatalog])

  // Fetch reconciliation audit summary once
  useEffect(() => {
    http.get("/api/catalog/reconciliation")
      .then((res) => setReconciliationData(res.data))
      .catch((err) => console.debug("Reconciliation fetch error:", err))
  }, [])

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

  const handleDispositionChange = (val) => {
    setDisposition(val)
    setPage(1)
  }

  const pageCount = Math.ceil(totalCount / ITEMS_PER_PAGE) || 1

  return (
    <Box sx={{ minHeight: "100vh", pb: 8 }}>
      {/* Page Header */}
      <PageHero
        title="Motion Graphics Catalog"
        subtitle="196 donor originals inventoried: 10 donor internalized + 2 6Clips original substitutes (12 operational blocks), 186 unready donor originals strictly quarantined. Truthful 9:16 vertical and 16:9 landscape previews."
        badge="Wave 11 Production Catalog (12 Operational / 186 Withheld)"
        action={
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
        }
      />

      <Container
        maxWidth="xl"
        role="region"
        aria-label="Catalog Block Directory"
        aria-busy={status === "LOADING"}
        sx={{ mt: 3, px: { xs: 2, sm: 3, md: 4 } }}
      >
        {/* Facet and Filtering Bar */}
        <CatalogFacetBar
          search={search}
          onSearchChange={handleSearchChange}
          category={category}
          onCategoryChange={handleCategoryChange}
          aspectRatio={aspectRatio}
          onAspectRatioChange={handleAspectChange}
          disposition={disposition}
          onDispositionChange={handleDispositionChange}
          totalCount={totalCount}
        />

        {/* State Machine: OFFLINE_BLOCKED */}
        {status === "OFFLINE_BLOCKED" && (
          <Alert
            severity="warning"
            icon={<IconWifiOff size={20} />}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={fetchCatalog}
                startIcon={<IconRotateClockwise size={16} />}
              >
                Reconnect
              </Button>
            }
            sx={{ mb: 3 }}
          >
            {errorMessage || "Network connection is offline. Reconnect and retry."}
          </Alert>
        )}

        {/* State Machine: ERROR_RETRYABLE */}
        {status === "ERROR_RETRYABLE" && (
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                size="small"
                onClick={fetchCatalog}
                startIcon={<IconRotateClockwise size={16} />}
              >
                Retry
              </Button>
            }
            sx={{ mb: 3 }}
          >
            {errorMessage || "Could not load catalog blocks."}
          </Alert>
        )}

        {/* State Machine: LOADING */}
        {status === "LOADING" && (
          <Stack
            data-testid="catalog-loading-indicator"
            alignItems="center"
            justifyContent="center"
            sx={{ py: 12 }}
          >
            <CircularProgress size={36} thickness={4} />
            <Typography variant="body2" sx={{ color: "text.secondary", mt: 2, fontWeight: 600 }}>
              Loading catalog blocks and authentic posters...
            </Typography>
          </Stack>
        )}

        {/* State Machine: EMPTY_FILTER */}
        {status === "EMPTY_FILTER" && (
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
                setDisposition("ALL")
              }}
            >
              Reset Filters
            </Button>
          </Box>
        )}

        {/* State Machine: READY_ITEMS */}
        {status === "READY_ITEMS" && (
          <>
            {/* Catalog Grid */}
            <Grid container spacing={2.5} data-testid="catalog-grid">
              {items.map((item) => (
                <Grid
                  item
                  key={item.id}
                  xs={12}
                  sm={6}
                  md={aspectRatio === "9:16" ? 3 : 4}
                  lg={aspectRatio === "9:16" ? 3 : 4}
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
                  onChange={(_, p) => setPage(p)}
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
