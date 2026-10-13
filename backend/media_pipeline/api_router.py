# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""FastAPI router for MediaProducerPort and artifact streaming."""

import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from backend.media_pipeline.models import (
    ProductionReportV1,
    ProductionRequestV1,
)
from backend.media_pipeline.producer_adapter import get_media_producer

router = APIRouter(prefix="/api/media/production", tags=["Media Production"])


@router.post("/batch", response_model=dict)
async def submit_production_batch(request: ProductionRequestV1):
    """Submit a new production request to the MediaProducerPort."""
    producer = get_media_producer()
    result = await producer.submit_batch(request)
    return result


@router.get("/batch/{job_id}", response_model=ProductionReportV1)
async def get_production_batch(job_id: str):
    """Get the current ProductionReportV1 for a batch job."""
    producer = get_media_producer()
    report = producer.get_batch(job_id)
    return report


@router.post("/batch/{job_id}/cancel", response_model=dict)
async def cancel_production_batch(job_id: str):
    """Cancel an ongoing production batch."""
    producer = get_media_producer()
    result = producer.cancel_batch(job_id)
    return result


@router.get("/jobs", response_model=list)
async def list_production_jobs(user_id: Optional[str] = None):
    """List production jobs from durable ledger, optionally filtered by user_id."""
    producer = get_media_producer()
    if hasattr(producer, "_ledger"):
        records = producer._ledger.list_jobs(user_id=user_id)
        return [r.model_dump() for r in records]
    return []


@router.get("/artifacts/{artifact_id}/stream")
async def stream_artifact_video(artifact_id: str, request: Request):
    """HTTP Range streaming for rendered video artifacts.
    
    Serves byte ranges to support smooth player scrubbing without exposing file:// paths.
    """
    producer = get_media_producer()
    file_path = producer.resolve_artifact_path(artifact_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found.")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("Range")

    if not range_header:
        def iterfile():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        headers = {
            "Content-Length": str(file_size),
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
        }
        return StreamingResponse(iterfile(), headers=headers, media_type="video/mp4")

    # Range request handling
    try:
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else file_size - 1
    except Exception:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    chunk_length = end - start + 1

    def iter_chunk():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_length
            while remaining > 0:
                to_read = min(remaining, 65536)
                data = f.read(to_read)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_length),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(iter_chunk(), status_code=206, headers=headers, media_type="video/mp4")
