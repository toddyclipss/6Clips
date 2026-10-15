# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Agent 5 Distribution Handoff Contract and Fail-Closed Guard.
Enforces that media delivery fails closed truthfully if publisher credentials or connections are missing.
No dummy publishers, fake receipts, or simulated uploads.
"""

import logging
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.connected_channel import ConnectedChannel
from backend.oaas_outcomes.models import Agent5DistributionHandoffContract

logger = logging.getLogger(__name__)


class DistributionHandoffManager:
    """Creates immutable distribution handoff payloads and enforces fail-closed connection checks."""

    @classmethod
    def normalize_platform_name(cls, destination_channel: str) -> str:
        """Map channel destination alias to database platform enum."""
        dest_lower = destination_channel.strip().lower()
        if "youtube" in dest_lower or "short" in dest_lower:
            return "youtube"
        if "tiktok" in dest_lower:
            return "tiktok"
        if "instagram" in dest_lower or "reel" in dest_lower:
            return "instagram"
        return dest_lower

    @classmethod
    async def check_channel_connection(
        cls,
        destination_channel: str,
        user_id: str = "local",
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Verify real connection and publication authorization in connected_channels.
        Returns: (is_connected_for_publish, status_truth, credentials_ref)
        """
        platform = cls.normalize_platform_name(destination_channel)

        async with AsyncSessionLocal() as db:
            query = select(ConnectedChannel).where(
                ConnectedChannel.user_id == user_id,
                ConnectedChannel.platform == platform,
            )
            res = await db.execute(query)
            channels = res.scalars().all()

            if not channels:
                return (
                    False,
                    f"No connected channel found for platform '{platform}'.",
                    None,
                )

            # Search for an active channel with publishing authorization
            publishing_channel = next((c for c in channels if c.can_publish), None)
            if not publishing_channel:
                first = channels[0]
                return (
                    False,
                    f"Channel '{first.channel_name or first.channel_url}' is in '{first.auth_type}' mode "
                    "without publishing permissions. OAuth publishing authorization required.",
                    None,
                )

            if not publishing_channel.credentials_ref:
                return (
                    False,
                    f"Channel '{publishing_channel.channel_name or platform}' lacks valid credentials_ref.",
                    None,
                )

            return True, "Channel connected and authorized for publication.", publishing_channel.credentials_ref

    @classmethod
    async def prepare_handoff_contract(
        cls,
        job_id: str,
        idempotency_token: str,
        render_file_sha256: str,
        media_path: str,
        project_id: str,
        revision_id: int,
        destination_channel: str,
        user_id: str = "local",
        user_authorized: bool = False,
        schedule_window: Optional[Dict[str, str]] = None,
        permission_scope: Optional[List[str]] = None,
    ) -> Agent5DistributionHandoffContract:
        """
        Prepare immutable Agent 5 distribution handoff contract.
        Fails closed with provider_status='PENDING_CREDENTIALS' or 'NOT_CONNECTED' if credentials missing.
        """
        is_connected, status_truth, cred_ref = await cls.check_channel_connection(
            destination_channel=destination_channel,
            user_id=user_id,
        )

        scope = permission_scope or ["content_publish", "metadata_write"]

        if not is_connected:
            logger.info(
                "Distribution handoff fail-closed: destination=%s, reason=%s",
                destination_channel,
                status_truth,
            )
            return Agent5DistributionHandoffContract(
                job_id=job_id,
                idempotency_token=idempotency_token,
                render_file_sha256=render_file_sha256,
                media_path=media_path,
                project_id=project_id,
                revision_id=revision_id,
                destination_channel=destination_channel,
                schedule_window=schedule_window,
                permission_scope=scope,
                user_authorized=user_authorized,
                provider_status="PENDING_CREDENTIALS",
                fail_closed=True,
                error_truth=f"Publication blocked: {status_truth}",
            )

        # Provider is connected, check explicit authorization
        if not user_authorized:
            return Agent5DistributionHandoffContract(
                job_id=job_id,
                idempotency_token=idempotency_token,
                render_file_sha256=render_file_sha256,
                media_path=media_path,
                project_id=project_id,
                revision_id=revision_id,
                destination_channel=destination_channel,
                schedule_window=schedule_window,
                permission_scope=scope,
                user_authorized=False,
                provider_status="CONNECTED",
                fail_closed=True,
                error_truth="Publication requires explicit user confirmation or standing authorization.",
            )

        # Fully authorized and connected
        return Agent5DistributionHandoffContract(
            job_id=job_id,
            idempotency_token=idempotency_token,
            render_file_sha256=render_file_sha256,
            media_path=media_path,
            project_id=project_id,
            revision_id=revision_id,
            destination_channel=destination_channel,
            schedule_window=schedule_window,
            permission_scope=scope,
            user_authorized=True,
            provider_status="CONNECTED",
            fail_closed=False,
            error_truth=None,
        )
