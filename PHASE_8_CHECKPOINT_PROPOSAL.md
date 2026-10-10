# VIRALMINT — PHASE 8 SOURCE CHECKPOINT PROPOSAL

**Date:** 2026-10-10  
**Target Git Branch:** `main`  
**Current HEAD Commit:** `83b912e3efb72a6aef912e0e0f8078c9d194c794`  
**Working-Tree State:** Intentionally Modified / Uncommitted (`DIRTY`)  
**Proposed Commit Title:** `feat(phase8): canonical project document, idempotency contract, motion studio UI, and visual playback baseline`  

---

## 1. Executive Summary & Checkpoint Objective

Phase 8 established the entire versioned motion graphics foundation for ViralMint:
- Optimistic concurrency control (CAS) via `Project → ProjectRevision`.
- Strict canonical request fingerprinting and deterministic idempotency deduplication with HTTP 409 conflict detection.
- Universal media asset resolution, scope authorization, and media type validation (`AssetResolver`).
- Full Motion Studio UI (`/motion`) with timeline ruler scrubbing, multi-track composition, layer order, variable controls, and visual preview stage.
- 2,934 passing automated tests and a production-grade frontend build (`npm run build`).

Because the working tree currently contains 46 modified tracked files and critical untracked source files, this document specifies the **exact source manifest and reproduction procedure** to create an intentional, atomic checkpoint commit before Phase 9 begins.

**Guarantees:**
- No destructive git commands (`git reset`, `git clean`, force-push) will be executed.
- No automatic git commit or push will occur without explicit product owner approval.
- No user work, historical media, or uncommitted work will be overwritten or discarded.

---

## 2. Git Baseline & Working-Tree Inspection

```bash
git rev-parse --show-toplevel
# Output: C:/Users/toddy/Desktop/ViralMint

git branch -vv
# Output: * main 83b912e [origin/main] feat: implement comprehensive frontend user interface and tools suite for ViralMint

git status --porcelain
# Output: 46 modified tracked files, 53 untracked files/directories
```

---

## 3. Proposed Commit Manifest

### A. Modified Tracked Source Files (46 files)
These files contain necessary Phase 8 enhancements to the core engine, agents, and test suites:

1. `.gitignore` — Ignore test tmpdirs, render staging, and cache files.
2. `backend/agents/generator_motion.py` — Staged motion render integration.
3. `backend/agents/job_helper.py` — Motion job type and error envelopes.
4. `backend/agents/planner.py` — Capabilities dispatch and motion intent routing.
5. `backend/agents/uploader.py` — Platform publication lineage checks.
6. `backend/api/channels.py` — Channel publish status distinction.
7. `backend/api/chat.py` — OaaS motion and refine intent routing.
8. `backend/api/downloaded.py` — Downloaded media asset metadata expansion.
9. `backend/api/tools.py` — Asset identity resolver integration.
10. `backend/core/ai_provider.py` — BYOK key encryption and provider fallback.
11. `backend/core/exceptions.py` — `IdempotencyConflictError`, `RevisionConflictError`, `AssetError` hierarchy.
12. `backend/core/task_runner.py` — Motion studio render task dispatch.
13. `backend/core/user_intelligence.py` — User telemetry tracking.
14. `backend/core/ws_manager.py` — Multi-client broadcast filtering.
15. `backend/database.py` — `NullPool` architecture, column migration sentinel, and revision unique indexes.
16. `backend/main.py` — Capabilities and projects router mounting.
17. `backend/models/connected_channel.py` — Publishing authorization fields.
18. `backend/models/generated_video.py` — Project revision lineage and file hash columns.
19. `backend/services/library_index.py` — Universal library indexing.
20. `backend/services/studio_service.py` — Media staging and project folder management.
21. `backend/services/tiktok_uploader.py` — Inbox delivery verification.
22. `frontend/src/components/clip/bench/SourceBench.jsx` — Source bench range commit to project document.
23. `frontend/src/components/clip/bench/useBenchRanges.js` — Bench range state sync with SQLite.
24. `frontend/src/pages/MotionGraphics.jsx` — Complete interactive Motion Studio editor page.
25–46. `tests/test_*.py` (22 modified test files) — Migration call count, whisper mock, clipper parity, and origin allowlist regressions.

