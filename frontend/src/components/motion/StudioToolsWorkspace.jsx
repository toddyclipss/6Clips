// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
import React, { useState } from "react"
import {
  Box,
  Stack,
  Typography,
  Button,
  IconButton,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  CircularProgress,
  Tabs,
  Tab,
  Switch,
  FormControlLabel,
  Tooltip,
} from "@mui/material"
import {
  IconScissors,
  IconCrop,
  IconGauge,
  IconArrowsMinimize,
  IconAdjustments,
  IconVolume,
  IconVolumeOff,
  IconMusic,
  IconPlayerPlay,
  IconMicrophone,
  IconSubtitles,
  IconSparkles,
  IconCopy,
  IconPlus,
  IconWaveSine,
  IconLayersIntersect,
  IconPhoto,
} from "@tabler/icons-react"
import http from "../../api/http"
import useAppStore from "../../store/appStore"

const TOOL_CATEGORIES = [
  { id: "video", label: "Video & Edit" },
  { id: "audio", label: "Audio & Sound" },
  { id: "voice", label: "Voice & Speech" },
  { id: "captions", label: "Subtitles & AI" },
]

const ALL_TOOLS = [
  // Video category
  { id: "trim", label: "Trim", category: "video", icon: <IconScissors size={14} />, desc: "Bounded subclip extraction with in/out timestamps" },
  { id: "crop", label: "Crop", category: "video", icon: <IconCrop size={14} />, desc: "Spatial box coordinate cropping" },
  { id: "speed", label: "Speed", category: "video", icon: <IconGauge size={14} />, desc: "Playback speed and PTS retime" },
  { id: "reframe", label: "Reframe", category: "video", icon: <IconLayersIntersect size={14} />, desc: "16:9 to 9:16 vertical reframing" },
  { id: "compress", label: "Compress", category: "video", icon: <IconArrowsMinimize size={14} />, desc: "CRF rate-controlled size reduction" },
  { id: "transform", label: "Transform", category: "video", icon: <IconAdjustments size={14} />, desc: "Flip horizontal/vertical and 90° rotation" },
  { id: "watermark", label: "Watermark", category: "video", icon: <IconPhoto size={14} />, desc: "Overlay image watermark onto video" },
  { id: "resize", label: "Resize", category: "video", icon: <IconCrop size={14} />, desc: "Resolution scaling" },
  { id: "merge-clips", label: "Merge", category: "video", icon: <IconLayersIntersect size={14} />, desc: "Sequential concatenation of media clips" },

  // Audio category
  { id: "extract-audio", label: "Extract Audio", category: "audio", icon: <IconMusic size={14} />, desc: "Extract standalone MP3/AAC audio track" },
  { id: "remove-audio", label: "Mute / Strip", category: "audio", icon: <IconVolumeOff size={14} />, desc: "Strip audio track (-an) leaving pure video" },
  { id: "enhance-audio", label: "Enhance Voice", category: "audio", icon: <IconVolume size={14} />, desc: "Dynamic compression and highpass clarity filter" },
  { id: "silence-remover", label: "Silence Remover", category: "audio", icon: <IconWaveSine size={14} />, desc: "Trim dead silence automatically" },
  { id: "split-silence", label: "Split Silence", category: "audio", icon: <IconScissors size={14} />, desc: "Segment media on silence boundaries" },

  // Voice category
  { id: "voiceover", label: "Voiceover (TTS)", category: "voice", icon: <IconMicrophone size={14} />, desc: "Neural text-to-speech synthesis via local Edge TTS" },
  { id: "dubbing", label: "Dubbing", category: "voice", icon: <IconMicrophone size={14} />, desc: "Target language speech replacement" },

  // Captions & AI category
  { id: "captions", label: "Captions", category: "captions", icon: <IconSubtitles size={14} />, desc: "Burn animated subtitles with styling" },
  { id: "transcribe", label: "Transcribe", category: "captions", icon: <IconSubtitles size={14} />, desc: "Whisper ASR word-level transcription" },
  { id: "translate", label: "Translate", category: "captions", icon: <IconSparkles size={14} />, desc: "Multi-language subtitle translation" },
  { id: "auto-chapters", label: "Auto Chapters", category: "captions", icon: <IconSparkles size={14} />, desc: "AI video segmentation and chapter timestamps" },
  { id: "hook-analysis", label: "Hook Analysis", category: "captions", icon: <IconSparkles size={14} />, desc: "AI opening retention scoring" },
  { id: "metadata", label: "Metadata & SEO", category: "captions", icon: <IconSparkles size={14} />, desc: "Viral title, description, and hashtag generation" },
]

