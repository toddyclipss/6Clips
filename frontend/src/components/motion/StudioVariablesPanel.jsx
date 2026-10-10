// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState, useEffect, useCallback, useMemo } from "react"
import {
  Box, Stack, Typography, TextField, Slider, Select, MenuItem,
  Switch, FormControlLabel, Divider, Tooltip, IconButton, Chip,
  CircularProgress, Alert, Button, InputAdornment,
} from "@mui/material"
import {
  IconSparkles,
  IconLock,
  IconPalette,
  IconAdjustments,
  IconCheck,
  IconRefresh,
  IconAlertCircle,
  IconFileCode,
} from "@tabler/icons-react"
import http from "../../api/http"

/**
 * Dedicated Variables Surface (/motion).
 * Provides a dedicated, typed parameter editor over block instance variables (clip.variables).
 * Reads and commits directly to canonical ProjectRevision via CAS operations.
 */
export default function StudioVariablesPanel({
  selectedElement = null,
  onUpdateVariables,
  onCommitVariables,
  isLocked = false,
}) {
  const [schemaVariables, setSchemaVariables] = useState([])
  const [loadingSchema, setLoadingSchema] = useState(false)
  const [localValues, setLocalValues] = useState({})
  const [validationErrors, setValidationErrors] = useState({})
  const [isSaving, setIsSaving] = useState(false)

  const blockId = selectedElement?.block_id
  const blockVersion = selectedElement?.block_version
  const clipId = selectedElement?.id
  const elementLocked = isLocked || !!selectedElement?.locked

  // 1. Fetch catalog block schema for rich typed definitions
  useEffect(() => {
    if (!blockId) {
      setSchemaVariables([])
      return
    }

    let active = true
    setLoadingSchema(true)
    http.get(`/api/projects/catalog/items/${blockId}`)
      .then((res) => {
        if (!active) return
        const vars = res.data?.variables || []
        setSchemaVariables(vars)
      })
      .catch(() => {
        if (!active) return
        // If manifest fetch fails, fall back to existing clip variables
        setSchemaVariables([])
      })
      .finally(() => {
        if (active) setLoadingSchema(false)
      })

    return () => { active = false }
  }, [blockId])

  // 2. Synchronize local edit values with selectedElement.variables
  useEffect(() => {
    if (selectedElement?.variables) {
      setLocalValues({ ...selectedElement.variables })
      setValidationErrors({})
    } else {
      setLocalValues({})
      setValidationErrors({})
    }
  }, [clipId, selectedElement?.variables])

  // 3. Merged variable definitions (from schema + any custom declared variables)
  const activeVarDefs = useMemo(() => {
    const map = new Map()
    schemaVariables.forEach((sv) => {
      map.set(sv.id, sv)
    })

    // Include any variables already defined on the clip even if missing from manifest
    if (selectedElement?.variables) {
      Object.entries(selectedElement.variables).forEach(([k, v]) => {
        if (!map.has(k)) {
          let inferType = typeof v
          if (inferType === "string" && (v.startsWith("#") || v.startsWith("rgb"))) inferType = "color"
          map.set(k, {
            id: k,
            label: k.replace(/[-_]/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
            type: inferType === "number" ? "number" : inferType === "boolean" ? "boolean" : inferType === "color" ? "color" : "string",
            default: v,
          })
        }
      })
    }

    return Array.from(map.values())
  }, [schemaVariables, selectedElement?.variables])

  // 4. Validate and handle live variable edit
  const handleValueChange = (varId, rawValue, def = null) => {
    if (elementLocked) return

    let value = rawValue
    const errors = { ...validationErrors }
    delete errors[varId]

    if (def) {
      if (def.type === "number") {
        const num = parseFloat(rawValue)
        if (isNaN(num)) {
          errors[varId] = "Must be a valid number"
        } else {
          if (def.min !== undefined && num < def.min) errors[varId] = `Min value is ${def.min}`
          if (def.max !== undefined && num > def.max) errors[varId] = `Max value is ${def.max}`
          value = num
        }
      } else if (def.type === "enum") {
        if (def.options && !def.options.includes(rawValue)) {
          errors[varId] = `Must be one of ${def.options.join(", ")}`
        }
      }
    }

    setValidationErrors(errors)
    const nextValues = { ...localValues, [varId]: value }
    setLocalValues(nextValues)

    if (onUpdateVariables && clipId) {
      onUpdateVariables(clipId, nextValues)
    }
  }

  // 5. Commit variable mutation with CAS
  const handleCommit = async (varId, finalValue, def = null) => {
    if (elementLocked) return
    if (validationErrors[varId]) return

    const patch = { [varId]: finalValue }
    if (onCommitVariables && clipId) {
      setIsSaving(true)
      try {
        await onCommitVariables(clipId, patch)
      } finally {
        setIsSaving(false)
      }
    }
  }

  // Render control by type
  const renderControl = (vdef) => {
    const val = localValues[vdef.id] !== undefined ? localValues[vdef.id] : (vdef.default ?? "")
    const err = validationErrors[vdef.id]

    switch (vdef.type) {
      case "boolean":
        return (
          <FormControlLabel
            control={
              <Switch
                size="small"
                disabled={elementLocked}
                checked={!!val}
                onChange={(e) => {
                  const checked = e.target.checked
                  handleValueChange(vdef.id, checked, vdef)
                  handleCommit(vdef.id, checked, vdef)
                }}
              />
            }
            label={
              <Typography variant="caption" sx={{ fontWeight: 600, fontSize: "0.75rem" }}>
                {val ? "Enabled" : "Disabled"}
              </Typography>
            }
          />
        )

      case "number":
        return (
          <Stack spacing={0.5}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Slider
                size="small"
                disabled={elementLocked}
                value={typeof val === "number" ? val : parseFloat(val) || 0}
                min={vdef.min !== undefined ? vdef.min : 0}
                max={vdef.max !== undefined ? vdef.max : 100}
                step={vdef.step !== undefined ? vdef.step : 1}
                onChange={(_, n) => handleValueChange(vdef.id, n, vdef)}
                onChangeCommitted={(_, n) => handleCommit(vdef.id, n, vdef)}
                sx={{ flex: 1 }}
              />
              <TextField
                size="small"
                type="number"
                disabled={elementLocked}
                value={val}
                onChange={(e) => handleValueChange(vdef.id, e.target.value, vdef)}
                onBlur={(e) => handleCommit(vdef.id, parseFloat(e.target.value) || 0, vdef)}
                sx={{
                  width: 65,
                  "& .MuiInputBase-input": { py: 0.25, px: 0.5, fontSize: "0.75rem", textAlign: "right" },
                }}
              />
            </Stack>
            {vdef.unit && (
              <Typography variant="caption" sx={{ color: "text.disabled", fontSize: "0.65rem" }}>
                Unit: {vdef.unit}
              </Typography>
            )}
          </Stack>
        )

      case "enum":
        return (
          <Select
            size="small"
            fullWidth
            disabled={elementLocked}
            value={val}
            onChange={(e) => {
              const next = e.target.value
              handleValueChange(vdef.id, next, vdef)
              handleCommit(vdef.id, next, vdef)
            }}
            sx={{ fontSize: "0.75rem", py: 0 }}
          >
            {(vdef.options || []).map((opt) => (
              <MenuItem key={opt} value={opt} sx={{ fontSize: "0.75rem" }}>
                {opt}
              </MenuItem>
            ))}
          </Select>
        )

      case "color":
        return (
          <Stack direction="row" spacing={1} alignItems="center">
            <Box
              component="input"
              type="color"
              disabled={elementLocked}
              value={typeof val === "string" && val.startsWith("#") ? val : "#ffffff"}
              onChange={(e) => handleValueChange(vdef.id, e.target.value, vdef)}
              onBlur={(e) => handleCommit(vdef.id, e.target.value, vdef)}
              sx={{
                width: 32,
                height: 28,
                p: 0,
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 1,
                cursor: elementLocked ? "not-allowed" : "pointer",
                bgcolor: "transparent",
              }}
            />
            <TextField
              size="small"
              fullWidth
              disabled={elementLocked}
              value={val}
              onChange={(e) => handleValueChange(vdef.id, e.target.value, vdef)}
              onBlur={(e) => handleCommit(vdef.id, e.target.value, vdef)}
              placeholder="#hex or color"
              sx={{ "& .MuiInputBase-input": { py: 0.4, px: 0.75, fontSize: "0.75rem" } }}
            />
          </Stack>
        )

      case "string":
      default:
        return (
          <TextField
            size="small"
            fullWidth
            disabled={elementLocked}
            value={val}
            onChange={(e) => handleValueChange(vdef.id, e.target.value, vdef)}
            onBlur={(e) => handleCommit(vdef.id, e.target.value, vdef)}
            placeholder={vdef.default || "Value..."}
            error={!!err}
            helperText={err}
            inputProps={{ maxLength: vdef.maxLength }}
            sx={{ "& .MuiInputBase-input": { py: 0.5, px: 0.75, fontSize: "0.75rem" } }}
          />
        )
    }
  }

  // Empty state: no element selected
  if (!selectedElement) {
    return (
      <Box sx={{ width: "100%", height: "100%", p: 2, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", color: "text.secondary" }}>
        <IconSparkles size={28} color="#94a3b8" style={{ marginBottom: 8 }} />
        <Typography variant="caption" sx={{ fontWeight: 700, fontSize: "0.8rem", color: "text.primary", mb: 0.5 }}>
          No Element Selected
        </Typography>
        <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.72rem", maxWidth: 220 }}>
          Select a HyperFrames block or component from the Timeline or Layers to edit its configurable variables.
        </Typography>
      </Box>
    )
  }

  // Non-block element with no variables
  if (!selectedElement.block_id && activeVarDefs.length === 0) {
    return (
      <Box sx={{ width: "100%", height: "100%", p: 2, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", color: "text.secondary" }}>
        <IconAdjustments size={28} color="#94a3b8" style={{ marginBottom: 8 }} />
        <Typography variant="caption" sx={{ fontWeight: 700, fontSize: "0.8rem", color: "text.primary", mb: 0.5 }}>
          {selectedElement.title || selectedElement.name || selectedElement.id}
        </Typography>
        <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.72rem", maxWidth: 220 }}>
          This element is a standard {selectedElement.type || "clip"} and does not declare configurable variables.
        </Typography>
      </Box>
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
            Configurable Variables
          </Typography>
          {loadingSchema ? (
            <CircularProgress size={14} />
          ) : (
            <Chip
              size="small"
              label={`${activeVarDefs.length} parameter${activeVarDefs.length !== 1 ? "s" : ""}`}
              sx={{ height: 18, fontSize: "0.65rem", fontWeight: 700, bgcolor: "rgba(139, 92, 246, 0.1)", color: "#7c3aed" }}
            />
          )}
        </Stack>
      </Box>

      {/* Target Info Bar */}
      <Box sx={{ px: 1.5, py: 1, borderBottom: "1px solid", borderColor: "divider", bgcolor: "#fafafa" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="caption" noWrap sx={{ fontWeight: 700, color: "text.primary", fontSize: "0.75rem" }}>
            {selectedElement.title || selectedElement.name || blockId}
          </Typography>
          {elementLocked ? (
            <Chip
              size="small"
              icon={<IconLock size={12} color="#dc2626" />}
              label="Locked"
              sx={{ height: 18, fontSize: "0.62rem", fontWeight: 700, bgcolor: "#fee2e2", color: "#b91c1c" }}
            />
          ) : (
            <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.68rem" }}>
              Instance: {clipId?.slice(0, 8)}
            </Typography>
          )}
        </Stack>
      </Box>

      {/* Variables List */}
      <Box sx={{ flex: 1, overflowY: "auto", p: 1.5, minHeight: 0 }}>
        {elementLocked && (
          <Alert severity="warning" sx={{ mb: 1.5, py: 0.25, fontSize: "0.72rem" }}>
            This element is locked. Unlock it in Layers or Timeline to modify its variables.
          </Alert>
        )}

        <Stack spacing={1.75}>
          {activeVarDefs.map((vdef) => (
            <Box
              key={vdef.id}
              data-variable-field={vdef.id}
              sx={{
                p: 1,
                borderRadius: 1.5,
                bgcolor: "#fdfefe",
                border: "1px solid",
                borderColor: validationErrors[vdef.id] ? "error.light" : "divider",
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "text.primary", fontSize: "0.72rem" }}>
                  {vdef.label || vdef.id}
                </Typography>
                <Chip
                  size="small"
                  label={vdef.type}
                  sx={{ height: 15, fontSize: "0.6rem", textTransform: "uppercase", px: 0.2 }}
                />
              </Stack>

              {vdef.description && (
                <Typography variant="caption" sx={{ color: "text.secondary", fontSize: "0.65rem", display: "block", mb: 0.5 }}>
                  {vdef.description}
                </Typography>
              )}

              {renderControl(vdef)}
            </Box>
          ))}
        </Stack>
      </Box>
    </Box>
  )
}
