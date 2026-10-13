// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogFacetBar: filtering and search controls for the HyperFrames feature catalog.
 */
import React from "react"
import {
  Box,
  Stack,
  TextField,
  Chip,
  ToggleButtonGroup,
  ToggleButton,
  Typography,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconSearch,
  IconX,
  IconDeviceMobile,
  IconDeviceTv,
  IconSparkles,
} from "@tabler/icons-react"

const CATEGORIES = [
  { id: "all", label: "All Blocks" },
  { id: "call-to-action", label: "Call to Action" },
  { id: "typography", label: "Typography" },
  { id: "lower-thirds", label: "Lower Thirds" },
  { id: "charts", label: "Charts & Data" },
  { id: "transitions", label: "Transitions" },
  { id: "backgrounds", label: "Backgrounds" },
  { id: "mock-ui", label: "Mock UI" },
]

export default function CatalogFacetBar({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  aspectRatio,
  onAspectRatioChange,
  disposition,
  onDispositionChange,
  totalCount,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  return (
    <Box sx={{ mb: 3 }}>
      {/* Search and Aspect Ratio Controls */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        alignItems={{ sm: "center" }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        <TextField
          size="small"
          placeholder="Search 196 catalog blocks, titles, tags, licenses..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <IconSearch
                  size={18}
                  style={{ marginRight: 8, color: theme.palette.text.secondary }}
                />
              ),
              endAdornment: search ? (
                <IconX
                  size={16}
                  style={{ cursor: "pointer", color: theme.palette.text.secondary }}
                  onClick={() => onSearchChange("")}
                />
              ) : null,
            },
          }}
          sx={{
            minWidth: { sm: 340 },
            "& .MuiOutlinedInput-root": {
              borderRadius: "10px",
              bgcolor: isDark ? alpha("#fff", 0.04) : alpha("#000", 0.02),
            },
          }}
        />

        <Stack direction="row" spacing={1.5} alignItems="center">
          {/* Aspect Ratio Toggle: 9:16 vs 16:9 */}
          <ToggleButtonGroup
            value={aspectRatio}
            exclusive
            onChange={(_, val) => val && onAspectRatioChange(val)}
            size="small"
            sx={{
              bgcolor: isDark ? alpha("#fff", 0.04) : alpha("#000", 0.03),
              borderRadius: "8px",
              "& .MuiToggleButton-root": {
                px: 1.5,
                py: 0.5,
                fontSize: "0.8rem",
                fontWeight: 600,
                textTransform: "none",
                gap: 0.5,
              },
            }}
          >
            <ToggleButton value="9:16" aria-label="Vertical 9:16">
              <IconDeviceMobile size={16} />
              9:16 (Shorts)
            </ToggleButton>
            <ToggleButton value="16:9" aria-label="Horizontal 16:9">
              <IconDeviceTv size={16} />
              16:9 (Landscape)
            </ToggleButton>
          </ToggleButtonGroup>

          {/* Disposition Filter */}
          <ToggleButtonGroup
            value={disposition}
            exclusive
            onChange={(_, val) => val && onDispositionChange(val)}
            size="small"
            sx={{
              bgcolor: isDark ? alpha("#fff", 0.04) : alpha("#000", 0.03),
              borderRadius: "8px",
              "& .MuiToggleButton-root": {
                px: 1.5,
                py: 0.5,
                fontSize: "0.8rem",
                fontWeight: 600,
                textTransform: "none",
              },
            }}
          >
            <ToggleButton value="ALL">All Status</ToggleButton>
            <ToggleButton value="SHIP">Ship Ready</ToggleButton>
            <ToggleButton value="FIX">In Repair</ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      </Stack>

      {/* Category Chips Bar */}
      <Stack
        direction="row"
        spacing={1}
        sx={{
          overflowX: "auto",
          pb: 0.5,
          "&::-webkit-scrollbar": { height: 4 },
        }}
      >
        {CATEGORIES.map((cat) => {
          const isSelected = category === cat.id
          return (
            <Chip
              key={cat.id}
              label={cat.label}
              onClick={() => onCategoryChange(cat.id)}
              variant={isSelected ? "filled" : "outlined"}
              color={isSelected ? "primary" : "default"}
              size="small"
              sx={{
                fontWeight: isSelected ? 700 : 500,
                fontSize: "0.8rem",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            />
          )
        })}
      </Stack>
    </Box>
  )
}
