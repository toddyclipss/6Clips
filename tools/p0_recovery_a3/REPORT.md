# Agent 3: Real YouTube/TikTok Source Video Edit Lineage Delivery Report

## 1. Executive Summary

This report delivers the complete Wave 21 Agent 3 subsystem for real source video ingestion, native FFmpeg-backed media editing, safe project timeline mutations, and deterministic lineage verification.

### Incident Diagnosed
User submitted the prompt:
> `analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4`

Previous attempts failed for three compounding reasons:
1. **Case-Sensitivity Defect**: The YouTube video ID was tested with a lowercase `l` (`FV93lVwJP_4`) instead of an uppercase `I` (`FV93IVwJP_4`), returning HTTP 404 and falsely concluding the video was unavailable. The live video is active, public, 1115s (18:35) long, titled `"GTA 6 Launch Trailer: Everything New YOU MISSED"`, produced by TGG.
2. **Container Output Mismatch**: When downloading DASH streams (AV01 video + Opus audio), `yt-dlp` produced `.webm` or `.mkv` files even when invoked with `-o target.mp4`. The ingestion service tried to check `target.mp4`, encountered a `FileNotFoundError`, and surfaced `BLOCKED_FETCH_FAILED`.
3. **Synthetic Substitution Anti-Pattern**: When ingestion failed or editing was invoked, synthetic text title cards over black backgrounds were generated instead of failing closed truthfully or natively transforming the source media. Furthermore, Python 3.14 lacked the `yt_dlp` python module, failing on import even though the `yt-dlp` CLI binary was installed.

---

## 2. Architecture & Delivered Modules

### `backend/services/ytdlp_service.py`
- Added transparent CLI subprocess fallback for `get_video_info`, `download_video`, and `check_ytdlp_version` when Python's `import yt_dlp` fails due to environment mismatch.
- Preserves exact URL character casing and handles CLI JSON parsing.

### `backend/oaas_chat_ingestion/ingestion_service.py`
- Added `--merge-output-format mp4` and format selection `bestvideo[height<=1080]+bestaudio/best[height<=1080]/best`.
- Implemented container auto-resolution: inspects actual disk files (`.mp4`, `.webm`, `.mkv`), automatically invoking lossless FFmpeg remuxing (`ffmpeg -c copy`) to deliver a verified `.mp4`.
- Enforces strict SSRF validation, blocks private IP ranges and unsafe protocols, and eliminates any user copyright attestation barriers.

### `backend/oaas_media_edit/` Subsystem
- **`models.py`**: Strong Pydantic models for `EditIntentType`, `SourceStreamInfo`, `SourceMediaAnalysis`, `EditExistingMediaContract`, `SourceLineageVerification`, and `EditExecutionResult`.
- **`analyzer.py` (`SourceMediaAnalyzer`)**:
  - Probes container, video, and audio streams with `ffprobe`.
  - Calculates SHA-256 hash and size.
  - Samples 5 equidistant frames to calculate average luminance, pixel standard deviation, and inter-frame motion delta.
  - Rejects static black or blank cards.
  - Computes bounded span candidates for editing based on user requested duration.
- **`editor.py` (`NativeMediaEditor`)**:
  - Implements native FFmpeg editing pipelines:
    - 9:16 vertical reframe with blurred background (`scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:5`) and crisp scaled foreground (`scale=1080:1920:force_original_aspect_ratio=decrease`), overlaid in center.
    - 1:1 square reframe and 16:9 widescreen reframe.
    - High-fidelity audio stream copying/re-encoding (`aac -b:a 192k`).
    - Accurate start/duration trimming.
- **`project_adapter.py` (`SafeProjectEditAdapter`)**:
  - Interacts safely with `ProjectService` via `apply_operation` without bypassing invariants.
  - Emits canonical operations: `add_asset`, `add_clip`, `set_aspect_ratio`, and `set_captions`.
  - Records source lineage (`source_asset_id`, `source_sha256`, `source_url`, `transform_type`) in clip and project metadata.
  - Supports multi-turn revisions ($N \to N+1$).
- **`verifier.py` (`SourceLineageVerifier`)**:
  - Deterministic gate predicate verifying:
    1. Deliverable file exists and is readable.
    2. Duration matches within $\pm 0.75\text{s}$ tolerance.
    3. Aspect ratio matches target.
    4. Deliverable contains video and audio streams.
    5. Frames are non-black (luminance $> 5.0$, pixel stddev $> 5.0$).
    6. Timeline references the genuine source SHA-256.
- **`adapter.py` (`EditExistingMediaAdapter`)**:
  - Clean unified facade exposing intent classification, source ingestion/resolution, contract preparation, execution, and verification.

---

## 3. Test Suite Verification

All 22 tests across 5 test suites pass with zero failures:
- `tests/p0_recovery/a3/test_e2e_real_video_edit_lineage.py` (5 passed)
  - Intent classification on exact user prompt
  - Live uppercase-I YouTube metadata fidelity
  - End-to-end source-backed video edit execution
  - Local source resolution avoiding redundant downloads
  - Truthful failure on genuinely unavailable URLs (closed failure)
- `tests/p0_recovery/a3/test_native_media_edit_pipeline.py` (3 passed)
  - Native FFmpeg vertical 9:16 reframe with blurred backdrop
  - Square 1:1 reframe
  - Canonical project revisions and multi-turn mutation
- `tests/p0_recovery/a3/test_source_acquisition_and_ingestion.py` (5 passed)
  - SSRF and protocol safety checks
  - URL casing integrity (uppercase I vs lowercase l)
  - Truthful failure on 404
  - Container auto-resolution (.webm -> .mp4)
  - Zero user ownership attestation requirement
- `tests/p0_recovery/a3/test_source_lineage_verifier_predicate.py` (4 passed)
  - Verifier passes on genuine deliverable
  - Verifier fails on duration drift
  - Verifier fails on static black title card
  - Verifier fails on SHA mismatch
- `tests/p0_recovery/a3/test_source_media_analysis_and_lineage.py` (5 passed)
  - Genuine video analysis (luminance, motion, audio)
  - Static black card rejection
  - Missing audio stream detection
  - Bounded edit span calculation
  - Missing/corrupt file handling

---

## 4. Inter-Agent Handoff
Agent 5 can invoke the high-level adapter directly:
```python
from backend.oaas_media_edit import EditExistingMediaAdapter, EditIntentType

adapter = EditExistingMediaAdapter()
intent = adapter.classify_intent("analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4")

if intent != EditIntentType.NEW_SYNTHETIC_GENERATION:
    contract = await adapter.prepare_contract(
        prompt="analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4",
        source_url="https://www.youtube.com/watch?v=FV93IVwJP_4",
        target_aspect_ratio="9:16",
        target_duration_sec=30.0
    )
    result = await adapter.execute_edit(contract)
    assert result.status == "success"
    assert result.lineage_verification.is_valid
```
