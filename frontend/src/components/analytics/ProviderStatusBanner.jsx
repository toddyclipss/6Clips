// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 ViralMint Contributors
import React from "react"
import {
  Box,
  Typography,
  Chip,
  Stack,
  Card,
  CardContent,
} from "@mui/material"
import {
  IconCheck,
  IconClock,
  IconPlugConnectedX,
  IconAlertTriangle,
  IconDatabase,
} from "@tabler/icons-react"

export function ProviderStatusBanner({ providerStatus, isFixturePreview, onClearFixture }) {
  const isDisconnected = providerStatus?.mode === "DISCONNECTED"

  return (
    <Box sx={{ mb: 3 }}>
      {isFixturePreview && (
        <Card
          sx={{
            mb: 2,
            border: "2px dashed #F59E0B",
            bgcolor: (t) => (t.palette.mode === "dark" ? "rgba(245,158,11,0.08)" : "rgba(245,158,11,0.05)"),
          }}
        >
          <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Chip
                  label="TEST_DATA WATERMARK"
                  color="warning"
                  size="small"
                  sx={{ fontWeight: 800, letterSpacing: "0.5px" }}
                />
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Showing isolated developer fixture data. This is NOT live social traffic.
                </Typography>
              </Stack>
              {onClearFixture && (
                <Chip
                  label="Switch to Live View"
                  onClick={onClearFixture}
                  variant="outlined"
                  size="small"
                  sx={{ cursor: "pointer", fontWeight: 600 }}
                />
              )}
            </Stack>
          </CardContent>
        </Card>
      )}

      <Card sx={{ border: "1px solid", borderColor: "divider" }}>
        <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            justifyContent="space-between"
            alignItems={{ xs: "flex-start", sm: "center" }}
            spacing={1.5}
          >
            <Stack direction="row" spacing={1} alignItems="center">
              {isDisconnected ? (
                <IconPlugConnectedX size={20} color="#94A3B8" />
              ) : (
                <IconCheck size={20} color="#10B981" />
              )}
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                Platform Analytics Connectors:
              </Typography>
              <Chip
                label={isDisconnected ? "NOT_CONNECTED (Offline Safe)" : "CONNECTED"}
                size="small"
                color={isDisconnected ? "default" : "success"}
                variant="outlined"
                sx={{ fontWeight: 700, fontSize: "0.7rem", height: 22 }}
              />
            </Stack>

            <Stack direction="row" spacing={1} flexWrap="wrap">
              {Object.entries(providerStatus?.providers || {}).map(([prov, details]) => {
                const isConn = details.connected
                return (
                  <Chip
                    key={prov}
                    label={`${prov.toUpperCase()}: ${details.status}`}
                    size="small"
                    variant={isConn ? "filled" : "outlined"}
                    color={isConn ? "success" : "default"}
                    sx={{ fontSize: "0.65rem", height: 22, textTransform: "uppercase" }}
                  />
                )
              })}
            </Stack>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}
