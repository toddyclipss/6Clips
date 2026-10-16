# 6Clips / ViralMint — P0 Recovery Squad: Agent 4 Report
**Component:** Motion Graphics Create / Review UI: Single Artifact Player Sync & No Social Gate  
**Branch:** `p0fix/04-canonical-review-ui`  
**Base SHA:** `7a76da6ec7bb0fce8e95a38941ab4e7ac8fa68a1`  

---

## 1. Executive Summary

Agent 4 resolved the UI defect where:
1. An edit-only request (`analise e edite esse video em ingles https://www.youtube.com/watch?v=FV93IVwJP_4`) triggered a false `PENDING_CREDENTIALS` social publishing status banner.
2. The Review player and cards defaulted to a hardcoded `15.00s` duration instead of the authoritative physical media duration (e.g. 9.8s or 8.0s).
3. On backend execution failures (such as `BLOCKED_UNAUTHORIZED_BACKGROUND_AI` or `FAILED_TERMINAL`), the UI retained stale preview artifacts from earlier runs instead of displaying a truthful terminal error state.
4. Output export and single player timeline synchronization lacked physical metadata propagation.

---

## 2. Root Cause Analysis

1. **Stale 15.00s Duration**:
   - `frontend/src/utils/nativeMotionAdapter.js`: `normalizeProjectForPlayer` returned `duration: doc.duration_seconds || 15`, ignoring `project.media_probe`.
   - `frontend/src/components/motion/StudioPreviewStage.jsx`: Default prop was `duration = 15`. It tracked `duration` but did not react to `<video>`'s `onLoadedMetadata` duration, nor did it propagate updates back to `MotionGraphics.jsx`.
   - `frontend/src/pages/MotionGraphics.jsx`: Lines 2038 and 2201 defaulted to `|| 15`.
2. **Spurious `PENDING_CREDENTIALS` Social Gate**:
   - `frontend/src/components/motion/MotionReviewPanel.jsx`: Rendered the external publishing status card if any output had `publication_requested` without checking if it was explicitly requested (`true` or `"REQUESTED"`). It also hardcoded a `<Chip label="NOT_CONNECTED / PENDING_CREDENTIALS" />` rather than reflecting actual server publication state.
3. **Stale Deliverable on Failure**:
   - `frontend/src/pages/MotionGraphics.jsx`: In `syncOutcome`, when `state === "FAILED_TERMINAL"` or `"BLOCKED"`, `renderedVideo` was left untouched in state, leaving the previous run's completed video displayed on screen.
4. **Player Keying & Remount**:
   - The `<video>` element inside `StudioPreviewStage.jsx` lacked an artifact-specific key, which caused cached video elements to retain `currentTime` and stale buffers across revision transitions.

---

## 3. Implemented Fixes

### A. `frontend/src/utils/nativeMotionAdapter.js`
- Prioritized `projectOrDoc.media_probe?.duration_seconds` before falling back to `document.timeline.duration_seconds`.
- Removed `|| 15` fallback, defaulting to `0`.

### B. `frontend/src/components/motion/MotionReviewPanel.jsx`
- Added strict `isExplicitPublicationRequested` predicate (`clip.publication_requested === true || clip.publication_requested === "REQUESTED"`).
- Suppressed the `review-publishing-status` container completely when publication is not explicitly requested.
- Replaced the hardcoded `NOT_CONNECTED / PENDING_CREDENTIALS` chip with dynamic status `o.publication_status || "PENDING_SOCIAL_AUTHORIZATION"`.
- Fixed duration display to read `media_probe.duration_seconds ?? duration_seconds ?? 0`.
- Added unique keys on cards using `out.artifact_id || out.sha256 || out.output_id || idx`.

### C. `frontend/src/components/motion/StudioPreviewStage.jsx`
- Replaced default prop `duration = 15` with `duration = 0`.
- Added `mediaDuration` state initialized from `renderedVideo.media_probe?.duration_seconds`.
- Bound `<video>` `onLoadedMetadata` to capture `e.target.duration`, set `mediaDuration`, and fire `onDurationChange(realDur)`.
- Keyed `<video>` tag with `key={renderedVideo.artifact_id || renderedVideo.sha256 || renderedVideo.output_id || ...}` to force clean DOM remount and reset time on artifact change.
- Added `useEffect` resetting `currentTime = 0` whenever the deliverable changes.

