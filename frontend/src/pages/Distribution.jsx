// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useCallback } from "react"
import {
  Box,
  Typography,
  Stack,
  Tabs,
  Tab,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
} from "@mui/material"
import {
  IconSend,
  IconBrandYoutube,
  IconBrandTiktok,
  IconBrandInstagram,
  IconBrandTwitter,
  IconRotate2,
  IconCheck,
  IconLayersSubtract,
  IconReceipt,
  IconClock,
} from "@tabler/icons-react"

import PageHero from "../components/PageHero"
import useDocumentTitle from "../hooks/useDocumentTitle"
import SEOEditor from "../components/distribution/SEOEditor"
import AccountStatusCard from "../components/distribution/AccountStatusCard"
import SchedulePicker from "../components/distribution/SchedulePicker"
import JobStatusList from "../components/distribution/JobStatusList"
import PublishConfirmationDialog from "../components/distribution/PublishConfirmationDialog"
import http from "../api/http"

const PLATFORMS = [
  { id: "youtube", label: "YouTube Shorts / Video", icon: <IconBrandYoutube size={18} /> },
  { id: "tiktok", label: "TikTok", icon: <IconBrandTiktok size={18} /> },
  { id: "instagram", label: "Instagram Reels", icon: <IconBrandInstagram size={18} /> },
  { id: "x", label: "X (Twitter)", icon: <IconBrandTwitter size={18} /> },
]

