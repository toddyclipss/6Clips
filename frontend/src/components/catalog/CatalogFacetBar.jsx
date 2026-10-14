// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogFacetBar: truthful discovery, facet filters, search, and inventory views.
 * Exposes explicit view modes per Wave 14 Stage 1 specification:
 * - Available now (operational: 10 donor + 2 6Clips original)
 * - All original HyperFrames (196 verified original donor blocks)
 * - Needs work (adaptation / pending port)
 * - Blocked (license / dependency / security)
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
  IconCheck,
  IconArchive,
  IconTool,
  IconShieldLock,
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
  viewMode = "AVAILABLE_NOW",
  onViewModeChange,
  counts = {},
  totalCount,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const availCount = counts.AVAILABLE_NOW != null ? counts.AVAILABLE_NOW : 12
  const origCount = counts.ALL_ORIGINAL_196 != null ? counts.ALL_ORIGINAL_196 : 196
  const needsWorkCount = counts.NEEDS_WORK != null ? counts.NEEDS_WORK : 0
  const blockedCount = counts.BLOCKED != null ? counts.BLOCKED : 0

  return (
    <Box sx={{ mb: 3 }} role="search" aria-label="Catalog Filtering and Navigation">
      {/* Search, Aspect Ratio, and View Mode Controls */}
      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={2}
        alignItems={{ lg: "center" }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        <TextField
          size="small"
          placeholder="Search catalog blocks, titles, tags, licenses, blocker reasons..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          inputProps={{
            "aria-label": "Search catalog blocks",
          }}
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
                  aria-label="Clear search"
                />
              ) : null,
            },
          }}
          sx={{
            minWidth: { xs: "100%", sm: 360, lg: 420 },
            "& .MuiOutlinedInput-root": {
              borderRadius: "10px",
              bgcolor: isDark ? alpha("#fff", 0.04) : alpha("#000", 0.02),
            },
          }}
        />

        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems={{ sm: "center" }}
          sx={{ flexWrap: "wrap", gap: 1 }}
        >
          {/* Aspect Ratio Toggle: 9:16 vs 16:9 */}
          <ToggleButtonGroup
            value={aspectRatio}
            exclusive
            onChange={(_, val) => val && onAspectRatioChange(val)}
            size="small"
            aria-label="Aspect Ratio Selection"
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
            <ToggleButton value="9:16" aria-label="Vertical 9:16 format">
              <IconDeviceMobile size={16} />
              9:16
            </ToggleButton>
            <ToggleButton value="16:9" aria-label="Horizontal 16:9 format">
              <IconDeviceTv size={16} />
              16:9
            </ToggleButton>
          </ToggleButtonGroup>

          {/* Primary View Filters per Wave 14 Task 2 */}
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, val) => val && onViewModeChange(val)}
            size="small"
            aria-label="Inventory View Selection"
            sx={{
              bgcolor: isDark ? alpha("#fff", 0.04) : alpha("#000", 0.03),
              borderRadius: "8px",
              flexWrap: "wrap",
              "& .MuiToggleButton-root": {
                px: 1.5,
                py: 0.5,
                fontSize: "0.8rem",
                fontWeight: 600,
                textTransform: "none",
                gap: 0.5,
                whiteSpace: "nowrap",
              },
            }}
          >
            <ToggleButton
              value="AVAILABLE_NOW"
              data-testid="filter-available-now"
              aria-label={`Available now: ${availCount} operational blocks`}
            >
              <IconCheck size={15} style={{ color: theme.palette.success.main }} />
              Available now ({availCount})
            </ToggleButton>

            <ToggleButton
              value="ALL_ORIGINAL_196"
              data-testid="filter-all-original"
              aria-label={`All original HyperFrames: ${origCount} verified donor blocks`}
            >
              <IconArchive size={15} style={{ color: theme.palette.info.main }} />
              All original HyperFrames ({origCount} verified)
            </ToggleButton>

            <ToggleButton
              value="NEEDS_WORK"
              data-testid="filter-needs-work"
              aria-label={`Needs work: ${needsWorkCount} blocks needing adaptation or porting`}
            >
              <IconTool size={15} style={{ color: theme.palette.warning.main }} />
              Needs work ({needsWorkCount})
            </ToggleButton>

            <ToggleButton
              value="BLOCKED"
              data-testid="filter-blocked"
              aria-label={`Blocked: ${blockedCount} blocks blocked by license or dependencies`}
            >
              <IconShieldLock size={15} style={{ color: theme.palette.error.main }} />
              Blocked ({blockedCount})
            </ToggleButton>
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
