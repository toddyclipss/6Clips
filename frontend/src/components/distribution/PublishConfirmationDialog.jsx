// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState } from "react"
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Stack,
  FormControlLabel,
  Checkbox,
  Alert,
  Divider,
  Box,
} from "@mui/material"
import { IconSend, IconAlertTriangle } from "@tabler/icons-react"

export default function PublishConfirmationDialog({
  open,
  onClose,
  onConfirm,
  jobPreview,
}) {
  const [consentGiven, setConsentGiven] = useState(false)

  if (!jobPreview) return null

  const handleConfirm = () => {
    if (!consentGiven) return
    onConfirm(jobPreview)
    onClose()
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>
        Confirm Distribution Schedule
      </DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Alert severity="warning" icon={<IconAlertTriangle size={20} />}>
            <strong>External Action Gate:</strong> Reviewing metadata and scheduling does not auto-publish.
            Publication requires explicit editorial approval and creator consent.
          </Alert>

          <Box sx={{ bgcolor: "action.hover", p: 1.5, borderRadius: "10px" }}>
            <Stack spacing={0.6}>
              <Typography variant="caption" color="text.secondary">
                <strong>Platform:</strong> {jobPreview.platform?.toUpperCase()}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                <strong>Output ID:</strong> {jobPreview.output_id} (Rev {jobPreview.project_revision})
              </Typography>
              <Typography variant="caption" color="text.secondary">
                <strong>Artifact Hash:</strong> {jobPreview.artifact_sha256?.substring(0, 16)}...
              </Typography>
              <Typography variant="caption" color="text.secondary">
                <strong>Scheduled For:</strong> {jobPreview.scheduled_time_utc} ({jobPreview.timezone || "UTC"})
              </Typography>
            </Stack>
          </Box>

          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
              Title / Hook
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              {jobPreview.seo_metadata?.title || "(Untitled)"}
            </Typography>
          </Box>

          {jobPreview.seo_metadata?.description && (
            <Box>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                Description
              </Typography>
              <Typography variant="body2" sx={{ color: "text.secondary", whiteSpace: "pre-wrap", maxHeight: 100, overflow: "auto" }}>
                {jobPreview.seo_metadata.description}
              </Typography>
            </Box>
          )}

          <Divider />

          <FormControlLabel
            control={
              <Checkbox
                checked={consentGiven}
                onChange={(e) => setConsentGiven(e.target.checked)}
                color="primary"
              />
            }
            label={
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                I explicitly authorize 6Clips to schedule and publish this media to the specified external platform.
              </Typography>
            }
          />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          disabled={!consentGiven}
          onClick={handleConfirm}
          startIcon={<IconSend size={16} />}
        >
          Confirm & Schedule
        </Button>
      </DialogActions>
    </Dialog>
  )
}
