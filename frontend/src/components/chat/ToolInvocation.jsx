import { useState } from "react"
import { Box, Typography, IconButton, Tooltip } from "@mui/material"
import { IconCheck, IconX, IconChevronDown, IconChevronRight, IconCopy } from "@tabler/icons-react"
import { motion, AnimatePresence } from "framer-motion"

export function TriangularLoader({ size = 18, color = "currentColor" }) {
  const [reducedMotion, setReducedMotion] = useState(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches
    }
    return false
  })

  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        flexShrink: 0,
      }}
      aria-label="Executing tool"
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ overflow: "visible" }}
      >
        {/* Triangular guide path */}
        <path
          d="M 12 4.5 L 19.5 17.5 L 4.5 17.5 Z"
          fill="none"
          stroke={color}
          strokeWidth="1.2"
          strokeOpacity="0.18"
          strokeLinejoin="round"
        />

        {reducedMotion ? (
          // Static vertices when user prefers reduced motion
          <>
            <circle cx="12" cy="4.5" r="2.2" fill={color} />
            <circle cx="19.5" cy="17.5" r="2.2" fill={color} />
            <circle cx="4.5" cy="17.5" r="2.2" fill={color} />
          </>
        ) : (
          // Three circles traveling along equilateral triangle edges, staggered by 1/3 (0.6s)
          <>
            <circle cx="0" cy="0" r="2.2" fill={color}>
              <animateMotion
                path="M 12 4.5 L 19.5 17.5 L 4.5 17.5 Z"
                dur="1.8s"
                begin="0s"
                repeatCount="indefinite"
              />
            </circle>
            <circle cx="0" cy="0" r="2.2" fill={color}>
              <animateMotion
                path="M 12 4.5 L 19.5 17.5 L 4.5 17.5 Z"
                dur="1.8s"
                begin="-0.6s"
                repeatCount="indefinite"
              />
            </circle>
            <circle cx="0" cy="0" r="2.2" fill={color}>
              <animateMotion
                path="M 12 4.5 L 19.5 17.5 L 4.5 17.5 Z"
                dur="1.8s"
                begin="-1.2s"
                repeatCount="indefinite"
              />
            </circle>
          </>
        )}
      </svg>
    </Box>
  )
}

export const ToolInvocationLoadingIcon = TriangularLoader

