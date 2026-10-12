# Rule: Media Streaming Security, Test Sandbox Isolation, and Authentic UI Playback

## 1. Test Sandbox Isolation & Database Immutability
- Acceptance tests and browser end-to-end verifications MUST NOT connect to or mutate the production database (`viralmint.db`).
- All acceptance runs must initialize an isolated sandbox:
  - Ephemeral directory (`VIRALMINT_DATA_DIR` pointed to a temporary folder).
  - Dedicated ephemeral SQLite database and storage tree.
  - Dedicated test server ports (e.g. backend port `16895`, Vite frontend port `5175`).
  - Pre- and post-test SHA-256 assertions guaranteeing that production database files remain 100% byte-for-byte identical.
- Process teardown must be strictly guaranteed via `finally` blocks, terminating all ephemeral backend/frontend processes and purging temporary directories.

## 2. Media Streaming Endpoint Security & Record Authorization
- Any endpoint serving media files from disk (e.g. `stream_downloaded`, `stream_video`) MUST enforce:
  1. **Record-Level Ownership:** Check that the requesting user matches the database record's `user_id`. Mismatched ownership must return HTTP 403 Forbidden.
  2. **Strict Root Containment:** Use `path.resolve().is_relative_to(root.resolve())` against strictly authorized roots (`settings.STORAGE_ROOT` and `settings.MOTION_DIR / "studio"`).
  3. **Strict Extension Whitelist:** Validate extensions against `ALLOWED_MEDIA_EXTENSIONS` (`{".mp4", ".webm", ".mkv", ".mov", ".avi", ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".srt", ".vtt"}`). Non-media extensions (including `.txt`) must return HTTP 403 Forbidden.
  4. **Tool Job Asset Isolation:** Distinct endpoints (`/api/library/asset/{id}`) serving tool job outputs (such as transcripts and auto-chapters) may explicitly allow document extensions (`.txt`, `.json`, `.csv`, `.zip`, `.md`) without exposing general streaming endpoints.

## 3. Authentic UI Interaction & Non-Synthetic Media Verification
- Acceptance tests MUST reproduce 100% authentic user flows:
  - Use genuine, non-synthetic user-owned footage (e.g. real gaming gameplay capture), never synthetic test-pattern loops.
  - Trigger file imports through visible UI buttons (`expect_file_chooser()` -> visible "Import" button).
  - Validate natural card rendering, metadata badges, and natural drawer opening on tile click.
  - Assert real video playback (`readyState >= 1`, positive `currentTime` progression, pause, seek, volume/mute).
  - Internal framework state manipulation (React Fiber, artificial dispatch) MUST NEVER be used as proof of user-facing functionality.
