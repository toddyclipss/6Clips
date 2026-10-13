import { useState, useCallback } from "react"
import { Box, Card, CardMedia, CardContent, Typography, Chip, Checkbox, Tooltip, Button, IconButton, Stack } from "@mui/material"
import {
  IconCircleCheck,
  IconPlayerPlayFilled,
  IconVideoOff,
  IconDownload,
  IconTrash,
  IconExternalLink,
  IconEye,
  IconThumbUp,
  IconNews,
  IconBookmarkPlus,
  IconBookmarkFilled,
} from "@tabler/icons-react"

function ViralityChip({ score }) {
  if (score === null || score === undefined) {
    return (
      <Tooltip title="Viral Opportunity Score not calculated" arrow>
        <Chip label="Not scored" size="small" variant="outlined" sx={{ fontWeight: 600, fontSize: "0.7rem", height: 22 }} />
      </Tooltip>
    )
  }
  const num = typeof score === "number" ? score : parseFloat(score)
  if (isNaN(num)) {
    return (
      <Tooltip title="Viral Opportunity Score not calculated" arrow>
        <Chip label="Not scored" size="small" variant="outlined" sx={{ fontWeight: 600, fontSize: "0.7rem", height: 22 }} />
      </Tooltip>
    )
  }
  const color = num >= 70 ? "success" : num >= 40 ? "warning" : "error"
  return (
    <Tooltip title={`Viral Opportunity Score: ${num.toFixed(1)} / 100`} arrow>
      <Chip label={`Score ${num.toFixed(1)}`} size="small" color={color} sx={{ fontWeight: 700, fontSize: "0.7rem", height: 22 }} />
    </Tooltip>
  )
}

function VPHChip({ vph }) {
  if (!vph || vph < 100) return null
  const label = vph >= 5000 ? "TRENDING NOW" : vph >= 1000 ? "Rising" : "Active"
  const color = vph >= 5000 ? "error" : vph >= 1000 ? "warning" : "default"
  return <Chip label={`${label} · ${formatViews(vph)}/hr`} size="small" color={color} variant="outlined" sx={{ fontSize: "0.65rem", height: 22 }} />
}

function OutlierChip({ score }) {
  if (!score || score < 3) return null
  let color, label
  if (score >= 20) { color = "error"; label = `🔥 ${score}x MONSTER` }
  else if (score >= 10) { color = "error"; label = `⚡ ${score}x BREAKOUT` }
  else if (score >= 5) { color = "warning"; label = `🚀 ${score}x STRONG` }
  else { color = "info"; label = `${score}x outlier` }
  return <Chip label={label} size="small" color={color} variant="outlined" sx={{ fontWeight: 700, fontSize: "0.65rem", height: 22 }} />
}

function RoleBadge({ suitability, duration, editorialRole, bytesAvailability, isDownloaded }) {
  const role = editorialRole || (suitability?.is_editable_source || (duration && duration >= 240) ? "editable_source_candidate" : (duration && duration < 180 ? "creative_reference" : "creative_reference"))
  let label = "Creative Reference"
  let color = "secondary"
  let tooltip = "Creative reference for hooks & pacing. Unsuitable as raw footage for 3x60s clips."

  if (role === "editable_source_candidate") {
    label = "Editable Source Candidate"
    color = "success"
    tooltip = `Substantial footage (${duration || ""}s) candidate for multi-clip editing. Requires verified permitted route before byte acquisition.`
  } else if (role === "marginal_source") {
    label = "Marginal Source"
    color = "info"
    tooltip = `Duration (${duration || ""}s) satisfies minimum threshold with limited editorial margin.`
  } else if (role === "topic_research_reference") {
    label = "Topic Research"
    color = "warning"
    tooltip = "Authoritative news / patch notes research reference."
  }

  const hasBytes = bytesAvailability === "available_local" || isDownloaded

  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
      <Tooltip title={tooltip} arrow>
        <Chip
          label={label}
          size="small"
          color={color}
          variant={role === "editable_source_candidate" ? "filled" : "outlined"}
          sx={{ fontWeight: 700, fontSize: "0.65rem", height: 22 }}
        />
      </Tooltip>
      {hasBytes ? (
        <Tooltip title="Physical media bytes verified in local storage." arrow>
          <Chip label="Bytes Ingested" size="small" color="primary" sx={{ fontSize: "0.6rem", height: 20 }} />
        </Tooltip>
      ) : (
        <Tooltip title="Metadata read from public search. Physical bytes not yet ingested." arrow>
          <Chip label="Metadata Read" size="small" variant="outlined" sx={{ fontSize: "0.6rem", height: 20, color: "text.secondary" }} />
        </Tooltip>
      )}
    </Stack>
  )
}

