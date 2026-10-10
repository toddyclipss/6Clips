# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""Execution lifecycle models: Run -> Step -> Job for agent-executor separation."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, String, Text, Integer, Float, DateTime

from backend.database import Base
from backend.models.base import TimestampMixin, UUIDMixin


class ExecutionRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "execution_runs"

    user_id = Column(String(36), default="local", index=True, nullable=False)
    objective = Column(String(500), nullable=False)
    
    # Optional project reference and input revision pinning
    project_id = Column(String(36), nullable=True, index=True)
    input_revision = Column(Integer, nullable=True)
    
    # Status: pending | running | success | failed | cancelled | paused_for_input
    status = Column(String(30), default="pending", index=True, nullable=False)
    
    # Pinned model & provider configuration for this entire execution
    resolved_provider = Column(String(30), nullable=True)  # anthropic | openai | openrouter | none
    resolved_model = Column(String(100), nullable=True)
    credential_ref = Column(String(100), nullable=True)
    
    # Budget and execution policies
    budget_limit_usd = Column(Float, default=0.0)
    actual_cost_usd = Column(Float, default=0.0)
    fallback_policy = Column(String(50), default="stop_on_error")  # stop_on_error | fallback_deterministic
    
    context_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class ExecutionStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "execution_steps"

    run_id = Column(String(36), index=True, nullable=False)
    step_number = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    capability = Column(String(100), nullable=False)  # name in CapabilityRegistry
    
    # Link to underlying async Job if applicable
    job_id = Column(String(36), nullable=True, index=True)
    
    # Status: pending | running | success | failed | skipped
    status = Column(String(20), default="pending", index=True, nullable=False)
    
    # Input/output payloads
    input_payload_json = Column(Text, nullable=True)
    output_payload_json = Column(Text, nullable=True)
    
    # Verification result: unverified | verified | failed
    verification_status = Column(String(20), default="unverified", nullable=False)
    verification_details_json = Column(Text, nullable=True)
    
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
