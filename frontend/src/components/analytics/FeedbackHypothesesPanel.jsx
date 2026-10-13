// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 ViralMint Contributors
import React from "react"
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  Alert,
  Divider,
  Box,
} from "@mui/material"
import {
  IconBulb,
  IconShieldLock,
  IconArrowRight,
  IconAlertCircle,
} from "@tabler/icons-react"

export function FeedbackHypothesesPanel({ feedback }) {
  if (!feedback || !feedback.hypotheses || feedback.hypotheses.length === 0) {
    return null
  }

  return (
    <Card sx={{ mt: 3, border: "1px solid", borderColor: "divider" }}>
      <CardContent>
        <Stack direction="row" alignItems="center" spacing={1} mb={1}>
          <IconBulb size={22} color="#F59E0B" />
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Algorithmic Creative Feedback (Hypotheses)
          </Typography>
          <Chip label="Creator Opt-In Required" size="small" color="warning" variant="outlined" sx={{ fontWeight: 700 }} />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={2}>
          {feedback.governance_notice}
        </Typography>

        <Stack spacing={2}>
          {feedback.hypotheses.map((hyp) => (
            <Box
              key={hyp.hypothesis_id}
              sx={{
                p: 2,
                borderRadius: 1.5,
                bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.02)"),
                border: "1px solid",
                borderColor: "divider",
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, textTransform: "capitalize" }}>
                  {hyp.dimension.replace("_", " ")}
                </Typography>
                <Chip
                  label={`Confidence: ${(hyp.confidence_score * 100).toFixed(0)}%`}
                  size="small"
                  color={hyp.confidence_score >= 0.7 ? "success" : "default"}
                  sx={{ fontWeight: 700, fontSize: "0.7rem", height: 20 }}
                />
              </Stack>

              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Observation:</strong> {hyp.observation_summary}
              </Typography>

              <Typography variant="body2" sx={{ color: "primary.main", fontWeight: 600, mb: 1 }}>
                <strong>Proposed Iteration:</strong> {hyp.proposed_change}
              </Typography>

              {hyp.confounders_noted && hyp.confounders_noted.length > 0 && (
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                  <Typography variant="caption" color="text.secondary">
                    Confounders noted:
                  </Typography>
                  {hyp.confounders_noted.map((c, idx) => (
                    <Chip key={idx} label={c} size="small" variant="outlined" sx={{ fontSize: "0.65rem", height: 20 }} />
                  ))}
                </Stack>
              )}
            </Box>
          ))}
        </Stack>
      </CardContent>
    </Card>
  )
}