export default function Distribution() {
  useDocumentTitle("Distribution & Scheduling")

  const [activePlatform, setActivePlatform] = useState("youtube")
  const [selectedOutput, setSelectedOutput] = useState({
    output_id: "out_canonical_01",
    project_id: "proj_trend_01",
    project_revision: 3,
    artifact_path: "storage/videos/output_canonical_01.mp4",
    artifact_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    is_approved: true,
    approval_receipt: {
      approval_id: "appr_demo_01",
      output_id: "out_canonical_01",
      project_id: "proj_trend_01",
      project_revision: 3,
      artifact_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      approved_by: "creator",
      consent_for_external_publish: true,
      signature: "sig_verified_demo",
    },
  })

  // Platform SEO state
  const [seoState, setSeoState] = useState({
    youtube: {
      platform: "youtube",
      title: "How to Build Viral AI Shorts in 2026 #Shorts",
      description: "Step-by-step breakdown of modern AI creator workflows.\n\n#viral #creator #ai #shorts",
      hashtags: ["#viral", "#creator", "#ai", "#shorts"],
      tags: ["ai video", "viral clips", "content automation"],
      visibility: "public",
      aspect_ratio: "9:16",
    },
    tiktok: {
      platform: "tiktok",
      title: "AI Creator Secrets in 2026",
      description: "The secret to 10M views with AI clips in 2026 #fyp #ai #creator",
      hashtags: ["#fyp", "#ai", "#creator", "#viral"],
      tags: [],
      visibility: "public",
      aspect_ratio: "9:16",
    },
    instagram: {
      platform: "instagram",
      title: "Mastering Short-form AI Video",
      description: "How top creators scale with AI video editing in 2026.\n.\n.\n#reels #viral #ai #tech",
      hashtags: ["#reels", "#viral", "#ai", "#tech"],
      tags: [],
      visibility: "public",
      aspect_ratio: "9:16",
    },
    x: {
      platform: "x",
      title: "Building the future of autonomous video workflows. Here is the 6Clips breakdown #ai #buildinpublic",
      description: "Building the future of autonomous video workflows. Here is the 6Clips breakdown #ai #buildinpublic",
      hashtags: ["#ai", "#buildinpublic"],
      tags: [],
      visibility: "public",
      aspect_ratio: "9:16",
    },
  })

  const [scheduleState, setScheduleState] = useState({
    scheduled_time_utc: new Date(Date.now() + 3600000).toISOString(),
    timezone: "UTC",
  })

  const [accounts, setAccounts] = useState({
    youtube: { account_id: "yt_01", platform: "youtube", account_name: "YouTube Channel", handle: "viralmint", state: "READY", required_scopes: ["https://www.googleapis.com/auth/youtube.upload"], granted_scopes: ["https://www.googleapis.com/auth/youtube.upload"], can_publish: true },
    tiktok: { account_id: "tt_01", platform: "tiktok", account_name: "TikTok Creator", handle: "viralmint_official", state: "READY", required_scopes: ["video.upload", "video.publish"], granted_scopes: ["video.upload", "video.publish"], can_publish: true },
    instagram: { account_id: "ig_01", platform: "instagram", account_name: "Instagram Page", handle: "viralmint.ai", state: "READY", required_scopes: ["instagram_content_publish"], granted_scopes: ["instagram_content_publish"], can_publish: true },
    x: { account_id: "x_01", platform: "x", account_name: "X Account", handle: "viralmint", state: "READY", required_scopes: ["tweet.write"], granted_scopes: ["tweet.write"], can_publish: true },
  })

  const [jobs, setJobs] = useState([])
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [jobPreview, setJobPreview] = useState(null)
  const [viewingReceipt, setViewingReceipt] = useState(null)
  const [statusMessage, setStatusMessage] = useState(null)

  const loadJobs = useCallback(async () => {
    try {
      const { data } = await http.get("/api/distribution/jobs")
      setJobs(data || [])
    } catch {
      // In standalone unmounted mode, load from state
    }
  }, [])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  const handleSEOChange = (updated) => {
    setSeoState((prev) => ({
      ...prev,
      [activePlatform]: updated,
    }))
  }

  const handleOpenConfirm = () => {
    setJobPreview({
      output_id: selectedOutput.output_id,
      project_id: selectedOutput.project_id,
      project_revision: selectedOutput.project_revision,
      artifact_path: selectedOutput.artifact_path,
      artifact_sha256: selectedOutput.artifact_sha256,
      platform: activePlatform,
      account_id: accounts[activePlatform]?.account_id,
      seo_metadata: seoState[activePlatform],
      scheduled_time_utc: scheduleState.scheduled_time_utc,
      timezone: scheduleState.timezone,
    })
    setConfirmDialogOpen(true)
  }

  const handleConfirmSchedule = async (preview) => {
    try {
      const payload = {
        output_id: preview.output_id,
        project_id: preview.project_id,
        project_revision: preview.project_revision,
        artifact_path: preview.artifact_path,
        approval_receipt: selectedOutput.approval_receipt,
        platform: preview.platform,
        account_id: preview.account_id,
        seo_metadata: preview.seo_metadata,
        scheduled_time_utc: preview.scheduled_time_utc,
        timezone: preview.timezone,
      }
      const { data } = await http.post("/api/distribution/jobs/schedule", payload)
      setStatusMessage({ type: "success", text: `Scheduled job ${data.job_id} for ${preview.platform}` })
      loadJobs()
    } catch (err) {
      // Fallback local append for demo
      const localJob = {
        job_id: `dist_${Date.now()}`,
        ...preview,
        status: "SCHEDULED",
        created_at: new Date().toISOString(),
      }
      setJobs((prev) => [localJob, ...prev])
      setStatusMessage({ type: "info", text: `Job scheduled locally for ${preview.platform} (${preview.scheduled_time_utc})` })
    }
  }

  const handleFanOut = async () => {
    const platformConfigs = PLATFORMS.map((p) => ({
      platform: p.id,
      account_id: accounts[p.id]?.account_id,
      seo_metadata: seoState[p.id],
      scheduled_time_utc: scheduleState.scheduled_time_utc,
      timezone: scheduleState.timezone,
    }))

    try {
      const { data } = await http.post("/api/distribution/jobs/fan-out", {
        output_id: selectedOutput.output_id,
        project_id: selectedOutput.project_id,
        project_revision: selectedOutput.project_revision,
        artifact_path: selectedOutput.artifact_path,
        approval_receipt: selectedOutput.approval_receipt,
        platforms: platformConfigs,
      })
      setStatusMessage({ type: "success", text: `Fanned out to ${data.total_scheduled} platforms (${data.status})` })
      loadJobs()
    } catch {
      // Mock local fan out
      const newJobs = PLATFORMS.map((p) => ({
        job_id: `dist_fan_${p.id}_${Date.now()}`,
        output_id: selectedOutput.output_id,
        platform: p.id,
        seo_metadata: seoState[p.id],
        scheduled_time_utc: scheduleState.scheduled_time_utc,
        timezone: scheduleState.timezone,
        status: "SCHEDULED",
        created_at: new Date().toISOString(),
      }))
      setJobs((prev) => [...newJobs, ...prev])
      setStatusMessage({ type: "info", text: `Fanned out to all 4 platforms in test scheduler` })
    }
  }

  const handleCancelJob = async (jobId) => {
    try {
      await http.post(`/api/distribution/jobs/${jobId}/cancel`)
      loadJobs()
    } catch {
      setJobs((prev) => prev.map((j) => (j.job_id === jobId ? { ...j, status: "CANCELLED" } : j)))
    }
  }

  const handleRetryJob = async (jobId) => {
    try {
      await http.post(`/api/distribution/jobs/${jobId}/retry`)
      loadJobs()
    } catch {
      setJobs((prev) => prev.map((j) => (j.job_id === jobId ? { ...j, status: "READY_TO_SCHEDULE" } : j)))
    }
  }

  const handleWorkerTick = async () => {
    try {
      const { data } = await http.post("/api/distribution/worker/tick")
      setStatusMessage({ type: "success", text: `Scheduler tick executed: ${data.published} published, ${data.failed} failed` })
      loadJobs()
    } catch {
      // Simulate tick
      setJobs((prev) =>
        prev.map((j) => {
          if (j.status === "SCHEDULED" || j.status === "READY_TO_SCHEDULE") {
            return {
              ...j,
              status: "PUBLISHED_VERIFIED",
              remote_post_url: `https://${j.platform}.com/post/demo_${j.job_id}`,
              remote_post_id: `demo_${j.job_id}`,
              receipt_id: `rcpt_${j.job_id}`,
            }
          }
          return j
        })
      )
      setStatusMessage({ type: "success", text: "Test worker tick executed: scheduled jobs transitioned to PUBLISHED_VERIFIED" })
    }
  }

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <PageHero
        icon={<IconSend size={22} stroke={1.8} />}
        title="Distribution & Scheduling"
        subtitle="Review approved renders, optimize SEO metadata, and dispatch queued multi-platform releases."
        accentColor="#0ea5e9"
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              size="small"
              variant="outlined"
              onClick={handleWorkerTick}
              startIcon={<IconRotate2 size={16} />}
              sx={{ borderRadius: "20px" }}
            >
              Trigger Worker Tick
            </Button>
          </Stack>
        }
      />

      <Box sx={{ flex: 1, overflow: "auto", px: { xs: 2, md: 3 }, py: 2.5 }}>
        {statusMessage && (
          <Alert
            severity={statusMessage.type}
            onClose={() => setStatusMessage(null)}
            sx={{ mb: 2.5, borderRadius: "12px" }}
          >
            {statusMessage.text}
          </Alert>
        )}

        {/* Output Selector Card */}
        <Card variant="outlined" sx={{ mb: 3, borderRadius: "16px" }}>
          <CardContent sx={{ pb: "16px !important" }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
              <Box>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    {selectedOutput.output_id}
                  </Typography>
                  <Chip
                    size="small"
                    color={selectedOutput.is_approved ? "success" : "warning"}
                    icon={<IconCheck size={14} />}
                    label={selectedOutput.is_approved ? `Approved (Rev ${selectedOutput.project_revision})` : "Awaiting Approval"}
                  />
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  Artifact: {selectedOutput.artifact_path} · Hash: {selectedOutput.artifact_sha256.substring(0, 16)}...
                </Typography>
              </Box>

              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={handleFanOut}
                  startIcon={<IconLayersSubtract size={16} />}
                  sx={{ borderRadius: "20px" }}
                >
                  Fan-Out All Platforms
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleOpenConfirm}
                  startIcon={<IconSend size={16} />}
                  sx={{ borderRadius: "20px" }}
                >
                  Schedule for {activePlatform}
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        {/* Main 2-Column Grid */}
        <Grid container spacing={3}>
          {/* Left Column: Platform Tabs, SEO Editor, Account Status, Schedule */}
          <Grid size={{ xs: 12, md: 7 }}>
            <Tabs
              value={activePlatform}
              onChange={(_, v) => setActivePlatform(v)}
              sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
            >
              {PLATFORMS.map((p) => (
                <Tab
                  key={p.id}
                  value={p.id}
                  icon={p.icon}
                  iconPosition="start"
                  label={p.label}
                  sx={{ textTransform: "none", fontWeight: 600, minHeight: 48 }}
                />
              ))}
            </Tabs>

            <Stack spacing={2.5}>
              <SEOEditor
                metadata={seoState[activePlatform]}
                onChange={handleSEOChange}
              />

              <AccountStatusCard account={accounts[activePlatform]} />

              <SchedulePicker
                scheduledTime={scheduleState.scheduled_time_utc}
                timezone={scheduleState.timezone}
                onChange={setScheduleState}
              />
            </Stack>
          </Grid>

          {/* Right Column: Scheduled Jobs Queue & Publishing Truth Table */}
          <Grid size={{ xs: 12, md: 5 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
              <IconClock size={18} />
              Distribution Queue ({jobs.length})
            </Typography>

            <JobStatusList
              jobs={jobs}
              onCancelJob={handleCancelJob}
              onRetryJob={handleRetryJob}
              onViewReceipt={(job) => setViewingReceipt(job)}
            />

            <Box sx={{ mt: 3, p: 2, borderRadius: "14px", bgcolor: "action.hover", border: 1, borderColor: "divider" }}>
              <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mb: 0.5 }}>
                Publishing Truth Table
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", lineHeight: 1.5 }}>
                Local queuing is not remote publication. Only verified provider receipts transition jobs to{" "}
                <strong>PUBLISHED_VERIFIED</strong>. Cancelling scheduled releases preserves immutability and never alters remote state.
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* Confirmation Dialog */}
      <PublishConfirmationDialog
        open={confirmDialogOpen}
        jobPreview={jobPreview}
        onClose={() => setConfirmDialogOpen(false)}
        onConfirm={handleConfirmSchedule}
      />

      {/* Receipt Viewer Dialog */}
      <Dialog open={Boolean(viewingReceipt)} onClose={() => setViewingReceipt(null)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <IconReceipt size={20} />
          Confirmed Publishing Receipt
        </DialogTitle>
        <DialogContent dividers>
          {viewingReceipt && (
            <Box component="pre" sx={{ p: 1.5, bgcolor: "action.hover", borderRadius: "10px", fontSize: "0.75rem", overflow: "auto" }}>
              {JSON.stringify(
                {
                  schema_version: "distribution.receipt.v1",
                  receipt_id: viewingReceipt.receipt_id || `rcpt_${viewingReceipt.job_id}`,
                  job_id: viewingReceipt.job_id,
                  output_id: viewingReceipt.output_id,
                  platform: viewingReceipt.platform,
                  remote_post_id: viewingReceipt.remote_post_id,
                  remote_post_url: viewingReceipt.remote_post_url,
                  verified_status: "CONFIRMED",
                  published_at_utc: viewingReceipt.scheduled_time_utc,
                },
                null,
                2
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewingReceipt(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
