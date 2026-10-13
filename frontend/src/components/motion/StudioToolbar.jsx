// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React from "react"
import {
  Box, Stack, Typography, Button, IconButton, Chip, Divider,
  Tooltip, Badge, CircularProgress,
} from "@mui/material"
import {
  IconMovie,
  IconPlayerPlay,
  IconDeviceFloppy,
  IconArrowBackUp,
  IconLock,
  IconCheck,
  IconAlertCircle,
  IconLayersSubtract,
  IconScissors,
  IconAdjustments,
  IconCode,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconLayoutSidebarRightCollapse,
  IconLayoutSidebarRightExpand,
  IconMaximize,
  IconMinimize,
} from "@tabler/icons-react"

/**
 * Compact Top Toolbar for the Unified Motion Graphics Workspace.
 * Light-theme professional editor header adhering to the visual reference.
 */
export default function StudioToolbar({
  project,
  revision,
  aspectRatio,
  onAspectChange,
  workspaceMode,
  onWorkspaceModeChange,
  isDirty,
  isSaving,
  onSave,
  onRender,
  isRendering,
  pinnedPanels,
  onTogglePin,
  pinnedLeft = true,
  onToggleLeft,
  pinnedRight = true,
  onToggleRight,
  expandedPreview = false,
  onToggleExpandedPreview,
  activeContext,
  onSelectContext,
}) {
  return (
    <Box
      data-testid="studio-toolbar"
      sx={{
        height: 48,
        minHeight: 48,
        bgcolor: "#ffffff",
        borderBottom: "1px solid",
        borderColor: "divider",
        px: { xs: 1, md: 1.5 },
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 0.5,
        userSelect: "none",
        zIndex: 10,
      }}
    >
      {/* Left: Project title & Revision badge */}
      <Stack direction="row" alignItems="center" spacing={{ xs: 0.5, sm: 0.8 }} sx={{ flexShrink: 0 }}>
        <Stack direction="row" alignItems="center" spacing={0.6}>
          <Box
            sx={{
              width: 24,
              height: 24,
              borderRadius: 1.5,
              bgcolor: "primary.main",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 6px rgba(139, 92, 246, 0.25)",
              flexShrink: 0,
            }}
          >
            <IconMovie size={14} stroke={2} />
          </Box>
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 700,
              fontSize: "0.78rem",
              color: "text.primary",
              letterSpacing: "-0.01em",
              maxWidth: { xs: 55, sm: 80, md: 95, lg: 150 },
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {project?.name || (project ? "Active Project" : "No Project Loaded")}
          </Typography>
        </Stack>

        {project && (
          <Chip
            size="small"
            label={`r${revision || 1}`}
            variant="outlined"
            sx={{
              height: 18,
              fontSize: "0.6rem",
              fontWeight: 700,
              bgcolor: "#f8fafc",
              borderColor: "divider",
              color: "text.secondary",
              px: 0.2,
            }}
          />
        )}

        {project?.is_frozen && (
          <Tooltip title="Revision is frozen for rendering" arrow>
            <Chip
              size="small"
              icon={<IconLock size={11} />}
              label="Frozen"
              sx={{
                height: 18,
                fontSize: "0.62rem",
                bgcolor: "#fef3c7",
                color: "#92400e",
                fontWeight: 600,
                display: { xs: "none", md: "inline-flex" },
              }}
            />
          </Tooltip>
        )}

        <Divider orientation="vertical" flexItem sx={{ height: 16, my: "auto", display: { xs: "none", lg: "block" } }} />

        {/* Aspect Ratio Switcher (Contract: 9:16 and 16:9 only) */}
        <Stack direction="row" spacing={0.2} sx={{ bgcolor: "#f1f5f9", p: 0.2, borderRadius: 1.2 }}>
          <Button
            size="small"
            data-testid="aspect-ratio-btn-9-16"
            variant={aspectRatio === "9:16" ? "contained" : "text"}
            onClick={() => onAspectChange("9:16")}
            sx={{
              minWidth: 38,
              height: 22,
              px: 0.6,
              py: 0,
              fontSize: "0.68rem",
              fontWeight: 700,
              borderRadius: 1,
              boxShadow: aspectRatio === "9:16" ? "0 1px 3px rgba(0,0,0,0.12)" : "none",
              bgcolor: aspectRatio === "9:16" ? "#ffffff" : "transparent",
              color: aspectRatio === "9:16" ? "primary.main" : "text.secondary",
              "&:hover": {
                bgcolor: aspectRatio === "9:16" ? "#ffffff" : "rgba(0,0,0,0.04)",
              },
            }}
          >
            9:16
          </Button>
          <Button
            size="small"
            data-testid="aspect-ratio-btn-16-9"
            variant={aspectRatio === "16:9" ? "contained" : "text"}
            onClick={() => onAspectChange("16:9")}
            sx={{
              minWidth: 38,
              height: 22,
              px: 0.6,
              py: 0,
              fontSize: "0.68rem",
              fontWeight: 700,
              borderRadius: 1,
              boxShadow: aspectRatio === "16:9" ? "0 1px 3px rgba(0,0,0,0.12)" : "none",
              bgcolor: aspectRatio === "16:9" ? "#ffffff" : "transparent",
              color: aspectRatio === "16:9" ? "primary.main" : "text.secondary",
              "&:hover": {
                bgcolor: aspectRatio === "16:9" ? "#ffffff" : "rgba(0,0,0,0.04)",
              },
            }}
          >
            16:9
          </Button>
        </Stack>
      </Stack>

      {/* Center: Stage Level Switcher (Create / Review / Refine) */}
      <Stack direction="row" spacing={0.2} sx={{ bgcolor: "#f8fafc", p: 0.2, borderRadius: 1.5, border: "1px solid", borderColor: "divider", flexShrink: 0 }}>
        {[
          { id: "create", label: "Create" },
          { id: "review", label: "Review" },
          { id: "refine", label: "Refine" },
        ].map((lvl) => {
          const active = workspaceMode === lvl.id
          const disabled = !project && lvl.id !== "create"
          return (
            <Button
              key={lvl.id}
              size="small"
              disabled={disabled}
              onClick={() => onWorkspaceModeChange(lvl.id)}
              sx={{
                height: 22,
                px: { xs: 0.8, sm: 1 },
                fontSize: "0.68rem",
                fontWeight: active ? 700 : 500,
                color: active ? "#ffffff" : disabled ? "text.disabled" : "text.secondary",
                bgcolor: active ? "primary.main" : "transparent",
                borderRadius: 1.2,
                boxShadow: active ? "0 1px 4px rgba(139, 92, 246, 0.3)" : "none",
                "&:hover": {
                  bgcolor: active ? "primary.dark" : "rgba(0,0,0,0.04)",
                },
              }}
            >
              {lvl.label}
            </Button>
          )
        })}
      </Stack>

      {/* Right: Contextual Controls, Save & Render */}
      <Stack direction="row" alignItems="center" spacing={0.6} sx={{ flexShrink: 0 }}>
        {/* Contextual Bottom Workspace Switcher (HyperFrames Timeline vs Clip Filmstrip) */}
        {workspaceMode === "refine" && (
          <Stack direction="row" spacing={0.3} sx={{ mr: 0.5 }}>
            <Tooltip title="HyperFrames Multi-track Timeline" arrow>
              <IconButton
                size="small"
                data-testid="studio-toolbar-timeline-btn"
                onClick={() => onSelectContext("hyperframes")}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: activeContext === "hyperframes" ? "#ede9fe" : "transparent",
                  color: activeContext === "hyperframes" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconLayersSubtract size={15} stroke={1.8} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Clip Studio Range & Filmstrip Bench" arrow>
              <IconButton
                size="small"
                data-testid="studio-toolbar-clip-btn"
                onClick={() => onSelectContext("clip")}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: activeContext === "clip" ? "#ede9fe" : "transparent",
                  color: activeContext === "clip" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconScissors size={15} stroke={1.8} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Deterministic Media Tools" arrow>
              <IconButton
                size="small"
                data-testid="studio-toolbar-tools-btn"
                onClick={() => onSelectContext("tools")}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: activeContext === "tools" ? "#ede9fe" : "transparent",
                  color: activeContext === "tools" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconAdjustments size={15} stroke={1.8} />
              </IconButton>
            </Tooltip>
            <Tooltip title="CodeMirror 6 & Project Code" arrow>
              <IconButton
                size="small"
                aria-label="CodeMirror 6 & Project Code"
                data-testid="studio-toolbar-code-btn"
                onClick={() => onSelectContext("code")}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: activeContext === "code" ? "#ede9fe" : "transparent",
                  color: activeContext === "code" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconCode size={15} stroke={1.8} />
              </IconButton>
            </Tooltip>
          </Stack>
        )}

        {/* Workspace Paneling & Stage Expansion Toggles */}
        {workspaceMode === "refine" && (
          <Stack direction="row" spacing={0.3} sx={{ mr: 0.5 }}>
            <Tooltip title={pinnedLeft ? "Collapse Left Panel (Layers & Assets)" : "Expand Left Panel (Layers & Assets)"} arrow>
              <IconButton
                size="small"
                data-testid="studio-toolbar-toggle-left-btn"
                onClick={onToggleLeft}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: !pinnedLeft ? "#ede9fe" : "transparent",
                  color: !pinnedLeft ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                {pinnedLeft ? <IconLayoutSidebarLeftCollapse size={15} stroke={1.8} /> : <IconLayoutSidebarLeftExpand size={15} stroke={1.8} />}
              </IconButton>
            </Tooltip>
            <Tooltip title={pinnedRight ? "Collapse Inspector Panel" : "Expand Inspector Panel"} arrow>
              <IconButton
                size="small"
                data-testid="studio-toolbar-toggle-right-btn"
                onClick={onToggleRight}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: !pinnedRight ? "#ede9fe" : "transparent",
                  color: !pinnedRight ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                {pinnedRight ? <IconLayoutSidebarRightCollapse size={15} stroke={1.8} /> : <IconLayoutSidebarRightExpand size={15} stroke={1.8} />}
              </IconButton>
            </Tooltip>
            <Tooltip title={expandedPreview ? "Restore Standard Preview Size" : "Expand Preview Stage (Focus Mode)"} arrow>
              <IconButton
                size="small"
                data-testid="studio-toolbar-toggle-expand-btn"
                onClick={onToggleExpandedPreview}
                sx={{
                  width: 26,
                  height: 26,
                  bgcolor: expandedPreview ? "#ede9fe" : "transparent",
                  color: expandedPreview ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                {expandedPreview ? <IconMinimize size={15} stroke={1.8} /> : <IconMaximize size={15} stroke={1.8} />}
              </IconButton>
            </Tooltip>
          </Stack>
        )}

        {/* Save button */}
        <Tooltip title={!project ? "No project loaded" : isSaving ? "Saving..." : isDirty ? "Save Draft" : "Saved"} arrow>
          <Button
            size="small"
            variant="outlined"
            data-testid="studio-toolbar-save-btn"
            disabled={!project || !isDirty || isSaving}
            startIcon={isSaving ? <CircularProgress size={12} color="inherit" /> : <IconDeviceFloppy size={13} stroke={2} />}
            onClick={onSave}
            sx={{
              height: 26,
              minWidth: { xs: 28, xl: 75 },
              px: { xs: 0.6, xl: 1 },
              fontSize: "0.7rem",
              fontWeight: 600,
              borderRadius: 1.5,
              borderColor: isDirty ? "primary.main" : "divider",
              color: isDirty ? "primary.main" : "text.secondary",
              flexShrink: 0,
              whiteSpace: "nowrap",
              "& .MuiButton-startIcon": {
                mr: { xs: 0, xl: 0.8 },
                ml: { xs: 0, xl: -0.2 },
              },
            }}
          >
            <Box component="span" sx={{ display: { xs: "none", xl: "inline" } }}>
              {isSaving ? "Saving..." : isDirty ? "Save Draft" : "Saved"}
            </Box>
          </Button>
        </Tooltip>

        {/* Export / Render */}
        <Tooltip title={!project ? "No project loaded" : isRendering ? "Rendering..." : "Export Video"} arrow>
          <Button
            size="small"
            variant="contained"
            data-testid="studio-toolbar-export-btn"
            disabled={!project || isRendering}
            startIcon={isRendering ? <CircularProgress size={12} color="inherit" /> : <IconPlayerPlay size={13} stroke={2} />}
            onClick={onRender}
            sx={{
              height: 26,
              minWidth: { xs: 28, xl: 95 },
              px: { xs: 0.8, xl: 1.2 },
              fontSize: "0.7rem",
              fontWeight: 700,
              borderRadius: 1.5,
              bgcolor: "primary.main",
              boxShadow: "0 2px 8px rgba(139, 92, 246, 0.35)",
              flexShrink: 0,
              whiteSpace: "nowrap",
              "&:hover": { bgcolor: "primary.dark" },
              "& .MuiButton-startIcon": {
                mr: { xs: 0, xl: 0.8 },
                ml: { xs: 0, xl: -0.2 },
              },
            }}
          >
            <Box component="span" sx={{ display: { xs: "none", xl: "inline" } }}>
              {isRendering ? "Rendering..." : "Export Video"}
            </Box>
          </Button>
        </Tooltip>
      </Stack>
    </Box>
  )
}
