# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Vetted Creative Capabilities & Motion Doctrines:
Adapts vetted, license-safe motion design doctrines and caption models from
HyperFrames donor documentation into structured, production-safe 6Clips capability templates.
Strictly rejects directives to exfiltrate tokens, download remote scripts, or execute untrusted code.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Untrusted directive blacklist
DISALLOWED_PROMPT_PATTERNS = [
    r"https?://",
    r"curl\s+",
    r"wget\s+",
    r"fetch\(",
    r"child_process",
    r"subprocess",
    r"eval\(",
    r"exec\(",
    r"token",
    r"api_key",
    r"password",
    r"private_key",
    r"exfiltrate",
    r"override\s+policy",
    r"ignore\s+security",
]


class VettedMotionDoctrine(BaseModel):
    doctrine_id: str
    name: str
    category: str
    summary: str
    rules: List[str]
    parameters: Dict[str, Any]
    provenance: str = "HyperFrames Apache-2.0 documentation adapted for 6Clips"
    security_vetted: bool = True


class VettedCapabilityRegistry:
    """Manages sanitized motion composition laws, velocity seams, and caption models."""

    @classmethod
    def sanitize_directive_text(cls, text: str) -> str:
        """Strips harmful or unauthorized prompt instructions."""
        cleaned = text
        for pat in DISALLOWED_PROMPT_PATTERNS:
            cleaned = re.sub(pat, "[BLOCKED_UNSAFE_DIRECTIVE]", cleaned, flags=re.IGNORECASE)
        return cleaned

    @classmethod
    def get_all_vetted_doctrines(cls) -> List[Dict[str, Any]]:
        return [
            {
                "doctrine_id": "motion-doctrine",
                "name": "Continuous Camera & Vector Continuity Law",
                "category": "composition",
                "summary": "Multi-scene video must feel like ONE continuous camera move instead of a stack of independently animated slides.",
                "rules": [
                    "Vector Law: How a visual element exits a scene strictly determines how the next scene enters (momentum preservation).",
                    "Z Scale-Sign Rule: Expanding elements enter from camera-forward (Z+), shrinking elements recede (Z-).",
                    "Causal Motion: Every motion must be initiated by an observable trigger (click, swipe, beat, camera pan).",
                    "Ban on Idle Wobble: Elements must perform narrative work, not oscillate with gratuitous idle breathing.",
                    "Stillness Before Climax: A brief pause (120-180ms) prior to high-energy impact amplifies perceived motion.",
                ],
                "parameters": {
                    "min_stillness_hold_ms": 120,
                    "default_transition_ease": "cubic-bezier(0.16, 1, 0.3, 1)",
                    "idle_animation_permitted": False,
                },
                "security_vetted": True,
            },
            {
                "doctrine_id": "cut-the-curve",
                "name": "Velocity-Matched Seams & Staggered Cascades",
                "category": "transitions",
                "summary": "Five velocity-matched seam techniques that eliminate perceived hard cuts between motion scenes.",
                "rules": [
                    "Zoom-Through: Camera accelerates into an element until it exceeds viewport bounds, emerging into scene 2.",
                    "Inverse Zoom-Through: Camera pulls back rapidly from macro detail into broad scene context.",
                    "Cut-the-Curve: The transition cut occurs at peak velocity (derivative max) where the eye cannot perceive seam boundaries.",
                    "Waterfall Entry: Staggered arrival cascades for kinetic text cards and segment openers.",
                    "Nudge Curve (10/65/25): Slow acceleration (10%), high-velocity travel (65%), gentle settling deceleration (25%).",
                ],
                "parameters": {
                    "slide_ratios": {"accel": 0.10, "travel": 0.65, "settle": 0.25},
                    "peak_velocity_blur_px": 18,
                    "text_stagger_delay_sec": 0.04,
                },
                "security_vetted": True,
            },
            {
                "doctrine_id": "captions-overlay",
                "name": "Drop / Rail / Embed Caption Overlay Model",
                "category": "subtitles",
                "summary": "Captions are composited as an overlay on top of film content rather than shifting scene elements up.",
                "rules": [
                    "Never reserve a bottom keep-out band that displaces scene composition centers.",
                    "Drop: Low-information filler words (um, uh, like) are dropped from display.",
                    "Rail: Verbatim speech rides the bottom overlay rail with high-contrast pill backdrops.",
                    "Embed: High-impact emotional keywords are promoted into scarce animated kinetic typography in the scene body.",
                    "Safe Areas: Minimum 96px bottom padding on 9:16 to avoid platform UI overlays (TikTok/Reels).",
                ],
                "parameters": {
                    "safe_area_bottom_9_16_px": 96,
                    "safe_area_top_9_16_px": 80,
                    "max_words_per_subtitle_line": 6,
                    "highlight_color": "#ffd200",
                },
                "security_vetted": True,
            },
            {
                "doctrine_id": "seam-craft",
                "name": "Opaque Stage Ground & Anti-Flash Guard",
                "category": "rendering",
                "summary": "Master timeline composition invariants preventing frame dips, white flashes, and unpainted buffers.",
                "rules": [
                    "Opaque Stage-Ground: Composition root (#root) must enforce solid background color to eliminate white flash on cut seams.",
                    "Track Ping-Ponging: Alternating tracks (Track A / Track B) for overlapping crossfades.",
                    "Frame Hold: Hold outgoing scene final frame across transition duration to prevent premature unmount.",
                ],
                "parameters": {
                    "stage_ground_color": "#000000",
                    "transition_overlap_frames": 12,
                    "hold_final_frame": True,
                },
                "security_vetted": True,
            },
            {
                "doctrine_id": "oversized-cursor",
                "name": "Pointer-Led Action & UI Motion Igniter",
                "category": "mock-ui",
                "summary": "House-style pointer cursor interactions for software tutorials, product announcements, and mock-UIs.",
                "rules": [
                    "Off-Screen Entry Law: Cursors must always travel smoothly from off-screen rather than popping into existence.",
                    "Click Ignites the Next Beat: The mouse-down / click scale pulse is the exact trigger that launches subsequent animations.",
                    "Scale Ratio: Cursors rendered at 1.4x scale for legible mobile 9:16 viewing.",
                ],
                "parameters": {
                    "cursor_scale_multiplier": 1.4,
                    "click_pulse_scale": 0.88,
                    "click_hold_duration_ms": 90,
                },
                "security_vetted": True,
            },
            {
                "doctrine_id": "faceless-explainer",
                "name": "Faceless Explainer Storytelling Pacing",
                "category": "storytelling",
                "summary": "Rhythm and visual cadence for faceless video compositions and educational short-form clips.",
                "rules": [
                    "3-Second Hook Rule: Major visual shift or reveal every 2.5 to 3.0 seconds to maintain audience retention.",
                    "Graphic Hierarchy: Background visual supports, but never competes with foreground textual message.",
                    "Color Contrast Invariant: Foreground elements maintain minimum 4.5:1 WCAG contrast against animated backdrops.",
                ],
                "parameters": {
                    "max_scene_duration_sec": 3.0,
                    "min_contrast_ratio": 4.5,
                },
                "security_vetted": True,
            },
        ]

    @classmethod
    def get_vetted_doctrine(cls, doctrine_id: str) -> Dict[str, Any]:
        """Retrieve a specific vetted doctrine by ID or raise KeyError."""
        for doc in cls.get_all_vetted_doctrines():
            if doc.get("doctrine_id") == doctrine_id or doc.get("id") == doctrine_id:
                res = dict(doc)
                res["id"] = doc.get("doctrine_id")
                return res
        raise KeyError(f"Vetted doctrine '{doctrine_id}' not found.")


# Export module-level aliases for convenient imports
def get_vetted_capabilities() -> List[Dict[str, Any]]:
    docs = VettedCapabilityRegistry.get_all_vetted_doctrines()
    for d in docs:
        d["id"] = d.get("doctrine_id")
    return docs


def get_vetted_capability(capability_id: str) -> Dict[str, Any]:
    return VettedCapabilityRegistry.get_vetted_doctrine(capability_id)


def sanitize_capability_directive(text: str) -> str:
    return VettedCapabilityRegistry.sanitize_directive_text(text)


VETTED_CAPABILITIES = get_vetted_capabilities()
