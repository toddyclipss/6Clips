import { useEffect, useRef, useState, useCallback } from "react"
import {
  Box, Typography, Button, Stack, CircularProgress,
  List, ListItemButton, ListItemText, IconButton,
  Tooltip, Dialog, DialogTitle, DialogContent, DialogActions,
} from "@mui/material"
import {
  IconPlus,
  IconArrowLeft,
  IconTrash,
  IconHistory,
} from "@tabler/icons-react"
import { ws } from "../../api/websocket"
import http from "../../api/http"
import useAppStore from "../../store/appStore"
import ChatMessage from "./ChatMessage"
import LiquidMultimodalInput from "./LiquidMultimodalInput"
import TrendsResultsCard from "./TrendsResultsCard"
import JobProgressCard from "./JobProgressCard"
import VideoPreviewCard from "./VideoPreviewCard"
import InsightsCard from "./InsightsCard"
import ChannelSummaryCard from "./ChannelSummaryCard"
import DownloadedListCard from "./DownloadedListCard"
import ContentCalendarCard from "./ContentCalendarCard"
import NewsResultsCard from "./NewsResultsCard"

function timeAgo(dateString) {
  if (!dateString) return ""
  const diff = Date.now() - new Date(dateString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days === 1) return "Yesterday"
  if (days < 7) return `${days}d ago`
  return new Date(dateString).toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

function RichMessage({ msg }) {
  const wrapper = { width: "100%", px: 0.5, py: 0.5 }
  switch (msg.type) {
    case "trend_results":
    case "trends_results":
      return <Box sx={wrapper}><TrendsResultsCard results={msg.data.results} platform={msg.data.platform} jobId={msg.data.jobId} /></Box>
    case "job_progress":
      return <Box sx={wrapper}><JobProgressCard jobId={msg.data.jobId} jobType={msg.data.jobType} message={msg.data.message} /></Box>
    case "video_preview":
      return <Box sx={wrapper}><VideoPreviewCard video={msg.data.video} /></Box>
    case "insights":
      return <Box sx={wrapper}><InsightsCard videos={msg.data.videos} /></Box>
    case "channel_summary":
      return <Box sx={wrapper}><ChannelSummaryCard summary={msg.data.summary} /></Box>
    case "downloaded_list":
      return <Box sx={wrapper}><DownloadedListCard videos={msg.data.videos} /></Box>
    case "content_calendar":
      return <Box sx={wrapper}><ContentCalendarCard calendar={msg.data.calendar} /></Box>
    case "news_results":
      return <Box sx={wrapper}><NewsResultsCard results={msg.data.results} query={msg.data.query} /></Box>
    default:
      return <ChatMessage role="system" content={JSON.stringify(msg.data)} />
  }
}

export default function ChatPanel() {
  const sessions = useAppStore((s) => s.sessions)
  const activeSessionId = useAppStore((s) => s.activeSessionId)
  const messages = useAppStore((s) => s.messages)
  const isStreaming = useAppStore((s) => s.isStreaming)
  const streamingText = useAppStore((s) => s.streamingText)
  const addMessage = useAppStore((s) => s.addMessage)
  const setStreaming = useAppStore((s) => s.setStreaming)
  const clearStreamingText = useAppStore((s) => s.clearStreamingText)
  const setMessages = useAppStore((s) => s.setMessages)
  const setActiveSessionId = useAppStore((s) => s.setActiveSessionId)
  const setSessions = useAppStore((s) => s.setSessions)
  const removeSession = useAppStore((s) => s.removeSession)
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const bottomRef = useRef(null)

  // View state: "chat" or "history" (rendered strictly inside ChatPanel)
  const [view, setView] = useState("chat")
  const [confirmDialog, setConfirmDialog] = useState({ open: false, title: "", message: "", onConfirm: null })

  const openConfirm = (title, message, onConfirm) => setConfirmDialog({ open: true, title, message, onConfirm })
  const closeConfirm = () => setConfirmDialog((prev) => ({ ...prev, open: false }))

  // Load chat sessions on mount
  useEffect(() => {
    http.get("/api/chat/sessions").then((res) => {
      setSessions(res.data)
    }).catch((err) => {
      console.error("Failed to load chat sessions:", err)
    })

    const savedSessionId = sessionStorage.getItem("vm_active_session")
    if (savedSessionId && !activeSessionId && messages.length === 0) {
      setActiveSessionId(savedSessionId)
      ws.send({ type: "set_session", session_id: savedSessionId })
      http.get(`/api/chat/sessions/${savedSessionId}/messages`).then((res) => {
        const loaded = res.data.map((m) => {
          if (m.role === "rich" || m.msg_type) {
            return { role: "rich", type: m.msg_type, data: m.data_json ? JSON.parse(m.data_json) : {} }
          }
          return { role: m.role, content: m.content }
        })
        setMessages(loaded)
      }).catch((err) => {
        console.error("Failed to restore session messages:", err)
        sessionStorage.removeItem("vm_active_session")
        setActiveSessionId(null)
      })
    }
  }, [])

  useEffect(() => {
    if (view === "chat") {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages, streamingText, view])

  const switchSession = useCallback(async (sessionId) => {
    if (sessionId === activeSessionId) {
      setView("chat")
      return
    }
    setActiveSessionId(sessionId)
    setMessages([])
    ws.send({ type: "set_session", session_id: sessionId })
    setView("chat")

    try {
      const res = await http.get(`/api/chat/sessions/${sessionId}/messages`)
      const loaded = res.data.map((m) => {
        if (m.role === "rich" || m.msg_type) {
          return { role: "rich", type: m.msg_type, data: m.data_json ? JSON.parse(m.data_json) : {} }
        }
        return { role: m.role, content: m.content }
      })
      setMessages(loaded)
    } catch (err) {
      console.warn("[Chat] Failed to restore session messages:", err)
    }
  }, [activeSessionId])

  const handleNewChat = () => {
    setActiveSessionId(null)
    setMessages([])
    ws.send({ type: "set_session", session_id: null })
    setView("chat")
  }

  const handleDeleteSession = (sessionId) => {
    openConfirm("Delete chat?", "This conversation will be permanently removed.", async () => {
      try {
        await http.delete(`/api/chat/sessions/${sessionId}`)
        removeSession(sessionId)
        if (activeSessionId === sessionId) {
          setActiveSessionId(null)
          setMessages([])
        }
        showSnackbar("Chat deleted", "info")
      } catch {
        showSnackbar("Failed to delete chat", "error")
      }
    })
  }

  const handleSend = (text, files = [], think = undefined) => {
    const trimmed = text.trim()
    if (!trimmed && files.length === 0) return

    addMessage({ role: "user", content: trimmed })
    setStreaming(true)
    clearStreamingText()
    if (activeSessionId) {
      ws.send({ type: "set_session", session_id: activeSessionId })
    }
    const payload = { type: "chat_message", content: trimmed }
    if (think !== undefined) {
      payload.think = think
    }
    ws.send(payload)
  }

  return (
    <Box
      sx={{
        width: { xs: "100%", md: "30%" },
        minWidth: { md: 320, lg: 350 },
        maxWidth: { md: 460 },
        height: "100%",
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        borderRight: 1,
        borderColor: "divider",
        bgcolor: "background.paper",
        position: "relative",
        zIndex: 10,
        boxShadow: (theme) => theme.customShadows?.sm,
      }}
    >
      {view === "history" ? (
        /* ── INLINE HISTORY VIEW (INSIDE CHAT COMPONENT) ── */
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Header */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              px: 1.5,
              py: 1,
              minHeight: 46,
              flexShrink: 0,
              borderBottom: 1,
              borderColor: "divider",
              bgcolor: (t) => t.palette.mode === "dark" ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.01)",
            }}
          >
            <Button
              size="small"
              startIcon={<IconArrowLeft size={16} stroke={1.8} />}
              onClick={() => setView("chat")}
              sx={{
                fontSize: "0.8rem",
                fontWeight: 600,
                borderRadius: "16px",
                textTransform: "none",
                color: "text.primary",
              }}
            >
              Back
            </Button>

            <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: "0.875rem", ml: 0.5 }}>
              Chat History
            </Typography>
          </Box>

          {/* Sessions List */}
          <Box sx={{ flex: 1, overflowY: "auto", p: 1.25 }}>
            <List disablePadding>
              {sessions.map((sess) => (
                <ListItemButton
                  key={sess.id}
                  selected={sess.id === activeSessionId}
                  onClick={() => switchSession(sess.id)}
                  sx={{
                    borderRadius: "14px",
                    mb: 0.5,
                    py: 0.75,
                    px: 1.25,
                    pr: 4.5,
                    position: "relative",
                    "&.Mui-selected": {
                      bgcolor: "rgba(139, 92, 246, 0.12)",
                      boxShadow: "inset 0 0 0 1px rgba(139, 92, 246, 0.25)",
                    },
                    "&:hover .del-btn": { opacity: 1 },
                  }}
                >
                  <ListItemText
                    primary={sess.title}
                    secondary={timeAgo(sess.updated_at || sess.created_at)}
                    slotProps={{
                      primary: {
                        noWrap: true,
                        fontSize: "0.825rem",
                        fontWeight: sess.id === activeSessionId ? 700 : 500,
                      },
                      secondary: {
                        noWrap: true,
                        fontSize: "0.7rem",
                      },
                    }}
                  />
                  <IconButton
                    className="del-btn"
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteSession(sess.id)
                    }}
                    sx={{
                      position: "absolute",
                      right: 6,
                      opacity: 0,
                      borderRadius: "8px",
                      transition: "opacity 0.15s",
                      color: "text.secondary",
                      "&:hover": { color: "error.main" },
                    }}
                  >
                    <IconTrash size={15} stroke={1.8} />
                  </IconButton>
                </ListItemButton>
              ))}

              {sessions.length === 0 && (
                <Typography variant="caption" sx={{ color: "text.secondary", display: "block", textAlign: "center", mt: 4 }}>
                  No previous conversations
                </Typography>
              )}
            </List>
          </Box>
        </Box>
      ) : (
        /* ── CHAT VIEW ── */
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Top Header */}
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              px: 1.5,
              py: 0.75,
              minHeight: 46,
              flexShrink: 0,
              borderBottom: 1,
              borderColor: "divider",
              bgcolor: (t) => t.palette.mode === "dark" ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.01)",
            }}
          >
            <Button
              size="small"
              variant="text"
              startIcon={<IconPlus size={16} stroke={2} />}
              onClick={handleNewChat}
              sx={{
                fontSize: "0.8rem",
                fontWeight: 600,
                py: 0.4,
                px: 1.4,
                borderRadius: "20px",
                color: "text.primary",
                bgcolor: "action.hover",
                textTransform: "none",
                "&:hover": { bgcolor: "action.selected" },
              }}
            >
              New chat
            </Button>

            <Tooltip title="History">
              <IconButton
                size="small"
                onClick={() => setView("history")}
                sx={{ color: "text.secondary", borderRadius: "10px" }}
              >
                <IconHistory size={18} stroke={1.8} />
              </IconButton>
            </Tooltip>
          </Box>

          {/* Messages Scroll Area */}
          <Box
            sx={{
              flex: 1,
              overflowY: "auto",
              overflowX: "hidden",
              p: 1.5,
              display: "flex",
              flexDirection: "column",
              gap: 1,
            }}
          >
            {messages.map((msg, i) => {
              if (msg.role === "rich") return <RichMessage key={i} msg={msg} />
              return <ChatMessage key={i} role={msg.role} content={msg.content} />
            })}

            {isStreaming && streamingText && (
              <ChatMessage role="assistant" content={streamingText} />
            )}

            {isStreaming && !streamingText && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 1.5, px: 1 }}>
                <CircularProgress size={14} sx={{ color: "primary.main" }} />
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.78rem" }}>
                  Thinking...
                </Typography>
              </Box>
            )}

            <div ref={bottomRef} />
          </Box>

          {/* Bottom Input Area ("embaixo") with LiquidMultimodalInput */}
          <Box
            sx={{
              p: 1.5,
              pb: 2,
              borderTop: 1,
              borderColor: "divider",
              bgcolor: "background.paper",
              flexShrink: 0,
            }}
          >
            <LiquidMultimodalInput
              placeholder="Message 6Clips or describe a video..."
              disabled={isStreaming}
              onSubmit={handleSend}
            />
          </Box>
        </Box>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={confirmDialog.open} onClose={closeConfirm} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: "1rem" }}>{confirmDialog.title}</DialogTitle>
        <DialogContent><Typography variant="body2">{confirmDialog.message}</Typography></DialogContent>
        <DialogActions>
          <Button onClick={closeConfirm} size="small">Cancel</Button>
          <Button color="error" variant="contained" size="small" onClick={() => { confirmDialog.onConfirm?.(); closeConfirm() }}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