function formatViews(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function getWatchUrl(r) {
  if (r.platform === "youtube" && r.video_id) return `https://www.youtube.com/watch?v=${r.video_id}`
  if (r.platform === "tiktok" && r.video_url) return r.video_url
  if (r.video_url) return r.video_url
  return null
}

const PAGE_SIZE = 50

export default function CardGrid({ results, onSelect, onDownload, onDelete, selectedIds, onToggle }) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const [loadingId, setLoadingId] = useState(null)
  const [brokenThumbs, setBrokenThumbs] = useState(() => new Set())

  const markThumbBroken = useCallback((id) => {
    setBrokenThumbs((prev) => (prev.has(id) ? prev : new Set(prev).add(id)))
  }, [])
  const showMore = useCallback(() => setVisibleCount((c) => c + PAGE_SIZE), [])

  if (!results || results.length === 0) {
    return <Typography sx={{ color: "text.secondary" }}>No results yet.</Typography>
  }

  const handleDownload = async (e, id) => {
    e.stopPropagation()
    setLoadingId(id)
    try { await onDownload(id) } finally { setLoadingId(null) }
  }

  const visible = results.slice(0, visibleCount)

  return (
    <>
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 2 }}>
      {visible.map((r) => {
        const isSelected = selectedIds?.has(r.id)
        const isNews = r.platform === "news"
        const watchUrl = isNews ? null : getWatchUrl(r)

        let newsDesc = null
        if (isNews && r.description) {
          try { newsDesc = typeof r.description === "string" ? JSON.parse(r.description) : r.description } catch { /* ignore */ }
        }

        return (
          <Card
            key={r.id}
            onClick={() => onSelect?.(r)}
            sx={{
              cursor: "pointer",
              position: "relative",
              borderRadius: "18px",
              borderColor: isSelected ? "primary.main" : "divider",
              transition: "border-color 0.2s, box-shadow 0.2s, transform 0.2s",
              "&:hover": { borderColor: "primary.main", boxShadow: "0 4px 14px rgba(139, 92, 246, 0.2)", transform: "translateY(-2px)" },
            }}
          >
            {onToggle && (
              <Checkbox
                checked={isSelected || false}
                onChange={(e) => { e.stopPropagation(); onToggle(r.id, e) }}
                onClick={(e) => e.stopPropagation()}
                size="small"
                sx={{ position: "absolute", top: 6, left: 6, zIndex: 2, p: 0, bgcolor: "background.paper", borderRadius: "6px" }}
              />
            )}

            {r.is_downloaded && (
              <Chip
                icon={isNews ? <IconBookmarkFilled size={14} /> : <IconCircleCheck size={14} stroke={1.8} />}
                label={isNews ? "Saved" : "Downloaded"}
                size="small"
                color="success"
                sx={{ position: "absolute", top: 8, right: 8, zIndex: 2 }}
              />
            )}

            {isNews ? (
              <Box sx={{
                position: "relative", width: "100%", aspectRatio: "16 / 9",
                bgcolor: (t) => t.palette.mode === "dark" ? "rgba(139,92,246,0.08)" : "rgba(139,92,246,0.05)",
                display: "flex", flexDirection: "column", justifyContent: "center", px: 2,
                overflow: "hidden",
              }}>
                {r.thumbnail_url && !brokenThumbs.has(r.id) ? (
                  <>
                    <CardMedia component="img" image={r.thumbnail_url} alt=""
                      onError={() => markThumbBroken(r.id)}
                      sx={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", objectFit: "cover", opacity: 0.15 }} />
                    <Box sx={{ position: "relative", zIndex: 1 }}>
                      <IconNews size={28} stroke={1.8} style={{ color: "#8b5cf6", marginBottom: 4 }} />
                      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", fontWeight: 600 }}>
                        {r.author || newsDesc?.source || "News"}
                      </Typography>
                      {newsDesc?.full_text_preview && (
                        <Typography variant="caption" sx={{
                          color: "text.secondary", display: "-webkit-box",
                          WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden",
                          lineHeight: 1.4, mt: 0.5, fontSize: "0.7rem",
                        }}>
                          {newsDesc.full_text_preview}
                        </Typography>
                      )}
                    </Box>
                  </>
                ) : (
                  <>
                    <IconNews size={28} stroke={1.8} style={{ color: "#8b5cf6", marginBottom: 4 }} />
                    <Typography variant="caption" sx={{ color: "text.secondary", display: "block", fontWeight: 600 }}>
                      {r.author || newsDesc?.source || "News"}
                    </Typography>
                    {newsDesc?.full_text_preview && (
                      <Typography variant="caption" sx={{
                        color: "text.secondary", display: "-webkit-box",
                        WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden",
                        lineHeight: 1.4, mt: 0.5, fontSize: "0.7rem",
                      }}>
                        {newsDesc.full_text_preview}
                      </Typography>
                    )}
                  </>
                )}
              </Box>
            ) : (
              <Box sx={{
                position: "relative",
                width: "100%",
                aspectRatio: "16 / 9",
                overflow: "hidden",
                bgcolor: "#000",
                "&:hover .play-icon": { transform: "scale(1.15)", opacity: 1 },
              }}>
                {r.thumbnail_url && !brokenThumbs.has(r.id) ? (
                  <CardMedia
                    component="img"
                    image={r.thumbnail_url}
                    alt={r.title}
                    onError={() => markThumbBroken(r.id)}
                    sx={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      display: "block",
                    }}
                  />
                ) : (
                  <Box sx={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    bgcolor: "action.hover",
                  }}>
                    <IconVideoOff size={30} stroke={1.5} />
                  </Box>
                )}
                {watchUrl && (
                  <Box onClick={(e) => { e.stopPropagation(); window.open(watchUrl, "_blank") }} sx={{
                    position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: "pointer",
                  }}>
                    <IconPlayerPlayFilled className="play-icon" style={{
                      width: 48, height: 48, color: "rgba(255,255,255,0.9)",
                      filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.5))",
                      opacity: 0.8, transition: "transform 0.15s, opacity 0.15s",
                    }} />
                  </Box>
                )}
                {r.duration_seconds > 0 && (
                  <Box sx={{
                    position: "absolute", bottom: 6, right: 6,
                    bgcolor: "rgba(0,0,0,0.85)", color: "#fff",
                    px: 0.8, py: 0.2, borderRadius: "4px",
                    fontSize: "0.7rem", fontWeight: 700, letterSpacing: 0.5,
                  }}>
                    {Math.floor(r.duration_seconds / 60)}:{(r.duration_seconds % 60).toString().padStart(2, "0")}
                  </Box>
                )}
              </Box>
            )}

            <CardContent sx={{ p: 1.5 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 0.5, flexWrap: "wrap", gap: 0.5 }}>
                <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", flexWrap: "wrap" }}>
                  <Chip label={isNews ? "NEWS" : r.platform} size="small" variant="outlined"
                    icon={isNews ? <IconNews size={13} stroke={1.8} /> : undefined}
                    sx={{ textTransform: "uppercase", fontSize: "0.65rem", height: 22,
                      ...(isNews && { borderColor: "warning.main", color: "warning.main" }) }} />
                  {!isNews && (
                    <RoleBadge
                      suitability={r.suitability_for_3x60s}
                      duration={r.duration_seconds}
                      editorialRole={r.editorial_role}
                      bytesAvailability={r.bytes_availability}
                      isDownloaded={r.is_downloaded}
                    />
                  )}
                  {!isNews && <VPHChip vph={r.views_per_hour} />}
                  {!isNews && <OutlierChip score={r.outlier_score} />}
                  {isNews && newsDesc?.word_count > 0 && (
                    <Chip label={`${newsDesc.word_count} words`} size="small" variant="outlined" sx={{ fontSize: "0.6rem", height: 20 }} />
                  )}
                  {isNews && newsDesc?.emotional_tone && (
                    <Chip label={newsDesc.emotional_tone} size="small" variant="outlined" color="info" sx={{ fontSize: "0.6rem", height: 20 }} />
                  )}
                </Box>
                <ViralityChip score={r.virality_score} />
              </Box>
              <Typography variant="body2" sx={{
                fontWeight: 600, mb: 0.5,
                lineHeight: 1.35,
                overflow: "hidden", textOverflow: "ellipsis",
                display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
              }} title={r.title}>
                {r.title}
              </Typography>

              {isNews ? (
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>
                  {r.author || newsDesc?.source || ""}
                  {r.upload_date && ` · ${new Date(r.upload_date).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`}
                  {newsDesc?.engagement > 0 && ` · ${formatViews(newsDesc.engagement)} engagement`}
                </Typography>
              ) : (
                <Typography variant="caption" sx={{ color: "text.secondary", display: "flex", alignItems: "center", flexWrap: "wrap", gap: 0.5, mb: 1 }}>
                  <span>{r.author}</span> ·
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                    <IconEye size={12} stroke={1.8} />{formatViews(r.views)}
                  </span> ·
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                    <IconThumbUp size={12} stroke={1.8} />{formatViews(r.likes || 0)}
                  </span>
                  {r.upload_date && ` · ${new Date(r.upload_date).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`}
                </Typography>
              )}

              {/* Actions */}
              <Stack direction="row" spacing={0.5} alignItems="center">
                {!r.is_downloaded && (
                  <Tooltip title={isNews ? "Save article" : "Ingest video if authorized route is verified"} arrow>
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={isNews ? <IconBookmarkPlus size={16} stroke={1.8} /> : <IconDownload size={16} stroke={1.8} />}
                      onClick={(e) => handleDownload(e, r.id)}
                      disabled={loadingId === r.id}
                      color={isNews ? "warning" : "primary"}
                      sx={{ borderRadius: "20px", textTransform: "none", fontWeight: 600 }}
                    >
                      {loadingId === r.id ? "Ingesting..." : isNews ? "Save to Library" : "Ingest & Analyze"}
                    </Button>
                  </Tooltip>
                )}
                <Box sx={{ flex: 1 }} />
                {r.video_url && (
                  <Tooltip title={isNews ? "Open article" : "Open original"} arrow>
                    <IconButton
                      size="small"
                      onClick={(e) => { e.stopPropagation(); window.open(r.video_url, "_blank", "noopener") }}
                      sx={{ p: 0.5, color: "text.secondary", borderRadius: "10px", "&:hover": { color: "primary.main" } }}
                    >
                      <IconExternalLink size={16} stroke={1.8} />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip title="Delete" arrow>
                  <IconButton
                    size="small"
                    onClick={(e) => { e.stopPropagation(); onDelete(r.id) }}
                    sx={{ p: 0.5, color: "text.secondary", borderRadius: "10px", "&:hover": { color: "error.main" } }}
                  >
                    <IconTrash size={16} stroke={1.8} />
                  </IconButton>
                </Tooltip>
              </Stack>
            </CardContent>
          </Card>
        )
      })}
    </Box>
    {visibleCount < results.length && (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
        <Button variant="outlined" onClick={showMore} sx={{ borderRadius: "20px" }}>
          Show more ({results.length - visibleCount} remaining)
        </Button>
      </Box>
    )}
    </>
  )
}
