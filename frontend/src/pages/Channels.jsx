import { useState, useEffect, useCallback } from "react"
import {
  Box, Typography, Tabs, Tab, Button, Chip, Stack, Paper, IconButton,
  CircularProgress, Alert, Avatar, Divider, Tooltip, FormControl, Select,
  MenuItem, TextField, Card, CardMedia, CardContent, TablePagination,
} from "@mui/material"
import {
  IconBrandYoutube,
  IconBroadcast,
  IconRefresh,
  IconPlayerPlay,
  IconExternalLink,
  IconWorld,
  IconDownload,
  IconLink,
  IconUnlink,
  IconSearch,
  IconCircleCheck,
  IconPlus,
  IconArrowLeft,
  IconEye,
  IconThumbUp,
  IconMessageDots,
  IconSend,
  IconSparkles,
  IconInbox,
} from "@tabler/icons-react"
import http from "../api/http"
import useAppStore from "../store/appStore"

function formatCount(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function timeAgo(dateStr) {
  if (!dateStr) return ""
  const d = typeof dateStr === "number" ? new Date(dateStr * 1000) : new Date(dateStr)
  const diff = Date.now() - d.getTime()
  const days = Math.floor(diff / 86400000)
  if (days < 1) return "Today"
  if (days === 1) return "1d ago"
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

function parseDuration(iso) {
  if (!iso) return ""
  const m = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/)
  if (!m) return ""
  const h = parseInt(m[1] || 0)
  const min = parseInt(m[2] || 0)
  const s = parseInt(m[3] || 0)
  if (h > 0) return `${h}:${String(min).padStart(2, "0")}:${String(s).padStart(2, "0")}`
  return `${min}:${String(s).padStart(2, "0")}`
}

/* ── Connect Form (search + URL fallback) ──────────────────────── */

function ConnectForm({ platform, onConnected }) {
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState("")
  const [results, setResults] = useState(null)
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [url, setUrl] = useState("")
  const isYT = platform === "youtube"
  const label = isYT ? "YouTube" : "TikTok"

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    setError("")
    setResults(null)
    try {
      const { data } = await http.get("/api/channels/search", {
        params: { q: query.trim(), platform },
      })
      setResults(data.results || [])
      if ((data.results || []).length === 0) {
        setError("No channels found. Try a different name or use the URL option below.")
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setSearching(false)
    }
  }

  const handleSelect = async (channel) => {
    setLoading(true)
    setError("")
    try {
      await http.post("/api/channels/connect", { platform, url: channel.url })
      onConnected()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleConnectUrl = async () => {
    if (!url.trim()) return
    setLoading(true)
    setError("")
    try {
      await http.post("/api/channels/connect", { platform, url: url.trim() })
      onConnected()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Paper elevation={0} sx={{
      p: 4, textAlign: "center", borderRadius: "18px",
      border: "2px dashed", borderColor: "rgba(139, 92, 246, 0.4)",
      bgcolor: (theme) => theme.palette.mode === "dark" ? "rgba(139, 92, 246, 0.05)" : "rgba(139, 92, 246, 0.03)",
    }}>
      {isYT ? (
        <IconBrandYoutube size={48} stroke={1.5} style={{ color: "#a78bfa", marginBottom: 8, opacity: 0.9 }} />
      ) : (
        <IconBroadcast size={48} stroke={1.5} style={{ color: "#a78bfa", marginBottom: 8, opacity: 0.9 }} />
      )}
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
        Connect a {label} Channel
      </Typography>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2.5, maxWidth: 480, mx: "auto" }}>
        Search for any {label} channel by name{isYT ? "" : " or @handle"} to view analytics and download videos
      </Typography>

      <Stack direction="row" spacing={1} sx={{ maxWidth: 480, mx: "auto", mb: 2 }}>
        <TextField
          fullWidth size="small"
          placeholder={isYT ? "Search by channel name..." : "Search by @handle or name..."}
          value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          disabled={searching || loading}
          sx={{ "& .MuiOutlinedInput-root": { borderRadius: "12px" } }}
        />
        <Button variant="contained" onClick={handleSearch} disabled={searching || !query.trim() || loading}
          startIcon={searching ? <CircularProgress size={16} /> : <IconSearch size={18} stroke={1.8} />}
          sx={{ whiteSpace: "nowrap", minWidth: 100, borderRadius: "20px" }}>
          Search
        </Button>
      </Stack>

      {results && results.length > 0 && (
        <Stack spacing={1} sx={{ maxWidth: 520, mx: "auto", mb: 2 }}>
          {results.map((ch) => (
            <Paper key={ch.channel_id || ch.username} elevation={0}
              sx={{
                display: "flex", alignItems: "center", gap: 1.5, p: 1.5,
                border: 1, borderColor: "divider", borderRadius: "14px", textAlign: "left",
                cursor: "pointer", "&:hover": { borderColor: "primary.main", bgcolor: "action.hover" },
              }}
              onClick={() => handleSelect(ch)}>
              <Avatar src={ch.thumbnail_url} sx={{ width: 48, height: 48 }} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600, fontSize: "0.9rem" }}>
                  {ch.title || ch.display_name}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 0.25 }}>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    {formatCount(ch.subscriber_count || ch.follower_count)} {isYT ? "subscribers" : "followers"}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    {formatCount(ch.video_count)} videos
                  </Typography>
                </Stack>
              </Box>
              {loading ? <CircularProgress size={20} /> : (
                <Tooltip title="Select this channel">
                  <IconButton size="small">
                    <IconCircleCheck size={22} stroke={1.8} style={{ color: "#8b5cf6" }} />
                  </IconButton>
                </Tooltip>
              )}
            </Paper>
          ))}
        </Stack>
      )}

      {error && (
        <Typography variant="caption" sx={{ color: "error.main", mb: 1.5, display: "block" }}>{error}</Typography>
      )}

      <Divider sx={{ my: 2, maxWidth: 480, mx: "auto" }}>
        <Chip label="or" size="small" />
      </Divider>

      {!showUrlInput ? (
        <Button size="small" variant="text" onClick={() => setShowUrlInput(true)}
          startIcon={<IconLink size={16} stroke={1.8} />} sx={{ color: "text.secondary", borderRadius: "20px" }}>
          Connect with channel URL instead
        </Button>
      ) : (
        <Stack direction="row" spacing={1} sx={{ maxWidth: 480, mx: "auto" }}>
          <TextField
            fullWidth size="small"
            placeholder={isYT ? "https://youtube.com/@yourchannel" : "https://tiktok.com/@yourprofile"}
            value={url} onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleConnectUrl()}
            disabled={loading}
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: "12px" } }}
          />
          <Button variant="outlined" onClick={handleConnectUrl} disabled={loading || !url.trim()}
            startIcon={loading ? <CircularProgress size={16} /> : <IconLink size={16} stroke={1.8} />}
            sx={{ whiteSpace: "nowrap", minWidth: 100, borderRadius: "20px" }}>
            Connect
          </Button>
        </Stack>
      )}
    </Paper>
  )
}