function formatDuration(ms) {
  if (ms === null || ms === undefined) return null
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function DiffBlock({ diffText }) {
  if (!diffText) return null
  const lines = typeof diffText === "string" ? diffText.split("\n") : []
  return (
    <Box sx={{ mt: 1 }}>
      <Typography
        variant="caption"
        sx={{
          fontWeight: 600,
          fontSize: "0.7rem",
          color: "text.secondary",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          display: "block",
          mb: 0.5,
        }}
      >
        State / Code Diff
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.25,
          borderRadius: 1,
          bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(0,0,0,0.4)" : "rgba(0,0,0,0.05)"),
          border: 1,
          borderColor: "divider",
          fontSize: "0.74rem",
          fontFamily: "'SF Mono', 'Fira Code', 'Roboto Mono', monospace",
          maxHeight: 240,
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {lines.map((line, idx) => {
          let lineBg = "transparent"
          let lineFg = "text.primary"
          if (line.startsWith("+")) {
            lineBg = "rgba(16, 185, 129, 0.12)"
            lineFg = "#10b981"
          } else if (line.startsWith("-")) {
            lineBg = "rgba(239, 68, 68, 0.12)"
            lineFg = "#ef4444"
          } else if (line.startsWith("@@")) {
            lineFg = "#06b6d4"
          }
          return (
            <Box
              key={idx}
              component="span"
              sx={{
                display: "block",
                bgcolor: lineBg,
                color: lineFg,
                px: 0.5,
                borderRadius: 0.5,
              }}
            >
              {line}
            </Box>
          )
        })}
      </Box>
    </Box>
  )
}

function CodeBlock({ label, data }) {
  const [copied, setCopied] = useState(false)
  const text = typeof data === "string" ? data : JSON.stringify(data, null, 2)

  const handleCopy = (e) => {
    e.stopPropagation()
    navigator.clipboard?.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Box sx={{ mt: 1 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0.5 }}>
        <Typography
          variant="caption"
          sx={{
            fontWeight: 600,
            fontSize: "0.7rem",
            color: "text.secondary",
            textTransform: "uppercase",
            letterSpacing: "0.04em",
          }}
        >
          {label}
        </Typography>
        <Tooltip title={copied ? "Copied" : "Copy"}>
          <IconButton size="small" onClick={handleCopy} sx={{ p: 0.25, color: "text.secondary" }}>
            {copied ? <IconCheck size={14} color="#10b981" /> : <IconCopy size={14} />}
          </IconButton>
        </Tooltip>
      </Box>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.25,
          borderRadius: 1,
          bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(0,0,0,0.35)" : "rgba(0,0,0,0.04)"),
          border: 1,
          borderColor: "divider",
          fontSize: "0.75rem",
          fontFamily: "'SF Mono', 'Fira Code', 'Roboto Mono', monospace",
          color: "text.primary",
          overflowX: "auto",
          maxHeight: 220,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {text}
      </Box>
    </Box>
  )
}

export default function ToolInvocation({ tool, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (!tool) return null

  const name = tool.name || tool.tool_name || "tool"
  const rawState = (tool.state || tool.status || "").toLowerCase()
  const isExecuting = rawState === "executing" || rawState === "running" || rawState === "input-available" || rawState === "input-streaming"
  const isError = rawState === "output-error" || rawState === "failed" || rawState === "error" || Boolean(tool.error) || (tool.result && tool.result.status === "error")
  const isCompleted = !isExecuting && !isError

  const durationText = formatDuration(tool.duration_ms ?? tool.durationMs)
  const jobId = tool.job_id || tool.jobId || tool.result?.job_id || tool.result?.jobId
  const diffData = tool.diff || tool.result?.diff || tool.code_diff || tool.result?.code_diff

  return (
    <Box
      sx={{
        borderRadius: 1.5,
        border: 1,
        borderColor: isError ? "error.light" : "divider",
        bgcolor: (t) =>
          t.palette.mode === "dark"
            ? isError
              ? "rgba(239,68,68,0.06)"
              : "rgba(255,255,255,0.02)"
            : isError
              ? "rgba(239,68,68,0.04)"
              : "rgba(0,0,0,0.015)",
        overflow: "hidden",
        transition: "border-color 0.15s ease",
      }}
    >
      {/* Header */}
      <Box
        component="button"
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        sx={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1.25,
          py: 0.85,
          background: "none",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          gap: 1,
          color: "inherit",
          "&:hover": {
            bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)"),
          },
        }}
      >
        {/* Left side: status icon + tool name + duration */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0, flex: 1 }}>
          {isExecuting ? (
            <TriangularLoader size={16} color="#6366f1" />
          ) : isError ? (
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                bgcolor: "error.main",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <IconX size={11} stroke={2.5} />
            </Box>
          ) : (
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                bgcolor: "success.main",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <IconCheck size={11} stroke={2.5} />
            </Box>
          )}

          <Typography
            component="span"
            sx={{
              fontFamily: "'SF Mono', 'Fira Code', monospace",
              fontSize: "0.78rem",
              fontWeight: 600,
              color: "text.primary",
              letterSpacing: "0.01em",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {name}
          </Typography>

          {durationText && (
            <Typography
              component="span"
              sx={{
                fontSize: "0.68rem",
                color: "text.disabled",
                fontFamily: "monospace",
                px: 0.6,
                py: 0.1,
                borderRadius: 0.75,
                bgcolor: "action.hover",
              }}
            >
              {durationText}
            </Typography>
          )}

          {jobId && (
            <Typography
              component="span"
              sx={{
                fontSize: "0.68rem",
                color: "primary.main",
                fontFamily: "monospace",
                px: 0.6,
                py: 0.1,
                borderRadius: 0.75,
                bgcolor: "action.hover",
                border: 1,
                borderColor: "divider",
              }}
            >
              Job #{jobId}
            </Typography>
          )}
        </Box>

        {/* Right side: status label + expand chevron */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexShrink: 0 }}>
          <Typography
            variant="caption"
            sx={{
              fontSize: "0.68rem",
              fontWeight: 500,
              color: isExecuting
                ? "primary.main"
                : isError
                  ? "error.main"
                  : "text.secondary",
            }}
          >
            {isExecuting ? "running" : isError ? "failed" : "completed"}
          </Typography>

          <Box sx={{ color: "text.secondary", display: "flex", alignItems: "center" }}>
            {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
          </Box>
        </Box>
      </Box>

      {/* Expandable detail content */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="tool-detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeInOut" }}
            style={{ overflow: "hidden" }}
          >
            <Box
              sx={{
                p: 1.25,
                pt: 0.5,
                borderTop: 1,
                borderColor: "divider",
                bgcolor: (t) =>
                  t.palette.mode === "dark" ? "rgba(0,0,0,0.15)" : "rgba(0,0,0,0.01)",
              }}
            >
              {isError && (
                <Box
                  sx={{
                    mb: 1,
                    p: 1,
                    borderRadius: 1,
                    bgcolor: "error.light",
                    color: "error.contrastText",
                    fontSize: "0.75rem",
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 600, display: "block" }}>
                    Execution Error:
                  </Typography>
                  <Typography variant="caption" sx={{ fontFamily: "monospace" }}>
                    {tool.error || (tool.result && tool.result.error) || "Tool returned an error."}
                  </Typography>
                </Box>
              )}

              {diffData && <DiffBlock diffText={diffData} />}

              {tool.arguments && Object.keys(tool.arguments).length > 0 && (
                <CodeBlock label="Arguments" data={tool.arguments} />
              )}

              {tool.result !== undefined && tool.result !== null && (
                <CodeBlock label="Result" data={tool.result} />
              )}
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </Box>
  )
}
