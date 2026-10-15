# Wave 19: Forensic Parity Crosswalk of Original 21 Tools

This document establishes the 1:1 forensic crosswalk between the legacy tools baseline (`C:\Users\toddy\Desktop\ViralMint-Legado`) and the native Motion Graphics editing architecture (`backend/tools_native`).

## Executive Architectural Summary

In legacy ViralMint, tools existed as standalone single-purpose SaaS pages (`/tools/*`) posting to REST endpoints (`/api/tools/*`) that created background `Job` records. 

In Wave 19, all 21 original tools are completely recovered as native editing actions operating directly over the canonical single Motion timeline and single `ProjectRevision` document (schema_version 2) with optimistic CAS concurrency.

### Core Guarantees:
1. **Single Player & Single Timeline:** No competing tool dashboards, popups, or external runner screens.
2. **Atomic CAS Concurrency:** Every tool mutation increments project `revision` and rejects stale updates with 409 conflict.
3. **Chat-First Main Agent Invocations:** The Main Agent can invoke any tool via `ToolsNativeAdapter` during autonomous goal execution.
4. **Contextual Refine Inspector:** Advanced users access tool parameters directly in the Refine Right Inspector (`Tools` tab).
5. **Secure Agent Ingestion:** Per Decision #5, manual URL download bars and resolution choosers are removed from the consumer UI; URL ingestion is executed by the Main Agent with SSRF validation, rights verification, and private IP blocking.

---

## 1:1 Tools Parity Matrix

| Tool ID | Legacy Page | Legacy API | Native Action Type | CAS Mutation Target | Primary Mode |
|---|---|---|---|---|---|
| `captions` | `pages/tools/Captions.jsx` | `POST /api/tools/captions` | `CAPTIONS` | `document.captions` | CAS_MUTATION |
| `reframe` | `pages/tools/Reframe.jsx` | `POST /api/tools/reframe` | `REFRAME` | `document.aspect_ratio` | CAS_MUTATION |
| `audio-enhance` | `pages/tools/AudioEnhance.jsx` | `POST /api/tools/audio-enhance` | `AUDIO_ENHANCE` | `document.audio_filters` | CAS_MUTATION |
| `watermark` | `pages/tools/Watermark.jsx` | `POST /api/tools/watermark` | `WATERMARK` | `document.watermark` | CAS_MUTATION |
| `merge-clips` | `pages/tools/MergeClips.jsx` | `POST /api/tools/merge-clips` | `MERGE_CLIPS` | `document.tracks` | CAS_MUTATION |
| `remove-silence`| `pages/tools/RemoveSilence.jsx` | `POST /api/tools/remove-silence` | `REMOVE_SILENCE`| `document.silence_removal`| CAS_MUTATION |
| `translate` | `pages/tools/Translate.jsx` | `POST /api/tools/translate` | `TRANSLATE` | `document.captions.target_language` | CAS_MUTATION |
| `hook-analysis` | `pages/tools/HookAnalysis.jsx` | `POST /api/tools/hook-analysis` | `HOOK_ANALYSIS` | `document.metadata.hook_analysis` | AGENT_COMMAND |
| `enhance-prompt`| `components/tools/PromptField.jsx` | `POST /api/tools/enhance-prompt` | `ENHANCE_PROMPT`| `document.metadata.enhanced_prompt` | AGENT_COMMAND |
| `voiceover` | `pages/tools/Voiceover.jsx` | `POST /api/tools/voiceover` | `VOICEOVER` | `document.tracks (audio)` | CAS_MUTATION |
| `transform` | `pages/tools/Transform.jsx` | `POST /api/tools/transform` | `TRANSFORM` | `document.tracks[].clips[].transform` | CAS_MUTATION |
| `music-visualizer`| `pages/tools/MusicVisualizer.jsx` | `POST /api/tools/music-visualizer` | `MUSIC_VISUALIZER`| `document.tracks (overlay)` | CAS_MUTATION |
| `gif` | `pages/tools/Gif.jsx` | `POST /api/tools/gif` | `GIF` | `document.export_settings.gif` | EXPORT_PIPE |
| `speed` | `pages/tools/Speed.jsx` | `POST /api/tools/speed` | `SPEED` | `document.tracks[].clips[].speed` | CAS_MUTATION |
| `metadata` | `pages/tools/Metadata.jsx` | `POST /api/tools/metadata` | `METADATA` | `document.metadata` | CAS_MUTATION |
| `auto-chapters` | `pages/tools/AutoChapters.jsx` | `POST /api/tools/auto-chapters` | `AUTO_CHAPTERS` | `document.markers` | CAS_MUTATION |
| `trim` | `pages/tools/Trim.jsx` | `POST /api/tools/trim` | `TRIM` | `document.tracks[].clips[].start_time` | CAS_MUTATION |
| `subtitles` | `pages/tools/Subtitles.jsx` | `POST /api/tools/subtitles` | `SUBTITLES` | `document.captions.subtitles` | CAS_MUTATION |
| `compress` | `pages/tools/Compress.jsx` | `POST /api/tools/compress` | `COMPRESS` | `document.export_settings.compression` | EXPORT_PIPE |
| `crop` | `pages/tools/Crop.jsx` | `POST /api/tools/crop` | `CROP` | `document.tracks[].clips[].crop` | CAS_MUTATION |
| `auto-zoom` | `pages/tools/AutoZoom.jsx` | `POST /api/tools/auto-zoom` | `AUTO_ZOOM` | `document.tracks[].clips[].auto_zoom` | CAS_MUTATION |
| `video-download`| `pages/tools/VideoDownload.jsx` | `POST /api/downloaded/batch-download` | `VIDEO_DOWNLOAD`| `document.assets` | AGENT_COMMAND |
