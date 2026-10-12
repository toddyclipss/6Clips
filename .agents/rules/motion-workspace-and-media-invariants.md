# Rule: Motion Workspace Navigation, Media Error Bifurcation & Locked Track Guards

## 1. Motion Workspace Entry & Navigation Invariants
- **Clean Default Entry**: Direct navigation to `/motion` without an explicit `?projectId=` query parameter must initialize an empty project (0 clips, 0 blocks, 0 captions, 9:16 aspect ratio default) in **Create** workspace mode.
- **No Arbitrary Fallback**: Never fall back to arbitrary database records (e.g. `existing[0]`). If an explicit `?projectId=` does not exist or is unauthorized, cleanly create a fresh isolated project and update the browser URL state rather than crashing or implying an invalid project was loaded.
- **Persistent Project Continuity**: Explicit visits to existing projects (`?projectId=<id>`) must preserve the canonical Project Document and ProjectRevision history byte-for-byte across browser reloads.

## 2. Media Error Bifurcation (Preview vs Render)
- **Interactive Preview Tolerance**: If an asset is missing or unresolvable during interactive UI preview, the studio preview endpoint must render an informative, non-crashing placeholder (`.missing-media-block`) on the canvas stage and return HTTP 200 smoothly so the editor remains operable.
- **Strict Render / Export Halting**: Render and export staging must strictly raise `AssetNotFoundError` when any referenced asset is missing from disk. Never mark a project `READY_FOR_REVIEW`, approved, or successfully exported when media references are unresolved.

## 3. Locked Track Mutation Guards
- **Dual-Layer Enforcement**: Track lock state (`track["locked"] == True`) must be guarded at both the frontend UI interaction layer (drop handlers) and the backend CAS domain operations (`ProjectService.add_clip` and `ProjectService.add_block`).
- **No Revision Increment on Rejection**: Operations targeting locked tracks must immediately raise `ProjectError` without altering the canonical Project Document or incrementing the ProjectRevision.
