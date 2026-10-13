import { useState } from "react"
import { Box, Typography, Button } from "@mui/material"
import { IconCheck, IconX, IconChevronDown, IconChevronUp } from "@tabler/icons-react"
import { motion, AnimatePresence } from "framer-motion"
import ToolInvocation, { TriangularLoader } from "./ToolInvocation"

function formatDuration(ms) {
  if (ms === null || ms === undefined) return null
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

export default function ThoughtChain({ steps = [], isStreaming = false }) {
  // Default state is strictly collapsed/minimized as mandated by product owner
  const [expanded, setExpanded] = useState(false)

  if (!steps || steps.length === 0) return null

  // Calculate status summary across all steps
  const hasError = steps.some(
    (s) =>
      s.status === "failed" ||
      s.status === "error" ||
      s.tool_calls?.some((tc) => tc.state === "output-error" || tc.status === "failed" || tc.error)
  )

  const isRunning =
    isStreaming ||
    steps.some(
      (s) =>
        s.status === "executing" ||
        s.status === "running" ||
        s.tool_calls?.some((tc) => tc.state === "executing" || tc.state === "running" || tc.state === "input-available")
    )

  // Find currently running tool name if running
  const activeTool = steps
    .flatMap((s) => s.tool_calls || [])
    .find((tc) => tc.state === "executing" || tc.state === "running" || tc.state === "input-available")

  // Total elapsed duration
  const totalDurationMs = steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
  const durationText = formatDuration(totalDurationMs)

  // Status label
  let summaryLabel = ""
  if (isRunning) {
    if (activeTool?.name) {
      summaryLabel = `Executing ${activeTool.name}...`
    } else {
      summaryLabel = "Executing Main Agent tools..."
    }
  } else if (hasError) {
    summaryLabel = "Tool execution failed"
  } else {
    const count = steps.length
    summaryLabel = `${count} ${count === 1 ? "step" : "steps"} completed`
  }

  return (
    <Box
      sx={{
        my: 1,
        borderRadius: 2,
        border: 1,
        borderColor: hasError
          ? "error.light"
          : isRunning
            ? "primary.light"
            : "divider",
        bgcolor: (t) =>
          t.palette.mode === "dark"
            ? "rgba(255, 255, 255, 0.02)"
            : "rgba(0, 0, 0, 0.015)",
        overflow: "hidden",
        fontSize: "0.825rem",
      }}
      role="region"
      aria-label="Execution timeline"
    >
      {/* Collapsed / Toggle summary header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1.5,
          py: 0.85,
          bgcolor: (t) =>
            t.palette.mode === "dark"
              ? isRunning
                ? "rgba(99, 102, 241, 0.08)"
                : "rgba(255, 255, 255, 0.025)"
              : isRunning
                ? "rgba(99, 102, 241, 0.04)"
                : "rgba(0, 0, 0, 0.02)",
        }}
      >
        {/* Left: status indicator + truthful summary label */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
          {isRunning ? (
            <TriangularLoader size={16} color="#6366f1" />
          ) : hasError ? (
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
            sx={{
              fontSize: "0.78rem",
              fontWeight: 600,
              color: isRunning
                ? "primary.main"
                : hasError
                  ? "error.main"
                  : "text.secondary",
            }}
          >
            {summaryLabel}
          </Typography>

          {durationText && (
            <Typography
              component="span"
              sx={{
                fontSize: "0.68rem",
                color: "text.disabled",
                fontFamily: "monospace",
                ml: 0.5,
              }}
            >
              ({durationText})
            </Typography>
          )}
        </Box>

        {/* Right: Toggle button */}
        <Button
          size="small"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          endIcon={expanded ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          sx={{
            textTransform: "none",
            fontSize: "0.72rem",
            fontWeight: 600,
            py: 0.25,
            px: 1,
            minWidth: 0,
            borderRadius: 1.5,
            color: "text.secondary",
            "&:hover": {
              bgcolor: "action.hover",
              color: "text.primary",
            },
          }}
        >
          {expanded ? "Hide details" : "Show details"}
        </Button>
      </Box>

      {/* Expanded view: Vertical timeline with nested ToolInvocations */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="thought-chain-content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            style={{ overflow: "hidden" }}
          >
            <Box sx={{ p: 1.5, pt: 1, borderTop: 1, borderColor: "divider" }}>
              <Box sx={{ position: "relative", pl: 3 }}>
                {/* Vertical connector line */}
                <Box
                  sx={{
                    position: "absolute",
                    left: "11px",
                    top: "10px",
                    bottom: "10px",
                    width: "2px",
                    bgcolor: "divider",
                    zIndex: 0,
                  }}
                />

                {/* Steps */}
                {steps.map((step, idx) => {
                  const isStepRunning =
                    step.status === "executing" ||
                    step.status === "running" ||
                    step.tool_calls?.some(
                      (tc) => tc.state === "executing" || tc.state === "running" || tc.state === "input-available"
                    )
                  const isStepError =
                    step.status === "failed" ||
                    step.status === "error" ||
                    step.tool_calls?.some((tc) => tc.state === "output-error" || tc.status === "failed" || tc.error)
                  const isStepDone = !isStepRunning && !isStepError

                  return (
                    <Box key={step.id || idx} sx={{ mb: idx === steps.length - 1 ? 0 : 2, position: "relative" }}>
                      {/* Step Indicator on the line */}
                      <Box
                        sx={{
                          position: "absolute",
                          left: "-24px",
                          top: "2px",
                          width: "20px",
                          height: "20px",
                          borderRadius: "50%",
                          bgcolor: "background.paper",
                          border: 2,
                          borderColor: isStepRunning
                            ? "primary.main"
                            : isStepError
                              ? "error.main"
                              : "success.main",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          zIndex: 1,
                        }}
                      >
                        {isStepRunning ? (
                          <TriangularLoader size={12} color="#6366f1" />
                        ) : isStepError ? (
                          <IconX size={10} color="#ef4444" stroke={3} />
                        ) : (
                          <IconCheck size={10} color="#10b981" stroke={3} />
                        )}
                      </Box>

                      {/* Step Header */}
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.75 }}>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 600,
                            fontSize: "0.75rem",
                            color: "text.primary",
                          }}
                        >
                          {step.title || `Step ${idx + 1}`}
                        </Typography>

                        {step.duration_ms && (
                          <Typography
                            variant="caption"
                            sx={{
                              fontSize: "0.68rem",
                              color: "text.disabled",
                              fontFamily: "monospace",
                            }}
                          >
                            {formatDuration(step.duration_ms)}
                          </Typography>
                        )}
                      </Box>

                      {/* Tool Calls inside this step */}
                      {step.tool_calls && step.tool_calls.length > 0 && (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                          {step.tool_calls.map((tc, tcIdx) => (
                            <ToolInvocation
                              key={tc.id || tcIdx}
                              tool={tc}
                              defaultExpanded={isStepError}
                            />
                          ))}
                        </Box>
                      )}
                    </Box>
                  )
                })}
              </Box>
            </Box>
          </motion.div>
        )}
      </AnimatePresence>
    </Box>
  )
}
