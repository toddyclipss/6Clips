# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Production Media Pipeline Runner Protocol and Adapter Interface (Wave 9).

Defines the clean boundary contract between acceptance orchestration (Role 5),
the execution coordinator/router (Role 1), and the FFmpeg media rendering engine (Role 2):
- Minimal, stable protocol for rendering V1 3x60s shorts, V2 10-clip batches, and V3 long-form narrative.
- Enforces that fake/test doubles cannot leak into production paths.
- Provides ProductionMediaPipelineRunner which connects to Role 2's native media engine when mounted.
- Keeps signed approval distinct from physical artifact existence.
"""
from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .contracts import (
    SourceMediaAsset,
    V1ExpectedOutputSpec,
    V1ProductionContract,
    V2ExpectedOutputSpec,
    V2ProductionContract,
    V3ProductionContract,
)
from .probe import MediaProbeService

logger = logging.getLogger(__name__)


class PipelineRunnerError(Exception):
    """Raised when the media pipeline runner encounters an operational failure."""
    def __init__(self, code: str, message: str, is_retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.is_retryable = is_retryable


class RenderedOutputResult(BaseModel):
    """Result of rendering a single output specification."""
    output_id: str
    project_id: str
    file_path: str
    sha256_hash: str = ""
    duration_seconds: float = 0.0
    aspect_ratio: str = "9:16"
    has_audio: bool = True
    success: bool = True
    error_message: Optional[str] = None
    motion_review_url: str = ""
    is_synthetic_filler: bool = False


class MediaPipelineRunnerProtocol(abc.ABC):
    """
    Abstract contract for the native media rendering pipeline.
    Role 1 mounts the implementation provided by Role 2.
    """

    @abc.abstractmethod
    async def render_v1_shorts(
        self,
        contract: V1ProductionContract,
        output_directory: Path | str,
        budget_limit_attempts: int = 3,
    ) -> List[RenderedOutputResult]:
        """
        Renders the 3 independent ~60s vertical shorts from the single gameplay source.
        Returns results for each spec. If 3rd fails, returns preserved 1st & 2nd with 3rd marked failed.
        """
        pass

    @abc.abstractmethod
    async def render_v2_batch(
        self,
        contract: V2ProductionContract,
        output_directory: Path | str,
    ) -> List[RenderedOutputResult]:
        """
        Renders the 10 distinct vertical clips from the 5 multi-source video assets.
        """
        pass

    @abc.abstractmethod
    async def render_v3_narrative(
        self,
        contract: V3ProductionContract,
        output_directory: Path | str,
    ) -> RenderedOutputResult:
        """
        Renders the 8-10 minute 16:9 narrative condensation from the ~60-minute recording.
        """
        pass


class ProductionMediaPipelineRunner(MediaPipelineRunnerProtocol):
    """
    Production adapter that mounts Role 2's FFmpeg media rendering engine.
    In the unmounted or standalone acceptance state, strictly reports that the external
    media engine is pending mounting by Agent 1, avoiding invented synthetic results.
    """

    def __init__(self, engine_callable: Optional[Any] = None):
        self._engine = engine_callable

    @property
    def is_engine_mounted(self) -> bool:
        return self._engine is not None

    async def render_v1_shorts(
        self,
        contract: V1ProductionContract,
        output_directory: Path | str,
        budget_limit_attempts: int = 3,
    ) -> List[RenderedOutputResult]:
        if not self.is_engine_mounted:
            raise PipelineRunnerError(
                code="MEDIA_ENGINE_NOT_MOUNTED",
                message=(
                    "Native FFmpeg media producer is not mounted in this worker context. "
                    "Integration with Role 2 engine pending mounting by Role 1 router."
                ),
                is_retryable=False,
            )
        # Delegated to mounted native engine
        return await self._engine.render_v1(contract, output_directory, budget_limit_attempts)

    async def render_v2_batch(
        self,
        contract: V2ProductionContract,
        output_directory: Path | str,
    ) -> List[RenderedOutputResult]:
        if not self.is_engine_mounted:
            raise PipelineRunnerError(
                code="MEDIA_ENGINE_NOT_MOUNTED",
                message="Native FFmpeg media producer not mounted for V2 multi-source render.",
                is_retryable=False,
            )
        return await self._engine.render_v2(contract, output_directory)

    async def render_v3_narrative(
        self,
        contract: V3ProductionContract,
        output_directory: Path | str,
    ) -> RenderedOutputResult:
        if not self.is_engine_mounted:
            raise PipelineRunnerError(
                code="MEDIA_ENGINE_NOT_MOUNTED",
                message="Native FFmpeg media producer not mounted for V3 narrative render.",
                is_retryable=False,
            )
        return await self._engine.render_v3(contract, output_directory)
