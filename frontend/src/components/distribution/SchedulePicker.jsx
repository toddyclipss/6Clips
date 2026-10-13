// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import {
  Box,
  Typography,
  Stack,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
} from "@mui/material"
import { IconCalendar, IconClock, IconWorld } from "@tabler/icons-react"

const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Asia/Tokyo",
  "America/Sao_Paulo",
]

export default function SchedulePicker({ scheduledTime, timezone, onChange }) {
  // Format to YYYY-MM-DDTHH:mm for local datetime-local input
  const formatDatetimeForInput = (isoString) => {
    if (!isoString) return ""
    try {
      const d = new Date(isoString)
      const pad = (n) => String(n).padStart(2, "0")
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    } catch {
      return ""
    }
  }

  const handleDateTimeChange = (e) => {
    const val = e.target.value
    if (!val) return
    const d = new Date(val)
    onChange({
      scheduled_time_utc: d.toISOString(),
      timezone: timezone || "UTC",
    })
  }

  const setPreset = (offsetMinutes) => {
    const d = new Date(Date.now() + offsetMinutes * 60 * 1000)
    onChange({
      scheduled_time_utc: d.toISOString(),
      timezone: timezone || "UTC",
    })
  }

  const setTomorrowAt = (hour) => {
    const d = new Date()
    d.setDate(d.getDate() + 1)
    d.setHours(hour, 0, 0, 0)
    onChange({
      scheduled_time_utc: d.toISOString(),
      timezone: timezone || "UTC",
    })
  }

  return (
    <Box sx={{ p: 2.5, borderRadius: "16px", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2, display: "flex", alignItems: "center", gap: 1 }}>
        <IconCalendar size={18} />
        Schedule & Timing
      </Typography>

      <Stack spacing={2}>
        <TextField
          type="datetime-local"
          size="small"
          label="Publish Time"
          value={formatDatetimeForInput(scheduledTime)}
          onChange={handleDateTimeChange}
          slotProps={{ inputLabel: { shrink: true } }}
          fullWidth
        />

        <FormControl fullWidth size="small">
          <InputLabel>Timezone</InputLabel>
          <Select
            value={timezone || "UTC"}
            label="Timezone"
            onChange={(e) => onChange({ scheduled_time_utc: scheduledTime, timezone: e.target.value })}
          >
            {TIMEZONES.map((tz) => (
              <MenuItem key={tz} value={tz}>
                {tz}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Quick Presets */}
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 600, display: "block", mb: 0.8, color: "text.secondary" }}>
            Quick Presets
          </Typography>
          <Stack direction="row" flexWrap="wrap" gap={1}>
            <Button size="small" variant="outlined" onClick={() => setPreset(0)} sx={{ borderRadius: "14px", py: 0.2 }}>
              Publish Immediately
            </Button>
            <Button size="small" variant="outlined" onClick={() => setPreset(60)} sx={{ borderRadius: "14px", py: 0.2 }}>
              +1 Hour
            </Button>
            <Button size="small" variant="outlined" onClick={() => setTomorrowAt(9)} sx={{ borderRadius: "14px", py: 0.2 }}>
              Tomorrow 9:00 AM
            </Button>
            <Button size="small" variant="outlined" onClick={() => setTomorrowAt(18)} sx={{ borderRadius: "14px", py: 0.2 }}>
              Tomorrow 6:00 PM
            </Button>
          </Stack>
        </Box>
      </Stack>
    </Box>
  )
}
