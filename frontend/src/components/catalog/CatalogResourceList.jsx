// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogResourceList: Reusable, accessible, state-machine-driven Catalog component
 * for embedded media/resource panels (e.g., StudioResourcePanel in MotionGraphics).
 *
 * State Machine:
 * - LOADING: Active, time-bounded query with aria-busy="true"
 * - READY_ITEMS: Items loaded and rendered with drag & drop and hover ghost preview
 * - EMPTY_FILTER: Truthful empty result when filter/search yields 0 matches, with Reset button
 * - ERROR_RETRYABLE: Error alert with explicit retry action (no infinite skeleton)
 * - OFFLINE_BLOCKED: Network/offline detection with reconnect/retry action
 */
import React, { useState, useEffect, useRef, useCallback } from "react"
import {
  Box,
  Stack,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Button,
  Alert,
  InputBase,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconSearch,
  IconX,
  IconPlus,
  IconRotateClockwise,
  IconFilter,
  IconWifiOff,
  IconAlertTriangle,
  IconSparkles,
} from "@tabler/icons-react"
import http from "../../api/http"

const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "typography", label: "Typography" },
  { id: "lower-thirds", label: "Lower Thirds" },
  { id: "mock-ui", label: "Mock UI & Social" },
  { id: "charts", label: "Charts" },
  { id: "backgrounds", label: "Backgrounds & Shaders" },
  { id: "transitions", label: "Transitions" },
  { id: "call-to-action", label: "Call to Action" },
]

