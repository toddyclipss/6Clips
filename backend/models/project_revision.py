# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Project Revision log for tracking operations and document snapshots."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, Text, Integer, DateTime, UniqueConstraint

from backend.database import Base
from backend.models.base import UUIDMixin


class ProjectRevision(Base, UUIDMixin):
    __tablename__ = "project_revisions"
    __table_args__ = (
        UniqueConstraint("project_id", "revision", name="uq_project_revisions_project_revision"),
    )

    project_id = Column(String(36), index=True, nullable=False)
    revision = Column(Integer, nullable=False, index=True)
    
    # Operation that created this revision
    operation_type = Column(String(50), nullable=False)  # add_clip | update_clip | remove_clip | set_captions | patch_document | init
    operation_payload_json = Column(Text, nullable=False, default="{}")
    
    # Full snapshot of document at this revision
    document_snapshot_json = Column(Text, nullable=False)
    
    # Idempotency token to guard against duplicate retries
    idempotency_key = Column(String(100), nullable=True, index=True)
    
    # Deterministic SHA-256 fingerprint of the canonical operation, payload, and scope
    request_fingerprint = Column(String(64), nullable=True, index=True)
    
    # Author of the change: "user" | "agent"
    author = Column(String(20), default="user", nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
