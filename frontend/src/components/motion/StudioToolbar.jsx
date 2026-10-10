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
  activeContext,
  onSelectContext,
}) {
  return (
    <Box
      sx={{
        height: 48,
        minHeight: 48,
        bgcolor: "#ffffff",
        borderBottom: "1px solid",
        borderColor: "divider",
        px: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        userSelect: "none",
        zIndex: 10,
      }}
    >
      {/* Left: Project title & Revision badge */}
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Box
            sx={{
              width: 28,
              height: 28,
              borderRadius: 1.5,
              bgcolor: "primary.main",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 6px rgba(139, 92, 246, 0.25)",
            }}
          >
            <IconMovie size={16} stroke={2} />
          </Box>
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 700,
              fontSize: "0.85rem",
              color: "text.primary",
              letterSpacing: "-0.01em",
              maxWidth: 200,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {project?.name || "Active Project"}
          </Typography>
        </Stack>

        <Chip
          size="small"
          label={`Rev ${revision || 1}`}
          variant="outlined"
          sx={{
            height: 20,
            fontSize: "0.68rem",
            fontWeight: 700,
            bgcolor: "#f8fafc",
            borderColor: "divider",
            color: "text.secondary",
          }}
        />

        {project?.is_frozen && (
          <Tooltip title="Revision is frozen for rendering" arrow>
            <Chip
              size="small"
              icon={<IconLock size={12} />}
              label="Frozen"
              sx={{
                height: 20,
                fontSize: "0.68rem",
                bgcolor: "#fef3c7",
                color: "#92400e",
                fontWeight: 600,
              }}
            />
          </Tooltip>
        )}

        <Divider orientation="vertical" flexItem sx={{ height: 18, my: "auto" }} />

        {/* Aspect Ratio Switcher (Contract: 9:16 and 16:9 only) */}
        <Stack direction="row" spacing={0.5} sx={{ bgcolor: "#f1f5f9", p: 0.5, borderRadius: 1.5 }}>
          <Button
            size="small"
            variant={aspectRatio === "9:16" ? "contained" : "text"}
            onClick={() => onAspectChange("9:16")}
            sx={{
              minWidth: 46,
              height: 24,
              px: 1,
              py: 0,
              fontSize: "0.72rem",
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
            variant={aspectRatio === "16:9" ? "contained" : "text"}
            onClick={() => onAspectChange("16:9")}
            sx={{
              minWidth: 46,
              height: 24,
              px: 1,
              py: 0,
              fontSize: "0.72rem",
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
      <Stack direction="row" spacing={0.5} sx={{ bgcolor: "#f8fafc", p: 0.5, borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
        {[
          { id: "create", label: "Create" },
          { id: "review", label: "Review" },
          { id: "refine", label: "Refine" },
        ].map((lvl) => {
          const active = workspaceMode === lvl.id
          return (
            <Button
              key={lvl.id}
              size="small"
              onClick={() => onWorkspaceModeChange(lvl.id)}
              sx={{
                height: 26,
                px: 1.5,
                fontSize: "0.75rem",
                fontWeight: active ? 700 : 500,
                color: active ? "#ffffff" : "text.secondary",
                bgcolor: active ? "primary.main" : "transparent",
                borderRadius: 1.5,
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
      <Stack direction="row" alignItems="center" spacing={1}>
        {/* Contextual Bottom Workspace Switcher (HyperFrames Timeline vs Clip Filmstrip) */}
        {workspaceMode === "refine" && (
          <Stack direction="row" spacing={0.5} sx={{ mr: 1 }}>
            <Tooltip title="HyperFrames Multi-track Timeline" arrow>
              <IconButton
                size="small"
                onClick={() => onSelectContext("hyperframes")}
                sx={{
                  width: 28,
                  height: 28,
                  bgcolor: activeContext === "hyperframes" ? "#ede9fe" : "transparent",
                  color: activeContext === "hyperframes" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconLayersSubtract size={16} stroke={1.8} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Clip Studio Range & Filmstrip Bench" arrow>
              <IconButton
                size="small"
                onClick={() => onSelectContext("clip")}
                sx={{
                  width: 28,
                  height: 28,
                  bgcolor: activeContext === "clip" ? "#ede9fe" : "transparent",
                  color: activeContext === "clip" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconScissors size={16} stroke={1.8} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Deterministic Media Tools" arrow>
              <IconButton
                size="small"
                onClick={() => onSelectContext("tools")}
                sx={{
                  width: 28,
                  height: 28,
                  bgcolor: activeContext === "tools" ? "#ede9fe" : "transparent",
                  color: activeContext === "tools" ? "primary.main" : "text.secondary",
                  borderRadius: 1.5,
                }}
              >
                <IconAdjustments size={16} stroke={1.8} />
              </IconButton>
            </Tooltip>
          </Stack>
        )}

        {/* Save button */}
        <Button
          size="small"
          variant="outlined"
          disabled={!isDirty || isSaving}
          startIcon={isSaving ? <CircularProgress size={14} color="inherit" /> : <IconDeviceFloppy size={15} stroke={2} />}
          onClick={onSave}
          sx={{
            height: 28,
            px: 1.5,
            fontSize: "0.75rem",
            fontWeight: 600,
            borderRadius: 1.5,
            borderColor: isDirty ? "primary.main" : "divider",
            color: isDirty ? "primary.main" : "text.secondary",
          }}
        >
          {isSaving ? "Saving..." : isDirty ? "Save Draft" : "Saved"}
        </Button>

        {/* Export / Render */}
        <Button
          size="small"
          variant="contained"
          disabled={isRendering}
          startIcon={isRendering ? <CircularProgress size={14} color="inherit" /> : <IconPlayerPlay size={15} stroke={2} />}
          onClick={onRender}
          sx={{
            height: 28,
            px: 1.8,
            fontSize: "0.75rem",
            fontWeight: 700,
            borderRadius: 1.5,
            bgcolor: "primary.main",
            boxShadow: "0 2px 8px rgba(139, 92, 246, 0.35)",
            "&:hover": { bgcolor: "primary.dark" },
          }}
        >
          {isRendering ? "Rendering..." : "Export Video"}
        </Button>
      </Stack>
    </Box>
  )
}
