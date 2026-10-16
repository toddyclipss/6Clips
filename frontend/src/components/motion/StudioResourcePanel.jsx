// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useRef } from "react"
import {
  Box, Stack, Typography, Tabs, Tab, IconButton, InputBase,
  Tooltip, CircularProgress, Chip, Dialog, DialogTitle,
  DialogContent, DialogActions, Button,
} from "@mui/material"
import {
  IconSearch,
  IconVideo,
  IconTrendingUp,
  IconPlus,
  IconPlayerPlay,
  IconPlayerPause,
  IconPin,
  IconPinnedOff,
  IconPhoto,
  IconEye,
  IconBrandYoutube,
  IconBrandTiktok,
  IconBrandInstagram,
  IconWorld,
  IconX,
} from "@tabler/icons-react"

/**
 * Left Resource Panel: Media Assets and Trend Sources.
 * Exposes real Library media and Trends sources for optional timeline placement.
 * Completely free of template-shopping cards, 196-block catalog UI, and mock previews.
 */
export default function StudioResourcePanel({
  libraryVideos = [],
  trendItems = [],
  loading = false,
  selectedAssetId = null,
  onAddMediaToTimeline,
  onSelectSource,
  isPinned = false,
  onTogglePin,
  aspectRatio = "9:16",
}) {
  const [tab, setTab] = useState(0) // 0 = Assets, 1 = Sources (Trends)
  const [search, setSearch] = useState("")

  // Audio Pre-listening state
  const [playingAudioKey, setPlayingAudioKey] = useState(null)
  const audioPlayerRef = useRef(null)

  // Source Preview Modal state
  const [previewingSource, setPreviewingSource] = useState(null)

  // Stop audio when unmounting or switching tabs
  useEffect(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause()
      audioPlayerRef.current = null
      setPlayingAudioKey(null)
    }
  }, [tab])

  const safeAssets = Array.isArray(libraryVideos) ? libraryVideos : []
  const safeTrends = Array.isArray(trendItems) ? trendItems : []

  // Filtered Assets by search query
  const filteredAssets = safeAssets.filter((asset) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      (asset.title || "").toLowerCase().includes(q) ||
      (asset.filename || "").toLowerCase().includes(q) ||
      (asset.tags || []).some((t) => String(t).toLowerCase().includes(q))
    )
  })

  // Filtered Trends by search query
  const filteredTrends = safeTrends.filter((trend) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      (trend.title || "").toLowerCase().includes(q) ||
      (trend.platform || "").toLowerCase().includes(q) ||
      (trend.author || "").toLowerCase().includes(q) ||
      (trend.summary || "").toLowerCase().includes(q)
    )
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

  // Helper to determine media type of asset
  const getAssetMediaType = (asset) => {
    if (asset.media) return asset.media
    const fn = (asset.filename || asset.title || "").toLowerCase()
    if (fn.endsWith(".mp3") || fn.endsWith(".wav") || fn.endsWith(".aac") || fn.endsWith(".m4a")) return "audio"
    if (fn.endsWith(".png") || fn.endsWith(".jpg") || fn.endsWith(".jpeg") || fn.endsWith(".webp") || fn.endsWith(".gif")) return "image"
    return "video"
  }

  // Helper to render platform badge
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
      data-testid="studio-resource-panel"
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
            Media & Sources
          </Typography>
          <Tooltip title={isPinned ? "Unpin panel" : "Pin panel"} arrow>
            <IconButton size="small" onClick={onTogglePin} sx={{ width: 22, height: 22, color: isPinned ? "primary.main" : "text.secondary" }}>
              {isPinned ? <IconPin size={14} /> : <IconPinnedOff size={14} />}
            </IconButton>
          </Tooltip>
        </Stack>

        {/* Tabs: Assets and Sources only (Zero template shopping picker) */}
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
          <Tab label={`Media Assets (${safeAssets.length})`} data-testid="tab-media-assets" />
          <Tab label={`Trends (${safeTrends.length})`} data-testid="tab-trends-sources" />
        </Tabs>

        {/* Search Row */}
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
              inputProps={{ "data-testid": "resource-search-input" }}
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
            <Typography variant="caption" sx={{ mt: 1 }}>Loading media…</Typography>
          </Stack>
        ) : tab === 0 ? (
          // Tab 0: Library Assets (Video, Image, Audio)
          filteredAssets.length === 0 ? (
            <Typography variant="caption" sx={{ color: "text.disabled", display: "block", textAlign: "center", mt: 4 }}>
              No media assets available in Library.
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
                    key={asset.id || asset.key}
                    data-testid={`asset-card-${asset.id || asset.key}`}
                    draggable
                    onDragStart={(e) => {
                      const payload = {
                        kind: "asset",
                        type: mediaType,
                        mediaType,
                        data: asset,
                        item: asset,
                        title: asset.title || asset.filename || "Media Clip",
                        duration: asset.duration_seconds || asset.duration || 3.0,
                        permitted_uses: ["timeline_motion"],
                      }
                      e.dataTransfer.setData("application/viralmint-clip", JSON.stringify(payload))
                      e.dataTransfer.setData("application/json", JSON.stringify(payload))
                      e.dataTransfer.setData("text/plain", asset.title || asset.filename || "Media Clip")
                    }}
                    onClick={() => {
                      if (onSelectSource) onSelectSource(asset)
                    }}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: "1px solid",
                      borderColor: isSelected ? "primary.main" : "divider",
                      bgcolor: isSelected ? "rgba(139, 92, 246, 0.05)" : "#ffffff",
                      cursor: "grab",
                      transition: "all 0.15s ease",
                      "&:hover": { borderColor: "primary.light", bgcolor: "#f8fafc" },
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center">
                      {/* Media Thumbnail or Audio Icon */}
                      <Box
                        sx={{
                          width: 44,
                          height: 44,
                          borderRadius: 1,
                          bgcolor: "#f1f5f9",
                          border: "1px solid",
                          borderColor: "divider",
                          overflow: "hidden",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          position: "relative",
                        }}
                      >
                        {thumbUrl ? (
                          <Box
                            component="img"
                            src={thumbUrl}
                            alt={asset.title}
                            loading="lazy"
                            sx={{ width: "100%", height: "100%", objectFit: "cover" }}
                            onError={(e) => { e.target.style.display = "none" }}
                          />
                        ) : null}

                        {mediaType === "audio" ? (
                          <IconButton
                            size="small"
                            onClick={(e) => handleToggleAudio(e, asset)}
                            sx={{ width: 36, height: 36, color: "#ffffff", bgcolor: "rgba(139, 92, 246, 0.5)", "&:hover": { bgcolor: "primary.main" } }}
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
                      {onAddMediaToTimeline && (
                        <Tooltip title="Add to Timeline" arrow>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              onAddMediaToTimeline(asset)
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
                      )}
                    </Stack>
                  </Box>
                )
              })}
            </Stack>
          )
        ) : (
          // Tab 1: Contextual Trends / Sources
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
                        kind: "trend",
                        type: "video",
                        mediaType: "video",
                        data: trend,
                        item: trend,
                        title: trend.title || "Trend Video",
                        duration: trend.duration_seconds || 5.0,
                        permitted_uses: ["timeline_motion"],
                      }
                      e.dataTransfer.setData("application/viralmint-clip", JSON.stringify(payload))
                      e.dataTransfer.setData("application/json", JSON.stringify(payload))
                      e.dataTransfer.setData("text/plain", trend.title || "Trend Video")
                    }}
                    onClick={() => {
                      if (onSelectSource) onSelectSource(trend)
                    }}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: "1px solid",
                      borderColor: "divider",
                      bgcolor: "#ffffff",
                      cursor: "grab",
                      transition: "all 0.15s ease",
                      "&:hover": { borderColor: "primary.light", bgcolor: "#f8fafc" },
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Box
                        sx={{
                          width: 44,
                          height: 44,
                          borderRadius: 1,
                          bgcolor: "#f1f5f9",
                          border: "1px solid",
                          borderColor: "divider",
                          overflow: "hidden",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
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
                        ) : (
                          <IconTrendingUp size={20} color="#94a3b8" />
                        )}
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
                            color: "text.primary",
                          }}
                        >
                          {trend.title || "Trend Lead"}
                        </Typography>
                        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
                          {renderPlatformBadge(trend.platform)}
                          {trend.author && (
                            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                              @{trend.author}
                            </Typography>
                          )}
                        </Stack>
                      </Box>

                      {/* Preview Button */}
                      <Tooltip title="Preview source" arrow>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation()
                            setPreviewingSource(trend)
                          }}
                          sx={{ width: 26, height: 26, color: "text.secondary" }}
                        >
                          <IconEye size={15} />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Box>
                )
              })}
            </Stack>
          )
        )}
      </Box>

      {/* Non-destructive Source Video Preview Dialog */}
      {previewingSource && (
        <Dialog
          open={Boolean(previewingSource)}
          onClose={() => setPreviewingSource(null)}
          maxWidth="xs"
          fullWidth
        >
          <DialogTitle sx={{ p: 1.5, pb: 1, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: "0.85rem" }}>
              {previewingSource.title || "Source Preview"}
            </Typography>
            <IconButton size="small" onClick={() => setPreviewingSource(null)}>
              <IconX size={16} />
            </IconButton>
          </DialogTitle>
          <DialogContent sx={{ p: 1.5, pt: 0 }}>
            {previewingSource.thumbnail_url && (
              <Box
                component="img"
                src={previewingSource.thumbnail_url}
                alt={previewingSource.title}
                sx={{ width: "100%", maxHeight: 320, objectFit: "contain", borderRadius: 1.5, bgcolor: "#000000" }}
              />
            )}
            <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mt: 1 }}>
              {previewingSource.summary || previewingSource.description || "Authentic trend source item from discovered channels."}
            </Typography>
          </DialogContent>
          <DialogActions sx={{ p: 1.5, pt: 0 }}>
            <Button size="small" onClick={() => setPreviewingSource(null)} sx={{ textTransform: "none" }}>
              Close
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </Box>
  )
}
