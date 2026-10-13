// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 ViralMint Contributors
import React, { useState, useEffect } from "react"
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Stack,
  CircularProgress,
  Alert,
  Chip,
  Tabs,
  Tab,
  Divider,
} from "@mui/material"
import {
  IconChartBar,
  IconRefresh,
  IconSparkles,
  IconAlertCircle,
  IconInbox,
  IconCheck,
} from "@tabler/icons-react"

import { ProviderStatusBanner } from "../components/analytics/ProviderStatusBanner"
import { PostMetricsDetailCard } from "../components/analytics/PostMetricsDetailCard"
import { FeedbackHypothesesPanel } from "../components/analytics/FeedbackHypothesesPanel"

export default function Analytics() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [providerStatus, setProviderStatus] = useState(null)
  const [receipts, setReceipts] = useState([])
  const [selectedReceiptId, setSelectedReceiptId] = useState(null)
  const [activeMetrics, setActiveMetrics] = useState(null)
  const [activeFeedback, setActiveFeedback] = useState(null)
  const [isFixturePreview, setIsFixturePreview] = useState(false)
  const [seeding, setSeeding] = useState(false)

  // Fetch initial analytics status and receipts
  const loadAnalyticsData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statusRes, receiptsRes] = await Promise.all([
        fetch("/api/analytics/status").then((r) => (r.ok ? r.json() : null)),
        fetch("/api/analytics/receipts").then((r) => (r.ok ? r.json() : { receipts: [] })),
      ])

      setProviderStatus(statusRes)
      const rcpts = receiptsRes?.receipts || []
      setReceipts(rcpts)

      if (rcpts.length > 0) {
        setSelectedReceiptId(rcpts[0].receipt_id)
      } else {
        setSelectedReceiptId(null)
        setActiveMetrics(null)
        setActiveFeedback(null)
      }
    } catch (err) {
      setError(err.message || "Failed to load analytics data")
    } finally {
      setLoading(false)
    }
  }

  // Load metrics & feedback for currently selected post
  useEffect(() => {
    if (!selectedReceiptId) {
      setActiveMetrics(null)
      setActiveFeedback(null)
      return
    }

    const fetchPostDetails = async () => {
      try {
        const postRes = await fetch(`/api/analytics/post/${selectedReceiptId}`).then((r) => r.json())
        setActiveMetrics(postRes)
        setIsFixturePreview(Boolean(postRes?.aggregate?.is_test_fixture))

        if (postRes?.status === "VERIFIED_METRICS_PRESENT") {
          const fbkRes = await fetch(`/api/analytics/feedback/${selectedReceiptId}`)
          if (fbkRes.ok) {
            const fbkData = await fbkRes.json()
            setActiveFeedback(fbkData.feedback)
          } else {
            setActiveFeedback(null)
          }
        } else {
          setActiveFeedback(null)
        }
      } catch (err) {
        console.error("Failed to load post metrics:", err)
      }
    }

    fetchPostDetails()
  }, [selectedReceiptId])

  useEffect(() => {
    loadAnalyticsData()
  }, [])

  // Explicit developer test fixture seed
  const handleSeedFixture = async () => {
    setSeeding(true)
    try {
      const res = await fetch("/api/analytics/fixtures/seed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "demo-creator-clip-1",
          provider: "youtube",
          views: 3420,
          likes: 215,
          comments: 38,
          shares: 19,
          completion_rate: 0.31,
        }),
      })
      if (res.ok) {
        await loadAnalyticsData()
      }
    } catch (err) {
      setError("Failed to seed developer fixture: " + err.message)
    } finally {
      setSeeding(false)
    }
  }

  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1400, mx: "auto" }}>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800 }}>
            Performance Analytics
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Verified post-publication metrics and algorithmic creative feedback.
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<IconRefresh size={16} />}
            onClick={loadAnalyticsData}
            sx={{ textTransform: "none", fontWeight: 600 }}
          >
            Refresh
          </Button>

          {/* Test fixture action only if no live receipts exist */}
          {receipts.length === 0 && (
            <Button
              variant="contained"
              color="warning"
              size="small"
              startIcon={<IconSparkles size={16} />}
              disabled={seeding}
              onClick={handleSeedFixture}
              sx={{ textTransform: "none", fontWeight: 700 }}
            >
              {seeding ? "Seeding..." : "Load Test Fixture"}
            </Button>
          )}
        </Stack>
      </Stack>

      {/* Provider Connectivity Banner */}
      <ProviderStatusBanner
        providerStatus={providerStatus}
        isFixturePreview={isFixturePreview}
        onClearFixture={receipts.length > 0 ? () => setIsFixturePreview(false) : null}
      />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box sx={{ textAlign: "center", py: 8 }}>
          <CircularProgress size={32} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Checking publication receipts and verified metrics...
          </Typography>
        </Box>
      ) : receipts.length === 0 ? (
        /* Empty / Disconnected state */
        <Card sx={{ border: "1px dashed", borderColor: "divider", py: 8, textAlign: "center" }}>
          <CardContent>
            <IconInbox size={48} color="#94A3B8" style={{ marginBottom: 12 }} />
            <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
              AWAITING_PUBLISHED_POST
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 520, mx: "auto", mb: 3 }}>
              No confirmed publication receipts registered yet. When a video is published through Phase 10 Distribution
              or an external provider receipt is recorded, real post metrics will surface here.
            </Typography>
            <Button
              variant="outlined"
              color="warning"
              startIcon={<IconSparkles size={16} />}
              onClick={handleSeedFixture}
              disabled={seeding}
              sx={{ textTransform: "none", fontWeight: 700 }}
            >
              {seeding ? "Generating..." : "Preview with Isolated Test Fixture"}
            </Button>
          </CardContent>
        </Card>
      ) : (
        /* Populated post receipts view */
        <Grid container spacing={3}>
          {/* Left column: Published post selector */}
          <Grid item xs={12} md={4}>
            <Card sx={{ border: "1px solid", borderColor: "divider" }}>
              <CardContent sx={{ p: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 1.5, textTransform: "uppercase" }}>
                  Published Posts ({receipts.length})
                </Typography>
                <Stack spacing={1}>
                  {receipts.map((r) => {
                    const isSelected = r.receipt_id === selectedReceiptId
                    return (
                      <Box
                        key={r.receipt_id}
                        onClick={() => setSelectedReceiptId(r.receipt_id)}
                        sx={{
                          p: 1.5,
                          borderRadius: 1.5,
                          cursor: "pointer",
                          bgcolor: isSelected
                            ? (t) => (t.palette.mode === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.04)")
                            : "transparent",
                          border: "1px solid",
                          borderColor: isSelected ? "primary.main" : "divider",
                          "&:hover": { borderColor: "primary.light" },
                        }}
                      >
                        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
                          <Chip
                            label={r.provider.toUpperCase()}
                            size="small"
                            variant="outlined"
                            sx={{ fontWeight: 700, fontSize: "0.65rem", height: 20 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {new Date(r.publish_timestamp).toLocaleDateString([], {
                              month: "short",
                              day: "numeric",
                            })}
                          </Typography>
                        </Stack>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {r.remote_post_id}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                          Account: {r.account_reference}
                        </Typography>
                      </Box>
                    )
                  })}
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          {/* Right column: Metric details and creative feedback */}
          <Grid item xs={12} md={8}>
            {activeMetrics && (
              <>
                <PostMetricsDetailCard
                  receipt={activeMetrics.receipt}
                  aggregate={activeMetrics.aggregate}
                />
                <FeedbackHypothesesPanel feedback={activeFeedback} />
              </>
            )}
          </Grid>
        </Grid>
      )}
    </Box>
  )
}