/* ── Video Card with inline play ──────────────────────────────── */

function VideoCard({ video, platform, onAnalyze, onDownload }) {
  const isYT = platform === "youtube"
  const duration = isYT
    ? parseDuration(video.duration)
    : video.duration > 0
      ? `${Math.floor(video.duration / 60)}:${String(video.duration % 60).padStart(2, "0")}`
      : ""
  const uploadDate = isYT ? video.published_at : video.created_at

  // Build watch URL for opening in browser
  const watchUrl = isYT
    ? `https://www.youtube.com/watch?v=${video.video_id}`
    : video.url || `https://www.tiktok.com/video/${video.video_id}`
  const thumbUrl = isYT ? video.thumbnail_url : video.cover_url

  return (
    <Card variant="outlined" sx={{
      position: "relative",
      borderRadius: "16px",
      transition: "border-color 0.2s, box-shadow 0.2s",
      "&:hover": { borderColor: "primary.main", boxShadow: "0 4px 20px rgba(139,92,246,0.2)" },
    }}>
      {/* Video area: thumbnail with play overlay — opens in browser */}
      <Box sx={{ position: "relative", width: "100%", height: 160, bgcolor: "black", cursor: "pointer", "&:hover .play-icon": { transform: "scale(1.15)", opacity: 1 } }}
        onClick={() => window.open(watchUrl, "_blank")}
      >
        {duration && (
          <Chip label={duration} size="small"
            sx={{ position: "absolute", top: 8, right: 8, zIndex: 2, height: 22, fontSize: "0.7rem", bgcolor: "rgba(0,0,0,0.75)", color: "#fff", "& .MuiChip-label": { px: 0.75 } }} />
        )}
        <CardMedia
          component="img" height={160}
          image={thumbUrl}
          alt={video.title}
          sx={{ cursor: "pointer" }}
          onError={(e) => { e.target.style.display = "none" }}
        />
        {/* Play button overlay */}
        <Box sx={{
          position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
          display: "flex", alignItems: "center", justifyContent: "center",
          bgcolor: "transparent",
        }}>
          <IconPlayerPlay className="play-icon" size={48} stroke={1.8} style={{
            color: "rgba(255,255,255,0.85)",
            filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.6))",
            opacity: 0.85, transition: "transform 0.15s, opacity 0.15s",
          }} />
        </Box>
      </Box>

      <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Typography variant="body2" sx={{
          fontWeight: 500, mb: 0.5,
          overflow: "hidden", textOverflow: "ellipsis",
          display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
        }}>
          {video.title || "Untitled"}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexWrap: "wrap" }}>
          <Typography variant="caption" sx={{ color: "text.secondary", display: "inline-flex", alignItems: "center" }}>
            <IconEye size={12} stroke={1.8} style={{ verticalAlign: "middle", marginRight: 3 }} />{formatCount(video.view_count)} &middot;&nbsp;
            <IconThumbUp size={12} stroke={1.8} style={{ verticalAlign: "middle", marginRight: 3 }} />{formatCount(video.like_count)} &middot;&nbsp;
            <IconMessageDots size={12} stroke={1.8} style={{ verticalAlign: "middle", marginRight: 3 }} />{formatCount(video.comment_count)}
            {!isYT && video.share_count > 0 && ` \u00B7 ${formatCount(video.share_count)} shares`}
          </Typography>
          {video.outlier_score >= 3 && (
            <Chip
              label={video.outlier_score >= 20 ? `🔥 ${video.outlier_score}x` : video.outlier_score >= 10 ? `⚡ ${video.outlier_score}x` : video.outlier_score >= 5 ? `🚀 ${video.outlier_score}x` : `${video.outlier_score}x`}
              size="small"
              color={video.outlier_score >= 10 ? "error" : video.outlier_score >= 5 ? "warning" : "info"}
              variant="outlined"
              sx={{ fontWeight: 700, fontSize: "0.6rem", height: 18 }}
            />
          )}
        </Box>
        <Typography variant="caption" sx={{ color: "text.disabled", fontSize: "0.7rem", display: "block", mt: 0.5 }}>
          {uploadDate ? timeAgo(uploadDate) : ""}
          {uploadDate && (() => {
            const d = typeof uploadDate === "number" ? new Date(uploadDate * 1000) : new Date(uploadDate)
            return isNaN(d.getTime()) ? "" : ` \u00B7 ${d.toLocaleDateString()}`
          })()}
        </Typography>
        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.75 }}>
          <Button size="small" variant="contained" startIcon={<IconDownload size={15} stroke={1.8} />}
            onClick={(e) => { e.stopPropagation(); onDownload(video) }}
            sx={{ borderRadius: "20px" }}>
            Download & Analyze
          </Button>
          <Box sx={{ flex: 1 }} />
          <Tooltip title="Analyze this video" arrow>
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); onAnalyze(video) }}
              sx={{ p: 0.5, color: "text.secondary", "&:hover": { color: "primary.main" } }}>
              <IconWorld size={18} stroke={1.8} />
            </IconButton>
          </Tooltip>
          <Tooltip title={`Open on ${isYT ? "YouTube" : "TikTok"}`} arrow>
            <IconButton size="small"
              onClick={(e) => { e.stopPropagation(); window.open(video.url, "_blank", "noopener") }}
              sx={{ p: 0.5, color: "text.secondary", "&:hover": { color: "primary.main" } }}>
              <IconExternalLink size={18} stroke={1.8} />
            </IconButton>
          </Tooltip>
        </Stack>
      </CardContent>
    </Card>
  )
}

