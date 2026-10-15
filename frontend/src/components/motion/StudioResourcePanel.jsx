// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useRef, useCallback } from "react"
import {
  Box, Stack, Typography, Tabs, Tab, IconButton, InputBase,
  Button, Tooltip, CircularProgress, Chip, Dialog, DialogTitle,
  DialogContent, DialogActions,
} from "@mui/material"
import http from "../../api/http"
import {
  IconSearch,
  IconVideo,
  IconTrendingUp,
  IconPlus,
  IconSparkles,
  IconPlayerPlay,
  IconPlayerPause,
  IconPin,
  IconPinnedOff,
  IconVolume,
  IconPhoto,
  IconEye,
  IconBrandYoutube,
  IconBrandTiktok,
  IconBrandInstagram,
  IconWorld,
  IconX,
  IconLink,
} from "@tabler/icons-react"
import {
  HYPERFRAMES_CATEGORIES,
  fetchAllInventoryPages,
  SHIPPED_OPERATIONAL_IDS,
  DONOR_INTERNALIZED_IDS,
  DONOR_PACKAGED_IDS,
  DONOR_SHADER_IDS,
  DONOR_LOWER_THIRD_IDS,
  RETIRED_6CLIPS_BLOCK_IDS,
  resolveBlockCategory,
} from "../../utils/catalogOriginals"