export default function StudioToolsWorkspace({
  activeAsset,
  onToolSuccess,
  onApplyOperation,
  currentTime = 0,
  projectDocument,
}) {
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const [activeCategory, setActiveCategory] = useState("video")
  const [activeTool, setActiveTool] = useState("trim")
  const [running, setRunning] = useState(false)
  const [insertToTimeline, setInsertToTimeline] = useState(true)

  // Parameters
  const [trimStart, setTrimStart] = useState(0)
  const [trimEnd, setTrimEnd] = useState(5)
  const [speedVal, setSpeedVal] = useState(1.5)
  const [aspect, setAspect] = useState("9:16")
  const [transformOp, setTransformOp] = useState("flip_h")
  const [compressLevel, setCompressLevel] = useState("high")
  const [ttsText, setTtsText] = useState("")
  const [ttsVoice, setTtsVoice] = useState("en-US-ChristopherNeural")
  const [captionStyle, setCaptionStyle] = useState("viral")
  const [targetLang, setTargetLang] = useState("Spanish")
  const [resizeW, setResizeW] = useState(720)
  const [resizeH, setResizeH] = useState(1280)

  const toolsInCategory = ALL_TOOLS.filter((t) => t.category === activeCategory)
  const currentToolDef = ALL_TOOLS.find((t) => t.id === activeTool) || ALL_TOOLS[0]

  const handleExecute = async () => {
    // Some tools don't require an active asset (like voiceover)
    if (!activeAsset && !["voiceover"].includes(activeTool)) {
      showSnackbar("Please select an active media asset first from Library or Timeline", "warning")
      return
    }

    setRunning(true)
    try {
      let endpoint = ""
      let payload = { video_id: activeAsset?.id }

      if (activeTool === "trim") {
        endpoint = "/api/tools/trim/from-asset"
        payload = { ...payload, start_seconds: trimStart, end_seconds: trimEnd }
      } else if (activeTool === "speed") {
        endpoint = "/api/tools/speed/from-asset"
        payload = { ...payload, speed: speedVal, keep_pitch: true }
      } else if (activeTool === "reframe") {
        endpoint = "/api/tools/reframe/from-asset"
        payload = { ...payload, aspect_ratio: aspect }
      } else if (activeTool === "compress") {
        endpoint = "/api/tools/compress/from-asset"
        payload = { ...payload, resolution: "original", level: compressLevel }
      } else if (activeTool === "transform") {
        endpoint = "/api/tools/transform/from-asset"
        payload = { ...payload, op: transformOp }
      } else if (activeTool === "remove-audio") {
        endpoint = "/api/tools/remove-audio/from-asset"
      } else if (activeTool === "extract-audio") {
        endpoint = "/api/tools/extract-audio/from-asset"
      } else if (activeTool === "enhance-audio") {
        endpoint = "/api/tools/enhance-audio/from-asset"
      } else if (activeTool === "silence-remover") {
        endpoint = "/api/tools/silence-remover/from-asset"
      } else if (activeTool === "voiceover") {
        endpoint = "/api/tools/voiceover"
        payload = { text: ttsText, voice: ttsVoice }
      } else if (activeTool === "captions") {
        endpoint = "/api/tools/captions/from-asset"
        payload = { ...payload, style: captionStyle }
      } else if (activeTool === "transcribe") {
        endpoint = "/api/tools/transcribe/from-asset"
      } else if (activeTool === "translate") {
        endpoint = "/api/tools/translate/from-asset"
        payload = { ...payload, target_lang: targetLang }
      } else {
        endpoint = `/api/tools/${activeTool}/from-asset`
      }

      const res = await http.post(endpoint, payload)
      showSnackbar(`Tool queued successfully (Job: ${res.data?.job_id || "Active"})`, "success")

      // If user requested timeline insertion and we have timeline mutation handler
      if (insertToTimeline && onApplyOperation && res.data?.output_path) {
        const isAudio = ["extract-audio", "voiceover"].includes(activeTool)
        const targetTrack = projectDocument?.tracks?.find((t) => t.type === (isAudio ? "audio" : "video"))
        if (targetTrack) {
          await onApplyOperation("add_clip", {
            track_id: targetTrack.id,
            clip: {
              name: `${currentToolDef.label} Output`,
              source: res.data.output_path,
              start: currentTime,
              duration: 5.0,
            },
          })
          showSnackbar("Generated media inserted into Timeline track", "success")
        }
      }

      if (onToolSuccess) onToolSuccess(res.data)
    } catch (err) {
      showSnackbar(err.response?.data?.detail || err.message, "error")
    } finally {
      setRunning(false)
    }
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#ffffff",
        borderTop: "1px solid",
        borderColor: "divider",
        p: 2,
        overflowY: "auto",
      }}
    >
      {/* Header & Category Tabs */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="caption" sx={{ fontWeight: 800, textTransform: "uppercase", color: "text.secondary" }}>
          Unified Creation Tools ({ALL_TOOLS.length} Historical Native Tools)
        </Typography>

        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={insertToTimeline}
              onChange={(e) => setInsertToTimeline(e.target.checked)}
            />
          }
          label={<Typography variant="caption" sx={{ fontSize: "0.72rem", fontWeight: 600 }}>Insert to Timeline</Typography>}
        />
      </Stack>

      <Tabs
        value={activeCategory}
        onChange={(_, val) => {
          setActiveCategory(val)
          const firstInCat = ALL_TOOLS.find((t) => t.category === val)
          if (firstInCat) setActiveTool(firstInCat.id)
        }}
        sx={{ minHeight: 32, mb: 1.5, "& .MuiTab-root": { minHeight: 32, py: 0.5, fontSize: "0.75rem", fontWeight: 700 } }}
      >
        {TOOL_CATEGORIES.map((cat) => (
          <Tab key={cat.id} value={cat.id} label={cat.label} />
        ))}
      </Tabs>

      {/* Tool Selection Pills */}
      <Stack direction="row" spacing={0.5} sx={{ mb: 1.5, flexWrap: "wrap", gap: 0.5 }}>
        {toolsInCategory.map((tool) => (
          <Button
            key={tool.id}
            size="small"
            variant={activeTool === tool.id ? "contained" : "outlined"}
            startIcon={tool.icon}
            onClick={() => setActiveTool(tool.id)}
            sx={{
              height: 26,
              fontSize: "0.72rem",
              px: 1.2,
              borderRadius: 1.5,
              textTransform: "none",
              fontWeight: activeTool === tool.id ? 700 : 500,
            }}
          >
            {tool.label}
          </Button>
        ))}
      </Stack>

      {/* Tool Description & Parameters */}
      <Box sx={{ flex: 1, bgcolor: "#f8fafc", p: 1.5, borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
        <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mb: 1.5, fontWeight: 500 }}>
          {currentToolDef.desc}
        </Typography>

        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" sx={{ gap: 1.5 }}>
          {/* Trim */}
          {activeTool === "trim" && (
            <>
              <TextField
                size="small"
                type="number"
                label="Start (sec)"
                value={trimStart}
                onChange={(e) => setTrimStart(Number(e.target.value))}
                sx={{ width: 120, "& .MuiInputBase-input": { fontSize: "0.78rem" } }}
              />
              <TextField
                size="small"
                type="number"
                label="End (sec)"
                value={trimEnd}
                onChange={(e) => setTrimEnd(Number(e.target.value))}
                sx={{ width: 120, "& .MuiInputBase-input": { fontSize: "0.78rem" } }}
              />
            </>
          )}

          {/* Speed */}
          {activeTool === "speed" && (
            <FormControl size="small" sx={{ width: 140 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Playback Speed</InputLabel>
              <Select
                value={speedVal}
                label="Playback Speed"
                onChange={(e) => setSpeedVal(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value={0.5}>0.5x (Slow)</MenuItem>
                <MenuItem value={1.0}>1.0x (Normal)</MenuItem>
                <MenuItem value={1.25}>1.25x (Fast)</MenuItem>
                <MenuItem value={1.5}>1.5x (Accelerated)</MenuItem>
                <MenuItem value={2.0}>2.0x (Double)</MenuItem>
              </Select>
            </FormControl>
          )}

          {/* Reframe */}
          {activeTool === "reframe" && (
            <FormControl size="small" sx={{ width: 140 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Target Aspect</InputLabel>
              <Select
                value={aspect}
                label="Target Aspect"
                onChange={(e) => setAspect(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value="9:16">9:16 (Vertical)</MenuItem>
                <MenuItem value="16:9">16:9 (Horizontal)</MenuItem>
              </Select>
            </FormControl>
          )}

          {/* Transform */}
          {activeTool === "transform" && (
            <FormControl size="small" sx={{ width: 160 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Operation</InputLabel>
              <Select
                value={transformOp}
                label="Operation"
                onChange={(e) => setTransformOp(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value="flip_h">Flip Horizontal</MenuItem>
                <MenuItem value="flip_v">Flip Vertical</MenuItem>
                <MenuItem value="rotate_90">Rotate 90° Clockwise</MenuItem>
              </Select>
            </FormControl>
          )}

          {/* Compress */}
          {activeTool === "compress" && (
            <FormControl size="small" sx={{ width: 140 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Compression Level</InputLabel>
              <Select
                value={compressLevel}
                label="Compression Level"
                onChange={(e) => setCompressLevel(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value="low">Low (High Quality)</MenuItem>
                <MenuItem value="medium">Medium (Balanced)</MenuItem>
                <MenuItem value="high">High (Maximum Savings)</MenuItem>
              </Select>
            </FormControl>
          )}

          {/* Voiceover */}
          {activeTool === "voiceover" && (
            <>
              <TextField
                size="small"
                label="Speech Script Text"
                value={ttsText}
                placeholder="Enter text to synthesize..."
                onChange={(e) => setTtsText(e.target.value)}
                sx={{ width: 260, "& .MuiInputBase-input": { fontSize: "0.78rem" } }}
              />
              <FormControl size="small" sx={{ width: 180 }}>
                <InputLabel sx={{ fontSize: "0.75rem" }}>Neural Voice</InputLabel>
                <Select
                  value={ttsVoice}
                  label="Neural Voice"
                  onChange={(e) => setTtsVoice(e.target.value)}
                  sx={{ fontSize: "0.78rem" }}
                >
                  <MenuItem value="en-US-ChristopherNeural">Christopher (US Male)</MenuItem>
                  <MenuItem value="en-US-JennyNeural">Jenny (US Female)</MenuItem>
                  <MenuItem value="en-GB-RyanNeural">Ryan (UK Male)</MenuItem>
                </Select>
              </FormControl>
            </>
          )}

          {/* Captions */}
          {activeTool === "captions" && (
            <FormControl size="small" sx={{ width: 160 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Caption Preset Style</InputLabel>
              <Select
                value={captionStyle}
                label="Caption Preset Style"
                onChange={(e) => setCaptionStyle(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value="viral">Viral (Yellow Highlight)</MenuItem>
                <MenuItem value="classic">Classic (White Box)</MenuItem>
                <MenuItem value="bold">Bold (Drop Shadow)</MenuItem>
                <MenuItem value="hormozi">Hormozi (High Contrast)</MenuItem>
              </Select>
            </FormControl>
          )}

          {/* Translate */}
          {activeTool === "translate" && (
            <FormControl size="small" sx={{ width: 140 }}>
              <InputLabel sx={{ fontSize: "0.75rem" }}>Target Language</InputLabel>
              <Select
                value={targetLang}
                label="Target Language"
                onChange={(e) => setTargetLang(e.target.value)}
                sx={{ fontSize: "0.78rem" }}
              >
                <MenuItem value="Spanish">Spanish</MenuItem>
                <MenuItem value="Portuguese">Portuguese</MenuItem>
                <MenuItem value="French">French</MenuItem>
                <MenuItem value="German">German</MenuItem>
                <MenuItem value="Japanese">Japanese</MenuItem>
              </Select>
            </FormControl>
          )}

          <Button
            size="small"
            variant="contained"
            disabled={running}
            startIcon={running ? <CircularProgress size={14} color="inherit" /> : <IconPlayerPlay size={15} />}
            onClick={handleExecute}
            sx={{
              height: 32,
              px: 2,
              fontSize: "0.75rem",
              fontWeight: 700,
              borderRadius: 1.5,
              ml: "auto",
            }}
          >
            {running ? "Processing…" : `Run ${currentToolDef.label}`}
          </Button>
        </Stack>
      </Box>
    </Box>
  )
}
