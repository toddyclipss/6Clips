// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Catalog — HyperFrames feature catalog with evidence-backed previews,
 * aspect ratio parity (9:16 vs 16:9), and non-destructive hover Ghost Previews.
 */
import React, { useState, useEffect, useCallback } from "react"
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

  const [items, setItems] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [selectedBlock, setSelectedBlock] = useState(null)
  const [showReconModal, setShowReconModal] = useState(false)
  const [reconciliationData, setReconciliationData] = useState(null)

  // Fetch catalog items
  const fetchCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
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
      })
      setItems(res.data?.items || [])
      setTotalCount(res.data?.total || 0)
    } catch (err) {
      console.error("Failed to load catalog items:", err)
      setError("Could not load catalog blocks. Please verify backend service.")
    } finally {
      setLoading(false)
    }
  }, [category, search, aspectRatio, disposition, page])

  useEffect(() => {
    fetchCatalog()
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
        subtitle="196 HyperFrames blocks: 6 internalized & ready for runtime rendering, truthful previews in 9:16 vertical and 16:9 landscape, and validated Add-to-Project timeline intents."
        badge="Wave 3 Production Catalog"
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

      <Container maxWidth="xl" sx={{ mt: 3, px: { xs: 2, sm: 3, md: 4 } }}>
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

        {/* Error Alert */}
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {/* Loading Indicator */}
        {loading ? (
          <Stack alignItems="center" justifyContent="center" sx={{ py: 12 }}>
            <CircularProgress size={36} thickness={4} />
            <Typography variant="body2" sx={{ color: "text.secondary", mt: 2 }}>
              Loading catalog blocks and authentic posters...
            </Typography>
          </Stack>
        ) : items.length === 0 ? (
          <Box
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
              Try adjusting your search query, selecting another category, or toggling aspect ratio.
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
        ) : (
          <>
            {/* Catalog Grid */}
            <Grid container spacing={2.5}>
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
