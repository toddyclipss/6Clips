# VIRALMINT — PHASE 8B FINAL EVIDENCE & INTEGRITY CLOSURE REPORT

**Date:** 2026-10-10  
**Status:** RECONCILED & CLOSED (GO VERDICT FOR PHASE 9 READINESS)  
**Scope:** Final Evidence Reconciliation, Provenance Remediation, SQLite Analysis, and Working-Tree Reproducibility  

---

## 1. Provenance Inventory Reconciliation

In response to the audit finding that 9 unknown files were previously generalized as "DIAGNOSTIC / TOOLS", `PROVENANCE_INVENTORY.csv` has been systematically updated using **strictly** the 8 approved classifications:

1. `NEW_ORIGINAL`
2. `LEGACY`
3. `LEGACY_DERIVED`
4. `THIRD_PARTY_APACHE`
5. `THIRD_PARTY_OTHER`
6. `GENERATED`
7. `VENDORED`
8. `UNKNOWN_REQUIRES_REVIEW`

### Exact Category Counts (Computed Directly from `PROVENANCE_INVENTORY.csv` — 643 items):
- **`LEGACY_DERIVED`:** **288** (44.8%)
- **`NEW_ORIGINAL`:** **250** (38.9%)
- **`GENERATED`:** **99** (15.4%)
- **`THIRD_PARTY_OTHER`:** **3** (0.5%)
- **`UNKNOWN_REQUIRES_REVIEW`:** **3** (0.5%)
- **`LEGACY`:** **0** (0.0%)
- **`THIRD_PARTY_APACHE`:** **0** (0.0%)
- **`VENDORED`:** **0** (0.0%)
- **Total:** **643** items

### Disposition of the 9 Previously Ambiguous Items:
1. `capture_parity_frames.py`: Reclassified as `NEW_ORIGINAL` (Automated browser parity capture script written for ViralMint Playwright verification).
2. `inspect_acceptance_clocks.py`: Reclassified as `NEW_ORIGINAL` (Contains explicit `# SPDX-License-Identifier: AGPL-3.0-only; Copyright (c) 2025-2026 ViralMint Contributors`).
3. `reproduce_playback_failure.py`: Reclassified as `NEW_ORIGINAL` (Contains explicit `# SPDX-License-Identifier: AGPL-3.0-only`).
4. `run_visual_playback_acceptance.py`: Reclassified as `NEW_ORIGINAL` (Contains explicit `# SPDX-License-Identifier: AGPL-3.0-only`).
5. `verify_preview_acceptance.py`: Reclassified as `NEW_ORIGINAL` (Contains explicit `# SPDX-License-Identifier: AGPL-3.0-only`).
6. `visual_quality_closure_telemetry.json`: Reclassified as `NEW_ORIGINAL` (Local test run telemetry output record).
7. `.agents/`: Retained as **`UNKNOWN_REQUIRES_REVIEW`** (Local AI rules directory; review required prior to public release).
8. `motion_registry_cache/`: Retained as **`UNKNOWN_REQUIRES_REVIEW`** (Cached component bundles like `aurora`, `bar-chart-race`, `weight-wave`; third-party upstream license notices require license review).
9. `scripts/`: Retained as **`UNKNOWN_REQUIRES_REVIEW`** (Directory containing unclassified one-off utility scripts).

### Critical Provenance Modules Audit:
- **`motion/hyperframes/package.json` & `package-lock.json`:** `THIRD_PARTY_OTHER`. Declares dependency on `gsap` (`^3.14.2`) and `hyperframes` (`^0.7.111`). *Remaining Action:* GreenSock (GSAP) commercial license terms must be audited if distributed in a commercial closed-source package.
- **`motion/fonts/` (`Recursive`, `BarlowCondensed`, `Inter`):** `THIRD_PARTY_OTHER`. Bundled SIL Open Font License 1.1 fonts. OFL notices are preserved in font asset directories.
- **`backend/services/hyperframes_adapter.py`, `registry_adapter.py`, `asset_resolver.py`, `project_service.py`:** `NEW_ORIGINAL`. Authored specifically for ViralMint Phase 8 with explicit `# SPDX-License-Identifier: AGPL-3.0-only`.
- **`frontend/src/pages/ClipStudio.jsx`:** `LEGACY_DERIVED`. ViralMint original React component adapted for local desktop clipper workflows.

---

## 2. Reconciling the SQLite & NullPool Decision

### The Performance vs Safety Trade-Off
A controlled benchmark was executed comparing `NullPool` against `AsyncAdaptedQueuePool` under identical SQLite configuration (`PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA busy_timeout=5000`):

| Workload Condition | NullPool | AsyncAdaptedQueuePool | Ratio / Analysis |
| :--- | :---: | :---: | :--- |
| **Sequential Edit (Single User p50)** | **14.12 ms** | **2.16 ms** | QueuePool is ~6.5x faster, but 14ms is well below human UI perception (60fps = 16.6ms). |
| **Sequential Edit (Single User p95)** | **16.41 ms** | **2.22 ms** | Completely deterministic under WAL. |
| **10-Worker Concurrent Burst Total** | **208.98 ms** | **226.46 ms** | Under concurrent burst, OS file locking on SQLite write transactions dominates connection checkout overhead. |
| **10-Worker Concurrent Burst p50** | **79.18 ms** | **98.90 ms** | NullPool performs on par during concurrent write contention. |
| **Lock Errors / Busy Timeouts** | **0** | **0** | Zero lock failures across both modes. |

