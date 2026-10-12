import { useState, useEffect, useRef } from "react"
import { NavLink } from "react-router-dom"
import {
  Box, Typography, Button, Chip, Stack, Paper, IconButton, Divider,
  Grid, CircularProgress, Tooltip, Menu, MenuItem, ListItemText,
} from "@mui/material"
import {
  IconSparkles,
  IconEdit,
  IconMovie,
  IconX,
  IconClock,
  IconDatabase,
  IconWorld,
  IconAspectRatio,
  IconPlayerPlay,
  IconScissors,
  IconFlame,
  IconLink,
  IconNews,
} from "@tabler/icons-react"
import http from "../../api/http"
import useAppStore from "../../store/appStore"
import { WHISPER_QUALITIES } from "./constants"

function InsightRow({ label, color, value }) {
  return (
    <Box>
      <Typography variant="caption" sx={{ color, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontSize: "0.85rem", lineHeight: 1.5 }}>
        {value}
      </Typography>
    </Box>
  )
}

function AIActionButton({ label, icon, loading, onClick, tooltip }) {
  return (
    <Tooltip title={tooltip || label} placement="top">
      <span>
        <Button
          size="small" variant="outlined"
          startIcon={loading ? <CircularProgress size={14} /> : icon}
          disabled={loading}
          onClick={onClick}
          sx={{
            borderRadius: "20px", textTransform: "none", fontSize: "0.75rem",
            fontWeight: 600, py: 0.4, px: 1.5, minWidth: 0,
            borderColor: "divider", color: "text.secondary",
            "&:hover": { borderColor: "primary.main", color: "primary.main", bgcolor: "action.hover" },
          }}
        >
          {label}
        </Button>
      </span>
    </Tooltip>
  )
}

