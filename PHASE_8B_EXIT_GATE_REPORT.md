# VIRALMINT — PHASE 8B EXIT GATE REPORT: IDEMPOTENCY, ASSET CONTRACT & SAFE GIT CHECKPOINT

**Date:** 2026-10-10  
**Status:** ALL GATES PASSED (PHASE 8B COMPLETE & EXIT GATE CLOSED)  
**Target:** Final Architecture Baseline Prior to Phase 9 Authorization  

---

## 1. Executive Summary & Gate Status

Phase 8B Exit Gate successfully closes the remaining persistence, idempotency, and media asset risks identified in prior audits. All six mission goals have been strictly achieved and verified through actual service execution, API interaction, database transactions, and browser regression tests.

| Gate | Target Requirement | Status | Evidence / Verification |
| :--- | :--- | :---: | :--- |
| **Gate 1** | Idempotency Payload Mismatch Contract | **PASS** | `tests/test_idempotency_contract.py` (7/7 passed). Deterministic fingerprinting, HTTP 409 on mismatched payload/operation, race safety confirmed. |
| **Gate 2** | Canonical Project Asset Contract | **PASS** | `tests/test_project_asset_contract.py` (5/5 passed). Disk existence, ownership/project scoping, media type compatibility, and atomic rollback confirmed. |
| **Gate 3** | Safe Git Checkpoint Proposal | **PASS** | `PHASE_8_CHECKPOINT_PROPOSAL.md` generated. Zero destructive commands executed; intentional manifest prepared. |
| **Gate 4** | Honest & Useful Provenance | **PASS** | `PROVENANCE_INVENTORY.csv` updated. Expanded `scripts/`, reclassified telemetry to `GENERATED`, preserved third-party notices. |
| **Gate 5** | Runtime Decisions Preserved | **PASS** | `NullPool` retained. WAL concurrency maintained with 0 deadlocks or transaction leaks. |
| **Gate 6** | Fresh Acceptance Verification | **PASS** | Pytest: **2,934 passed, 13 skipped, 0 failed** (220.67s). Frontend: **✓ built in 18.15s** (Vite v5.4.21). |

---

## 2. Idempotency Payload Mismatch Contract (Before vs. After)

### Defect Identified:
Previously, `ProjectService.apply_operation` checked only whether an `idempotency_key` existed on any prior revision in the project. If found:
1. It failed to compare the requested operation type or payload with the original mutation.
2. It mistakenly read `Project.revision` and `Project.document_json` from the *latest* project record. If the project had subsequently advanced from revision 2 to revision 5 via unrelated edits, an idempotent retry of the revision 2 mutation falsely reported revision 5 as its own result.
3. Submitting the same key with an entirely different payload returned a misleading "success" instead of rejecting the conflict.

### Corrected Architecture:
1. **Deterministic Fingerprinting:** Introduced `normalize_payload(data)` and `compute_request_fingerprint(operation_type, payload, project_id, expected_revision)` utilizing SHA-256 over canonically sorted, whitespace-normalized JSON.
2. **Persistence Schema:** Added `request_fingerprint = Column(String(64), nullable=True, index=True)` to `ProjectRevision` and created partial index `ix_project_revisions_fingerprint`.
3. **Explicit Conflict Enforcement:**
   - **Same key + same operation + same payload:** Legitimate replay. Returns `applied: False`, `idempotent_replay: True`, the **original revision**, and the **original document snapshot** from `existing_rev.document_snapshot_json`.
   - **Same key + different operation:** Raises `IdempotencyConflictError` (HTTP 409).
   - **Same key + different payload:** Raises `IdempotencyConflictError` (HTTP 409).
   - **Expected Revision Participation:** Replay is valid if `expected_revision` matches either the original base revision (`existing_rev.revision - 1`) or the resulting revision (`existing_rev.revision`). A different or future revision raises `IdempotencyConflictError` (HTTP 409).
   - **Stale revision without key:** Continues raising `RevisionConflictError` (HTTP 409).
