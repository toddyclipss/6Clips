// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useCallback, useMemo, memo } from "react"
import {
  Box, Stack, Typography, IconButton, Button, Tooltip, Chip,
  CircularProgress, Alert, Divider,
} from "@mui/material"
import {
  IconDeviceFloppy, IconRefresh, IconAlertCircle, IconCheck,
  IconX, IconFileCode, IconEye, IconPlus, IconCode, IconEdit,
} from "@tabler/icons-react"
import StudioFileTree from "./StudioFileTree"
import StudioCodeMirror from "./StudioCodeMirror"

export const StudioCodeWorkspace = memo(function StudioCodeWorkspace({
  project,
  revision,
  codeFiles = [],
  onApplyOperation,
  selectedElement,
  onFileSaved,
  onDirtyChange,
}) {
  const [openTabs, setOpenTabs] = useState([]) // list of file paths/ids
  const [activeTab, setActiveTab] = useState(null) // active file path/id
  const [localDrafts, setLocalDrafts] = useState({}) // { [fileId]: content }
  const [savingFileId, setSavingFileId] = useState(null)
  const [editableOverride, setEditableOverride] = useState({}) // { [fileId]: boolean }
  const [errorBanner, setErrorBanner] = useState(null)
  const [successNotice, setSuccessNotice] = useState(null)

  const hasAnyDrafts = useMemo(() => {
    return Object.keys(localDrafts).some((fid) => {
      const f = codeFiles.find((c) => c.id === fid)
      return f && localDrafts[fid] !== undefined && localDrafts[fid] !== (f.content || "")
    })
  }, [localDrafts, codeFiles])

  useEffect(() => {
    onDirtyChange?.(hasAnyDrafts)
  }, [hasAnyDrafts, onDirtyChange])

  // Seed default open tab if files exist and none opened
  useEffect(() => {
    if (codeFiles.length > 0 && openTabs.length === 0) {
      const first = codeFiles[0]
      setOpenTabs([first.id])
      setActiveTab(first.id)
    }
  }, [codeFiles, openTabs.length])

  // Contextual sync: when an element (e.g. block) is selected, switch to its code if present
  useEffect(() => {
    if (!selectedElement) return
    const matched = codeFiles.find(
      (f) => f.clip_id === selectedElement.id || f.path === `compositions/${selectedElement.id}.html`
    )
    if (matched) {
      if (!openTabs.includes(matched.id)) {
        setOpenTabs((prev) => [...prev, matched.id])
      }
      setActiveTab(matched.id)
    }
  }, [selectedElement, codeFiles, openTabs])

  const activeFile = useMemo(() => {
    return codeFiles.find((f) => f.id === activeTab || f.path === activeTab) || null
  }, [codeFiles, activeTab])

  const activeContent = useMemo(() => {
    if (!activeFile) return ""
    if (localDrafts[activeFile.id] !== undefined) {
      return localDrafts[activeFile.id]
    }
    return activeFile.content || ""
  }, [activeFile, localDrafts])

  const isFileDirty = useMemo(() => {
    if (!activeFile) return false
    const draft = localDrafts[activeFile.id]
    return draft !== undefined && draft !== (activeFile.content || "")
  }, [activeFile, localDrafts])

  const jsonValidationError = useMemo(() => {
    if (!activeFile || !activeFile.path?.toLowerCase().endsWith(".json")) return null
    if (!activeContent.trim()) return null
    try {
      JSON.parse(activeContent)
      return null
    } catch (e) {
      return e.message
    }
  }, [activeFile, activeContent])

  const handleSelectFile = useCallback((file) => {
    if (!openTabs.includes(file.id)) {
      setOpenTabs((prev) => [...prev, file.id])
    }
    setActiveTab(file.id)
    setErrorBanner(null)
  }, [openTabs])

  const handleCloseTab = useCallback((e, fileId) => {
    e.stopPropagation()
    setOpenTabs((prev) => {
      const filtered = prev.filter((id) => id !== fileId)
      if (activeTab === fileId) {
        setActiveTab(filtered.length > 0 ? filtered[filtered.length - 1] : null)
      }
      return filtered
    })
  }, [activeTab])

  const handleDraftChange = useCallback((newContent) => {
    if (!activeFile) return
    setLocalDrafts((prev) => ({
      ...prev,
      [activeFile.id]: newContent,
    }))
    setErrorBanner(null)
  }, [activeFile])

  const handleSaveActiveFile = async () => {
    if (!activeFile || !project) return
    const contentToSave = localDrafts[activeFile.id] !== undefined ? localDrafts[activeFile.id] : (activeFile.content || "")
    if (activeFile.path?.toLowerCase().endsWith(".json")) {
      try {
        JSON.parse(contentToSave)
      } catch (e) {
        setErrorBanner(`Invalid JSON syntax: ${e.message}`)
        return
      }
    }
    setSavingFileId(activeFile.id)
    setErrorBanner(null)

    try {
      const res = await onApplyOperation?.("update_file", {
        id: activeFile.id,
        path: activeFile.path,
        content: contentToSave,
      })
      if (res) {
        // Clear draft for this file
        setLocalDrafts((prev) => {
          const next = { ...prev }
          delete next[activeFile.id]
          return next
        })
        setSuccessNotice(`Saved "${activeFile.path}" (Rev ${res.revision})`)
        setTimeout(() => setSuccessNotice(null), 3000)
        onFileSaved?.(activeFile, res.revision)
      } else {
        setErrorBanner("Save conflict: project modified concurrently. Your draft has been retained.")
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || "Failed to save file"
      setErrorBanner(typeof msg === "object" ? JSON.stringify(msg) : String(msg))
    } finally {
      setSavingFileId(null)
    }
  }

  const handleCreateFile = async (path, content = "") => {
    setErrorBanner(null)
    try {
      const res = await onApplyOperation?.("create_file", {
        path,
        content,
      })
      if (res) {
        setSuccessNotice(`Created "${path}" (Rev ${res.revision})`)
        setTimeout(() => setSuccessNotice(null), 3000)
        const newFiles = (res.document?.code?.files) || []
        const created = newFiles.find((f) => f.path === path)
        if (created) {
          handleSelectFile(created)
        }
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || "Failed to create file"
      setErrorBanner(typeof msg === "object" ? JSON.stringify(msg) : String(msg))
    }
  }

  const handleRenameFile = async (fileId, newPath) => {
    setErrorBanner(null)
    try {
      const res = await onApplyOperation?.("rename_file", {
        id: fileId,
        new_path: newPath,
      })
      if (res) {
        setSuccessNotice(`Renamed to "${newPath}" (Rev ${res.revision})`)
        setTimeout(() => setSuccessNotice(null), 3000)
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || "Failed to rename file"
      setErrorBanner(typeof msg === "object" ? JSON.stringify(msg) : String(msg))
    }
  }

  const handleMoveFile = async (fileId, newPath) => {
    setErrorBanner(null)
    try {
      const res = await onApplyOperation?.("move_file", {
        id: fileId,
        new_path: newPath,
      })
      if (res) {
        setSuccessNotice(`Moved to "${newPath}" (Rev ${res.revision})`)
        setTimeout(() => setSuccessNotice(null), 3000)
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || "Failed to move file"
      setErrorBanner(typeof msg === "object" ? JSON.stringify(msg) : String(msg))
    }
  }

  const handleDeleteFile = async (fileId) => {
    setErrorBanner(null)
    try {
      const res = await onApplyOperation?.("delete_file", {
        id: fileId,
      })
      if (res) {
        setSuccessNotice(`Deleted file (Rev ${res.revision})`)
        setTimeout(() => setSuccessNotice(null), 3000)
        setOpenTabs((prev) => prev.filter((id) => id !== fileId))
        if (activeTab === fileId) {
          setActiveTab(null)
        }
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || "Failed to delete file"
      setErrorBanner(typeof msg === "object" ? JSON.stringify(msg) : String(msg))
    }
  }

  return (
    <Box data-testid="studio-code-workspace" sx={{ width: "100%", height: "100%", display: "flex", bgcolor: "#ffffff", borderTop: "1px solid", borderColor: "divider" }}>
      {/* 1. Left Explorer Pane */}
      <Box sx={{ width: 220, minWidth: 200, maxWidth: 280, height: "100%", borderRight: "1px solid", borderColor: "divider" }}>
        <StudioFileTree
          files={codeFiles}
          activeFileId={activeFile?.id}
          activeFilePath={activeFile?.path}
          onSelectFile={handleSelectFile}
          onCreateFile={handleCreateFile}
          onRenameFile={handleRenameFile}
          onMoveFile={handleMoveFile}
          onDeleteFile={handleDeleteFile}
        />
      </Box>

      {/* 2. Main Editor Pane */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, height: "100%" }}>
        {/* Tab Header Bar */}
        <Box
          sx={{
            height: 36,
            minHeight: 36,
            bgcolor: "#f8fafc",
            borderBottom: "1px solid",
            borderColor: "divider",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            px: 1,
          }}
        >
          {/* Scrollable Tabs */}
          <Stack direction="row" spacing={0.5} sx={{ overflowX: "auto", flex: 1, mr: 1 }}>
            {openTabs.map((tid) => {
              const file = codeFiles.find((f) => f.id === tid || f.path === tid)
              if (!file) return null
              const isSelected = activeFile?.id === file.id
              const hasDraft = localDrafts[file.id] !== undefined && localDrafts[file.id] !== file.content

              return (
                <Box
                  key={file.id}
                  onClick={() => setActiveTab(file.id)}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    px: 1.25,
                    py: 0.25,
                    height: 28,
                    borderRadius: 1,
                    cursor: "pointer",
                    bgcolor: isSelected ? "#ffffff" : "transparent",
                    border: "1px solid",
                    borderColor: isSelected ? "divider" : "transparent",
                    color: isSelected ? "primary.main" : "text.secondary",
                    "&:hover": { bgcolor: isSelected ? "#ffffff" : "rgba(0,0,0,0.03)" },
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: isSelected ? 700 : 500, fontSize: "0.72rem", mr: 0.5 }}>
                    {file.path.split("/").pop()}
                    {hasDraft && " *"}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={(e) => handleCloseTab(e, file.id)}
                    sx={{ width: 14, height: 14, p: 0, color: "text.secondary", "&:hover": { color: "error.main" } }}
                  >
                    <IconX size={10} />
                  </IconButton>
                </Box>
              )
            })}
          </Stack>

          {/* Action Toolbar */}
          <Stack direction="row" alignItems="center" spacing={1}>
            {activeFile && (
              <>
                {activeFile.provenance === "project_owned" || editableOverride[activeFile.id] || !activeFile.read_only ? (
                  <Chip
                    size="small"
                    label="Project-Owned"
                    sx={{ height: 18, fontSize: "0.65rem", bgcolor: "#ecfdf5", color: "#047857", fontWeight: 700 }}
                  />
                ) : (
                  <>
                    <Chip
                      size="small"
                      label="Shared Catalog (Read-Only)"
                      sx={{ height: 18, fontSize: "0.65rem", bgcolor: "#f1f5f9", color: "#64748b", fontWeight: 700 }}
                    />
                    <Button
                      size="small"
                      variant="outlined"
                      color="secondary"
                      data-testid="studio-code-customize-btn"
                      onClick={() => setEditableOverride((prev) => ({ ...prev, [activeFile.id]: true }))}
                      startIcon={<IconEdit size={12} />}
                      sx={{ height: 24, px: 1, fontSize: "0.7rem", fontWeight: 700 }}
                    >
                      Customize Code
                    </Button>
                  </>
                )}
              </>
            )}

            {isFileDirty && (
              <Chip
                size="small"
                label="Unsaved Draft"
                sx={{ height: 18, fontSize: "0.65rem", bgcolor: "#fef3c7", color: "#b45309", fontWeight: 700 }}
              />
            )}
            <Button
              size="small"
              variant="contained"
              data-testid="studio-code-save-btn"
              disabled={!activeFile || !isFileDirty || savingFileId !== null}
              onClick={handleSaveActiveFile}
              startIcon={savingFileId !== null ? <CircularProgress size={12} color="inherit" /> : <IconDeviceFloppy size={14} />}
              sx={{
                height: 24,
                px: 1.25,
                fontSize: "0.72rem",
                fontWeight: 700,
                borderRadius: 1,
              }}
            >
              Save File
            </Button>
          </Stack>
        </Box>

        {/* Notices */}
        {jsonValidationError && (
          <Alert severity="warning" data-testid="studio-code-json-warning" sx={{ py: 0.25, px: 1.5, fontSize: "0.74rem" }}>
            JSON Syntax Error: {jsonValidationError}
          </Alert>
        )}
        {errorBanner && (
          <Alert severity="error" data-testid="studio-code-error-banner" sx={{ py: 0.25, px: 1.5, fontSize: "0.74rem" }} onClose={() => setErrorBanner(null)}>
            {errorBanner}
          </Alert>
        )}
        {successNotice && (
          <Alert severity="success" sx={{ py: 0.25, px: 1.5, fontSize: "0.74rem" }} onClose={() => setSuccessNotice(null)}>
            {successNotice}
          </Alert>
        )}

        {/* Editor Area */}
        <Box sx={{ flex: 1, minHeight: 0, position: "relative" }}>
          {activeFile ? (
            <StudioCodeMirror
              content={activeContent}
              filePath={activeFile.path}
              onChange={handleDraftChange}
              readOnly={Boolean(activeFile.read_only && !editableOverride[activeFile.id])}
            />
          ) : (
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", flexDirection: "column" }}>
              <IconCode size={32} color="#94a3b8" />
              <Typography variant="caption" sx={{ color: "text.secondary", mt: 1 }}>
                Select a file from the explorer or create a new file to start editing.
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  )
})

export default StudioCodeWorkspace
