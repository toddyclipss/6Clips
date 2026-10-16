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
import StudioToolsInspector from "../components/motion/StudioToolsInspector"
import StudioLayersPanel from "../components/motion/StudioLayersPanel"
import StudioVariablesPanel from "../components/motion/StudioVariablesPanel"
import StudioCodeWorkspace from "../components/motion/StudioCodeWorkspace"
import MotionInstallGate from "../components/MotionInstallGate"
import MotionReviewPanel from "../components/motion/MotionReviewPanel"
import { normalizeProjectForPlayer } from "../utils/nativeMotionAdapter"
import { inspectLegacyProjectBlocks, DONOR_INTERNALIZED_IDS, SHIPPED_OPERATIONAL_IDS } from "../utils/catalogOriginals"

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
  const [isProjectLoading, setIsProjectLoading] = useState(false)
  const [projectError, setProjectError] = useState(null)
  const [revision, setRevision] = useState(1)
  const [aspectRatio, setAspectRatio] = useState("9:16")
  const [document, setDocument] = useState(null)
  const [isDirty, setIsDirty] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isRendering, setIsRendering] = useState(false)
  const [conflictState, setConflictState] = useState(null)
  const [undoStack, setUndoStack] = useState([])
  const [redoStack, setRedoStack] = useState([])
  const lastCommittedDocumentRef = useRef(null)
  const handledDeepLinkAssetRef = useRef(null)
  const handledDeepLinkBlockRef = useRef(null)

  // Active background jobs from appStore
  const activeJobs = useAppStore((s) => s.activeJobs)

  // Advanced Editing unobtrusive toggle (technical timeline & manual controls)
  const [advancedEditing, setAdvancedEditing] = useState(() => {
    const qp = new URLSearchParams(window.location.search)
    const m = qp.get("mode")?.toLowerCase()
    const adv = qp.get("advanced")?.toLowerCase()
    return m === "refine" || adv === "true" || adv === "1"
  })

  // Workspace exposure mode: Create and Review only
  const [workspaceMode, setWorkspaceMode] = useState(() => {
    const qp = new URLSearchParams(window.location.search)
    const m = qp.get("mode")?.toLowerCase()
    if (m === "review") return "review"
    if (qp.get("review") || qp.get("jobId") || qp.get("job_id")) return "review"
    return "create"
  })

  const activeJob = useMemo(() => {
    const list = Object.values(activeJobs || {})
    if (project?.id) {
      const found = list.find((j) => j.projectId === project.id || j.project_id === project.id)
      if (found) return found
    }
    const qp = new URLSearchParams(window.location.search)
    const qJobId = qp.get("jobId") || qp.get("job_id")
    if (qJobId && activeJobs[qJobId]) return activeJobs[qJobId]
    return list.find((j) => j.status === "running") || null
  }, [activeJobs, project?.id])
  const [renderedVideo, setRenderedVideo] = useState(null)
  const [productionBatch, setProductionBatch] = useState(null)
  const [selectedOutputIndex, setSelectedOutputIndex] = useState(0)
  const [approvedOutputs, setApprovedOutputs] = useState(() => new Set())
  const [reviewNotes, setReviewNotes] = useState({})

  const handleReviewNotesChange = useCallback((outputId, notesText) => {
    setReviewNotes((prev) => ({ ...prev, [outputId]: notesText }))
  }, [])

  const reviewOutputs = useMemo(() => {
    if (productionBatch?.outputs?.length) return productionBatch.outputs
    if (renderedVideo?.outputs?.length) return renderedVideo.outputs
    if (renderedVideo?.video_url || renderedVideo?.preview_ref) return [renderedVideo]
    return []
  }, [productionBatch, renderedVideo])

  const activeReviewOutput = reviewOutputs[selectedOutputIndex] || reviewOutputs[0] || renderedVideo
  const [activeContext, setActiveContext] = useState(() => {
    const qp = new URLSearchParams(window.location.search)
    const m = qp.get("mode")?.toLowerCase()
    if (m && ["clip", "tools", "code", "hyperframes"].includes(m)) {
      return m
    }
    const t = qp.get("tab")?.toLowerCase()
    if (t && ["clip", "tools", "code", "hyperframes"].includes(t)) {
      return t
    }
    return "hyperframes"
  }) // hyperframes | clip | tools | code
  const [leftNav, setLeftNav] = useState(() => {
    const qp = new URLSearchParams(window.location.search)
    const tab = qp.get("tab")?.toLowerCase()
    if (tab === "catalog") return "resources"
    const m = qp.get("mode")?.toLowerCase()
    if (m === "clip" || m === "tools") return "resources"
    return m === "refine" ? "layers" : "resources"
  })
  const [rightNav, setRightNav] = useState("properties") // properties | variables

  // Pinned panels control
  const [pinnedLeft, setPinnedLeft] = useState(() => {
    const qp = new URLSearchParams(window.location.search)
    if (qp.get("tab") === "catalog") return true
    return true
  })
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
  const [dataLoading, setDataLoading] = useState(false)
  const [libraryVideos, setLibraryVideos] = useState([])
  const [trendItems, setTrendItems] = useState([])
  const [selectedAsset, setSelectedAsset] = useState(null)
  const activeAsset = selectedAsset || null

  // Diagnostic report for legacy 6Clips blocks requiring migration
  const legacyReport = useMemo(() => {
    return inspectLegacyProjectBlocks(document)
  }, [document])

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

    const unsubRun = ws.on("agent_run_completed", async (msg) => {
      if (project && (!msg.project_id || msg.project_id === project.id)) {
        try {
          const detail = await http.get(`/api/projects/${project.id}`)
          const doc = detail.data?.document
          const totalClips = (doc?.timeline?.tracks || []).reduce((acc, t) => acc + (t.clips || []).length, 0)
          if (totalClips > 0) {
            setWorkspaceMode("review")
            showSnackbar("Agent finished execution — switched to Review mode", "success")
          }
        } catch {
          // non-blocking
        }
      }
    })
    return () => {
      unsub && unsub()
      unsubRun && unsubRun()
    }
  }, [project, revision, isDirty, showSnackbar])

  // Synchronize workspaceMode changes with URL query string
  const handleWorkspaceModeChange = useCallback((mode) => {
    const validMode = mode === "review" ? "review" : "create"
    setWorkspaceMode(validMode)
    try {
      const url = new URL(window.location.href)
      url.searchParams.set("mode", validMode)
      window.history.replaceState({}, "", url.toString())
    } catch {}
  }, [])

  const handleToggleAdvancedEditing = useCallback(() => {
    setAdvancedEditing((prev) => {
      const next = !prev
      try {
        const url = new URL(window.location.href)
        if (next) {
          url.searchParams.set("advanced", "1")
        } else {
          url.searchParams.delete("advanced")
          if (url.searchParams.get("mode") === "refine") {
            url.searchParams.set("mode", "review")
          }
        }
        window.history.replaceState({}, "", url.toString())
      } catch {}
      return next
    })
  }, [])

  // 1a. Immediate Project Load from URL query (independent of studio startup)
  useEffect(() => {
    let cancelled = false
    const queryParams = new URLSearchParams(window.location.search)
    const requestedId = queryParams.get("projectId") || queryParams.get("project_id")
    const requestedMode = queryParams.get("mode")?.toLowerCase()
    const requestedTab = queryParams.get("tab")?.toLowerCase()
    const requestedAdv = queryParams.get("advanced")?.toLowerCase()

    if (requestedMode === "review" || queryParams.get("review") || queryParams.get("jobId") || queryParams.get("job_id")) {
      setWorkspaceMode("review")
    } else {
      setWorkspaceMode("create")
    }

    if (requestedMode === "refine" || requestedTab === "refine" || requestedAdv === "1" || requestedAdv === "true") {
      setAdvancedEditing(true)
      setLeftNav("layers")
    }

    if (!requestedId) {
      setProject(null)
      setDocument(null)
      setRenderedVideo(null)
      setIsProjectLoading(false)
      setProjectError(null)
      return
    }

    const loadProject = async () => {
      setIsProjectLoading(true)
      setProjectError(null)
      try {
        const detail = await http.get(`/api/projects/${requestedId}`)
        if (cancelled) return
        const norm = normalizeProjectForPlayer(detail.data)
        setProject(detail.data)
        setRevision(detail.data.revision)
        setAspectRatio(detail.data.aspect_ratio || norm.aspectRatio || "9:16")
        setDocument(norm.tracks?.length ? { ...detail.data.document, timeline: { tracks: norm.tracks, duration_seconds: norm.duration, fps: norm.fps } } : detail.data.document)
        lastCommittedDocumentRef.current = detail.data.document
        setUndoStack([])
        setRedoStack([])
        if (detail.data.latest_render) {
          setRenderedVideo(detail.data.latest_render)
        }
      } catch (fetchErr) {
        if (!cancelled) {
          console.warn(`Requested project ${requestedId} not found`, fetchErr)
          setProject(null)
          setDocument(null)
          lastCommittedDocumentRef.current = null
          setUndoStack([])
          setRedoStack([])
          setRenderedVideo(null)
          setProjectError(fetchErr.response?.data?.detail || fetchErr.message || `Project "${requestedId}" not found`)
          showSnackbar(`Requested project "${requestedId}" not found`, "warning")
        }
      } finally {
        if (!cancelled) {
          setIsProjectLoading(false)
        }
      }
    }

    loadProject()
    return () => { cancelled = true }
  }, [showSnackbar])

  // Undo / Redo / Cancel Handlers
  const pushUndo = useCallback((prevDoc) => {
    if (!prevDoc) return
    setUndoStack((prev) => [...prev.slice(-30), prevDoc])
    setRedoStack([])
  }, [])

  const handleUndo = useCallback(() => {
    if (undoStack.length === 0) return
    const prevDoc = undoStack[undoStack.length - 1]
    setUndoStack((prev) => prev.slice(0, prev.length - 1))
    setRedoStack((prev) => [...prev, document])
    setDocument(prevDoc)
    setIsDirty(true)
    showSnackbar("Undone last edit", "info")
  }, [undoStack, document, showSnackbar])

  const handleRedo = useCallback(() => {
    if (redoStack.length === 0) return
    const nextDoc = redoStack[redoStack.length - 1]
    setRedoStack((prev) => prev.slice(0, prev.length - 1))
    setUndoStack((prev) => [...prev, document])
    setDocument(nextDoc)
    setIsDirty(true)
    showSnackbar("Redone edit", "info")
  }, [redoStack, document, showSnackbar])

  const handleCancelDraft = useCallback(() => {
    if (lastCommittedDocumentRef.current) {
      setDocument(lastCommittedDocumentRef.current)
      setIsDirty(false)
      setUndoStack([])
      setRedoStack([])
      showSnackbar("Draft changes discarded, reverted to committed revision", "info")
    } else {
      setIsDirty(false)
    }
  }, [showSnackbar])

  const handleNewProject = useCallback(async () => {
    try {
      const res = await http.post("/api/projects", {
        name: `Motion Project ${new Date().toISOString().slice(11, 19)}`,
        aspect_ratio: aspectRatio || "9:16",
      })
      if (res.data?.id) {
        setProject(res.data)
        setRevision(res.data.revision || 1)
        setDocument(res.data.document)
        lastCommittedDocumentRef.current = res.data.document
        setUndoStack([])
        setRedoStack([])
        setIsDirty(false)
        showSnackbar(`Created project "${res.data.name}"`, "success")
        try {
          const url = new URL(window.location.href)
          url.searchParams.set("projectId", res.data.id)
          window.history.replaceState({}, "", url.toString())
        } catch {}
      }
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    }
  }, [aspectRatio, showSnackbar])


  // Global Undo/Redo keyboard shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e) => {
      const tag = e.target?.tagName?.toLowerCase()
      if (tag === "input" || tag === "textarea" || e.target?.isContentEditable) return

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault()
        if (e.shiftKey) {
          handleRedo()
        } else {
          handleUndo()
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault()
        handleRedo()
      }
    }
    window.addEventListener("keydown", handleGlobalKeyDown)
    return () => window.removeEventListener("keydown", handleGlobalKeyDown)
  }, [handleUndo, handleRedo])

  // 1a-2. Batch report load from URL query
  useEffect(() => {
    let cancelled = false
    const qp = new URLSearchParams(window.location.search)
    const jId = qp.get("jobId") || qp.get("job_id")
    if (jId) {
      http.get(`/api/media/production/batch/${jId}`)
        .then((res) => {
          if (!cancelled && res.data) {
            setProductionBatch(res.data)
            if (res.data.outputs?.length > 0) {
              setWorkspaceMode("review")
            }
          }
        })
        .catch(() => {})
    }
    return () => { cancelled = true }
  }, [])

  const handleSelectOutput = useCallback((index) => {
    setSelectedOutputIndex(index)
  }, [])

  const handleApproveOutput = useCallback((outputId) => {
    setApprovedOutputs((prev) => {
      const next = new Set(prev)
      if (next.has(outputId)) {
        next.delete(outputId)
        showSnackbar(`Output "${outputId}" reverted to awaiting review`, "info")
      } else {
        next.add(outputId)
        showSnackbar(`Output "${outputId}" creatively approved`, "success")
      }
      return next
    })
  }, [showSnackbar])

  const handleExportOutput = useCallback((output) => {
    if (!output) return
    const url = output.preview_ref || output.video_url
    if (url) {
      const link = document.createElement("a")
      link.href = url
      link.download = `${output.output_id || "clip"}.mp4`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      showSnackbar(`Exporting ${output.output_id || "clip"}.mp4...`, "success")
    } else {
      showSnackbar("Output artifact is not yet available for export", "warning")
    }
  }, [showSnackbar])

  const handleRefineOutput = useCallback(async (output) => {
    if (!output) return
    if (output.project_revision_id && project?.id) {
      try {
        const revDetail = await http.get(`/api/projects/${project.id}/revisions/${output.project_revision_id}`)
        if (revDetail.data?.document) {
          setDocument(revDetail.data.document)
          setRevision(Number(output.project_revision_id))
        }
      } catch {
        // Fallback: keep current document
      }
    }
    setAdvancedEditing(true)
    setLeftNav("layers")
    showSnackbar(`Opened ${output.output_id || "output"} in Advanced Editing`, "info")
  }, [project, showSnackbar])

  // 1b. Ensure HyperFrames studio is running
  useEffect(() => {
    let cancelled = false
    const initStudio = async () => {
      setStarting(true)
      try {
        const studioRes = await http.post(`/api/generate/motion/studio/start?mode=${theme.palette.mode}`)
        if (cancelled) return
        if (studioRes.data?.error_code === "hyperframes_not_installed") {
          setInstalled(false)
          setStarting(false)
          return
        }
        setInstalled(true)
        if (studioRes.data?.port) setPreviewPort(studioRes.data.port)
      } catch (err) {
        if (!cancelled) setStartError(err.message)
      } finally {
        if (!cancelled) setStarting(false)
      }
    }

    initStudio()
    return () => { cancelled = true }
  }, [theme.palette.mode])

  // 2. Load Assets and Trends
  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()
    const fetchData = async () => {
      setDataLoading(true)
      try {
        const [vids, trs] = await Promise.allSettled([
          http.get("/api/library/items", { signal: controller.signal }),
          http.get("/api/trends/results", { signal: controller.signal }),
        ])
        if (cancelled) return
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
        if (!cancelled) {
          setDataLoading(false)
        }
      }
    }
    fetchData()
    return () => {
      cancelled = true
      controller.abort()
    }
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
      lastCommittedDocumentRef.current = res.data.document
      setUndoStack([])
      setRedoStack([])
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
    const filename = (asset.filename || asset.title || asset.id || "").toLowerCase()
    const isAudio = asset.media === "audio" || asset.media_type === "audio" || filename.endsWith(".mp3") || filename.endsWith(".wav") || filename.endsWith(".aac") || filename.endsWith(".ogg") || filename.endsWith(".m4a")
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

    const resolvedAssetId = asset.key || asset.id
    const resolvedAssetFile = asset.filename || (asset.id && asset.id.includes(".") ? asset.id : (isAudio ? `${asset.title || "audio"}.${asset.ext || "mp3"}` : asset.id ? `${asset.id}.mp4` : null))

    const newClip = {
      id: `clip_${Date.now()}`,
      type: mType,
      asset_id: resolvedAssetId,
      asset_file: resolvedAssetFile,
      title: asset.title || asset.filename || (isAudio ? "Audio Clip" : "Video Clip"),
      start_seconds: startSec,
      duration_seconds: asset.duration_seconds ? Math.min(asset.duration_seconds, 10) : (asset.duration ? Math.min(asset.duration, 10) : 5),
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
        lastCommittedDocumentRef.current = res.data.document
        setUndoStack([])
        setRedoStack([])
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

  // 5c. Handle Native Drag & Drop from Resources to Timeline
  const handleDropExternalClip = async ({ item, targetTrackId, startSeconds }) => {
    if (!project) return
    const tracks = project.document?.timeline?.tracks || []
    let targetTrack = tracks.find((t) => t.id === targetTrackId)
    if (targetTrack?.locked) {
      showSnackbar(`Track "${targetTrack.name || targetTrackId}" is locked.`, "error")
      return
    }
    const kind = item.kind || (item.block_id || item.variables || item.type === "block" ? "catalog" : "asset")
    const startSec = Math.max(0, Number(startSeconds || 0))

    if (kind === "catalog" || item.type === "block") {
      const blockData = item.data || item.item || item
      const category = (blockData?.category || item?.category || "").toLowerCase()
      const tags = Array.isArray(blockData?.tags) ? blockData.tags.map((t) => String(t).toLowerCase()) : []
      const isCaptionBlock = category === "text-captions" || category === "captions" || category === "typography" || tags.includes("captions") || tags.includes("caption-style") || tags.includes("typography")
      const isAudioBlock = category === "audio" || category === "music" || tags.includes("audio") || tags.includes("music")
      const isTransitionBlock = category === "transitions" || tags.includes("transition") || tags.includes("transitions")

      const destType = (targetTrack?.type || "video").toLowerCase()

      if (isCaptionBlock && destType !== "captions" && destType !== "text") {
        showSnackbar(`Incompatible track: Caption block "${blockData.title || blockData.name}" can only be dropped on a text/captions track.`, "error")
        return
      }
      if (isAudioBlock && destType !== "audio") {
        showSnackbar(`Incompatible track: Audio block "${blockData.title || blockData.name}" can only be dropped on an audio track.`, "error")
        return
      }
      if (isTransitionBlock && destType !== "transition" && destType !== "transitions") {
        showSnackbar(`Incompatible track: Transition block "${blockData.title || blockData.name}" can only be dropped on a transition track.`, "error")
        return
      }
      if (!isCaptionBlock && !isAudioBlock && !isTransitionBlock && (destType === "audio" || destType === "captions" || destType === "text")) {
        showSnackbar(`Incompatible track: Visual block "${blockData.title || blockData.name}" can only be dropped on a media/video track.`, "error")
        return
      }

      const defaultVars = {}
      if (Array.isArray(blockData.variables)) {
        blockData.variables.forEach((v) => {
          defaultVars[v.name] = v.default !== undefined ? v.default : ""
        })
      }
      const res = await handleApplyOperation("add_block", {
        block_id: blockData.name || blockData.id,
        track_id: targetTrackId,
        variables: defaultVars,
        start_seconds: startSec,
        duration_seconds: Number(blockData.duration_seconds || 3.0),
      })
      if (res) {
        showSnackbar(`Block "${blockData.title || blockData.name}" placed at ${startSec.toFixed(2)}s (Rev ${res.revision})`, "success")
      }
    } else if (kind === "source") {
      const trend = item.data || item
      const res = await handleApplyOperation("add_clip", {
        track_id: targetTrackId,
        clip: {
          id: `clip_${Date.now()}`,
          type: "video",
          asset_id: `trend:${trend.id || trend.query || "source"}`,
          asset_file: trend.video_url || "source.mp4",
          title: trend.title || trend.query || "Trend Source",
          start_seconds: startSec,
          duration_seconds: 5.0,
        },
      })
      if (res) {
        showSnackbar(`Source "${trend.title || "Trend"}" placed at ${startSec.toFixed(2)}s (Rev ${res.revision})`, "success")
      }
    } else {
      // Asset / MotionAssetIntent
      const asset = item.data || item

      // 1. Rights / permitted uses policy check
      const permitted = Array.isArray(item.permitted_uses)
        ? item.permitted_uses
        : Array.isArray(asset.permitted_uses)
        ? asset.permitted_uses
        : ["timeline_motion"]

      if (!permitted.includes("timeline_motion")) {
        showSnackbar("Asset rights policy forbids timeline_motion use.", "error")
        return
      }

      // 2. Asset ID shape check
      const resolvedAssetId = item.asset_id || item.key || asset.key || asset.id
      if (!resolvedAssetId) {
        showSnackbar("Malformed asset drop payload: missing asset ID or key.", "error")
        return
      }

      const rawMediaType = (item.media_type || item.mediaType || asset.media || asset.media_type || "").toLowerCase()
      const isAudio = rawMediaType === "audio" || (asset.ext && ["mp3", "wav", "aac", "ogg"].includes(asset.ext.toLowerCase())) || asset.source === "music"
      const isImage = rawMediaType === "image" || (asset.ext && ["png", "jpg", "jpeg", "webp", "gif"].includes(asset.ext.toLowerCase()))
      const mType = isAudio ? "audio" : isImage ? "image" : "video"

      // 3. Auto-route to compatible track if needed
      let effectiveTrackId = targetTrackId
      if (isAudio && targetTrack && targetTrack.type !== "audio") {
        const audioTrack = tracks.find((t) => t.type === "audio")
        if (audioTrack) {
          effectiveTrackId = audioTrack.id
        } else {
          const addRes = await handleApplyOperation("add_track", { type: "audio", name: "Audio Track" })
          if (addRes) {
            effectiveTrackId = (addRes.document?.timeline?.tracks || []).find((t) => t.type === "audio")?.id
          }
        }
      } else if (!isAudio && targetTrack && targetTrack.type === "audio") {
        const videoTrack = tracks.find((t) => t.type === "video") || tracks[0]
        if (videoTrack) effectiveTrackId = videoTrack.id
      }

      const resolvedAssetFile = item.asset_file || asset.filename || (String(resolvedAssetId).includes(".") ? resolvedAssetId : (isAudio ? `${asset.title || "audio"}.${asset.ext || "mp3"}` : isImage ? `${resolvedAssetId}.png` : `${resolvedAssetId}.mp4`))

      const newClip = {
        id: `clip_${Date.now()}`,
        type: mType,
        asset_id: resolvedAssetId,
        asset_file: resolvedAssetFile,
        stream_url: item.stream_url || asset.stream_url || null,
        title: item.title || asset.title || asset.filename || (isAudio ? "Audio Clip" : isImage ? "Image Clip" : "Video Clip"),
        start_seconds: startSec,
        duration_seconds: item.duration_seconds
          ? Math.min(item.duration_seconds, 60)
          : (asset.duration_seconds ? Math.min(asset.duration_seconds, 60) : (asset.duration ? Math.min(asset.duration, 60) : (isImage ? 3 : 5))),
        source_provenance: item.source_provenance || asset.source_provenance || "library_user_asset",
        permitted_uses: permitted,
        file_sha256: item.file_sha256 || asset.file_sha256 || asset.sha256 || null,
      }

      const res = await handleApplyOperation("add_clip", {
        track_id: effectiveTrackId,
        clip: newClip,
      })
      if (res) {
        showSnackbar(`Added ${newClip.title} at ${startSec.toFixed(2)}s (Rev ${res.revision})`, "success")
      }
    }
  }

  const handleDropRejected = useCallback(({ item, track, reason }) => {
    const title = item?.title || item?.name || item?.id || "Item"
    if (reason === "TRACK_LOCKED") {
      showSnackbar(`Track "${track?.name || track?.id || 'target'}" is locked.`, "error")
    } else {
      showSnackbar(`Incompatible track: Cannot drop "${title}" onto ${track?.type || 'target'} track "${track?.name || track?.id || ''}".`, "error")
    }
  }, [showSnackbar])

  // 5d. Resolve and consume /motion?asset={key} deep links
  useEffect(() => {
    const queryParams = new URLSearchParams(window.location.search)
    const assetKey = queryParams.get("asset")
    if (!assetKey || handledDeepLinkAssetRef.current === assetKey) return
    if (!project || !document) return

    handledDeepLinkAssetRef.current = assetKey

    const consumeDeepLink = async () => {
      try {
        let resolvedItem = null
        try {
          const itemRes = await http.get(`/api/library/asset/${encodeURIComponent(assetKey)}`)
          resolvedItem = itemRes.data
        } catch {
          try {
            const listRes = await http.get("/api/library/items")
            const items = listRes.data?.items || listRes.data || []
            resolvedItem = items.find((i) => i.key === assetKey || i.id === assetKey)
          } catch {}
        }

        if (!resolvedItem) {
          showSnackbar(`Deep-linked asset "${assetKey}" could not be resolved from Library.`, "warning")
          return
        }

        const permitted = Array.isArray(resolvedItem.permitted_uses)
          ? resolvedItem.permitted_uses
          : ["timeline_motion"]
        if (!permitted.includes("timeline_motion")) {
          showSnackbar(`Asset "${assetKey}" rights policy forbids timeline_motion use.`, "error")
          return
        }

        setSelectedAsset(resolvedItem)

        const rawMediaType = (resolvedItem.media || resolvedItem.media_type || resolvedItem.mediaType || "video").toLowerCase()
        const isAudio = rawMediaType === "audio" || (resolvedItem.ext && ["mp3", "wav", "aac", "ogg"].includes(resolvedItem.ext.toLowerCase()))
        const isImage = rawMediaType === "image" || (resolvedItem.ext && ["png", "jpg", "jpeg", "webp", "gif"].includes(resolvedItem.ext.toLowerCase()))
        const clipType = isAudio ? "audio" : isImage ? "image" : "video"

        const tracks = document.timeline?.tracks || []
        let targetTrack = isAudio ? tracks.find((t) => t.type === "audio") : tracks.find((t) => t.type === "video")

        let targetTrackId = targetTrack?.id
        if (isAudio && !targetTrack) {
          const addTrackRes = await handleApplyOperation("add_track", { type: "audio", name: "Audio Track" })
          if (addTrackRes) {
            targetTrackId = (addTrackRes.document?.timeline?.tracks || []).find((t) => t.type === "audio")?.id
          }
        }

        if (!targetTrackId && tracks.length > 0) {
          targetTrackId = tracks[0].id
        }

        if (!targetTrackId) {
          showSnackbar(`No suitable timeline track found for deep link asset "${assetKey}".`, "error")
          return
        }

        const resolvedAssetId = resolvedItem.key || resolvedItem.id || assetKey
        const resolvedAssetFile = resolvedItem.filename || (String(resolvedAssetId).includes(".") ? resolvedAssetId : (isAudio ? `${resolvedItem.title || "audio"}.${resolvedItem.ext || "mp3"}` : isImage ? `${resolvedAssetId}.png` : `${resolvedAssetId}.mp4`))

        const newClip = {
          id: `clip_${Date.now()}`,
          type: clipType,
          asset_id: resolvedAssetId,
          asset_file: resolvedAssetFile,
          stream_url: resolvedItem.stream_url || `/api/library/asset/${resolvedAssetId}`,
          title: resolvedItem.title || resolvedItem.filename || (isAudio ? "Audio Clip" : "Media Clip"),
          start_seconds: currentTime || 0.0,
          duration_seconds: resolvedItem.duration_seconds ? Math.min(resolvedItem.duration_seconds, 60) : (isImage ? 3 : 5),
          source_provenance: resolvedItem.source_provenance || "library_user_asset",
          permitted_uses: permitted,
          file_sha256: resolvedItem.file_sha256 || resolvedItem.sha256 || null,
        }

        const res = await handleApplyOperation("add_clip", {
          track_id: targetTrackId,
          clip: newClip,
        })
        if (res) {
          showSnackbar(`Ingested deep link asset "${newClip.title}" into timeline (Rev ${res.revision})`, "success")
        }
      } catch (err) {
        showSnackbar(`Failed to ingest deep link asset "${assetKey}": ${err.message}`, "error")
      }
    }

    consumeDeepLink()
  }, [project, document, currentTime, handleApplyOperation, showSnackbar])

  // 5e. Resolve and consume /motion?insertBlock={id} deep links from Catalog
  useEffect(() => {
    const queryParams = new URLSearchParams(window.location.search)
    const blockId = queryParams.get("insertBlock") || queryParams.get("block")
    if (!blockId || handledDeepLinkBlockRef.current === blockId) return
    if (!project || !document) return

    handledDeepLinkBlockRef.current = blockId

    const consumeBlockDeepLink = async () => {
      try {
        let blockItem = null
        try {
          const res = await http.get(`/api/projects/catalog/items/${encodeURIComponent(blockId)}`)
          blockItem = res.data
        } catch {
          const listRes = await http.get("/api/projects/catalog/items")
          const items = listRes.data?.items || listRes.data || []
          blockItem = items.find((i) => (i.name || i.id) === blockId)
        }

        if (!blockItem) {
          showSnackbar(`Block "${blockId}" is not operational and cannot be inserted into timeline.`, "error")
          return
        }

        await handleAddBlock(blockItem)
      } catch (err) {
        showSnackbar(`Failed to insert catalog block "${blockId}": ${err.message}`, "error")
      }
    }

    consumeBlockDeepLink()
  }, [project, document, handleAddBlock, showSnackbar])

  // 6. Delete Clip via atomic operation
  const handleDeleteClip = async (clipOrId) => {
    if (!project || !clipOrId) return
    const clipId = typeof clipOrId === "string" ? clipOrId : clipOrId?.id
    if (!clipId) return
    if (selectedElement?.id === clipId) setSelectedElement(null)
    const res = await handleApplyOperation("remove_clip", { clip_id: clipId })
    if (res) {
      showSnackbar(`Removed clip from timeline (Rev ${res.revision})`, "info")
    }
  }

  // 7. Update element in inspector (local reactive state)
  const handleUpdateElement = (updatedElem) => {
    setSelectedElement(updatedElem)
    if (!document) return
    pushUndo(document)
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
    if (updatedElem.manual_transcript_override !== undefined) {
      patch.manual_transcript_override = updatedElem.manual_transcript_override
    }
    if (updatedElem.framing_preset !== undefined) patch.framing_preset = updatedElem.framing_preset
    if (updatedElem.speed !== undefined) patch.speed = updatedElem.speed
    if (updatedElem.trim_start !== undefined) patch.trim_start = updatedElem.trim_start
    if (updatedElem.trim_end !== undefined) patch.trim_end = updatedElem.trim_end
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

  // 7e-2. Ripple delete clip: remove clip and shift subsequent clips on that track left
  const handleRippleDeleteClip = async (clipOrId) => {
    if (!document || !clipOrId) return
    const clipId = typeof clipOrId === "string" ? clipOrId : clipOrId?.id
    if (!clipId) return
    if (selectedElement?.id === clipId) setSelectedElement(null)

    pushUndo(document)
    let delDur = 0
    let delStart = 0
    let targetTrackId = null

    for (const t of (document.timeline?.tracks || [])) {
      const found = (t.clips || []).find((c) => c.id === clipId)
      if (found) {
        delDur = Number(found.duration_seconds || 0)
        delStart = Number(found.start_seconds || 0)
        targetTrackId = t.id
        break
      }
    }

    const nextTracks = (document.timeline?.tracks || []).map((t) => {
      if (t.id !== targetTrackId) return t
      const remaining = (t.clips || []).filter((c) => c.id !== clipId)
      const shifted = remaining.map((c) => {
        const s = Number(c.start_seconds || 0)
        if (s >= delStart) {
          return { ...c, start_seconds: Math.max(0, Number((s - delDur).toFixed(2))) }
        }
        return c
      })
      return { ...t, clips: shifted }
    })

    const nextDoc = {
      ...document,
      timeline: { ...document.timeline, tracks: nextTracks },
    }
    setDocument(nextDoc)
    setIsDirty(true)
    showSnackbar("Ripple deleted clip and shifted subsequent clips", "info")

    if (project) {
      handleApplyOperation("update_document", { document: nextDoc })
    }
  }

  // 7e-3. Slip edit clip: adjust source window (trim_start/trim_end) without changing start_seconds/duration
  const handleSlipClip = async (clipOrId, deltaSeconds) => {
    if (!document || !clipOrId) return
    const clipId = typeof clipOrId === "string" ? clipOrId : clipOrId?.id
    if (!clipId) return

    pushUndo(document)
    let updatedClip = null
    const nextTracks = (document.timeline?.tracks || []).map((t) => ({
      ...t,
      clips: (t.clips || []).map((c) => {
        if (c.id === clipId) {
          const curTrim = Number(c.trim_start || 0)
          const curDur = Number(c.duration_seconds || 1.0)
          const nextTrim = Math.max(0, Number((curTrim + deltaSeconds).toFixed(2)))
          const nextEnd = Number((nextTrim + curDur).toFixed(2))
          updatedClip = { ...c, trim_start: nextTrim, trim_end: nextEnd }
          return updatedClip
        }
        return c
      }),
    }))

    if (updatedClip && selectedElement?.id === clipId) {
      setSelectedElement(updatedClip)
    }

    const nextDoc = {
      ...document,
      timeline: { ...document.timeline, tracks: nextTracks },
    }
    setDocument(nextDoc)
    setIsDirty(true)
    showSnackbar(`Slipped clip by ${deltaSeconds > 0 ? "+" : ""}${deltaSeconds.toFixed(1)}s`, "info")

    if (project && updatedClip) {
      handleApplyOperation("update_clip_timing", {
        clip_id: clipId,
        trim_start: updatedClip.trim_start,
        trim_end: updatedClip.trim_end,
      })
    }
  }

  // 7e-4. Retime clip speed multiplier
  const handleSpeedChangeClip = async (clipOrId, newSpeed) => {
    if (!document || !clipOrId || newSpeed <= 0) return
    const clipId = typeof clipOrId === "string" ? clipOrId : clipOrId?.id
    if (!clipId) return

    pushUndo(document)
    let updatedClip = null
    const nextTracks = (document.timeline?.tracks || []).map((t) => ({
      ...t,
      clips: (t.clips || []).map((c) => {
        if (c.id === clipId) {
          const oldSpeed = Number(c.speed || 1.0)
          const oldDur = Number(c.duration_seconds || 1.0)
          const newDur = Math.max(0.1, Number(((oldDur * oldSpeed) / newSpeed).toFixed(2)))
          updatedClip = { ...c, speed: newSpeed, duration_seconds: newDur }
          return updatedClip
        }
        return c
      }),
    }))

    if (updatedClip && selectedElement?.id === clipId) {
      setSelectedElement(updatedClip)
    }

    const nextDoc = {
      ...document,
      timeline: { ...document.timeline, tracks: nextTracks },
    }
    setDocument(nextDoc)
    setIsDirty(true)
    showSnackbar(`Retime clip speed to ${newSpeed}x`, "info")

    if (project && updatedClip) {
      handleApplyOperation("update_clip_timing", {
        clip_id: clipId,
        duration_seconds: updatedClip.duration_seconds,
        speed: updatedClip.speed,
      })
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

  const handleNavigateToCode = useCallback((file, clipId) => {
    setActiveContext("code")
    if (clipId) {
      handleSelectElementId(clipId)
    } else if (file) {
      setSelectedElement(file)
    }
  }, [handleSelectElementId])

  const handleRefreshLibrary = useCallback(async () => {
    try {
      const res = await http.get("/api/library/items")
      const list = res.data?.items || res.data
      if (Array.isArray(list)) {
        setLibraryVideos(list)
        if (list.length > 0 && !activeAsset) {
          setSelectedAsset(list[0])
        }
      }
      return list
    } catch {
      return []
    }
  }, [activeAsset])

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
            pushUndo(document)
            setDocument({ ...document, aspect_ratio: asp })
            setIsDirty(true)
          }
        }}
        workspaceMode={workspaceMode}
        onWorkspaceModeChange={handleWorkspaceModeChange}
        advancedEditing={advancedEditing}
        onToggleAdvancedEditing={handleToggleAdvancedEditing}
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
        canUndo={undoStack.length > 0}
        onUndo={handleUndo}
        canRedo={redoStack.length > 0}
        onRedo={handleRedo}
        canCancel={isDirty}
        onCancelDraft={handleCancelDraft}
        onNewProject={handleNewProject}
      />

      {/* Migration Warning: Controlled notice for legacy projects with retired 6Clips blocks */}
      {legacyReport.hasLegacy && (
        <Alert
          severity="warning"
          variant="filled"
          data-testid="legacy-blocks-migration-alert"
          sx={{
            mx: 2,
            mt: 1,
            mb: 0.5,
            borderRadius: 1.5,
            fontSize: "0.8rem",
            py: 0.5,
          }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                showSnackbar(
                  `Legacy block(s) (${legacyReport.legacyBlocks.join(", ")}) preserved safely. In Wave 15, replace with authentic HyperFrames donor originals.`,
                  "info"
                )
              }}
              sx={{ fontWeight: 700, fontSize: "0.72rem" }}
            >
              Migration Info
            </Button>
          }
        >
          <strong>REQUIRES_MIGRATION:</strong> Legacy 6Clips-authored block(s) detected (
          {legacyReport.legacyBlocks.join(", ")}). Project content and timing are fully preserved. In Wave 15, replace with authentic HyperFrames donor originals.
        </Alert>
      )}

      {/* 2. Main Studio Body: Vertical Split (Upper: Stage & Panels; Lower: Full-Width Contextual Workspace) */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>

        {/* Upper Stage & Sidebars Row */}
        <Box
          sx={{
            flex: workspaceMode === "refine" ? (expandedPreview ? "1 1 70%" : "1 1 56%") : "1 1 100%",
            display: "flex",
            minHeight: expandedPreview ? 400 : 320,
            overflow: "hidden",
            position: "relative",
          }}
        >
          {/* Left: Collapsed Rail Indicator (Advanced Editing Mode only) */}
        {advancedEditing && !pinnedLeft && (
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

        {/* Left: MotionReviewPanel (Review mode) */}
        {workspaceMode === "review" && pinnedLeft && (
          <Box sx={{ width: 320, minWidth: 280, maxWidth: 380, height: "100%", zIndex: 2, display: "flex", flexDirection: "column", bgcolor: "#ffffff", borderRight: "1px solid", borderColor: "divider" }}>
            <MotionReviewPanel
              outputs={reviewOutputs}
              selectedOutputIndex={selectedOutputIndex}
              onSelectOutput={handleSelectOutput}
              onApproveOutput={handleApproveOutput}
              onExportOutput={handleExportOutput}
              onRefineOutput={handleRefineOutput}
              approvedOutputs={approvedOutputs}
              reviewNotes={reviewNotes}
              onChangeReviewNotes={handleReviewNotesChange}
            />
          </Box>
        )}

        {/* Left: Layers or Media & Sources (Advanced Editing Mode only) */}
        {advancedEditing && pinnedLeft && (
          <Box sx={{ width: 280, minWidth: 260, maxWidth: 340, height: "100%", zIndex: 2, display: "flex", flexDirection: "column", bgcolor: "#ffffff", borderRight: "1px solid", borderColor: "divider" }}>
            {/* Left Nav Header Tabs: Layers vs Media & Sources */}
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
                  Media & Sources
                </Button>
              </Stack>
            </Box>

            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
              {leftNav === "layers" ? (
                <StudioLayersPanel
                  tracks={document?.timeline?.tracks || []}
                  codeFiles={document?.code?.files || []}
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
                  onNavigateToCode={handleNavigateToCode}
                />
              ) : (
                <StudioResourcePanel
                  libraryVideos={libraryVideos}
                  trendItems={trendItems}
                  loading={dataLoading}
                  selectedAssetId={activeAsset?.id}
                  aspectRatio={aspectRatio}
                  onSelectSource={(asset) => setSelectedAsset(asset)}
                  onAddMediaToTimeline={handleAddMedia}
                  isPinned={pinnedLeft}
                  onTogglePin={() => setPinnedLeft(!pinnedLeft)}
                />
              )}
            </Box>
          </Box>
        )}

        {/* Center: Stage */}
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, height: "100%" }}>
          {workspaceMode === "review" && reviewOutputs.length > 1 && (
            <Box
              sx={{
                py: 0.75,
                px: 2,
                bgcolor: "#f1f5f9",
                borderBottom: "1px solid",
                borderColor: "divider",
                display: "flex",
                alignItems: "center",
                gap: 1,
                zIndex: 5,
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", textTransform: "uppercase", fontSize: "0.7rem" }}>
                Outputs:
              </Typography>
              <Stack direction="row" spacing={0.8}>
                {reviewOutputs.map((out, idx) => (
                  <Button
                    key={out.output_id || idx}
                    size="small"
                    variant={selectedOutputIndex === idx ? "contained" : "outlined"}
                    color={approvedOutputs.has(out.output_id) ? "success" : "primary"}
                    onClick={() => handleSelectOutput(idx)}
                    sx={{
                      fontSize: "0.72rem",
                      py: 0.25,
                      px: 1.25,
                      borderRadius: 1.5,
                      fontWeight: 700,
                      textTransform: "none",
                    }}
                  >
                    Clip {idx + 1}: {out.output_id || `Output ${idx + 1}`}
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          <StudioPreviewStage
            ref={previewStageRef}
            project={project}
            previewUrl={previewUrl}
            aspectRatio={aspectRatio}
            isLoading={isProjectLoading || (starting && !!project)}
            error={startError || projectError}
            onRetry={() => window.location.reload()}
            loadingMessage={isProjectLoading ? "Loading project document…" : "Starting preview server…"}
            currentTime={currentTime}
            duration={activeReviewOutput?.media_probe?.duration_seconds || renderedVideo?.duration_seconds || document?.timeline?.duration_seconds || 15}
            isPlaying={isPlaying}
            onTogglePlay={() => setIsPlaying(!isPlaying)}
            onPlaybackStateChange={setIsPlaying}
            onTimeUpdate={setCurrentTime}
            onSeek={handleUserSeek}
            onRefresh={() => window.location.reload()}
            onSelectElementId={handleSelectElementId}
            workspaceMode={workspaceMode}
            renderedVideo={activeReviewOutput}
            activeJob={activeJob}
            onOpenAdvanced={() => setAdvancedEditing(true)}
            onNewProject={handleNewProject}
          />
        </Box>

        {/* Right: Properties / Variables Inspector (Advanced Editing Mode only) */}
        {advancedEditing && pinnedRight && (
          <Box sx={{ width: 280, minWidth: 260, maxWidth: 340, height: "100%", zIndex: 2, display: "flex", flexDirection: "column", bgcolor: "#ffffff", borderLeft: "1px solid", borderColor: "divider" }}>
            {/* Right Nav Header Tabs: Properties vs Variables */}
            <Box sx={{ px: 1, py: 0.75, borderBottom: "1px solid", borderColor: "divider", bgcolor: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Stack direction="row" spacing={0.5}>
                <Button
                  size="small"
                  data-testid="tab-properties"
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
                  data-testid="tab-variables"
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
                  onNavigateToCode={handleNavigateToCode}
                  onSlipClip={handleSlipClip}
                  onSpeedChangeClip={handleSpeedChangeClip}
                />
              ) : rightNav === "variables" ? (
                <StudioVariablesPanel
                  selectedElement={selectedElement}
                  onUpdateVariables={handleUpdateVariables}
                  onCommitVariables={handleCommitVariables}
                  isLocked={selectedElement?.locked}
                />
              ) : (
                <StudioToolsInspector
                  selectedElement={selectedElement}
                  tracks={document?.timeline?.tracks || []}
                  currentTime={currentTime}
                  project={project}
                  revision={revision}
                  projectDocument={document}
                  onApplyOperation={handleApplyOperation}
                  onSplitClip={handleSplitClip}
                  onDeleteClip={handleDeleteClip}
                  onDuplicateClip={handleDuplicateClip}
                  onSlipClip={handleSlipClip}
                  onSpeedChangeClip={handleSpeedChangeClip}
                  showSnackbar={showSnackbar}
                />
              )}
            </Box>
          </Box>
        )}

        {/* Right: Collapsed Rail Indicator (Advanced Editing Mode only) */}
        {advancedEditing && !pinnedRight && (
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

      {/* Lower: Full-Width Canonical Workspace (Advanced Editing Mode only) */}
      {advancedEditing && (
        <Box
          data-testid="studio-advanced-workspace"
          sx={{
            flex: expandedPreview ? "0 0 160px" : "1 1 44%",
            minHeight: expandedPreview ? 140 : 220,
            width: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            borderTop: "1px solid",
            borderColor: "divider",
            zIndex: 3,
          }}
        >
          {activeContext === "code" ? (
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
          ) : (
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
              onRippleDeleteClip={handleRippleDeleteClip}
              onSlipClip={handleSlipClip}
              onSpeedChangeClip={handleSpeedChangeClip}
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
              onDropExternalClip={handleDropExternalClip}
              onDropRejected={handleDropRejected}
            />
          )}
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
    </Box>
  )
}
