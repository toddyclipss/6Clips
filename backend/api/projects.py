# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Projects REST API: versioned documents, controlled operations, and render execution."""
import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, AsyncSessionLocal
from backend.models.project import Project
from backend.services.project_service import ProjectService
from backend.core.exceptions import RevisionConflictError, IdempotencyConflictError, ProjectNotFoundError, ProjectError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
async def create_project(body: dict = None, db: AsyncSession = Depends(get_db)):
    """Create a new versioned project."""
    body = body or {}
    name = body.get("name", "Untitled Project").strip() or "Untitled Project"
    aspect = body.get("aspect_ratio", "9:16")
    user_id = body.get("user_id", "local")
    initial_doc = body.get("initial_document")

    p = await ProjectService.create_project(
        name=name,
        aspect_ratio=aspect,
        initial_document=initial_doc,
        user_id=user_id,
    )
    return {
        "id": p.id,
        "name": p.name,
        "aspect_ratio": p.aspect_ratio,
        "revision": p.revision,
        "document": json.loads(p.document_json),
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("")
async def list_projects(user_id: str = "local", db: AsyncSession = Depends(get_db)):
    """List all projects for user."""
    res = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.updated_at.desc())
    )
    projects = res.scalars().all()
    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "aspect_ratio": p.aspect_ratio,
                "revision": p.revision,
                "is_frozen": p.is_frozen,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projects
        ]
    }


@router.get("/catalog/items")
async def list_catalog_blocks():
    """List all available HyperFrames registry blocks."""
    from backend.services.registry_adapter import RegistryAdapter
    return RegistryAdapter.list_catalog_items()


