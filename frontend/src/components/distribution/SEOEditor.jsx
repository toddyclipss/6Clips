// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState } from "react"
import {
  Box,
  Typography,
  Stack,
  TextField,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  IconButton,
  Button,
} from "@mui/material"
import {
  IconTag,
  IconPlus,
  IconX,
  IconSparkles,
  IconAlertTriangle,
} from "@tabler/icons-react"

const PLATFORM_LIMITS = {
  youtube: { titleMax: 100, descMax: 5000, hasTags: true, visibilities: ["public", "unlisted", "private"] },
  tiktok: { titleMax: 2200, descMax: 2200, hasTags: false, visibilities: ["public", "friends", "private"] },
  instagram: { titleMax: 2200, descMax: 2200, hasTags: false, visibilities: ["public", "private"] },
  x: { titleMax: 280, descMax: 280, hasTags: false, visibilities: ["public"] },
}

export default function SEOEditor({ metadata, onChange, onGenerateDraft }) {
  const [newTagInput, setNewTagInput] = useState("")
  const platform = (metadata.platform || "youtube").toLowerCase()
  const limits = PLATFORM_LIMITS[platform] || PLATFORM_LIMITS.youtube

  const handleTitleChange = (e) => {
    onChange({ ...metadata, title: e.target.value, is_ai_draft: false })
  }

  const handleDescChange = (e) => {
    onChange({ ...metadata, description: e.target.value, is_ai_draft: false })
  }

  const handleVisibilityChange = (e) => {
    onChange({ ...metadata, visibility: e.target.value })
  }

  const addHashtag = () => {
    if (!newTagInput.trim()) return
    let tag = newTagInput.trim().replace(/^#+/, "")
    if (!tag) return
    const formatted = `#${tag}`
    if (!metadata.hashtags?.includes(formatted)) {
      onChange({
        ...metadata,
        hashtags: [...(metadata.hashtags || []), formatted],
      })
    }
    setNewTagInput("")
  }

  const removeHashtag = (tagToRemove) => {
    onChange({
      ...metadata,
      hashtags: (metadata.hashtags || []).filter((t) => t !== tagToRemove),
    })
  }

  const titleLen = metadata.title?.length || 0
  const descLen = metadata.description?.length || 0
  const isTitleOver = titleLen > limits.titleMax
  const isDescOver = descLen > limits.descMax

  return (
    <Box sx={{ p: 2.5, borderRadius: "16px", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, textTransform: "capitalize" }}>
          {platform} SEO & Metadata
        </Typography>
        {metadata.is_ai_draft && (
          <Chip
            size="small"
            icon={<IconSparkles size={14} />}
            label="AI Draft (Unedited)"
            color="secondary"
            variant="outlined"
          />
        )}
      </Stack>

      <Stack spacing={2.5}>
        {/* Title Input */}
        <Box>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              {platform === "x" ? "Post Text" : "Title / Hook"}
            </Typography>
            <Typography
              variant="caption"
              color={isTitleOver ? "error.main" : "text.secondary"}
              sx={{ fontWeight: isTitleOver ? 700 : 400 }}
            >
              {titleLen} / {limits.titleMax} chars
            </Typography>
          </Stack>
          <TextField
            fullWidth
            size="small"
            placeholder={platform === "x" ? "What's happening?" : "Catchy title..."}
            value={metadata.title || ""}
            onChange={handleTitleChange}
            error={isTitleOver}
            helperText={isTitleOver ? `Exceeds platform limit of ${limits.titleMax} characters` : ""}
          />
        </Box>

        {/* Description Input (if distinct from title) */}
        {platform !== "x" && (
          <Box>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 600 }}>
                {platform === "tiktok" ? "Caption & Tags" : "Description"}
              </Typography>
              <Typography
                variant="caption"
                color={isDescOver ? "error.main" : "text.secondary"}
                sx={{ fontWeight: isDescOver ? 700 : 400 }}
              >
                {descLen} / {limits.descMax} chars
              </Typography>
            </Stack>
            <TextField
              fullWidth
              multiline
              rows={4}
              size="small"
              placeholder="Engaging summary, call-to-action, links..."
              value={metadata.description || ""}
              onChange={handleDescChange}
              error={isDescOver}
            />
          </Box>
        )}

        {/* Hashtags Section */}
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 600, display: "block", mb: 0.5 }}>
            Hashtags
          </Typography>
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <TextField
              size="small"
              placeholder="Add tag (e.g. viral, ai, clips)"
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addHashtag())}
              sx={{ flex: 1 }}
            />
            <Button variant="outlined" size="small" onClick={addHashtag} startIcon={<IconPlus size={16} />}>
              Add
            </Button>
          </Stack>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.8 }}>
            {(metadata.hashtags || []).map((ht) => (
              <Chip
                key={ht}
                size="small"
                label={ht}
                onDelete={() => removeHashtag(ht)}
                deleteIcon={<IconX size={14} />}
              />
            ))}
            {(!metadata.hashtags || metadata.hashtags.length === 0) && (
              <Typography variant="caption" color="text.secondary">
                No hashtags added.
              </Typography>
            )}
          </Box>
        </Box>

        {/* Visibility Setting */}
        <FormControl fullWidth size="small">
          <InputLabel>Visibility</InputLabel>
          <Select
            value={metadata.visibility || limits.visibilities[0]}
            label="Visibility"
            onChange={handleVisibilityChange}
          >
            {limits.visibilities.map((v) => (
              <MenuItem key={v} value={v} sx={{ textTransform: "capitalize" }}>
                {v}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Draft Generator Trigger */}
        {onGenerateDraft && (
          <Button
            variant="text"
            size="small"
            startIcon={<IconSparkles size={16} />}
            onClick={() => onGenerateDraft(platform)}
            sx={{ alignSelf: "flex-start", borderRadius: "20px" }}
          >
            Regenerate AI Draft for {platform}
          </Button>
        )}
      </Stack>
    </Box>
  )
}