/* ── Channel Detail View (videos grid) ─────────────────────────── */

function ChannelDetail({ channel, onBack }) {
  const [channelInfo, setChannelInfo] = useState(null)
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortBy, setSortBy] = useState("recent")
  // Videos open in browser (no embedded iframe — avoids YouTube bot detection)
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(20)
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const isYT = channel.platform === "youtube"

  const fetchData = useCallback(async (refresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (refresh) params.refresh = true
      const { data: resp } = await http.get(`/api/channels/videos/${channel.id}`, { params })
      setVideos(resp.videos || [])
      setChannelInfo(resp.channel || resp.user || null)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [channel.id])

  useEffect(() => { fetchData() }, [fetchData])

  const handleRefresh = () => {
    setVideos([])
    setPage(0)
    fetchData(true)
  }

  const handleAnalyze = async (video) => {
    try {
      await http.post("/api/channels/analyze", { video_url: video.url, title: video.title })
      showSnackbar(`Analyzing: ${video.title || "video"}`, "info")
    } catch (e) {
      showSnackbar(`Failed to start analysis: ${e.response?.data?.detail || e.message}`, "error")
    }
  }

  const handleDownload = async (video) => {
    try {
      await http.post("/api/downloaded/batch-download", {
        urls: [{ url: video.url, title: video.title || "" }],
      })
      showSnackbar(`Downloading: ${video.title || "video"}`, "info", { label: "View in Library", href: "/videos" })
    } catch (e) {
      showSnackbar(`Download failed: ${e.response?.data?.detail || e.message}`, "error")
    }
  }

  const sorted = [...videos].sort((a, b) => {
    if (sortBy === "views") return b.view_count - a.view_count
    if (sortBy === "likes") return b.like_count - a.like_count
    return 0
  })

  const paged = sorted.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)

  return (
    <Box>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 2 }}>
        <IconButton size="small" onClick={onBack} sx={{ borderRadius: "10px" }}>
          <IconArrowLeft size={20} stroke={1.8} />
        </IconButton>
        <Avatar src={channel.thumbnail_url || channelInfo?.thumbnail_url} sx={{ width: 44, height: 44 }} />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, fontSize: "1rem" }}>
            {channel.channel_name || channelInfo?.title || channelInfo?.display_name || "Channel"}
          </Typography>
          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
            <Chip size="small" variant="outlined"
              label={`${formatCount(channel.subscriber_count || channelInfo?.subscriber_count || channelInfo?.follower_count || 0)} ${isYT ? "subscribers" : "followers"}`} />
            <Chip size="small" variant="outlined"
              label={`${formatCount(channel.video_count || channelInfo?.video_count || 0)} videos`} />
            {channelInfo?.median_views > 0 && (
              <Chip size="small" variant="outlined" color="info"
                label={`Median: ${formatCount(channelInfo.median_views)} views`} />
            )}
          </Stack>
        </Box>
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={handleRefresh} sx={{ borderRadius: "10px" }}>
            <IconRefresh size={18} stroke={1.8} />
          </IconButton>
        </Tooltip>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* Performance Analytics Summary */}
      {!loading && videos.length > 0 && (() => {
        const views = videos.map(v => v.view_count || 0).filter(v => v > 0)
        const likes = videos.map(v => v.like_count || 0).filter(l => l > 0)
        const totalViews = views.reduce((a, b) => a + b, 0)
        const avgViews = views.length ? Math.round(totalViews / views.length) : 0
        const sortedViews = [...views].sort((a, b) => a - b)
        const medianViews = sortedViews.length ? sortedViews[Math.floor(sortedViews.length / 2)] : 0
        const topPerformer = videos.reduce((best, v) => (v.view_count || 0) > (best.view_count || 0) ? v : best, videos[0])
        const totalLikes = likes.reduce((a, b) => a + b, 0)
        const engagementRate = totalViews > 0 ? ((totalLikes / totalViews) * 100).toFixed(2) : 0
        const recentVideos = videos.filter(v => {
          const raw = v.published_at || v.upload_date || v.created_at
          if (!raw) return false
          const d = typeof raw === "number" ? new Date(raw * 1000) : new Date(raw)
          return !isNaN(d.getTime()) && (Date.now() - d.getTime()) < 30 * 86400000
        })

        const stats = [
          { label: "Total Views", value: formatCount(totalViews) },
          { label: "Avg Views", value: formatCount(avgViews) },
          { label: "Median Views", value: formatCount(medianViews) },
          { label: "Engagement", value: `${engagementRate}%` },
          { label: "Last 30d", value: `${recentVideos.length} videos` },
          { label: "Top Video", value: formatCount(topPerformer?.view_count || 0) + " views" },
        ]

        return (
          <Box sx={{
            display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 1.5, mb: 2,
          }}>
            {stats.map(s => (
              <Paper key={s.label} variant="outlined" sx={{ p: 1.5, borderRadius: "14px", textAlign: "center" }}>
                <Typography variant="h6" sx={{ fontWeight: 700, fontSize: "1.1rem", lineHeight: 1.2 }}>
                  {s.value}
                </Typography>
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
                  {s.label}
                </Typography>
              </Paper>
            ))}
          </Box>
        )
      })()}

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress size={32} />
        </Box>
      ) : error ? (
        <Alert severity="error" sx={{ borderRadius: "14px" }}>{error}</Alert>
      ) : (
        <>
          {/* Sort control */}
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, fontSize: "0.7rem" }}>
              {videos.length} video{videos.length !== 1 ? "s" : ""}
            </Typography>
            <FormControl size="small" sx={{ minWidth: 130 }}>
              <Select value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(0) }}
                sx={{ fontSize: "0.82rem", borderRadius: "12px", "& .MuiSelect-select": { py: 0.5 } }}>
                <MenuItem value="recent">Recent</MenuItem>
                <MenuItem value="views">Most Views</MenuItem>
                <MenuItem value="likes">Most Likes</MenuItem>
              </Select>
            </FormControl>
          </Stack>

          {/* Video cards grid */}
          {sorted.length === 0 ? (
            <Paper elevation={0} sx={{ p: 3, textAlign: "center", border: 1, borderColor: "divider", borderRadius: "14px" }}>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>No videos found.</Typography>
            </Paper>
          ) : (
            <>
              <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 2 }}>
                {paged.map((v) => (
                  <VideoCard key={v.video_id} video={v} platform={channel.platform} onAnalyze={handleAnalyze} onDownload={handleDownload} />
                ))}
              </Box>
              <TablePagination
                component="div"
                count={sorted.length}
                page={page}
                onPageChange={(_, p) => { setPage(p) }}
                rowsPerPage={rowsPerPage}
                onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0) }}
                rowsPerPageOptions={[20, 50, 100]}
                sx={{ borderTop: 1, borderColor: "divider", mt: 1 }}
              />
            </>
          )}
        </>
      )}
    </Box>
  )
}

