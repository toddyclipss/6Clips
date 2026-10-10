// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useMemo, memo } from "react"
import {
  Box, Stack, Typography, IconButton, Tooltip, InputBase,
  Menu, MenuItem, ListItemIcon, ListItemText, Dialog, DialogTitle,
  DialogContent, DialogContentText, DialogActions, Button,
} from "@mui/material"
import {
  IconFolder, IconFolderOpen, IconFile, IconFileCode, IconPlus,
  IconFolderPlus, IconTrash, IconEdit, IconArrowsExchange, IconChevronRight,
  IconChevronDown, IconLock,
} from "@tabler/icons-react"

function getFileIcon(filename = "") {
  const ext = filename.split(".").pop()?.toLowerCase() || ""
  switch (ext) {
    case "html":
    case "htm":
      return <IconFileCode size={14} color="#f97316" />
    case "css":
      return <IconFileCode size={14} color="#06b6d4" />
    case "js":
    case "jsx":
    case "ts":
    case "tsx":
      return <IconFileCode size={14} color="#eab308" />
    case "json":
      return <IconFileCode size={14} color="#10b981" />
    default:
      return <IconFile size={14} color="#64748b" />
  }
}

function buildTreeStructure(files = []) {
  const root = { name: "", path: "", isFolder: true, children: {}, files: [] }

  for (const f of files) {
    const rawPath = f.path || f.name || "untitled.txt"
    const parts = rawPath.split("/")
    let current = root

    for (let i = 0; i < parts.length - 1; i++) {
      const folderName = parts[i]
      const folderPath = parts.slice(0, i + 1).join("/")
      if (!current.children[folderName]) {
        current.children[folderName] = {
          name: folderName,
          path: folderPath,
          isFolder: true,
          children: {},
          files: [],
        }
      }
      current = current.children[folderName]
    }

    const fileName = parts[parts.length - 1]
    current.files.push({
      ...f,
      fileName,
      path: rawPath,
    })
  }

  return root
}

