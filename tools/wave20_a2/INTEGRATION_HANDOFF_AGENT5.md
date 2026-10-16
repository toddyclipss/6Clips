# WAVE 20 / AGENT 2 — INTEGRATION HANDOFF TO AGENT 5 (INTEGRATOR)

## 1. Overview & Scope Ownership
- **Branch:** `wave20/02-create-review-minimal-ui`
- **Worktree:** `C:\Users\toddy\Desktop\ViralMint-wave20-02-ui`
- **Base Commit (`WAVE20_BASE_SHA`):** `51924aa5acaebb8e00f899015ee26c44ca86b4fe`
- **Ownership Scope:** `frontend/**`, `tools/wave20_a2/**`, `tests/wave20/a2/**`
- **Constraint Compliance:** Strictly zero edits to `backend/**`.

---

## 2. Key Architecture Decisions & Approved UX Implementation

### 2.1 Five Primary Sidebar Destinations
Sidebar strictly renders 5 primary destinations in order in `frontend/src/components/Layout.jsx`:
1. `Motion Graphics` (`/motion`) — default home landing
2. `Trends` (`/trends`)
3. `My Channel` (`/channels`)
4. `Library` (`/videos`)
5. `Messages` (`/messaging`)
*Settings* is positioned exclusively as a secondary utility at the bottom (`bottomItems`).

### 2.2 Create & Review Only (Refine Eliminated from Primary Journey)
- The primary stage switcher in `StudioToolbar.jsx` presents strictly **Create** (`stage-tab-create`) and **Review** (`stage-tab-review`).
- The former SaaS "Refine" tab is removed from the primary workflow.
- **Advanced Editing:** Available unobtrusively via the "Advanced Editing" button (`data-testid="studio-toolbar-advanced-editing-btn"` in toolbar, `data-testid="stage-open-advanced-btn"` on stage header).
- Lower timeline workspace (`StudioTimelineWorkspace`) and side panels are guarded by `advancedEditing`. The agent continues to have full program access to timeline state even when collapsed.

### 2.3 Complete Elimination of User-Facing HyperFrames Block Catalog
- Removed Tab 2 (Catalog) and all 196 block cards, category chips, hover preview, "Ask AI to insert block in chat", and "Add Block" buttons from `StudioResourcePanel.jsx`.
- Clean two-tab resource panel retained: `Media Assets` (user uploads/stock) and `Trends`.
- Removed `ghostPreview` frame, overlay, and escape listeners from `StudioPreviewStage.jsx`.
- Technical legacy routes (`/catalog`, `/clips`, `/tools`) redirect directly to `/motion` without shopping query parameters (`defaultQuery={{ tab: "catalog" }}` removed).
- Backing files (`catalogInventory.js`, `catalogOriginals.js`) are kept untouched for legacy CAS revision backward compatibility until Agent 5 physical removal gates.

### 2.4 Authenticated Real Job State
- `StudioPreviewStage.jsx` displays a real job status badge (`data-testid="studio-stage-job-status"`):
  - Consumes authentic `activeJob.step || activeJob.message || "composing"`.
  - Zero fabricated progress percentages (no fake `35%`, `78%`, etc.).
  - Reads directly from `useAppStore.activeJobs`, driven by genuine WebSocket events.

### 2.5 Review Panel Integrity & Truthful Publishing
- Added deliverable count badge: `data-testid="review-deliverables-count"`.
- Added clear Chat-based correction guidance: `data-testid="review-correction-guidance"`.
- Added truthful external publishing state footer: `NOT_CONNECTED / PENDING_CREDENTIALS` (no false claims of publication when third-party OAuth credentials are unauthenticated).

---

## 3. Typed Native Motion Adapter (`nativeMotionAdapter.js`)

Located at: `frontend/src/utils/nativeMotionAdapter.js`

### 3.1 Exported Symbols
```javascript
export const NATIVE_MOTION_SCHEMA_VERSION = "native_motion_v1"
export const CANONICAL_TRACK_TYPES = ["video", "audio", "captions", "effects", "transitions"]
export const TRACK_DROP_PERMISSIONS = {
  video: ["video", "image", "media", "broll"],
  audio: ["audio", "voiceover", "music", "sfx", "speech"],
  captions: ["captions", "caption", "text", "subtitle"],
  effects: ["effect", "filter", "shader"],
  transitions: ["transition"]
}

export function isNativeMotionV1(doc): boolean
export function validateTrackDrop(clip, targetTrack): { valid: boolean, reason?: string }
export function normalizeProjectForPlayer(projectOrDoc): {
  isNativeMotion: boolean,
  tracks: Array<object>,
  duration: number,
  fps: number,
  aspectRatio: string,
  aspect_ratio: string,
  schemaVersion: string
}
```

### 3.2 Content-Safe Drop Boundaries
- Prevents cross-category drag & drop corruption in `StudioTimelineWorkspace.jsx`.
- Captions cannot drop into audio tracks (`caption -> audio: valid=false`).
- Audio cannot drop into caption tracks (`audio -> captions: valid=false`).
- Video cannot drop into audio tracks (`video -> audio: valid=false`).
- Locked tracks unconditionally reject drops.

---

## 4. Verification & Testing Evidence

All tests executed locally on Windows host against real Microsoft Edge:

1. **Frontend Compilation (Vite):**
   ```powershell
   npm run build
   # Exit code: 0, 7967 modules transformed, production build generated in 22.51s
   ```

2. **Audit Verification Tool:**
   ```powershell
   python tools/wave20_a2/audit_minimal_oaas_ui.py
   # Exit code: 0, ALL AUDIT CHECKS PASSED: 8/8 gates compliant with OAAS contract
   ```

3. **Pytest Minimal UX Contract Suite:**
   ```powershell
   pytest tests/wave20/a2/test_wave20_a2_minimal_motion_ux.py -v
   # Exit code: 0, 7 passed in 0.43s
   ```

4. **Real Microsoft Edge Browser E2E Suite:**
   ```powershell
   pytest tests/wave20/a2/test_wave20_a2_edge_e2e.py -v
   # Exit code: 0, 4 passed in 32.25s
   # Captured responsive layout proofs:
   # - tools/wave20_a2/screenshots/edge_1920x1080_create.png (72.3 KB)
   # - tools/wave20_a2/screenshots/edge_1440x900_create.png  (66.5 KB)
   # - tools/wave20_a2/screenshots/edge_1366x768_create.png  (64.3 KB)
   ```

---

## 5. Merging & Integration Instructions for Agent 5
1. Merge branch `wave20/02-create-review-minimal-ui` into the Wave 20 integration candidate.
2. Ensure the junction or package install for `frontend/node_modules` is present during candidate build.
3. Keep backing files (`catalogInventory.js`, `catalogOriginals.js`) intact during pre-cutover to allow legacy projects to load. Agent 5 can physically remove them when GT-39/GT-42 cutover gates pass.