### B. Untracked Production Source Files (To Add)
1. **Backend Versioning & Core APIs:**
   - `backend/models/project.py` — Canonical Project model and default empty document schema.
   - `backend/models/project_revision.py` — Immutable revision log with `request_fingerprint` and `idempotency_key`.
   - `backend/models/execution.py` — OaaS execution run and step models.
   - `backend/services/project_service.py` — Optimistic CAS mutations, deterministic idempotency, and revision management.
   - `backend/services/asset_resolver.py` — Universal asset resolver with scope and media type checks.
   - `backend/services/hyperframes_adapter.py` — Project document to HTML compiler, GSAP timeline bridge, isolated render staging.
   - `backend/services/registry_adapter.py` — Catalog component snapshotting and variable validation.
   - `backend/services/executor_service.py` — Step-by-step execution coordinator.
   - `backend/core/capabilities.py` — Deterministic capability definitions.
   - `backend/core/verifiers.py` — Media stream and lineage verifiers.
   - `backend/api/projects.py` — Full Projects REST API (`/projects`, `/operations`, `/preview`, `/render`, `/ingest-trend`).
   - `backend/api/capabilities_api.py` — Capabilities execution REST API.

2. **Frontend Motion Studio Components (`frontend/src/components/motion/`):**
   - `StudioToolbar.jsx` — Transport controls (Play/Pause/Timecode/Ratio selector/Render button).
   - `StudioPreviewStage.jsx` — Master composition canvas iframe with preview bridge.
   - `StudioTimelineWorkspace.jsx` — Multi-track virtualized timeline with ruler scrubbing and trim handles.
   - `StudioLayersPanel.jsx` — Visual layer stack with visibility toggles and lock controls.
   - `StudioVariablesPanel.jsx` — Interactive catalog template variable editing controls.
   - `StudioInspectorPanel.jsx` — Selected element properties, timing, and transform controls.
   - `StudioResourcePanel.jsx` — Source media bench and catalog component browser drawer.
   - `StudioToolsWorkspace.jsx` — OaaS background tool operations drawer.

3. **Phase 8 Automated Test Suites (`tests/`):**
   - `tests/test_idempotency_contract.py` — 7 tests: same key replay, payload mismatch conflict, op mismatch, stale rev, concurrency race, atomic rollback.
   - `tests/test_project_asset_contract.py` — 5 tests: physical existence, user/project scoping, media type compatibility, deleted files, path rejection.
   - `tests/test_api_projects.py` — Projects CRUD, optimistic concurrency 409s, preview serving.
   - `tests/test_project_service.py` — Service-level revisions, render freeze snapshots.
   - `tests/test_hyperframes_adapter.py` — HTML compilation, GSAP playback attributes, staging.
   - `tests/test_browser_visual_playback.py` — Live Playwright browser visual playback regression.
   - `tests/test_browser_timeline.py` — Timeline multi-track scrubbing and magnetic snapping test.
   - `tests/test_phase8a_layers_variables_locks.py` — Layer order mutations, lock checks, variable updates.
   - `tests/test_motion_migration_verification.py` — Schema v2 migration, aspect ratio sync.
   - `tests/test_staging_and_preview_fixes.py` — Isolated render staging and manifest creation.
   - `tests/test_flow_library_to_cuts_and_render.py` — End-to-end library to render pipeline.
   - `tests/test_real_trend_ingest_pipeline.py` — Trend ingestion into project document.
   - `tests/test_timeline_operations.py` — Timing, move, split, keyframe mutations.
   - `tests/test_capabilities_api.py` — Capabilities API endpoints.
   - `tests/test_executor_service.py` — Step execution runner.
   - `tests/test_agent_oaas_and_acceptance.py` — Agent orchestration acceptance.
   - `tests/test_oaas_chat_routing.py` — Chat routing.
   - `tests/test_layers_and_variables.py` — Variable validation.
   - `tests/test_manual_clip_write_persistence.py` — Bench clip persistence.
   - `tests/test_motion_visual_quality.py` — Render visual quality verifications.
   - `tests/test_async_job_resume.py` — Async job resumption.
   - `tests/verify_followup_fixes.cjs` — Node-based schema verification.

4. **Automation Scripts (`scripts/`):**
   - `scripts/run_final_acceptance_verification.py`
   - `scripts/run_final_gap_closure.py`
   - `scripts/run_phase8a_browser_acceptance.py`
   - `scripts/scan_registry_variables.py`

