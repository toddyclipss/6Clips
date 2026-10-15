// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogCard: individual motion block card with truthful posters for operational blocks,
 * authentic metadata/blocker blueprints for inventory-only blocks (without fake posters),
 * aspect ratio badge, real disposition status, authentic HyperFrames categories, and
 * non-destructive hover Ghost Preview.
 */
import React, { useState, useRef, useEffect } from "react"
import {
  Box,
  Typography,
  Stack,
  Chip,
  Tooltip,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconPlayerPlay,
  IconShieldLock,
  IconAlertTriangle,
  IconClockHour4,
  IconLock,
  IconAlertCircle,
  IconFolderOff,
} from "@tabler/icons-react"
import { DONOR_INTERNALIZED_IDS, UNINDEXED_DONOR_IDS } from "../../utils/catalogOriginals"

export default function CatalogCard({
  item,
  aspectRatio = "9:16",
  onSelect,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"

  const [hovered, setHovered] = useState(false)
  const [ghostActive, setGhostActive] = useState(false)
  const hoverTimerRef = useRef(null)

  const is9x16 = aspectRatio === "9:16"
  const isDonorInternalized = DONOR_INTERNALIZED_IDS.has(item.id) || item.integration_status === "INTERNALIZED"
  const isOperational = isDonorInternalized || Boolean(item.isOperational)
  const isUnindexed = UNINDEXED_DONOR_IDS.has(item.id) || Boolean(item.isUnindexed)

  const aspectSupport = is9x16 ? (item.aspect_9_16 || "CONTAINED_ONLY") : (item.aspect_16_9 || "CONTAINED_ONLY")

  // For operational blocks only: truthful poster & preview endpoints
  const posterUrl = isOperational
    ? (item.poster_url || `/api/catalog/blocks/${item.id}/poster?aspect_ratio=${aspectRatio}`)
    : null
  const previewUrl = isOperational
    ? (item.preview_url || `/api/catalog/blocks/${item.id}/preview?aspect_ratio=${aspectRatio}`)
    : null

  // Hover Ghost Preview: debounced 220ms, ONLY active for operational blocks
  const handleMouseEnter = () => {
    setHovered(true)
    if (isOperational) {
      hoverTimerRef.current = setTimeout(() => {
        setGhostActive(true)
      }, 220)
    }
  }

  const handleMouseLeave = () => {
    setHovered(false)
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current)
      hoverTimerRef.current = null
    }
    setGhostActive(false)
  }

  // Escape key cancels ghost preview immediately
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && ghostActive) {
        setGhostActive(false)
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [ghostActive])

  // Card frame dimensions based on selected aspect ratio
  const frameHeight = is9x16 ? 260 : 160

  // Status computation based on real backend disposition
  let statusLabel = "QUARANTINED"
  let statusColor = theme.palette.warning.main
  let statusIcon = <IconLock size={14} />

  if (isOperational) {
    statusLabel = "OPERATIONAL"
    statusColor = theme.palette.success.main
    statusIcon = <IconPlayerPlay size={14} />
  } else if (item.integration_status === "ELIGIBLE_NOT_PORTED") {
    statusLabel = "VETTED (NOT PORTED)"
    statusColor = theme.palette.warning.main
    statusIcon = <IconClockHour4 size={14} />
  } else if (item.integration_status === "NEEDS_ADAPTATION") {
    statusLabel = "NEEDS ADAPTATION"
    statusColor = theme.palette.warning.dark
    statusIcon = <IconAlertTriangle size={14} />
  } else if (item.integration_status === "BLOCKED_DEPENDENCY") {
    statusLabel = "BLOCKED DEPENDENCY"
    statusColor = theme.palette.error.main
    statusIcon = <IconLock size={14} />
  } else if (item.integration_status === "BLOCKED_LICENSE" || item.license_status === "RESTRICTED") {
    statusLabel = "BLOCKED LICENSE"
    statusColor = theme.palette.error.main
    statusIcon = <IconShieldLock size={14} />
  }

  const aspectBadgeColor =
    aspectSupport === "NATIVE"
      ? theme.palette.primary.main
      : aspectSupport === "ADAPTED"
      ? theme.palette.info.main
      : theme.palette.text.secondary

  return (
    <Box
      data-testid={`catalog-card-${item.id}`}
      data-operational={isOperational}
      data-status={statusLabel}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={() => onSelect(item)}
      role="button"
      tabIndex={0}
      aria-label={`${item.title || item.id} - ${statusLabel}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onSelect(item)
        }
      }}
      sx={{
        borderRadius: "14px",
        overflow: "hidden",
        border: 1,
        borderColor: hovered ? (isOperational ? "primary.main" : "warning.main") : "divider",
        bgcolor: isDark ? alpha("#fff", 0.03) : "#ffffff",
        transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
        transform: hovered ? "translateY(-3px)" : "none",
        boxShadow: hovered
          ? `0 10px 24px ${alpha(theme.palette.common.black, isDark ? 0.4 : 0.08)}`
          : "none",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        outline: "none",
        "&:focus-visible": {
          borderColor: "primary.main",
          boxShadow: `0 0 0 2px ${alpha(theme.palette.primary.main, 0.4)}`,
        },
      }}
    >
      {/* Visual Frame: Real Poster / Live Ghost Preview OR Truthful Metadata Frame */}
      <Box
        sx={{
          height: frameHeight,
          position: "relative",
          bgcolor: isOperational ? "#000" : isDark ? "#0f172a" : "#f1f5f9",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderBottom: 1,
          borderColor: "divider",
        }}
      >
        {isOperational ? (
          ghostActive ? (
            <Box
              component="iframe"
              src={previewUrl}
              title={`${item.title} Preview`}
              sx={{
                width: "100%",
                height: "100%",
                border: 0,
                pointerEvents: "none",
              }}
            />
          ) : (
            <Box
              component="img"
              src={posterUrl}
              alt={item.title}
              loading="lazy"
              sx={{
                width: "100%",
                height: "100%",
                objectFit: is9x16 ? "cover" : "contain",
                display: "block",
              }}
            />
          )
        ) : (
          /* Honest Metadata Frame for Inventory-Only Blocks (NO fake posters) */
          <Box
            sx={{
              p: 2,
              width: "100%",
              height: "100%",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              boxSizing: "border-box",
              backgroundImage: isDark
                ? "radial-gradient(ellipse at top, rgba(30, 41, 59, 0.6), transparent 70%)"
                : "radial-gradient(ellipse at top, rgba(226, 232, 240, 0.8), transparent 70%)",
            }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Chip
                label="INVENTORY ONLY"
                size="small"
                sx={{
                  height: 18,
                  fontSize: "0.62rem",
                  fontWeight: 800,
                  bgcolor: alpha(theme.palette.warning.main, 0.15),
                  color: theme.palette.warning.main,
                  border: 1,
                  borderColor: alpha(theme.palette.warning.main, 0.3),
                }}
              />
              <Box sx={{ color: statusColor, display: "flex", alignItems: "center" }}>
                {statusIcon}
              </Box>
            </Stack>

            <Box sx={{ my: "auto", textAlign: "center", px: 1 }}>
              <Typography
                variant="caption"
                sx={{
                  display: "block",
                  color: statusColor,
                  fontWeight: 700,
                  fontSize: "0.72rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  mb: 0.5,
                }}
              >
                {statusLabel}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  fontSize: "0.7rem",
                  lineHeight: 1.25,
                  display: "-webkit-box",
                  WebkitLineClamp: is9x16 ? 4 : 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {item.blocker_reason || "Metadata-only donor block entry awaiting porting and verification."}
              </Typography>
            </Box>

            <Typography
              variant="caption"
              sx={{
                fontSize: "0.65rem",
                color: "text.disabled",
                textAlign: "center",
                fontWeight: 600,
              }}
            >
              Action disabled · Click to inspect
            </Typography>
          </Box>
        )}

        {/* Ghost Preview Active Indicator (operational only) */}
        {ghostActive && isOperational && (
          <Box
            sx={{
              position: "absolute",
              top: 8,
              left: 8,
              px: 1,
              py: 0.25,
              borderRadius: "4px",
              bgcolor: alpha("#000", 0.75),
              color: "#38bdf8",
              fontSize: "0.68rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 0.5,
              zIndex: 3,
            }}
          >
            <IconPlayerPlay size={12} />
            PREVIEW
          </Box>
        )}

        {/* Aspect Compatibility Tag */}
        <Box
          sx={{
            position: "absolute",
            bottom: 8,
            left: 8,
            px: 1,
            py: 0.25,
            borderRadius: "4px",
            bgcolor: alpha("#000", 0.75),
            color: aspectBadgeColor,
            fontSize: "0.68rem",
            fontWeight: 700,
            zIndex: 2,
          }}
        >
          {aspectSupport}
        </Box>

        {/* Duration Badge */}
        {item.duration > 0 && (
          <Box
            sx={{
              position: "absolute",
              bottom: 8,
              right: 8,
              px: 0.75,
              py: 0.2,
              borderRadius: "4px",
              bgcolor: alpha("#000", 0.75),
              color: "#fff",
              fontSize: "0.68rem",
              fontWeight: 600,
              zIndex: 2,
            }}
          >
            {item.duration}s
          </Box>
        )}
      </Box>

      {/* Card Info Footer */}
      <Box sx={{ p: 1.5, flex: 1, display: "flex", flexDirection: "column" }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={1}>
          <Typography
            sx={{
              fontSize: "0.92rem",
              fontWeight: 700,
              lineHeight: 1.3,
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "-webkit-box",
              WebkitLineClamp: 1,
              WebkitBoxOrient: "vertical",
            }}
          >
            {item.title || item.id}
          </Typography>

          <Chip
            label={statusLabel}
            size="small"
            sx={{
              height: 18,
              fontSize: "0.62rem",
              fontWeight: 700,
              bgcolor: alpha(statusColor, 0.15),
              color: statusColor,
              border: 1,
              borderColor: alpha(statusColor, 0.3),
              whiteSpace: "nowrap",
            }}
          />
        </Stack>

        {/* Authentic Categories and Provenance Chips */}
        <Stack direction="row" spacing={0.5} sx={{ mt: 0.75, mb: 0.5, flexWrap: "wrap", gap: 0.5 }}>
          {/* Authentic HyperFrames Category */}
          <Chip
            label={item.category || "scenes"}
            size="small"
            sx={{
              height: 16,
              fontSize: "0.6rem",
              fontWeight: 700,
              bgcolor: alpha(theme.palette.primary.main, 0.12),
              color: theme.palette.primary.main,
            }}
          />

          {/* Missing Source Category Diagnostic */}
          {item.source_category_missing && (
            <Tooltip title="Diagnostic: Upstream registry-item.json has no explicit category. Classified via tags." arrow>
              <Chip
                icon={<IconAlertCircle size={10} />}
                label="Tags Resolved"
                size="small"
                sx={{
                  height: 16,
                  fontSize: "0.58rem",
                  fontWeight: 600,
                  bgcolor: alpha(theme.palette.warning.main, 0.12),
                  color: theme.palette.warning.dark,
                  border: "1px dashed",
                  borderColor: alpha(theme.palette.warning.main, 0.4),
                }}
              />
            </Tooltip>
          )}

          {/* 26 Unindexed Donor Dir Indicator */}
          {isUnindexed && (
            <Tooltip title="One of 26 unindexed directories under registry/blocks/." arrow>
              <Chip
                icon={<IconFolderOff size={10} />}
                label="Unindexed"
                size="small"
                sx={{
                  height: 16,
                  fontSize: "0.58rem",
                  fontWeight: 600,
                  bgcolor: alpha(theme.palette.info.main, 0.1),
                  color: theme.palette.info.dark,
                }}
              />
            </Tooltip>
          )}

          {/* License Status */}
          {item.license_status && (
            <Chip
              label={item.license_status.replace("VERIFIED_", "")}
              size="small"
              sx={{
                height: 16,
                fontSize: "0.58rem",
                fontWeight: 600,
                bgcolor: alpha(
                  item.license_status.startsWith("VERIFIED")
                    ? theme.palette.success.main
                    : theme.palette.warning.main,
                  0.12
                ),
                color: item.license_status.startsWith("VERIFIED")
                  ? theme.palette.success.main
                  : theme.palette.warning.main,
              }}
            />
          )}
        </Stack>

        <Typography
          sx={{
            fontSize: "0.75rem",
            color: "text.secondary",
            mt: 0.5,
            lineHeight: 1.3,
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            flex: 1,
          }}
        >
          {item.description || "Original HyperFrames donor block for video compositions."}
        </Typography>

        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          sx={{ mt: 1.25, pt: 1, borderTop: 1, borderColor: "divider" }}
        >
          <Typography sx={{ fontSize: "0.7rem", color: "text.disabled", fontWeight: 500 }}>
            {item.id} · {item.license || "Apache-2.0"}
          </Typography>
          <Typography sx={{ fontSize: "0.7rem", color: "text.disabled" }}>
            {(item.variables || []).length} vars
          </Typography>
        </Stack>
      </Box>
    </Box>
  )
}
