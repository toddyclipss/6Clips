import { useState, useEffect } from "react"
import {
  Box, Stack, Typography, Alert, TextField, Button, FormControl, InputLabel,
  Select, MenuItem, IconButton, InputAdornment, Chip, Card, CardContent, Divider,
  ToggleButtonGroup, ToggleButton,
} from "@mui/material"
import {
  IconEye,
  IconEyeOff,
  IconDeviceFloppy,
  IconTrash,
  IconCircleCheck,
  IconAlertTriangle,
  IconCpu,
  IconRefresh,
} from "@tabler/icons-react"
import http from "../../api/http"
import { fetchModelRegistry, invalidateModelRegistryCache } from "../../api/modelRegistry"
import useAppStore from "../../store/appStore"
import { formatModelName } from "../chat/LiquidMultimodalInput"

const PROVIDER_METADATA = {
  openai: {
    id: "openai",
    name: "OpenAI",
    placeholder: "sk-...",
    hint: "platform.openai.com → API Keys",
    keyField: "openai_api_key",
    flagField: "openai_api_key_set",
  },
  anthropic: {
    id: "anthropic",
    name: "Anthropic",
    placeholder: "sk-ant-...",
    hint: "console.anthropic.com → API Keys",
    keyField: "anthropic_api_key",
    flagField: "anthropic_api_key_set",
  },
  gemini: {
    id: "gemini",
    name: "Google Gemini",
    placeholder: "AIzaSy...",
    hint: "aistudio.google.com → Get API key (Gemini 3.8 Flash & Gemini 3.1 Pro Preview)",
    keyField: "gemini_api_key",
    flagField: "gemini_api_key_set",
  },
  openrouter: {
    id: "openrouter",
    name: "OpenRouter",
    placeholder: "sk-or-...",
    hint: "openrouter.ai/keys (Multi-provider gateway)",
    keyField: "openrouter_api_key",
    flagField: "openrouter_api_key_set",
  },
  ollama: {
    id: "ollama",
    name: "Ollama (Local Engine)",
    placeholder: "http://127.0.0.1:11434",
    hint: "Local or authorized remote Ollama daemon — zero API key required",
    keyField: "ollama_base_url",
    flagField: "ollama_connected",
  },
}

