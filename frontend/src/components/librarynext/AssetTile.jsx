// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * AssetTile — one item in the proposed Library grid (prototype).
 *
 * One tile component for every media type, so a mixed grid reads as one
 * system: same footprint, same footer grammar, same hover affordances. What
 * changes per media is only what fills the frame (poster / waveform / snippet).
 *
 * The colored rail down the left edge is the provenance signal — created /
 * captured / derived — and it is the ONLY thing colour is used for on this
 * page. It repeats as the connector in the by-source view, so one visual
 * device answers "where did this come from?" in both layouts.
 */
import { useState, useEffect } from "react"
import { Box, Typography, Stack, IconButton, Tooltip, alpha, useTheme } from "@mui/material"
import http from "../../api/http"
import {
  IconPlayerPlay,
  IconDots,
  IconCheck,
  IconMovie,
  IconPhoto,
  IconMusic,
  IconFileText,
  IconBolt,
} from "@tabler/icons-react"
import { ORIGINS, originColor, originTextColor, fmtDay, waveformBars } from "./assetModel"
import { formatClock } from "../../utils/format"

const TILE_WAVEFORM_CACHE = new Map()

const MEDIA_ICON = {
  video: IconMovie,
  image: IconPhoto,
  audio: IconMusic,
  doc: IconFileText,
}

// The app's motion tokens, read defensively: `customMotion` is ours, not a MUI
// default, so a bare ThemeProvider (tests, or any future embed) would otherwise
// throw on `theme.customMotion.duration`.
const MOTION_BASE = "0.2s"
const MOTION_FAST = "0.12s"
const MOTION_EASE = "cubic-bezier(0.4, 0, 0.2, 1)"

