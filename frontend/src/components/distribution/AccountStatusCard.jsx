// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import { Box, Typography, Stack, Chip, Alert } from "@mui/material"
import {
  IconCheck,
  IconAlertCircle,
  IconLock,
  IconShieldCheck,
} from "@tabler/icons-react"

export default function AccountStatusCard({ account }) {
  if (!account) return null

  const getStatusChip = (state) => {
    switch (state) {
      case "READY":
        return <Chip size="small" color="success" icon={<IconCheck size={14} />} label="Connected & Ready" />
      case "INSUFFICIENT_SCOPES":
        return <Chip size="small" color="warning" icon={<IconAlertCircle size={14} />} label="Missing Scopes" />
      case "EXPIRED":
        return <Chip size="small" color="error" icon={<IconAlertCircle size={14} />} label="Auth Expired" />
      case "NOT_CONNECTED":
      default:
        return <Chip size="small" color="default" icon={<IconLock size={14} />} label="Not Connected" />
    }
  }

  return (
    <Box sx={{ p: 2, borderRadius: "14px", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            {account.account_name || `${account.platform} Channel`}
          </Typography>
          {account.handle && (
            <Typography variant="caption" color="text.secondary">
              @{account.handle}
            </Typography>
          )}
        </Box>
        {getStatusChip(account.state)}
      </Stack>

      {/* Scope status */}
      <Box sx={{ mb: 1.5 }}>
        <Typography variant="caption" sx={{ fontWeight: 600, display: "block", mb: 0.5 }}>
          Required Publishing Scopes
        </Typography>
        <Stack spacing={0.5}>
          {(account.required_scopes || []).map((scope) => {
            const isGranted = (account.granted_scopes || []).includes(scope)
            return (
              <Stack key={scope} direction="row" spacing={0.8} alignItems="center">
                {isGranted ? (
                  <IconCheck size={13} color="var(--mui-palette-success-main, #22c55e)" />
                ) : (
                  <IconAlertCircle size={13} color="var(--mui-palette-warning-main, #f59e0b)" />
                )}
                <Typography variant="caption" sx={{ fontFamily: "monospace", fontSize: "0.72rem" }}>
                  {scope}
                </Typography>
              </Stack>
            )
          })}
        </Stack>
      </Box>

      {account.state !== "READY" && (
        <Alert severity="info" sx={{ py: 0.2, fontSize: "0.75rem", borderRadius: "10px" }}>
          Live remote publishing requires authenticated OAuth connection. Disconnected local execution records receipts safely.
        </Alert>
      )}
    </Box>
  )
}