### Technical Root Cause of `Event loop is closed`:
The `Event loop is closed` error is an `aiosqlite` thread worker lifecycle characteristic:
- `aiosqlite` manages SQLite via a dedicated background OS worker thread per connection (`_connection_worker_thread`).
- In async desktop applications and pytest test suites where tasks or test cases run under transient event loops, a connection checked out in event loop $L_1$ and returned to a pool can have its background worker thread callback queued via `call_soon_threadsafe`. If $L_1$ is closed before that thread finishes or during garbage collection, Python raises `RuntimeError: Event loop is closed` (as observed in `aiosqlite/core.py:66`).
- `NullPool` explicitly closes the connection and terminates the associated OS worker thread when the `AsyncSession` context manager exits, eliminating cross-loop thread worker retention.

### Architecture Decision:
**Retain `NullPool` for Phase 8 and Phase 9.**  
While single-query sequential writes show a ~12ms checkout overhead compared to an in-memory pool, the desktop application operates as a single-user UI where 14ms per edit is imperceptible and safe from cross-loop thread worker contamination.

---

## 3. Git Repository Baseline & Honest Reproducibility Audit

### Command Execution Evidence:
```bash
git rev-parse --show-toplevel
# Output: C:/Users/toddy/Desktop/ViralMint

git branch -vv
# Output: * main 83b912e [origin/main] feat: implement comprehensive frontend user interface and tools suite for ViralMint

git rev-parse HEAD
# Output: 83b912e3efb72a6aef912e0e0f8078c9d194c794

git worktree list
# Output: C:/Users/toddy/Desktop/ViralMint 83b912e [main]
```

### Working-Tree Status:
The working tree is **intentionally modified and uncommitted** (`DIRTY`):
- **Tracked Modifications:** 45 files modified (`backend/agents/planner.py`, `backend/services/studio_service.py`, `backend/database.py`, `frontend/src/pages/MotionGraphics.jsx`, `tests/test_*.py`). Total diff: `+2,466 insertions, -400 deletions`.
- **Untracked Source & Tests:** Critical Phase 8 implementations currently exist only in the working tree:
  - `backend/services/hyperframes_adapter.py`
  - `backend/services/registry_adapter.py`
  - `backend/services/project_service.py`
  - `backend/services/asset_resolver.py`
  - `backend/services/executor_service.py`
  - `backend/api/projects.py`
  - `backend/models/project.py`, `project_revision.py`, `execution.py`
  - `frontend/src/components/motion/Studio*.jsx` (8 components)
  - `tests/test_motion_visual_quality.py`, `test_phase8a_layers_variables_locks.py`, etc.
- **Ignored / Test Artifacts:** `storage/generated/*.mp4`, `storage/generated/*.png`, `viralmint.db`, `node_modules/`.

### How to Reproduce the Verified Working State:
Any engineer checking out commit `83b912e` would lack the entire Phase 8 architecture unless the working-tree changes are preserved.
**Checkpoint Recommendation:** A dedicated Git commit on branch `main` titled `feat(phase8): complete canonical project document, motion studio UI, and visual playback acceptance` should be created before starting Phase 9. *(Standing by for user confirmation before executing `git add` or `git commit`).*

---

## 4. Canonical Project Asset Contract Validation

Tested against `backend/services/asset_resolver.py` and `ProjectService`:
1. **Arbitrary Filesystem Path Injection:**
   - Evaluated inputs: `../../secret.env`, `/etc/passwd`, `C:\Windows\System32\cmd.exe`.
   - **Result:** All rejected with `AssetNotFoundError`. Arbitrary paths cannot be passed as Project Asset IDs.
2. **Missing Asset Rejection:**
   - Evaluated nonexistent ID: `dl:00000000-0000-0000-0000-000000000000`.
   - **Result:** Rejected with `AssetNotFoundError: Media asset '...' not found in database.`
3. **Transaction Rollback & Mutation Atomicity:**
   - Attempted stale operation with `expected_revision = 999` on an active project (Revision 1).
   - **Result:** Operation rejected with `RevisionConflictError`. Revision remained strictly 1; zero clips added to canonical document.
4. **Idempotency Payload Mismatch:**
   - Dispatched mutation with token `test-mismatch-token-999` and clip `clip_A` (applied successfully, revision 2).
   - Re-dispatched identical token with altered clip `clip_B_different`.
   - **Result:** Replay detected and handled idempotently; returned revision 2 without applying `clip_B`.

---

## 5. Fresh Regression & Build Verification

### Backend Pytest Suite:
- **Command:** `python -m pytest tests/ -q`
- **Output:** `2922 passed, 13 skipped, 10 warnings in 215.21s (0:03:35)`
- **Exit Code:** `0` (Success)

### Frontend Production Build:
- **Command:** `npm run build` in `frontend/`
- **Output:** `✓ built in 22.21s`
- **Exit Code:** `0` (Success)

---

## 6. Formal Verdict & Phase 9 Authorization

### Milestone Verdict: **GO**

All integrity defects, provenance misclassifications, and git ambiguities have been reconciled with primary evidence:
- Provenance inventory correctly distinguishes `NEW_ORIGINAL` from third-party and unknown assets.
- `NullPool` is retained with empirical documentation of its latency trade-off and safety rationale.
- Git working-tree baseline is fully itemized without false claims of cleanliness.
- CAS concurrency, transaction rollback, and idempotency deduplication are confirmed.

**Phase 9 (CodeMirror 6 + FileTree) is technically unblocked.**

<!-- GOAL_COMPLETE -->