5. **Provenance & Audit Records:**
   - `PROVENANCE_INVENTORY.csv` — Reconciled 649-entry provenance inventory.
   - `CURRENT_IMPLEMENTATION_GAP_AUDIT.md`
   - `HYPERFRAMES_ADVANCED_EDITOR_INTEGRATION_AUDIT.md`
   - `MOTION_16X9_FRAMING_FINAL_FIX_REPORT.md`
   - `MOTION_FINAL_VIDEO_DELIVERY_REPORT.md`
   - `MOTION_PLAYBACK_FINAL_ACCEPTANCE_CLOSURE.md`
   - `MOTION_PREVIEW_VISUAL_PLAYBACK_FIX_REPORT.md`
   - `OAAS_ROUTING_AND_BASELINE_CLOSURE_REPORT.md`
   - `PHASE_8A_FINAL_GAP_CLOSURE_REPORT.md`
   - `PHASE_8A_FUNCTIONAL_CLOSURE_REPORT.md`
   - `PHASE_8B_ARCHITECTURE_RUNTIME_CLOSURE_REPORT.md`
   - `PHASE_8B_FINAL_EVIDENCE_RECONCILIATION.md`
   - `VIRALMINT_GLOBAL_ROADMAP_CONFORMANCE_AUDIT.md`
   - `PHASE_8B_EXIT_GATE_REPORT.md`
   - `PHASE_8_CHECKPOINT_PROPOSAL.md`

---

## 4. Files Intentionally Excluded From Git

The following files exist in the working directory but **MUST NOT** be committed to Git:

1. **Transient Test Renders and Screen Captures (Binary PNGs):**
   - `67ce99d3_*.png`, `source_*.png`, `video_*.png`, `stage_*.png`, `raw_*.png`, `real_*.png`, `acceptance_*.png`.
2. **Local Ad-hoc Diagnostic Scripts (One-off verification runners in root):**
   - `capture_parity_frames.py`
   - `inspect_acceptance_clocks.py`
   - `phase8_prompt.txt`
   - `reproduce_playback_failure.py`
   - `run_visual_playback_acceptance.py`
   - `test_browser_draft_reconciliation.py`
   - `test_closure_proofs.py`
   - `test_dup_style.py`
   - `test_gate_a.py`
   - `test_gate_b.py`
   - `test_play_inspection.py`
   - `test_playwright_block_vars.py`
   - `test_playwright_phase8.py`
   - `test_render_layers_and_variables.py`
   - `test_reproduce_preview_failure.py`
   - `test_seeks_diagnostic.py`
   - `test_sim_hf.py`
   - `verify_preview_acceptance.py`
3. **Local IDE & Agent Workflow Configurations:**
   - `.agents/` (local environment rules).
4. **Third-Party Unvetted Cache:**
   - `motion_registry_cache/` (third-party component bundles pending licensing review).
5. **Runtime Databases, Media Storage, and Secrets:**
   - `viralmint.db`, `viralmint.db-wal`, `viralmint.db-shm` (contains local developer test data).
   - `storage/` (contains generated MP4s and downloaded test videos).
   - `.env` (contains local environment configuration).
   - `frontend/dist/` (compiled build artifacts).
   - `frontend/node_modules/` (vendored npm packages).
   - `.pytest_cache/`, `__pycache__/` (Python execution caches).

---

## 5. Accidental Credentials & Private Paths Audit

A full forensic diff inspection was conducted across all modified files:
- `git diff -U0 | findstr -i "api_key password secret auth_token"`
- **Result:** Zero hardcoded private credentials. All occurrences are unit-test mock keys (`anthr-key`, `openai-env-key`) or runtime configuration lookups.
- **Path Audit:** Zero private machine paths are hardcoded in application logic. Storage paths resolve dynamically via `settings.STORAGE_ROOT` or `StudioService.project_dir()`.

---

## 6. Exact Reproduction Procedure

To reproduce the verified working state on any fresh clone:

1. **Clone repository and checkout baseline:**
   ```bash
   git clone <repo-url> ViralMint
   cd ViralMint
   git checkout main
   ```
2. **Install Python dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```
3. **Install Frontend dependencies and build:**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
4. **Run DB Migrations:**
   ```bash
   python -c "import asyncio; from backend.database import init_db; asyncio.run(init_db())"
   ```
5. **Execute Full Automated Test Suite:**
   ```bash
   python -m pytest tests/ -q
   # Expected: 2934 passed, 13 skipped, 0 failed
   ```
6. **Launch Application:**
   ```bash
   python run.py
   # Navigates to http://localhost:16888 / http://localhost:5173/motion
   ```

---

## 7. Product Owner Authorization Request

To execute this checkpoint, the following command sequence is prepared and waiting for authorization:

```bash
# 1. Stage tracked modifications and new Phase 8 source files
git add .gitignore backend/ frontend/src/ tests/ scripts/ *.md PROVENANCE_INVENTORY.csv

# 2. Verify staging matches the manifest exactly
git status --short

# 3. Commit checkpoint
git commit -m "feat(phase8): canonical project document, idempotency contract, motion studio UI, and visual playback baseline"
```

**Status:** Standing by. No `git add` or `git commit` has been executed.
