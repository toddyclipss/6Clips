// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import {
  Box,
  Typography,
  Stack,
  Chip,
  IconButton,
  Button,
  Tooltip,
} from "@mui/material"
import {
  IconCheck,
  IconClock,
  IconAlertTriangle,
  IconBan,
  IconExternalLink,
  IconRotate2,
  IconX,
} from "@tabler/icons-react"

export default function JobStatusList({ jobs, onCancelJob, onRetryJob, onViewReceipt }) {
  const getStatusChip = (status) => {
    switch (status) {
      case "PUBLISHED_VERIFIED":
        return <Chip size="small" color="success" icon={<IconCheck size={14} />} label="Published (Verified)" />
      case "SCHEDULED":
        return <Chip size="small" color="info" icon={<IconClock size={14} />} label="Scheduled" />
      case "DISPATCHING":
        return <Chip size="small" color="secondary" icon={<IconRotate2 size={14} />} label="Dispatching..." />
      case "UNCERTAIN":
        return <Chip size="small" color="warning" icon={<IconAlertTriangle size={14} />} label="Uncertain (Awaiting Receipt)" />
      case "FAILED_RETRYABLE":
        return <Chip size="small" color="warning" icon={<IconAlertTriangle size={14} />} label="Retryable Error" />
      case "BLOCKED":
        return <Chip size="small" color="error" icon={<IconBan size={14} />} label="Blocked" />
      case "CANCELLED":
        return <Chip size="small" color="default" label="Cancelled" />
      default:
        return <Chip size="small" label={status} />
    }
  }

  if (!jobs || jobs.length === 0) {
    return (
      <Box sx={{ p: 4, textAlign: "center", border: 1, borderStyle: "dashed", borderColor: "divider", borderRadius: "16px" }}>
        <Typography variant="body2" color="text.secondary">
          No distribution jobs scheduled yet.
        </Typography>
      </Box>
    )
  }

  return (
    <Stack spacing={1.5}>
      {jobs.map((job) => (
        <Box
          key={job.job_id}
          sx={{
            p: 2,
            borderRadius: "14px",
            border: 1,
            borderColor: "divider",
            bgcolor: "background.paper",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 1.5,
          }}
        >
          <Box sx={{ minWidth: 200, flex: 1 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Chip
                size="small"
                label={job.platform?.toUpperCase()}
                variant="outlined"
                sx={{ fontWeight: 700, fontSize: "0.7rem", height: 22 }}
              />
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }} noWrap>
                {job.seo_metadata?.title || job.output_id}
              </Typography>
            </Stack>

            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              Scheduled: {new Date(job.scheduled_time_utc).toLocaleString()} ({job.timezone || "UTC"})
            </Typography>

            {job.error_message && (
              <Typography variant="caption" color="error.main" sx={{ display: "block", mt: 0.3 }}>
                {job.error_message}
              </Typography>
            )}
          </Box>

          <Stack direction="row" spacing={1} alignItems="center">
            {getStatusChip(job.status)}

            {job.status === "PUBLISHED_VERIFIED" && job.remote_post_url && (
              <Tooltip title="View Remote Post">
                <IconButton
                  size="small"
                  component="a"
                  href={job.remote_post_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <IconExternalLink size={16} />
                </IconButton>
              </Tooltip>
            )}

            {job.status === "PUBLISHED_VERIFIED" && onViewReceipt && (
              <Button size="small" variant="text" onClick={() => onViewReceipt(job)}>
                Receipt
              </Button>
            )}

            {(job.status === "SCHEDULED" || job.status === "READY_TO_SCHEDULE") && (
              <Button
                size="small"
                color="error"
                variant="outlined"
                onClick={() => onCancelJob(job.job_id)}
                startIcon={<IconX size={14} />}
                sx={{ borderRadius: "14px" }}
              >
                Cancel
              </Button>
            )}

            {(job.status === "FAILED_RETRYABLE" || job.status === "BLOCKED" || job.status === "UNCERTAIN") && (
              <Button
                size="small"
                variant="outlined"
                onClick={() => onRetryJob(job.job_id)}
                startIcon={<IconRotate2 size={14} />}
                sx={{ borderRadius: "14px" }}
              >
                Retry
              </Button>
            )}
          </Stack>
        </Box>
      ))}
    </Stack>
  )
}