export default function CatalogResourceList({
  aspectRatio = "9:16",
  onSelectBlock,
  onAddBlock,
  onStartGhostPreview,
  onEndGhostPreview,
  selectedBlockId = null,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const [status, setStatus] = useState("LOADING") // LOADING | READY_ITEMS | EMPTY_FILTER | ERROR_RETRYABLE | OFFLINE_BLOCKED
  const [items, setItems] = useState([])
  const [category, setCategory] = useState("all")
  const [search, setSearch] = useState("")
  const [errorMessage, setErrorMessage] = useState(null)

  const abortControllerRef = useRef(null)
  const requestIdRef = useRef(0)
  const hoverTimerRef = useRef(null)

  const fetchItems = useCallback(async () => {
    // Check offline state first
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setStatus("OFFLINE_BLOCKED")
      setErrorMessage("Network is offline. Check your connection to browse catalog blocks.")
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
      const params = {
        category: category !== "all" ? category : undefined,
        search: search.trim() || undefined,
        aspect_ratio: aspectRatio,
        limit: 100,
      }

      // Try primary catalog endpoint, fallback to projects catalog route
      let res
      try {
        res = await http.get("/api/catalog/items", {
          params,
          signal: controller.signal,
        })
      } catch (firstErr) {
        if (controller.signal.aborted) return
        res = await http.get("/api/projects/catalog/items", {
          params,
          signal: controller.signal,
        })
      }

      // Guard against stale response
      if (currentReqId !== requestIdRef.current) return

      const fetchedItems = res.data?.items || (Array.isArray(res.data) ? res.data : [])
      setItems(fetchedItems)

      if (fetchedItems.length === 0) {
        setStatus("EMPTY_FILTER")
      } else {
        setStatus("READY_ITEMS")
      }
    } catch (err) {
      if (controller.signal.aborted) return
      if (currentReqId !== requestIdRef.current) return

      console.error("Catalog query error:", err)
      const isOffline = typeof navigator !== "undefined" && !navigator.onLine
      if (isOffline) {
        setStatus("OFFLINE_BLOCKED")
        setErrorMessage("Network disconnected while loading catalog blocks.")
      } else {
        setStatus("ERROR_RETRYABLE")
        setErrorMessage(err.response?.data?.detail || "Could not load catalog blocks. Please retry.")
      }
    }
  }, [category, search, aspectRatio])

  useEffect(() => {
    fetchItems()
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      if (hoverTimerRef.current) {
        clearTimeout(hoverTimerRef.current)
      }
    }
  }, [fetchItems])

  const handleMouseEnter = (item) => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current)
    hoverTimerRef.current = setTimeout(() => {
      if (onStartGhostPreview) onStartGhostPreview(item)
    }, 200)
  }

  const handleMouseLeave = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current)
      hoverTimerRef.current = null
    }
    if (onEndGhostPreview) onEndGhostPreview()
  }

  return (
    <Box
      data-testid="catalog-resource-panel"
      role="region"
      aria-label="Motion Graphics Catalog"
      aria-busy={status === "LOADING"}
      sx={{ display: "flex", flexDirection: "column", height: "100%" }}
    >
      {/* Search Bar */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          px: 1,
          py: 0.5,
          borderRadius: 1.5,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: isDark ? alpha("#fff", 0.04) : "#f8fafc",
          mb: 1,
        }}
      >
        <IconSearch size={14} style={{ color: theme.palette.text.secondary, marginRight: 6 }} />
        <InputBase
          placeholder="Search catalog blocks..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          inputProps={{ "aria-label": "Search catalog blocks" }}
          sx={{ fontSize: "0.78rem", flex: 1 }}
        />
        {search && (
          <IconButton size="small" onClick={() => setSearch("")} sx={{ p: 0.25 }}>
            <IconX size={12} />
          </IconButton>
        )}
      </Box>

      {/* Category Pills */}
      <Stack
        direction="row"
        spacing={0.5}
        sx={{
          mb: 1.5,
          overflowX: "auto",
          pb: 0.5,
          "&::-webkit-scrollbar": { height: 4 },
          "&::-webkit-scrollbar-thumb": { bgcolor: alpha(theme.palette.primary.main, 0.2), borderRadius: 2 },
        }}
      >
        {CATEGORIES.map((cat) => (
          <Chip
            key={cat.id}
            size="small"
            label={cat.label}
            clickable
            variant={category === cat.id ? "filled" : "outlined"}
            color={category === cat.id ? "primary" : "default"}
            onClick={() => setCategory(cat.id)}
            sx={{
              height: 22,
              fontSize: "0.68rem",
              fontWeight: 700,
              flexShrink: 0,
            }}
          />
        ))}
      </Stack>

      {/* Dynamic State Machine View */}
      <Box sx={{ flex: 1, overflowY: "auto" }}>
        {status === "LOADING" && (
          <Box
            data-testid="catalog-loading-state"
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              py: 5,
              gap: 1.5,
            }}
          >
            <CircularProgress size={24} thickness={4} />
            <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 600 }}>
              Loading verified catalog blocks...
            </Typography>
          </Box>
        )}

        {status === "EMPTY_FILTER" && (
          <Box
            data-testid="catalog-empty-filter-state"
            sx={{
              textAlign: "center",
              py: 5,
              px: 2,
              borderRadius: 2,
              border: "1px dashed",
              borderColor: "divider",
              bgcolor: isDark ? alpha("#fff", 0.02) : alpha("#000", 0.01),
            }}
          >
            <IconFilter size={32} style={{ color: theme.palette.text.disabled, marginBottom: 8 }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              No catalog blocks match your filter
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.5, mb: 2 }}>
              Try another category or clear your search term.
            </Typography>
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                setCategory("all")
                setSearch("")
              }}
              sx={{ fontSize: "0.72rem", py: 0.25, px: 1.5, borderRadius: 1 }}
            >
              Reset Filters
            </Button>
          </Box>
        )}

        {status === "ERROR_RETRYABLE" && (
          <Alert
            severity="error"
            data-testid="catalog-error-state"
            action={
              <Button
                color="inherit"
                size="small"
                onClick={fetchItems}
                startIcon={<IconRotateClockwise size={14} />}
                sx={{ fontSize: "0.72rem", fontWeight: 700 }}
              >
                Retry
              </Button>
            }
            sx={{ my: 2, fontSize: "0.75rem", borderRadius: 1.5 }}
          >
            {errorMessage || "Failed to load catalog blocks."}
          </Alert>
        )}

        {status === "OFFLINE_BLOCKED" && (
          <Alert
            severity="warning"
            data-testid="catalog-offline-state"
            icon={<IconWifiOff size={18} />}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={fetchItems}
                startIcon={<IconRotateClockwise size={14} />}
                sx={{ fontSize: "0.72rem", fontWeight: 700 }}
              >
                Reconnect
              </Button>
            }
            sx={{ my: 2, fontSize: "0.75rem", borderRadius: 1.5 }}
          >
            {errorMessage || "Network offline. Reconnect to load catalog."}
          </Alert>
        )}

        {status === "READY_ITEMS" && (
          <Stack spacing={1} data-testid="catalog-items-grid">
            {items.map((item) => {
              const bName = item.name || item.id
              const posterUrl = item.poster_url || `/api/catalog/blocks/${bName}/poster?aspect_ratio=${aspectRatio}`
              const isSelected = selectedBlockId === bName

              return (
                <Box
                  key={bName}
                  data-testid={`catalog-card-${bName}`}
                  onClick={() => onSelectBlock && onSelectBlock(item)}
                  onMouseEnter={() => handleMouseEnter(item)}
                  onMouseLeave={handleMouseLeave}
                  draggable
                  onDragStart={(e) => {
                    const payload = {
                      kind: "catalog",
                      type: "block",
                      mediaType: "block",
                      data: item,
                      item,
                      title: item.title || item.name || item.id,
                      duration: item.duration_seconds || item.duration || 3.0,
                    }
                    e.dataTransfer.setData("application/viralmint-clip", JSON.stringify(payload))
                    e.dataTransfer.setData("application/json", JSON.stringify(payload))
                    e.dataTransfer.effectAllowed = "copy"
                  }}
                  sx={{
                    p: 1,
                    borderRadius: 1.5,
                    border: "1px solid",
                    borderColor: isSelected ? "primary.main" : "divider",
                    bgcolor: isSelected
                      ? isDark ? alpha(theme.palette.primary.main, 0.15) : "#f3e8ff"
                      : isDark ? alpha("#fff", 0.03) : "#ffffff",
                    cursor: "grab",
                    transition: "all 0.15s ease",
                    "&:hover": {
                      borderColor: "primary.main",
                      bgcolor: isDark ? alpha(theme.palette.primary.main, 0.1) : "#f8fafc",
                      boxShadow: "0 2px 8px rgba(139, 92, 246, 0.12)",
                    },
                    "&:active": { cursor: "grabbing" },
                  }}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    {/* Visual Poster Thumbnail */}
                    <Box
                      sx={{
                        width: 54,
                        height: 54,
                        borderRadius: 1,
                        bgcolor: "#0f172a",
                        overflow: "hidden",
                        flexShrink: 0,
                        position: "relative",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                      }}
                    >
                      <Box
                        component="img"
                        src={posterUrl}
                        alt={item.title || bName}
                        loading="lazy"
                        onError={(e) => { e.target.style.display = "none" }}
                        sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
                      <IconSparkles size={18} color="#a855f7" style={{ position: "absolute", zIndex: 0 }} />
                    </Box>

                    {/* Metadata */}
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 700,
                          color: "text.primary",
                          display: "-webkit-box",
                          WebkitLineClamp: 1,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          fontSize: "0.74rem",
                        }}
                      >
                        {item.title || bName}
                      </Typography>
                      <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
                        <Chip
                          size="small"
                          label={item.category || "block"}
                          sx={{ height: 16, fontSize: "0.62rem", textTransform: "capitalize" }}
                        />
                        {item.duration && (
                          <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.65rem" }}>
                            {Number(item.duration).toFixed(1)}s
                          </Typography>
                        )}
                      </Stack>
                    </Box>

                    {/* Add to Timeline Button */}
                    {onAddBlock && (
                      <Tooltip title="Add block to timeline" arrow>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation()
                            onAddBlock(item)
                          }}
                          sx={{
                            width: 26,
                            height: 26,
                            bgcolor: isDark ? alpha(theme.palette.primary.main, 0.2) : "#f3e8ff",
                            color: "primary.main",
                            "&:hover": {
                              bgcolor: isDark ? alpha(theme.palette.primary.main, 0.3) : "#ede9fe",
                            },
                          }}
                        >
                          <IconPlus size={14} stroke={2.5} />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Stack>
                </Box>
              )
            })}
          </Stack>
        )}
      </Box>
    </Box>
  )
}
