// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useCallback, useMemo, useRef } from "react"
import { useNavigate } from "react-router-dom"
import {
  Box, Stack, Typography, CircularProgress, useTheme,
  Button, Alert, Snackbar, IconButton, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
} from "@mui/material"
import {
  IconLayoutSidebarLeftExpand,
  IconLayoutSidebarRightExpand,
} from "@tabler/icons-react"
import useDocumentTitle from "../hooks/useDocumentTitle"
import useAppStore from "../store/appStore"
import http from "../api/http"
import { ws } from "../api/websocket"

import StudioToolbar from "../components/motion/StudioToolbar"
import StudioResourcePanel from "../components/motion/StudioResourcePanel"
import StudioInspectorPanel from "../components/motion/StudioInspectorPanel"
import StudioPreviewStage from "../components/motion/StudioPreviewStage"
import StudioTimelineWorkspace from "../components/motion/StudioTimelineWorkspace"
import StudioToolsWorkspace from "../components/motion/StudioToolsWorkspace"
import StudioLayersPanel from "../components/motion/StudioLayersPanel"
import StudioVariablesPanel from "../components/motion/StudioVariablesPanel"
import StudioCodeWorkspace from "../components/motion/StudioCodeWorkspace"
import SourceBench from "../components/clip/bench/SourceBench"
import ExtractDialog from "../components/clip/ExtractDialog"
import useClipSettings from "../components/clip/useClipSettings"
import useBenchRanges from "../components/clip/bench/useBenchRanges"
import MotionInstallGate from "../components/MotionInstallGate"

/**
 * Unified Motion Graphics Workspace (/motion).
 * Consolidates HyperFrames composition, Clip Studio ranges, deterministic Tools,
 * Library media, and Trends sources into a single professional creation workspace.
 */
