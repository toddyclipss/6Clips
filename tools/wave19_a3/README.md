# Wave 19 Agent 3: Forensic Restoration of All Original Clip Studio Functions

## 1. Executive Summary & Git Attribution
- **Role:** Agent 3 of 5 — Forensic Restoration of All Original Clip Studio Functions
- **Dedicated Branch:** `wave19/03-legacy-clipstudio-native`
- **Worktree Directory:** `C:\Users\toddy\Desktop\ViralMint-wave19-03-clipstudio-native`
- **Base Local `main` SHA:** `5103a363b9b8514a486ffe83ef289f47eb67a782`
- **Integration Status:** `READY_FOR_INTEGRATION_REVIEW` (marker: [READY.json](file:///c:/Users/toddy/Desktop/ViralMint-wave19-03-clipstudio-native/tools/wave19_a3/READY.json))

---

## 2. Non-Negotiable OAAS Architecture
In accordance with the product contract:
- **6Clips sells outcomes, not SaaS editing software:** There is NO standalone Clip Studio page, sub-screen, source bench panel, or secondary player.
- **Single Canonical Player & Timeline:** All original Clip Studio capabilities are consolidated into native commands operating on Motion Graphics' single canonical player, single timeline, single Project document, and single export pipeline.
- **Main Agent Invocation:** Creative clipping goals (e.g., *"Take my 2-hour livestream and make 3 vertical clips with captions"*) are executed autonomously by Main Agent through `clipstudio_native_adapter` without requiring manual form manipulations. Advanced users interact with the same timeline via drag-and-drop.
- **No Compatibility Removal Before Parity:** Legacy endpoints (`/api/downloaded/{id}/suggest-clips`, `/api/downloaded/{id}/extract-clips`, `/api/videos/...`) remain supported via drop-in adapter.

---

## 3. Forensic Legacy Census: 34 Mapped Capabilities
While initial estimates referenced 9 workflows, our forensic audit of the legacy checkout at `C:\Users\toddy\Desktop\ViralMint-Legado` (inspected in STRICT READ-ONLY mode) identified **34 distinct capabilities** across the complete surface:

| ID | Capability Name | Legacy Source Location | Current Native Mapping |
| :--- | :--- | :--- | :--- |
| **CS-01** | `source_select` | `frontend/src/pages/ClipStudio.jsx:150` | `clipstudio_native_adapter.select_source_media` -> `add_asset` |
| **CS-02** | `source_preview` | `frontend/src/pages/ClipStudio.jsx:205` | Canonical Motion player stream (`GET /downloaded/{id}/stream`) |
| **CS-03** | `filmstrip_generate` | `backend/api/downloaded.py:1496` | `GET /downloaded/{id}/filmstrip` (timeline scrubbing sprites) |
| **CS-04** | `frame_extract` | `backend/api/downloaded.py:1572` | `GET /downloaded/{id}/frame` (playhead hover inspect) |
| **CS-05** | `speech_transcribe` | `backend/services/clip_extractor.py:1209` | Whisper transcription (`fast`, `balanced`, `accurate`, `best`) |
| **CS-06** | `segments_cache` | `backend/api/downloaded.py:1637` | `GET /downloaded/{id}/segments` (zero retranscribe cache) |
| **CS-07** | `suggest_clips_ai` | `backend/api/downloaded.py:1159` | `clipstudio_native_adapter.suggest_clips` ("Ask AI" highlight detector) |
| **CS-08** | `platform_bias` | `backend/services/clip_extractor.py:322` | Target platform hook ranker bias (`tiktok`, `shorts`, `reels`, `linkedin`) |
| **CS-09** | `genre_bias` | `backend/services/clip_extractor.py:432` | Genre selection bias (`podcast`, `interview`, `tutorial`, `gaming`, etc.) |
| **CS-10** | `user_query_filter` | `backend/services/clip_extractor.py:1780` | Natural-language topic filter query |
| **CS-11** | `bench_range_set` | `frontend/src/components/clip/bench/useBenchRanges.js:50` | `ProjectService.apply_operation(set_bench_ranges)` |
| **CS-12** | `bench_range_snap` | `backend/services/clip_extractor.py:1531` | Sentence and speech-pause boundary snapping |
| **CS-13** | `bench_range_dedup` | `backend/services/clip_extractor.py:1589` | Non-overlapping range collision removal |
| **CS-14** | `bench_topic_dedup` | `backend/services/clip_extractor.py:1694` | Semantic topic keyword deduplication |
| **CS-15** | `extract_clips_ai` | `backend/api/downloaded.py:982` | `clipstudio_native_adapter.extract_clips_to_project` (AI mode) |
| **CS-16** | `extract_clips_manual` | `backend/api/downloaded.py:982` | `clipstudio_native_adapter.extract_clips_to_project` (manual mode) |
| **CS-17** | `duration_fallback` | `backend/services/clip_extractor.py:997` | Evenly-spaced duration slicing fallback |
| **CS-18** | `silence_remove` | `backend/services/clip_extractor.py:2465` | Dead air (>0.5s) and filler words removal |
| **CS-19** | `segment_retime` | `backend/services/clip_extractor.py:2653` | Dynamic segment and subtitle retiming |
| **CS-20** | `reframe_vertical` | `backend/services/ffmpeg_service.py` | 9:16 vertical blur-fill reframing |
| **CS-21** | `captions_burn` | `backend/services/clip_extractor.py:2699` | Synchronized ASS captions burn-in with word animation |
| **CS-22** | `captions_style` | `backend/services/caption_service.py:80` | 10 typography presets (`viral`, `standard`, `beast`, etc.) |
| **CS-23** | `emoji_density` | `backend/services/caption_service.py:250` | AutoEmoji keyword density (`none`, `minimal`, `moderate`, `heavy`) |
| **CS-24** | `metadata_generate` | `backend/services/clip_extractor.py:2809` | LLM title, description, and hashtags generation |
| **CS-25** | `virality_score_breakdown` | `backend/services/clip_extractor.py:1659` | 5-factor scorecard (`hook`, `flow`, `value`, `trend`, `shareability`) |
| **CS-26** | `thumbnail_generate` | `backend/services/thumbnail_service.py:40` | Hook peak cover frame extraction |
| **CS-27** | `thumbnail_regenerate` | `backend/api/videos.py:322` | Playhead timecode thumbnail extraction |
| **CS-28** | `clip_metadata_edit` | `backend/api/videos.py:268` | `PATCH /videos/{id}` metadata update |
| **CS-29** | `clip_stream` | `backend/api/videos.py:481` | HTTP Range video streaming |
| **CS-30** | `clip_stream_aspect` | `backend/api/videos.py:618` | Aspect-specific variant streaming |
| **CS-31** | `clip_delete` | `backend/api/videos.py:355` | Cascade deletion of deliverables and records |
| **CS-32** | `timeline_project_map` | `frontend/src/components/clip/bench/SourceBench.jsx` | Native timeline clip, track, and asset insertion |
| **CS-33** | `project_reopen` | `backend/services/project_service.py` | Schema version 2 project state restoration |
| **CS-34** | `project_export_mp4` | `backend/clipstudio_native/service.py` | Physical MP4 composition export decoded by FFprobe |

Complete machine-readable manifests:
- [clipstudio_legacy_vs_current.csv](file:///c:/Users/toddy/Desktop/ViralMint-wave19-03-clipstudio-native/tools/wave19_a3/clipstudio_legacy_vs_current.csv)
- [clipstudio_legacy_vs_current.json](file:///c:/Users/toddy/Desktop/ViralMint-wave19-03-clipstudio-native/tools/wave19_a3/clipstudio_legacy_vs_current.json)

---

## 4. Deliverables & Evidence
- **Physical Media Deliverables (Decoded via FFprobe, SHA-256 verified):**
  - `source_stream_30s.mp4`: Authentic 30s 1920x1080 source test video with audio.
  - `batch_clips/clip_01_range_1d9ed9b7.mp4`: 1080x1920 9:16 vertical blur-fill with audio (SHA: `7c69df112452...`).
  - `batch_clips/clip_02_range_19dba3a7.mp4`: 1080x1920 9:16 vertical blur-fill with audio (SHA: `b676a9eba60b...`).
  - `proj_wave19_cs_*_export.mp4`: Full composition MP4 export (SHA: `0d808fe170bb...`).
- **Full Evidence Ledger:**
  - Recorded in [clipstudio_evidence_ledger.json](file:///c:/Users/toddy/Desktop/ViralMint-wave19-03-clipstudio-native/tools/wave19_a3/clipstudio_evidence_ledger.json).

---

## 5. Integration Handoff for Agent 5 (Integrator)
1. **Import Public Adapter:**
   ```python
   from backend.clipstudio_native import clipstudio_native_adapter
   ```
2. **Main Agent Tool Wiring:**
   Route clipping intent directly to:
   - `clipstudio_native_adapter.suggest_clips(...)`
   - `clipstudio_native_adapter.extract_clips_to_project(project_id, ...)`
   - `clipstudio_native_adapter.extract_batch_clips(...)`
3. **Compatibility Routing (Optional drop-in):**
   Agent 5 can mount `backend.clipstudio_native.compat.compat_router` into `backend/main.py`.
4. **UI Parity (Agent 2):**
   Ensure dragging an asset onto the video track executes native `add_clip` with `trim_start` and `trim_end`, displaying proposed highlights in the timeline's ghost lane via `document["bench_ranges"]`.
