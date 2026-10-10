# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Project document service with optimistic concurrency, revisioning, and idempotent operations."""
import asyncio
import copy
import json
import logging
import re
from typing import Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.database import AsyncSessionLocal
from backend.models.project import Project, default_empty_document
from backend.models.project_revision import ProjectRevision
from backend.core.exceptions import (
    ProjectError,
    ProjectNotFoundError,
    RevisionConflictError,
    IdempotencyConflictError,
    AssetError,
    AssetNotFoundError,
    AssetAccessError,
    AssetTypeMismatchError,
    InvalidAssetReferenceError,
)

logger = logging.getLogger(__name__)


def normalize_payload(data):
    """Recursively normalize dictionary keys and data types for deterministic comparison and fingerprinting."""
    if isinstance(data, dict):
        return {str(k): normalize_payload(v) for k, v in sorted(data.items())}
    elif isinstance(data, list):
        return [normalize_payload(item) for item in data]
    elif isinstance(data, float):
        return round(data, 6)
    return data


def compute_request_fingerprint(
    operation_type: str,
    payload: dict,
    project_id: str,
    expected_revision: Optional[int] = None,
) -> str:
    """Compute SHA-256 fingerprint for canonical request identity."""
    import hashlib
    norm = {
        "project_id": str(project_id),
        "operation_type": str(operation_type),
        "payload": normalize_payload(payload or {}),
    }
    if expected_revision is not None:
        norm["expected_revision"] = int(expected_revision)
    raw = json.dumps(norm, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProjectService:
    _project_locks: dict[str, asyncio.Lock] = {}

    @classmethod
    def _get_lock(cls, project_id: str) -> asyncio.Lock:
        if project_id not in cls._project_locks:
            cls._project_locks[project_id] = asyncio.Lock()
        return cls._project_locks[project_id]

    @staticmethod
    def migrate_project_document(doc: dict) -> dict:
        """Ensure document conforms to schema_version 2, preserving all existing clips, tracks, and metadata."""
        if not isinstance(doc, dict):
            return doc
        if doc.get("schema_version") is None or doc.get("schema_version") < 2:
            doc["schema_version"] = 2
        timeline = doc.setdefault("timeline", {})
        timeline.setdefault("fps", 30)
        timeline.setdefault("duration_seconds", 0.0)
        tracks = timeline.setdefault("tracks", [])
        for t in tracks:
            for idx, c in enumerate(t.get("clips", [])):
                c.setdefault("visible", True)
                c.setdefault("locked", False)
                c.setdefault("parent_id", None)
                if c.get("layer_order") is None:
                    c["layer_order"] = idx
        doc.setdefault("bench_ranges", {})
        doc.setdefault("assets", [])
        code = doc.setdefault("code", {})
        if not isinstance(code, dict):
            code = {"files": []}
            doc["code"] = code
        code.setdefault("files", [])
        doc.setdefault("metadata", {})
        return doc

    @staticmethod
    def _find_clip_and_track(tracks: list, clip_id: str) -> tuple[Optional[dict], Optional[dict]]:
        """Locate a clip by id across all tracks and return (clip, track)."""
        for t in tracks:
            for c in t.get("clips", []):
                if c.get("id") == clip_id:
                    return c, t
        return None, None

    @classmethod
    def _check_clip_unlocked(cls, clip: dict, op_name: str, tracks: Optional[list] = None) -> None:
        """Raise ProjectError if element or any of its ancestor groups is locked to prevent unauthorized mutation."""
        cid = clip.get("id", "unknown")
        if tracks and clip.get("parent_id"):
            curr_pid = clip.get("parent_id")
            visited = set()
            while curr_pid and curr_pid not in visited:
                visited.add(curr_pid)
                p_clip, _ = cls._find_clip_and_track(tracks, curr_pid)
                if p_clip:
                    if p_clip.get("locked") is True:
                        raise ProjectError(
                            f"Cannot perform '{op_name}' on element '{cid}' because ancestor group '{curr_pid}' is locked. Unlock the group first."
                        )
                    curr_pid = p_clip.get("parent_id")
                else:
                    break
        if clip.get("locked") is True:
            raise ProjectError(f"Cannot perform '{op_name}' on locked element '{cid}'. Unlock it first.")

    @classmethod
    def _check_associated_clip_unlocked(cls, tracks: list, file_entry: dict, op_name: str) -> None:
        """Raise ProjectError if code file is associated with a locked clip or composition."""
        clip_id = file_entry.get("clip_id")
        if not clip_id and file_entry.get("path", "").startswith("compositions/"):
            m = re.match(r"^compositions/([^/]+)\.(html|htm)$", file_entry.get("path", ""))
            if m:
                clip_id = m.group(1)
        if clip_id:
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if c:
                cls._check_clip_unlocked(c, op_name, tracks=tracks)

    @classmethod
    def validate_block_variables(cls, block_id: Optional[str], variables: dict) -> None:
        """Validate block instance variables against registry schema if registered."""
        if not block_id or not variables:
            return
        try:
            from backend.services.registry_adapter import RegistryAdapter
            item = RegistryAdapter.get_catalog_item(block_id)
            if not item:
                return
            schema_vars = {v["id"]: v for v in item.get("variables", [])}
            import re
            color_re = re.compile(
                r"^(#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d.]+\s*\)|hsl\(\s*\d+\s*,\s*[\d.%]+\s*,\s*[\d.%]+\s*\)|hsla\(\s*\d+\s*,\s*[\d.%]+\s*,\s*[\d.%]+\s*,\s*[\d.]+\s*\)|[a-zA-Z]+)$"
            )
            for k, val in variables.items():
                if k not in schema_vars:
                    continue
                vdef = schema_vars[k]
                vtype = vdef.get("type", "string")
                if vtype == "number":
                    try:
                        n = float(val)
                    except (ValueError, TypeError):
                        raise ProjectError(f"Variable '{k}' must be numeric, got {val!r}")
                    if "min" in vdef and n < float(vdef["min"]):
                        raise ProjectError(f"Variable '{k}' ({n}) below minimum {vdef['min']}")
                    if "max" in vdef and n > float(vdef["max"]):
                        raise ProjectError(f"Variable '{k}' ({n}) above maximum {vdef['max']}")
                elif vtype == "boolean":
                    if not isinstance(val, bool) and str(val).lower() not in ("true", "false", "0", "1"):
                        raise ProjectError(f"Variable '{k}' must be boolean, got {val!r}")
                elif vtype == "enum":
                    options = vdef.get("options") or []
                    if options and str(val) not in [str(o) for o in options]:
                        raise ProjectError(f"Variable '{k}' value {val!r} not in options {options}")
                elif vtype == "color":
                    if not isinstance(val, str) or not color_re.match(val.strip()):
                        raise ProjectError(f"Variable '{k}' must be a valid CSS color, got {val!r}")
                elif vtype in ("image", "asset"):
                    if not isinstance(val, str) or not val.strip():
                        raise ProjectError(f"Variable '{k}' must be a valid asset ID or internal block asset reference, got {val!r}")
                    clean_val = val.strip()
                    from backend.services.asset_resolver import validate_asset_identifier_safety
                    try:
                        validate_asset_identifier_safety(clean_val)
                    except Exception as err:
                        raise ProjectError(f"Variable '{k}' invalid asset reference: {err}")
        except ProjectError:
            raise
        except Exception as e:
            logger.warning("Variable validation skipped for %s: %s", block_id, e)

    @classmethod
    def _normalize_file_path(cls, raw_path: str) -> str:
        """Validate and normalize relative logical file paths.

        Strictly prevents directory traversal ('..'), absolute paths ('/'),
        drive letter paths ('C:'), and invalid characters.
        """
        import re
        if not isinstance(raw_path, str):
            raise ProjectError("File path must be a string.")
        p = raw_path.replace("\\", "/").strip()
        if p.startswith("/") or p.startswith("\\"):
            raise ProjectError(f"Absolute paths starting with / are not permitted: {raw_path}")
        if re.match(r"^[a-zA-Z]:", p):
            raise ProjectError(f"Drive letter paths are not permitted: {raw_path}")
        parts = p.split("/")
        if any(seg == "" for seg in parts):
            raise ProjectError(f"Empty path segments or duplicate slashes are not permitted: {raw_path}")
        resolved = []
        for seg in parts:
            if seg == "..":
                raise ProjectError(f"Directory traversal (..) is not permitted: {raw_path}")
            if seg == ".":
                raise ProjectError(f"Dot path segments (.) are not permitted: {raw_path}")
            if not re.match(r"^[a-zA-Z0-9_\-\.\@]+$", seg):
                raise ProjectError(f"Invalid characters in path component '{seg}': {raw_path}")
            resolved.append(seg)
        if not resolved:
            raise ProjectError("Path cannot be empty.")
        return "/".join(resolved)

    @classmethod
    def _validate_file_extension_and_content(cls, path: str, content: str) -> None:
        """Ensure file extension is supported, file size <= 1MB, and JSON content is valid."""
        import json
        allowed_exts = (".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt")
        lowered = path.lower()
        if not any(lowered.endswith(ext) for ext in allowed_exts):
            raise ProjectError(f"File extension for '{path}' is not supported. Allowed: {allowed_exts}")
        if len(content.encode("utf-8")) > 1024 * 1024:
            raise ProjectError(f"File size for '{path}' exceeds 1MB limit ({len(content.encode('utf-8'))} bytes).")
        if lowered.endswith(".json") and content.strip():
            try:
                json.loads(content)
            except Exception as e:
                raise ProjectError(f"Invalid JSON content in '{path}': {e}")

    @classmethod
    async def validate_asset_reference(
        cls,
        asset_id: str,
        user_id: Optional[str] = "local",
        project_id: Optional[str] = None,
        expected_media_type: Optional[str] = None,
        must_exist: bool = True,
        db=None,
    ) -> tuple:
        """Validate asset identifier safety, DB record, disk availability, scope, and media type."""
        from backend.services.asset_resolver import (
            resolve_asset_record_and_path,
            validate_asset_identifier_safety,
        )
        validate_asset_identifier_safety(asset_id)
        return await resolve_asset_record_and_path(
            asset_id=asset_id,
            db=db,
            must_exist=must_exist,
            user_id=user_id,
            project_id=project_id,
            expected_media_type=expected_media_type,
        )

    @classmethod
    async def create_project(
        cls,
        name: str = "Untitled Project",
        aspect_ratio: str = "9:16",
        initial_document: Optional[dict] = None,
        user_id: str = "local",
    ) -> Project:
        """Create a new versioned project and record revision 1."""
        if initial_document:
            migrated = cls.migrate_project_document(dict(initial_document))
            doc_str = json.dumps(migrated)
        else:
            doc_str = default_empty_document(name, aspect_ratio)

        async with AsyncSessionLocal() as db:
            project = Project(
                user_id=user_id,
                name=name,
                aspect_ratio=aspect_ratio,
                revision=1,
                document_json=doc_str,
                is_frozen=False,
            )
            db.add(project)
            await db.flush()

            # Record initial revision
            rev_record = ProjectRevision(
                project_id=project.id,
                revision=1,
                operation_type="init",
                operation_payload_json=json.dumps({"name": name, "aspect_ratio": aspect_ratio}),
                document_snapshot_json=doc_str,
                idempotency_key=None,
                author="user",
            )
            db.add(rev_record)
            await db.commit()
            await db.refresh(project)
            return project

    @staticmethod
    async def get_project(project_id: str) -> Project:
        """Retrieve project by ID or raise ProjectNotFoundError."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Project).where(Project.id == project_id))
            proj = res.scalar_one_or_none()
            if not proj:
                raise ProjectNotFoundError(f"Project '{project_id}' not found.")
            return proj

    @staticmethod
    async def get_revision_snapshot(project_id: str, revision: int) -> dict:
        """Retrieve frozen document snapshot for a specific revision."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(ProjectRevision)
                .where(ProjectRevision.project_id == project_id)
                .where(ProjectRevision.revision == revision)
            )
            rev = res.scalar_one_or_none()
            if not rev:
                raise ProjectError(f"Revision {revision} for project '{project_id}' not found.")
            return json.loads(rev.document_snapshot_json)

    @staticmethod
    async def list_revisions(project_id: str) -> list[dict]:
        """List revision history for a project."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(ProjectRevision)
                .where(ProjectRevision.project_id == project_id)
                .order_by(ProjectRevision.revision.asc())
            )
            revisions = res.scalars().all()
            return [
                {
                    "revision": r.revision,
                    "operation_type": r.operation_type,
                    "author": r.author,
                    "idempotency_key": r.idempotency_key,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in revisions
            ]

    @classmethod
    async def apply_operation(
        cls,
        project_id: str,
        expected_revision: int,
        operation_type: str,
        payload: dict,
        idempotency_key: Optional[str] = None,
        author: str = "user",
    ) -> dict:
        """
        Apply a controlled operation to the versioned project document.
        
        Guarantees:
        1. Idempotency: if idempotency_key was already processed, return current state without re-applying.
        2. Optimistic concurrency: if expected_revision != project.revision, raise RevisionConflictError.
        3. Persisted versioning: bumps revision, updates document_json, saves immutable snapshot to ProjectRevision.
        """
        async with cls._get_lock(project_id):
            async with AsyncSessionLocal() as db:
                # 1. Check idempotency if key is provided
                if idempotency_key:
                    res_idem = await db.execute(
                        select(ProjectRevision)
                        .where(ProjectRevision.project_id == project_id)
                        .where(ProjectRevision.idempotency_key == idempotency_key)
                    )
                    existing_rev = res_idem.scalar_one_or_none()
                    if existing_rev:
                        # Operation type mismatch check
                        if existing_rev.operation_type != operation_type:
                            raise IdempotencyConflictError(
                                f"Idempotency conflict: key '{idempotency_key}' was used for operation '{existing_rev.operation_type}', but current request specifies '{operation_type}'.",
                                existing_revision=existing_rev.revision,
                                expected_revision=expected_revision,
                            )

                        # Payload mismatch check
                        existing_payload = json.loads(existing_rev.operation_payload_json)
                        if normalize_payload(existing_payload) != normalize_payload(payload):
                            raise IdempotencyConflictError(
                                f"Idempotency conflict: key '{idempotency_key}' was used with a different payload for operation '{operation_type}'.",
                                existing_revision=existing_rev.revision,
                                expected_revision=expected_revision,
                            )

                        # Expected revision participation in replay identity:
                        # Original operation transitioned from (existing_rev.revision - 1) to existing_rev.revision.
                        # Legitimate replays may specify either the original base revision or the resulting revision.
                        orig_base_revision = existing_rev.revision - 1
                        if expected_revision is not None and expected_revision not in (orig_base_revision, existing_rev.revision):
                            raise IdempotencyConflictError(
                                f"Idempotency conflict: key '{idempotency_key}' was executed at base revision {orig_base_revision} (result {existing_rev.revision}), but current request expects revision {expected_revision}.",
                                existing_revision=existing_rev.revision,
                                expected_revision=expected_revision,
                            )

                        logger.info(
                            "Legitimate idempotent replay detected for project %s key %s (revision %d)",
                            project_id, idempotency_key, existing_rev.revision
                        )
                        # Return the original operation result snapshot, not an unrelated later mutation
                        return {
                            "project_id": project_id,
                            "revision": existing_rev.revision,
                            "document": json.loads(existing_rev.document_snapshot_json),
                            "applied": False,
                            "idempotent_replay": True,
                            "operation_type": existing_rev.operation_type,
                            "author": existing_rev.author,
                        }

                # 2. Load project
                p_res = await db.execute(select(Project).where(Project.id == project_id))
                project = p_res.scalar_one_or_none()
                if not project:
                    raise ProjectNotFoundError(f"Project '{project_id}' not found.")

                # Concurrency check
                if project.revision != expected_revision:
                    logger.warning(
                        "Revision conflict on project %s: current=%d expected=%d",
                        project_id, project.revision, expected_revision
                    )
                    raise RevisionConflictError(
                        current_revision=project.revision,
                        expected_revision=expected_revision,
                        message=f"Conflict: project has revision {project.revision}, expected {expected_revision}."
                    )

                # Validate asset references if requested or during add_asset
                if operation_type == "add_asset":
                    asset_info = payload.get("asset") or {}
                    asset_id = asset_info.get("id")
                    if not asset_id:
                        raise ProjectError("Missing 'id' in add_asset operation.")
                    from backend.services.asset_resolver import validate_asset_identifier_safety
                    validate_asset_identifier_safety(asset_id)
                    if payload.get("validate", True):
                        await cls.validate_asset_reference(
                            asset_id=asset_id,
                            user_id=project.user_id,
                            project_id=project.id,
                            expected_media_type=payload.get("media_type"),
                            must_exist=payload.get("must_exist", True),
                            db=db,
                        )
                elif payload.get("validate_asset") or payload.get("validate_assets"):
                    clip_data = payload.get("clip") or payload
                    aid = clip_data.get("asset_id") or clip_data.get("video_id")
                    if aid:
                        await cls.validate_asset_reference(
                            asset_id=aid,
                            user_id=project.user_id,
                            project_id=project.id,
                            expected_media_type=payload.get("media_type") or clip_data.get("type"),
                            must_exist=payload.get("must_exist", True),
                            db=db,
                        )

                # 3. Parse and mutate document
                doc = cls.migrate_project_document(json.loads(project.document_json))
                cls._mutate_document(doc, operation_type, payload)
                cls.migrate_project_document(doc)

                # Update timeline duration if tracks exist
                cls._recalculate_timeline_duration(doc)

                # 4. Bump revision with atomic CAS
                new_revision = expected_revision + 1
                doc_str = json.dumps(doc)
                doc_aspect = doc.get("aspect_ratio") or project.aspect_ratio or "9:16"

                cas_stmt = (
                    update(Project)
                    .where(Project.id == project_id, Project.revision == expected_revision)
                    .values(
                        revision=new_revision,
                        document_json=doc_str,
                        aspect_ratio=doc_aspect,
                    )
                )
                cas_res = await db.execute(cas_stmt)
                if cas_res.rowcount == 0:
                    current_rev = (await db.execute(select(Project.revision).where(Project.id == project_id))).scalar_one_or_none()
                    raise RevisionConflictError(
                        current_revision=current_rev if current_rev is not None else -1,
                        expected_revision=expected_revision,
                        message=f"Conflict: project revision was changed concurrently."
                    )

                # 5. Persist revision snapshot with deterministic fingerprint
                req_fingerprint = compute_request_fingerprint(
                    operation_type=operation_type,
                    payload=payload,
                    project_id=project_id,
                    expected_revision=expected_revision,
                )
                rev_entry = ProjectRevision(
                    project_id=project_id,
                    revision=new_revision,
                    operation_type=operation_type,
                    operation_payload_json=json.dumps(payload),
                    document_snapshot_json=doc_str,
                    idempotency_key=idempotency_key,
                    author=author,
                    request_fingerprint=req_fingerprint,
                )
                db.add(rev_entry)

                try:
                    await db.commit()
                except IntegrityError:
                    await db.rollback()
                    # Race-safe recovery: check if duplicate idempotency key was committed concurrently
                    if idempotency_key:
                        res_check = await db.execute(
                            select(ProjectRevision)
                            .where(ProjectRevision.project_id == project_id)
                            .where(ProjectRevision.idempotency_key == idempotency_key)
                        )
                        c_rev = res_check.scalar_one_or_none()
                        if c_rev:
                            if c_rev.operation_type != operation_type or normalize_payload(json.loads(c_rev.operation_payload_json)) != normalize_payload(payload):
                                raise IdempotencyConflictError(
                                    f"Idempotency conflict: key '{idempotency_key}' was committed concurrently with different payload.",
                                    existing_revision=c_rev.revision,
                                    expected_revision=expected_revision,
                                )
                            return {
                                "project_id": project_id,
                                "revision": c_rev.revision,
                                "document": json.loads(c_rev.document_snapshot_json),
                                "applied": False,
                                "idempotent_replay": True,
                                "operation_type": c_rev.operation_type,
                                "author": c_rev.author,
                            }
                    current_rev = (await db.execute(select(Project.revision).where(Project.id == project_id))).scalar_one_or_none()
                    raise RevisionConflictError(
                        current_revision=current_rev if current_rev is not None else -1,
                        expected_revision=expected_revision,
                        message="Conflict: revision unique constraint violated during concurrent commit."
                    )

                return {
                    "project_id": project_id,
                    "revision": new_revision,
                    "document": doc,
                    "applied": True,
                    "operation_type": operation_type,
                    "author": author,
                }

    @classmethod
    def _mutate_document(cls, doc: dict, operation_type: str, payload: dict) -> None:
        """Apply deterministic in-memory transformation on document schema."""
        timeline = doc.setdefault("timeline", {})
        tracks = timeline.setdefault("tracks", [])

        if operation_type in ("add_clip", "insert_track_clip"):
            track_id = payload.get("track_id", "track_video_main")
            clip_data = dict(payload.get("clip") or {})
            if not clip_data:
                clip_data = {k: v for k, v in payload.items() if k != "track_id"}
            if "id" not in clip_data:
                clip_data["id"] = f"clip_{uuid4().hex[:8]}"

            clip_data.setdefault("visible", True)
            clip_data.setdefault("locked", False)
            clip_data.setdefault("parent_id", None)
            if "layer_order" not in clip_data or clip_data["layer_order"] is None:
                max_lo = max((int(c.get("layer_order", 0) or 0) for tr in tracks for c in tr.get("clips", [])), default=-1)
                clip_data["layer_order"] = max_lo + 1

            target_track = next((t for t in tracks if t.get("id") == track_id), None)
            if not target_track:
                target_track = {"id": track_id, "type": "video", "name": "Video", "clips": []}
                tracks.append(target_track)

            target_track.setdefault("clips", []).append(clip_data)

        elif operation_type == "update_clip":
            clip_id = payload.get("clip_id")
            patch = payload.get("patch", {})
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "update_clip", tracks=tracks)
            c.update(patch)

        elif operation_type in ("remove_clip", "delete_clip"):
            clip_id = payload.get("clip_id")
            c, track = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "remove_clip", tracks=tracks)
            if c.get("type") == "group":
                locked_child = next(
                    (ch for tr in tracks for ch in tr.get("clips", []) if ch.get("parent_id") == clip_id and ch.get("locked")),
                    None,
                )
                if locked_child:
                    raise ProjectError(f"Cannot remove group '{clip_id}' because child element '{locked_child['id']}' is locked.")
                parent_of_group = c.get("parent_id")
                for t in tracks:
                    for child in t.get("clips", []):
                        if child.get("parent_id") == clip_id:
                            child["parent_id"] = parent_of_group
            track["clips"] = [item for item in track.get("clips", []) if item.get("id") != clip_id]

        elif operation_type == "set_captions":
            captions_data = payload.get("captions", [])
            cap_track = next((t for t in tracks if t.get("type") == "captions"), None)
            if not cap_track:
                cap_track = {"id": "track_captions", "type": "captions", "name": "Captions", "clips": []}
                tracks.append(cap_track)
            cap_track["clips"] = captions_data

        elif operation_type == "set_aspect_ratio":
            aspect = payload.get("aspect_ratio", "9:16")
            doc["aspect_ratio"] = aspect

        elif operation_type == "patch_document":
            patch = payload.get("patch", {})
            doc.update(patch)

        elif operation_type == "update_document":
            new_doc = payload.get("document")
            if new_doc is None and ("timeline" in payload or "tracks" in payload):
                new_doc = payload
            if not isinstance(new_doc, dict):
                raise ProjectError("Payload must include a valid 'document' dictionary.")
            doc.clear()
            doc.update(new_doc)

        elif operation_type == "set_bench_ranges":
            source_id = str(payload.get("source_id") or "")
            ranges = payload.get("ranges") or []
            bench_ranges = doc.setdefault("bench_ranges", {})
            if source_id:
                bench_ranges[source_id] = ranges

        elif operation_type == "clear_bench_ranges":
            source_id = str(payload.get("source_id") or "")
            bench_ranges = doc.setdefault("bench_ranges", {})
            if source_id in bench_ranges:
                del bench_ranges[source_id]

        elif operation_type == "add_asset":
            asset_info = payload.get("asset") or {}
            assets = doc.setdefault("assets", [])
            asset_id = asset_info.get("id")
            if asset_id:
                existing = next((a for a in assets if a.get("id") == asset_id), None)
                if existing:
                    existing.update(asset_info)
                else:
                    assets.append(asset_info)
        elif operation_type == "add_block":
            block_id = payload.get("block_id")
            if not block_id:
                raise ProjectError("Missing 'block_id' in add_block operation.")
            
            # Resolve or snapshot block to ensure version immutability
            block_version = payload.get("block_version")
            try:
                from backend.services.registry_adapter import RegistryAdapter
                snapshot = RegistryAdapter.freeze_block_snapshot(block_id, expected_version=block_version)
                block_version = snapshot.get("version_hash", block_version or "0000000000000000")
            except Exception as e:
                logger.warning("Could not snapshot block %s: %s", block_id, e)
                block_version = block_version or "0000000000000000"

            track_id = payload.get("track_id")
            instance_id = payload.get("instance_id") or f"elem_{uuid4().hex[:8]}"
            title = payload.get("title") or block_id.replace("-", " ").title()
            start_sec = float(payload.get("start_seconds", 0.0) or 0.0)
            dur_sec = float(payload.get("duration_seconds", 5.0) or 5.0)
            variables = dict(payload.get("variables") or {})

            # Validate variables against catalog schema
            cls.validate_block_variables(block_id, variables)

            if not track_id:
                comp_track = next((t for t in tracks if t.get("type") in ["graphics", "components"]), None)
                if not comp_track:
                    comp_track = {
                        "id": "track_graphics_main",
                        "type": "graphics",
                        "name": "Graphics & Blocks",
                        "clips": []
                    }
                    tracks.append(comp_track)
                target_track = comp_track
            else:
                target_track = next((t for t in tracks if t.get("id") == track_id), None)
                if not target_track:
                    target_track = {"id": track_id, "type": "graphics", "name": "Graphics", "clips": []}
                    tracks.append(target_track)

            max_lo = max((int(c.get("layer_order", 0) or 0) for tr in tracks for c in tr.get("clips", [])), default=-1)
            clip_data = {
                "id": instance_id,
                "type": "block",
                "block_id": block_id,
                "block_version": block_version,
                "title": title,
                "start_seconds": start_sec,
                "duration_seconds": dur_sec,
                "variables": variables,
                "visible": True,
                "locked": False,
                "parent_id": None,
                "layer_order": max_lo + 1,
            }
            target_track.setdefault("clips", []).append(clip_data)

        elif operation_type == "update_block_variables":
            clip_id = payload.get("clip_id")
            variables = payload.get("variables") or {}
            patch = payload.get("patch") or {}
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Block clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "update_block_variables", tracks=tracks)
            cls.validate_block_variables(c.get("block_id"), variables)
            c.setdefault("variables", {}).update(variables)
            if patch:
                c.update(patch)

        elif operation_type in ("update_clip_timing", "resize_clip"):
            clip_id = payload.get("clip_id")
            start_sec = payload.get("start_seconds")
            dur_sec = payload.get("duration_seconds")
            trim_start = payload.get("trim_start")
            trim_end = payload.get("trim_end")
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, operation_type, tracks=tracks)
            if start_sec is not None:
                c["start_seconds"] = max(0.0, float(start_sec))
            if dur_sec is not None:
                c["duration_seconds"] = max(0.1, float(dur_sec))
            if trim_start is not None:
                c["trim_start"] = max(0.0, float(trim_start))
            if trim_end is not None:
                c["trim_end"] = max(0.0, float(trim_end))

        elif operation_type == "move_clip":
            clip_id = payload.get("clip_id")
            new_track_id = payload.get("new_track_id")
            new_start = payload.get("start_seconds")
            found_clip, source_track = cls._find_clip_and_track(tracks, clip_id)
            if not found_clip:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(found_clip, "move_clip", tracks=tracks)

            if new_start is not None:
                found_clip["start_seconds"] = max(0.0, float(new_start))

            if new_track_id and new_track_id != source_track.get("id"):
                dest_track = next((t for t in tracks if t.get("id") == new_track_id), None)
                if not dest_track:
                    dest_track = {"id": new_track_id, "type": source_track.get("type", "video"), "name": new_track_id, "clips": []}
                    tracks.append(dest_track)
                source_track["clips"] = [c for c in source_track.get("clips", []) if c.get("id") != clip_id]
                dest_track.setdefault("clips", []).append(found_clip)

        elif operation_type == "duplicate_clip":
            clip_id = payload.get("clip_id")
            found_clip, target_track = cls._find_clip_and_track(tracks, clip_id)
            if not found_clip:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")

            cloned = copy.deepcopy(found_clip)
            prefix = "elem" if (cloned.get("type") == "block" or cloned.get("block_id")) else "clip"
            cloned["id"] = f"{prefix}_{uuid4().hex[:8]}"
            cloned["locked"] = False
            max_lo = max((int(c.get("layer_order", 0) or 0) for tr in tracks for c in tr.get("clips", [])), default=-1)
            cloned["layer_order"] = max_lo + 1
            offset = float(payload.get("offset_seconds", cloned.get("duration_seconds", 1.0)) or 1.0)
            cloned["start_seconds"] = round(float(cloned.get("start_seconds", 0.0)) + offset, 2)
            target_track.setdefault("clips", []).append(cloned)

        elif operation_type == "split_clip":
            clip_id = payload.get("clip_id")
            split_time = float(payload.get("split_time", 0.0) or 0.0)
            found_clip, target_track = cls._find_clip_and_track(tracks, clip_id)
            if not found_clip:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(found_clip, "split_clip")

            c_start = float(found_clip.get("start_seconds", 0.0) or 0.0)
            c_dur = float(found_clip.get("duration_seconds", 0.0) or 0.0)
            c_end = c_start + c_dur

            if split_time <= c_start + 0.05 or split_time >= c_end - 0.05:
                raise ProjectError(f"Split time {split_time} must be strictly inside clip bounds ({c_start} to {c_end}).")

            part2 = copy.deepcopy(found_clip)
            prefix = "elem" if (part2.get("type") == "block" or part2.get("block_id")) else "clip"
            part2["id"] = f"{prefix}_{uuid4().hex[:8]}"
            part2["locked"] = False

            orig_trim_start = float(found_clip.get("trim_start", 0.0) or 0.0)
            orig_trim_end = float(found_clip.get("trim_end", orig_trim_start + c_dur) or (orig_trim_start + c_dur))

            # Part 1 keeps start to split_time
            dur1 = round(split_time - c_start, 2)
            found_clip["duration_seconds"] = dur1
            found_clip["trim_end"] = round(orig_trim_start + dur1, 2)

            # Part 2 starts at split_time
            dur2 = round(c_end - split_time, 2)
            part2["start_seconds"] = round(split_time, 2)
            part2["duration_seconds"] = dur2
            part2["trim_start"] = round(orig_trim_start + dur1, 2)
            part2["trim_end"] = orig_trim_end

            target_track.setdefault("clips", []).append(part2)

        elif operation_type == "add_keyframe":
            clip_id = payload.get("clip_id")
            kf = payload.get("keyframe") or {}
            if not kf.get("property"):
                raise ProjectError("Missing 'property' in keyframe.")
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "add_keyframe", tracks=tracks)
            anims = c.setdefault("animations", [])
            existing = next((a for a in anims if a.get("property") == kf.get("property") and abs(float(a.get("time", 0.0)) - float(kf.get("time", 0.0))) < 0.001), None)
            if existing:
                existing.update(kf)
            else:
                anims.append(kf)
            anims.sort(key=lambda x: float(x.get("time", 0.0) or 0.0))

        elif operation_type == "update_keyframe":
            clip_id = payload.get("clip_id")
            prop = payload.get("property")
            kf_time = float(payload.get("time", 0.0) or 0.0)
            patch = payload.get("patch") or {}
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "update_keyframe", tracks=tracks)
            anims = c.get("animations", [])
            found = False
            for a in anims:
                if a.get("property") == prop and abs(float(a.get("time", 0.0)) - kf_time) < 0.01:
                    a.update(patch)
                    found = True
                    break
            if not found:
                raise ProjectError(f"Keyframe at time {kf_time} for property '{prop}' not found on clip '{clip_id}'.")
            anims.sort(key=lambda x: float(x.get("time", 0.0) or 0.0))

        elif operation_type == "remove_keyframe":
            clip_id = payload.get("clip_id")
            prop = payload.get("property")
            kf_time = float(payload.get("time", 0.0) or 0.0)
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Clip '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "remove_keyframe", tracks=tracks)
            anims = c.get("animations", [])
            c["animations"] = [a for a in anims if not (a.get("property") == prop and abs(float(a.get("time", 0.0)) - kf_time) < 0.01)]

        elif operation_type == "set_element_visibility":
            clip_id = payload.get("clip_id")
            visible = bool(payload.get("visible", True))
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Element '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "set_element_visibility", tracks=tracks)
            if c.get("type") == "group":
                locked_child = next(
                    (ch for tr in tracks for ch in tr.get("clips", []) if ch.get("parent_id") == clip_id and ch.get("locked")),
                    None,
                )
                if locked_child:
                    raise ProjectError(f"Cannot toggle visibility for group '{clip_id}' because child element '{locked_child['id']}' is locked.")
            c["visible"] = visible
            if c.get("type") == "group":
                for t in tracks:
                    for child in t.get("clips", []):
                        if child.get("parent_id") == clip_id:
                            child["visible"] = visible

        elif operation_type == "set_element_lock":
            clip_id = payload.get("clip_id")
            locked = bool(payload.get("locked", False))
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Element '{clip_id}' not found in project document.")
            if not locked and c.get("parent_id"):
                p_clip, _ = cls._find_clip_and_track(tracks, c.get("parent_id"))
                if p_clip and p_clip.get("locked"):
                    raise ProjectError(f"Cannot unlock element '{clip_id}' while parent group '{p_clip['id']}' is locked.")
            c["locked"] = locked
            if c.get("type") == "group":
                for t in tracks:
                    for child in t.get("clips", []):
                        if child.get("parent_id") == clip_id:
                            child["locked"] = locked

        elif operation_type in ("rename_element", "rename_clip"):
            clip_id = payload.get("clip_id")
            name = str(payload.get("name") or payload.get("title") or "").strip()
            if not name:
                raise ProjectError("Element name cannot be empty.")
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Element '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "rename_element", tracks=tracks)
            c["name"] = name
            c["title"] = name

        elif operation_type == "reorder_layer":
            clip_id = payload.get("clip_id")
            layer_order = int(payload.get("layer_order", 0))
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Element '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "reorder_layer", tracks=tracks)
            delta = layer_order - int(c.get("layer_order", 0) or 0)
            c["layer_order"] = layer_order
            if c.get("type") == "group" and delta != 0:
                for t in tracks:
                    for child in t.get("clips", []):
                        if child.get("parent_id") == clip_id:
                            child["layer_order"] = int(child.get("layer_order", 0) or 0) + delta
            if "parent_id" in payload:
                pid = payload.get("parent_id")
                if pid:
                    if pid == clip_id:
                        raise ProjectError(f"Cannot set element '{clip_id}' as its own parent.")
                    parent_c, _ = cls._find_clip_and_track(tracks, pid)
                    if not parent_c:
                        raise ProjectError(f"Parent group '{pid}' not found.")
                    cls._check_clip_unlocked(parent_c, "reorder_layer", tracks=tracks)
                c["parent_id"] = pid

        elif operation_type == "set_parent":
            clip_id = payload.get("clip_id")
            parent_id = payload.get("parent_id")
            c, _ = cls._find_clip_and_track(tracks, clip_id)
            if not c:
                raise ProjectError(f"Element '{clip_id}' not found in project document.")
            cls._check_clip_unlocked(c, "set_parent", tracks=tracks)
            if parent_id == clip_id:
                raise ProjectError(f"Cannot set element '{clip_id}' as its own parent.")
            if c.get("parent_id"):
                old_p, _ = cls._find_clip_and_track(tracks, c.get("parent_id"))
                if old_p:
                    cls._check_clip_unlocked(old_p, "set_parent", tracks=tracks)
            if parent_id:
                p_clip, _ = cls._find_clip_and_track(tracks, parent_id)
                if not p_clip:
                    raise ProjectError(f"Target parent group '{parent_id}' not found.")
                cls._check_clip_unlocked(p_clip, "set_parent", tracks=tracks)
                curr = p_clip.get("parent_id")
                visited = {parent_id}
                while curr and curr not in visited:
                    if curr == clip_id:
                        raise ProjectError(f"Cycle detected: element '{clip_id}' is an ancestor of '{parent_id}'.")
                    visited.add(curr)
                    anc, _ = cls._find_clip_and_track(tracks, curr)
                    curr = anc.get("parent_id") if anc else None
            c["parent_id"] = parent_id

        elif operation_type == "group_elements":
            clip_ids = list(payload.get("clip_ids") or [])
            group_name = str(payload.get("group_name") or "New Group").strip() or "New Group"
            group_id = payload.get("group_id") or f"group_{uuid4().hex[:8]}"
            if not clip_ids:
                raise ProjectError("No elements specified to group.")

            target_clips = []
            target_track = None
            for cid in clip_ids:
                c, t = cls._find_clip_and_track(tracks, cid)
                if not c:
                    raise ProjectError(f"Element '{cid}' not found for grouping.")
                cls._check_clip_unlocked(c, "group_elements", tracks=tracks)
                target_clips.append(c)
                if not target_track:
                    target_track = t

            if not target_track:
                target_track = tracks[0] if tracks else None
                if not target_track:
                    target_track = {"id": "track_video_main", "type": "video", "name": "Video", "clips": []}
                    tracks.append(target_track)

            min_start = min((float(c.get("start_seconds", 0.0) or 0.0) for c in target_clips), default=0.0)
            max_end = max(((float(c.get("start_seconds", 0.0) or 0.0) + float(c.get("duration_seconds", 5.0) or 5.0)) for c in target_clips), default=5.0)
            max_order = max((int(c.get("layer_order", 0) or 0) for c in target_clips), default=0)

            group_clip = {
                "id": group_id,
                "type": "group",
                "name": group_name,
                "title": group_name,
                "visible": True,
                "locked": False,
                "parent_id": None,
                "layer_order": max_order + 1,
                "start_seconds": min_start,
                "duration_seconds": max(0.1, round(max_end - min_start, 2)),
            }
            for c in target_clips:
                c["parent_id"] = group_id

            target_track.setdefault("clips", []).append(group_clip)

        elif operation_type == "ungroup_elements":
            group_id = payload.get("group_id")
            group_clip, group_track = cls._find_clip_and_track(tracks, group_id)
            if not group_clip:
                raise ProjectError(f"Group '{group_id}' not found.")
            cls._check_clip_unlocked(group_clip, "ungroup_elements", tracks=tracks)
            locked_child = next(
                (ch for tr in tracks for ch in tr.get("clips", []) if ch.get("parent_id") == group_id and ch.get("locked")),
                None,
            )
            if locked_child:
                raise ProjectError(f"Cannot ungroup '{group_id}' because child element '{locked_child['id']}' is locked.")
            parent_of_group = group_clip.get("parent_id")
            for t in tracks:
                for c in t.get("clips", []):
                    if c.get("parent_id") == group_id:
                        c["parent_id"] = parent_of_group
            group_track["clips"] = [c for c in group_track.get("clips", []) if c.get("id") != group_id]

        elif operation_type == "update_track_state":
            track_id = payload.get("track_id")
            patch = payload.get("patch") or {}
            target_track = next((t for t in tracks if t.get("id") == track_id), None)
            if not target_track:
                raise ProjectError(f"Track '{track_id}' not found in project document.")
            for key in ("muted", "locked", "visible", "collapsed", "name"):
                if key in patch:
                    target_track[key] = patch[key]

        elif operation_type == "create_file":
            raw_path = payload.get("path") or payload.get("name")
            if not raw_path:
                raise ProjectError("Missing 'path' in create_file operation.")
            norm_path = cls._normalize_file_path(raw_path)
            content = payload.get("content", "")
            cls._validate_file_extension_and_content(norm_path, content)
            file_id = payload.get("id") or f"file_{uuid4().hex[:8]}"

            # Lock enforcement on associated clip
            clip_id = payload.get("clip_id")
            if not clip_id and norm_path.startswith("compositions/"):
                m = re.match(r"^compositions/([^/]+)\.(html|htm)$", norm_path)
                if m:
                    clip_id = m.group(1)
            if clip_id:
                c, _ = cls._find_clip_and_track(tracks, clip_id)
                if c:
                    cls._check_clip_unlocked(c, "create_file", tracks=tracks)

            code = doc.setdefault("code", {})
            files = code.setdefault("files", [])
            # Check for path collision
            if any(f.get("path") == norm_path for f in files):
                raise ProjectError(f"File path '{norm_path}' already exists in project.")
            if any(f.get("id") == file_id for f in files):
                raise ProjectError(f"File ID '{file_id}' already exists in project.")

            file_entry = {
                "id": file_id,
                "path": norm_path,
                "content": content,
                "clip_id": clip_id,
                "read_only": bool(payload.get("read_only", False)),
            }
            files.append(file_entry)

        elif operation_type == "update_file":
            file_id = payload.get("id")
            file_path = payload.get("path")
            if not file_id and not file_path:
                raise ProjectError("update_file requires 'id' or 'path'.")
            content = payload.get("content")
            if content is None:
                raise ProjectError("Missing 'content' in update_file operation.")

            code = doc.setdefault("code", {})
            files = code.setdefault("files", [])
            target = next((f for f in files if (file_id and f.get("id") == file_id) or (file_path and f.get("path") == file_path)), None)
            if not target:
                raise ProjectError(f"File '{file_id or file_path}' not found in project.")
            if target.get("read_only"):
                raise ProjectError(f"Cannot update read-only file '{target.get('path')}'.")

            cls._check_associated_clip_unlocked(tracks, target, "update_file")
            cls._validate_file_extension_and_content(target.get("path", ""), content)
            target["content"] = content

        elif operation_type in ("rename_file", "move_file"):
            file_id = payload.get("id")
            old_path = payload.get("old_path") or payload.get("path")
            new_path_raw = payload.get("new_path") or payload.get("new_name")
            if not new_path_raw:
                raise ProjectError("Missing 'new_path' in file rename/move operation.")

            code = doc.setdefault("code", {})
            files = code.setdefault("files", [])
            target = next((f for f in files if (file_id and f.get("id") == file_id) or (old_path and f.get("path") == old_path)), None)
            if not target:
                raise ProjectError(f"File '{file_id or old_path}' not found in project.")
            if target.get("read_only"):
                raise ProjectError(f"Cannot rename/move read-only file '{target.get('path')}'.")

            cls._check_associated_clip_unlocked(tracks, target, operation_type)

            if "/" not in new_path_raw and target and "/" in target.get("path", "") and operation_type == "rename_file":
                parent_dir = target["path"].rsplit("/", 1)[0]
                new_path_raw = f"{parent_dir}/{new_path_raw}"

            new_path = cls._normalize_file_path(new_path_raw)

            # Check collision with other files
            collision = next((f for f in files if f.get("path") == new_path and f.get("id") != target.get("id")), None)
            if collision:
                raise ProjectError(f"Cannot rename/move to '{new_path}': path already exists.")

            cls._validate_file_extension_and_content(new_path, target.get("content", ""))
            target["path"] = new_path

        elif operation_type == "delete_file":
            file_id = payload.get("id")
            file_path = payload.get("path")
            if not file_id and not file_path:
                raise ProjectError("delete_file requires 'id' or 'path'.")

            code = doc.setdefault("code", {})
            files = code.setdefault("files", [])
            target = next((f for f in files if (file_id and f.get("id") == file_id) or (file_path and f.get("path") == file_path)), None)
            if not target:
                raise ProjectError(f"File '{file_id or file_path}' not found in project.")
            if target.get("read_only"):
                raise ProjectError(f"Cannot delete read-only file '{target.get('path')}'.")

            cls._check_associated_clip_unlocked(tracks, target, "delete_file")

            # Safe deletion: verify if file is referenced by active clips/composition elements
            tid = target.get("id")
            tpath = target.get("path")
            target_clip_id = target.get("clip_id")
            active_clip_ref = next(
                (c for tr in tracks for c in tr.get("clips", [])
                 if c.get("file") == tpath
                 or c.get("code_file_id") == tid
                 or (target_clip_id and c.get("id") == target_clip_id)
                 or tpath == f"compositions/{c.get('id')}.html"
                 or tpath == f"blocks/{c.get('id')}.html"),
                None
            )
            if active_clip_ref and not payload.get("force", False):
                raise ProjectError(
                    f"Cannot delete file '{tpath}': referenced by active clip '{active_clip_ref.get('id')}'. Set force=True to delete."
                )

            code["files"] = [f for f in files if f.get("id") != target.get("id")]

        elif operation_type == "update_code_files":
            new_files = payload.get("files")
            if not isinstance(new_files, list):
                raise ProjectError("update_code_files requires 'files' list.")
            code = doc.setdefault("code", {})
            existing_files = {f.get("id"): f for f in code.get("files", [])}

            # Pre-audit existing files for read-only and lock protections
            new_file_map = {f.get("id"): f for f in new_files if isinstance(f, dict) and f.get("id")}
            for eid, ef in existing_files.items():
                if ef.get("read_only"):
                    matching_new = new_file_map.get(eid)
                    if not matching_new or matching_new.get("content") != ef.get("content") or matching_new.get("path") != ef.get("path"):
                        raise ProjectError(f"Cannot modify or remove read-only file '{ef.get('path')}'.")
                # Check locked element protection on modified or removed files
                matching_new = new_file_map.get(eid)
                if not matching_new or matching_new.get("content") != ef.get("content") or matching_new.get("path") != ef.get("path"):
                    cls._check_associated_clip_unlocked(tracks, ef, "update_code_files")

            # Check active clip references for deleted files
            if not payload.get("force", False):
                for eid, ef in existing_files.items():
                    if eid not in new_file_map:
                        tpath = ef.get("path")
                        active_clip_ref = next(
                            (c for tr in tracks for c in tr.get("clips", []) if c.get("file") == tpath or c.get("code_file_id") == eid),
                            None
                        )
                        if active_clip_ref:
                            raise ProjectError(
                                f"Cannot delete file '{tpath}': referenced by active clip '{active_clip_ref.get('id')}'. Set force=True to delete."
                            )

            normalized_list = []
            seen_paths = set()
            seen_ids = set()
            for f in new_files:
                if not isinstance(f, dict):
                    continue
                fid = f.get("id") or f"file_{uuid4().hex[:8]}"
                fpath = cls._normalize_file_path(f.get("path", ""))
                fcontent = str(f.get("content", ""))
                cls._validate_file_extension_and_content(fpath, fcontent)
                if fpath in seen_paths:
                    raise ProjectError(f"Duplicate file path '{fpath}' in code files list.")
                if fid in seen_ids:
                    raise ProjectError(f"Duplicate file ID '{fid}' in code files list.")
                seen_paths.add(fpath)
                seen_ids.add(fid)
                normalized_list.append({
                    "id": fid,
                    "path": fpath,
                    "content": fcontent,
                    "clip_id": f.get("clip_id"),
                    "read_only": bool(f.get("read_only", False)),
                })
            code["files"] = normalized_list

        else:
            raise ProjectError(f"Unsupported operation type: {operation_type}")

    @staticmethod
    def _recalculate_timeline_duration(doc: dict) -> None:
        """Calculate max duration across all clips in timeline."""
        timeline = doc.get("timeline", {})
        tracks = timeline.get("tracks", [])
        max_end = 0.0
        for t in tracks:
            for c in t.get("clips", []):
                start = float(c.get("start_seconds", 0.0) or 0.0)
                dur = float(c.get("duration_seconds", 0.0) or 0.0)
                if start + dur > max_end:
                    max_end = start + dur
        timeline["duration_seconds"] = round(max_end, 2)

    @classmethod
    async def freeze_for_render(cls, project_id: str, revision: Optional[int] = None) -> tuple[int, dict]:
        """Freeze project snapshot for an immutable render job."""
        async with AsyncSessionLocal() as db:
            p_res = await db.execute(select(Project).where(Project.id == project_id))
            project = p_res.scalar_one_or_none()
            if not project:
                raise ProjectNotFoundError(f"Project '{project_id}' not found.")

            target_rev = revision if revision is not None else project.revision
            snapshot = await cls.get_revision_snapshot(project_id, target_rev)
            return target_rev, snapshot