export default function AIProviderSection({ settings, updateSettings }) {
  const showSnackbar = useAppStore((s) => s.showSnackbar)

  // Active Model Selection state (synchronized bidirectionally with Global Chat)
  const [activeProvider, setActiveProvider] = useState(settings?.ai_provider || "")
  const [activeModel, setActiveModel] = useState(settings?.ai_model || "")
  const [activeReasoning, setActiveReasoning] = useState(() => {
    const lvl = settings?.ai_reasoning_level?.toLowerCase()
    if (!lvl) return ""
    return (lvl === "high" || lvl === "hard") ? "hard" : lvl
  })

  const [registry, setRegistry] = useState({})
  const [savingActive, setSavingActive] = useState(false)

  // Independent API key input state
  const [keysInput, setKeysInput] = useState({
    openai: "",
    anthropic: "",
    gemini: "",
    openrouter: "",
    ollama: settings?.ollama_base_url || "http://127.0.0.1:11434",
  })

  const [showKeys, setShowKeys] = useState({
    openai: false,
    anthropic: false,
    gemini: false,
    openrouter: false,
  })

  const [validating, setValidating] = useState({})
  const [actionLoading, setActionLoading] = useState({})

  // Fetch model registry with caching and in-flight deduplication
  const fetchRegistry = (force = false) => {
    return fetchModelRegistry({ force })
      .then((reg) => setRegistry(reg || {}))
      .catch(() => {})
  }

  useEffect(() => {
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

  // Sync state when settings change
  useEffect(() => {
    if (settings) {
      setActiveProvider(settings.ai_provider || "")
      setActiveModel(settings.ai_model || "")
      const lvl = settings.ai_reasoning_level?.toLowerCase()
      setActiveReasoning(lvl ? ((lvl === "high" || lvl === "hard") ? "high" : lvl) : "")
      if (settings.ollama_base_url) {
        setKeysInput((prev) => ({ ...prev, ollama: settings.ollama_base_url }))
      }
    }
  }, [settings?.ai_provider, settings?.ai_model, settings?.ai_reasoning_level, settings?.ollama_base_url])

  // Handle active selection save
  const handleSaveActiveSelection = async (newProv, newMod, newLvl) => {
    const p = newProv !== undefined ? newProv : activeProvider
    const m = newMod !== undefined ? newMod : activeModel
    const r = newLvl !== undefined ? newLvl : activeReasoning

    setSavingActive(true)
    try {
      await updateSettings({
        ai_provider: p || null,
        ai_model: m || null,
        ai_reasoning_level: r || null,
      })
      if (typeof window !== "undefined") {
        if (p) localStorage.setItem("6clips_ai_provider", p)
        else localStorage.removeItem("6clips_ai_provider")
        if (m) localStorage.setItem("6clips_ai_model", m)
        else localStorage.removeItem("6clips_ai_model")
        if (r) localStorage.setItem("6clips_ai_reasoning", r)
        else localStorage.removeItem("6clips_ai_reasoning")
      }
      showSnackbar("Active AI model and reasoning synchronized", "success")
    } catch {
      // handled in updateSettings
    } finally {
      setSavingActive(false)
    }
  }

  // Handle key validation (zero paid inference calls)
  const handleValidateCredential = async (providerId) => {
    setValidating((prev) => ({ ...prev, [providerId]: true }))
    try {
      const isOllama = providerId === "ollama"
      const payload = {
        provider: providerId,
        ...(isOllama
          ? { base_url: keysInput.ollama.trim() || undefined }
          : { api_key: keysInput[providerId].trim() || undefined }),
      }

      const { data } = await http.post("/api/settings/validate-key", payload)
      if (data?.ok) {
        showSnackbar(data.message || `${PROVIDER_METADATA[providerId].name} credentials valid`, "success")
        if (isOllama) {
          invalidateModelRegistryCache()
          fetchRegistry(true)
        }
      } else {
        showSnackbar(data?.error || `Validation failed for ${PROVIDER_METADATA[providerId].name}`, "error")
      }
    } catch (e) {
      showSnackbar(`Validation error: ${e?.response?.data?.detail || e.message}`, "error")
    } finally {
      setValidating((prev) => ({ ...prev, [providerId]: false }))
    }
  }

  // Handle saving independent key without altering active provider
  const handleSaveCredential = async (providerId) => {
    setActionLoading((prev) => ({ ...prev, [providerId]: true }))
    try {
      const meta = PROVIDER_METADATA[providerId]
      const val = keysInput[providerId].trim()

      if (providerId === "ollama") {
        await updateSettings({ ollama_base_url: val || "http://127.0.0.1:11434" })
        showSnackbar("Ollama endpoint URL saved", "success")
      } else {
        if (!val) {
          showSnackbar("Enter an API key first", "warning")
          return
        }
        await updateSettings({ [meta.keyField]: val })
        setKeysInput((prev) => ({ ...prev, [providerId]: "" }))
        showSnackbar(`${meta.name} API key saved independently (provider active state preserved)`, "success")
      }
    } catch {
      // handled
    } finally {
      setActionLoading((prev) => ({ ...prev, [providerId]: false }))
    }
  }

  // Handle revoking independent key
  const handleRevokeCredential = async (providerId) => {
    setActionLoading((prev) => ({ ...prev, [providerId]: true }))
    try {
      const meta = PROVIDER_METADATA[providerId]
      await updateSettings({ [meta.keyField]: "" })
      showSnackbar(`${meta.name} API key removed`, "info")
    } catch {
      // handled
    } finally {
      setActionLoading((prev) => ({ ...prev, [providerId]: false }))
    }
  }

  const availableModelsForActiveProvider = registry[activeProvider]?.models || []

  return (
    <Stack spacing={3}>
      {/* ── Active Selection Card (Synchronized with Global Chat) ── */}
      <Card
        variant="outlined"
        sx={{
          borderRadius: "18px",
          bgcolor: "background.paper",
          borderColor: "divider",
          boxShadow: "0 2px 12px -2px rgba(0,0,0,0.05)",
        }}
      >
        <CardContent sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Box
                  sx={{
                    width: 28,
                    height: 28,
                    borderRadius: "8px",
                    display: "grid",
                    placeItems: "center",
                    bgcolor: "action.hover",
                    color: "text.primary",
                  }}
                >
                  <IconCpu size={16} />
                </Box>
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  Active Model & Reasoning Selection
                </Typography>
              </Stack>

              <Chip
                size="small"
                label={activeProvider && activeModel ? "Active Selection Ready" : "No Active Model Selected"}
                color={activeProvider && activeModel ? "success" : "default"}
                variant="outlined"
                sx={{ borderRadius: "8px", fontWeight: 500 }}
              />
            </Stack>

            <Typography variant="body2" color="text.secondary">
              Synchronized two-way with the Global Chat selector. There is zero default model or silent fallback.
            </Typography>

            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
              {/* Provider Selection */}
              <FormControl size="small" sx={{ minWidth: 160, flex: 1 }}>
                <InputLabel id="active-provider-label">AI Provider</InputLabel>
                <Select
                  labelId="active-provider-label"
                  label="AI Provider"
                  value={activeProvider}
                  onChange={(e) => {
                    const p = e.target.value
                    setActiveProvider(p)
                    const firstModel = registry[p]?.models?.[0] || ""
                    setActiveModel(firstModel)
                    handleSaveActiveSelection(p, firstModel, activeReasoning)
                  }}
                >
                  <MenuItem value="">
                    <em>Select Provider</em>
                  </MenuItem>
                  {Object.values(PROVIDER_METADATA).map((meta) => (
                    <MenuItem key={meta.id} value={meta.id}>
                      {meta.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Model Selection */}
              <FormControl size="small" sx={{ minWidth: 200, flex: 1.5 }} disabled={!activeProvider}>
                <InputLabel id="active-model-label">Model</InputLabel>
                <Select
                  labelId="active-model-label"
                  label="Model"
                  value={activeModel}
                  onChange={(e) => {
                    const m = e.target.value
                    setActiveModel(m)
                    handleSaveActiveSelection(activeProvider, m, activeReasoning)
                  }}
                >
                  {availableModelsForActiveProvider.map((m) => (
                    <MenuItem key={m} value={m}>
                      {formatModelName(m)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Reasoning Level: strictly low, medium, high */}
              <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                <Typography variant="caption" sx={{ fontWeight: 600, color: "text.secondary" }}>
                  Reasoning Effort
                </Typography>
                <ToggleButtonGroup
                  size="small"
                  exclusive
                  value={activeReasoning}
                  onChange={(_, val) => {
                    if (val) {
                      setActiveReasoning(val)
                      handleSaveActiveSelection(activeProvider, activeModel, val)
                    }
                  }}
                >
                  <ToggleButton value="low" sx={{ textTransform: "none", px: 1.5, py: 0.5, fontWeight: 500 }}>
                    Low
                  </ToggleButton>
                  <ToggleButton value="medium" sx={{ textTransform: "none", px: 1.5, py: 0.5, fontWeight: 500 }}>
                    Medium
                  </ToggleButton>
                  <ToggleButton value="high" sx={{ textTransform: "none", px: 1.5, py: 0.5, fontWeight: 500 }}>
                    High
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {/* ── Section Header ── */}
      <Box>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Bring Your Own Key (BYOK) Credentials
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Configure API keys independently. Storing credentials does not automatically switch or activate that provider.
        </Typography>
      </Box>

      {/* ── Independent Provider Cards ── */}
      <Stack spacing={2}>
        {Object.values(PROVIDER_METADATA).map((meta) => {
          const isOllama = meta.id === "ollama"
          const isConfigured = Boolean(settings?.[meta.flagField])
          const showKey = showKeys[meta.id]
          const isVal = validating[meta.id]
          const isAct = actionLoading[meta.id]

          return (
            <Card
              key={meta.id}
              variant="outlined"
              sx={{
                borderRadius: "16px",
                borderColor: "divider",
                bgcolor: "background.paper",
                transition: "all 0.15s ease",
              }}
            >
              <CardContent sx={{ p: 2 }}>
                <Stack spacing={2}>
                  {/* Top row: Icon, Name, Status Badge */}
                  <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
                    <Stack direction="row" alignItems="center" spacing={1.2}>
                      <Box
                        sx={{
                          width: 32,
                          height: 32,
                          borderRadius: "10px",
                          display: "grid",
                          placeItems: "center",
                          bgcolor: "action.hover",
                          color: "text.primary",
                        }}
                      >
                        <IconCpu size={18} />
                      </Box>
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {meta.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {meta.hint}
                        </Typography>
                      </Box>
                    </Stack>

                    <Chip
                      size="small"
                      icon={isConfigured ? <IconCircleCheck size={14} /> : undefined}
                      label={
                        isOllama
                          ? (isConfigured ? "Daemon Reachable" : "Unreachable")
                          : (isConfigured ? "Configured" : "Not configured")
                      }
                      color={isConfigured ? "success" : "default"}
                      variant="outlined"
                      sx={{ borderRadius: "8px", fontWeight: 500 }}
                    />
                  </Stack>

                  {/* Input and Action Buttons */}
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems="center">
                    <TextField
                      size="small"
                      fullWidth
                      type={isOllama || showKey ? "text" : "password"}
                      placeholder={isConfigured ? (isOllama ? meta.placeholder : "••••••••••••••••") : meta.placeholder}
                      value={keysInput[meta.id]}
                      onChange={(e) => setKeysInput({ ...keysInput, [meta.id]: e.target.value })}
                      InputProps={{
                        endAdornment: !isOllama ? (
                          <InputAdornment position="end">
                            <IconButton
                              size="small"
                              onClick={() => setShowKeys({ ...showKeys, [meta.id]: !showKey })}
                            >
                              {showKey ? <IconEyeOff size={16} /> : <IconEye size={16} />}
                            </IconButton>
                          </InputAdornment>
                        ) : null,
                      }}
                    />

                    <Stack direction="row" spacing={1} sx={{ shrink: 0 }}>
                      {/* Validate Button (Zero Cost) */}
                      <Button
                        size="small"
                        variant="outlined"
                        disabled={isVal || (!isConfigured && !keysInput[meta.id].trim() && !isOllama)}
                        onClick={() => handleValidateCredential(meta.id)}
                        sx={{ borderRadius: "10px", textTransform: "none", minWidth: 80 }}
                      >
                        {isVal ? "Testing..." : (isOllama ? "Test" : "Validate")}
                      </Button>

                      {/* Save Key Button */}
                      <Button
                        size="small"
                        variant="contained"
                        disabled={isAct || (!keysInput[meta.id].trim() && !isOllama)}
                        onClick={() => handleSaveCredential(meta.id)}
                        sx={{
                          borderRadius: "10px",
                          textTransform: "none",
                        }}
                      >
                        {isAct ? "Saving..." : (isOllama ? "Save" : "Save Key")}
                      </Button>

                      {/* Revoke Key Button */}
                      {isConfigured && !isOllama && (
                        <IconButton
                          size="small"
                          color="error"
                          disabled={isAct}
                          onClick={() => handleRevokeCredential(meta.id)}
                          aria-label={`Remove ${meta.name} key`}
                        >
                          <IconTrash size={16} />
                        </IconButton>
                      )}
                    </Stack>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          )
        })}
      </Stack>
    </Stack>
  )
}