### D. `frontend/src/pages/MotionGraphics.jsx`
- In `syncOutcome`:
  - On `FAILED_TERMINAL`, `BLOCKED`, `BLOCKED_UNAUTHORIZED_BACKGROUND_AI`, or `FAILED_RETRYABLE`: atomically set `renderedVideo(null)` and `setProductionBatch(null)`.
  - On new in-progress run dispatch: atomically clear stale deliverables from prior runs if `run_id` differs.
  - Normalized incoming deliverable with `media_probe.duration_seconds`, artifact ID, run ID, and explicit publication flag.
- In `handleExportOutput`: prioritized `output.download_url` over `preview_ref` / `video_url`, and named download files using `output.output_id || output.artifact_id || "clip"`.
- Removed `|| 15` from `StudioPreviewStage` and `StudioTimelineWorkspace` duration props.
- Passed `onDurationChange` to `StudioPreviewStage` to synchronize document duration with physical video duration.

---

## 4. Verification Evidence

### A. Unit and Component Tests
**Command:** `pytest tests/p0_recovery/a4/test_a4_review_player_sync.py`  
**Result:** 15 passed in 0.61s  
- `TestNativeMotionAdapterDurationSync`:
  - `test_respects_probe_duration`: PASS (duration: 8.0)
  - `test_respects_document_duration_when_no_probe`: PASS (duration: 9.8)
  - `test_defaults_to_zero_not_fifteen`: PASS (duration: 0)
- `TestMotionReviewPanelContracts`:
  - `test_no_hardcoded_social_gate_for_edit_only`: PASS
  - `test_review_panel_uses_probe_duration`: PASS
  - `test_review_panel_keys_by_unique_artifact_id`: PASS
- `TestStudioPreviewStageContracts`:
  - `test_preview_stage_no_15s_default_prop`: PASS
  - `test_preview_stage_syncs_with_video_metadata`: PASS
  - `test_preview_stage_remounts_on_artifact_change`: PASS
  - `test_preview_stage_resets_time_on_video_change`: PASS
- `TestMotionGraphicsOrchestrationContracts`:
  - `test_sync_outcome_invalidates_stale_deliverable_on_failure`: PASS
  - `test_motion_graphics_passes_real_duration_and_on_duration_change`: PASS
  - `test_export_output_uses_download_url_and_canonical_id`: PASS
  - `test_source_vs_output_duration_lineage_preserves_probe_duration`: PASS (source: 19.0s, output probe: 8.0s)
  - `test_atomic_replacement_on_new_revision`: PASS

### B. Microsoft Edge Browser E2E Tests
**Command:** `pytest tests/p0_recovery/a4/test_a4_edge_review_e2e.py`  
**Result:** 3 passed in 16.32s  
- Headless Microsoft Edge rendering against compiled SPA.
- Screenshots captured in `tools/p0_recovery_a4/evidence/screenshots/`:
  - `p0_edge_1920x1080_motion_review.png` (71.8 KB)
  - `p0_edge_1920x1080_review_mode.png` (75.4 KB)
  - `p0_edge_1440x900_review.png` (66.3 KB)
  - `p0_edge_1366x768_review.png` (64.2 KB)
- Verified DOM assertions:
  1. Five sidebar entries: Motion Graphics, Trends, My Channel, Library, Messages.
  2. Create / Review mode switcher only (zero Refine tab).
  3. Zero `PENDING_CREDENTIALS` or `External Social Publishing Status` on initial load or review mode.
  4. Zero hardcoded `15.00s` fallback in rendered DOM.

### C. Frontend Production Build
**Command:** `npm run build` in `frontend`  
**Result:** Clean build in 20.43s. 0 errors.

---

## 5. Gate Ledger

| Gate | Status | Evidence / Notes |
|---|---|---|
| Single Player & Physical Duration Sync | **PASS** | Uses `media_probe.duration_seconds` and `onLoadedMetadata`, zero 15s fallbacks |
| Zero Social Gate for Edit-Only | **PASS** | Guarded by `isExplicitPublicationRequested`, no `PENDING_CREDENTIALS` |
| Atomic Deliverable Invalidation on Failure | **PASS** | Clears `renderedVideo` and `productionBatch` on terminal errors |
| Navigation & Mode Constraints | **PASS** | 5 sidebars, Create/Review only, optional Advanced Editing |
| Scope & Boundary Enforcement | **PASS** | Strictly owned files modified only, no forbidden cross-agent edits |
| Evidence & Handoff Contract | **PASS** | `HANDOFF.json`, `REPORT.md`, screenshots, and 18/18 passing tests |
