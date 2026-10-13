# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Catalog Project Intent Contract:
Defines the validated integration interface for adding HyperFrames catalog blocks
into video composition timelines without directly mutating the global ProjectService.
Provides scoped instance IDs, CAS expected revision checks, input sanitization,
and license provenance metadata.
"""
from __future__ import annotations

import html
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.catalog.manifest_service import CatalogManifestService, CatalogManifestError

logger = logging.getLogger(__name__)

# Dangerous patterns to disallow in user variable inputs
DANGEROUS_INPUT_PATTERNS = [
    r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
    r"javascript:",
    r"data:text/html",
    r"on\w+\s*=",  # onload=, onerror=, etc.
    r"__proto__",
    r"prototype",
    r"constructor",
    r"\.\./",
    r"\.\.\\",
]


class BlockVariableInput(BaseModel):
    name: str
    value: Any


class AddToProjectIntentRequest(BaseModel):
    """Client request initiating intent to add a catalog block to a composition."""
    project_id: Optional[str] = Field(None, description="Target composition ID if active, or None for draft insertion")
    timeline_track_index: int = Field(0, ge=0, description="Target timeline track index")
    start_time_seconds: float = Field(0.0, ge=0.0, description="Insertion timestamp on timeline in seconds")
    aspect_ratio: str = Field("9:16", description="Target aspect ratio: '9:16' or '16:9'")
    custom_variables: Dict[str, Any] = Field(default_factory=dict, description="User-configured block parameters")
    instance_id: Optional[str] = Field(None, description="Optional client-specified instance ID or None to generate")
    expected_revision: Optional[int] = Field(None, ge=0, description="Optimistic CAS concurrency revision for the project")
    keyframes: List[Dict[str, Any]] = Field(default_factory=list, description="Property keyframes over time (GT-09)")
    owning_user_id: Optional[str] = Field("user_default", description="Owning user ID for multi-tenant isolation")
    project_owned_source: Optional[str] = Field(None, description="Custom CodeMirror source code override for instance (GT-09)")


class ValidatedTimelineItem(BaseModel):
    """Standardized timeline item structure ready for ProjectService insertion."""
    item_id: str
    instance_id: str
    item_type: str = "motion_block"
    block_id: str
    title: str
    start_time: float
    duration: float
    end_time: float
    track_index: int
    aspect_ratio: str
    aspect_support: str
    preview_url: str
    poster_url: str
    variables: Dict[str, Any]
    internalized: bool
    runtime_ready: bool
    license_provenance: Dict[str, Any] = Field(default_factory=dict)
    is_independently_editable: bool = True
    keyframes: List[Dict[str, Any]] = Field(default_factory=list)
    owning_user_id: str = "user_default"
    instance_source_code: Optional[str] = None
    has_custom_source: bool = False
    export_manifest: Optional[Dict[str, Any]] = None


class AddToProjectIntentResult(BaseModel):
    """Validated intent contract returned to client and coordinator."""
    intent_id: str
    status: str  # "VALIDATED_INTENT", "WARNING_UNVERIFIED"
    block_id: str
    target_project_id: Optional[str]
    timeline_item: ValidatedTimelineItem
    integration_request: Dict[str, Any]


class CatalogProjectIntentAdapter:
    """Validates block readiness and constructs the normalized timeline item payload."""

    @classmethod
    def sanitize_variable_value(cls, key: str, val: Any) -> Any:
        """Sanitizes user-provided variable overrides to prevent injection attacks."""
        # Reject prototype pollution keys
        if key.lower() in ("__proto__", "prototype", "constructor"):
            raise CatalogManifestError(f"Disallowed parameter key: '{key}'")

        if isinstance(val, str):
            # Check length limit
            if len(val) > 2000:
                val = val[:2000]

            # Check dangerous injection patterns
            for pat in DANGEROUS_INPUT_PATTERNS:
                if re.search(pat, val, re.IGNORECASE):
                    # Sanitize by escaping and stripping script fragments
                    val = re.sub(pat, "", val, flags=re.IGNORECASE)

            # Strip control characters except newline and tab
            val = "".join(ch for ch in val if ch in ("\n", "\t") or ord(ch) >= 32)
            return val.strip()

        # Numeric and boolean types pass through
        if isinstance(val, (int, float, bool)):
            return val

        if isinstance(val, list):
            return [cls.sanitize_variable_value(key, v) for v in val[:50]]

        if isinstance(val, dict):
            return {cls.sanitize_variable_value(k, k): cls.sanitize_variable_value(k, v) for k, v in list(val.items())[:50]}

        return str(val)

    @classmethod
    def sanitize_custom_source(cls, source_code: Optional[str]) -> Optional[str]:
        """
        Sanitizes client-edited CodeMirror source code (GT-09).
        Allows local HTML/CSS/SVG canvas logic while rejecting remote scripts,
        eval, token exfiltration, and path traversal attempts.
        """
        if not source_code:
            return None

        # Check path traversal
        if any(bad in source_code for bad in ("../", "..\\", "%2e%2e")):
            raise CatalogManifestError("Path traversal pattern disallowed in custom source code.")

        # Reject remote scripts and unpinned CDNs
        for pat in [r"https?://", r"cdn\.", r"unpkg\.com", r"jsdelivr\.net"]:
            if re.search(pat, source_code, re.IGNORECASE):
                raise CatalogManifestError("Remote scripts and CDNs disallowed in project-owned source code.")

        # Reject exfiltration and arbitrary execution hooks
        for pat in [r"\btoken\b", r"\bexfiltrate\b", r"eval\(", r"child_process", r"subprocess"]:
            if re.search(pat, source_code, re.IGNORECASE):
                raise CatalogManifestError("Unsafe execution or token pattern disallowed in custom source code.")

        # Length safety cap (500 KB)
        if len(source_code) > 500_000:
            raise CatalogManifestError("Custom source code exceeds maximum allowed size (500KB).")

        return source_code

    @classmethod
    def sanitize_keyframes(cls, keyframes: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Validates timeline property keyframes for numeric/safe attributes."""
        if not keyframes:
            return []
        cleaned = []
        for kf in keyframes[:100]:
            if not isinstance(kf, dict):
                continue
            time_val = float(kf.get("time_seconds", kf.get("time", 0.0)))
            if time_val < 0:
                time_val = 0.0
            properties = kf.get("properties", {})
            safe_props = {}
            if isinstance(properties, dict):
                for pk, pv in properties.items():
                    if isinstance(pk, str) and re.match(r"^[a-zA-Z0-9_\-]+$", pk):
                        safe_props[pk] = pv
            cleaned.append({
                "time_seconds": round(time_val, 4),
                "properties": safe_props,
                "easing": str(kf.get("easing", "linear"))[:50],
            })
        return cleaned

    @classmethod
    def create_add_to_project_intent(
        cls,
        block_id: str,
        request: AddToProjectIntentRequest,
    ) -> AddToProjectIntentResult:
        CatalogManifestService.validate_block_id(block_id)
        item = CatalogManifestService.get_item(block_id)
        if not item:
            raise CatalogManifestError(f"Block '{block_id}' not found in catalog.")

        # Determine aspect support
        aspect_norm = "9:16" if request.aspect_ratio in ("9:16", "9x16", "vertical") else "16:9"
        aspect_key = "aspect_9_16" if aspect_norm == "9:16" else "aspect_16_9"
        aspect_support = item.get(aspect_key, "CONTAINED_ONLY")

        # Determine readiness using Wave 4 internalized set
        from backend.catalog.manifest_service import WAVE4_INTERNALIZED_BLOCKS, CORE_INTERNALIZED_BLOCKS
        is_internalized = (
            item.get("internalized", False)
            or block_id in WAVE4_INTERNALIZED_BLOCKS
            or block_id in CORE_INTERNALIZED_BLOCKS
        )
        duration = float(item.get("duration", 5.0))
        end_time = round(request.start_time_seconds + duration, 3)

        # Merge and sanitize custom variables with defaults
        resolved_vars: Dict[str, Any] = {}
        for var_def in item.get("variables", []):
            v_name = var_def.get("name")
            if v_name:
                raw_val = request.custom_variables.get(v_name, var_def.get("default", ""))
                resolved_vars[v_name] = cls.sanitize_variable_value(v_name, raw_val)

        # Allow extra sanitized variables that may not be in schema
        for k, v in request.custom_variables.items():
            if k not in resolved_vars:
                resolved_vars[k] = cls.sanitize_variable_value(k, v)

        # Sanitize custom source code (GT-09) and keyframes
        sanitized_custom_source = cls.sanitize_custom_source(request.project_owned_source)
        sanitized_keyframes = cls.sanitize_keyframes(request.keyframes)

        # Generate unique scoped instance_id and stable item_id
        intent_id = f"intent_{uuid.uuid4().hex[:12]}"
        unique_suffix = uuid.uuid4().hex[:8]
        instance_id = request.instance_id or f"inst_{block_id}_{unique_suffix}"
        item_id = f"block_{block_id}_{unique_suffix}"

        status = "VALIDATED_INTENT" if is_internalized else "WARNING_UNVERIFIED"

        license_provenance = {
            "license": item.get("license", "Apache-2.0"),
            "author": item.get("author", "HyperFrames"),
            "license_status": "VERIFIED_DISTRIBUTABLE" if is_internalized else "UNVERIFIED_OR_CDN_BLOCKED",
            "offline_capable": is_internalized,
            "zero_external_cdn": is_internalized,
        }

        # Generate export-consumable manifest for Role 2 FFmpeg consumption
        from backend.catalog.export_contract import CatalogExportContract
        export_manifest = CatalogExportContract.generate_export_manifest(
            block_id=block_id,
            aspect_ratio=aspect_norm,
            instance_id=instance_id,
            custom_variables=resolved_vars,
            keyframes=sanitized_keyframes,
            custom_source_code=sanitized_custom_source,
        )

        timeline_item = ValidatedTimelineItem(
            item_id=item_id,
            instance_id=instance_id,
            item_type="motion_block",
            block_id=block_id,
            title=item.get("title", block_id),
            start_time=request.start_time_seconds,
            duration=duration,
            end_time=end_time,
            track_index=request.timeline_track_index,
            aspect_ratio=aspect_norm,
            aspect_support=aspect_support,
            preview_url=f"/api/catalog/blocks/{block_id}/preview?aspect_ratio={aspect_norm}",
            poster_url=f"/api/catalog/blocks/{block_id}/poster?aspect_ratio={aspect_norm}",
            variables=resolved_vars,
            internalized=is_internalized,
            runtime_ready=is_internalized,
            license_provenance=license_provenance,
            is_independently_editable=True,
            keyframes=sanitized_keyframes,
            owning_user_id=request.owning_user_id or "user_default",
            instance_source_code=sanitized_custom_source,
            has_custom_source=sanitized_custom_source is not None,
            export_manifest=export_manifest,
        )

        integration_request = {
            "target_service": "backend.services.project_service.ProjectService",
            "suggested_method": "add_timeline_clip_or_block",
            "parameters": {
                "project_id": request.project_id,
                "timeline_item": timeline_item.model_dump(),
            },
            "cas_precondition": {
                "expected_revision": request.expected_revision,
                "optimistic_concurrency_required": request.expected_revision is not None,
            },
            "export_manifest": export_manifest,
            "coordinator_action_required": True,
        }

        return AddToProjectIntentResult(
            intent_id=intent_id,
            status=status,
            block_id=block_id,
            target_project_id=request.project_id,
            timeline_item=timeline_item,
            integration_request=integration_request,
        )