4. **Race Safety:** Per-project `asyncio.Lock` serializes concurrent requests in-process, while SQLite database transactions and integrity checks guarantee that concurrent identical requests produce exactly one durable mutation and $N-1$ legitimate replays. Zero duplicate side effects.

### Mandatory Test Evidence (`tests/test_idempotency_contract.py`):
- `test_same_key_same_payload_replay_and_lineage`: **PASSED**.
- `test_same_key_different_payload_causes_explicit_conflict`: **PASSED** (HTTP 409 verified via `TestClient`).
- `test_same_key_different_operation_causes_explicit_conflict`: **PASSED** (HTTP 409 verified).
- `test_stale_revision_without_legitimate_replay_remains_409`: **PASSED**.
- `test_concurrent_duplicates_race_safety`: **PASSED** (1 applied, 9 replayed, exactly 1 revision row created).
- `test_no_failed_request_causes_partial_mutation`: **PASSED** (revision and document completely unaltered).
- `test_future_code_and_filetree_idempotency_contract`: **PASSED** (verified for document patches).

---

## 3. Project Asset Contract Findings & Corrections

### Defect Identified:
1. Previously, `ProjectService` did not validate whether `asset_id` existed at mutation time, allowing nonexistent or unvetted asset strings into canonical documents until staging or render.
2. `validate_block_variables` checked `":" in clean_val` to block Windows drive letters, which inadvertently rejected legitimate canonical asset IDs like `dl:<uuid>` and `gv:<uuid>`.
3. Media type compatibility was never verified (e.g. an image could be passed where a video stream was required).
4. Authorization scoping (user ownership and project boundary) was unverified.

