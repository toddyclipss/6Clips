// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * CatalogCard: individual motion block card with truthful posters,
 * aspect ratio badge, disposition status, and non-destructive hover Ghost Preview.
 */
import React, { useState, useRef, useEffect } from "react"
import {
  Box,
  Typography,
  Stack,
  Chip,
  IconButton,
  alpha,
  useTheme,
} from "@mui/material"
import {
  IconEye,
  IconSparkles,
  IconCheck,
  IconAlertTriangle,
  IconPlayerPlay,
} from "@tabler/icons-react"

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
  const aspectTag = is9x16 ? "9x16" : "16x9"
  const aspectSupport = is9x16 ? item.aspect_9_16 : item.aspect_16_9

  const posterUrl = `/api/catalog/blocks/${item.id}/poster?aspect_ratio=${aspectRatio}`
  const previewUrl = `/api/catalog/blocks/${item.id}/preview?aspect_ratio=${aspectRatio}`

  // Hover Ghost Preview: debounced 220ms, non-destructive, muted
  const handleMouseEnter = () => {
    setHovered(true)
    hoverTimerRef.current = setTimeout(() => {
      setGhostActive(true)
    }, 220)
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

  // Card dimensions based on selected aspect ratio
  const frameHeight = is9x16 ? 260 : 160

  const isOperational12 = [
    "aurora", "data-chart", "instagram-follow", "tiktok-follow", "weight-wave", "yt-lower-third",
    "flowing-gradient", "plasma", "stripes", "holographic", "glitch-transition", "creator-hud"
  ].includes(item.id)

  const cardReadiness = isOperational12
    ? "OPERATIONAL"
    : item.disposition === "FIX"
    ? "STRUCTURAL FIX"
    : "QUARANTINED"

  const readinessChipColor = isOperational12
    ? theme.palette.info.main
    : item.disposition === "FIX"
    ? theme.palette.error.main
    : theme.palette.warning.main

  const dispositionColor = readinessChipColor

  const aspectBadgeColor =
    aspectSupport === "NATIVE"
      ? theme.palette.primary.main
      : aspectSupport === "ADAPTED"
      ? theme.palette.info.main
      : theme.palette.text.secondary

  return (
    <Box
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={() => onSelect(item)}
      role="button"
      tabIndex={0}
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
        borderColor: hovered ? "primary.main" : "divider",
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
      {/* Visual Frame: Poster or Live Ghost Preview */}
      <Box
        sx={{
          height: frameHeight,
          position: "relative",
          bgcolor: "#000",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {ghostActive ? (
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
        )}

        {/* Ghost Preview Active Indicator */}
        {ghostActive && (
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
            {item.title}
          </Typography>

          <Chip
            label={cardReadiness}
            size="small"
            sx={{
              height: 18,
              fontSize: "0.65rem",
              fontWeight: 700,
              bgcolor: alpha(readinessChipColor, 0.15),
              color: readinessChipColor,
              border: 1,
              borderColor: alpha(readinessChipColor, 0.3),
            }}
          />
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
          {item.description || "Self-contained motion block for video compositions."}
        </Typography>

        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          sx={{ mt: 1.25, pt: 1, borderTop: 1, borderColor: "divider" }}
        >
          <Typography sx={{ fontSize: "0.7rem", color: "text.disabled", fontWeight: 500 }}>
            {item.category} · {item.license}
          </Typography>
          <Typography sx={{ fontSize: "0.7rem", color: "text.disabled" }}>
            {item.variables_count || 0} vars
          </Typography>
        </Stack>
      </Box>
    </Box>
  )
}
