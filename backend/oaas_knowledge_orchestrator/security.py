# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 ViralMint Contributors
"""
Security and Safety Validator for Knowledge-First OAAS Orchestration.
Prevents prompt injection, shell command execution, SSRF attacks,
untrusted arbitrary code generation, and unauthorized media ingestion.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from backend.oaas_chat_ingestion.security import IngestionSecurityValidator

logger = logging.getLogger(__name__)

# Patterns indicative of shell command execution, script injection, or system traversal
UNSAFE_PATTERNS = [
    re.compile(r"(\brm\s+-rf\b|\brmdir\s+/s\b)", re.IGNORECASE),
    re.compile(r"(\bbash\s+-c\b|\bsh\s+-c\b|\bcmd\.exe\b|\bpowershell\b)", re.IGNORECASE),
    re.compile(r"(\bcurl\s+http|\bwget\s+http|\bnc\s+-e\b)", re.IGNORECASE),
    re.compile(r"(\beval\(|\bexec\(|\bsubprocess\.|\bos\.system|\bPopen\b)", re.IGNORECASE),
    re.compile(r"(<script[\s>]|javascript:|data:text/html)", re.IGNORECASE),
    re.compile(r"(\.\./\.\./|/etc/passwd|/windows/system32|c:\\windows)", re.IGNORECASE),
    re.compile(r"(\bDROP\s+TABLE\b|\bUNION\s+SELECT\b|\b1=1\b)", re.IGNORECASE),
]

VALID_ASPECT_RATIOS = {"9:16", "16:9", "1:1", "4:5"}


class SecurityValidationError(Exception):
    """Raised when an untrusted input fails security or safety validation."""
    pass


class KnowledgeSecurityValidator:
    """Security guards for knowledge orchestration."""

    @classmethod
    def sanitize_and_validate_prompt(cls, message: str) -> Tuple[bool, Optional[str]]:
        """
        Scan user input for prompt injection, shell commands, or malicious payloads.
        Returns (is_safe, error_reason).
        """
        if not message or not message.strip():
            return False, "User message cannot be empty."

        for pattern in UNSAFE_PATTERNS:
            match = pattern.search(message)
            if match:
                matched_token = match.group(0)
                logger.warning("Rejected malicious prompt pattern '%s' in message: %s", matched_token, message[:80])
                return False, f"Malicious or executable instruction pattern detected: '{matched_token}'"

        return True, None

    @classmethod
    def validate_duration_and_aspect(
        cls,
        duration_sec: float,
        aspect_ratio: str,
        min_sec: float = 1.0,
        max_sec: float = 300.0,
    ) -> Tuple[bool, Optional[str]]:
        """
        Strictly validate duration and aspect ratio values.
        """
        if math.isnan(duration_sec) or math.isinf(duration_sec):
            return False, "Duration cannot be NaN or infinite."

        if duration_sec < min_sec or duration_sec > max_sec:
            return False, f"Requested duration ({duration_sec}s) out of bounds [{min_sec}s, {max_sec}s]."

        if aspect_ratio not in VALID_ASPECT_RATIOS:
            return False, f"Aspect ratio '{aspect_ratio}' is invalid. Supported: {sorted(list(VALID_ASPECT_RATIOS))}."

        return True, None

    @classmethod
    def validate_untrusted_spec(cls, spec_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Ensure native motion spec contains no arbitrary executable JS/HTML scripts,
        suspicious remote URLs, or malicious expressions.
        """
        raw_str = str(spec_data)
        for pattern in UNSAFE_PATTERNS:
            match = pattern.search(raw_str)
            if match:
                matched_token = match.group(0)
                logger.warning("Unsafe pattern '%s' detected in motion spec", matched_token)
                return False, f"Unsafe expression detected in motion spec: '{matched_token}'"

        return True, None

    @classmethod
    def validate_source_url_authorization(
        cls,
        url: str,
        authorizations: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that any remote media URL has verified user rights and passes SSRF checks.
        """
        # 1. SSRF and scheme validation via existing IngestionSecurityValidator
        ssrf_ok, _, blocker_code, blocker_reason = IngestionSecurityValidator.validate_url(url)
        if not ssrf_ok:
            return False, f"SSRF security policy violation: {blocker_reason}"

        # 2. Rights confirmation requirement
        has_auth = (
            authorizations.get("user_authorized") is True
            or authorizations.get("rights_confirmed") is True
            or authorizations.get("standing_authorization") is True
        )
        if not has_auth:
            return False, "Remote media ingestion requires explicit user rights confirmation (user_authorized: true)."

        return True, None

    @classmethod
    def sanitize_retrieved_knowledge(cls, text_or_chunk: str) -> Tuple[bool, Optional[str]]:
        """
        Scan retrieved MDX/documentation snippets for prompt injection, executable code tags,
        or jailbreak instructions before passing to creative planner or prompt contexts.
        """
        if not text_or_chunk:
            return True, None

        # Check for injection and system override phrases
        injection_phrases = [
            "ignore previous instructions",
            "disregard all prior instructions",
            "system prompt override",
            "you are now in developer mode",
            "jailbreak",
            "pretend you are an unrestricted",
        ]
        text_lower = text_or_chunk.lower()
        for phrase in injection_phrases:
            if phrase in text_lower:
                logger.warning("Prompt injection pattern '%s' detected in retrieved knowledge", phrase)
                return False, f"Prompt injection pattern detected in retrieved knowledge: '{phrase}'"

        # Check for unsafe executable patterns
        for pattern in UNSAFE_PATTERNS:
            match = pattern.search(text_or_chunk)
            if match:
                matched_token = match.group(0)
                logger.warning("Unsafe pattern '%s' detected in retrieved knowledge content", matched_token)
                return False, f"Unsafe execution pattern in retrieved knowledge: '{matched_token}'"

        return True, None

    @classmethod
    def validate_file_path_isolation(cls, target_path: str) -> Tuple[bool, Optional[str]]:
        """
        Ensure file operations cannot traverse directories or touch protected system or database files.
        """
        path_lower = str(target_path).lower().replace("\\", "/")
        if ".." in path_lower:
            return False, "Path traversal ('..') is strictly prohibited."
        if "viralmint.db" in path_lower and not ("test" in path_lower or "mock" in path_lower):
            return False, "Direct writes to production viralmint.db are strictly blocked."
        if any(p in path_lower for p in ["/etc/", "system32", "windows/system", "/var/", "/secrets"]):
            return False, "System directory access is prohibited."
        return True, None