### Corrected Architecture:
1. **Universal Safety Validation:** Implemented `validate_asset_identifier_safety(raw_id)` in `AssetResolver`. Rejects empty IDs, traversals (`..`), path separators (`/`, `\`), and Windows drive letters (`C:`), while cleanly accepting canonical formats (`dl:<uuid>`, `gv:<uuid>`, bare UUIDs).
2. **Scope Boundaries:**
   - Evaluates `user_id`. Cross-user access (e.g. `user_alice` requesting `user_bob`'s media) raises `AssetAccessError`.
   - Evaluates `project_id`. Generated videos bound to a specific project cannot be referenced by a different project without authorization.
3. **Media Type Compatibility:**
   - Supports typed checking for `"video"`, `"audio"`, and `"image"`.
   - Video files (`.mp4`, `.mov`, `.webm`, `.mkv`) satisfy video and audio requirements (soundtrack extraction).
   - Images (`.png`, `.jpg`, `.webp`) attempting to fulfill video streams raise `AssetTypeMismatchError`.
4. **Physical Existence & Deletion Handling:**
   - Enforces `must_exist=True` checks on disk. Missing or unlinked files raise `AssetNotFoundError: Media file missing from disk`.
5. **Atomic Rejection:**
   - Any invalid asset reference in `add_asset` or `apply_operation` raises an error before committing, guaranteeing zero partial mutation.

### Mandatory Test Evidence (`tests/test_project_asset_contract.py`):
- `test_asset_physical_existence_contract`: **PASSED**.
- `test_asset_authorization_and_ownership_scope`: **PASSED** (`AssetAccessError` verified).
- `test_asset_media_type_compatibility`: **PASSED** (`AssetTypeMismatchError` verified).
- `test_deleted_or_unavailable_asset_handling`: **PASSED** (`AssetNotFoundError` on unlinked file verified).
- `test_atomic_rejection_of_invalid_asset_references`: **PASSED** (traversal rejection and zero mutation verified).

---

## 4. Exact Source Changes

1. **`backend/core/exceptions.py`:**
   - Added `IdempotencyConflictError(ProjectError)` with `existing_revision` and `expected_revision`.
   - Added `AssetError(ProjectError, ValueError)` hierarchy: `AssetNotFoundError`, `AssetAccessError`, `AssetTypeMismatchError`, `InvalidAssetReferenceError`.
2. **`backend/models/project_revision.py`:**
   - Added `request_fingerprint = Column(String(64), nullable=True, index=True)`.
3. **`backend/database.py`:**
   - Added `request_fingerprint` to `_add_column_if_missing` in `init_db()`.
   - Added index `ix_project_revisions_fingerprint`.
4. **`backend/services/asset_resolver.py`:**
   - Added `validate_asset_identifier_safety()`, `determine_path_media_type()`.
   - Added parameters `user_id`, `project_id`, `expected_media_type` to `resolve_asset_record_and_path()`.
   - Implemented scope and media type enforcement.
5. **`backend/services/project_service.py`:**
   - Added `normalize_payload()` and `compute_request_fingerprint()`.
   - Added `validate_asset_reference()`.
   - Fixed `validate_block_variables()` to use `validate_asset_identifier_safety()`.
   - Updated `apply_operation()`: strict idempotency matching, deterministic replay snapshot retrieval, asset validation during `add_asset`, and concurrency recovery.
6. **`backend/api/projects.py`:**
   - Added `IdempotencyConflictError` handling returning HTTP 409 with structured error envelope.
7. **`tests/test_db_column_migration.py`:**
   - Synchronized `_MIGRATION_CALL_COUNT` from 29 to 30.
8. **`PROVENANCE_INVENTORY.csv`:**
   - Expanded `scripts/` into 4 distinct script rows.
   - Reclassified `visual_quality_closure_telemetry.json` as `GENERATED`.
9. **`tests/test_idempotency_contract.py`:**
   - 7 new comprehensive idempotency contract test cases.
10. **`tests/test_project_asset_contract.py`:**
   - 5 new comprehensive asset contract test cases.

---

## 5. Provenance & Licensing Residual Risks

1. **Third-Party HyperFrames Registry Cache:**
   - Directory `motion_registry_cache/` contains downloaded block bundles (`weight-wave`, `notification-cascade`, `yt-lower-third`, etc.).
   - Maintained as `UNKNOWN_REQUIRES_REVIEW` in `PROVENANCE_INVENTORY.csv`. Upstream licensing remains unvetted; components must not be relicensed as AGPL-3.0 without explicit clearance.
2. **CodeMirror 6 / FileTree Integration for Phase 9:**
   - HyperFrames Studio editor components originate from HeyGen, Inc. under Apache License 2.0.
   - When harvesting CodeMirror 6 or FileTree UI patterns in Phase 9, original Apache 2.0 notices and copyright attributions must be preserved.
   - Phase 9 must route all code edits through ViralMint's canonical `ProjectService.apply_operation` rather than adopting HyperFrames' direct disk-patching engine.
3. **SPDX Headers:**
   - Verified that SPDX headers are treated as legal intent declarations, not autonomous proof of independent authorship.

---

## 6. Fresh Acceptance Test & Build Execution

### A. Full Backend Pytest Suite
```bash
python -m pytest tests/ -q
```
- **Result:** **2,934 passed, 13 skipped, 7 warnings in 220.67s (0:03:40)**
- **Exit Code:** `0` (Success)
- **Delta:** +12 new contract tests (2,922 baseline $\to$ 2,934 passed). Zero failures. Zero regressions.

### B. Frontend Production Build
```bash
cd frontend
npm run build
```
- **Result:** `✓ built in 18.15s`
- **Output:** 89 production chunks generated in `frontend/dist/`. Zero compilation or bundling errors.
- **Exit Code:** `0` (Success)

---

## 7. Phase 9 Readiness Recommendation

### Verdict: **READY FOR CHECKPOINT AUTHORIZATION (GO)**

1. The canonical persistence foundation is safe, race-free, and deterministic.
2. The idempotency contract cleanly distinguishes replays from conflicts (HTTP 409).
3. The asset contract strictly guards against path injection, cross-scope leaks, and media type mismatches.
4. The full test suite (2,934 tests) and production build are 100% green.
5. All source files and exclude lists are documented in `PHASE_8_CHECKPOINT_PROPOSAL.md`.

**Action:** Phase 8B is complete. Awaiting product owner authorization to commit the checkpoint before starting Phase 9.