/**
 * Left Resource Panel: Sources, Assets, and Real HyperFrames Catalog.
 * Connects directly to real Library, Trends, and Catalog endpoints.
 * Supports media-type specific asset previews, discovered video thumbnails with fallbacks,
 * non-destructive source preview, and 180-300ms hover ghost previews in the motion player.
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
  aspectRatio = "9:16",
  onStartGhostPreview,
  onEndGhostPreview,
  onAskAiToInsert,
  onRefreshLibrary,
}) {
  const [tab, setTab] = useState(() => {
    try {
      const qp = new URLSearchParams(window.location.search)
      const t = qp.get("tab")?.toLowerCase()
      if (t === "catalog") return 2
      if (t === "sources" || t === "trends") return 1
      if (t === "assets" || t === "media") return 0
    } catch {}
    return 0
  }) // 0 = Assets, 1 = Sources (Trends), 2 = Catalog
  const [search, setSearch] = useState("")
  const [catalogItems, setCatalogItems] = useState([])
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [catalogError, setCatalogError] = useState(null)
  const [catalogCategory, setCatalogCategory] = useState("all")

  useEffect(() => {
    try {
      const qp = new URLSearchParams(window.location.search)
      const t = qp.get("tab")?.toLowerCase()
      if (t === "catalog") setTab(2)
      else if (t === "sources" || t === "trends") setTab(1)
      else if (t === "assets" || t === "media") setTab(0)
    } catch {}
  }, [])



  // Audio Pre-listening state
  const [playingAudioKey, setPlayingAudioKey] = useState(null)
  const audioPlayerRef = useRef(null)

  // Source Preview Modal state
  const [previewingSource, setPreviewingSource] = useState(null)

  // Hover timer and race-condition guard for ghost preview
  const hoverTimerRef = useRef(null)
  const hoverCounterRef = useRef(0)

  // Stop audio when unmounting or switching tabs
  useEffect(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause()
      audioPlayerRef.current = null
      setPlayingAudioKey(null)
    }
    // Also cancel any pending ghost preview on tab switch
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current)
      hoverTimerRef.current = null
    }
    if (onEndGhostPreview) onEndGhostPreview()
  }, [tab])

  const safeAssets = Array.isArray(libraryVideos) ? libraryVideos : []
  const safeTrends = Array.isArray(trendItems) ? trendItems : []

  const filteredAssets = safeAssets.filter((v) =>
    (v?.title || v?.source_title || "asset").toLowerCase().includes(search.toLowerCase())
  )

  const filteredTrends = [...safeTrends]
    .filter((t) =>
      (t?.title || t?.query || "").toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const sA = typeof a?.virality_score === "number" ? a.virality_score : (parseFloat(a?.virality_score) || (typeof a?.traffic === "number" ? a.traffic : -1))
      const sB = typeof b?.virality_score === "number" ? b.virality_score : (parseFloat(b?.virality_score) || (typeof b?.traffic === "number" ? b.traffic : -1))
      return sB - sA
    })

  const fetchCatalog = useCallback((signal = null) => {
    setCatalogLoading(true)
    setCatalogError(null)

    fetchAllInventoryPages({ signal, pageSize: 100 })
      .then((res) => {
        if (res.status === "VERIFIED_LIVE" && res.blocks && res.blocks.length > 0) {
          const validDonorBlocks = res.blocks.filter(
            (b) => !RETIRED_6CLIPS_BLOCK_IDS.has(b.id || b.name)
          )
          setCatalogItems(validDonorBlocks)
        } else {
          // Fallback to /api/projects/catalog/items, strictly filtering 6Clips blocks
          return http.get("/api/projects/catalog/items", { signal }).then((fallbackRes) => {
            const rawItems = fallbackRes.data?.items || (Array.isArray(fallbackRes.data) ? fallbackRes.data : [])
            const filtered = rawItems
              .filter((it) => !RETIRED_6CLIPS_BLOCK_IDS.has(it.name || it.id))
              .map((it) => {
                const bName = it.name || it.id
                const isOp = DONOR_INTERNALIZED_IDS.has(bName)
                const resCat = resolveBlockCategory(it.tags)
                return {
                  ...it,
                  id: bName,
                  category: resCat,
                  origin: "HYPERFRAMES_DONOR",
                  isOperational: isOp,
                  runtime_operable: isOp,
                  poster_url: isOp ? `/api/catalog/blocks/${bName}/poster` : null,
                  preview_url: isOp ? `/api/catalog/blocks/${bName}/preview` : null,
                }
              })
            setCatalogItems(filtered)
          })
        }
      })
      .catch((err) => {
        if (signal?.aborted) return
        setCatalogError(err.response?.data?.detail || err.message || "Failed to load catalog items")
      })
      .finally(() => {
        if (!signal?.aborted) setCatalogLoading(false)
      })
  }, [])

  useEffect(() => {
    let controller = null
    if (tab === 2 && catalogItems.length === 0 && !catalogError) {
      controller = new AbortController()
      fetchCatalog(controller.signal)
    }
    return () => {
      if (controller) controller.abort()
    }
  }, [tab, catalogItems.length, catalogError, fetchCatalog])

  const filteredCatalog = catalogItems.filter((item) => {
    const bName = item.name || item.id
    if (RETIRED_6CLIPS_BLOCK_IDS.has(bName)) return false
    const q = search.toLowerCase().trim()
    const matchesSearch =
      !q ||
      (item.name || "").toLowerCase().includes(q) ||
      (item.title || "").toLowerCase().includes(q) ||
      (item.id || "").toLowerCase().includes(q) ||
      (item.category || "").toLowerCase().includes(q) ||
      (item.tags || []).some((t) => String(t).toLowerCase().includes(q))
    if (!matchesSearch) return false
    if (catalogCategory === "all") return true
    if (catalogCategory === "source_missing") return Boolean(item.source_category_missing)
    const cat = (item.category || "").toLowerCase()
    return cat === catalogCategory.toLowerCase()
  }).sort((a, b) => {
    const aName = a.name || a.id
    const bName = b.name || b.id
    const aOp = (SHIPPED_OPERATIONAL_IDS.has(aName) || DONOR_INTERNALIZED_IDS.has(aName) || Boolean(a.isOperational) || a.integration_status === "SHIPPED_OPERATIONAL" || a.integration_status === "INTERNALIZED") ? 2 : ((DONOR_PACKAGED_IDS.has(aName) || Boolean(a.isPackaged)) ? 1 : 0)
    const bOp = (SHIPPED_OPERATIONAL_IDS.has(bName) || DONOR_INTERNALIZED_IDS.has(bName) || Boolean(b.isOperational) || b.integration_status === "SHIPPED_OPERATIONAL" || b.integration_status === "INTERNALIZED") ? 2 : ((DONOR_PACKAGED_IDS.has(bName) || Boolean(b.isPackaged)) ? 1 : 0)
    return bOp - aOp
  })

  // Audio playback handler
  const handleToggleAudio = (e, asset) => {
    e.stopPropagation()
    const key = asset.key || asset.id
    if (playingAudioKey === key) {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause()
        audioPlayerRef.current = null
      }
      setPlayingAudioKey(null)
    } else {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause()
      }
      const streamUrl = asset.stream_url || (asset.id ? `/api/downloaded/${asset.id}/stream` : null)
      if (streamUrl) {
        const audio = new Audio(streamUrl)
        audio.onended = () => {
          setPlayingAudioKey(null)
          audioPlayerRef.current = null
        }
        audio.onerror = () => {
          setPlayingAudioKey(null)
          audioPlayerRef.current = null
        }
        audio.play().catch(() => {
          setPlayingAudioKey(null)
        })
        audioPlayerRef.current = audio
        setPlayingAudioKey(key)
      }
    }
  }

  // Hover Ghost Preview handlers with 200ms debounce
  const handleCatalogItemMouseEnter = (item) => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current)
    const requestId = ++hoverCounterRef.current
    hoverTimerRef.current = setTimeout(() => {
      if (hoverCounterRef.current === requestId && onStartGhostPreview) {
        onStartGhostPreview(item)
      }
    }, 200)
  }

  const handleCatalogItemMouseLeave = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current)
      hoverTimerRef.current = null
    }
    hoverCounterRef.current++
    if (onEndGhostPreview) {
      onEndGhostPreview()
    }
  }

  // Helper to determine media type of asset
  const getAssetMediaType = (asset) => {
    if (asset.media) return asset.media
    const fn = (asset.filename || asset.title || "").toLowerCase()
    if (fn.endsWith(".mp3") || fn.endsWith(".wav") || fn.endsWith(".aac") || fn.endsWith(".m4a")) return "audio"
    if (fn.endsWith(".png") || fn.endsWith(".jpg") || fn.endsWith(".jpeg") || fn.endsWith(".webp") || fn.endsWith(".gif")) return "image"
    return "video"
  }

  // Helper to render platform icon and chip
  const renderPlatformBadge = (platform) => {
    const p = (platform || "web").toLowerCase()
    if (p.includes("youtube")) {
      return (
        <Chip
          size="small"
          icon={<IconBrandYoutube size={12} color="#ffffff" />}
          label="YouTube"
          sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#ef4444", color: "#ffffff", "& .MuiChip-icon": { color: "#ffffff" } }}
        />
      )
    }
    if (p.includes("tiktok")) {
      return (
        <Chip
          size="small"
          icon={<IconBrandTiktok size={12} color="#ffffff" />}
          label="TikTok"
          sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#0f172a", color: "#00f2fe", "& .MuiChip-icon": { color: "#00f2fe" } }}
        />
      )
    }
    if (p.includes("instagram")) {
      return (
        <Chip
          size="small"
          icon={<IconBrandInstagram size={12} color="#ffffff" />}
          label="Instagram"
          sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#d946ef", color: "#ffffff", "& .MuiChip-icon": { color: "#ffffff" } }}
        />
      )
    }
    return (
      <Chip
        size="small"
        icon={<IconWorld size={12} color="#475569" />}
        label={platform || "Web"}
        sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#f1f5f9", color: "#334155" }}
      />
    )
  }

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
          <Tab label={`Assets (${safeAssets.length})`} />
          <Tab label={`Sources (${safeTrends.length})`} />
          <Tab label="Catalog" />
        </Tabs>

        {/* Search & Ingest URL Row */}
        <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 1 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              bgcolor: "#f8fafc",
              borderRadius: 1.5,
              px: 1,
              py: 0.25,
              border: "1px solid",
              borderColor: "divider",
              flex: 1,
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
        </Stack>
      </Box>

      {/* Content Area */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 1.5 }}>
        {loading ? (
          <Stack alignItems="center" justifyContent="center" sx={{ height: 160, color: "text.secondary" }}>
            <CircularProgress size={20} />
            <Typography variant="caption" sx={{ mt: 1 }}>Loading assets…</Typography>
          </Stack>
        ) : tab === 0 ? (
          // Tab 0: Library Assets (Video, Image, Audio)
          filteredAssets.length === 0 ? (
            <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 4 }}>
              No library assets found.
            </Typography>
          ) : (
            <Stack spacing={1}>
              {filteredAssets.map((asset) => {
                const isSelected = String(asset.id) === String(selectedAssetId)
                const mediaType = getAssetMediaType(asset)
                const isPlayingThis = playingAudioKey === (asset.key || asset.id)
                const thumbUrl = asset.thumb_url || (mediaType === "video" && asset.id ? `/api/videos/${asset.id}/thumbnail` : null)

                return (
                  <Box
                    key={asset.key || asset.id}
                    data-testid="asset-card"
                    draggable
                    onDragStart={(e) => {
                      const resolvedKey = asset.key || asset.id
                      const motionIntent = {
                        asset_id: String(asset.id || resolvedKey),
                        key: String(resolvedKey),
                        title: asset.title || (mediaType === "audio" ? "Audio Track" : "Media Clip"),
                        media_type: mediaType,
                        stream_url: asset.stream_url || (asset.id ? `/api/downloaded/${asset.id}/stream` : `/api/library/asset/${resolvedKey}`),
                        duration_seconds: Number(asset.duration_seconds || asset.duration || 5),
                        aspect_ratio: asset.aspect_ratio || aspectRatio || "9:16",
                        source_provenance: asset.source_provenance || "library_user_asset",
                        permitted_uses: Array.isArray(asset.permitted_uses) ? asset.permitted_uses : ["timeline_motion", "derivative_clips", "commercial_creator"],
                        intent_action: "add_track",
                        target_track: mediaType === "audio" ? "audio" : "video",
                        target_start_time_seconds: 0.0,
                        file_sha256: asset.sha256 || asset.file_sha256 || null,
                      }
                      const payload = {
                        kind: "asset",
                        mediaType,
                        data: asset,
                        title: motionIntent.title,
                        duration: motionIntent.duration_seconds,
                        ...motionIntent,
                      }
                      e.dataTransfer.setData("application/x-6clips-asset", JSON.stringify(motionIntent))
                      e.dataTransfer.setData("application/viralmint-clip", JSON.stringify(payload))
                      e.dataTransfer.setData("application/json", JSON.stringify(payload))
                      e.dataTransfer.effectAllowed = "copy"
                    }}
                    onClick={() => onSelectSource && onSelectSource(asset)}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: isSelected ? "2px solid #8b5cf6" : "1px solid",
                      borderColor: isSelected ? "#8b5cf6" : "divider",
                      bgcolor: isSelected ? "#f5f3ff" : "#ffffff",
                      cursor: "grab",
                      transition: "all 0.15s ease",
                      "&:hover": {
                        borderColor: isSelected ? "#8b5cf6" : "primary.light",
                        bgcolor: isSelected ? "#ede9fe" : "#f8fafc",
                        boxShadow: "0 2px 8px rgba(139, 92, 246, 0.12)",
                      },
                      "&:active": {
                        cursor: "grabbing",
                      },
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center">
                      {/* Media-Specific Thumbnail Container */}
                      <Box
                        sx={{
                          width: 48,
                          height: 48,
                          borderRadius: 1,
                          bgcolor: "#0f172a",
                          color: "#ffffff",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          overflow: "hidden",
                          flexShrink: 0,
                          position: "relative",
                        }}
                      >
                        {mediaType === "image" && asset.stream_url ? (
                          <Box
                            component="img"
                            src={asset.stream_url}
                            alt={asset.title}
                            loading="lazy"
                            sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                            onError={(e) => { e.target.style.display = "none" }}
                          />
                        ) : mediaType === "video" && thumbUrl ? (
                          <Box
                            component="img"
                            src={thumbUrl}
                            alt={asset.title}
                            loading="lazy"
                            sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                            onError={(e) => { e.target.style.display = "none" }}
                          />
                        ) : null}

                        {/* Fallback Icon overlay if no image or audio */}
                        {mediaType === "audio" ? (
                          <IconButton
                            size="small"
                            onClick={(e) => handleToggleAudio(e, asset)}
                            sx={{ width: 36, height: 36, color: "#ffffff", bgcolor: "rgba(139, 92, 246, 0.4)", "&:hover": { bgcolor: "primary.main" } }}
                          >
                            {isPlayingThis ? <IconPlayerPause size={18} /> : <IconPlayerPlay size={18} />}
                          </IconButton>
                        ) : mediaType === "image" ? (
                          <IconPhoto size={20} color="#94a3b8" />
                        ) : (
                          <IconVideo size={20} color="#94a3b8" />
                        )}
                      </Box>

                      {/* Metadata */}
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
                            color: "text.primary",
                          }}
                        >
                          {asset.title || asset.filename || "Asset"}
                        </Typography>
                        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
                          <Chip
                            size="small"
                            label={mediaType.toUpperCase()}
                            sx={{
                              height: 16,
                              fontSize: "0.58rem",
                              fontWeight: 800,
                              bgcolor: mediaType === "audio" ? "#ecfeff" : mediaType === "image" ? "#fef3c7" : "#ede9fe",
                              color: mediaType === "audio" ? "#0891b2" : mediaType === "image" ? "#b45309" : "#7c3aed",
                            }}
                          />
                          <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                            {asset.duration_seconds || asset.duration ? `${Math.round(asset.duration_seconds || asset.duration)}s` : (asset.size_mb ? `${asset.size_mb} MB` : "Ready")}
                          </Typography>
                        </Stack>
                      </Box>

                      {/* Add to Timeline Button */}
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
          // Tab 1: Contextual Trends / Sources with Real Video Posters
          filteredTrends.length === 0 ? (
            <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 4 }}>
              No trend sources available.
            </Typography>
          ) : (
            <Stack spacing={1}>
              {filteredTrends.map((trend, idx) => {
                const thumbUrl = trend.thumbnail_url

                return (
                  <Box
                    key={trend.id || idx}
                    data-testid="source-card"
                    draggable
                    onDragStart={(e) => {
                      const payload = {
                        kind: "source",
                        mediaType: "video",
                        data: trend,
                        title: trend.title || trend.query || "Trend Source",
                        duration: 5,
                      }
                      e.dataTransfer.setData("application/viralmint-clip", JSON.stringify(payload))
                      e.dataTransfer.setData("application/json", JSON.stringify(payload))
                      e.dataTransfer.effectAllowed = "copy"
                    }}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: "1px solid",
                      borderColor: "divider",
                      bgcolor: "#ffffff",
                      cursor: "grab",
                      transition: "all 0.15s ease",
                      "&:hover": { borderColor: "primary.main", bgcolor: "#fdf4ff", boxShadow: "0 2px 8px rgba(168, 85, 247, 0.12)" },
                      "&:active": { cursor: "grabbing" },
                    }}
                    onClick={() => setPreviewingSource(trend)}
                  >
                    <Stack direction="row" spacing={1} alignItems="center">
                      {/* Video Poster Thumbnail or Styled Platform Fallback */}
                      <Box
                        sx={{
                          width: 52,
                          height: 52,
                          borderRadius: 1,
                          bgcolor: "#0f172a",
                          overflow: "hidden",
                          flexShrink: 0,
                          position: "relative",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {thumbUrl ? (
                          <Box
                            component="img"
                            src={thumbUrl}
                            alt={trend.title}
                            loading="lazy"
                            sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                            onError={(e) => { e.target.style.display = "none" }}
                          />
                        ) : null}
                        <IconTrendingUp size={20} color="#a855f7" />
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
                          {trend.title || trend.query}
                        </Typography>
                        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
                          {renderPlatformBadge(trend.platform)}
                          <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                            Score: {trend.virality_score || trend.traffic || "High"}
                          </Typography>
                        </Stack>
                      </Box>

                      {/* Non-destructive preview eye + Ingest button */}
                      <Stack direction="row" spacing={0.5} alignItems="center">
                        <Tooltip title="Preview source details" arrow>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              setPreviewingSource(trend)
                            }}
                            sx={{ width: 24, height: 24, color: "text.secondary", "&:hover": { color: "primary.main" } }}
                          >
                            <IconEye size={14} />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Ingest to Project" arrow>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              onIngestTrend && onIngestTrend(trend)
                            }}
                            sx={{
                              width: 26,
                              height: 26,
                              bgcolor: "#f3e8ff",
                              color: "#7c3aed",
                              "&:hover": { bgcolor: "#ede9fe" },
                            }}
                          >
                            <IconPlus size={14} stroke={2.5} />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Stack>
                  </Box>
                )
              })}
            </Stack>
          )
        ) : (
          // Tab 2: Real HyperFrames Catalog Blocks with Posters & Hover Preview
          <Box>
            {/* Category Filter Chips */}
            <Stack
              direction="row"
              spacing={0.5}
              sx={{
                mb: 1,
                overflowX: "auto",
                pb: 0.5,
                scrollbarWidth: "none",
                msOverflowStyle: "none",
                "&::-webkit-scrollbar": { display: "none" },
              }}
            >
              {HYPERFRAMES_CATEGORIES.map((cat) => (
                <Chip
                  key={cat.id}
                  size="small"
                  label={cat.label}
                  clickable
                  variant={catalogCategory === cat.id ? "filled" : "outlined"}
                  color={catalogCategory === cat.id ? (cat.id === "source_missing" ? "warning" : "primary") : "default"}
                  onClick={() => setCatalogCategory(cat.id)}
                  sx={{ height: 20, fontSize: "0.65rem", fontWeight: 700 }}
                />
              ))}
            </Stack>

            {catalogLoading ? (
              <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", py: 4, gap: 1 }}>
                <CircularProgress size={20} color="primary" />
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.72rem" }}>
                  Loading catalog blocks…
                </Typography>
              </Box>
            ) : catalogError ? (
              <Box sx={{ p: 2, textAlign: "center" }} data-testid="catalog-error-box">
                <Typography variant="caption" color="error" sx={{ display: "block", mb: 1, fontSize: "0.72rem" }}>
                  {catalogError}
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  data-testid="catalog-retry-btn"
                  onClick={fetchCatalog}
                  sx={{ fontSize: "0.7rem", textTransform: "none", py: 0.25, px: 1.5 }}
                >
                  Retry
                </Button>
              </Box>
            ) : filteredCatalog.length === 0 ? (
              <Box sx={{ py: 4, textAlign: "center", px: 2 }}>
                <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 2 }}>
                  No catalog blocks found.
                </Typography>
                {catalogCategory !== "all" && (
                  <Button
                    size="small"
                    variant="text"
                    onClick={() => setCatalogCategory("all")}
                    sx={{ fontSize: "0.7rem", mt: 1, textTransform: "none" }}
                  >
                    Reset category filter
                  </Button>
                )}
              </Box>
            ) : (
              <Stack spacing={1}>
                {filteredCatalog.map((item) => {
                  const bName = item.name || item.id
                  const isOperational = SHIPPED_OPERATIONAL_IDS.has(bName) || DONOR_INTERNALIZED_IDS.has(bName) || Boolean(item.isOperational) || item.integration_status === "SHIPPED_OPERATIONAL" || item.integration_status === "INTERNALIZED"
                  const isPackaged = isOperational || DONOR_PACKAGED_IDS.has(bName) || Boolean(item.isPackaged)
                  const isShader = DONOR_SHADER_IDS.has(bName) || Boolean(item.isShader)
                  const isLowerThird = DONOR_LOWER_THIRD_IDS.has(bName) || Boolean(item.isLowerThird)
                  const canInsert = isOperational
                  const posterUrl = isPackaged
                    ? (item.poster_url || item.preview?.poster || `/api/projects/catalog/blocks/${bName}/poster?aspect_ratio=${aspectRatio}`)
                    : null

                  let statusChipLabel = isOperational ? "Operational" : "Awaiting Port"
                  let statusBg = isOperational ? "#ecfdf5" : "#f1f5f9"
                  let statusColor = isOperational ? "#047857" : "#94a3b8"
                  if (isOperational) {
                    statusChipLabel = "Operational"
                    statusBg = "#ecfdf5"
                    statusColor = "#047857"
                  } else {
                    statusChipLabel = "Awaiting Port"
                    statusBg = "#f8fafc"
                    statusColor = "#94a3b8"
                  }

                  return (
                    <Box
                      key={bName}
                      data-testid={`catalog-card-${bName}`}
                      data-operational={isOperational}
                      data-packaged={isPackaged}
                      tabIndex={isOperational ? 0 : -1}
                      role="button"
                      aria-label={item.title || bName}
                      title={
                        isOperational
                          ? "Drag onto a compatible timeline track, or hover/focus to preview on player"
                          : "Donor block awaiting stage 2 porting"
                      }
                      onMouseEnter={() => {
                        if (isOperational) handleCatalogItemMouseEnter(item)
                      }}
                      onMouseLeave={handleCatalogItemMouseLeave}
                      onFocus={() => {
                        if (isOperational) handleCatalogItemMouseEnter(item)
                      }}
                      onBlur={handleCatalogItemMouseLeave}
                      onKeyDown={(e) => {
                        if ((e.key === "Enter" || e.key === " ") && isOperational) {
                          e.preventDefault()
                          if (onAddBlock) onAddBlock(item)
                        }
                      }}
                      draggable={isOperational}
                      onDragStart={(e) => {
                        if (!isOperational) return
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
                        borderColor: "divider",
                        bgcolor: "#ffffff",
                        cursor: isOperational ? "grab" : "default",
                        opacity: isOperational ? 1 : isPackaged ? 0.95 : 0.85,
                        transition: "all 0.15s ease",
                        "&:hover, &:focus-visible": {
                          borderColor: isOperational ? "#8b5cf6" : isPackaged ? "#38bdf8" : "warning.main",
                          bgcolor: isOperational ? "#f8fafc" : isPackaged ? "#f0f9ff" : "#fffbeb",
                          boxShadow: isOperational ? "0 2px 8px rgba(139, 92, 246, 0.12)" : "none",
                          outline: "none",
                        },
                      }}
                    >
                      <Stack direction="row" spacing={1} alignItems="center">
                        {/* Visual Poster Thumbnail with Graceful Fallback */}
                        <Box
                          sx={{
                            width: 56,
                            height: 56,
                            borderRadius: 1,
                            bgcolor: isOperational ? "#0f172a" : isPackaged ? "#1e293b" : "#f1f5f9",
                            overflow: "hidden",
                            flexShrink: 0,
                            position: "relative",
                            border: "1px solid rgba(0, 0, 0, 0.08)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          {posterUrl ? (
                            <Box
                              component="img"
                              src={posterUrl}
                              alt={item.title || bName}
                              loading="lazy"
                              sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                              onError={(e) => {
                                e.target.style.display = "none"
                              }}
                            />
                          ) : (
                            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                              <IconSparkles size={16} stroke={1.5} color="#94a3b8" />
                              <Typography variant="caption" sx={{ fontSize: "0.55rem", fontWeight: 700, color: "text.disabled", textAlign: "center", px: 0.5, mt: 0.2 }}>
                                TEMPLATE
                              </Typography>
                            </Box>
                          )}
                        </Box>

                        {/* Title & Metadata */}
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography
                            variant="caption"
                            sx={{
                              fontWeight: 800,
                              color: "text.primary",
                              display: "block",
                              textOverflow: "ellipsis",
                              overflow: "hidden",
                              whiteSpace: "nowrap",
                              fontSize: "0.75rem",
                            }}
                          >
                            {item.title || bName}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              fontFamily: "monospace",
                              fontSize: "0.65rem",
                              color: "text.disabled",
                              display: "block",
                              lineHeight: 1.1,
                            }}
                          >
                            {bName}
                          </Typography>
                          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25, flexWrap: "wrap", gap: 0.5 }}>
                            <Chip
                              size="small"
                              label={statusChipLabel}
                              sx={{
                                height: 16,
                                fontSize: "0.58rem",
                                fontWeight: 800,
                                bgcolor: statusBg,
                                color: statusColor,
                              }}
                            />
                            <Chip
                              size="small"
                              label={item.category_label || item.category || "scenes"}
                              sx={{ height: 16, fontSize: "0.6rem", fontWeight: 700, bgcolor: "#f1f5f9" }}
                            />
                            {(() => {
                              const dims = item.dimensions || {}
                              const isVert = (dims.width && dims.height && dims.width < dims.height) || bName === "weight-wave"
                              const compat = aspectRatio === "9:16"
                                ? (item.aspect_compat_9x16 || (bName === "weight-wave" ? "ADAPTED" : (isVert ? "NATIVE" : "CONTAINED")))
                                : (item.aspect_compat_16x9 || (isVert ? "CONTAINED" : "NATIVE"))
                              const label = compat === "NATIVE" ? "Native" : (compat === "ADAPTED" ? "Adapted" : "Contained")
                              const chipColor = compat === "NATIVE" ? "#0369a1" : (compat === "ADAPTED" ? "#047857" : "#475569")
                              const chipBg = compat === "NATIVE" ? "#e0f2fe" : (compat === "ADAPTED" ? "#d1fae5" : "#f1f5f9")
                              return (
                                <Chip
                                  size="small"
                                  label={label}
                                  sx={{ height: 16, fontSize: "0.58rem", fontWeight: 700, color: chipColor, bgcolor: chipBg }}
                                />
                              )
                            })()}
                            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                              {item.duration || 5}s • {(item.variables || []).length} vars
                            </Typography>
                          </Stack>
                        </Box>
                      </Stack>
                    </Box>
                  )
                })}
              </Stack>
            )}
          </Box>
        )}
      </Box>

      {/* Non-destructive Source Detail & Preview Dialog */}
      {previewingSource && (
        <Dialog
          open={Boolean(previewingSource)}
          onClose={() => setPreviewingSource(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ p: 2, pb: 1, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Stack direction="row" spacing={1} alignItems="center">
              {renderPlatformBadge(previewingSource.platform)}
              <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                Discovered Source Preview
              </Typography>
            </Stack>
            <IconButton size="small" onClick={() => setPreviewingSource(null)}>
              <IconX size={16} />
            </IconButton>
          </DialogTitle>
          <DialogContent sx={{ p: 2 }}>
            {previewingSource.thumbnail_url && (
              <Box
                sx={{
                  width: "100%",
                  maxHeight: 280,
                  borderRadius: 2,
                  overflow: "hidden",
                  bgcolor: "#0f172a",
                  mb: 2,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Box
                  component="img"
                  src={previewingSource.thumbnail_url}
                  alt={previewingSource.title}
                  sx={{ maxWidth: "100%", maxHeight: 280, objectFit: "contain" }}
                />
              </Box>
            )}
            <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 0.5 }}>
              {previewingSource.title || previewingSource.query}
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary", fontSize: "0.8rem", mb: 1.5 }}>
              {previewingSource.description || "No description provided."}
            </Typography>
            <Stack direction="row" spacing={2} sx={{ p: 1.5, bgcolor: "#f8fafc", borderRadius: 1.5, border: "1px solid", borderColor: "divider" }}>
              <Box>
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>Author</Typography>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>{previewingSource.author || "Unknown"}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>Views</Typography>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>{previewingSource.views ? Number(previewingSource.views).toLocaleString() : "—"}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>Virality Score</Typography>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>{previewingSource.virality_score || previewingSource.traffic || "High"}</Typography>
              </Box>
            </Stack>
          </DialogContent>
          <DialogActions sx={{ p: 2, pt: 1 }}>
            <Button onClick={() => setPreviewingSource(null)} sx={{ textTransform: "none" }}>
              Close
            </Button>
            <Button
              variant="contained"
              sx={{ bgcolor: "primary.main", textTransform: "none", fontWeight: 700 }}
              onClick={() => {
                const src = previewingSource
                setPreviewingSource(null)
                if (onIngestTrend) onIngestTrend(src)
              }}
            >
              Ingest to Project
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  )
}
