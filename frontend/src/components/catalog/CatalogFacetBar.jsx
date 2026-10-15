// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogFacetBar (Wave 16): truthful discovery, authentic HyperFrames categories,
 * aspect ratio controls, and inventory views.
 *
 * Upstream HyperFrames Categories (from donor gallery metadata):
 * - Scenes & Demos, Transitions, Carousels, Text & Captions, Blocks, Surfaces, Code, Data & Charts, 3D Motion, Motion & Effects
 * - Diagnostic: Source Category Missing (25 items with proposed fallbacks)
 *
 * Exposes explicit view modes per Wave 16 specification:
 * - Available now (37 locally packaged cards in shipped_blocks, including 10 operational)
 * - All original HyperFrames (196 verified original donor blocks)
 * - Needs work (159 unported blocks)
 * - Blocked (license / dependency restrictions)
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
  Tooltip,
  Button,
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
  IconAlertCircle,
  IconLayoutGrid,
  IconListDetails,
  IconPackage,
} from "@tabler/icons-react"
import { HYPERFRAMES_CATEGORIES, CATEGORY_COLOR_MAP } from "../../utils/catalogOriginals"

export default function CatalogFacetBar({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  aspectRatio,
  onAspectRatioChange,
  viewMode = "AVAILABLE_NOW",
  onViewModeChange,
  groupByCategory = false,
  onToggleGroupByCategory,
  counts = {},
  totalCount,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const availCount = counts.AVAILABLE_NOW != null ? counts.AVAILABLE_NOW : (counts.PACKAGED_37 != null ? counts.PACKAGED_37 : 37)
  const origCount = counts.ALL_ORIGINAL_196 != null ? counts.ALL_ORIGINAL_196 : 196
  const needsWorkCount = counts.NEEDS_WORK != null ? counts.NEEDS_WORK : 159
  const blockedCount = counts.BLOCKED != null ? counts.BLOCKED : 0
  const categoryCounts = counts.categories || {}

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
          placeholder="Search 196 original donor blocks, slugs, titles, tags, licenses, blocker reasons..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          inputProps={{
            "aria-label": "Search catalog blocks",
            "data-testid": "catalog-search-input",
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
            <ToggleButton value="9:16" aria-label="Vertical 9:16 format" data-testid="aspect-ratio-9-16">
              <IconDeviceMobile size={16} />
              9:16
            </ToggleButton>
            <ToggleButton value="16:9" aria-label="Horizontal 16:9 format" data-testid="aspect-ratio-16-9">
              <IconDeviceTv size={16} />
              16:9
            </ToggleButton>
          </ToggleButtonGroup>

          {/* Group View Toggle */}
          {onToggleGroupByCategory && (
            <Button
              size="small"
              variant={groupByCategory ? "contained" : "outlined"}
              onClick={onToggleGroupByCategory}
              startIcon={groupByCategory ? <IconListDetails size={16} /> : <IconLayoutGrid size={16} />}
              data-testid="toggle-group-by-category"
              sx={{
                borderRadius: "8px",
                fontSize: "0.78rem",
                fontWeight: 600,
                textTransform: "none",
                px: 1.5,
                py: 0.5,
              }}
            >
              {groupByCategory ? "Grouped" : "Grid"}
            </Button>
          )}

          {/* Primary View Filters per Wave 16 */}
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
              aria-label={`Available now: ${availCount} packaged blocks`}
            >
              <IconPackage size={15} style={{ color: theme.palette.info.main }} />
              Available / Packaged ({availCount})
            </ToggleButton>

            <ToggleButton
              value="ALL_ORIGINAL_196"
              data-testid="filter-all-original"
              aria-label={`All original HyperFrames: ${origCount} verified donor blocks`}
            >
              <IconArchive size={15} style={{ color: theme.palette.primary.main }} />
              All 196 Donor Originals ({origCount})
            </ToggleButton>

            <ToggleButton
              value="NEEDS_WORK"
              data-testid="filter-needs-work"
              aria-label={`Needs work: ${needsWorkCount} unported blocks`}
            >
              <IconTool size={15} style={{ color: theme.palette.warning.main }} />
              Unported ({needsWorkCount})
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

      {/* Upstream HyperFrames Category Chips Bar */}
      <Stack
        direction="row"
        spacing={1}
        sx={{
          overflowX: "auto",
          pb: 0.5,
          "&::-webkit-scrollbar": { height: 4 },
        }}
      >
        {HYPERFRAMES_CATEGORIES.map((cat) => {
          const isSelected = category === cat.id
          let catCount = 0
          if (cat.id === "all") {
            catCount = totalCount != null ? totalCount : origCount
          } else if (cat.id === "source_missing") {
            catCount = categoryCounts.source_missing || (counts.SOURCE_CATEGORY_MISSING != null ? counts.SOURCE_CATEGORY_MISSING : 25)
          } else {
            catCount = categoryCounts[cat.id] || 0
          }

          const chipLabel = `${cat.label}${catCount > 0 ? ` (${catCount})` : ""}`
          const isMissingDiagnostic = cat.id === "source_missing"

          return (
            <Tooltip
              key={cat.id}
              title={
                isMissingDiagnostic
                  ? "Diagnostic: 25 unindexed on-disk donor directories lack an explicit category in donor gallery catalog. Proposed fallbacks are derived honestly."
                  : `Authentic HyperFrames gallery category: ${cat.label}`
              }
              arrow
            >
              <Chip
                label={chipLabel}
                icon={isMissingDiagnostic ? <IconAlertCircle size={14} /> : undefined}
                onClick={() => onCategoryChange(cat.id)}
                variant={isSelected ? "filled" : "outlined"}
                color={isSelected ? (isMissingDiagnostic ? "warning" : "primary") : "default"}
                size="small"
                data-testid={`category-filter-${cat.id}`}
                sx={{
                  fontWeight: isSelected ? 700 : 500,
                  fontSize: "0.78rem",
                  borderRadius: "8px",
                  cursor: "pointer",
                  ...(isMissingDiagnostic && !isSelected
                    ? {
                        borderStyle: "dashed",
                        borderColor: theme.palette.warning.main,
                        color: theme.palette.warning.dark,
                      }
                    : {}),
                }}
              />
            </Tooltip>
          )
        })}
      </Stack>
    </Box>
  )
}
