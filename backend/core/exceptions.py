# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Custom exception hierarchy for ViralMint."""
import json
import logging as _logging


def safe_json_loads(raw, default=None, logger=None):
    """Parse JSON safely. Returns *default* on failure instead of raising."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        if logger:
            logger.warning("safe_json_loads failed: %s", exc)
        return default


class ViralMintError(Exception):
    """Base exception."""
    pass


# ── Scout errors ──────────────────────────────────────────────────────────────
class ScoutError(ViralMintError):
    pass

class PlatformUnavailableError(ScoutError):
    """Scout platform (TikTok, Douyin) is temporarily unavailable."""
    pass

class CookieExpiredError(ScoutError):
    """Session cookie is expired or invalid."""
    pass

class QuotaExceededError(ScoutError):
    """API quota (YouTube) exceeded."""
    pass


# ── Download errors ───────────────────────────────────────────────────────────
class DownloadError(ViralMintError):
    pass

class RateLimitError(DownloadError):
    """HTTP 429 — platform rate limiting."""
    pass

class VideoUnavailableError(DownloadError):
    """Video is private, deleted, or region-blocked."""
    pass

class DownloadTimeoutError(DownloadError):
    """The download exceeded its wall-clock cap and was abandoned.

    Like DownloadStalledError this is an ABANDONMENT: the worker thread is
    still running (Python cannot cancel it) and still owns the part-files in
    the output directory. Callers must treat it as terminal and must not
    start another attempt into the same output dir — see the note on
    `ytdlp_service._await_with_stall_guard`.
    """
    pass

class DownloadStalledError(DownloadError):
    """The transfer stopped moving bytes for longer than the stall budget.

    Distinct from a plain timeout: the wall clock had not run out, the
    download simply stopped making progress. yt-dlp's own retry budget
    (socket timeouts and retries with exponential backoff, times the
    format-fallback ladder) can burn well over an hour without delivering a
    single byte, and nothing in it measures progress.

    A DownloadError subclass so the batch runner's per-URL error collection
    and the UI error mapping route it without changes — but, like
    DownloadTimeoutError, it is TERMINAL inside `download_video`: the
    abandoned worker thread is still running and still owns the part-files,
    so a retry into the same output directory would race it.
    """
    pass


# ── Job lifecycle ─────────────────────────────────────────────────────────────
class JobCancelledError(ViralMintError):
    """The user cancelled the job while it was running.

    Cancellation flips the Job row to "cancelled" (backend/api/jobs.py) but
    does NOT interrupt the coroutine — long pipelines must poll
    `job_helper.job_cancelled()` at phase boundaries and raise this to stop.
    Runners catch it separately from real failures: no `job_failed` WS event
    for something the user did on purpose, and the row keeps its "cancelled"
    status instead of being overwritten by a late "success"/"failed" write.
    """
    pass


# ── Generation errors ─────────────────────────────────────────────────────────
class GenerationError(ViralMintError):
    pass

class VoiceGenerationError(GenerationError):
    pass

class VideoGenerationError(GenerationError):
    pass


# ── Upload errors ─────────────────────────────────────────────────────────────
class UploadError(ViralMintError):
    pass

class UploadAuthError(UploadError):
    """OAuth token missing or expired."""
    pass


# ── AI errors ─────────────────────────────────────────────────────────────────
class AIProviderError(ViralMintError):
    pass

class AIKeyMissingError(AIProviderError):
    pass


# ── Motion Graphics ───────────────────────────────────────────────────────────

class WhisperModelUnavailableError(ViralMintError):
    """The local speech-recognition model isn't on disk and couldn't be fetched.

    Whisper WEIGHTS are not bundled in the installer (the installer-size
    budget) — faster-whisper downloads them from HuggingFace into
    ``DATA_DIR/whisper-cache`` the first time a quality tier is used. Before
    this class existed, a first-run user with no network (or a blocked HF host)
    got the raw huggingface_hub error wrapped in a generic 500 / "job failed",
    which reads as "transcription is broken" rather than "the one-time download
    didn't happen". The message is user-facing.

    ENVELOPE mirrors HyperFramesNotInstalledError so the on-demand-dependency
    gates share one shape.
    """

    ENVELOPE = {
        "ok": False,
        "error_code": "whisper_model_unavailable",
        "action_url": "/settings#advanced",
    }


class MotionGraphicsError(ViralMintError):
    """Base for the local motion-graphics (HyperFrames) render path."""


class HyperFramesNotInstalledError(MotionGraphicsError):
    """The on-demand HyperFrames plugin is missing.

    Raised by the install gate every motion endpoint pre-flights, so the caller
    can answer with an "install it from Settings" pointer instead of a stack
    trace. Distinct from MotionRenderError: nothing was attempted.

    ENVELOPE is what the API layer returns instead of a 500 — a structured
    answer the UI keys on to offer the install, rather than an error string
    someone has to read to understand. It is a normal 200 on purpose: "this
    feature needs a one-click install" is a state, not a failure.
    """

    ENVELOPE = {
        "ok": False,
        "error_code": "hyperframes_not_installed",
        "message": (
            "Motion Graphics isn't installed. "
            "Install it from Settings → Add-ons."
        ),
        "action_url": "/settings#motion-graphics",
    }


class MotionRenderError(MotionGraphicsError):
    """A render was attempted and did not produce a usable MP4."""


# ── Project versioning & execution errors ─────────────────────────────────────
class ProjectError(ViralMintError):
    """Base for project document and versioning errors."""
    pass


class ProjectNotFoundError(ProjectError):
    """Requested project does not exist."""
    pass


class RevisionConflictError(ProjectError):
    """Optimistic concurrency conflict when applying an operation to a project."""
    def __init__(self, current_revision: int, expected_revision: int, message: str = None):
        self.current_revision = current_revision
        self.expected_revision = expected_revision
        msg = message or f"Conflict: project is at revision {current_revision}, but operation expected revision {expected_revision}."
        super().__init__(msg)


class IdempotencyConflictError(ProjectError):
    """Raised when an idempotency key is reused with a different operation type, mismatched payload, or incompatible revision scope."""
    def __init__(self, message: str, existing_revision: int = None, expected_revision: int = None):
        self.existing_revision = existing_revision
        self.expected_revision = expected_revision
        super().__init__(message)


class AssetError(ProjectError, ValueError):
    """Base error for media asset resolution, ownership scope, and type compatibility."""
    pass


class AssetNotFoundError(AssetError):
    """Raised when an asset record or its physical media file is missing."""
    pass


class AssetAccessError(AssetError, PermissionError):
    """Raised when an asset is outside authorized project or user scope."""
    pass


class AssetTypeMismatchError(AssetError, TypeError):
    """Raised when an asset's media type does not match the expected track or variable type."""
    pass


class InvalidAssetReferenceError(AssetError):
    """Raised when an asset identifier contains path traversal, directory injection, or illegal characters."""
    pass


class CapabilityPreconditionError(ViralMintError):
    """Preconditions for executing a capability are not met."""
    pass


class AuthorizationRequiredError(ViralMintError):
    """Execution blocked because action requires explicit user authorization."""
    pass


class CapabilityExecutionError(ViralMintError):
    """Capability execution failed or unsupported."""
    pass


class VerificationError(ViralMintError):
    """Verification of an execution step output failed."""
    pass


