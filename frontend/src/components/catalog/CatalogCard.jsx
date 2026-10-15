// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogCard (Wave 16): individual motion block card with truthful posters for operational & packaged blocks,
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
  IconPackage,
  IconSparkles,
} from "@tabler/icons-react"
import {
  DONOR_INTERNALIZED_IDS,
  DONOR_PACKAGED_IDS,
  DONOR_SHADER_IDS,
  DONOR_LOWER_THIRD_IDS,
  SOURCE_CATEGORY_MISSING_IDS,
  UNINDEXED_DONOR_IDS,
  CATEGORY_COLOR_MAP,
} from "../../utils/catalogOriginals"

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
  const isPackaged = DONOR_PACKAGED_IDS.has(item.id) || Boolean(item.isPackaged)
  const isShader = DONOR_SHADER_IDS.has(item.id) || Boolean(item.isShader)
  const isLowerThird = DONOR_LOWER_THIRD_IDS.has(item.id) || Boolean(item.isLowerThird)
  const isUnindexed = UNINDEXED_DONOR_IDS.has(item.id) || Boolean(item.isUnindexed)
  const isMissingCategory = Boolean(item.source_category_missing) || SOURCE_CATEGORY_MISSING_IDS.has(item.id)

  const aspectSupport = is9x16
    ? (item.aspect_9_16 || (item.supported_aspects?.includes("9:16") ? "NATIVE" : "CONTAINED_ONLY"))
    : (item.aspect_16_9 || (item.supported_aspects?.includes("16:9") ? "NATIVE" : "CONTAINED_ONLY"))

  // For operational & packaged blocks: truthful poster & preview endpoints
  const posterUrl = isPackaged
    ? (item.poster_url || `/api/projects/catalog/blocks/${item.id}/poster?aspect_ratio=${aspectRatio}`)
    : null
  const previewUrl = isOperational
    ? (item.preview_url || `/api/projects/catalog/blocks/${item.id}/preview?aspect_ratio=${aspectRatio}`)
    : null

  // Hover Ghost Preview: debounced 200ms, active for operational blocks
  const handleMouseEnter = () => {
    setHovered(true)
    if (isOperational) {
      hoverTimerRef.current = setTimeout(() => {
        setGhostActive(true)
      }, 200)
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
  let statusLabel = "NEEDS ADAPTATION"
  let statusColor = theme.palette.warning.dark
  let statusIcon = <IconAlertTriangle size={14} />

  if (isOperational) {
    statusLabel = "OPERATIONAL"
    statusColor = theme.palette.success.main
    statusIcon = <IconPlayerPlay size={14} />
  } else if (isShader) {
    statusLabel = "PACKAGED SHADER"
    statusColor = "#8b5cf6"
    statusIcon = <IconSparkles size={14} />
  } else if (isLowerThird) {
    statusLabel = "PACKAGED LOWER-THIRD"
    statusColor = "#0284c7"
    statusIcon = <IconPackage size={14} />
  } else if (isPackaged) {
    statusLabel = "PACKAGED"
    statusColor = theme.palette.info.main
    statusIcon = <IconPackage size={14} />
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

  const catStyle = CATEGORY_COLOR_MAP[item.category] || { bg: "#f1f5f9", text: "#475569", border: "#cbd5e1" }

  return (
    <Box
      data-testid={`catalog-card-${item.id}`}
      data-operational={isOperational}
      data-packaged={isPackaged}
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
        borderColor: hovered ? (isOperational ? "primary.main" : isPackaged ? "info.main" : "warning.main") : "divider",
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
          bgcolor: isOperational ? "#000" : isPackaged ? "#0f172a" : isDark ? "#0f172a" : "#f1f5f9",
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
              onError={(e) => {
                e.target.style.display = "none"
              }}
              sx={{
                width: "100%",
                height: "100%",
                objectFit: is9x16 ? "cover" : "contain",
                display: "block",
              }}
            />
          )
        ) : isPackaged ? (
          /* Packaged Shipped Block (Shaders & Lower Thirds) */
          <Box sx={{ width: "100%", height: "100%", position: "relative" }}>
            <Box
              component="img"
              src={posterUrl}
              alt={item.title}
              loading="lazy"
              onError={(e) => {
                e.target.style.display = "none"
              }}
              sx={{
                width: "100%",
                height: "100%",
                objectFit: is9x16 ? "cover" : "contain",
                display: "block",
              }}
            />
            <Box
              sx={{
                position: "absolute",
                top: 8,
                right: 8,
                px: 1,
                py: 0.25,
                borderRadius: "4px",
                bgcolor: alpha("#000", 0.75),
                color: isShader ? "#c084fc" : "#38bdf8",
                fontSize: "0.62rem",
                fontWeight: 800,
                letterSpacing: "0.04em",
                zIndex: 2,
              }}
            >
              {isShader ? "SHADER" : isLowerThird ? "LOWER-THIRD" : "SHIPPED"}
            </Box>
          </Box>
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
                label="TEMPLATE"
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
          <Box sx={{ minWidth: 0, flex: 1 }}>
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
            {/* Displayed Original Slug */}
            <Typography
              data-testid={`card-slug-${item.id}`}
              sx={{
                fontSize: "0.68rem",
                fontFamily: "monospace",
                color: "text.disabled",
                letterSpacing: "-0.01em",
              }}
            >
              {item.id}
            </Typography>
          </Box>

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
          {isMissingCategory ? (
            <Tooltip
              title={`Source Category Missing in upstream gallery. Proposed fallback: ${item.proposed_fallback_category || "scenes-demos"}`}
              arrow
            >
              <Chip
                icon={<IconAlertCircle size={10} />}
                label={`Proposed: ${item.proposed_fallback_category || "scenes"}`}
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
          ) : (
            <Tooltip title="Authentic HyperFrames upstream gallery category" arrow>
              <Chip
                label={item.category_label || item.category || "Scenes & Demos"}
                size="small"
                sx={{
                  height: 16,
                  fontSize: "0.6rem",
                  fontWeight: 700,
                  bgcolor: alpha(theme.palette.primary.main, 0.12),
                  color: theme.palette.primary.main,
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
            {item.license || "Apache-2.0"}
          </Typography>
          <Typography sx={{ fontSize: "0.7rem", color: "text.disabled" }}>
            {(item.variables || []).length} vars
          </Typography>
        </Stack>
      </Box>
    </Box>
  )
}