@router.get("/catalog/items/{block_id}")
async def get_catalog_block(block_id: str):
    """Get metadata and variables for a specific HyperFrames block."""
    from backend.services.registry_adapter import RegistryAdapter
    item = RegistryAdapter.get_catalog_item(block_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Catalog block '{block_id}' not found.")
    return item


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project document and revision."""
    try:
        p = await ProjectService.get_project(project_id)
        return {
            "id": p.id,
            "name": p.name,
            "aspect_ratio": p.aspect_ratio,
            "revision": p.revision,
            "document": json.loads(p.document_json),
            "is_frozen": p.is_frozen,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/revisions")
async def get_project_revisions(project_id: str):
    """Get revision history for a project."""
    try:
        revisions = await ProjectService.list_revisions(project_id)
        return {"project_id": project_id, "revisions": revisions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/operations")
async def apply_project_operation(
    project_id: str,
    body: dict,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Apply a controlled operation to the versioned project.
    Requires expected_revision for optimistic concurrency control.
    """
    expected_revision = body.get("expected_revision")
    operation_type = body.get("operation_type")
    payload = body.get("payload", {})
    idempotency_key = body.get("idempotency_key") or idempotency_key_header
    author = body.get("author", "user")

    if expected_revision is None or not operation_type:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: 'expected_revision' and 'operation_type'."
        )

    try:
        res = await ProjectService.apply_operation(
            project_id=project_id,
            expected_revision=int(expected_revision),
            operation_type=operation_type,
            payload=payload,
            idempotency_key=idempotency_key,
            author=author,
        )
        try:
            from backend.core.ws_manager import ws_manager
            await ws_manager.send({
                "type": "project_updated",
                "project_id": project_id,
                "revision": res["revision"],
                "document": res["document"],
                "author": author,
            }, "local")
        except Exception:
            pass
        return res
    except RevisionConflictError as err:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "revision_conflict",
                "message": str(err),
                "current_revision": err.current_revision,
                "expected_revision": err.expected_revision,
            }
        )
    except IdempotencyConflictError as err:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "idempotency_conflict",
                "message": str(err),
                "existing_revision": err.existing_revision,
                "expected_revision": err.expected_revision,
            }
        )
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except ProjectError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/{project_id}/sync-studio")
async def sync_project_to_studio(project_id: str, body: dict = None):
    """Sync the versioned project document to the preview studio index.html."""
    body = body or {}
    revision = body.get("revision")
    try:
        from backend.services.hyperframes_adapter import HyperFramesAdapter
        res = await HyperFramesAdapter.sync_project_to_studio(project_id, revision)
        return res
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error("Failed syncing project %s to studio: %s", project_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/preview")
async def get_project_preview(project_id: str, revision: Optional[int] = None):
    """Serve the read-only composition preview HTML generated from the project document."""
    from backend.services.hyperframes_adapter import HyperFramesAdapter
    from backend.services.studio_service import StudioService
    from fastapi.responses import HTMLResponse
    from pathlib import Path
    try:
        res = await HyperFramesAdapter.sync_project_to_studio(project_id, revision)
        html_path = Path(res["html_path"])
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Preview index not found")
        content = html_path.read_text(encoding="utf-8")
        # Route asset and composition requests to our preview endpoints
        content = content.replace('src="./assets/', f'src="/api/projects/{project_id}/preview/assets/')
        content = content.replace('src="assets/', f'src="/api/projects/{project_id}/preview/assets/')
        content = content.replace('src="compositions/', f'src="/api/projects/{project_id}/preview/compositions/')
        content = content.replace('data-composition-src="compositions/', f'data-composition-src="/api/projects/{project_id}/preview/compositions/')
        return HTMLResponse(content, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"})
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        logger.error("Failed generating project preview: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/preview/assets/{filename:path}")
async def get_project_preview_asset(project_id: str, filename: str):
    """Serve staged composition assets (media files, gsap script) for preview."""
    from backend.services.studio_service import StudioService
    from fastapi.responses import FileResponse
    proj_dir = StudioService.project_dir()
    asset_path = (proj_dir / "assets" / filename).resolve()
    if not asset_path.is_file() or not asset_path.is_relative_to((proj_dir / "assets").resolve()):
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset_path, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"})


@router.get("/{project_id}/preview/compositions/{filename:path}")
async def get_project_preview_composition(project_id: str, filename: str):
    """Serve staged subcomposition html and font/image assets for preview."""
    from backend.services.studio_service import StudioService
    from fastapi.responses import FileResponse, HTMLResponse
    proj_dir = StudioService.project_dir()
    comp_path = (proj_dir / "compositions" / filename).resolve()
    if not comp_path.is_file() or not comp_path.is_relative_to((proj_dir / "compositions").resolve()):
        raise HTTPException(status_code=404, detail="Composition file not found")
    if comp_path.suffix == ".html":
        html_text = comp_path.read_text(encoding="utf-8")
        html_text = html_text.replace('src="assets/', f'src="/api/projects/{project_id}/preview/compositions/assets/')
        html_text = html_text.replace('url("assets/', f'url("/api/projects/{project_id}/preview/compositions/assets/')
        return HTMLResponse(html_text, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"})
    return FileResponse(comp_path, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"})


@router.get("/catalog/items")
async def list_catalog_items(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100),
):
    """List available normalized catalog blocks from registry."""
    from backend.services.registry_adapter import RegistryAdapter
    items = RegistryAdapter.list_catalog_items(category=category, search=search, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/catalog/items/{block_id}")
async def get_catalog_item_detail(block_id: str):
    """Get normalized details for single catalog block."""
    from backend.services.registry_adapter import RegistryAdapter
    item = RegistryAdapter.get_catalog_item(block_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Block '{block_id}' not found")
    return item


@router.get("/{project_id}/code/files")
async def get_project_code_files(project_id: str, revision: Optional[int] = None):
    """Retrieve all logical code files for a project or specific revision snapshot."""
    try:
        if revision is not None:
            snapshot = await ProjectService.get_revision_snapshot(project_id, revision)
            doc = snapshot
        else:
            p = await ProjectService.get_project(project_id)
            import json
            doc = json.loads(p.document_json)
        code_sec = doc.get("code") or {}
        files = code_sec.get("files") or []
        return {
            "project_id": project_id,
            "revision": revision if revision is not None else p.revision,
            "files": files,
            "count": len(files),
        }
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/code/files/{file_id}")
async def get_project_code_file_detail(project_id: str, file_id: str, revision: Optional[int] = None):
    """Retrieve detail and content for a single code file."""
    try:
        if revision is not None:
            snapshot = await ProjectService.get_revision_snapshot(project_id, revision)
            doc = snapshot
        else:
            p = await ProjectService.get_project(project_id)
            import json
            doc = json.loads(p.document_json)
        code_sec = doc.get("code") or {}
        files = code_sec.get("files") or []
        target = next((f for f in files if f.get("id") == file_id or f.get("path") == file_id), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"File '{file_id}' not found in project")
        return target
    except HTTPException:
        raise
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/{project_id}/render")
async def render_project(project_id: str, body: dict = None, db: AsyncSession = Depends(get_db)):
    """Freeze revision snapshot and dispatch render."""
    body = body or {}
    requested_rev = body.get("revision")
    title = body.get("title")

    try:
        p = await ProjectService.get_project(project_id)
        frozen_rev, snapshot = await ProjectService.freeze_for_render(project_id, requested_rev)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    from backend.agents.job_helper import create_job
    from backend.core.task_runner import run_studio_render, dispatch
    from backend.services.hyperframes_adapter import HyperFramesAdapter

    effective_aspect = snapshot.get("aspect_ratio") or p.aspect_ratio or "9:16"

    # Stage isolated immutable directory for this render run
    try:
        frozen_rev, isolated_dir = await HyperFramesAdapter.stage_project_for_render(project_id, revision=frozen_rev)
    except Exception as e:
        logger.error("HyperFramesAdapter staging failed for render: %s", e)
        raise HTTPException(status_code=400, detail=f"Render staging failed: {e}")

    job = await create_job("motion_render", p.user_id, {
        "project_id": project_id,
        "project_revision": frozen_rev,
        "project_dir": str(isolated_dir),
        "title": title or p.name,
        "aspect_ratio": effective_aspect,
    })

    dispatch(run_studio_render(
        job_id=job.id,
        title=title or p.name,
        aspect_ratio=effective_aspect,
        project_id=project_id,
        project_revision=frozen_rev,
        project_dir=isolated_dir,
        user_id=p.user_id,
    ))

    return {
        "job_id": job.id,
        "project_id": project_id,
        "frozen_revision": frozen_rev,
        "message": f"Render dispatched from frozen revision {frozen_rev}.",
    }


@router.post("/{project_id}/ingest-trend")
async def ingest_trend_to_project(project_id: str, body: dict):
    """Ingest a trending video into library, link to project, and update document."""
    trend_result_id = body.get("trend_result_id")
    if not trend_result_id:
        raise HTTPException(status_code=400, detail="Missing required 'trend_result_id' parameter.")
    expected_revision = body.get("expected_revision")

    from backend.services.executor_service import ExecutorService
    from backend.services.project_service import ProjectService
    from backend.services.asset_resolver import AssetNotFoundError
    try:
        p = await ProjectService.get_project(project_id)
        target_rev = int(expected_revision) if expected_revision is not None else p.revision
        run = await ExecutorService.create_run(
            objective=f"Ingest trend {trend_result_id} into project {project_id}",
            project_id=project_id,
            input_revision=target_rev,
        )
        res = await ExecutorService.execute_step(
            run_id=run.id,
            step_name="ingest_trend",
            capability_name="ingest_trend",
            payload={
                "trend_result_id": trend_result_id,
                "project_id": project_id,
                "expected_revision": target_rev,
            },
        )
        return {
            "run_id": run.id,
            "step_id": res["step_id"],
            "status": res["status"],
            "output": res["output"],
            "verification": res["verification"],
        }
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed ingesting trend %s: %s", trend_result_id, e)
        raise HTTPException(status_code=400, detail=str(e))

