// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useMemo, useCallback } from "react"
import {
  Box, Stack, Typography, IconButton, Tooltip, Menu, MenuItem,
  ListItemIcon, ListItemText, TextField, Chip, Divider,
} from "@mui/material"
import {
  IconLock,
  IconLockOpen,
  IconEye,
  IconEyeOff,
  IconFolder,
  IconFolderOpen,
  IconChevronDown,
  IconChevronRight,
  IconGripVertical,
  IconTrash,
  IconCopy,
  IconEdit,
  IconSparkles,
  IconVideo,
  IconPhoto,
  IconTypography,
  IconSubtitles,
  IconVolume,
  IconDiamonds,
  IconDotsVertical,
  IconClock,
  IconLayersIntersect,
  IconFolderMinus,
} from "@tabler/icons-react"

/**
 * Professional Layers View (/motion).
 * Projects visual hierarchy, stacking order, parent-child groups,
 * durable visibility, and mutation locking from canonical timeline.tracks[].clips[].
 */
export default function StudioLayersPanel({
  tracks = [],
  selectedElementId = null,
  onSelectElement,
  onToggleVisibility,
  onToggleLock,
  onRenameElement,
  onReorderLayer,
  onGroupElements,
  onUngroupElements,
  onDuplicateClip,
  onDeleteClip,
  onSeek,
}) {
  const [collapsedGroups, setCollapsedGroups] = useState({})
  const [contextMenu, setContextMenu] = useState(null)
  const [renamingId, setRenamingId] = useState(null)
  const [renameText, setRenameText] = useState("")
  const [draggedClipId, setDraggedClipId] = useState(null)
  const [dragOverTargetId, setDragOverTargetId] = useState(null)

  // 1. Flatten all clips from tracks and normalize layer ordering
  const allClips = useMemo(() => {
    const list = []
    tracks.forEach((t) => {
      (t.clips || []).forEach((c) => {
        list.push({
          ...c,
          track_type: t.type || "video",
          track_id: t.id,
        })
      })
    })
    return list
  }, [tracks])

  // 2. Separate visual clips and audio clips
  const visualClips = useMemo(() => {
    return allClips.filter((c) => c.track_type !== "audio" && c.type !== "audio")
  }, [allClips])

  const audioClips = useMemo(() => {
    return allClips.filter((c) => c.track_type === "audio" || c.type === "audio")
  }, [allClips])

  // 3. Build group hierarchy: root elements (parent_id == null) and children
  const { rootElements, childrenMap, groupMap } = useMemo(() => {
    const cMap = {}
    const gMap = {}
    const roots = []

    visualClips.forEach((c) => {
      if (c.type === "group") {
        gMap[c.id] = c
      }
    })

    visualClips.forEach((c) => {
      if (c.parent_id && gMap[c.parent_id]) {
        if (!cMap[c.parent_id]) cMap[c.parent_id] = []
        cMap[c.parent_id].push(c)
      } else {
        roots.push(c)
      }
    })

    // Sort by layer_order descending so higher layers appear at the top of the Layers panel (Photoshop / Premiere convention)
    const sorter = (a, b) => (Number(b.layer_order || 0) - Number(a.layer_order || 0))
    roots.sort(sorter)
    Object.keys(cMap).forEach((k) => cMap[k].sort(sorter))

    return { rootElements: roots, childrenMap: cMap, groupMap: gMap }
  }, [visualClips])

  // Helper: friendly name
  const getClipName = (c) => {
    if (c.title) return c.title
    if (c.name) return c.name
    if (c.block_id) return c.block_id.replace(/[-_]/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
    if (c.track_type === "captions" || c.type === "captions") return c.caption_text ? `CC "${c.caption_text.slice(0, 16)}..."` : "Captions"
    if (c.type === "group") return "Group"
    if (c.track_type === "audio") return c.file || "Audio Track"
    return `${c.type || "Element"} ${c.id.slice(0, 6)}`
  }

  // Type icon resolver
  const renderTypeIcon = (c) => {
    if (c.type === "group") {
      const isCol = !!collapsedGroups[c.id]
      return isCol ? <IconFolder size={16} color="#eab308" /> : <IconFolderOpen size={16} color="#eab308" />
    }
    if (c.type === "block" || c.block_id) {
      return <IconSparkles size={15} color="#8b5cf6" />
    }
    if (c.track_type === "captions" || c.caption_text) {
      return <IconSubtitles size={15} color="#06b6d4" />
    }
    if (c.track_type === "image" || c.type === "image") {
      return <IconPhoto size={15} color="#10b981" />
    }
    if (c.track_type === "audio" || c.type === "audio") {
      return <IconVolume size={15} color="#f97316" />
    }
    return <IconVideo size={15} color="#3b82f6" />
  }

  // Context menu handlers
  const handleOpenContextMenu = (e, clip) => {
    e.preventDefault()
    e.stopPropagation()
    setContextMenu({
      mouseX: e.clientX + 2,
      mouseY: e.clientY - 6,
      clip,
    })
  }

  const handleCloseContextMenu = () => {
    setContextMenu(null)
  }

  const handleStartRename = (clip) => {
    setRenamingId(clip.id)
    setRenameText(clip.title || clip.name || getClipName(clip))
    handleCloseContextMenu()
  }

  const handleCommitRename = (clipId) => {
    if (renameText.trim() && onRenameElement) {
      onRenameElement(clipId, renameText.trim())
    }
    setRenamingId(null)
  }

  // Drag and Drop reordering handlers
  const handleDragStart = (e, clipId) => {
    setDraggedClipId(clipId)
    e.dataTransfer.setData("text/plain", clipId)
    e.dataTransfer.effectAllowed = "move"
  }

  const handleDragOver = (e, targetId) => {
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = "move"
    if (dragOverTargetId !== targetId) {
      setDragOverTargetId(targetId)
    }
  }

  const handleDrop = (e, targetClip) => {
    e.preventDefault()
    e.stopPropagation()
    const sourceId = draggedClipId || e.dataTransfer.getData("text/plain")
    setDraggedClipId(null)
    setDragOverTargetId(null)

    if (!sourceId || sourceId === targetClip.id) return

    const sourceClip = allClips.find((c) => c.id === sourceId)
    if (!sourceClip || sourceClip.locked) return

    if (targetClip.type === "group") {
      // Drop inside group
      if (onReorderLayer) {
        const children = childrenMap[targetClip.id] || []
        const minOrder = children.length > 0 ? Math.min(...children.map((c) => Number(c.layer_order || 0))) : Number(targetClip.layer_order || 0)
        onReorderLayer(sourceId, minOrder, targetClip.id)
      }
    } else {
      // Drop adjacent to target clip (adopt target's parent and target's order)
      if (onReorderLayer) {
        const newOrder = Number(targetClip.layer_order || 0) + 1
        onReorderLayer(sourceId, newOrder, targetClip.parent_id || null)
      }
    }
  }

  // Keyboard navigation
  const handleKeyDown = (e, clip) => {
    if (renamingId) return
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      const idx = visualClips.findIndex((c) => c.id === clip.id)
      if (idx !== -1) {
        const nextIdx = e.key === "ArrowDown" ? Math.min(visualClips.length - 1, idx + 1) : Math.max(0, idx - 1)
        if (onSelectElement) onSelectElement(visualClips[nextIdx])
      }
    } else if (e.key === "ArrowLeft" && clip.type === "group") {
      e.preventDefault()
      setCollapsedGroups((prev) => ({ ...prev, [clip.id]: true }))
    } else if (e.key === "ArrowRight" && clip.type === "group") {
      e.preventDefault()
      setCollapsedGroups((prev) => ({ ...prev, [clip.id]: false }))
    } else if (e.key === "Delete" || e.key === "Backspace") {
      if (!clip.locked && onDeleteClip) {
        e.preventDefault()
        onDeleteClip(clip.id)
      }
    } else if (e.key === " ") {
      e.preventDefault()
      if (onToggleVisibility && !clip.locked) {
        onToggleVisibility(clip.id, clip.visible === false)
      }
    }
  }

  // Row Renderer
  const renderLayerRow = (clip, depth = 0) => {
    const isSelected = selectedElementId === clip.id
    const isGroup = clip.type === "group"
    const isCollapsed = isGroup && !!collapsedGroups[clip.id]
    const children = childrenMap[clip.id] || []
    const isLocked = !!clip.locked
    const isVisible = clip.visible !== false
    const hasAnimation = Array.isArray(clip.animations) && clip.animations.length > 0
    const isRenaming = renamingId === clip.id
    const isDragOver = dragOverTargetId === clip.id

    return (
      <React.Fragment key={clip.id}>
        <Box
          data-layer-id={clip.id}
          tabIndex={0}
          draggable={!isLocked && !isRenaming}
          onDragStart={(e) => handleDragStart(e, clip.id)}
          onDragOver={(e) => handleDragOver(e, clip.id)}
          onDragLeave={() => dragOverTargetId === clip.id && setDragOverTargetId(null)}
          onDrop={(e) => handleDrop(e, clip)}
          onClick={(e) => {
            e.stopPropagation()
            if (onSelectElement) onSelectElement(clip)
          }}
          onDoubleClick={(e) => {
            e.stopPropagation()
            if (!isLocked) handleStartRename(clip)
          }}
          onContextMenu={(e) => handleOpenContextMenu(e, clip)}
          onKeyDown={(e) => handleKeyDown(e, clip)}
          sx={{
            display: "flex",
            alignItems: "center",
            px: 1,
            py: 0.6,
            pl: 1 + depth * 2,
            bgcolor: isSelected
              ? "rgba(59, 130, 246, 0.12)"
              : isDragOver
              ? "rgba(139, 92, 246, 0.15)"
              : "transparent",
            borderLeft: isSelected ? "3px solid #3b82f6" : "3px solid transparent",
            borderBottom: "1px solid",
            borderColor: "divider",
            cursor: "pointer",
            userSelect: "none",
            transition: "background-color 0.15s ease",
            "&:hover": {
              bgcolor: isSelected ? "rgba(59, 130, 246, 0.16)" : "rgba(0, 0, 0, 0.03)",
            },
            opacity: isVisible ? 1 : 0.45,
          }}
        >
          {/* Drag Handle */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              color: isLocked ? "text.disabled" : "text.secondary",
              mr: 0.5,
              cursor: isLocked ? "not-allowed" : "grab",
            }}
          >
            <IconGripVertical size={13} />
          </Box>

          {/* Group Expand / Collapse Toggle */}
          {isGroup ? (
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation()
                setCollapsedGroups((prev) => ({ ...prev, [clip.id]: !prev[clip.id] }))
              }}
              sx={{ p: 0.25, mr: 0.5, width: 18, height: 18 }}
            >
              {isCollapsed ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
            </IconButton>
          ) : (
            <Box sx={{ width: isGroup ? 18 : 6 }} />
          )}

          {/* Type Icon */}
          <Box sx={{ display: "flex", alignItems: "center", mr: 1 }}>
            {renderTypeIcon(clip)}
          </Box>

          {/* Human Readable Name or Inline Rename */}
          <Box sx={{ flex: 1, minWidth: 0, mr: 1 }}>
            {isRenaming ? (
              <TextField
                size="small"
                autoFocus
                value={renameText}
                onChange={(e) => setRenameText(e.target.value)}
                onBlur={() => handleCommitRename(clip.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCommitRename(clip.id)
                  if (e.key === "Escape") setRenamingId(null)
                }}
                onClick={(e) => e.stopPropagation()}
                sx={{
                  "& .MuiInputBase-input": {
                    py: 0.2,
                    px: 0.5,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                  },
                }}
              />
            ) : (
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <Typography
                  variant="caption"
                  noWrap
                  sx={{
                    fontWeight: isSelected ? 700 : 500,
                    color: isSelected ? "primary.main" : "text.primary",
                    fontSize: "0.75rem",
                  }}
                >
                  {getClipName(clip)}
                </Typography>
                {isGroup && (
                  <Chip
                    size="small"
                    label={`${children.length}`}
                    sx={{ height: 15, fontSize: "0.62rem", px: 0.2, bgcolor: "rgba(0,0,0,0.06)" }}
                  />
                )}
                {hasAnimation && (
                  <Tooltip title="Contains animated keyframes" arrow>
                    <Box component="span" sx={{ display: "inline-flex", color: "#8b5cf6" }}>
                      <IconDiamonds size={12} />
                    </Box>
                  </Tooltip>
                )}
              </Stack>
            )}
          </Box>

          {/* Quick Actions: Visibility, Lock, Menu */}
          <Stack direction="row" alignItems="center" spacing={0.25}>
            {/* Lock Toggle */}
            <Tooltip title={isLocked ? "Unlock element (allows mutations)" : "Lock element (prevents changes)"} arrow>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation()
                  if (onToggleLock) onToggleLock(clip.id, !isLocked)
                }}
                sx={{
                  p: 0.25,
                  width: 22,
                  height: 22,
                  color: isLocked ? "#ef4444" : "text.disabled",
                  "&:hover": { color: isLocked ? "#dc2626" : "text.secondary" },
                }}
              >
                {isLocked ? <IconLock size={13} /> : <IconLockOpen size={13} />}
              </IconButton>
            </Tooltip>

            {/* Visibility Toggle */}
            <Tooltip title={isVisible ? "Hide element" : "Show element"} arrow>
              <IconButton
                size="small"
                disabled={isLocked}
                onClick={(e) => {
                  e.stopPropagation()
                  if (onToggleVisibility && !isLocked) {
                    onToggleVisibility(clip.id, !isVisible)
                  }
                }}
                sx={{
                  p: 0.25,
                  width: 22,
                  height: 22,
                  color: isVisible ? "text.secondary" : "#94a3b8",
                  "&:hover": { color: isVisible ? "text.primary" : "text.secondary" },
                }}
              >
                {isVisible ? <IconEye size={14} /> : <IconEyeOff size={14} />}
              </IconButton>
            </Tooltip>

            {/* 3-dots Context Menu Trigger */}
            <IconButton
              size="small"
              onClick={(e) => handleOpenContextMenu(e, clip)}
              sx={{ p: 0.25, width: 20, height: 20, color: "text.disabled" }}
            >
              <IconDotsVertical size={13} />
            </IconButton>
          </Stack>
        </Box>

        {/* Children if Group is Expanded */}
        {isGroup && !isCollapsed && children.map((ch) => renderLayerRow(ch, depth + 1))}
      </React.Fragment>
    )
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#ffffff",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Box sx={{ p: 1.5, pb: 1, borderBottom: "1px solid", borderColor: "divider", bgcolor: "#f8fafc" }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography
            variant="caption"
            sx={{
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "text.secondary",
            }}
          >
            Layers & Stacking
          </Typography>
          <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.7rem", fontWeight: 600 }}>
            {visualClips.length} visual layer{visualClips.length !== 1 ? "s" : ""}
          </Typography>
        </Stack>
      </Box>

      {/* Visual Hierarchy Tree */}
      <Box sx={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {rootElements.length === 0 ? (
          <Box sx={{ p: 3, textAlign: "center", color: "text.secondary" }}>
            <Typography variant="caption" sx={{ display: "block", mb: 0.5, fontWeight: 600 }}>
              No visual elements in timeline
            </Typography>
            <Typography variant="caption" sx={{ color: "text.disabled", fontSize: "0.7rem" }}>
              Add blocks, videos, images, or captions to view and reorder layers.
            </Typography>
          </Box>
        ) : (
          rootElements.map((c) => renderLayerRow(c, 0))
        )}

        {/* Audio Section (clearly demarcated without visual z-order confusion) */}
        {audioClips.length > 0 && (
          <Box sx={{ mt: 1, borderTop: "2px dashed", borderColor: "divider" }}>
            <Box sx={{ px: 1.5, py: 0.75, bgcolor: "#fff7ed" }}>
              <Typography variant="caption" sx={{ fontWeight: 800, color: "#ea580c", fontSize: "0.68rem" }}>
                AUDIO TRACKS (NON-VISUAL)
              </Typography>
            </Box>
            {audioClips.map((ac) => (
              <Box
                key={ac.id}
                onClick={() => onSelectElement && onSelectElement(ac)}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  px: 1.5,
                  py: 0.5,
                  bgcolor: selectedElementId === ac.id ? "rgba(234, 88, 12, 0.1)" : "transparent",
                  borderLeft: selectedElementId === ac.id ? "3px solid #ea580c" : "3px solid transparent",
                  borderBottom: "1px solid",
                  borderColor: "divider",
                  cursor: "pointer",
                }}
              >
                <IconVolume size={14} color="#ea580c" style={{ marginRight: 8 }} />
                <Typography variant="caption" noWrap sx={{ flex: 1, fontSize: "0.72rem", fontWeight: 600 }}>
                  {ac.title || ac.name || ac.file || "Audio Clip"}
                </Typography>
                <Typography variant="caption" sx={{ color: "text.disabled", fontSize: "0.65rem" }}>
                  {Number(ac.duration_seconds || 0).toFixed(1)}s
                </Typography>
              </Box>
            ))}
          </Box>
        )}
      </Box>

      {/* Context Menu */}
      <Menu
        open={!!contextMenu}
        onClose={handleCloseContextMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu ? { top: contextMenu.mouseY, left: contextMenu.mouseX } : undefined
        }
      >
        <MenuItem
          dense
          disabled={!contextMenu?.clip || contextMenu.clip.locked}
          onClick={() => handleStartRename(contextMenu?.clip)}
        >
          <ListItemIcon><IconEdit size={16} /></ListItemIcon>
          <ListItemText primary="Rename" />
        </MenuItem>

        <MenuItem
          dense
          disabled={!contextMenu?.clip}
          onClick={() => {
            if (contextMenu?.clip && onDuplicateClip) {
              onDuplicateClip(contextMenu.clip.id)
            }
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon><IconCopy size={16} /></ListItemIcon>
          <ListItemText primary="Duplicate" />
        </MenuItem>

        <MenuItem
          dense
          disabled={!contextMenu?.clip}
          onClick={() => {
            if (contextMenu?.clip && onToggleVisibility && !contextMenu.clip.locked) {
              onToggleVisibility(contextMenu.clip.id, contextMenu.clip.visible === false)
            }
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon>
            {contextMenu?.clip?.visible === false ? <IconEye size={16} /> : <IconEyeOff size={16} />}
          </ListItemIcon>
          <ListItemText primary={contextMenu?.clip?.visible === false ? "Show Layer" : "Hide Layer"} />
        </MenuItem>

        <MenuItem
          dense
          disabled={!contextMenu?.clip}
          onClick={() => {
            if (contextMenu?.clip && onToggleLock) {
              onToggleLock(contextMenu.clip.id, !contextMenu.clip.locked)
            }
            handleCloseContextMenu()
          }}
        >
          <ListItemIcon>
            {contextMenu?.clip?.locked ? <IconLockOpen size={16} /> : <IconLock size={16} />}
          </ListItemIcon>
          <ListItemText primary={contextMenu?.clip?.locked ? "Unlock" : "Lock"} />
        </MenuItem>

        {contextMenu?.clip?.type === "group" ? (
          <MenuItem
            dense
            disabled={contextMenu.clip.locked}
            onClick={() => {
              if (onUngroupElements) onUngroupElements(contextMenu.clip.id)
              handleCloseContextMenu()
            }}
          >
            <ListItemIcon><IconFolderMinus size={16} /></ListItemIcon>
            <ListItemText primary="Ungroup" />
          </MenuItem>
        ) : (
          <MenuItem
            dense
            disabled={contextMenu?.clip?.locked}
            onClick={() => {
              if (contextMenu?.clip && onGroupElements) {
                onGroupElements([contextMenu.clip.id], `${getClipName(contextMenu.clip)} Group`)
              }
              handleCloseContextMenu()
            }}
          >
            <ListItemIcon><IconLayersIntersect size={16} /></ListItemIcon>
            <ListItemText primary="Group in Folder" />
          </MenuItem>
        )}

        {onSeek && contextMenu?.clip && (
          <MenuItem
            dense
            onClick={() => {
              onSeek(Number(contextMenu.clip.start_seconds || 0))
              handleCloseContextMenu()
            }}
          >
            <ListItemIcon><IconClock size={16} /></ListItemIcon>
            <ListItemText primary="Reveal in Timeline" />
          </MenuItem>
        )}

        <Divider />

        <MenuItem
          dense
          disabled={!contextMenu?.clip || contextMenu.clip.locked}
          onClick={() => {
            if (contextMenu?.clip && onDeleteClip) {
              onDeleteClip(contextMenu.clip.id)
            }
            handleCloseContextMenu()
          }}
          sx={{ color: "error.main" }}
        >
          <ListItemIcon><IconTrash size={16} color="#ef4444" /></ListItemIcon>
          <ListItemText primary="Delete" />
        </MenuItem>
      </Menu>
    </Box>
  )
}
