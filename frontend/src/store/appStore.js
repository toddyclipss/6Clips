import { create } from "zustand"

const useAppStore = create((set, get) => ({
  // ── Chat sessions ───────────────────────────────────────────────────────
  sessions: [],          // [{id, title, message_count, created_at, updated_at}]
  activeSessionId: null,
  messages: [],
  isStreaming: false,
  streamingText: "",
  wsConnected: false,
  latestOutcome: null,

  setWsConnected: (v) => set({ wsConnected: Boolean(v) }),
  setLatestOutcome: (outcome) => set({ latestOutcome: outcome }),

  setSessions: (sessions) => set({ sessions }),
  setActiveSessionId: (id) => {
    if (id) sessionStorage.setItem("vm_active_session", id)
    else sessionStorage.removeItem("vm_active_session")
    set({ activeSessionId: id })
  },

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setMessages: (msgs) => set({ messages: msgs }),
  setStreaming: (v) => set({ isStreaming: v }),
  appendStreamToken: (token) => set((s) => ({ streamingText: s.streamingText + token })),
  streamingExecutionTimeline: [],
  setStreamingExecutionTimeline: (t) => set({ streamingExecutionTimeline: t }),
  clearStreamingExecutionTimeline: () => set({ streamingExecutionTimeline: [] }),
  handleToolEvent: (event) => set((s) => {
    const { step_id, tool_call_id, tool_name, state, arguments: args, result, duration_ms, error } = event
    const existingSteps = [...s.streamingExecutionTimeline]
    let stepIndex = existingSteps.findIndex((st) => st.id === step_id)

    const isErr = state === "output-error" || Boolean(error) || (result && result.status === "error")
    const isDone = state === "output-available" && !isErr
    const stepStatus = isErr ? "failed" : isDone ? "completed" : "executing"

    if (stepIndex === -1) {
      existingSteps.push({
        id: step_id || `step_${Date.now()}`,
        title: `Execute ${tool_name || "tool"}`,
        status: stepStatus,
        duration_ms: duration_ms || 0,
        tool_calls: [
          {
            id: tool_call_id || `tc_${Date.now()}`,
            name: tool_name,
            state: state || "executing",
            arguments: args,
            result: result,
            duration_ms: duration_ms,
            error: error,
          },
        ],
      })
    } else {
      const targetStep = { ...existingSteps[stepIndex] }
      const tcList = [...(targetStep.tool_calls || [])]
      let tcIndex = tcList.findIndex((tc) => tc.id === tool_call_id)
      const newTc = {
        id: tool_call_id,
        name: tool_name || (tcIndex >= 0 ? tcList[tcIndex].name : "tool"),
        state: state,
        arguments: args !== undefined ? args : tcIndex >= 0 ? tcList[tcIndex].arguments : {},
        result: result !== undefined ? result : tcIndex >= 0 ? tcList[tcIndex].result : undefined,
        duration_ms: duration_ms !== undefined ? duration_ms : tcIndex >= 0 ? tcList[tcIndex].duration_ms : undefined,
        error: error !== undefined ? error : tcIndex >= 0 ? tcList[tcIndex].error : undefined,
      }
      if (tcIndex === -1) {
        tcList.push(newTc)
      } else {
        tcList[tcIndex] = newTc
      }
      targetStep.tool_calls = tcList
      if (duration_ms) targetStep.duration_ms = duration_ms
      targetStep.status = stepStatus
      existingSteps[stepIndex] = targetStep
    }
    return { streamingExecutionTimeline: existingSteps }
  }),

  // quickReplies is optional — when the planner emits a <quick_replies> block,
  // the chips render below the just-finished assistant bubble. They live only
  // in the in-memory message (not persisted), so they vanish on session reload
  // (intended — the conversation has moved on).
  finalizeStream: (fullText, quickReplies, executionTimeline) => {
    const cleaned = fullText || get().streamingText
    const timeline = (executionTimeline && executionTimeline.length > 0)
      ? executionTimeline
      : get().streamingExecutionTimeline
    const msg = {
      role: "assistant",
      content: cleaned,
      executionTimeline: timeline && timeline.length > 0 ? timeline : null,
    }
    if (Array.isArray(quickReplies) && quickReplies.length > 0) {
      msg.quickReplies = quickReplies
    }
    set((s) => ({
      messages: [...s.messages, msg],
      streamingText: "",
      streamingExecutionTimeline: [],
      isStreaming: false,
    }))
  },
  clearStreamingText: () => set({ streamingText: "" }),

  // Update a session in the list (title, message_count)
  updateSession: (sessionId, updates) => set((s) => ({
    sessions: s.sessions.map(sess =>
      sess.id === sessionId ? { ...sess, ...updates } : sess
    ),
  })),

  // Add a session to the top of the list
  prependSession: (session) => set((s) => ({
    sessions: [session, ...s.sessions.filter(ss => ss.id !== session.id)],
  })),

  // Remove a session from the list
  removeSession: (sessionId) => set((s) => ({
    sessions: s.sessions.filter(ss => ss.id !== sessionId),
    activeSessionId: s.activeSessionId === sessionId ? null : s.activeSessionId,
    messages: s.activeSessionId === sessionId ? [] : s.messages,
  })),

  // Smart suggestions
  suggestions: [],
  setSuggestions: (s) => set({ suggestions: s }),

  // Active wizard
  activeWizard: null,
  setActiveWizard: (w) => set({ activeWizard: w }),

  // Motion Graphics plugin opt-in state. Set by the Settings card and by the
  // route gate, so the sidebar entry and the Tools card can reflect "installed"
  // without each of them polling the same endpoint. `null` = not yet known,
  // which is deliberately distinct from `false`: an entry that flashes
  // "not installed" for one frame on every page load reads as broken.
  motionInstalled: null,
  setMotionInstalled: (v) => set({ motionInstalled: v }),

  // Jobs (polling from API — Dashboard uses this)
  jobs: [],
  setJobs: (j) => set({ jobs: j }),

  // ── Activity panel ────────────────────────────────────────────────────────
  // The job log lives in a panel any surface can open, because jobs start from
  // Stock Video, a tool page, the Clipper and the Motion studio alike — it used
  // to be a Library tab, reachable from exactly one route. The sidebar's
  // running-jobs pill and the Library's Activity button both flip this.
  activityOpen: false,
  openActivity: () => set({ activityOpen: true }),
  closeActivity: () => set({ activityOpen: false }),

  // Active jobs — real-time via WebSocket, persists across page nav
  // { [jobId]: { jobId, jobType, status, percent, step, message, startedAt } }
  activeJobs: {},
  startJob: (jobId, jobType, message, meta) => set((s) => ({
    activeJobs: {
      ...s.activeJobs,
      [jobId]: { jobId, jobType, status: "running", percent: 0, step: message || "", message, startedAt: Date.now(), ...(meta || {}) },
    },
  })),
  updateJobProgress: (jobId, percent, step) => set((s) => {
    const existing = s.activeJobs[jobId]
    if (!existing) return {}
    return { activeJobs: { ...s.activeJobs, [jobId]: { ...existing, percent, step } } }
  }),
  completeJob: (jobId) => set((s) => {
    const existing = s.activeJobs[jobId]
    if (!existing) return {}
    return { activeJobs: { ...s.activeJobs, [jobId]: { ...existing, status: "success", percent: 100 } } }
  }),
  failJob: (jobId, error) => set((s) => {
    const existing = s.activeJobs[jobId]
    if (!existing) return {}
    return { activeJobs: { ...s.activeJobs, [jobId]: { ...existing, status: "failed", step: error || "Failed" } } }
  }),
  removeJob: (jobId) => set((s) => {
    const { [jobId]: _, ...rest } = s.activeJobs
    return { activeJobs: rest }
  }),


  // Settings
  settings: null,
  setSettings: (s) => set({ settings: s }),

  // Trends results
  trendResults: [],
  trendsResults: [],
  setTrendResults: (r) => set({ trendResults: r, trendsResults: r }),
  setTrendsResults: (r) => set({ trendResults: r, trendsResults: r }),

  // Global snackbar (action: optional { label, href } for a clickable link)
  snackbar: { open: false, message: "", severity: "info", action: null },
  showSnackbar: (message, severity = "info", action = null) => set({ snackbar: { open: true, message, severity, action } }),
  closeSnackbar: () => set((s) => ({ snackbar: { ...s.snackbar, open: false } })),
}))

export default useAppStore
