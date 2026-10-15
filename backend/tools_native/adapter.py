# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Tools Native Adapter for Main Agent, Refine Inspector, and 5-Branch Integration.
Enables high-level execution of all 21 original tools over the canonical Project model.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .executor import NativeToolExecutor
from .models import NativeToolType, ToolActionRequest, ToolActionResult, ToolDescriptor
from .registry import NativeToolRegistry

logger = logging.getLogger(__name__)


class ToolsNativeAdapter:
    """Public integration adapter for Wave 19 Native Tools."""

    @classmethod
    async def execute_tool_command(
        cls,
        project_id: str,
        tool: str | NativeToolType,
        params: Optional[Dict[str, Any]] = None,
        expected_revision: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        author: str = "main_agent",
        user_id: str = "local",
    ) -> ToolActionResult:
        """
        Execute a native tool command by name or enum.
        If expected_revision is omitted, loads dynamically during execution.
        """
        if isinstance(tool, str):
            try:
                tool_type = NativeToolType(tool)
            except ValueError:
                return ToolActionResult(
                    success=False,
                    tool_type=NativeToolType.CAPTIONS,
                    project_id=project_id,
                    previous_revision=-1,
                    new_revision=-1,
                    error=f"Invalid tool type: {tool}",
                )
        else:
            tool_type = tool

        req = ToolActionRequest(
            project_id=project_id,
            tool_type=tool_type,
            params=params or {},
            expected_revision=expected_revision,
            idempotency_key=idempotency_key or str(uuid4()),
            author=author,
            user_id=user_id,
        )
        return await NativeToolExecutor.execute_tool(req)

    @classmethod
    async def batch_execute(
        cls,
        project_id: str,
        commands: List[Dict[str, Any]],
        author: str = "main_agent",
        user_id: str = "local",
    ) -> List[ToolActionResult]:
        """
        Execute a sequence of tool commands atomically chaining revisions.
        If any command fails, execution halts and returns results so far.
        """
        results = []
        for cmd in commands:
            tool = cmd.get("tool")
            params = cmd.get("params", {})
            res = await cls.execute_tool_command(
                project_id=project_id,
                tool=tool,
                params=params,
                author=author,
                user_id=user_id,
            )
            results.append(res)
            if not res.success:
                logger.warning(f"Batch tool execution halted at '{tool}': {res.error}")
                break
        return results

    @classmethod
    def list_capabilities(cls) -> List[ToolDescriptor]:
        """List all 21 native tools capabilities."""
        return NativeToolRegistry.list_all()

    @classmethod
    def get_descriptor(cls, tool: str | NativeToolType) -> Optional[ToolDescriptor]:
        """Get descriptor for specific tool."""
        return NativeToolRegistry.get(tool)
