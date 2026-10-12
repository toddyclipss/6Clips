import * as React from "react"
import { motion, AnimatePresence, LayoutGroup } from "framer-motion"
import { createPortal } from "react-dom"
import {
  IconPaperclip,
  IconArrowUp,
  IconX,
  IconRocket,
  IconBulb,
  IconSparkles,
  IconCheck,
  IconChevronDown,
  IconFileDescription,
  IconCpu,
} from "@tabler/icons-react"
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import http from "../../api/http"
import useAppStore from "../../store/appStore"
import useSettings from "../../hooks/useSettings"

function cn(...inputs) {
  return twMerge(clsx(inputs))
}

const LIQUID_MATTE_NOISE = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.65 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>")`

const PROVIDER_NAMES = {
  openai: "OpenAI",
  anthropic: "Anthropic",
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

  const { settings } = useSettings()
  const [registry, setRegistry] = React.useState({})

  React.useEffect(() => {
    http
      .get("/api/config/model_registry")
      .then(({ data }) => setRegistry(data?.value || {}))
      .catch(() => {})
  }, [])

  const currentProvider = settings?.ai_provider || "openai"
  const defaultModel = registry[currentProvider]?.default_model || ""
  const effectiveModel = settings?.ai_model || defaultModel
  const modelMetadata = registry[currentProvider]?.model_metadata?.[effectiveModel] || registry.ollama?.model_metadata?.[effectiveModel]
  const thinkingCap = modelMetadata?.thinking
  const hasThinkingCapability = Boolean(thinkingCap && Array.isArray(thinkingCap.values) && thinkingCap.values.length > 1)

  const [thinking, setThinking] = React.useState(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem("viralmint_thinking_" + effectiveModel) : null
    if (stored !== null) return stored === "true"
    return thinkingCap?.default ?? true
  })

  React.useEffect(() => {
    if (typeof window === "undefined") return
    const stored = localStorage.getItem("viralmint_thinking_" + effectiveModel)
    if (stored !== null) {
      setThinking(stored === "true")
    } else if (thinkingCap) {
      setThinking(thinkingCap.default ?? true)
    }
  }, [effectiveModel, thinkingCap])

  const toggleThinking = () => {
    setThinking((prev) => {
      const next = !prev
      if (typeof window !== "undefined") {
        localStorage.setItem("viralmint_thinking_" + effectiveModel, String(next))
      }
      return next
    })
  }

  function submit() {
    if ((!value.trim() && files.length === 0) || disabled) return
    onSubmit?.(value, files.map((f) => f.file), hasThinkingCapability ? thinking : undefined)
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
              "conic-gradient(from 0deg, #8b5cf6, #c084fc, #8b5cf6, #7c3aed, #8b5cf6)",
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
            dragOver && "border-purple-500/45 dark:border-purple-500/45"
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
            className="lmi-border pointer-events-none absolute inset-0 z-10 opacity-40 transition-opacity duration-500 group-focus-within:opacity-100 group-hover:opacity-100"
            style={{
              borderRadius: "22px",
              padding: "1px",
              WebkitMask:
                "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
              WebkitMaskComposite: "xor",
              maskComposite: "exclude",
              background:
                "conic-gradient(from var(--lmi-angle, 0deg), transparent 65%, rgba(139,92,246,0.6) 80%, #c084fc 95%, transparent 100%)",
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

              <ModelSelector registry={registry} setRegistry={setRegistry} />

              {hasThinkingCapability && (
                <button
                  type="button"
                  onClick={toggleThinking}
                  aria-label={`Thinking: ${thinking ? "On" : "Off"}`}
                  className={cn(
                    "inline-flex h-7 items-center gap-1 rounded-full px-2 text-[12px] font-medium transition-all duration-200 cursor-pointer select-none",
                    thinking
                      ? "bg-purple-500/15 text-purple-700 dark:bg-purple-400/20 dark:text-purple-300 border border-purple-500/30"
                      : "bg-black/5 text-slate-500 dark:bg-white/5 dark:text-slate-400 border border-transparent hover:bg-black/10 dark:hover:bg-white/10"
                  )}
                >
                  <IconBulb size={13} className={thinking ? "text-purple-600 dark:text-purple-400" : "text-slate-400"} />
                  <span>Thinking: {thinking ? "On" : "Off"}</span>
                </button>
              )}
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
                  "bg-gradient-to-br from-[#8b5cf6] to-[#a78bfa] text-white shadow-[0_2px_8px_-2px_rgba(139,92,246,0.4)]",
                  "hover:opacity-95 hover:shadow-[0_4px_12px_-2px_rgba(139,92,246,0.6)]",
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
                <div className="flex items-center gap-2 rounded-full border border-purple-500/20 bg-white px-4 py-2 text-xs font-semibold text-purple-700 shadow-xl dark:border-purple-500/30 dark:bg-[#1a1a1a] dark:text-purple-400">
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

function ModelSelector({ registry: passedRegistry, setRegistry: passedSetRegistry }) {
  const [open, setOpen] = React.useState(false)
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

  const provider = settings?.ai_provider || "openai"
  const model = settings?.ai_model || ""

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
    : ["openai", "anthropic", "openrouter", "ollama"]

  const currentModels = registry[provider]?.models || [
    ...(provider === "openai"
      ? ["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"]
      : provider === "anthropic"
      ? ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]
      : provider === "ollama"
      ? ["gemma4:e4b"]
      : ["anthropic/claude-opus-4.7", "openai/gpt-5.5", "google/gemini-3.1-pro-preview"]),
  ]
  const defaultModel = registry[provider]?.default_model || currentModels[0] || ""
  const effectiveModel = model || defaultModel

  // Format a friendly display label for the button
  const displayLabel = React.useMemo(() => {
    if (!effectiveModel) return "Model"
    const parts = effectiveModel.split("/")
    const name = parts[parts.length - 1]
    return name
      .replace(/^claude-/, "Claude ")
      .replace(/^gpt-/, "GPT-")
      .replace(/^gemini-/, "Gemini ")
      .replace(/^gemma4:/, "Gemma 4 ")
  }, [effectiveModel])

  const updateMenuPosition = React.useCallback(() => {
    const button = buttonRef.current
    if (!button || typeof window === "undefined") return

    const rect = button.getBoundingClientRect()
    const viewportPadding = 12
    const menuWidth = Math.min(330, window.innerWidth - viewportPadding * 2)
    // Anchored directly ABOVE the button with comfortable clearance:
    const maxHeight = Math.max(300, Math.min(460, rect.top - viewportPadding - 12))
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
  }, [open, updateMenuPosition])

  React.useLayoutEffect(() => {
    if (!open) return
    updateMenuPosition()
  }, [open, updateMenuPosition])

  const handleSelectProvider = async (newProvider) => {
    const def = registry[newProvider]?.default_model || ""
    try {
      await updateSettings({ ai_provider: newProvider, ai_model: def })
      showSnackbar(`Provider set to ${PROVIDER_NAMES[newProvider] || newProvider}`, "info")
    } catch {
      // updateSettings handles error notification
    }
  }

  const handleSelectModel = async (newModel) => {
    try {
      await updateSettings({ ai_provider: provider, ai_model: newModel })
      setOpen(false)
      showSnackbar(`Model: ${newModel}`, "success")
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
                    const isSelected = p === provider
                    return (
                      <button
                        key={p}
                        type="button"
                        onClick={() => handleSelectProvider(p)}
                        className={cn(
                          "flex-1 py-1 px-1.5 text-[11px] font-medium rounded-md transition-all text-center truncate cursor-pointer",
                          isSelected
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
                      maxHeight: Math.max(240, menuPosition.maxHeight - 110),
                      overflowY: "auto",
                      paddingBottom: "4px",
                    }}
                    className="overscroll-contain flex flex-col gap-1 pr-0.5"
                  >
                    {currentModels.map((m) => {
                      const isSelected = m === effectiveModel
                      const isDefault = m === defaultModel
                      return (
                        <button
                          key={m}
                          role="option"
                          aria-selected={isSelected}
                          onClick={() => handleSelectModel(m)}
                          className={cn(
                            "group/opt relative flex w-full items-center justify-between rounded-xl px-2.5 py-2 text-left outline-none transition-colors cursor-pointer",
                            isSelected
                              ? "bg-purple-500/10 text-purple-700 dark:bg-purple-400/10 dark:text-purple-400 font-medium"
                              : "text-[var(--foreground)] hover:bg-black/5 dark:hover:bg-white/5"
                          )}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 pr-2">
                            <span
                              className={cn(
                                "grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs",
                                isSelected
                                  ? "bg-purple-500/20 text-purple-700 dark:text-purple-400"
                                  : "bg-black/5 dark:bg-white/5 text-[var(--muted-foreground)]"
                              )}
                            >
                              <IconCpu size={15} />
                            </span>
                            <div className="min-w-0 flex flex-col">
                              <span className="text-[12.5px] truncate font-medium leading-tight">
                                {m}
                              </span>
                              {isDefault && (
                                <span className="text-[9.5px] text-[var(--muted-foreground)] leading-tight mt-0.5">
                                  Default
                                </span>
                              )}
                            </div>
                          </div>

                          {isSelected && (
                            <motion.span
                              key="check"
                              initial={{ scale: 0, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              exit={{ scale: 0, opacity: 0 }}
                              className="text-purple-600 dark:text-purple-400 shrink-0 mr-1"
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
        aria-label={`Model: ${displayLabel}`}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex h-7 items-center gap-1 rounded-full px-2 text-[12px] font-medium transition-all duration-200",
          "bg-transparent text-slate-600 hover:text-slate-900 hover:bg-black/5",
          "dark:text-slate-300 dark:hover:text-white dark:hover:bg-white/10",
          open && "bg-black/5 text-slate-900 dark:bg-white/10 dark:text-white"
        )}
      >
        <span className="text-purple-600 dark:text-purple-400">
          <IconSparkles size={14} />
        </span>
        <span className="max-w-[160px] truncate">{displayLabel}</span>
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