export default function MotionGraphics() {
  useDocumentTitle("Motion Graphics Studio")
  const theme = useTheme()
  const navigate = useNavigate()
  const showSnackbar = useAppStore((s) => s.showSnackbar)

  // Installed & server state
  const [installed, setInstalled] = useState(null)
  const [starting, setStarting] = useState(true)
  const [startError, setStartError] = useState(null)
  const [previewPort, setPreviewPort] = useState(16890)

  // Project document state
  const [project, setProject] = useState(null)
  const [revision, setRevision] = useState(1)
  const [aspectRatio, setAspectRatio] = useState("9:16")
  const [document, setDocument] = useState(null)
  const [isDirty, setIsDirty] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isRendering, setIsRendering] = useState(false)
  const [conflictState, setConflictState] = useState(null)

  // Extract dialog state
  const [extractDialogOpen, setExtractDialogOpen] = useState(false)
  const [extractTarget, setExtractTarget] = useState(null)
  const [isExtracting, setIsExtracting] = useState(false)

  // Workspace exposure mode (Create / Review / Refine)
  const [workspaceMode, setWorkspaceMode] = useState("refine")
  const [activeContext, setActiveContext] = useState("hyperframes") // hyperframes | clip | tools
  const [leftNav, setLeftNav] = useState("layers") // layers | resources
  const [rightNav, setRightNav] = useState("properties") // properties | variables

  // Pinned panels control
  const [pinnedLeft, setPinnedLeft] = useState(true)
  const [pinnedRight, setPinnedRight] = useState(true)
  const [expandedPreview, setExpandedPreview] = useState(false)

  // Selection & playback
  const previewStageRef = useRef(null)
  const [selectedElement, setSelectedElement] = useState(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const handleUserSeek = useCallback((time) => {
    setCurrentTime(time)
    if (previewStageRef.current && previewStageRef.current.seek) {
      previewStageRef.current.seek(time)
    }
  }, [])

  // External data & active asset selection
  const [libraryVideos, setLibraryVideos] = useState([])
  const [trendItems, setTrendItems] = useState([])
  const [dataLoading, setDataLoading] = useState(false)
  const [selectedAsset, setSelectedAsset] = useState(null)

  const activeAsset = selectedAsset || libraryVideos[0] || null

  // Clip Studio hooks for contextual clip workspace with Project document persistence
  const clipSettings = useClipSettings()

  const handleCommitBenchRanges = useCallback((ranges) => {
    if (!activeAsset?.id) return
    setDocument((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        bench_ranges: {
          ...(prev.bench_ranges || {}),
          [activeAsset.id]: ranges,
        },
      }
    })
    setIsDirty(true)
  }, [activeAsset?.id])

  const benchRanges = useBenchRanges(
    activeAsset?.id || null,
    activeAsset?.duration_seconds || 0,
    document?.bench_ranges?.[activeAsset?.id] || null,
    handleCommitBenchRanges,
  )

  // Real-time synchronization via websocket
  useEffect(() => {
    const unsub = ws.on("project_updated", async (msg) => {
      if (project && msg.project_id === project.id) {
        if (msg.revision > revision) {
          // If user currently has unsaved local edits, PRESERVE THEM!
          // Advancing revision while document is old would let a subsequent save overwrite
          // the agent's work without detecting conflict.
          if (isDirty) {
            showSnackbar(
              `Agent updated project to rev ${msg.revision}. You have unsaved changes — save or reload to reconcile.`,
              "warning"
            )
            return
          }

          let nextDoc = msg.document
          if (!nextDoc) {
            try {
              const res = await http.get(`/api/projects/${project.id}`)
              nextDoc = res.data?.document
            } catch {
              // non-blocking
            }
          }

          if (nextDoc) {
            setRevision(msg.revision)
            setDocument(nextDoc)
            if (nextDoc.aspect_ratio) {
              setAspectRatio(nextDoc.aspect_ratio)
            }
            setIsDirty(false)
            showSnackbar(`Project updated to rev ${msg.revision} (${msg.summary || "synced"})`, "info")
          }
        }
      }
    })
    return () => unsub && unsub()
  }, [project, revision, isDirty, showSnackbar])

  // 1. Initial Load: Ensure HyperFrames server is running and load/create active project
  useEffect(() => {
    let cancelled = false
    const init = async () => {
      setStarting(true)
      try {
        // Start studio
        const studioRes = await http.post(`/api/generate/motion/studio/start?mode=${theme.palette.mode}`)
        if (cancelled) return
        if (studioRes.data?.error_code === "hyperframes_not_installed") {
          setInstalled(false)
          setStarting(false)
          return
        }
        setInstalled(true)
        if (studioRes.data?.port) setPreviewPort(studioRes.data.port)

        // Load requested project from URL query or recent project or create new one
        const queryParams = new URLSearchParams(window.location.search)
        const requestedId = queryParams.get("projectId") || queryParams.get("project_id")
        const projRes = await http.get("/api/projects")
        const existing = projRes.data?.projects || []
        const targetProj = (requestedId && existing.find(p => p.id === requestedId)) || (requestedId ? { id: requestedId } : existing[0])

        if (targetProj) {
          const detail = await http.get(`/api/projects/${targetProj.id}`)
          setProject(detail.data)
          setRevision(detail.data.revision)
          setAspectRatio(detail.data.aspect_ratio || "9:16")
          setDocument(detail.data.document)
        } else {
          const created = await http.post("/api/projects", {
            name: "Main Motion Project",
            aspect_ratio: "9:16",
          })
          setProject(created.data)
          setRevision(created.data.revision)
          setAspectRatio(created.data.aspect_ratio || "9:16")
          setDocument(created.data.document)
        }
      } catch (err) {
        if (!cancelled) setStartError(err.message)
      } finally {
        if (!cancelled) setStarting(false)
      }
    }

    init()
    return () => { cancelled = true }
  }, [theme.palette.mode])

  // 2. Load Assets and Trends
  useEffect(() => {
    const fetchData = async () => {
      setDataLoading(true)
      try {
        const [vids, trs] = await Promise.allSettled([
          http.get("/api/library/items"),
          http.get("/api/trends/results"),
        ])
        if (vids.status === "fulfilled") {
          const list = vids.value.data?.items || vids.value.data
          setLibraryVideos(Array.isArray(list) ? list : [])
        }
        if (trs.status === "fulfilled") {
          const list = trs.value.data?.results || trs.value.data
          setTrendItems(Array.isArray(list) ? list : [])
        }
      } catch {
        // non-blocking
      } finally {
        setDataLoading(false)
      }
    }
    fetchData()
  }, [])

  // 3. Save draft / apply operation
  const handleSave = async () => {
    if (!project || !document) return
    setIsSaving(true)
    try {
      // Apply full document update operation
      const res = await http.post(`/api/projects/${project.id}/operations`, {
        expected_revision: revision,
        operation_type: "update_document",
        payload: { document },
        author: "user",
      })
      setRevision(res.data.revision)
      setDocument(res.data.document)
      setIsDirty(false)

      // Sync to studio preview
      await http.post(`/api/projects/${project.id}/sync-studio`, { revision: res.data.revision })
      showSnackbar(`Saved revision ${res.data.revision}`, "success")
    } catch (err) {
      if (err.response?.status === 409) {
        showSnackbar("Conflict detected: project was modified concurrently.", "warning")
        try {
          const refreshed = await http.get(`/api/projects/${project.id}`)
          if (refreshed.data?.document && refreshed.data?.revision != null) {
            setConflictState({
              remoteRevision: refreshed.data.revision,
              remoteDocument: refreshed.data.document,
            })
          }
        } catch {
          showSnackbar("Unable to fetch latest remote project state. Please check connection and retry.", "error")
        }
      } else {
        showSnackbar(err.response?.data?.detail || err.message, "error")
      }
    } finally {
      setIsSaving(false)
    }
  }

  const handleResolveConflictOverwrite = async () => {
    if (!project || !document) return
    let targetRev = conflictState?.remoteRevision
    if (targetRev == null) {
      try {
        const refreshed = await http.get(`/api/projects/${project.id}`)
        if (refreshed.data?.revision != null) {
          targetRev = refreshed.data.revision
        } else {
          showSnackbar("Cannot overwrite: failed to retrieve remote revision.", "error")
          return
        }
      } catch {
        showSnackbar("Cannot overwrite: unable to contact server.", "error")
        return
      }
    }
    setIsSaving(true)
    try {
      const opType = conflictState?.pendingOp?.type || "update_document"
      const opPayload = conflictState?.pendingOp?.payload || { document }
      const res = await http.post(`/api/projects/${project.id}/operations`, {
        expected_revision: targetRev,
        operation_type: opType,
        payload: opPayload,
        author: "user",
      })
      setRevision(res.data.revision)
      setDocument(res.data.document)
      setIsDirty(false)
      setConflictState(null)
      await http.post(`/api/projects/${project.id}/sync-studio`, { revision: res.data.revision })
      showSnackbar(`Saved revision ${res.data.revision} (remote overwritten)`, "success")
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    } finally {
      setIsSaving(false)
    }
  }

  const handleResolveConflictDiscard = async () => {
    let targetDoc = conflictState?.remoteDocument
    let targetRev = conflictState?.remoteRevision

    if (!targetDoc || targetRev == null) {
      if (!project) return
      try {
        const refreshed = await http.get(`/api/projects/${project.id}`)
        if (refreshed.data?.document && refreshed.data?.revision != null) {
          targetDoc = refreshed.data.document
          targetRev = refreshed.data.revision
        } else {
          showSnackbar("Cannot discard: server did not return valid project state.", "error")
          return
        }
      } catch {
        showSnackbar("Cannot discard: failed to fetch remote project state. Please retry.", "error")
        return
      }
    }

    setDocument(targetDoc)
    setRevision(targetRev)
    setIsDirty(false)
    setConflictState(null)
    showSnackbar("Local draft discarded, updated to remote revision", "info")
  }

  const handleResolveConflictReconcile = async () => {
    if (!project || !document || !conflictState) return
    setIsSaving(true)
    try {
      const remoteDoc = conflictState.remoteDocument
      const remoteRev = conflictState.remoteRevision

      const mergedTracks = [...(remoteDoc?.timeline?.tracks || [])]
      const localTracks = document.timeline?.tracks || []

      for (const lt of localTracks) {
        const rt = mergedTracks.find((t) => t.id === lt.id)
        if (!rt) {
          mergedTracks.push(lt)
        } else {
          const existingIds = new Set((rt.clips || []).map((c) => c.id))
          for (const lc of (lt.clips || [])) {
            if (!existingIds.has(lc.id)) {
              rt.clips.push(lc)
            }
          }
        }
      }

      const reconciledDoc = {
        ...remoteDoc,
        aspect_ratio: document.aspect_ratio || remoteDoc.aspect_ratio,
        timeline: {
          ...(remoteDoc.timeline || {}),
          tracks: mergedTracks,
        },
      }

      const res = await http.post(`/api/projects/${project.id}/operations`, {
        expected_revision: remoteRev,
        operation_type: "update_document",
        payload: { document: reconciledDoc },
        author: "user",
      })
      setRevision(res.data.revision)
      setDocument(res.data.document)
      setIsDirty(false)
      setConflictState(null)
      await http.post(`/api/projects/${project.id}/sync-studio`, { revision: res.data.revision })
      showSnackbar(`Reconciled and saved revision ${res.data.revision}`, "success")
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    } finally {
      setIsSaving(false)
    }
  }

  const handleDismissConflict = () => {
    setConflictState(null)
  }

  // 4. Render Project
  const handleRender = async () => {
    if (!project) return
    setIsRendering(true)
    try {
      const res = await http.post(`/api/projects/${project.id}/render`, {
        revision,
        title: project.name,
      })
      showSnackbar(`Render dispatched! Job: ${res.data.job_id}`, "success")
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    } finally {
      setIsRendering(false)
    }
  }

  // 5. Add Media to Timeline via atomic operation
  const handleAddMedia = async (asset) => {
    if (!project || !document) return
    const tracks = document.timeline?.tracks || []
    const filename = (asset.filename || asset.title || "").toLowerCase()
    const isAudio = asset.media_type === "audio" || filename.endsWith(".mp3") || filename.endsWith(".wav") || filename.endsWith(".aac")
    const mType = isAudio ? "audio" : "video"

    let targetTrack = null
    if (isAudio) {
      targetTrack = tracks.find((t) => t.type === "audio")
      if (!targetTrack) {
        const addRes = await handleApplyOperation("add_track", { type: "audio", name: "Audio Track" })
        if (!addRes) return
        targetTrack = (addRes.document?.timeline?.tracks || []).find((t) => t.type === "audio")
      }
    } else {
      targetTrack = tracks.find((t) => t.type === "video") || tracks[0]
    }

    if (!targetTrack) return

    const currentClips = targetTrack.clips || []
    const lastClip = currentClips[currentClips.length - 1]
    const startSec = lastClip ? Number(lastClip.start_seconds || 0) + Number(lastClip.duration_seconds || 5) : 0

    const newClip = {
      id: `clip_${Date.now()}`,
      type: mType,
      asset_id: asset.id,
      asset_file: asset.filename || asset.title || (isAudio ? "audio.mp3" : "media.mp4"),
      title: asset.title || asset.filename || (isAudio ? "Audio Clip" : "Video Clip"),
      start_seconds: startSec,
      duration_seconds: asset.duration ? Math.min(asset.duration, 10) : 5,
    }

    const res = await handleApplyOperation("add_clip", { track_id: targetTrack.id, clip: newClip })
    if (res) {
      showSnackbar(`Added ${newClip.title} to ${targetTrack.name} (Rev ${res.revision})`, "success")
    }
  }

  const handleApplyOperation = async (operation_type, payload, targetRevision = null) => {
    if (!project) return null
    const revToUse = targetRevision != null ? targetRevision : revision
    try {
      const res = await http.post(`/api/projects/${project.id}/operations`, {
        expected_revision: revToUse,
        operation_type,
        payload,
        author: "user",
      })
      if (res.data?.revision != null && res.data?.document) {
        setRevision(res.data.revision)
        setDocument(res.data.document)
        setIsDirty(false)
        // Background sync to studio preview
        http.post(`/api/projects/${project.id}/sync-studio`, { revision: res.data.revision }).catch(() => {})
      }
      return res.data
    } catch (err) {
      if (err.response?.status === 409) {
        showSnackbar("Conflict detected: project was modified concurrently.", "warning")
        try {
          const refreshed = await http.get(`/api/projects/${project.id}`)
          if (refreshed.data?.document && refreshed.data?.revision != null) {
            setConflictState({
              remoteRevision: refreshed.data.revision,
              remoteDocument: refreshed.data.document,
              pendingOp: { type: operation_type, payload },
            })
          }
        } catch {
          // non-blocking
        }
      } else {
        showSnackbar(err.response?.data?.detail || err.message, "error")
      }
      return null
    }
  }

  // 5b. Add HyperFrames Catalog Block via atomic add_block operation
  const handleAddBlock = async (catalogItem) => {
    if (!project) return
    let currentRev = revision
    // If user has unsaved draft changes, flush them first so local edits survive
    if (isDirty && document) {
      try {
        const draftRes = await http.post(`/api/projects/${project.id}/operations`, {
          expected_revision: revision,
          operation_type: "update_document",
          payload: { document },
          author: "user",
        })
        currentRev = draftRes.data.revision
        setRevision(currentRev)
        setIsDirty(false)
      } catch (err) {
        if (err.response?.status === 409) {
          showSnackbar("Conflict detected: please resolve before inserting block.", "warning")
          try {
            const refreshed = await http.get(`/api/projects/${project.id}`)
            if (refreshed.data?.document && refreshed.data?.revision != null) {
              setConflictState({
                remoteRevision: refreshed.data.revision,
                remoteDocument: refreshed.data.document,
              })
            }
          } catch {}
          return
        }
      }
    }

    const defaultVars = {}
    if (Array.isArray(catalogItem.variables)) {
      catalogItem.variables.forEach((v) => {
        defaultVars[v.name] = v.default !== undefined ? v.default : ""
      })
    }
    const res = await handleApplyOperation("add_block", {
      block_id: catalogItem.name || catalogItem.id,
      variables: defaultVars,
      start_seconds: currentTime || 0.0,
      duration_seconds: catalogItem.duration_seconds || 3.0,
    }, currentRev)
    if (res) {
      showSnackbar(`Block "${catalogItem.title || catalogItem.name}" added to timeline (Rev ${res.revision})`, "success")
    }
  }

  // 6. Delete Clip via atomic operation
  const handleDeleteClip = async (clip) => {
    if (!project || !clip?.id) return
    if (selectedElement?.id === clip.id) setSelectedElement(null)
    const res = await handleApplyOperation("remove_clip", { clip_id: clip.id })
    if (res) {
      showSnackbar(`Removed clip from timeline (Rev ${res.revision})`, "info")
    }
  }

  // 7. Update element in inspector (local reactive state)
  const handleUpdateElement = (updatedElem) => {
    setSelectedElement(updatedElem)
    if (!document) return
    const tracks = (document.timeline?.tracks || []).map((t) => ({
      ...t,
      clips: (t.clips || []).map((c) => (c.id === updatedElem.id ? updatedElem : c)),
    }))
    setDocument({
      ...document,
      timeline: { ...document.timeline, tracks },
    })
    setIsDirty(true)
  }

  // 7b. Commit element property changes from Inspector to DB revision
  const handleCommitElement = async (updatedElem) => {
    if (!project || !updatedElem?.id) return
    if (updatedElem.type === "block" || updatedElem.block_id) {
      const res = await handleApplyOperation("update_block_variables", {
        clip_id: updatedElem.id,
        variables: updatedElem.variables || {},
        patch: {
          start_seconds: Number(updatedElem.start_seconds || 0),
          duration_seconds: Number(updatedElem.duration_seconds || 1),
        },
      })
      if (res) {
        showSnackbar(`Block variables persisted (Rev ${res.revision})`, "success")
      }
      return
    }
    const patch = {
      start_seconds: Number(updatedElem.start_seconds || 0),
      duration_seconds: Number(updatedElem.duration_seconds || 1),
    }
    if (updatedElem.caption_text !== undefined) patch.caption_text = updatedElem.caption_text
    const res = await handleApplyOperation("update_clip", {
      clip_id: updatedElem.id,
      patch,
    })
    if (res) {
      showSnackbar(`Properties persisted (Rev ${res.revision})`, "success")
    }
  }

  // 7c. Commit clip timing drag/trim from Timeline directly to DB revision
  const handleCommitClipTiming = async (clipId, timingPatch) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("update_clip_timing", {
      clip_id: clipId,
      ...timingPatch,
    })
    if (res) {
      showSnackbar(`Clip timing persisted (Rev ${res.revision})`, "success")
    }
  }

  // 7d. Duplicate clip
  const handleDuplicateClip = async (clip) => {
    if (!project || !clip?.id) return
    const res = await handleApplyOperation("duplicate_clip", { clip_id: clip.id })
    if (res) {
      showSnackbar(`Clip duplicated (Rev ${res.revision})`, "success")
    }
  }

  // 7e. Split clip at playhead
  const handleSplitClip = async (clip, splitTime) => {
    if (!project || !clip?.id) return
    const targetTime = splitTime != null ? splitTime : currentTime
    const res = await handleApplyOperation("split_clip", {
      clip_id: clip.id,
      split_time: targetTime,
    })
    if (res) {
      showSnackbar(`Clip split at ${Number(targetTime).toFixed(2)}s (Rev ${res.revision})`, "success")
    }
  }

  // 7f. Keyframe operations
  const handleAddKeyframe = async (clipId, keyframe) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("add_keyframe", { clip_id: clipId, keyframe })
    if (res) {
      showSnackbar(`Keyframe added (Rev ${res.revision})`, "success")
    }
  }

  const handleUpdateKeyframe = async (clipId, property, time, patch) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("update_keyframe", { clip_id: clipId, property, time, patch })
    if (res) {
      showSnackbar(`Keyframe updated (Rev ${res.revision})`, "success")
    }
  }

  const handleRemoveKeyframe = async (clipId, property, time) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("remove_keyframe", { clip_id: clipId, property, time })
    if (res) {
      showSnackbar(`Keyframe removed (Rev ${res.revision})`, "info")
    }
  }

  // 7g. Track state toggle
  const handleToggleTrackState = async (trackId, patch) => {
    if (!project || !trackId) return
    const res = await handleApplyOperation("update_track_state", { track_id: trackId, patch })
    if (res) {
      showSnackbar(`Track updated (Rev ${res.revision})`, "info")
    }
  }

  // 7g-2. Track CRUD operations
  const handleAddTrack = async (type, name) => {
    if (!project) return
    const res = await handleApplyOperation("add_track", { type, name })
    if (res) {
      showSnackbar(`Added ${type} track (Rev ${res.revision})`, "success")
    }
  }

  const handleDeleteTrack = async (trackId, force = false) => {
    if (!project || !trackId) return
    const res = await handleApplyOperation("delete_track", { track_id: trackId, force })
    if (res) {
      showSnackbar(`Track deleted (Rev ${res.revision})`, "info")
    }
  }

  const handleReorderTracks = async (trackIds) => {
    if (!project || !trackIds?.length) return
    const res = await handleApplyOperation("reorder_tracks", { track_ids: trackIds })
    if (res) {
      showSnackbar(`Tracks reordered (Rev ${res.revision})`, "info")
    }
  }

  const handleRenameTrack = async (trackId, name) => {
    if (!project || !trackId || !name) return
    const res = await handleApplyOperation("rename_track", { track_id: trackId, name })
    if (res) {
      showSnackbar(`Track renamed to "${name}" (Rev ${res.revision})`, "success")
    }
  }

  const handleMoveClip = async (clipId, newTrackId, startSeconds) => {
    if (!project || !clipId || !newTrackId) return
    const payload = { clip_id: clipId, new_track_id: newTrackId }
    if (startSeconds != null) payload.start_seconds = startSeconds
    const res = await handleApplyOperation("move_clip", payload)
    if (res) {
      showSnackbar(`Clip moved to track (Rev ${res.revision})`, "success")
    }
  }

  // 7h. Layer hierarchy & locking mutations
  const handleToggleVisibility = async (clipId, visible) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("set_element_visibility", { clip_id: clipId, visible })
    if (res) {
      showSnackbar(`Element ${visible ? "visible" : "hidden"} (Rev ${res.revision})`, "info")
    }
  }

  const handleToggleLock = async (clipId, locked) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("set_element_lock", { clip_id: clipId, locked })
    if (res) {
      showSnackbar(`Element ${locked ? "locked" : "unlocked"} (Rev ${res.revision})`, "info")
    }
  }

  const handleRenameElement = async (clipId, name) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("rename_element", { clip_id: clipId, name })
    if (res) {
      showSnackbar(`Element renamed to "${name}" (Rev ${res.revision})`, "success")
    }
  }

  const handleReorderLayer = async (clipId, layer_order, parent_id) => {
    if (!project || !clipId) return
    const payload = { clip_id: clipId, layer_order }
    if (parent_id !== undefined) payload.parent_id = parent_id
    const res = await handleApplyOperation("reorder_layer", payload)
    if (res) {
      showSnackbar(`Layer reordered (Rev ${res.revision})`, "info")
    }
  }

  const handleGroupElements = async (clipIds, groupName) => {
    if (!project || !clipIds?.length) return
    const res = await handleApplyOperation("group_elements", { clip_ids: clipIds, group_name: groupName || "New Group" })
    if (res) {
      showSnackbar(`Grouped ${clipIds.length} element(s) (Rev ${res.revision})`, "success")
    }
  }

  const handleUngroupElements = async (groupId) => {
    if (!project || !groupId) return
    const res = await handleApplyOperation("ungroup_elements", { group_id: groupId })
    if (res) {
      showSnackbar(`Ungrouped (Rev ${res.revision})`, "info")
    }
  }

  const handleUpdateVariables = (clipId, nextVars) => {
    if (!document || !clipId) return
    const updated = selectedElement && selectedElement.id === clipId ? { ...selectedElement, variables: nextVars } : selectedElement
    if (updated) setSelectedElement(updated)
    const tracks = (document.timeline?.tracks || []).map((t) => ({
      ...t,
      clips: (t.clips || []).map((c) => (c.id === clipId ? { ...c, variables: nextVars } : c)),
    }))
    setDocument({
      ...document,
      timeline: { ...document.timeline, tracks },
    })
    setIsDirty(true)
  }

  const handleCommitVariables = async (clipId, varPatch) => {
    if (!project || !clipId) return
    const res = await handleApplyOperation("update_block_variables", {
      clip_id: clipId,
      variables: varPatch,
    })
    if (res) {
      showSnackbar(`Variables committed (Rev ${res.revision})`, "success")
    }
  }

  const handleSelectElementId = useCallback((id) => {
    if (!document || !id) return
    let found = null
    for (const t of (document.timeline?.tracks || [])) {
      for (const c of (t.clips || [])) {
        if (c.id === id) {
          found = c
          break
        }
      }
      if (found) break
    }
    if (found) {
      setSelectedElement(found)
    }
  }, [document])

  // 8. Extract clips (Manual & Auto-cut)
  const handleExtract = async (videoId, opts) => {
    setIsExtracting(true)
    try {
      const isManual = opts.mode === "manual"
      const payload = { caption_style: opts.caption_style }
      if (opts.force_retranscribe) {
        payload.whisper_quality = opts.whisper_quality
        payload.force_retranscribe = true
      }
      if (opts.emoji_style && opts.emoji_style !== "moderate") payload.emoji_style = opts.emoji_style
      if (opts.remove_silence) payload.remove_silence = true
      if (opts.force_vertical) payload.force_vertical = true

      if (isManual) {
        payload.mode = "manual"
        payload.time_ranges = opts.time_ranges
      } else {
        if (opts.min_duration) payload.min_duration = opts.min_duration
        if (opts.max_duration) payload.max_duration = opts.max_duration
        if (opts.max_clips) payload.max_clips = opts.max_clips
        if (opts.user_query && opts.user_query.trim()) payload.user_query = opts.user_query.trim()
        if (opts.target_platform) payload.target_platform = opts.target_platform
        if (opts.genre) payload.genre = opts.genre
      }

      await http.post(`/api/downloaded/${videoId}/extract-clips`, payload)
      showSnackbar(
        isManual
          ? `Cutting ${opts.time_ranges?.length || ""} clip(s) from selected ranges.`
          : "Extracting viral clips with AI analysis...",
        "success"
      )
      const libRes = await http.get("/api/library/items")
      const list = libRes.data?.items || libRes.data
      if (Array.isArray(list)) setLibraryVideos(list)
      return true
    } catch (e) {
      showSnackbar(`Extract failed: ${e.response?.data?.detail || e.message}`, "error")
      return false
    } finally {
      setIsExtracting(false)
    }
  }

  const handleDoCut = async () => {
    if (!activeAsset || benchRanges.ranges.length === 0 || isExtracting) return
    const ok = await handleExtract(activeAsset.id, {
      ...clipSettings.toPayload({ hasTranscript: !!activeAsset.has_transcript_segments }),
      mode: "manual",
      time_ranges: benchRanges.ranges.map(({ start, end }) => ({ start, end })),
    })
    if (ok) {
      benchRanges.clear()
    }
  }

  // 9. Ingest Trend into Project
  const handleIngestTrend = async (trend) => {
    if (!project || !trend?.id) return
    showSnackbar(`Ingesting trend "${trend.title || trend.query}" into project...`, "info")
    try {
      const res = await http.post(`/api/projects/${project.id}/ingest-trend`, {
        trend_result_id: trend.id,
        expected_revision: revision,
      })
      if (res.data?.output) {
        setRevision(res.data.output.revision)
        const [projRes, libRes] = await Promise.all([
          http.get(`/api/projects/${project.id}`),
          http.get("/api/library/items"),
        ])
        if (projRes.data?.document) {
          setDocument(projRes.data.document)
        }
        const list = libRes.data?.items || libRes.data
        if (Array.isArray(list)) {
          setLibraryVideos(list)
          const dvId = res.data.output.downloaded_video_id
          const matched = list.find((item) => item.id === dvId || item.id === `dl:${dvId}`)
          if (matched) setSelectedAsset(matched)
        }
        showSnackbar(`Trend ingested into project (Rev ${res.data.output.revision})`, "success")
      }
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    }
  }

  // Canonical read-only composition preview URL from versioned project document
  const previewUrl = project ? `/api/projects/${project.id}/preview?revision=${revision}` : null

  if (installed === false) {
    return <MotionInstallGate />
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#f8fafc",
        overflow: "hidden",
      }}
    >
      {/* 1. Compact Top Toolbar */}
      <StudioToolbar
        project={project}
        revision={revision}
        aspectRatio={aspectRatio}
        onAspectChange={(asp) => {
          setAspectRatio(asp)
          if (document) {
            setDocument({ ...document, aspect_ratio: asp })
            setIsDirty(true)
          }
        }}
        workspaceMode={workspaceMode}
        onWorkspaceModeChange={setWorkspaceMode}
        isDirty={isDirty}
        isSaving={isSaving}
        onSave={handleSave}
        onRender={handleRender}
        isRendering={isRendering}
        activeContext={activeContext}
        onSelectContext={setActiveContext}
        pinnedLeft={pinnedLeft}
        onToggleLeft={() => setPinnedLeft(!pinnedLeft)}
        pinnedRight={pinnedRight}
        onToggleRight={() => setPinnedRight(!pinnedRight)}
        expandedPreview={expandedPreview}
        onToggleExpandedPreview={() => setExpandedPreview(!expandedPreview)}
      />

      {/* 2. Main Studio Body */}
      <Box sx={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>
        {/* Left: Collapsed Rail Indicator */}
        {(workspaceMode === "refine" || workspaceMode === "create") && !pinnedLeft && (
          <Box
            sx={{
              width: 24,
              height: "100%",
              bgcolor: "#ffffff",
              borderRight: "1px solid",
              borderColor: "divider",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              pt: 1,
              zIndex: 2,
            }}
          >
            <Tooltip title="Expand Left Panel" placement="right" arrow>
              <IconButton
                size="small"
                onClick={() => setPinnedLeft(true)}
                sx={{ width: 22, height: 22, color: "text.secondary" }}
              >
                <IconLayoutSidebarLeftExpand size={14} />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {/* Left: Layers or Sources / Assets / Catalog (Refine & Create modes) */}
        {(workspaceMode === "refine" || workspaceMode === "create") && pinnedLeft && (
          <Box sx={{ width: 280, minWidth: 260, maxWidth: 340, height: "100%", zIndex: 2, display: "flex", flexDirection: "column", bgcolor: "#ffffff", borderRight: "1px solid", borderColor: "divider" }}>
            {/* Left Nav Header Tabs: Layers vs Resources */}
            <Box sx={{ px: 1, py: 0.75, borderBottom: "1px solid", borderColor: "divider", bgcolor: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Stack direction="row" spacing={0.5}>
                <Button
                  size="small"
                  variant={leftNav === "layers" ? "contained" : "text"}
                  onClick={() => setLeftNav("layers")}
                  sx={{
                    py: 0.25,
                    px: 1.25,
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    borderRadius: 1.5,
                    minWidth: "auto",
                    bgcolor: leftNav === "layers" ? "primary.main" : "transparent",
                    color: leftNav === "layers" ? "#ffffff" : "text.secondary",
                  }}
                >
                  Layers
                </Button>
                <Button
                  size="small"
                  variant={leftNav === "resources" ? "contained" : "text"}
                  onClick={() => setLeftNav("resources")}
                  sx={{
                    py: 0.25,
                    px: 1.25,
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    borderRadius: 1.5,
                    minWidth: "auto",
                    bgcolor: leftNav === "resources" ? "primary.main" : "transparent",
                    color: leftNav === "resources" ? "#ffffff" : "text.secondary",
                  }}
                >
                  Catalog & Media
                </Button>
              </Stack>
            </Box>

            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
              {leftNav === "layers" ? (
                <StudioLayersPanel
                  tracks={document?.timeline?.tracks || []}
                  selectedElementId={selectedElement?.id}
                  onSelectElement={setSelectedElement}
                  onToggleVisibility={handleToggleVisibility}
                  onToggleLock={handleToggleLock}
                  onRenameElement={handleRenameElement}
                  onReorderLayer={handleReorderLayer}
                  onGroupElements={handleGroupElements}
                  onUngroupElements={handleUngroupElements}
                  onDuplicateClip={handleDuplicateClip}
                  onDeleteClip={handleDeleteClip}
                  onSeek={handleUserSeek}
                />
              ) : (
                <StudioResourcePanel
                  libraryVideos={libraryVideos}
                  trendItems={trendItems}
                  loading={dataLoading}
                  selectedAssetId={activeAsset?.id}
                  onSelectSource={(asset) => setSelectedAsset(asset)}
                  onAddMediaToTimeline={handleAddMedia}
                  onAddBlock={handleAddBlock}
                  onIngestTrend={handleIngestTrend}
                  isPinned={pinnedLeft}
                  onTogglePin={() => setPinnedLeft(!pinnedLeft)}
                />
              )}
            </Box>
          </Box>
        )}

        {/* Center: Stage & Contextual Workspace */}
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, height: "100%" }}>
          {/* Top: Central Video Preview Stage */}
          <Box sx={{ flex: workspaceMode === "refine" ? (expandedPreview ? "1 1 75%" : "1 1 55%") : "1 1 100%", minHeight: expandedPreview ? 460 : 360, display: "flex", flexDirection: "column" }}>
            <StudioPreviewStage
              ref={previewStageRef}
              previewUrl={previewUrl}
              aspectRatio={aspectRatio}
              isLoading={starting}
              currentTime={currentTime}
              duration={document?.timeline?.duration_seconds || 15}
              isPlaying={isPlaying}
              onTogglePlay={() => setIsPlaying(!isPlaying)}
              onPlaybackStateChange={setIsPlaying}
              onTimeUpdate={setCurrentTime}
              onSeek={handleUserSeek}
              onRefresh={() => window.location.reload()}
              onSelectElementId={handleSelectElementId}
            />
          </Box>

          {/* Bottom: Contextual Workspace (Refine Mode) */}
          {workspaceMode === "refine" && (
            <Box sx={{ flex: expandedPreview ? "0 0 160px" : "1 1 45%", minHeight: expandedPreview ? 140 : 220, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              {activeContext === "hyperframes" && (
                <StudioTimelineWorkspace
                  tracks={document?.timeline?.tracks || []}
                  currentTime={currentTime}
                  duration={document?.timeline?.duration_seconds || 15}
                  fps={document?.timeline?.fps || 30}
                  isPlaying={isPlaying}
                  onTogglePlay={() => setIsPlaying(!isPlaying)}
                  onSeek={handleUserSeek}
                  selectedElementId={selectedElement?.id}
                  onSelectElement={setSelectedElement}
                  onDeleteClip={handleDeleteClip}
                  onUpdateClipTiming={handleCommitClipTiming}
                  onDuplicateClip={handleDuplicateClip}
                  onSplitClip={handleSplitClip}
                  onAddKeyframe={handleAddKeyframe}
                  onUpdateKeyframe={handleUpdateKeyframe}
                  onRemoveKeyframe={handleRemoveKeyframe}
                  onToggleTrackState={handleToggleTrackState}
                  onAddTrack={handleAddTrack}
                  onDeleteTrack={handleDeleteTrack}
                  onReorderTracks={handleReorderTracks}
                  onRenameTrack={handleRenameTrack}
                  onMoveClip={handleMoveClip}
                />
              )}

              {activeContext === "clip" && (
                <Box sx={{ height: "100%", display: "flex", flexDirection: "column", bgcolor: "#ffffff", borderTop: "1px solid", borderColor: "divider" }}>
                  {benchRanges.ranges.length > 0 && (
                    <Box sx={{ px: 2, py: 0.75, bgcolor: "#f8fafc", borderBottom: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>
                        {benchRanges.ranges.length} range(s) marked for extraction
                      </Typography>
                      <Button
                        size="small"
                        variant="contained"
                        disabled={isExtracting}
                        onClick={handleDoCut}
                        sx={{
                          py: 0.25,
                          px: 1.5,
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          bgcolor: "primary.main",
                          borderRadius: 1.5,
                        }}
                      >
                        {isExtracting ? <CircularProgress size={14} sx={{ color: "#ffffff", mr: 1 }} /> : null}
                        Cut {benchRanges.ranges.length} clip{benchRanges.ranges.length !== 1 ? "s" : ""}
                      </Button>
                    </Box>
                  )}
                  <Box sx={{ flex: 1, minHeight: 0 }}>
                    <SourceBench
                      source={activeAsset}
                      ranges={benchRanges}
                      settings={clipSettings.settings}
                      onSettings={clipSettings.update}
                      existingClips={[]}
                      onOpenDialog={() => {
                        setExtractTarget(activeAsset)
                        setExtractDialogOpen(true)
                      }}
                    />
                  </Box>
                </Box>
              )}

              {activeContext === "tools" && (
                <StudioToolsWorkspace
                  activeAsset={activeAsset}
                  onToolSuccess={() => showSnackbar("Tool executed successfully", "success")}
                />
              )}

              {activeContext === "code" && (
                <StudioCodeWorkspace
                  project={project}
                  revision={revision}
                  codeFiles={document?.code?.files || []}
                  selectedElement={selectedElement}
                  onApplyOperation={handleApplyOperation}
                  onDirtyChange={setIsDirty}
                  onFileSaved={async (savedFile, newRev) => {
                    showSnackbar(`File "${savedFile.path}" persisted (Rev ${newRev})`, "success")
                  }}
                />
              )}
            </Box>
          )}
        </Box>

        {/* Right: Properties / Variables Inspector (Refine & Review modes) */}
        {(workspaceMode === "refine" || workspaceMode === "review") && pinnedRight && (
          <Box sx={{ width: 280, minWidth: 260, maxWidth: 340, height: "100%", zIndex: 2, display: "flex", flexDirection: "column", bgcolor: "#ffffff", borderLeft: "1px solid", borderColor: "divider" }}>
            {/* Right Nav Header Tabs: Properties vs Variables */}
            <Box sx={{ px: 1, py: 0.75, borderBottom: "1px solid", borderColor: "divider", bgcolor: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Stack direction="row" spacing={0.5}>
                <Button
                  size="small"
                  variant={rightNav === "properties" ? "contained" : "text"}
                  onClick={() => setRightNav("properties")}
                  sx={{
                    py: 0.25,
                    px: 1.25,
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    borderRadius: 1.5,
                    minWidth: "auto",
                    bgcolor: rightNav === "properties" ? "primary.main" : "transparent",
                    color: rightNav === "properties" ? "#ffffff" : "text.secondary",
                  }}
                >
                  Properties
                </Button>
                <Button
                  size="small"
                  variant={rightNav === "variables" ? "contained" : "text"}
                  onClick={() => setRightNav("variables")}
                  sx={{
                    py: 0.25,
                    px: 1.25,
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    borderRadius: 1.5,
                    minWidth: "auto",
                    bgcolor: rightNav === "variables" ? "primary.main" : "transparent",
                    color: rightNav === "variables" ? "#ffffff" : "text.secondary",
                  }}
                >
                  Variables
                </Button>
              </Stack>
            </Box>

            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
              {rightNav === "properties" ? (
                <StudioInspectorPanel
                  selectedElement={selectedElement}
                  onUpdateElement={handleUpdateElement}
                  onCommitElement={handleCommitElement}
                  tracks={document?.timeline?.tracks || []}
                  isPinned={pinnedRight}
                  onTogglePin={() => setPinnedRight(!pinnedRight)}
                />
              ) : (
                <StudioVariablesPanel
                  selectedElement={selectedElement}
                  onUpdateVariables={handleUpdateVariables}
                  onCommitVariables={handleCommitVariables}
                  isLocked={selectedElement?.locked}
                />
              )}
            </Box>
          </Box>
        )}

        {/* Right: Collapsed Rail Indicator */}
        {(workspaceMode === "refine" || workspaceMode === "review") && !pinnedRight && (
          <Box
            sx={{
              width: 24,
              height: "100%",
              bgcolor: "#ffffff",
              borderLeft: "1px solid",
              borderColor: "divider",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              pt: 1,
              zIndex: 2,
            }}
          >
            <Tooltip title="Expand Inspector" placement="left" arrow>
              <IconButton
                size="small"
                onClick={() => setPinnedRight(true)}
                sx={{ width: 22, height: 22, color: "text.secondary" }}
              >
                <IconLayoutSidebarRightExpand size={14} />
              </IconButton>
            </Tooltip>
          </Box>
        )}
      </Box>

      {/* Conflict Reconciliation Dialog */}
      {conflictState && (
        <Dialog open={!!conflictState} onClose={handleDismissConflict} maxWidth="sm" fullWidth data-testid="conflict-dialog">
          <DialogTitle>Concurrent Modification Conflict</DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ mb: 2 }} data-testid="conflict-dialog-text">
              Another process or user saved revision {conflictState.remoteRevision} while you were editing revision {revision}.
              Your local draft changes have been preserved. What would you like to do?
            </DialogContentText>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={handleDismissConflict} color="inherit" data-testid="conflict-dismiss-btn">
              Keep Editing Locally
            </Button>
            <Button onClick={handleResolveConflictDiscard} color="error" variant="outlined" data-testid="conflict-discard-btn">
              Discard My Changes
            </Button>
            <Button onClick={handleResolveConflictReconcile} color="secondary" variant="outlined" data-testid="conflict-reconcile-btn">
              Reconcile (Merge)
            </Button>
            <Button onClick={handleResolveConflictOverwrite} color="primary" variant="contained" data-testid="conflict-overwrite-btn">
              Overwrite Remote
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* Extract Clips Dialog */}
      <ExtractDialog
        open={extractDialogOpen}
        onClose={() => setExtractDialogOpen(false)}
        video={extractTarget}
        onExtract={handleExtract}
        sharedSettings={clipSettings.settings}
        onSharedSettings={clipSettings.update}
      />
    </Box>
  )
}
