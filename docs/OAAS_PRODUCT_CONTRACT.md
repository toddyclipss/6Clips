# 6CLIPS / VIRALMINT OAAS PRODUCT CONTRACT

**Status:** Canonical & Non-Negotiable  
**Architecture:** OAAS (Outcome as a Service)  
**Version:** 1.0.0 (Wave 17)  

---

## 1. Core Philosophy: OAAS vs SaaS

6Clips / ViralMint is **OAAS (OUTCOME AS A SERVICE)**, **NOT SAAS (SOFTWARE AS A SERVICE)**.
- We sell completed video and publication outcomes, not access to a complex suite of disconnected tools.
- A user states a goal; the Main Agent plans, executes, verifies, and delivers finished videos and publication outcomes.
- Minimize clicks, configurations, dashboards, and manual operations.
- Human intervention is strictly reserved for creative decisions, explicit editorial approvals, credential authorization, or genuine exception recovery.
- No unsolicited or quietly automated publication to external platforms without explicit user authorization or a configured standing policy.

---

## 2. Product Navigation Lock: Exactly 5 Destinations

The workspace navigation has **ONLY FIVE** top-level destinations:
1. `Trends` — Discover viral angles, hooks, and topic intelligence.
2. `My Channel` — Unified channel health, authorized accounts, concise publication delivery status, real analytics results, and required interventions.
3. `Library` — Curated media assets, sound tracks, and approved video revisions.
4. `Motion Graphics` — Canvas, visual composition, and the integrated HyperFrames block catalog.
5. `Messages` — High-priority notifications, editorial approval requests, and agent communication.

### Prohibitions & Absorptions
- **No 6th Top-Level Destination:** The sidebar must never exceed these 5 primary destinations.
- **Settings:** Remains a compact modal utility, never an expanded top-level production destination.
- **Catalog:** Absorbed completely into `Motion Graphics` as an integrated block drawer and template selector. No standalone `/catalog` navigation entry.
- **Clip Studio:** Functions absorbed into `Motion Graphics` before removing legacy routes; `/clips` and `/tools` maintained for backwards compatibility.
- **Distribution, Scheduling & Analytics:** Background services only. Surfaced exclusively as concise status cards, pending approvals, and verified metrics inside `My Channel` and the Main Agent chat. Large standalone SaaS dashboards are prohibited.

---

## 3. Reality Lock & Anti-Fake Acceptance

### Zero Tolerance for Synthetic Illusions in Production
- **No Fake Acceptance:** No new production demo, mock, simulation, fixture, fabricated provider receipt, fake analytics, placeholder content masquerading as genuine completed work, or periodic fake tick.
- **Production UI Hygiene:** Production controls such as `Load Test Fixture`, `Preview with Isolated Test Fixture`, or `Trigger Worker Tick` are strictly forbidden in standard user interfaces.
- **Segregated Developer Utilities:** Technical scaffolding and isolated mocks belong strictly in automated unit tests (`tests/`), never in user-facing code or production routes.
- **State Truth:**
  - `NOT_CONNECTED` != published.
  - Local queue != provider receipt.
  - Test fixture != live analytics.
  - `npm run build` != end-to-end product acceptance.
  - Metadata-only inventory entry != operable HyperFrames block.
- **Fail-Closed Principle:** If functionality lacks live credentials, valid tokens, or network connectivity, it must accurately report `PENDING_CREDENTIALS`, `NOT_CONNECTED`, `BLOCKED`, or `LOCAL_ONLY`. Never report `LIVE_PUBLISHED`, `PROVIDER_VERIFIED`, `196 OPERABLE`, or `DONE` without matching, reproducible proof.

---

## 4. 196 Original HyperFrames Identity Lock

- **Target Census:** Exactly **196 ORIGINAL** HyperFrames donor blocks, identified by authentic donor slugs and grouped using genuine upstream category evidence.
- **No Synthetic Substitutes:** Custom 6Clips blocks or synthetic lookalikes must never be labeled as HyperFrames originals.
- **Retired Block Exclusion:** `creator-hud` and `glitch-transition` are retired 6Clips legacy blocks. They must remain completely excluded from the donor catalog inventory and quarantined.
- **Read-Only Donor Guarantee:** The donor repository (`C:\Users\toddy\Desktop\hyperframes`) is strictly a read-only reference. Shipping 6Clips runtime code must be self-contained and never reference external donor disk paths.
- **Licensing & Rights Integrity:** Preserve upstream MIT licenses, runtime notices, and distinguish permissive code licenses from proprietary brand assets or trademarks (e.g., iPhone, MacBook, Stripe, GitHub logos require generic placeholders and disclaimers).
- **Census State Definitions:**
  - *Inventoried:* Recognized in the canonical 196 manifest.
  - *Shipped on Disk:* Self-contained HTML, JS, and CSS files vendored in `backend/catalog/shipped_blocks/`.
  - *Active Operable:* Fully verified across insertion, variable mutation, CAS revision, dual-aspect render (9:16 & 16:9), and physical MP4 playback.
  - *Stage 1 Ported:* Ported to disk with local runtime adapter, awaiting live browser and rendering acceptance.
  - *Unported:* Awaiting porting to self-contained disk bundles.

---

## 5. Distribution, Scheduling & Real Provider Receipts

- **Editorial Approval:** Immutable, HMAC-SHA256 signed approval receipts bound to specific project revisions (`project_revision`) and artifact hashes (`artifact_sha256`).
- **Real Provider Dispatch:** External API requests to YouTube Data API v3, TikTok Content Posting API, Instagram Graph API, or X API v2 require valid, scoped OAuth credentials.
- **Receipt Integrity:**
  - Receipts require real remote post IDs, remote permalinks, and provider-verified timestamps.
  - Fake receipt IDs (e.g., `fake_*`) are strictly rejected by production transports and analytics ingestors.
- **Queue State Transitions:**
  - `DRAFT` → `WAITING_FOR_APPROVAL` → `WAITING_FOR_ACCOUNT` (or `PENDING_CREDENTIALS`) → `READY_TO_SCHEDULE` → `SCHEDULED` → `DISPATCHING` → `PROVIDER_ACCEPTED` → `PUBLISHED_VERIFIED` (or `FAILED_RETRYABLE` / `BLOCKED`).
- **Offline Host Truth:** ViralMint operates locally. Scheduled jobs cannot execute when the host computer is turned off, asleep, or the backend is stopped. The background worker evaluates queued jobs during active backend lifecycle.

---

## 6. Grounded Analytics Ingestion

- **Authentic Metrics Ingestion:** Metrics are ingested solely from actual linked provider accounts via official APIs or verified publication receipts.
- **Attribution & Provenance:** Every metric observation records exact observation timestamps, provider name, account reference, and remote post ID.
- **Disconnected Truth:** Without linked accounts or verified receipts, analytics services truthfully report `NO_VERIFIED_PUBLICATIONS`, `PENDING_CREDENTIALS`, or `NOT_CONNECTED`. Synthetic traffic generation or simulated follower growth in production is strictly prohibited.
