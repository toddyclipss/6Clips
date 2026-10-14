import * as React from "react"
import { motion, AnimatePresence, LayoutGroup } from "framer-motion"
import { createPortal } from "react-dom"
import {
  IconPaperclip,
  IconArrowUp,
  IconX,
  IconRocket,
  IconBulb,
  IconCheck,
  IconChevronDown,
  IconFileDescription,
  IconCpu,
} from "@tabler/icons-react"
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import http from "../../api/http"
import { fetchModelRegistry } from "../../api/modelRegistry"
import useAppStore from "../../store/appStore"
import useSettings from "../../hooks/useSettings"

function cn(...inputs) {
  return twMerge(clsx(inputs))
}

const LIQUID_MATTE_NOISE = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.65 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>")`

export const PROVIDER_NAMES = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Gemini",
  openrouter: "OpenRouter",
  ollama: "Ollama",
}

export function LiquidMultimodalInput({
  placeholder = "Message 6Clips or describe a video...",
  maxHeight = 200,
  accept = "image/*,video/*,text/*,application/pdf,.doc,.docx,.xls,.xlsx,.csv,.json",
  onSubmit,
  onChange,
  disabled = false,
  className,
}) {
  const [value, setValue] = React.useState("")
  const [files, setFiles] = React.useState([])
  const [dragOver, setDragOver] = React.useState(false)
  const taRef = React.useRef(null)
  const fileInputRef = React.useRef(null)
  const dragCounter = React.useRef(0)

  React.useEffect(() => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = Math.min(Math.max(ta.scrollHeight, 48), maxHeight) + "px"
    if (!value) ta.scrollTop = 0
  }, [value, maxHeight])

  function addFiles(list) {
    const arr = Array.from(list)
      .filter((f) => !f.type.startsWith("audio/"))
      .map((f) => ({
        id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()),
        file: f,
        preview: f.type.startsWith("image/") ? URL.createObjectURL(f) : undefined,
      }))
    setFiles((prev) => [...prev, ...arr])
  }

  function removeFile(id) {
    setFiles((prev) => {
      const f = prev.find((x) => x.id === id)
      if (f?.preview) URL.revokeObjectURL(f.preview)
      return prev.filter((x) => x.id !== id)
    })
  }

  const { settings, updateSettings } = useSettings()
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const [registry, setRegistry] = React.useState({})
  const [selectorOpen, setSelectorOpen] = React.useState(false)

  React.useEffect(() => {
    let active = true
    const controller = new AbortController()
    fetchModelRegistry({ signal: controller.signal })
      .then((reg) => {
        if (active && reg) setRegistry(reg)
      })
      .catch(() => {})
    return () => {
      active = false
      controller.abort()
    }
  }, [])

  // Explicit Model Choice state — strict zero default:
  const [localProvider, setLocalProvider] = React.useState(() => {
    return (typeof window !== "undefined" ? localStorage.getItem("6clips_ai_provider") : null) || null
  })
  const [localModel, setLocalModel] = React.useState(() => {
    return (typeof window !== "undefined" ? localStorage.getItem("6clips_ai_model") : null) || null
  })
  const [reasoningLevel, setReasoningLevel] = React.useState(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("6clips_ai_reasoning") : null
    if (!saved) return null
    const s = saved.toLowerCase()
    return (s === "high" || s === "hard") ? "high" : s
  })

  // Synchronize two-way with backend settings:
  React.useEffect(() => {
    if (settings?.ai_provider && settings?.ai_model) {
      setLocalProvider(settings.ai_provider)
      setLocalModel(settings.ai_model)
    }
    if (settings?.ai_reasoning_level) {
      const lvl = settings.ai_reasoning_level.toLowerCase()
      setReasoningLevel((lvl === "high" || lvl === "hard") ? "high" : lvl)
    }
  }, [settings?.ai_provider, settings?.ai_model, settings?.ai_reasoning_level])

  const isModelValid = Boolean(
    localProvider &&
    localModel &&
    registry[localProvider]?.models?.includes(localModel)
  )

  const selectedProvider = isModelValid ? localProvider : null
  const selectedModel = isModelValid ? localModel : null

  const handleSelectReasoning = async (lvl) => {
    const validLevel = (lvl === "high" || lvl === "hard") ? "high" : lvl
    setReasoningLevel(validLevel)
    if (typeof window !== "undefined") {
      localStorage.setItem("6clips_ai_reasoning", validLevel)
    }
    try {
      await updateSettings({ ai_reasoning_level: validLevel })
    } catch {}
    const displayLabel = validLevel.charAt(0).toUpperCase() + validLevel.slice(1)
    showSnackbar(`Reasoning set to ${displayLabel}`, "info")
  }

  function submit() {
    if ((!value.trim() && files.length === 0) || disabled) return
    if (!selectedProvider || !selectedModel) {
      showSnackbar("No AI model selected. Choose a model in Global Chat to continue.", "warning")
      setSelectorOpen(true)
      return
    }
    if (!reasoningLevel) {
      showSnackbar("No reasoning effort selected. Choose Low, Medium, or High to continue.", "warning")
      setSelectorOpen(true)
      return
    }
    const userIntentId = `user_submit_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    onSubmit?.(value, files.map((f) => f.file), {
      provider: selectedProvider,
      model: selectedModel,
      reasoning_level: reasoningLevel,
      user_intent_id: userIntentId,
      authorized: true,
    })
    setValue("")
    files.forEach((f) => f.preview && URL.revokeObjectURL(f.preview))
    setFiles([])
    if (taRef.current) {
      taRef.current.style.height = "48px"
      taRef.current.scrollTop = 0
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function onDragEnter(e) {
    e.preventDefault()
    dragCounter.current++
    if (e.dataTransfer.types.includes("Files")) setDragOver(true)
  }
  function onDragLeave(e) {
    e.preventDefault()
    dragCounter.current--
    if (dragCounter.current <= 0) {
      dragCounter.current = 0
      setDragOver(false)
    }
  }
  function onDrop(e) {
    e.preventDefault()
    dragCounter.current = 0
    setDragOver(false)
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files)
  }

  return (
    <div
      className={cn("w-full", className)}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={(e) => e.preventDefault()}
      onDrop={onDrop}
      style={{ willChange: "transform" }}
    >
      <div className="relative w-full flex flex-col items-center">
        {/* Outer Glow (Drop target) */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute -inset-[2px] rounded-[24px] opacity-0 blur-[10px]"
          animate={{ opacity: dragOver ? 0.9 : 0 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          style={{
            background:
              "conic-gradient(from 0deg, #64748b, #94a3b8, #64748b, #475569, #64748b)",
            willChange: "opacity",
          }}
        />

        {/* Main Form Container */}
        <div
          className={cn(
            "group relative isolate flex w-full flex-col transition-all duration-150 ease-in-out",
            "border border-black/[0.08] bg-[radial-gradient(ellipse_90%_70%_at_50%_-10%,#ffffff_0%,#f4f4f5_72%)] text-sm",
            "shadow-[0_1px_2px_rgba(0,0,0,.06),0_8px_24px_-12px_rgba(0,0,0,.08)]",
            "hover:border-black/[0.12] focus-within:border-black/[0.14]",
            "dark:border-white/[0.06] dark:bg-[radial-gradient(ellipse_90%_70%_at_50%_-10%,#1a1918_0%,#121110_72%)]",
            "dark:shadow-[0_1px_2px_rgba(0,0,0,.4),0_8px_24px_-12px_rgba(0,0,0,.6)]",
            "dark:hover:border-white/[0.12] dark:focus-within:border-white/[0.16]",
            dragOver && "border-slate-500/45 dark:border-slate-400/45"
          )}
          style={{
            padding: "14px 16px 12px 16px",
            borderRadius: "22px",
            boxSizing: "border-box",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
          }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-overlay dark:opacity-[0.055]"
            style={{
              backgroundImage: LIQUID_MATTE_NOISE,
              backgroundSize: "240px 240px",
            }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(0,0,0,0.035)_0%,transparent_30%,transparent_72%,rgba(0,0,0,0.055)_100%)] dark:bg-[linear-gradient(to_bottom,rgba(0,0,0,0.12)_0%,transparent_28%,transparent_72%,rgba(0,0,0,0.22)_100%)]"
          />

          {/* Animated Gradient Thin Inner Edge (1px) */}
          <div
            aria-hidden
            className="lmi-border pointer-events-none absolute inset-0 z-10 opacity-30 transition-opacity duration-500 group-focus-within:opacity-80 group-hover:opacity-80"
            style={{
              borderRadius: "22px",
              padding: "1px",
              WebkitMask:
                "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
              WebkitMaskComposite: "xor",
              maskComposite: "exclude",
              background:
                "conic-gradient(from var(--lmi-angle, 0deg), transparent 65%, rgba(100,116,139,0.5) 80%, #94a3b8 95%, transparent 100%)",
            }}
          />
          <style>{`
            @property --lmi-angle {
              syntax: '<angle>';
              initial-value: 0deg;
              inherits: false;
            }
            .lmi-border {
              animation: lmi-spin 4s linear infinite;
            }
            @keyframes lmi-spin {
              to { --lmi-angle: 360deg; }
            }
          `}</style>

          <div className="w-full min-w-0 relative z-20">
            <div className="relative flex flex-col w-full flex-1">
              {/* Attachments Gallery */}
              <AnimatePresence initial={false}>
                {files.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex flex-wrap gap-2 px-1 pt-0.5 pb-2"
                  >
                    {files.map((f) => (
                      <motion.div
                        key={f.id}
                        layout
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        transition={{ type: "spring", stiffness: 400, damping: 28 }}
                        className="group/file relative flex shrink-0 items-center justify-center"
                      >
                        {f.preview ? (
                          <button
                            type="button"
                            onClick={() => window.open(f.preview, "_blank")}
                            className="relative h-14 w-14 overflow-hidden rounded-lg border border-black/5 shadow-sm dark:border-white/10 cursor-zoom-in focus:outline-none focus:ring-2 focus:ring-violet-500/50"
                          >
                            <img
                              src={f.preview}
                              alt={f.file.name}
                              className="h-full w-full object-cover transition-transform duration-300 group-hover/file:scale-105"
                            />
                            <div className="absolute inset-0 bg-black/10 opacity-0 transition-opacity duration-200 group-hover/file:opacity-100" />
                          </button>
                        ) : (
                          <div className="flex h-11 max-w-[140px] items-center gap-1.5 rounded-lg border border-black/5 bg-black/5 px-2 shadow-sm dark:border-white/10 dark:bg-white/5">
                            <IconFileDescription
                              size={16}
                              className="shrink-0 text-slate-400 dark:text-muted-foreground"
                            />
                            <span className="truncate text-xs font-medium text-slate-700 dark:text-foreground">
                              {f.file.name}
                            </span>
                          </div>
                        )}

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeFile(f.id)
                          }}
                          aria-label={`Remove ${f.file.name}`}
                          className={cn(
                            "absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full bg-slate-800 text-white shadow-md transition-all duration-200",
                            "opacity-75 hover:bg-violet-600 hover:opacity-100 focus:opacity-100",
                            "dark:bg-slate-700 dark:hover:bg-violet-600"
                          )}
                        >
                          <IconX size={12} stroke={2.5} />
                        </button>
                      </motion.div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Textarea */}
              <textarea
                ref={taRef}
                value={value}
                onChange={(e) => {
                  setValue(e.target.value)
                  onChange?.(e.target.value)
                }}
                onKeyDown={handleKey}
                placeholder={placeholder}
                disabled={disabled}
                aria-label="Chat input"
                style={{
                  minHeight: "44px",
                  maxHeight: `${maxHeight}px`,
                  boxSizing: "border-box",
                  border: "none",
                  outline: "none",
                  boxShadow: "none",
                  background: "transparent",
                  width: "100%",
                  resize: "none",
                  padding: "4px 4px 6px 4px",
                  fontSize: "14px",
                  lineHeight: "1.5",
                  fontFamily: "inherit",
                  display: "block",
                  color: "inherit",
                  overflowY: "auto",
                }}
              />
            </div>
          </div>

          {/* Toolbar Container */}
          <div
            className="relative z-20 flex items-center justify-between gap-1 w-full"
            style={{
              paddingTop: "6px",
              paddingBottom: "2px",
              boxSizing: "border-box",
            }}
          >
            {/* Left controls: Attach File & Model Selector */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                aria-label="Attach file"
                className="grid h-7 w-7 place-items-center rounded-full text-slate-500 transition-colors hover:bg-black/5 hover:text-foreground dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-foreground cursor-pointer"
              >
                <IconPaperclip size={16} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={accept}
                hidden
                onChange={(e) => {
                  if (e.target.files?.length) addFiles(e.target.files)
                  e.target.value = ""
                }}
              />

              <ModelSelector
                registry={registry}
                setRegistry={setRegistry}
                selectedProvider={selectedProvider}
                selectedModel={selectedModel}
                reasoningLevel={reasoningLevel}
                onSelectReasoning={handleSelectReasoning}
                onSelectModel={(p, m) => {
                  setLocalProvider(p)
                  setLocalModel(m)
                }}
                open={selectorOpen}
                setOpen={setSelectorOpen}
              />
            </div>

            {/* Right controls: Submit button */}
            <div className="flex items-center">
              <motion.button
                type="button"
                onClick={submit}
                disabled={(!value.trim() && files.length === 0) || disabled}
                aria-label="Send message"
                whileTap={{ scale: 0.92 }}
                transition={{ type: "spring", stiffness: 400, damping: 22 }}
                className={cn(
                  "grid h-7 w-7 place-items-center rounded-full transition-all shrink-0 cursor-pointer",
                  "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.3)]",
                  "hover:opacity-90",
                  "disabled:bg-slate-200 disabled:from-slate-200 disabled:to-slate-200 disabled:text-slate-400 disabled:shadow-none",
                  "dark:disabled:bg-white/10 dark:disabled:from-white/10 dark:disabled:to-white/10 dark:disabled:text-white/30"
                )}
                style={{ willChange: "transform" }}
              >
                <IconArrowUp size={15} stroke={2.5} />
              </motion.button>
            </div>
          </div>

          {/* Drop overlay */}
          <AnimatePresence>
            {dragOver && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.18 }}
                className="pointer-events-none absolute inset-0 z-30 grid place-items-center rounded-[22px] bg-white/50 backdrop-blur-[2px] dark:bg-[#121212]/60"
                style={{ willChange: "opacity" }}
              >
                <div className="flex items-center gap-2 rounded-full border border-slate-500/20 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-xl dark:border-slate-500/30 dark:bg-[#1a1a1a] dark:text-slate-300">
                  <IconPaperclip size={14} />
                  Drop files here
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}

/* ───────────────────────── Dynamic Model & Provider Selector ───────────────────────── */

export function formatModelName(modelId) {
  if (!modelId) return "Model"
  const m = String(modelId).toLowerCase().trim()
  if (m === "gemma4:e4b") return "Gemma 4 E4B"
  if (m.includes("gpt-6-astra")) return "GPT-6 Astra"
  if (m.includes("gpt-6.1-sol")) return "GPT-6.1 Sol"
  if (m.includes("gpt-6-luna") || m.includes("gpt-6.1-luna")) return "GPT-6 Luna"
  if (m.includes("claude-fable-5-1") || m.includes("claude-fable-5.1")) return "Claude Fable 5.1"
  if (m.includes("claude-opus-5-5") || m.includes("claude-opus-5.5")) return "Claude Opus 5.5"
  if (m.includes("claude-sonnet-5-5") || m.includes("claude-sonnet-5.5")) return "Claude Sonnet 5.5"
  if (m.includes("claude-haiku-5-5") || m.includes("claude-haiku-5.5")) return "Claude Haiku 5.5"
  if (m.includes("gemini-3.8-flash")) return "Gemini 3.8 Flash"
  if (m.includes("gemini-3.1-pro-preview")) return "Gemini 3.1 Pro Preview"
  const parts = modelId.split("/")
  const name = parts[parts.length - 1]
  return name
    .replace(/^claude-/, "Claude ")
    .replace(/^gpt-/, "GPT-")
    .replace(/^gemini-/, "Gemini ")
    .replace(/^gemma4:/, "Gemma 4 ")
}

function ModelSelector({
  registry: passedRegistry,
  setRegistry: passedSetRegistry,
  selectedProvider,
  selectedModel,
  reasoningLevel,
  onSelectReasoning,
  onSelectModel,
  open: controlledOpen,
  setOpen: controlledSetOpen,
}) {
  const [internalOpen, setInternalOpen] = React.useState(false)
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen
  const setOpen = controlledSetOpen !== undefined ? controlledSetOpen : setInternalOpen

  const [localRegistry, setLocalRegistry] = React.useState({})
  const registry = passedRegistry && Object.keys(passedRegistry).length > 0 ? passedRegistry : localRegistry
  const setRegistry = passedSetRegistry || setLocalRegistry
  const [menuPosition, setMenuPosition] = React.useState(null)
  const wrapRef = React.useRef(null)
  const buttonRef = React.useRef(null)
  const menuRef = React.useRef(null)
  const listboxId = React.useId()

  const { settings, updateSettings } = useSettings()
  const showSnackbar = useAppStore((s) => s.showSnackbar)

  const [activeTab, setActiveTab] = React.useState(selectedProvider || "ollama")

  React.useEffect(() => {
    if (selectedProvider) setActiveTab(selectedProvider)
  }, [selectedProvider])

  // Load registry if not passed
  React.useEffect(() => {
    if (passedRegistry && Object.keys(passedRegistry).length > 0) return
    http
      .get("/api/config/model_registry")
      .then(({ data }) => setRegistry(data?.value || {}))
      .catch(() => {})
  }, [passedRegistry, setRegistry])

  const availableProviders = Object.keys(registry).length > 0
    ? Object.keys(registry)
    : ["gemini", "ollama", "openai", "anthropic", "openrouter"]

  const currentModels = registry[activeTab]?.models || [
    ...(activeTab === "openai"
      ? ["gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"]
      : activeTab === "anthropic"
      ? ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
      : activeTab === "gemini"
      ? ["gemini-3.8-flash", "gemini-3.1-pro-preview"]
      : activeTab === "ollama"
      ? ["gemma4:e4b"]
      : [
          "anthropic/claude-fable-5.1",
          "anthropic/claude-opus-5.5",
          "anthropic/claude-sonnet-5.5",
          "anthropic/claude-haiku-5.5",
          "openai/gpt-6-astra",
          "openai/gpt-6.1-sol",
          "openai/gpt-6.1-luna",
          "google/gemini-3.8-flash",
          "google/gemini-3.1-pro-preview",
        ]),
  ]

  const isModelChosen = Boolean(selectedModel && selectedProvider)

  const displayLabel = React.useMemo(() => {
    if (!isModelChosen) return "Select Model"
    const friendlyName = formatModelName(selectedModel)
    if (!reasoningLevel) return `${friendlyName} · Select Effort`
    const levelStr = (reasoningLevel === "hard" || reasoningLevel === "high")
      ? "High"
      : reasoningLevel.charAt(0).toUpperCase() + reasoningLevel.slice(1)
    return `${friendlyName} · ${levelStr}`
  }, [isModelChosen, selectedModel, reasoningLevel])

  const updateMenuPosition = React.useCallback(() => {
    const button = buttonRef.current
    if (!button || typeof window === "undefined") return

    const rect = button.getBoundingClientRect()
    const viewportPadding = 12
    const menuWidth = Math.min(340, window.innerWidth - viewportPadding * 2)
    const maxHeight = Math.max(340, Math.min(500, rect.top - viewportPadding - 12))
    const bottom = window.innerHeight - rect.top + 10

    const left = Math.max(
      viewportPadding,
      Math.min(
        rect.left,
        window.innerWidth - menuWidth - viewportPadding
      )
    )

    setMenuPosition({
      bottom,
      left,
      width: menuWidth,
      maxHeight,
      placement: "top",
    })
  }, [])

  React.useEffect(() => {
    if (!open) {
      setMenuPosition(null)
      return
    }

    updateMenuPosition()

    function onDoc(e) {
      const target = e.target
      if (
        wrapRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return
      }
      setOpen(false)
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false)
    }
    function onViewportChange() {
      updateMenuPosition()
    }

    document.addEventListener("mousedown", onDoc)
    document.addEventListener("keydown", onKey)
    window.addEventListener("resize", onViewportChange)
    window.addEventListener("scroll", onViewportChange, true)

    return () => {
      document.removeEventListener("mousedown", onDoc)
      document.removeEventListener("keydown", onKey)
      window.removeEventListener("resize", onViewportChange)
      window.removeEventListener("scroll", onViewportChange, true)
    }
  }, [open, updateMenuPosition, setOpen])

  React.useLayoutEffect(() => {
    if (!open) return
    updateMenuPosition()
  }, [open, updateMenuPosition])

  const handleSelectProvider = (newProvider) => {
    setActiveTab(newProvider)
  }

  const handleSelectModel = async (newModel) => {
    try {
      if (typeof window !== "undefined") {
        localStorage.setItem("6clips_ai_provider", activeTab)
        localStorage.setItem("6clips_ai_model", newModel)
      }
      await updateSettings({
        ai_provider: activeTab,
        ai_model: newModel,
        ai_reasoning_level: reasoningLevel || null,
      })
      onSelectModel?.(activeTab, newModel)
      showSnackbar(`Selected: ${formatModelName(newModel)} (${PROVIDER_NAMES[activeTab] || activeTab})`, "success")
    } catch {
      // handled
    }
  }

  const menu =
    open && menuPosition
      ? createPortal(
          <AnimatePresence>
            <motion.div
              key={listboxId}
              ref={menuRef}
              role="listbox"
              id={listboxId}
              initial={{
                opacity: 0,
                y: 8,
                scale: 0.94,
                filter: "blur(6px)",
              }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
              exit={{
                opacity: 0,
                y: 8,
                scale: 0.96,
                filter: "blur(4px)",
              }}
              transition={{ type: "spring", stiffness: 420, damping: 26 }}
              className={cn(
                "fixed isolate z-[9999] overflow-hidden rounded-2xl border border-black/[0.08]",
                "bg-[radial-gradient(ellipse_90%_70%_at_50%_-10%,#ffffff_0%,#f4f4f5_72%)]",
                "shadow-[0_1px_2px_rgba(0,0,0,.06),0_20px_50px_-16px_rgba(0,0,0,.2)]",
                "dark:border-white/[0.08] dark:bg-[radial-gradient(ellipse_90%_70%_at_50%_-10%,#1c1a19_0%,#11100f_72%)]",
                "dark:shadow-[0_1px_2px_rgba(0,0,0,.4),0_20px_50px_-14px_rgba(0,0,0,.75)]"
              )}
              style={{
                bottom: menuPosition.bottom,
                left: menuPosition.left,
                width: menuPosition.width,
                maxHeight: menuPosition.maxHeight,
                padding: "14px 14px 14px 14px",
                boxSizing: "border-box",
                borderRadius: "20px",
                transformOrigin: "bottom left",
                willChange: "transform, opacity, filter",
              }}
            >
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-[0.04] mix-blend-overlay dark:opacity-[0.055]"
                style={{
                  backgroundImage: LIQUID_MATTE_NOISE,
                  backgroundSize: "240px 240px",
                }}
              />

              {/* Provider Tabs Header */}
              <div className="relative z-10 mb-3 px-0.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1.5">
                  AI Provider
                </span>
                <div className="flex items-center gap-1 p-0.5 rounded-lg bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
                  {availableProviders.map((p) => {
                    const isTabActive = p === activeTab
                    return (
                      <button
                        key={p}
                        type="button"
                        onClick={() => handleSelectProvider(p)}
                        className={cn(
                          "flex-1 py-1 px-1.5 text-[11px] font-medium rounded-md transition-all text-center truncate cursor-pointer",
                          isTabActive
                            ? "bg-white dark:bg-white/10 text-[var(--foreground)] shadow-xs font-semibold"
                            : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        )}
                      >
                        {PROVIDER_NAMES[p] || p}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Models List */}
              <div className="relative z-10">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] px-0.5 block mb-1.5">
                  Available Models
                </span>
                <LayoutGroup id="liquid-model-menu">
                  <div
                    style={{
                      maxHeight: Math.max(160, menuPosition.maxHeight - 170),
                      overflowY: "auto",
                      paddingBottom: "4px",
                    }}
                    className="overscroll-contain flex flex-col gap-1 pr-0.5"
                  >
                    {currentModels.map((m) => {
                      const isModelActive = activeTab === selectedProvider && m === selectedModel
                      const friendlyTitle = formatModelName(m)
                      return (
                        <button
                          key={m}
                          role="option"
                          aria-selected={isModelActive}
                          onClick={() => handleSelectModel(m)}
                          className={cn(
                            "group/opt relative flex w-full items-center justify-between rounded-xl px-2.5 py-2 text-left outline-none transition-colors cursor-pointer",
                            isModelActive
                              ? "bg-black/10 dark:bg-white/10 text-[var(--foreground)] font-semibold"
                              : "text-[var(--foreground)] hover:bg-black/5 dark:hover:bg-white/5"
                          )}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 pr-2">
                            <span
                              className={cn(
                                "grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs",
                                isModelActive
                                  ? "bg-black/15 dark:bg-white/20 text-[var(--foreground)]"
                                  : "bg-black/5 dark:bg-white/5 text-[var(--muted-foreground)]"
                              )}
                            >
                              <IconCpu size={15} />
                            </span>
                            <div className="min-w-0 flex flex-col">
                              <span className="text-[12.5px] truncate font-medium leading-tight">
                                {friendlyTitle}
                              </span>
                              <span className="text-[9.5px] text-[var(--muted-foreground)] leading-tight mt-0.5 truncate">
                                {m}
                              </span>
                            </div>
                          </div>

                          {isModelActive && (
                            <motion.span
                              key="check"
                              initial={{ scale: 0, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              exit={{ scale: 0, opacity: 0 }}
                              className="shrink-0 mr-1 text-[var(--foreground)]"
                            >
                              <IconCheck size={15} stroke={2.5} />
                            </motion.span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                </LayoutGroup>
              </div>

              {/* Reasoning Selection Inside Dropdown */}
              <div className="relative z-10 mt-3 pt-2.5 border-t border-black/[0.08] dark:border-white/[0.08]">
                <div className="flex items-center justify-between mb-1.5 px-0.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Reasoning Effort
                  </span>
                  <span className="text-[10px] font-semibold capitalize text-slate-700 dark:text-slate-300">
                    {reasoningLevel === "hard" || reasoningLevel === "high"
                      ? "High"
                      : reasoningLevel
                        ? reasoningLevel.charAt(0).toUpperCase() + reasoningLevel.slice(1)
                        : "Not set"}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1 p-0.5 rounded-lg bg-black/5 dark:bg-white/5 border border-black/5 dark:border-white/5">
                  {[
                    { id: "low", label: "Low" },
                    { id: "medium", label: "Medium" },
                    { id: "high", label: "High" },
                  ].map(({ id, label }) => {
                    const isLvlSelected = reasoningLevel === id || (id === "high" && reasoningLevel === "hard")
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectReasoning?.(id)
                        }}
                        className={cn(
                          "py-1 px-2 text-[11px] font-medium rounded-md transition-all text-center cursor-pointer",
                          isLvlSelected
                            ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 font-semibold shadow-xs"
                            : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                        )}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </motion.div>
          </AnimatePresence>,
          document.body
        )
      : null

  return (
    <div ref={wrapRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={isModelChosen ? `Model: ${displayLabel}` : "Select Model"}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium transition-all duration-200 cursor-pointer select-none",
          isModelChosen
            ? "bg-black/5 text-slate-800 dark:bg-white/10 dark:text-slate-200 border border-black/10 dark:border-white/10 hover:bg-black/10 dark:hover:bg-white/15"
            : "bg-black/5 text-slate-700 dark:bg-white/5 dark:text-slate-300 border border-black/10 dark:border-white/10 hover:bg-black/10 dark:hover:bg-white/10",
          open && "ring-2 ring-black/10 dark:ring-white/10"
        )}
      >
        <span className="max-w-[180px] truncate">{displayLabel}</span>
        <motion.span
          aria-hidden
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="inline-flex text-inherit opacity-70"
          style={{ willChange: "transform" }}
        >
          <IconChevronDown size={12} />
        </motion.span>
      </button>
      {menu}
    </div>
  )
}

export default LiquidMultimodalInput