/* ── Platform Tab (channel list + add) ─────────────────────────── */

function PlatformTab({ platform }) {
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [selectedChannel, setSelectedChannel] = useState(null)
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const isYT = platform === "youtube"

  const fetchChannels = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await http.get("/api/channels/list", { params: { platform } })
      const list = data.channels || []
      setChannels(list)
      // Auto-select if only one channel
      if (list.length === 1 && !selectedChannel) {
        setSelectedChannel(list[0])
      }
    } catch (e) {
      showSnackbar(`Failed to load channels: ${e.message}`, "error")
    } finally {
      setLoading(false)
    }
  }, [platform, showSnackbar]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchChannels() }, [fetchChannels])

  const handleDisconnect = async (ch) => {
    try {
      await http.post("/api/channels/disconnect", { id: ch.id })
      setChannels((prev) => prev.filter((c) => c.id !== ch.id))
      showSnackbar(`${ch.channel_name || "Channel"} disconnected`, "info")
    } catch (e) {
      showSnackbar(`Failed to disconnect: ${e.message}`, "error")
    }
  }

  const handleConnected = () => {
    setShowAdd(false)
    fetchChannels()
  }

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress size={32} />
      </Box>
    )
  }

  // Show channel detail view
  if (selectedChannel) {
    return (
      <ChannelDetail
        channel={selectedChannel}
        onBack={() => setSelectedChannel(null)}
      />
    )
  }

  // Show add form
  if (showAdd || channels.length === 0) {
    return (
      <Box>
        {channels.length > 0 && (
          <Button size="small" startIcon={<IconArrowLeft size={16} stroke={1.8} />} onClick={() => setShowAdd(false)}
            sx={{ mb: 2, borderRadius: "20px" }}>
            Back to channels
          </Button>
        )}
        <ConnectForm platform={platform} onConnected={handleConnected} />
      </Box>
    )
  }

  // Channel list
  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 600 }}>
          {channels.length} channel{channels.length !== 1 ? "s" : ""} connected
        </Typography>
        <Button variant="contained" startIcon={<IconPlus size={18} stroke={1.8} />} onClick={() => setShowAdd(true)} sx={{ borderRadius: "20px" }}>
          Add Channel
        </Button>
      </Stack>

      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 2 }}>
        {channels.map((ch) => (
          <Card key={ch.id} variant="outlined" sx={{
            borderRadius: "16px", cursor: "pointer",
            "&:hover": { borderColor: "primary.main", boxShadow: "0 4px 20px rgba(139, 92, 246, 0.2)" },
            transition: "all 0.15s",
          }}>
            <CardContent
              sx={{ display: "flex", alignItems: "center", gap: 1.5, p: 2, "&:last-child": { pb: 2 } }}
              onClick={() => setSelectedChannel(ch)}
            >
              <Avatar src={ch.thumbnail_url} sx={{ width: 52, height: 52 }}>
                {isYT ? <IconBrandYoutube size={26} stroke={1.8} /> : <IconBroadcast size={26} stroke={1.8} />}
              </Avatar>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Tooltip title={ch.channel_name || ch.channel_url} enterDelay={500}>
                  <Typography variant="body2" sx={{ fontWeight: 600, fontSize: "0.92rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {ch.channel_name || ch.channel_url}
                  </Typography>
                </Tooltip>
                <Stack direction="row" spacing={1} sx={{ mt: 0.25 }}>
                  {ch.subscriber_count > 0 && (
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>
                      {formatCount(ch.subscriber_count)} {isYT ? "subs" : "followers"}
                    </Typography>
                  )}
                  {ch.video_count > 0 && (
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>
                      {formatCount(ch.video_count)} videos
                    </Typography>
                  )}
                </Stack>
              </Box>
              <Stack alignItems="center" spacing={0.5}>
                <Button size="small" variant="text" sx={{ minWidth: 0, borderRadius: "20px" }}>
                  View videos
                </Button>
                <Tooltip title="Disconnect">
                  <IconButton size="small" onClick={(e) => { e.stopPropagation(); handleDisconnect(ch) }}
                    sx={{ color: "text.secondary" }}>
                    <IconUnlink size={18} stroke={1.8} />
                  </IconButton>
                </Tooltip>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  )
}

/* ── Outcome Delivery Summary (Wave 17 OAAS Consolidation) ───────── */

function OutcomeDeliverySummary({ onSwitchTab }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [receipts, setReceipts] = useState([])
  const [distributionJobs, setDistributionJobs] = useState([])
  const [providerStatus, setProviderStatus] = useState(null)
  const showSnackbar = useAppStore((s) => s.showSnackbar)

  const loadOutcomeData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [recRes, jobsRes, statRes] = await Promise.allSettled([
        http.get("/api/analytics/receipts"),
        http.get("/api/distribution/jobs"),
        http.get("/api/analytics/status"),
      ])

      if (recRes.status === "fulfilled") {
        setReceipts(recRes.value.data?.receipts || [])
      }
      if (jobsRes.status === "fulfilled") {
        setDistributionJobs(jobsRes.value.data?.jobs || jobsRes.value.data || [])
      }
      if (statRes.status === "fulfilled") {
        setProviderStatus(statRes.value.data)
      }
    } catch (e) {
      setError(e.message || "Failed to load outcome data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOutcomeData()
  }, [loadOutcomeData])

  const handleCancelJob = async (jobId) => {
    try {
      await http.post(`/api/distribution/jobs/${jobId}/cancel`)
      showSnackbar(`Cancelled release job ${jobId}`, "info")
      loadOutcomeData()
    } catch (e) {
      showSnackbar(`Cancel failed: ${e.response?.data?.detail || e.message}`, "error")
    }
  }

  const isYtConnected = providerStatus?.youtube?.connected || false
  const isTtConnected = providerStatus?.tiktok?.connected || false

  return (
    <Box data-testid="outcome-summary" sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Top Banner / Truth Disclosure */}
      <Alert severity="info" sx={{ borderRadius: "14px", border: "1px solid rgba(14, 165, 233, 0.25)" }}>
        <strong>Outcome-As-A-Service (OAAS):</strong> Video distribution, multi-platform scheduling, and performance analytics are consolidated into automated background services. Platforms are <code>NOT_CONNECTED</code> by default; live publication outcomes appear only upon verified provider receipts.
      </Alert>

      {/* KPI / Metric Outcome Cards */}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: "14px", bgcolor: "#f8fafc" }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box sx={{ width: 40, height: 40, borderRadius: "10px", bgcolor: "#ecfdf5", color: "#059669", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <IconCircleCheck size={22} stroke={1.8} />
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem" }}>
                Verified Published
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 800, color: "text.primary" }}>
                {receipts.length}
              </Typography>
            </Box>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: "14px", bgcolor: "#f8fafc" }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box sx={{ width: 40, height: 40, borderRadius: "10px", bgcolor: "#f0f9ff", color: "#0284c7", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <IconSend size={22} stroke={1.8} />
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem" }}>
                Scheduled Queue
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 800, color: "text.primary" }}>
                {distributionJobs.length}
              </Typography>
            </Box>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: "14px", bgcolor: "#f8fafc" }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box sx={{ width: 40, height: 40, borderRadius: "10px", bgcolor: "#faf5ff", color: "#7c3aed", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <IconSparkles size={22} stroke={1.8} />
            </Box>
            <Box>
              <Typography variant="caption" sx={{ color: "text.secondary", fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem" }}>
                Connected Platforms
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 800, color: "text.primary" }}>
                {(isYtConnected ? 1 : 0) + (isTtConnected ? 1 : 0)} / 2
              </Typography>
            </Box>
          </Stack>
        </Paper>
      </Box>

      {/* Platform Connectors Section */}
      <Paper variant="outlined" data-testid="platform-connectors" sx={{ p: 2.5, borderRadius: "16px" }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
          Platform Credentials & Automation State
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <Box sx={{ flex: 1, p: 2, borderRadius: "12px", border: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Avatar sx={{ bgcolor: "#fee2e2", color: "#ef4444" }}>
                <IconBrandYoutube size={22} />
              </Avatar>
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>YouTube API</Typography>
                <Chip
                  size="small"
                  label={isYtConnected ? "CONNECTED" : "NOT_CONNECTED"}
                  color={isYtConnected ? "success" : "default"}
                  sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700, mt: 0.5 }}
                />
              </Box>
            </Stack>
            <Button
              size="small"
              variant={isYtConnected ? "outlined" : "contained"}
              onClick={() => onSwitchTab(1)}
              sx={{ borderRadius: "20px", fontSize: "0.75rem", textTransform: "none" }}
            >
              {isYtConnected ? "Manage Channel" : "Connect YouTube"}
            </Button>
          </Box>

          <Box sx={{ flex: 1, p: 2, borderRadius: "12px", border: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Avatar sx={{ bgcolor: "#f1f5f9", color: "#0f172a" }}>
                <IconBroadcast size={22} />
              </Avatar>
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>TikTok API</Typography>
                <Chip
                  size="small"
                  label={isTtConnected ? "CONNECTED" : "NOT_CONNECTED"}
                  color={isTtConnected ? "success" : "default"}
                  sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700, mt: 0.5 }}
                />
              </Box>
            </Stack>
            <Button
              size="small"
              variant={isTtConnected ? "outlined" : "contained"}
              onClick={() => onSwitchTab(2)}
              sx={{ borderRadius: "20px", fontSize: "0.75rem", textTransform: "none" }}
            >
              {isTtConnected ? "Manage Channel" : "Connect TikTok"}
            </Button>
          </Box>
        </Stack>
      </Paper>

      {/* Published Outcomes (Provider-Verified) */}
      <Paper variant="outlined" data-testid="published-outcomes" sx={{ p: 2.5, borderRadius: "16px" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              Published Outcomes (Provider-Verified)
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Authentic post performance receipts recorded directly from platform endpoints
            </Typography>
          </Box>
          <Tooltip title="Refresh receipts">
            <IconButton size="small" onClick={loadOutcomeData}>
              <IconRefresh size={18} />
            </IconButton>
          </Tooltip>
        </Stack>

        {receipts.length === 0 ? (
          <Box sx={{ p: 4, textAlign: "center", border: "1px dashed", borderColor: "divider", borderRadius: "12px" }}>
            <IconInbox size={40} color="#94a3b8" style={{ marginBottom: 8 }} />
            <Typography variant="subtitle2" sx={{ fontWeight: 800, color: "text.primary" }}>
              AWAITING_PUBLISHED_POST
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary", maxWidth: 480, mx: "auto", mt: 0.5, fontSize: "0.82rem" }}>
              No confirmed publication receipts registered yet. When a video is dispatched through background distribution and verified by the external provider, real metrics will surface here.
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5}>
            {receipts.map((rec, i) => (
              <Box key={rec.id || i} sx={{ p: 1.5, borderRadius: "10px", border: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {rec.title || rec.video_id || `Post ${rec.id}`}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    {rec.platform} · {rec.published_at ? timeAgo(rec.published_at) : "Verified Published"}
                  </Typography>
                </Box>
                <Chip size="small" label="VERIFIED" color="success" sx={{ fontWeight: 700, height: 20 }} />
              </Box>
            ))}
          </Stack>
        )}
      </Paper>

      {/* Pending Approvals & Distribution Queue */}
      <Paper variant="outlined" data-testid="distribution-queue" sx={{ p: 2.5, borderRadius: "16px" }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
          Pending Approvals & Distribution Queue
        </Typography>
        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 2 }}>
          Automated releases awaiting scheduled publication window or background worker dispatch
        </Typography>

        {distributionJobs.length === 0 ? (
          <Box sx={{ p: 3, textAlign: "center", border: "1px dashed", borderColor: "divider", borderRadius: "12px" }}>
            <Typography variant="body2" sx={{ color: "text.secondary", fontSize: "0.82rem" }}>
              No pending releases in the queue. Rendered compositions in Motion Graphics can be dispatched for automated delivery.
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5}>
            {distributionJobs.map((job) => (
              <Box key={job.job_id || job.id} sx={{ p: 1.5, borderRadius: "10px", border: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {job.title || job.output_id || job.job_id}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>
                    Target: {(job.platforms || []).join(", ") || "Multi-platform"} · Status: {job.status}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip size="small" label={job.status || "QUEUED"} color="info" sx={{ fontWeight: 700, height: 20 }} />
                  {job.status !== "published" && job.status !== "failed" && (
                    <Button size="small" color="error" variant="text" onClick={() => handleCancelJob(job.job_id || job.id)}>
                      Cancel
                    </Button>
                  )}
                </Stack>
              </Box>
            ))}
          </Stack>
        )}
      </Paper>
    </Box>
  )
}

/* ── Main Page ─────────────────────────────────────────────────── */

export default function Channels() {
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* ── Header ── */}
      <Box sx={{
        px: 3, py: 2, flexShrink: 0,
        borderBottom: 1, borderColor: "divider",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: (t) => t.palette.mode === "dark"
          ? "linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(18, 18, 22, 1) 100%)"
          : "linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(255, 255, 255, 1) 100%)",
      }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <IconBroadcast size={26} stroke={1.8} style={{ color: "#a78bfa" }} />
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: -0.3 }}>
              My Channel
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Outcome delivery summary, verified published releases, and connected channels
            </Typography>
          </Box>
        </Stack>
      </Box>

      {/* ── Tabs ── */}
      <Box sx={{ px: 3, flexShrink: 0, borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ minHeight: 42 }}>
          <Tab icon={<IconSparkles size={18} stroke={1.8} />} iconPosition="start" label="Outcomes & Delivery" sx={{ textTransform: "none", minHeight: 42, fontSize: "0.9rem" }} />
          <Tab icon={<IconBrandYoutube size={18} stroke={1.8} />} iconPosition="start" label="YouTube" sx={{ textTransform: "none", minHeight: 42, fontSize: "0.9rem" }} />
          <Tab icon={<IconBroadcast size={18} stroke={1.8} />} iconPosition="start" label="TikTok" sx={{ textTransform: "none", minHeight: 42, fontSize: "0.9rem" }} />
        </Tabs>
      </Box>

      {/* ── Scrollable content ── */}
      <Box sx={{ flex: 1, overflow: "auto", p: { xs: 2, md: 3 } }}>
        {tab === 0 && <OutcomeDeliverySummary onSwitchTab={(newTab) => setTab(newTab)} />}
        {tab === 1 && <PlatformTab platform="youtube" />}
        {tab === 2 && <PlatformTab platform="tiktok" />}
      </Box>
    </Box>
  )
}
