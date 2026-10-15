# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
OAAS Outcome Adapter for Agent 5 Integration.
Provides a clean, disjoint interface for Agent 5 (Distribution/Analytics & Promotion)
to dispatch outcomes, query state, poll handoff contracts, and run reconciliation.
Agent 5 does not need to edit internal outcome logic.
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.oaas_outcomes.engine import OutcomeDeliveryEngine
from backend.oaas_outcomes.models import (
    Agent5DistributionHandoffContract,
    DurationPolicy,
    OutcomeJobRecord,
    OutcomeJobState,
    OutcomeRequestContract,
)


class OAASOutcomeAdapter:
    """
    Public integration interface for Agent 5 and downstream background workers.

    Integration Example for Agent 5:
    --------------------------------
    ```python
    from backend.oaas_outcomes.adapter import OAASOutcomeAdapter

    adapter = OAASOutcomeAdapter()

    # 1. Dispatch an outcome from Main Agent conversation:
    job = await adapter.execute_goal(
        user_goal="Create a 60-second video analyzing tech stocks trends",
        channel_targets=["youtube_shorts"],
        standing_authorization=False,
    )

    # 2. Check resulting state:
    print(f"Job {job.job_id} reached state: {job.state.value}")

    # 3. Retrieve distribution handoff contract (if verified):
    handoff = await adapter.get_distribution_handoff(job.job_id)
    if handoff and not handoff.fail_closed:
        # Agent 5 can safely proceed with authenticated upload/scheduling
        pass
    elif handoff and handoff.fail_closed:
        # Agent 5 truthfully informs user that credentials/connection are needed
        print(f"Handoff blocked: {handoff.error_truth}")
    ```
    """

    @classmethod
    async def execute_goal(
        cls,
        user_goal: str,
        channel_targets: Optional[List[str]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        editor_actions: Optional[List[Dict[str, Any]]] = None,
        standing_authorization: bool = False,
        session_id: str = "default_session",
        user_id: str = "local",
        idempotency_token: Optional[str] = None,
        allow_test_fixture: bool = False,
    ) -> OutcomeJobRecord:
        """Submit a user goal for autonomous planning, rendering, verification, and delivery."""
        token = idempotency_token or f"idem-{uuid4().hex}"
        pref = preferences or {
            "aspect_ratio": "9:16",
            "duration_seconds": 60.0,
            "duration_policy": DurationPolicy.TARGET,
            "tolerance_seconds": 3.0,
            "language": "en",
        }
        req = OutcomeRequestContract(
            user_id=user_id,
            session_id=session_id,
            user_intent=user_goal,
            permitted_channel_targets=channel_targets or ["youtube_shorts"],
            minimal_preferences=pref,
            project_id=project_id,
            editor_actions=editor_actions or [],
            standing_authorization=standing_authorization,
            idempotency_token=token,
        )
        return await OutcomeDeliveryEngine.execute_outcome(req, allow_test_fixture=allow_test_fixture)

    @classmethod
    def get_job(cls, job_id: str) -> Optional[OutcomeJobRecord]:
        """Fetch current state of an outcome job."""
        return OutcomeDeliveryEngine.load_job(job_id)

    @classmethod
    async def retry_job(cls, job_id: str, allow_test_fixture: bool = False) -> OutcomeJobRecord:
        """Retry a failed job idempotently."""
        return await OutcomeDeliveryEngine.retry_job(job_id, allow_test_fixture=allow_test_fixture)

    @classmethod
    def cancel_job(cls, job_id: str, reason: str = "User cancelled") -> OutcomeJobRecord:
        """Cancel an in-progress outcome job."""
        return OutcomeDeliveryEngine.cancel_job(job_id, reason=reason)

    @classmethod
    async def reconcile_active_jobs(cls) -> List[OutcomeJobRecord]:
        """Reconcile all incomplete jobs after a process crash or restart."""
        return await OutcomeDeliveryEngine.reconcile_all_active_jobs()

    @classmethod
    async def get_distribution_handoff(cls, job_id: str) -> Optional[Agent5DistributionHandoffContract]:
        """Retrieve the immutable Agent 5 distribution handoff contract for a job."""
        job = cls.get_job(job_id)
        if not job:
            return None
        return job.distribution_handoff
