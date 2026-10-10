# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Versioned Project model for the ViralMint production workspace."""
import json
from uuid import uuid4
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime
from datetime import datetime

from backend.database import Base
from backend.models.base import TimestampMixin, UUIDMixin


def default_empty_document(title: str = "Untitled Project", aspect_ratio: str = "9:16") -> str:
    """Default JSON document schema for a versioned project."""
    doc = {
        "schema_version": 2,
        "title": title,
        "aspect_ratio": aspect_ratio,
        "timeline": {
            "fps": 30,
            "duration_seconds": 0.0,
            "tracks": [
                {
                    "id": "track_video_main",
                    "type": "video",
                    "name": "Main Video",
                    "clips": []
                },
                {
                    "id": "track_audio_main",
                    "type": "audio",
                    "name": "Audio",
                    "clips": []
                },
                {
                    "id": "track_captions",
                    "type": "captions",
                    "name": "Captions",
                    "clips": []
                }
            ]
        },
        "bench_ranges": {},
        "assets": [],
        "code": {
            "files": []
        },
        "metadata": {
            "created_by": "user",
            "render_preset": "high",
        }
    }
    return json.dumps(doc)


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    user_id = Column(String(36), default="local", index=True, nullable=False)
    name = Column(String(200), nullable=False, default="Untitled Project")
    aspect_ratio = Column(String(10), default="9:16", nullable=False)
    
    # Monotonically increasing revision counter (1, 2, 3...)
    revision = Column(Integer, default=1, nullable=False)
    
    # The current persisted document state
    document_json = Column(Text, nullable=False, default=lambda: default_empty_document())
    
    # When locked/frozen for render or export
    is_frozen = Column(Boolean, default=False, nullable=False)
