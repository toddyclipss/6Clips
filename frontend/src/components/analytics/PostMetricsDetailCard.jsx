// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 ViralMint Contributors
import React from "react"
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Grid,
  Box,
  Stack,
  Divider,
} from "@mui/material"
import {
  IconEye,
  IconThumbUp,
  IconMessageCircle,
  IconShare,
  IconChartBar,
} from "@tabler/icons-react"

function StatTile({ label, value, sublabel, icon: Icon, isMissing }) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1.5,
        bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)"),
        border: "1px solid",
        borderColor: "divider",
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={1}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: "uppercase" }}>
          {label}
        </Typography>
        {Icon && <Icon size={18} color="#94A3B8" />}
      </Stack>
      {isMissing ? (
        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: "italic" }}>
          Not reported by provider
        </Typography>
      ) : (
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          {value !== null && value !== undefined ? (typeof value === "number" ? value.toLocaleString() : value) : "—"}
        </Typography>
      )}
      {sublabel && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
          {sublabel}
        </Typography>
      )}
    </Box>
  )
}

export function PostMetricsDetailCard({ receipt, aggregate }) {
  if (!aggregate) {
    return (
      <Card sx={{ border: "1px solid", borderColor: "divider" }}>
        <CardContent sx={{ textAlign: "center", py: 4 }}>
          <IconChartBar size={36} color="#94A3B8" style={{ marginBottom: 8 }} />
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
            NO_VERIFIED_METRICS
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 450, mx: "auto" }}>
            This post was published ({receipt?.provider?.toUpperCase()}) but no verified metric snapshots have been recorded yet.
          </Typography>
        </CardContent>
      </Card>
    )
  }

  const latestObs = aggregate.history_snapshots?.[aggregate.history_snapshots.length - 1]
  const missingList = latestObs?.missing_metrics || []

  return (
    <Card sx={{ border: "1px solid", borderColor: "divider" }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 800 }}>
              Performance Metrics Snapshot
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Remote Post ID: {receipt.remote_post_id} · Provider: {receipt.provider.toUpperCase()}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center">
            {aggregate.is_test_fixture && (
              <Chip label="TEST_DATA" size="small" color="warning" sx={{ fontWeight: 800 }} />
            )}
            <Chip
              label={`${aggregate.observation_count} snapshot(s)`}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 600 }}
            />
          </Stack>
        </Stack>

        <Grid container spacing={2} mb={2}>
          <Grid item xs={12} sm={6} md={3}>
            <StatTile
              label="Total Views"
              value={aggregate.latest_views}
              sublabel="Cumulative reach"
              icon={IconEye}
              isMissing={missingList.includes("views")}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatTile
              label="Likes"
              value={aggregate.latest_likes}
              sublabel="Direct reactions"
              icon={IconThumbUp}
              isMissing={missingList.includes("likes")}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatTile
              label="Comments"
              value={aggregate.latest_comments}
              sublabel="Audience debate"
              icon={IconMessageCircle}
              isMissing={missingList.includes("comments")}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatTile
              label="Engagement Rate"
              value={aggregate.engagement_rate !== null ? `${aggregate.engagement_rate}%` : null}
              sublabel="(Likes + Comments + Shares) / Views"
              icon={IconShare}
              isMissing={aggregate.engagement_rate === null}
            />
          </Grid>
        </Grid>

        {aggregate.history_snapshots && aggregate.history_snapshots.length > 0 && (
          <Box sx={{ mt: 2, pt: 2, borderTop: "1px solid", borderColor: "divider" }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700, textTransform: "uppercase" }}>
              Observation History Timecodes (UTC)
            </Typography>
            <Stack spacing={1} mt={1}>
              {aggregate.history_snapshots.map((s, idx) => (
                <Stack
                  key={idx}
                  direction="row"
                  justifyContent="space-between"
                  alignItems="center"
                  sx={{ py: 0.5, px: 1, bgcolor: "background.default", borderRadius: 1 }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    {new Date(s.observed_at).toLocaleString([], { dateStyle: "short", timeStyle: "medium" })}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Views: {s.views !== null ? s.views : "N/A"} · Likes: {s.likes !== null ? s.likes : "N/A"} · Source: {s.observation_source}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
