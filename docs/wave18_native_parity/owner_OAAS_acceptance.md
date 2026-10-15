# OAAS First-Run & Native Motion Editor Acceptance Document

**Wave:** 18  
**Architecture:** OAAS (Outcome as a Service)  
**Editor Model:** Single Native Motion Graphics Editor  

---

## 1. Product Mission & Owner Invariant Enforcement

- **Outcome as a Service (OAAS):** 6Clips delivers completed video outcomes and authorized publications rather than a fragmented cockpit of SaaS dashboards.
- **Single Motion Graphics Editor:** Clip Studio and Tools are dissolved into native Motion Graphics editing commands, timeline tracks, and inspector panels.
  - Exactly **ONE** player and canvas.
  - Exactly **ONE** transport playhead clock.
  - Exactly **ONE** timeline and selection model.
  - Exactly **ONE** authoritative `ProjectRevision` CAS document.
- **First-Run Default Landing:** User sessions and root `/` immediately open `/motion` with the Main Agent goal request prompt readily accessible, even prior to project creation.
- **Navigation Lock:** Exactly 5 top-level workspace destinations in strict priority:
  1. `Motion Graphics` (`/motion`)
  2. `Trends` (`/trends`)
  3. `My Channel` (`/channels`)
  4. `Library` (`/videos`)
  5. `Messages` (`/messaging`)
- **Anti-Fake Guarantee:** Zero synthetic test fixture buttons (`Load Test Fixture`, `Preview with Isolated Test Fixture`, `Trigger Worker Tick`). Distribution and performance telemetry fail closed (`PENDING_CREDENTIALS` / `NOT_CONNECTED`) without fabricated metrics or fake receipts.

---

## 2. Capability Unification (30 Workflows Mapped to Native Motion)

All 21 legacy Tools and 9 Clip Studio workflows have been mapped to canonical Motion command executors mutating the unified CAS `ProjectRevision`:
- **Tools Inspector:** Located on the right-hand Refine inspector panel beside `Properties` and `Variables` under the `Tools` tab.
- **Timeline Operations:** Split (`S`), Trim, Slip, and Ripple Delete (`Shift+Delete`) operate directly on canvas clips.
- **Speech & Captions:** Word-level timestamps, silence auto-cut, and verbatim transcript corrections persist directly in the project document.
- **Zero Forked State:** All edits update the document SHA-256 and increment revision number atomically without secondary `ClipStudioState` or detached job records.

---

## 3. Grounded 196 Donor Inventory & Owner Reality Baseline

- **Total Donor Originals:** Exactly **196** canonical HyperFrames blocks.
- **Owner Reality Baseline:** Exactly **10** blocks are confirmed previewable in the running user application (`aurora`, `flowing-gradient`, `holographic`, `plasma`, `stripes`, `data-chart`, `instagram-follow`, `tiktok-follow`, `weight-wave`, `yt-lower-third`).
- **Disk Inventory:** **149** shipped blocks on disk.
- **Retired Block Exclusion:** `creator-hud` and `glitch-transition` are strictly quarantined and absent from the donor catalog.
- **Categorization Integrity:** 171 gallery-confirmed blocks and 25 fallback-mapped blocks categorized strictly according to authentic upstream evidence without fabricated classifications.