export default function DownloadedDetail({ video, onUseAsInspiration, onClose, onDetailUpdate }) {
  const [toolsAnchor, setToolsAnchor] = useState(null)
  const [reanalyzeAnchor, setReanalyzeAnchor] = useState(null)
  const [reanalyzing, setReanalyzing] = useState(false)
  const [aiActionLoading, setAiActionLoading] = useState(null)
  const [aiActionResult, setAiActionResult] = useState(null)
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const pollRef = useRef(null)

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current.pollId)
        clearTimeout(pollRef.current.safetyTimeout)
      }
    }
  }, [])

  const handleAiAction = async (action, extra = {}) => {
    setAiActionLoading(action)
    setAiActionResult(null)
    try {
      const res = await http.post(`/api/downloaded/${video.id}/ai-action`, { action, ...extra })
      setAiActionResult({ action, ...res.data })
      showSnackbar(`AI action "${action}" complete`, "success")
    } catch (e) {
      showSnackbar(e.response?.data?.detail || `AI action failed: ${e.message}`, "error")
    } finally {
      setAiActionLoading(null)
    }
  }

  const handleReanalyze = async (quality) => {
    setReanalyzeAnchor(null)
    setReanalyzing(true)
    try {
      const res = await http.post(`/api/downloaded/${video.id}/reanalyze`, { whisper_quality: quality })
      const jobId = res.data.job_id

      // Poll job status until complete
      const pollId = setInterval(async () => {
        try {
          const jr = await http.get(`/api/jobs/${jobId}`)
          const { status, error_message } = jr.data
          if (status === "success") {
            clearInterval(pollId)
            clearTimeout(safetyTimeout)
            setReanalyzing(false)
            showSnackbar("Re-analysis complete!", "success")
            const detail = await http.get(`/api/downloaded/${video.id}`)
            if (onDetailUpdate) onDetailUpdate({ ...detail.data, _type: "downloaded" })
          } else if (status === "failed") {
            clearInterval(pollId)
            clearTimeout(safetyTimeout)
            setReanalyzing(false)
            showSnackbar(`Re-analysis failed: ${error_message || "unknown error"}`, "error")
          }
        } catch { /* keep polling */ }
      }, 3000)

      // Safety: stop polling after 10 minutes (large models take time)
      const safetyTimeout = setTimeout(() => { clearInterval(pollId); setReanalyzing(false) }, 600000)

      // Store cleanup refs so unmount can clear them
      pollRef.current = { pollId, safetyTimeout }
    } catch (e) {
      setReanalyzing(false)
      showSnackbar(`Re-analyze failed: ${e.response?.data?.detail || e.message}`, "error")
    }
  }

  return (
    <Box sx={{ p: 0 }}>
      {/* Media Player */}
      <Box sx={{ mb: 2 }}>
        {video.video_path ? (
          <Box
            component="video"
            controls
            preload="metadata"
            sx={{
              width: "100%",
              borderRadius: "14px",
              bgcolor: "#000",
              display: "block",
              mx: "auto",
              objectFit: "contain",
              maxHeight: 400,
            }}
            src={`/api/downloaded/${video.id}/stream`}
          />
        ) : video.platform === "news" ? (
          <Paper variant="outlined" sx={{ p: 2, borderRadius: "14px", bgcolor: "action.hover" }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
              <IconNews size={20} stroke={1.8} color="#f59e0b" />
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>News Article</Typography>
              {video.source_url && (
                <Chip label={(() => { try { return new URL(video.source_url).hostname.replace("www.", "") } catch { return "source" } })()}
                  size="small" variant="outlined" sx={{ fontSize: "0.65rem", height: 20, borderRadius: "10px" }} />
              )}
            </Stack>
            {video.source_url && (
              <Button size="small" variant="outlined" href={video.source_url} target="_blank" rel="noopener"
                startIcon={<IconLink size={16} stroke={1.8} />} sx={{ textTransform: "none", fontSize: "0.78rem", mb: 1.5, borderRadius: "20px" }}>
                Read original article
              </Button>
            )}
            {/* Show AI analysis summary if available */}
            {video.insights && (
              <Stack spacing={1} sx={{ mb: 1.5 }}>
                {video.insights.why_trending && (
                  <Box sx={{ p: 1, borderRadius: 1, bgcolor: (t) => t.palette.mode === "dark" ? "rgba(255,152,0,0.08)" : "rgba(255,152,0,0.06)" }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: "warning.main" }}>Why Trending</Typography>
                    <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>{video.insights.why_trending}</Typography>
                  </Box>
                )}
                {video.insights.hook && (
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>Video Hook</Typography>
                    <Typography variant="body2" sx={{ fontSize: "0.85rem", fontWeight: 500 }}>&ldquo;{video.insights.hook}&rdquo;</Typography>
                  </Box>
                )}
                {video.insights.suggested_angle && (
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>Suggested Angle</Typography>
                    <Typography variant="body2" sx={{ fontSize: "0.82rem" }}>{video.insights.suggested_angle}</Typography>
                  </Box>
                )}
                {video.insights.talking_points?.length > 0 && (
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>Talking Points</Typography>
                    {video.insights.talking_points.map((pt, i) => (
                      <Typography key={i} variant="body2" sx={{ fontSize: "0.8rem", pl: 1 }}>• {pt}</Typography>
                    ))}
                  </Box>
                )}
              </Stack>
            )}
            {video.transcript && (
              <>
                <Divider sx={{ my: 1 }} />
                <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", display: "block", mb: 0.5 }}>Article Text</Typography>
                <Typography variant="body2" sx={{ fontSize: "0.82rem", color: "text.secondary", lineHeight: 1.6, maxHeight: 250, overflowY: "auto" }}>
                  {video.transcript.slice(0, 2000)}{video.transcript.length > 2000 ? "..." : ""}
                </Typography>
              </>
            )}
          </Paper>
        ) : (
          <Box sx={{ height: 180, borderRadius: 2, bgcolor: "action.hover", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Typography sx={{ color: "text.disabled" }}>No video file</Typography>
          </Box>
        )}
      </Box>

      {/* Action bar and metadata */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <Stack direction="row" spacing={1} alignItems="center">
          <Button
            variant="contained"
            size="small"
            startIcon={<IconMovie size={16} stroke={1.8} />}
            onClick={(e) => onUseAsInspiration(video.id, e)}
            sx={{ borderRadius: "20px", fontWeight: 600 }}
          >
            {video.platform === "news" ? "Create Video from Article" : "Use as Inspiration"}
          </Button>

          {video.platform !== "news" && (
            <>
              <Button
                variant="outlined"
                size="small"
                startIcon={reanalyzing ? <CircularProgress size={14} /> : <IconSparkles size={16} stroke={1.8} />}
                disabled={reanalyzing}
                onClick={(e) => setToolsAnchor(e.currentTarget)}
                sx={{ borderRadius: "20px", color: "text.secondary", borderColor: "divider" }}
              >
                {reanalyzing ? "Analyzing..." : "Actions ▾"}
              </Button>
              <Menu
                anchorEl={toolsAnchor}
                open={Boolean(toolsAnchor)}
                onClose={() => setToolsAnchor(null)}
                slotProps={{ paper: { sx: { borderRadius: "16px", minWidth: 200 } } }}
              >
                <MenuItem
                  onClick={(e) => {
                    setToolsAnchor(null)
                    setReanalyzeAnchor(e.currentTarget)
                  }}
                  sx={{ borderRadius: "10px", mx: 0.5 }}
                >
                  <ListItemText primary="Re-analyze Transcript" secondary="Choose Whisper quality" />
                </MenuItem>
                <MenuItem
                  onClick={async () => {
                    setToolsAnchor(null)
                    try {
                      await http.post(`/api/downloaded/${video.id}/generate`, {
                        aspect_ratio: "9:16", tts_provider: "edge_tts",
                        caption_enabled: true, caption_style: "viral", music_enabled: true, music_genre: "lofi",
                      })
                      showSnackbar("Quick video generation started!", "success")
                    } catch (e) { showSnackbar(e.response?.data?.detail || e.message, "error") }
                  }}
                  sx={{ borderRadius: "10px", mx: 0.5 }}
                >
                  <ListItemText primary="Quick Stock Video" secondary="Generate vertical 9:16 draft" />
                </MenuItem>
                <MenuItem
                  component={NavLink}
                  to="/clips"
                  onClick={() => setToolsAnchor(null)}
                  sx={{ borderRadius: "10px", mx: 0.5 }}
                >
                  <ListItemText primary="Open in Clip Studio" secondary="Extract highlight clips" />
                </MenuItem>
              </Menu>
              <Menu
                anchorEl={reanalyzeAnchor}
                open={Boolean(reanalyzeAnchor)}
                onClose={() => setReanalyzeAnchor(null)}
                slotProps={{ paper: { sx: { borderRadius: "16px" } } }}
              >
                {WHISPER_QUALITIES.map((q) => (
                  <MenuItem key={q.value} onClick={() => handleReanalyze(q.value)} sx={{ borderRadius: "10px", mx: 0.5 }}>
                    <ListItemText primary={q.label} secondary={q.desc} />
                  </MenuItem>
                ))}
              </Menu>
            </>
          )}
        </Stack>

        <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
          {video.platform !== "news" && video.duration_seconds && (
            <Chip icon={<IconClock size={13} stroke={1.8} />} label={`${Math.floor(video.duration_seconds / 60)}m${video.duration_seconds % 60}s`}
              size="small" variant="outlined" sx={{ borderRadius: "10px", fontSize: "0.72rem" }} />
          )}
          {video.platform !== "news" && video.file_size_mb && (
            <Chip icon={<IconDatabase size={13} stroke={1.8} />} label={`${video.file_size_mb} MB`} size="small" variant="outlined" sx={{ borderRadius: "10px", fontSize: "0.72rem" }} />
          )}
          <Chip
            label={video.platform === "news"
              ? (video.insights ? "Analyzed" : "Saved")
              : (video.insights ? "Analyzed" : video.transcript ? "Transcribed" : "Downloaded")}
            size="small"
            color={video.insights ? "success" : video.transcript ? "warning" : "default"}
            sx={{ borderRadius: "10px", fontSize: "0.72rem" }}
          />
          {onClose && (
            <IconButton size="small" onClick={onClose} sx={{ ml: 0.5, borderRadius: "10px" }} aria-label="Close">
              <IconX size={18} stroke={1.8} />
            </IconButton>
          )}
        </Stack>
      </Stack>

      <Divider sx={{ mb: 2 }} />

      {/* AI Insights & Transcript Section */}
      {video.insights ? (
        <Box sx={{ mb: 2 }}>
          <Typography variant="overline" sx={{ color: "text.secondary", mb: 1, display: "block" }}>AI Insights</Typography>
          <Stack spacing={1.5}>
            {video.insights.hook && <InsightRow label="Hook" color="secondary.main" value={video.insights.hook} />}
            {video.insights.structure && <InsightRow label="Structure" color="secondary.main" value={video.insights.structure} />}
            {video.insights.tone && <InsightRow label="Tone" color="secondary.main" value={video.insights.tone} />}
            {video.insights.why_viral && <InsightRow label="Why viral" color="warning.main" value={video.insights.why_viral} />}
            {video.insights.suggested_angle && <InsightRow label="Your angle" color="primary.main" value={video.insights.suggested_angle} />}
            {video.insights.suggested_title && <InsightRow label="Title idea" color="primary.main" value={video.insights.suggested_title} />}
          </Stack>

          {/* ── AI Action Buttons (Inline refinement) ────── */}
          <Divider sx={{ my: 2 }} />
          <Typography variant="overline" sx={{ color: "text.secondary", mb: 1, display: "block" }}>
            Refine with AI
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ gap: 0.75 }}>
            <AIActionButton
              label="Stronger Hook"
              icon={<IconFlame size={16} stroke={1.8} />}
              loading={aiActionLoading === "strengthen_hook"}
              onClick={() => handleAiAction("strengthen_hook")}
              tooltip="Rewrite the hook to be more attention-grabbing"
            />
            <AIActionButton
              label="Improve Angle"
              icon={<IconSparkles size={16} stroke={1.8} />}
              loading={aiActionLoading === "improve_angle"}
              onClick={() => handleAiAction("improve_angle")}
              tooltip="Elaborate and strengthen the suggested video angle"
            />
            <AIActionButton
              label="5 Title Ideas"
              icon={<IconEdit size={16} stroke={1.8} />}
              loading={aiActionLoading === "suggest_titles"}
              onClick={() => handleAiAction("suggest_titles")}
              tooltip="Generate 5 click-worthy title alternatives"
            />
            <AIActionButton
              label="Make Shorter"
              icon={<IconScissors size={16} stroke={1.8} />}
              loading={aiActionLoading === "rewrite_shorter"}
              onClick={() => handleAiAction("rewrite_shorter")}
              tooltip="Shorten the suggested angle to 1-2 punchy sentences"
            />
            <AIActionButton
              label="For TikTok"
              icon={<IconAspectRatio size={16} stroke={1.8} />}
              loading={aiActionLoading === "rewrite_for_platform"}
              onClick={() => handleAiAction("rewrite_for_platform", { platform: "TikTok" })}
              tooltip="Adapt concept specifically for TikTok's format"
            />
            <AIActionButton
              label="Translate"
              icon={<IconWorld size={16} stroke={1.8} />}
              loading={aiActionLoading === "translate"}
              onClick={() => handleAiAction("translate", { language: "Chinese" })}
              tooltip="Translate all insights into Chinese"
            />
          </Stack>

          {/* ── AI Action Result ──────────────────────────── */}
          {aiActionResult && (
            <Paper variant="outlined" sx={{
              mt: 2, p: 2, borderRadius: "14px",
              borderColor: "primary.main", borderWidth: 1,
              bgcolor: (t) => t.palette.mode === "dark" ? "rgba(139, 92, 246, 0.08)" : "rgba(139, 92, 246, 0.04)",
            }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "primary.main", textTransform: "uppercase", letterSpacing: 0.5 }}>
                  AI Result — {aiActionResult.action?.replace(/_/g, " ")}
                </Typography>
                <IconButton size="small" onClick={() => setAiActionResult(null)} sx={{ p: 0.25, borderRadius: "10px" }}>
                  <IconX size={14} stroke={1.8} />
                </IconButton>
              </Stack>
              {aiActionResult.action === "suggest_titles" && Array.isArray(aiActionResult.result) ? (
                <Stack spacing={0.75}>
                  {aiActionResult.result.map((title, i) => (
                    <Paper key={i} variant="outlined" sx={{ px: 1.5, py: 0.75, borderRadius: 1.5, cursor: "pointer", "&:hover": { bgcolor: "action.hover" } }}
                      onClick={() => { navigator.clipboard?.writeText(title); showSnackbar("Copied to clipboard", "success") }}>
                      <Typography variant="body2" sx={{ fontSize: "0.85rem" }}>
                        {i + 1}. {title}
                      </Typography>
                    </Paper>
                  ))}
                  <Typography variant="caption" sx={{ color: "text.disabled" }}>Click a title to copy</Typography>
                </Stack>
              ) : aiActionResult.action === "rewrite_for_platform" && typeof aiActionResult.result === "object" ? (
                <Stack spacing={1}>
                  {aiActionResult.result.hook && <InsightRow label="Hook" color="secondary.main" value={aiActionResult.result.hook} />}
                  {aiActionResult.result.suggested_angle && <InsightRow label="Angle" color="primary.main" value={aiActionResult.result.suggested_angle} />}
                  {aiActionResult.result.suggested_title && <InsightRow label="Title" color="primary.main" value={aiActionResult.result.suggested_title} />}
                  {aiActionResult.result.format_tips && <InsightRow label="Format Tips" color="warning.main" value={aiActionResult.result.format_tips} />}
                </Stack>
              ) : aiActionResult.action === "translate" && typeof aiActionResult.result === "object" ? (
                <Stack spacing={1}>
                  {Object.entries(aiActionResult.result).map(([key, val]) => (
                    <InsightRow key={key} label={key.replace(/_/g, " ")} color="text.secondary" value={typeof val === "string" ? val : JSON.stringify(val)} />
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" sx={{ fontSize: "0.85rem", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                  {typeof aiActionResult.result === "string" ? aiActionResult.result : JSON.stringify(aiActionResult.result, null, 2)}
                </Typography>
              )}
            </Paper>
          )}
        </Box>
      ) : !video.transcript ? (
        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", py: 4, color: "text.disabled" }}>
          <Typography variant="body2" sx={{ mb: 0.5 }}>No analysis yet</Typography>
          <Typography variant="caption">Use Actions ▾ to transcribe and extract insights</Typography>
        </Box>
      ) : null}

      {video.transcript && (
        <Box sx={{ mt: video.insights ? 2 : 0 }}>
          <Typography variant="overline" sx={{ color: "text.secondary" }}>
            Transcript {video.transcript_language && `(${video.transcript_language})`}
          </Typography>
          <Paper variant="outlined" sx={{ p: 1.5, maxHeight: 320, overflowY: "auto", fontSize: "0.82rem", color: "text.secondary", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
            {video.transcript}
          </Paper>
        </Box>
      )}
    </Box>
  )
}