export default function AssetTile({
  item,
  dense = false,
  selected = false,
  anySelected = false,
  onOpen,
  onToggleSelect,
 
  onMore,
}) {
  const theme = useTheme()
  const isDark = theme.palette.mode === "dark"
  const [hovered, setHovered] = useState(false)
  // Focus is the keyboard's hover. Every control on this tile — select, play,
  // play, more — was rendered only while `hovered`, which a keyboard user
  // never triggers, so none of them existed in the DOM to tab to. React's
  // onFocus/onBlur bubble (focusin/focusout semantics), so this catches focus
  // landing on the tile OR on anything inside it.
  const [focused, setFocused] = useState(false)
  const [broken, setBroken] = useState(false)
  const [tilePeaks, setTilePeaks] = useState(() => (item?.key ? TILE_WAVEFORM_CACHE.get(item.key) : null))

  useEffect(() => {
    if (item?.media !== "audio" || !item?.key) return
    if (TILE_WAVEFORM_CACHE.has(item.key)) {
      setTilePeaks(TILE_WAVEFORM_CACHE.get(item.key))
      return
    }
    let alive = true
    const count = dense ? 22 : 30
    http.get(`/api/library/waveform/${encodeURIComponent(item.key)}`, { params: { count } })
      .then(({ data }) => {
        if (Array.isArray(data?.peaks)) {
          TILE_WAVEFORM_CACHE.set(item.key, data.peaks)
          if (alive) setTilePeaks(data.peaks)
        }
      })
      .catch(() => {})
    return () => { alive = false }
  }, [item?.key, item?.media, dense])

  const active = hovered || focused

  const oc = originColor(item.origin, isDark)
  const ocText = originTextColor(item.origin, isDark)
  const frameH = dense ? 112 : 148
  const MediaIcon = MEDIA_ICON[item.media] || IconMovie
  const showPoster = (item.media === "video" || item.media === "image") && item.thumb_url && !broken
  const badge = item.aspect || (item.ext ? item.ext.toUpperCase() : null)
  const dur = formatClock(item.duration_seconds)

  return (
    <Box
      role="button"
      data-testid="asset-tile"
      tabIndex={0}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(e) => {
        // Only when focus leaves the tile entirely — moving between the
        // tile's own controls must not tear them out from under the user.
        if (!e.currentTarget.contains(e.relatedTarget)) setFocused(false)
      }}
      onClick={() => (anySelected ? onToggleSelect?.(item) : onOpen?.(item))}
      draggable={true}
      onDragStart={(e) => {
        const dndPayload = {
          asset_id: item.id,
          key: item.key,
          title: item.title,
          media_type: item.media,
          stream_url: item.stream_url,
          duration_seconds: item.duration_seconds || 0,
          aspect_ratio: item.aspect || "9:16",
          source_provenance: `${item.origin}:${item.producer}`,
          permitted_uses: ["timeline_motion", "derivative_clips"],
        }
        e.dataTransfer.setData("application/x-6clips-asset", JSON.stringify(dndPayload))
        e.dataTransfer.setData("text/plain", item.title)
        e.dataTransfer.effectAllowed = "copy"
      }}
      // Mirrors onClick exactly. It used to always open, so with a selection
      // live the keyboard and the mouse did DIFFERENT things from the same
      // control. Space is handled because this claims role="button", and a
      // real button responds to both (preventDefault stops the page scrolling).
      onKeyDown={(e) => {
        if (e.key !== "Enter" && e.key !== " ") return
        e.preventDefault()
        if (anySelected) onToggleSelect?.(item)
        else onOpen?.(item)
      }}
      sx={{
        position: "relative",
        borderRadius: "14px",
        overflow: "hidden",
        cursor: "pointer",
        bgcolor: "background.paper",
        border: 1,
        borderColor: selected ? alpha(theme.palette.primary.main, 0.5) : "divider",
        boxShadow: selected ? theme.customShadows?.md : theme.customShadows?.sm,
        transition: `transform ${MOTION_BASE} ${MOTION_EASE}, box-shadow ${MOTION_BASE} ${MOTION_EASE}, border-color ${MOTION_FAST} ease`,
        "&:hover": { transform: "translateY(-2px)", boxShadow: theme.customShadows?.lg },
        "@media (prefers-reduced-motion: reduce)": { transition: "none", "&:hover": { transform: "none" } },
      }}
    >
      {/* Provenance rail — the page's one use of colour */}
      <Box sx={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: 3, zIndex: 3,
        bgcolor: oc, opacity: 0.9,
      }} />

      {/* ── Frame ── */}
      <Box sx={{ position: "relative", height: frameH, bgcolor: "background.subtle", overflow: "hidden" }}>
        {showPoster ? (
          /* Letterboxed poster over a quiet plate. */
          <Box component="img" src={item.thumb_url} alt=""
            loading="lazy" decoding="async"
            onError={() => setBroken(true)}
            sx={{
              position: "relative", width: "100%", height: "100%",
              objectFit: "contain", display: "block",
            }} />
        ) : item.media === "audio" ? (
          <Stack direction="row" alignItems="center" justifyContent="center" spacing={0.4}
            sx={{ height: "100%", px: 2, bgcolor: alpha(oc, isDark ? 0.1 : 0.06) }}>
            {waveformBars(item.key, dense ? 22 : 30, tilePeaks).map((h, i) => (
              <Box key={i} sx={{
                width: 3, borderRadius: 2, height: `${Math.round(h * 62)}%`,
                bgcolor: oc, opacity: 0.28 + h * 0.5,
              }} />
            ))}
          </Stack>
        ) : item.media === "doc" ? (
          <Box sx={{ height: "100%", p: 1.25, bgcolor: alpha(oc, isDark ? 0.08 : 0.05) }}>
            <Typography sx={{
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              fontSize: "0.6rem", lineHeight: 1.7, color: "text.secondary",
              whiteSpace: "pre-wrap", display: "-webkit-box",
              WebkitLineClamp: dense ? 4 : 5, WebkitBoxOrient: "vertical", overflow: "hidden",
            }}>
              {item.snippet || item.title}
            </Typography>
          </Box>
        ) : (
          // Poster-less video/image → provenance-tinted plate, never an empty box
          <Box sx={{
            height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
            background: `linear-gradient(135deg, ${alpha(oc, isDark ? 0.22 : 0.16)}, ${alpha(oc, 0.03)})`,
          }}>
            <MediaIcon size={30} stroke={1.5} style={{ color: alpha(oc, 0.55) }} />
          </Box>
        )}

        {/* Aspect / extension badge */}
        {badge && (
          <Box sx={{
            position: "absolute", top: 6, right: 6, px: 0.6, py: 0.1, borderRadius: "6px",
            fontSize: "0.6rem", fontWeight: 700, letterSpacing: "0.03em",
            color: "#fff", bgcolor: "rgba(0,0,0,0.62)",
          }}>
            {badge}
          </Box>
        )}

        {/* Select control */}
        {(active || selected || anySelected) && (
          <Box
            role="checkbox"
            aria-checked={selected}
            tabIndex={0}
            onClick={(e) => { e.stopPropagation(); onToggleSelect?.(item) }}
            onKeyDown={(e) => {
              if (e.key !== "Enter" && e.key !== " ") return
              e.preventDefault()
              e.stopPropagation()
              onToggleSelect?.(item)
            }}
            aria-label={selected ? "Deselect" : "Select"}
            sx={{
              position: "absolute", top: 6, left: 8, width: 20, height: 20,
              borderRadius: "6px", display: "flex", alignItems: "center", justifyContent: "center",
              bgcolor: selected ? "primary.main" : "rgba(0,0,0,0.55)",
              border: 1, borderColor: selected ? "primary.main" : "rgba(255,255,255,0.5)",
              zIndex: 4, cursor: "pointer",
            }}>
            {selected && <IconCheck size={14} stroke={2.5} style={{ color: "#fff" }} />}
          </Box>
        )}

        {/* Bottom strip */}
        <Box sx={{
          position: "absolute", left: 0, right: 0, bottom: 0,
          px: 0.75, py: 0.5, display: "flex", alignItems: "center", gap: 0.5,
          background: active
            ? "linear-gradient(to top, rgba(0,0,0,0.62), rgba(0,0,0,0))"
            : "linear-gradient(to top, rgba(0,0,0,0.34), rgba(0,0,0,0))",
          transition: `background ${MOTION_FAST} ease`,
        }}>
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flex: 1, minWidth: 0 }}>
            {dur && <Pill>{dur}</Pill>}
            {item.status === "failed" && <Pill tone="error">Failed</Pill>}
            {item.status === "draft" && <Pill>Draft</Pill>}
            {item.hook_score != null && (
              <Pill><IconBolt size={11} stroke={1.8} style={{ marginRight: 2, marginBottom: -1 }} />{item.hook_score}</Pill>
            )}
          </Stack>
          {active && (
            <Stack direction="row" spacing={0.25} sx={{ flexShrink: 0 }}>
              <FrameAction title={item.media === "image" || item.media === "doc" ? "Open" : "Play"}
                onClick={(e) => { e.stopPropagation(); onOpen?.(item) }}>
                <IconPlayerPlay size={16} stroke={1.8} />
              </FrameAction>
              <FrameAction title="More" onClick={(e) => { e.stopPropagation(); onMore?.(item, e) }}>
                <IconDots size={16} stroke={1.8} />
              </FrameAction>
            </Stack>
          )}
        </Box>
      </Box>

      {/* ── Footer ── */}
      <Box sx={{ pl: 1.5, pr: 1.25, pt: 0.9, pb: 1 }}>
        <Typography sx={{
          fontSize: "0.8rem", fontWeight: 600, lineHeight: 1.35, letterSpacing: "-0.01em",
          display: "-webkit-box", WebkitLineClamp: dense ? 1 : 2, WebkitBoxOrient: "vertical",
          overflow: "hidden", minHeight: dense ? undefined : 34,
        }}>
          {item.title}
        </Typography>
        <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 0.4, minWidth: 0 }}>
          {/* Text steps down to the readable variant; the dot beside it keeps
              the brand colour (decoration clears its own 3:1 floor). */}
          <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: oc, flexShrink: 0 }} />
          <Typography sx={{
            fontSize: "0.62rem", fontWeight: 700, letterSpacing: "0.07em",
            textTransform: "uppercase", color: ocText, flexShrink: 0,
          }}>
            {ORIGINS[item.origin]?.label}
          </Typography>
          <Typography sx={{ fontSize: "0.68rem", color: "text.secondary", flexShrink: 0 }}>·</Typography>
          <Typography noWrap sx={{ fontSize: "0.68rem", color: "text.secondary", minWidth: 0 }}>
            {item.producer}
          </Typography>
          <Typography sx={{ fontSize: "0.68rem", color: "text.disabled", flexShrink: 0, ml: "auto" }}>
            {fmtDay(item.created_at)}
          </Typography>
        </Stack>
      </Box>
    </Box>
  )
}

/** Small glass pill used inside the frame. */
function Pill({ children, tone }) {
  return (
    <Box sx={{
      px: 0.55, py: 0.05, borderRadius: "6px", flexShrink: 0,
      fontSize: "0.6rem", fontWeight: 700, fontVariantNumeric: "tabular-nums",
      color: "#fff", display: "inline-flex", alignItems: "center",
      bgcolor: tone === "error" ? alpha("#dc2626", 0.85) : "rgba(0,0,0,0.62)",
    }}>
      {children}
    </Box>
  )
}

function FrameAction({ title, onClick, children }) {
  return (
    <Tooltip title={title} enterDelay={400}>
      <IconButton size="small" onClick={onClick} aria-label={title}
        sx={{
          width: 24, height: 24, color: "#fff", bgcolor: "rgba(0,0,0,0.58)",
          "&:hover": { bgcolor: "rgba(0,0,0,0.72)" },
        }}>
        {children}
      </IconButton>
    </Tooltip>
  )
}