export const StudioFileTree = memo(function StudioFileTree({
  files = [],
  activeFileId,
  activeFilePath,
  onSelectFile,
  onCreateFile,
  onRenameFile,
  onMoveFile,
  onDeleteFile,
}) {
  const [expandedFolders, setExpandedFolders] = useState(() => new Set(["", "styles", "scripts", "compositions"]))
  const [contextMenu, setContextMenu] = useState(null)
  const [targetItem, setTargetItem] = useState(null)
  const [dialogMode, setDialogMode] = useState(null) // "create" | "rename" | "move" | "delete"
  const [inputVal, setInputVal] = useState("")

  useEffect(() => {
    const allFolderPaths = new Set(["", "styles", "scripts", "compositions"])
    for (const f of files) {
      const parts = (f.path || "").split("/")
      for (let i = 1; i < parts.length; i++) {
        allFolderPaths.add(parts.slice(0, i).join("/"))
      }
    }
    setExpandedFolders((prev) => new Set([...prev, ...allFolderPaths]))
  }, [files])

  const tree = useMemo(() => buildTreeStructure(files), [files])

  const toggleFolder = (path) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const handleContextMenu = (e, item) => {
    e.preventDefault()
    e.stopPropagation()
    setTargetItem(item)
    setContextMenu({ mouseX: e.clientX, mouseY: e.clientY })
  }

  const handleCloseContext = () => {
    setContextMenu(null)
  }

  const openActionDialog = (mode) => {
    handleCloseContext()
    setDialogMode(mode)
    if (mode === "create") {
      setInputVal(targetItem?.isFolder ? `${targetItem.path ? targetItem.path + "/" : ""}new_file.css` : "new_file.css")
    } else if (mode === "rename") {
      setInputVal(targetItem?.path || "")
    } else if (mode === "move") {
      setInputVal(targetItem?.path || "")
    }
  }

  const executeDialogAction = () => {
    if (!inputVal.trim() && dialogMode !== "delete") return

    if (dialogMode === "create") {
      onCreateFile?.(inputVal.trim(), "")
    } else if (dialogMode === "rename") {
      if (targetItem?.id) onRenameFile?.(targetItem.id, inputVal.trim())
    } else if (dialogMode === "move") {
      if (targetItem?.id) onMoveFile?.(targetItem.id, inputVal.trim())
    } else if (dialogMode === "delete") {
      if (targetItem?.id) onDeleteFile?.(targetItem.id)
    }
    setDialogMode(null)
    setInputVal("")
  }

  const renderFolderNode = (node, depth = 0) => {
    const isExpanded = expandedFolders.has(node.path)
    const folderKeys = Object.keys(node.children).sort()
    const sortedFiles = [...node.files].sort((a, b) => a.fileName.localeCompare(b.fileName))

    return (
      <Box key={node.path || "root"} sx={{ userSelect: "none" }}>
        {node.name && (
          <Box
            onClick={() => toggleFolder(node.path)}
            onContextMenu={(e) => handleContextMenu(e, node)}
            sx={{
              display: "flex",
              alignItems: "center",
              py: 0.4,
              px: 1,
              pl: 1 + depth * 1.5,
              cursor: "pointer",
              borderRadius: 1,
              "&:hover": { bgcolor: "rgba(0,0,0,0.04)" },
            }}
          >
            <Box sx={{ width: 16, display: "flex", alignItems: "center" }}>
              {isExpanded ? <IconChevronDown size={12} color="#94a3b8" /> : <IconChevronRight size={12} color="#94a3b8" />}
            </Box>
            <Box sx={{ mr: 0.75, display: "flex", alignItems: "center" }}>
              {isExpanded ? <IconFolderOpen size={14} color="#8b5cf6" /> : <IconFolder size={14} color="#8b5cf6" />}
            </Box>
            <Typography variant="caption" sx={{ fontWeight: 600, fontSize: "0.74rem", color: "#334155" }}>
              {node.name}
            </Typography>
          </Box>
        )}

        {(isExpanded || !node.name) && (
          <Box>
            {folderKeys.map((k) => renderFolderNode(node.children[k], depth + (node.name ? 1 : 0)))}
            {sortedFiles.map((file) => {
              const isSelected = activeFileId === file.id || activeFilePath === file.path
              return (
                <Box
                  key={file.id || file.path}
                  onClick={() => onSelectFile?.(file)}
                  onContextMenu={(e) => handleContextMenu(e, file)}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    py: 0.4,
                    px: 1,
                    pl: 1 + (depth + (node.name ? 1 : 0)) * 1.5 + 1.25,
                    cursor: "pointer",
                    borderRadius: 1,
                    bgcolor: isSelected ? "#ede9fe" : "transparent",
                    color: isSelected ? "primary.main" : "text.primary",
                    "&:hover": { bgcolor: isSelected ? "#ede9fe" : "rgba(0,0,0,0.03)" },
                  }}
                >
                  <Stack direction="row" alignItems="center" spacing={0.75} sx={{ minWidth: 0 }}>
                    {getFileIcon(file.fileName)}
                    <Typography
                      variant="caption"
                      noWrap
                      sx={{
                        fontWeight: isSelected ? 700 : 500,
                        fontSize: "0.74rem",
                        color: isSelected ? "primary.main" : "#334155",
                      }}
                    >
                      {file.fileName}
                    </Typography>
                  </Stack>
                  {file.read_only && (
                    <Tooltip title="Read-only block source">
                      <IconLock size={12} color="#94a3b8" />
                    </Tooltip>
                  )}
                </Box>
              )
            })}
          </Box>
        )}
      </Box>
    )
  }

  return (
    <Box data-testid="studio-file-tree" sx={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", bgcolor: "#f8fafc" }}>
      {/* Header bar with actions */}
      <Box
        sx={{
          px: 1.25,
          py: 0.75,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: "#ffffff",
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 700, fontSize: "0.72rem", color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Project Explorer ({files.length})
        </Typography>
        <Stack direction="row" spacing={0.5}>
          <Tooltip title="New File" arrow>
            <IconButton
              size="small"
              data-testid="studio-filetree-new-file-btn"
              aria-label="New File"
              onClick={() => {
                setTargetItem(null)
                openActionDialog("create")
              }}
              sx={{ width: 22, height: 22 }}
            >
              <IconPlus size={14} />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Tree content */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 0.75 }}>
        {files.length === 0 ? (
          <Box sx={{ p: 2, textAlign: "center" }}>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              No code files yet. Click + to add custom CSS, HTML, JS, or JSON.
            </Typography>
          </Box>
        ) : (
          renderFolderNode(tree)
        )}
      </Box>

      {/* Context Menu */}
      <Menu
        open={contextMenu !== null}
        onClose={handleCloseContext}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu !== null
            ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
            : undefined
        }
      >
        <MenuItem onClick={() => openActionDialog("create")} sx={{ fontSize: "0.78rem", py: 0.5 }}>
          <ListItemIcon><IconPlus size={14} /></ListItemIcon>
          <ListItemText primary="New File Here" />
        </MenuItem>
        {!targetItem?.isFolder && !targetItem?.read_only && (
          <MenuItem onClick={() => openActionDialog("rename")} sx={{ fontSize: "0.78rem", py: 0.5 }}>
            <ListItemIcon><IconEdit size={14} /></ListItemIcon>
            <ListItemText primary="Rename File" />
          </MenuItem>
        )}
        {!targetItem?.isFolder && !targetItem?.read_only && (
          <MenuItem onClick={() => openActionDialog("move")} sx={{ fontSize: "0.78rem", py: 0.5 }}>
            <ListItemIcon><IconArrowsExchange size={14} /></ListItemIcon>
            <ListItemText primary="Move File" />
          </MenuItem>
        )}
        {!targetItem?.isFolder && !targetItem?.read_only && (
          <MenuItem onClick={() => openActionDialog("delete")} sx={{ fontSize: "0.78rem", py: 0.5, color: "error.main" }}>
            <ListItemIcon><IconTrash size={14} color="#ef4444" /></ListItemIcon>
            <ListItemText primary="Delete File" />
          </MenuItem>
        )}
      </Menu>

      {/* Action Dialog */}
      <Dialog open={dialogMode !== null} onClose={() => setDialogMode(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontSize: "0.9rem", fontWeight: 700 }}>
          {dialogMode === "create" && "Create New Project Code File"}
          {dialogMode === "rename" && "Rename File"}
          {dialogMode === "move" && "Move File to Logical Path"}
          {dialogMode === "delete" && "Confirm File Deletion"}
        </DialogTitle>
        <DialogContent>
          {dialogMode === "delete" ? (
            <DialogContentText sx={{ fontSize: "0.82rem" }}>
              Are you sure you want to delete <b>{targetItem?.path}</b>? This action will bump the project revision.
            </DialogContentText>
          ) : (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 0.5 }}>
                Relative path (e.g. styles/theme.css, custom.html, config.json):
              </Typography>
              <InputBase
                inputProps={{ "data-testid": "studio-filetree-input" }}
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                autoFocus
                fullWidth
                sx={{
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 1,
                  px: 1.5,
                  py: 0.5,
                  fontSize: "0.82rem",
                  bgcolor: "#ffffff",
                }}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button size="small" onClick={() => setDialogMode(null)} sx={{ fontSize: "0.75rem" }}>
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            data-testid="studio-filetree-confirm-btn"
            color={dialogMode === "delete" ? "error" : "primary"}
            onClick={executeDialogAction}
            sx={{ fontSize: "0.75rem", fontWeight: 700 }}
          >
            {dialogMode === "delete" ? "Delete" : "Confirm"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
})

export default StudioFileTree
