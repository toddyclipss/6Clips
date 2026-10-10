// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect } from "react"
import {
  Box, Stack, Typography, Tabs, Tab, IconButton, InputBase,
  Card, CardMedia, CardContent, Button, Tooltip, CircularProgress,
  Divider, Chip,
} from "@mui/material"
import http from "../../api/http"
import {
  IconSearch,
  IconVideo,
  IconTrendingUp,
  IconFolder,
  IconPlus,
  IconSparkles,
  IconPlayerPlay,
  IconCheck,
  IconPin,
  IconPinnedOff,
  IconComponents,
} from "@tabler/icons-react"

/**
 * Left Resource Panel: Sources, Assets, and Real HyperFrames Catalog.
 * Connects directly to real Library, Trends, and Catalog endpoints.
 */
export default function StudioResourcePanel({
  libraryVideos = [],
  trendItems = [],
  catalogTemplates = [],
  loading = false,
  selectedAssetId = null,
  onAddMediaToTimeline,
  onAddBlock,
  onSelectSource,
  onIngestTrend,
  isPinned = false,
  onTogglePin,
}) {
  const [tab, setTab] = useState(0) // 0 = Assets, 1 = Sources (Trends), 2 = Catalog
  const [search, setSearch] = useState("")
  const [catalogItems, setCatalogItems] = useState([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogCategory, setCatalogCategory] = useState("all")

  const safeAssets = Array.isArray(libraryVideos) ? libraryVideos : []
  const safeTrends = Array.isArray(trendItems) ? trendItems : []

  const filteredAssets = safeAssets.filter((v) =>
    (v?.title || v?.source_title || "video").toLowerCase().includes(search.toLowerCase())
  )

  const filteredTrends = safeTrends.filter((t) =>
    (t?.title || t?.query || "").toLowerCase().includes(search.toLowerCase())
  )

  useEffect(() => {
    if (tab === 2 && catalogItems.length === 0) {
      setCatalogLoading(true)
      http.get("/api/projects/catalog/items")
        .then((res) => {
          const items = Array.isArray(res.data) ? res.data : []
          setCatalogItems(items)
        })
        .catch(() => {})
        .finally(() => setCatalogLoading(false))
    }
  }, [tab, catalogItems.length])

  const filteredCatalog = catalogItems.filter((item) => {
    const q = search.toLowerCase()
    const matchesSearch = !q || (item.name || "").toLowerCase().includes(q) || (item.title || "").toLowerCase().includes(q)
    if (!matchesSearch) return false
    if (catalogCategory === "all") return true
    const cat = (item.category || "").toLowerCase()
    const name = (item.name || "").toLowerCase()
    if (catalogCategory === "lower") return cat.includes("lower") || name.includes("lower")
    if (catalogCategory === "type") return cat.includes("type") || name.includes("wave") || name.includes("text") || cat.includes("typography")
    if (catalogCategory === "ui") return cat.includes("mockup") || name.includes("cascade") || name.includes("card") || name.includes("notification")
    if (catalogCategory === "data") return cat.includes("data") || cat.includes("chart") || name.includes("chart")
    if (catalogCategory === "visual") return cat.includes("shader") || name.includes("aurora") || name.includes("canvas")
    return true
  })

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#ffffff",
        borderRight: "1px solid",
        borderColor: "divider",
        overflow: "hidden",
      }}
    >
      {/* Panel Header */}
      <Box sx={{ p: 1.5, pb: 1, borderBottom: "1px solid", borderColor: "divider" }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
          <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: "text.secondary" }}>
            Media & Resources
          </Typography>
          <Tooltip title={isPinned ? "Unpin panel" : "Pin panel"} arrow>
            <IconButton size="small" onClick={onTogglePin} sx={{ width: 22, height: 22, color: isPinned ? "primary.main" : "text.secondary" }}>
              {isPinned ? <IconPin size={14} /> : <IconPinnedOff size={14} />}
            </IconButton>
          </Tooltip>
        </Stack>

        {/* Tabs */}
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          variant="fullWidth"
          sx={{
            minHeight: 28,
            "& .MuiTab-root": {
              minHeight: 28,
              py: 0.5,
              fontSize: "0.72rem",
              fontWeight: 700,
              textTransform: "none",
            },
          }}
        >
          <Tab label={`Assets (${libraryVideos.length})`} />
          <Tab label={`Sources (${trendItems.length})`} />
          <Tab label="Catalog" />
        </Tabs>

        {/* Search */}
        <Box
          sx={{
            mt: 1,
            display: "flex",
            alignItems: "center",
            bgcolor: "#f8fafc",
            borderRadius: 1.5,
            px: 1,
            py: 0.25,
            border: "1px solid",
            borderColor: "divider",
          }}
        >
          <IconSearch size={14} color="#94a3b8" />
          <InputBase
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search items..."
            sx={{ ml: 1, fontSize: "0.75rem", flex: 1 }}
          />
        </Box>
      </Box>

      {/* Content Area */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 1.5 }}>
        {loading ? (
          <Stack alignItems="center" justifyContent="center" sx={{ height: 160, color: "text.secondary" }}>
            <CircularProgress size={20} />
            <Typography variant="caption" sx={{ mt: 1 }}>Loading assets…</Typography>
          </Stack>
        ) : tab === 0 ? (
          // Tab 0: Library Assets
          filteredAssets.length === 0 ? (
            <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 4 }}>
              No library assets found.
            </Typography>
          ) : (
            <Stack spacing={1}>
              {filteredAssets.map((asset) => {
                const isSelected = String(asset.id) === String(selectedAssetId)
                return (
                  <Box
                    key={asset.id}
                    onClick={() => onSelectSource && onSelectSource(asset)}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: isSelected ? "2px solid #8b5cf6" : "1px solid",
                      borderColor: isSelected ? "#8b5cf6" : "divider",
                      bgcolor: isSelected ? "#f5f3ff" : "#f8fafc",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                      "&:hover": {
                        borderColor: isSelected ? "#8b5cf6" : "primary.light",
                        bgcolor: isSelected ? "#ede9fe" : "#f1f5f9",
                      },
                    }}
                  >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box
                      sx={{
                        width: 44,
                        height: 44,
                        borderRadius: 1,
                        bgcolor: "#0f172a",
                        color: "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        overflow: "hidden",
                        flexShrink: 0,
                      }}
                    >
                      <IconVideo size={20} />
                    </Box>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 700,
                          fontSize: "0.74rem",
                          display: "-webkit-box",
                          WebkitLineClamp: 1,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        {asset.title || asset.filename || "Video Asset"}
                      </Typography>
                      <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                        {asset.duration ? `${Math.round(asset.duration)}s` : "Media"} • {asset.status || "ready"}
                      </Typography>
                    </Box>
                    <Tooltip title="Add to Timeline" arrow>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation()
                          onAddMediaToTimeline && onAddMediaToTimeline(asset)
                        }}
                        sx={{
                          width: 26,
                          height: 26,
                          bgcolor: "primary.main",
                          color: "#ffffff",
                          "&:hover": { bgcolor: "primary.dark" },
                        }}
                      >
                        <IconPlus size={14} stroke={2.5} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Box>
              )
            })}
          </Stack>
          )
        ) : tab === 1 ? (
          // Tab 1: Contextual Trends / Sources
          filteredTrends.length === 0 ? (
            <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 4 }}>
              No trend sources available.
            </Typography>
          ) : (
            <Stack spacing={1}>
              {filteredTrends.map((trend, idx) => (
                <Box
                  key={trend.id || idx}
                  sx={{
                    p: 1,
                    borderRadius: 1.5,
                    border: "1px solid",
                    borderColor: "divider",
                    bgcolor: "#ffffff",
                    cursor: "pointer",
                    "&:hover": { borderColor: "primary.main", bgcolor: "#fdf4ff" },
                  }}
                  onClick={() => onSelectSource && onSelectSource(trend)}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <IconTrendingUp size={16} color="#8b5cf6" style={{ marginTop: 2 }} />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: "text.primary", display: "block", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                        {trend.title || trend.query}
                      </Typography>
                      <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                        Score: {trend.virality_score || trend.traffic || "High"} • {trend.platform || "Web"}
                      </Typography>
                    </Box>
                    <Tooltip title="Ingest to Project" arrow>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation()
                          onIngestTrend && onIngestTrend(trend)
                        }}
                        sx={{
                          width: 24,
                          height: 24,
                          bgcolor: "#f3e8ff",
                          color: "#7c3aed",
                          "&:hover": { bgcolor: "#ede9fe" },
                        }}
                      >
                        <IconPlus size={13} stroke={2.5} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Box>
              ))}
            </Stack>
          )
        ) : (
          // Tab 2: Real HyperFrames Catalog Blocks
          <Box>
            {/* Category Filter Chips */}
            <Stack direction="row" spacing={0.5} sx={{ mb: 1, overflowX: "auto", pb: 0.5 }}>
              {[
                { id: "all", label: "All" },
                { id: "lower", label: "Lower Third" },
                { id: "type", label: "Typography" },
                { id: "ui", label: "UI Mockup" },
                { id: "data", label: "Data / Charts" },
                { id: "visual", label: "Shaders" },
              ].map((cat) => (
                <Chip
                  key={cat.id}
                  size="small"
                  label={cat.label}
                  clickable
                  variant={catalogCategory === cat.id ? "filled" : "outlined"}
                  color={catalogCategory === cat.id ? "primary" : "default"}
                  onClick={() => setCatalogCategory(cat.id)}
                  sx={{ height: 20, fontSize: "0.65rem", fontWeight: 700 }}
                />
              ))}
            </Stack>

            {catalogLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
                <CircularProgress size={20} />
              </Box>
            ) : filteredCatalog.length === 0 ? (
              <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 4 }}>
                No catalog blocks found.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {filteredCatalog.map((item) => (
                  <Box
                    key={item.name}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/json", JSON.stringify({ type: "block", item }))
                    }}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: "1px solid",
                      borderColor: "divider",
                      bgcolor: "#ffffff",
                      cursor: "grab",
                      "&:hover": { borderColor: "primary.main", bgcolor: "#f8fafc" },
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 0.5 }}>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="caption" sx={{ fontWeight: 800, color: "text.primary", display: "block", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                          {item.title || item.name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.65rem", display: "block" }}>
                          {item.category || "Motion Component"} • {item.variables_count || (item.variables || []).length} vars
                        </Typography>
                      </Box>
                      <Chip
                        size="small"
                        label={`${item.duration_seconds || 3}s`}
                        sx={{ height: 16, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#f1f5f9" }}
                      />
                    </Stack>

                    <Stack direction="row" spacing={0.5} justifyContent="flex-end" sx={{ mt: 0.5 }}>
                      <Button
                        size="small"
                        variant="contained"
                        sx={{ height: 22, fontSize: "0.68rem", px: 1, py: 0, bgcolor: "primary.main", textTransform: "none" }}
                        onClick={() => {
                          if (onAddBlock) {
                            onAddBlock(item)
                          } else if (onAddMediaToTimeline) {
                            onAddMediaToTimeline({ type: "block", block_id: item.name, item })
                          }
                        }}
                      >
                        Insert Block
                      </Button>
                    </Stack>
                  </Box>
                ))}
              </Stack>
            )}
          </Box>
        )}
      </Box>
    </Box>
  )
}
