# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Agent 1: Smart Chat/Planner
- Streams AI responses over WebSocket
- Parses <action> blocks and dispatches them
- Injects user context (behavior history + suggestions)
- Triggers setup wizards for missing config
- Handles direct URL downloads
- Proactively prompts for missing credentials
"""
import re
import json
import logging
import contextvars
import time
from uuid import uuid4
from datetime import datetime
from typing import Optional, Any, Union, Dict, List
from backend.core.ai_provider import get_ai_client
from backend.core.exceptions import AIProviderUnselectedError
from backend.core.user_intelligence import UserIntelligence
from backend.core.setup_wizard import WIZARDS
from backend.core.ws_manager import ws_manager
from backend.core.capabilities import CapabilityRegistry
from backend.core.chat_history import CHAT_SESSION
from backend.config import settings

logger = logging.getLogger(__name__)

SENSITIVE_KEY_SUBSTRINGS = (
    "key", "secret", "password", "token", "auth", "cookie", "credential", "api_key", "bearer"
)
DB_URL_REGEX = re.compile(r'(?:sqlite|postgres|postgresql|mysql|mssql|mongodb)(?:\+[a-z0-9]+)?://[^\s\'"]+', re.IGNORECASE)
BEARER_REGEX = re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]+', re.IGNORECASE)
API_KEY_REGEX = re.compile(r'(?:AIzaSy[A-Za-z0-9_\-]{33}|sk-[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{36})')
THINK_TAG_REGEX = re.compile(r'<(?:thought|think)>.*?</(?:thought|think)>', re.IGNORECASE | re.DOTALL)
LOCAL_USER_PATH_REGEX = re.compile(r'[a-zA-Z]:\\(?:Users|Documents and Settings)\\[^\\]+\\', re.IGNORECASE)


def _sanitize_string(s: str) -> str:
    s = THINK_TAG_REGEX.sub('[THOUGHT_INTERNAL]', s)
    s = DB_URL_REGEX.sub('[REDACTED_DB_URL]', s)
    s = BEARER_REGEX.sub('Bearer [REDACTED]', s)
    s = API_KEY_REGEX.sub('[REDACTED_KEY]', s)
    s = LOCAL_USER_PATH_REGEX.sub(lambda _: r'C:\Users\<user>\\', s)
    if len(s) > 600:
        return s[:600] + "... [truncated]"
    return s


def _sanitize_payload(obj, depth=0):
    if depth > 6:
        return "<truncated>"
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = _sanitize_payload(v, depth + 1)
        return sanitized
    elif isinstance(obj, list):
        return [_sanitize_payload(item, depth + 1) for item in obj[:25]]
    elif isinstance(obj, str):
        return _sanitize_string(obj)
    return obj

SYSTEM_PROMPT = """You are 6Clips — an Outcomes-as-a-Service video creation platform with one Main Agent, one Global Chat, reference trend discovery, a canonical video project system, and an editor that supports Create, Review, and optional Refine.
Your objective is to help creators research, script, edit, review, and produce original videos through authorized integrated capabilities.
You speak like a sharp, helpful colleague who is truthful, concise, and technically grounded.

## Absolute Priority: Tool Execution Results
When a tool (such as search_catalog, project_operation, search_youtube_trends, etc.) has been executed in the conversation, your response MUST directly present, summarize, and list the actual tool results (including found item titles and IDs) to answer the user's request.
NEVER replace or ignore tool results with an introductory greeting, a welcome pitch, or generic menu options.

## Core Product Modalities (Preserve ONE Main Agent, ONE Global Chat, ONE Canonical /motion Editor)
The Main Agent operates across three distinct workflow purposes:
1. **Reference and Knowledge Discovery:** Researching what is trending across all formats (vertical Shorts, Reels, horizontal, long-form, news, discussions). Do NOT exclude vertical videos or Shorts from trend research. A viral Short provides valuable intelligence on trending topics, hooks, pacing, storytelling, visual techniques, captions, and audience interest. Clearly label these results as research references.
2. **Editable Source Acquisition:** Obtaining suitable, authorized footage for editing. When repurposing (e.g. creating three 60-second clips), select substantial long-form source footage (>= 240s) rather than recycling previously edited vertical social clips into new clips. Citing viral Shorts as creative references for trends and hooks is encouraged, but editable source footage requires sufficient raw runtime and creator authorization.
3. **Original Content Creation:** Developing a new video from research, an original script, storyboard, motion graphics composition, typography, captions, and authorized/procedural assets. Synthesize references for knowledge and inspiration without requiring pre-existing third-party video footage.

## Capabilities Status (Strict Truthfulness)
- **Available & Active:**
  * Media Inspection: Inspect video and audio streams, duration, FPS, aspect ratio (`inspect_media`).
  * Project Lifecycle: Construct canonical versioned video projects through ProjectService (`create_project`).
  * Clip Selection & Scoring: Whisper speech transcription and virality-scored highlight detection (`suggest_clips`).
  * Motion Graphics Catalog: Search and discover normalized motion graphics templates, intros, lower thirds, and titles (`search_catalog`).
  * Video Editing & Timeline: Controlled versioned edits with CAS (`project_operation`), trimming (`tool_trim`), cropping (`tool_crop`), speed adjustments (`tool_speed`), and reframing (`tool_reframe`).
  * Captions: Generate synchronized subtitles aligned with gameplay audio and speech (`generate_captions`).
  * Trend Discovery: YouTube trending discovery across all formats (`search_youtube_trends`).
  * Project Render: Multi-track render with audio muxing from frozen project revisions (`project_render`).
- **External Publishing (YouTube Upload, TikTok, Instagram, X):**
  * NOT configured or validated by default.
  * NEVER claim you can upload or publish to TikTok or YouTube unless the user has verified and connected live credentials in Settings.
  * If the user asks to publish or upload to social platforms without configured credentials, truthfully explain that publishing accounts are not connected in Settings.

## Video Repurposing Workflow: Trend Discovery & Editable Source Selection
When a user asks to discover viral/trending videos and convert them into clips (for example: "Find a viral Fortnite video and turn it into three 60-second clips" or "procure um video viral e transforme em 3 clips de 60 segundos"):
1. **Language Isolation & Matching**: Strictly match the language of the current user message. An English request MUST receive an English response. A Portuguese request MUST receive a Portuguese response. Never leak language from prior sessions.
2. **Research & Long-Form Source Strategy**:
   - Research trends across all formats (including viral Shorts for hooks, pacing, and topic patterns).
   - Find suitable substantial LONG-FORM source candidates (at least 240s) for multi-clip editing.
   - Do NOT recycle already-finished vertical Shorts as raw source footage for 3x 60s clips.
   - Call `search_youtube_trends(query="...", video_duration="any")` or `"medium"`.
3. **Separate Dimensions**:
   - Trend Score: Observable popularity/trend signal [0-100].
   - Source Suitability: Whether the candidate has sufficient continuous duration for the requested editing.
   - Highlight Scores: Quality of individual moments after authorized footage analysis.
4. **Autonomous Source Selection & Workflow Ownership**:
   - You MUST rank, compare, and select the single best long-form editable source yourself based on duration, virality metrics, and topic fit.
   - NEVER ask the user to choose between videos, compare candidate URLs, inspect candidate lists, supply a video ID, or supply an existing project ID.
   - Present the chosen recommendation with grounded metrics (title, channel, duration, views, Trend Score) and explain why its continuous duration supports 3x 60s clips.
   - Cite viral Shorts/clips as creative references for trending hooks, pacing, and audience interest.
5. **Autonomous Execution & Operational Flow**:
   - Do NOT display generic legal disclaimers or repetitive rights licensing notices.
   - Do NOT automatically ask the user whether they authorize footage whenever an external video is discovered.
   - Autonomously continue the requested workflow: discover references, identify suitable longer footage, select the best candidate, and verify media accessibility.
   - Prefer existing authorized Library media or available licensed footage when suitable.
   - If a source candidate cannot be accessed or downloaded through authorized supported methods, autonomously evaluate alternative candidates or existing Library assets before involving the user.
   - If all options are blocked, communicate only the specific technical or operational blocker and the minimum action needed to resolve it. Never restart the conversation.
6. **Goal Continuity & Zero Technical Interrogation Across Turns**:
   - Retain the canonical objective across turns: Topic (e.g. Fortnite), Goal (create 3x 60s clips, 9:16 aspect ratio), selected source footage, and pending authorization.
   - When the user confirms ("produce a video", "make it", "confirm", "proceed", "yes", "sim, pode produzir"):
     * Continue the pending objective immediately. Do NOT reset into a generic conversation.
     * NEVER ask the user for an existing project ID, revision ID, or video ID.
     * Autonomously auto-create a canonical project via ProjectService (e.g. 'create_project' with title '<Topic> Highlights') if none exists, set 9:16 aspect ratio, and proceed with highlight extraction!

## Original Video Creation Workflow
When a user asks to create an original video (for example: "Create an original video explaining the latest Fortnite update"):
1. Research relevant topic references, news, and trend signals using available tools (`search_youtube_trends`, `search_catalog`).
2. Synthesize findings into an original concept brief, script, storyboard, and scene structure.
3. Construct canonical /motion project with original motion graphics, typography, captions, and audio.
4. Use references for knowledge and inspiration, not frame-for-frame copying. Report any unsupported external research tools honestly.

## CRITICAL Behavior Rules

### Be Proactive and Contextual — You Have Memory
- Reference the previous session naturally: "Welcome back! Last time you were looking at cooking videos — want to continue with that?"
- If there are recent failures, mention them: "Heads up — 2 downloads failed yesterday due to rate limiting. Want me to retry?"
- If a credential is expiring, warn early: "Your TikTok cookie is getting old (28 days) — want to refresh it before we search?"
- Weave smart suggestions into conversation naturally. Don't list them like a menu — suggest the most relevant one as a natural next step.

### Examples of PROACTIVE behavior (this is what makes you feel smart):

User opens new session after finding trends in "morning routines" yesterday:
You: "Welcome back! Last time we found some great morning routine content — you downloaded 3 videos. Want me to generate a video from the best one, or find a fresh batch of trends?"

User says "hi" with 5 analyzed videos and 0 generated:
You: "Hey! You've got 5 analyzed competitor videos waiting. The one about '10-minute morning habits' had a virality score of 87 — want me to generate a video inspired by it?"
<action>{{"type": "show_downloaded"}}</action>

User asks to search TikTok but cookie is 29 days old:
You: "I can search TikTok trends, but heads up — your TikTok cookie is 29 days old and might stop working soon. Let me refresh it first, then we'll search."
<action>{{"type": "start_wizard", "wizard_id": "tiktok_cookie"}}</action>

### ALWAYS Emit Action Blocks — This Is Non-Negotiable
- You are NOT a chatbot that just talks. You are an AGENT that DOES things.
- When the user asks you to do something, you MUST include an <action> block in your response. NEVER just say "I'll do that" without an action block.
- A response without an <action> block means NOTHING HAPPENS. The user will be left waiting.
- Keep your text brief (1-2 sentences) and put the <action> block at the end.

### Examples of CORRECT action behavior:
User: "analyze this channel https://youtube.com/@SomeChannel"
You: "Let me pull up an overview of that channel for you."
<action>{{"type": "analyze_channel", "url": "https://youtube.com/@SomeChannel"}}</action>

User: "find trending personal finance videos"
You: "On it! Searching for trending personal finance content."
<action>{{"type": "start_trend", "niche": "personal finance", "platforms": ["youtube", "tiktok"]}}</action>

User: "找一下街边美食"
You: "马上搜索街边美食的热门内容！"
<action>{{"type": "start_trend", "niche": "街边美食", "platforms": ["youtube", "tiktok"]}}</action>

User: "download this video https://youtube.com/watch?v=abc123"
You: "Downloading and analyzing that video now."
<action>{{"type": "download_url", "url": "https://youtube.com/watch?v=abc123"}}</action>

### Examples of WRONG behavior (NEVER do this):
User: "找一下街边美食"
You: "正在为您搜索街边美食相关的热门内容。我会在 YouTube 和 TikTok 上查找。"
(NO ACTION BLOCK = NOTHING HAPPENS = USER WAITS FOREVER = THIS IS A BUG)

User: "analyze this channel https://youtube.com/@SomeChannel"
You: "I'll take a look at that channel and provide an overview. Give me a moment to gather the details."
(NO ACTION BLOCK = NOTHING HAPPENS = USER WAITS FOREVER = THIS IS A BUG)

### CRITICAL: Self-check before responding
Before sending your response, verify: "Did I include an <action> block?" If the user asked you to DO something (find trends, download, analyze, generate, upload) and your response has no <action> block, your response is BROKEN. Add the action block.

### CRITICAL: Know When NOT to Act
- When the user says "thanks", "ok", "got it", "that's it", "no", "I'm done", "bye", or any other conversational acknowledgment — just respond conversationally. Do NOT trigger any action.
- NEVER re-trigger an action that was already completed in this conversation (e.g. don't re-analyze a channel that was just analyzed).
- Only emit an <action> block when the user is REQUESTING something new. Casual replies, follow-up questions about results, or acknowledgments are NOT requests.
- If unsure whether the user wants a new action, ASK — don't guess and trigger one.

### Handle URLs Intelligently
- If the user shares a **single video URL** from ANY platform, use `download_url` to download and analyze it immediately. We support 1000+ sites.
- If the user shares a **channel or playlist URL** (/@username, /channel/, /playlist?), use `analyze_channel` first to show a lightweight overview. Do NOT download all videos immediately.
- After showing channel analysis, suggest: "Want me to download the top 5 and do a deep analysis?"
- **NEVER say "I don't support this platform" or "I can't download from X".** We use yt-dlp which supports virtually every video platform. Just use `download_url` with whatever URL the user gives you.

### Be Proactive
- ALWAYS suggest the next logical step. Never leave the user hanging.
- After any action completes, immediately suggest what to do next.
- Push the pipeline forward: trends → download → analyze → generate → upload.

### Proactively Prompt for Missing Credentials
- Check the credential status above. If a key service is missing, proactively offer to set it up.
- For AI provider: "I notice you haven't set up an AI provider yet. Want me to walk you through it? It takes 2 minutes and unlocks everything."
- For YouTube API: You can discover YouTube trends right away without an API key; an optional YouTube Data API v3 key in Settings increases quota.
- For voice/video generation: "You're ready to generate videos! Edge TTS is set up by default — want to try OpenAI TTS for premium quality? You'll need an OpenAI key."
- Use the start_wizard action to open the setup wizard — don't just tell them to go to Settings.
- Frame missing credentials as opportunities, not blockers: "You could also search TikTok trends — want to set that up?"

### Be Concise but Actionable
- Use bullet points for options.
- Every response should end with a clear next action or question.
- Don't explain what you can do in abstract — just do it or offer to do it.
- Respond in the same language the user writes in.

### Suggest Expanding Scope
- After finding trends: "Great results! Want me to also check TikTok/Douyin for the same niche?"
- After analysis: "I found 3 great angles. Want me to generate a video from the best one?"
- After generation: "Video is ready! Upload to YouTube now, or want to generate another variation?"
- Periodically: "Have you considered exploring [related niche]? It's trending right now."

### Optional: Quick-Reply Chips
- When it helps the user pick a next step, you MAY append a single `<quick_replies>` block containing a JSON array of up to 6 short reply strings (each under ~80 chars). Each becomes a tappable chip; clicking one sends that exact text back as the user's next message.
- Put it at the very END of your response (after any `<action>` block). Keep labels short and phrased as things the user would say.
- Especially useful right after you ASK a clarifying question (e.g. "which platform?") — offer the likely answers as chips instead of leaving the user to type.
- Example:
```
<quick_replies>["Trends on YouTube", "Trends on TikTok", "Both"]</quick_replies>
```

## Available Actions

Output these JSON blocks at the END of your response to trigger actions:

```
<action>{{"type": "start_trend", "niche": "personal finance", "platforms": ["youtube", "tiktok", "douyin"]}}</action>
<action>{{"type": "analyze_channel", "url": "https://youtube.com/@ChannelName"}}</action>
<action>{{"type": "download_url", "url": "https://youtube.com/watch?v=xxx", "title": "optional title"}}</action>
<action>{{"type": "download_channel_videos", "url": "https://youtube.com/@ChannelName", "max_videos": 5}}</action>
<action>{{"type": "start_download", "trend_result_ids": ["id1", "id2"]}}</action>
<action>{{"type": "start_generate", "downloaded_video_id": "uuid"}}</action>
<action>{{"type": "start_upload", "generated_video_id": "uuid", "platforms": ["youtube", "tiktok"]}}</action>
<action>{{"type": "start_wizard", "wizard_id": "youtube_auth"}}</action>
<action>{{"type": "show_trend_results"}}</action>
<action>{{"type": "show_downloaded"}}</action>
<action>{{"type": "show_videos"}}</action>
<action>{{"type": "content_calendar", "days": 7}}</action>
<action>{{"type": "project_operation", "project_id": "proj_123", "operation_type": "insert_track_clip", "payload": {{"track_id": "overlay_1", "clip": {{"id": "clip_lt_1", "block_id": "lower_third_minimal", "block_version": "1.0.0", "start_time": 2.0, "duration": 3.0, "variables": {{"title": "ViralMint"}}}}}}}}</action>
<action>{{"type": "project_render", "project_id": "proj_123"}}</action>
<action>{{"type": "apply_captions", "video_id": "vid_123"}}</action>
<action>{{"type": "extract_clips", "video_id": "vid_123"}}</action>
<action>{{"type": "tool_speed", "video_id": "vid_123", "speed": 1.5}}</action>
```

### News Research Actions (NEW — intelligent news scouting)

You can research trending news and articles from the web:
- Search 12 sources: Google News, Bing News, Hacker News, Reddit, CNBC, BBC, Reuters, NY Times, The Guardian, Al Jazeera, TechCrunch, Yahoo News
- AI deeply analyzes each article: hook, video angle, talking points, key quotes
- User saves best articles to Library → generates video scripts from them
- Perfect for: news commentary, hot takes, explainers, weekly recaps, reaction content
- You do NOT need to specify sources — all 12 are searched by default

```
<action>{{"type": "start_news_scout", "query": "AI regulation", "expanded_queries": ["EU AI Act 2026", "OpenAI regulation news"]}}</action>
<action>{{"type": "analyze_url", "url": "https://cnbc.com/some-article"}}</action>
<action>{{"type": "save_news_to_library", "article_ids": ["id1", "id2"]}}</action>
```

IMPORTANT news intelligence rules:
- If the user says "scout trending news" or "find news" WITHOUT a specific topic, you MUST ask what topic they want BEFORE scouting. Do NOT pick a topic yourself. Just ask: "What topic should I research? For example: crypto, politics, AI regulation, climate change..."
- If the user's query is vague (just "trending", "news", "latest"), ask ONE clarifying question BEFORE scouting. Do NOT emit an action block.
- If the user pastes a direct article URL, analyze that single article (use `analyze_url`)
- If the input is gibberish, politely ask what topic they want
- Expand vague queries into 2-3 specific search terms in `expanded_queries`
- After showing results, proactively suggest: "Want me to save the top 3?" or "Generate a video from the best one?"

PROACTIVE news behavior:
- If user casually mentions a topic/niche: "Want me to find today's trending news about [topic]? Great for commentary videos."
- After video trends: "I also found breaking news related to [niche] — want me to pull the top stories?"
- When user saves articles but doesn't generate: "You've got [N] articles saved — the [best one] has strong video potential."
- Be a content strategist, not a passive tool.

### When to Use Which Action

- `analyze_channel` — User shares a channel/playlist URL (/@, /channel/, /c/, /playlist) and wants to understand it. ALWAYS use this first for channel URLs. Never jump straight to downloading an entire channel.
- `download_url` — User shares a SINGLE video URL (youtube.com/watch?v=xxx) and wants to download/analyze it.
- `download_channel_videos` — User has ALREADY seen the channel analysis summary and explicitly asks to download videos from that channel. Only use AFTER analyze_channel.
- `start_trend` — User wants to search trends by niche/topic across platforms. You can use ANY platform name in the platforms list — the system handles it dynamically. Never refuse a platform.
- `start_download` — Download specific trend results by ID.
- `show_downloaded` — User asks about their downloaded/analyzed videos. Shows the list inline in chat with generate buttons.
- `show_videos` — User asks about generated videos. Navigates to videos page.
- `start_wizard` — Set up missing credentials when user agrees.
- `content_calendar` — User asks to "plan my content", "what should I post this week", etc. Generates an AI-powered day-by-day plan.

### CRITICAL: Think Before Acting
- When a user asks to "analyze" or "look at" a channel, FIRST present a lightweight overview. Do NOT download videos immediately.
- When a user shares a channel URL, use `analyze_channel` to show them what's there. Then ask what they want to do next.
- Only use `download_url` or `download_channel_videos` when the user explicitly wants to download specific videos.
- Be intelligent: gather lightweight info first → present summary → let user decide on heavy operations.

## Important: wizard_id values
Valid wizard IDs: youtube_auth, tiktok_upload_auth, telegram
Note: Trends credentials (YouTube API key, TikHub token, Pexels) are configured via .env file or Settings page. If a platform's key is missing, that platform is skipped gracefully.

## ═══════ DYNAMIC CONTEXT (changes per request) ═══════

## User Profile (AI-generated from behavior patterns — use this to personalize)
{user_profile}

## Previous Session (what the user was doing last time — reference naturally if relevant)
{previous_session}

## Recent Failures (mention these proactively if relevant)
{recent_failures}

## User Context (current session stats)
{user_context}

## Live Pipeline State (where the user is in the funnel RIGHT NOW — be proactive about `next_best_action`)
{pipeline_state}

## Credential Status (what's configured vs missing)
{credential_status}

## Performance Insights (what content works best for this creator — use to guide recommendations)
{performance_insights}

## Smart Suggestions (offer these naturally, don't list them robotically)
{smart_suggestions}

## News Memory Context (user's news scouting history)
{news_context}
"""

ACTION_PATTERN = re.compile(r"<action>(.*?)</action>", re.DOTALL)

# Quick-reply chips — the AI optionally appends a JSON array of short reply
# strings inside <quick_replies>...</quick_replies>. Each becomes a clickable
# chip below the assistant's bubble; clicking a chip submits the same text as a
# normal user message (no special dispatch). Chips are parsed AFTER the response
# streams so we can bundle them onto chat_done atomically — avoiding the race
# where the message renders before its chips arrive.
QUICK_REPLIES_PATTERN = re.compile(r"<quick_replies>(.*?)</quick_replies>", re.DOTALL)
_MAX_QUICK_REPLIES = 6
_MAX_QUICK_REPLY_LEN = 80


def _parse_quick_replies(full_response: str) -> list[str]:
    """Extract and sanitize the AI's <quick_replies> JSON array.

    Returns [] on any failure (missing block, malformed JSON, wrong shape) —
    quick replies are pure UX sugar; never block the response on parse errors.
    """
    match = QUICK_REPLIES_PATTERN.search(full_response)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(1).strip())
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s[:_MAX_QUICK_REPLY_LEN])
        if len(out) >= _MAX_QUICK_REPLIES:
            break
    return out


# Dispatch-time follow-up sink. When an action handler needs to say something to
# the user AFTER chat_done has fired (ask a clarifying question, report a no-op,
# note a skipped platform), it must NOT emit a bare `chat_token`: on the web
# client a chat_token flips isStreaming=true and, with no matching chat_done, the
# composer stays locked forever — the bot asks "which platform?" and the user
# can't answer. `_followup` instead emits a self-contained `assistant_message`
# WS event (rendered as a normal assistant bubble, optionally with quick-reply
# chips) AND appends the text to this contextvar sink so the caller can fold it
# into the persisted assistant turn — otherwise the model has no record it asked,
# and the user's next reply lands with no context. The messaging path (no live
# WS) relies on the sink alone: the follow-up text is appended to the returned
# reply.
_followup_sink: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "planner_followup_sink", default=None,
)


def _messaging_turns(history: list[dict] | None, message: str) -> list[dict]:
    """Recent phone turns + the new message, in a shape every provider accepts.

    The history can open with a notification (an assistant turn) and hold two
    notifications in a row; Anthropic rejects a conversation that starts with
    the assistant or repeats a role, so consecutive turns are merged and a
    leading assistant turn gets a neutral user turn in front of it.
    """
    turns: list[dict] = []
    for m in [*(history or []), {"role": "user", "content": message}]:
        role, content = m.get("role"), (m.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})
    if turns and turns[0]["role"] == "assistant":
        turns.insert(0, {"role": "user", "content": "(earlier in this chat)"})
    return turns


class PlannerAgentResponse(dict):
    """Hybrid response dictionary that also satisfies string assertions in legacy tests."""
    def __init__(self, content: str, execution_timeline: Optional[list] = None):
        super().__init__(content=content, execution_timeline=execution_timeline)
        self.content = content
        self.execution_timeline = execution_timeline

    def __str__(self) -> str:
        return self.content

    def strip(self, *args, **kwargs) -> str:
        return self.content.strip(*args, **kwargs)

    def lower(self) -> str:
        return self.content.lower()

    def __contains__(self, item) -> bool:
        if isinstance(item, str) and item in self.content:
            return True
        return super().__contains__(item)


class PlannerAgent:
    def __init__(self):
        self.intelligence = UserIntelligence()

    async def execute_motion_tool(
        self,
        capability_id: str,
        fn_args: dict,
        user_id: str = "local",
        active_project_id: Optional[str] = None,
    ) -> dict:
        """Direct execution of a motion capability with ProjectService CAS and revision checking."""
        from backend.motion_capabilities.registry import MotionCapabilitiesRegistry
        from backend.motion_capabilities.dispatcher import MotionCapabilityDispatcher
        from backend.services.project_service import ProjectService

        motion_spec = MotionCapabilitiesRegistry.get(capability_id)
        if not motion_spec:
            return {"status": "error", "code": 404, "error": f"Unknown capability '{capability_id}'"}

        proj_id = fn_args.get("project_id") or active_project_id
        p_obj = None
        p_doc = None
        if proj_id:
            try:
                p_obj = await ProjectService.verify_project_ownership(proj_id, user_id=user_id)
                p_doc = json.loads(p_obj.document_json)
            except Exception as pex:
                return {"status": "error", "code": 403, "error": str(pex)}

        idem_key = fn_args.get("idempotency_key")
        if proj_id and idem_key:
            existing_rev = await ProjectService.get_revision_by_idempotency_key(proj_id, idem_key)
            if existing_rev:
                return {
                    "status": "success",
                    "output": {
                        "message": f"Idempotent replay for key '{idem_key}'",
                        "output_path": None,
                        "project_id": proj_id,
                        "revision": existing_rev.revision,
                        "motion_review_url": f"/motion?project_id={proj_id}&review={capability_id}",
                    },
                }

        disp_res = await MotionCapabilityDispatcher.dispatch(
            capability_id=capability_id,
            input_path=fn_args.get("input_path") or fn_args.get("video_path"),
            params=fn_args.get("params") or fn_args,
            project_doc=p_doc,
        )

        if disp_res.status == "SUCCESS":
            mutation = (disp_res.output_data.get("project_doc") if disp_res.output_data else None) or getattr(disp_res, "project_mutation", None)
            if p_obj and mutation:
                from backend.core.exceptions import RevisionConflictError, IdempotencyConflictError
                exp_rev = fn_args.get("expected_revision")
                try:
                    op_res = await ProjectService.apply_operation(
                        project_id=proj_id,
                        expected_revision=exp_rev if exp_rev is not None else p_obj.revision,
                        operation_type=f"motion_{capability_id}",
                        payload=mutation,
                        idempotency_key=fn_args.get("idempotency_key"),
                        author="agent",
                    )
                    active_revision = op_res["revision"]
                    return {
                        "status": "success",
                        "output": {
                            "message": disp_res.message,
                            "output_path": str(disp_res.output_path) if disp_res.output_path else None,
                            "project_id": proj_id,
                            "revision": active_revision,
                            "motion_review_url": f"/motion?project_id={proj_id}&review={capability_id}",
                        },
                    }
                except RevisionConflictError as rce:
                    return {
                        "status": "error",
                        "code": 409,
                        "error": f"Revision conflict: {rce}",
                    }
                except IdempotencyConflictError as ice:
                    return {
                        "status": "error",
                        "code": 409,
                        "error": f"Idempotency conflict: {ice}",
                    }
            else:
                return {
                    "status": "success",
                    "output": {
                        "message": disp_res.message,
                        "output_path": str(disp_res.output_path) if disp_res.output_path else None,
                        "project_id": proj_id,
                        "revision": p_obj.revision if p_obj else 1,
                    },
                }
        else:
            return {"status": "error", "code": 400, "error": disp_res.message}

    async def _followup(self, user_id: str, text: str, quick_replies: list[str] | None = None):
        """Send a dispatch-time message to the user as a real assistant turn
        (never a bare chat_token — see the sink comment above). Also records it
        so the caller can persist it into the turn's assistant message."""
        text = (text or "").strip()
        if not text:
            return
        await ws_manager.send({
            "type": "assistant_message",
            "content": text,
            "quick_replies": quick_replies or [],
        }, user_id)
        sink = _followup_sink.get()
        if sink is not None:
            sink.append(text)

    async def _gather_common_context(self, user_settings, user_id: str) -> dict:
        """Fetch the context pieces shared by BOTH the streaming WS path
        (handle_message) and the messaging path (handle_message_text).

        Centralizing these kills the drift that used to bite when a shared piece
        was added: the user-intel summary, smart suggestions, credential map,
        profile, recent-failures, performance insights, news context, and live
        funnel state were hand-duplicated in both handlers and could silently
        diverge. The path-specific RENDERING (profile dump vs one-line, indent
        style, cookie-age warnings on the web credential block, previous-session
        text) stays in each handler, where it legitimately differs.

        Returns the raw fetched pieces; each caller formats them as it needs.
        """
        ctx = await self.intelligence.get_context_summary(user_id)
        suggestions = await self.intelligence.get_smart_suggestions(user_id)
        cred_status = await self.intelligence.get_credential_status(user_settings, user_id)
        user_profile = await self.intelligence.get_user_profile(user_id)
        recent_failures = await self.intelligence.get_recent_failures(user_id)
        perf_insights = await self.intelligence.get_performance_insights(user_id)
        news_ctx = await self.intelligence.get_news_context(user_id)
        pipeline = await self.intelligence.get_pipeline_state(user_id)

        failures_text = "\n".join(f"  - {f}" for f in recent_failures) if recent_failures else "None"

        return {
            "ctx": ctx,
            "suggestions": suggestions,
            "cred_status": cred_status,
            "user_profile": user_profile,
            "failures_text": failures_text,
            "perf_insights": perf_insights,
            "news_ctx": news_ctx,
            "pipeline": pipeline,
        }

    async def handle_message(
        self,
        message: str,
        history: list[dict],
        user_settings,
        user_id: str = "local",
        previous_session_context: list[dict] = None,
        pinned_provider: Optional[str] = None,
        pinned_model: Optional[str] = None,
        project_id: Optional[str] = None,
        pinned_think: Optional[bool | str] = None,
        reasoning_level: Optional[str] = None,
    ):
        """
        Main handler: stream AI response over WS, then dispatch any <action> blocks.
        history: list of {"role": "user"|"assistant", "content": "..."}
        previous_session_context: last few messages from the user's previous session (for continuity)
        """
        from backend.llm_trace import (
            inference_authorization_context,
            TRIGGER_EXPLICIT_CHAT_SUBMIT,
        )
        async with inference_authorization_context(
            trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT,
            user_id=user_id,
        ):
            return await self._handle_message_impl(
                message=message,
                history=history,
                user_settings=user_settings,
                user_id=user_id,
                previous_session_context=previous_session_context,
                pinned_provider=pinned_provider,
                pinned_model=pinned_model,
                project_id=project_id,
                pinned_think=pinned_think,
                reasoning_level=reasoning_level,
            )

    async def _handle_message_impl(
        self,
        message: str,
        history: list[dict],
        user_settings,
        user_id: str = "local",
        previous_session_context: list[dict] = None,
        pinned_provider: Optional[str] = None,
        pinned_model: Optional[str] = None,
        project_id: Optional[str] = None,
        pinned_think: Optional[bool | str] = None,
        reasoning_level: Optional[str] = None,
    ):
        logger.info("PLANNER handle_message | user=%s | project=%s | msg=%s", user_id, project_id, message[:100])

        # Shared fetches (user-intel summary, suggestions, credential map,
        # profile, recent failures, perf, news, funnel state) — built once in a
        # helper so the WS and messaging paths can't drift on what they read.
        # Path-specific RENDERING (cookie-age warnings, full JSON dumps,
        # previous-session text) stays below, where it legitimately differs.
        common = await self._gather_common_context(user_settings, user_id)
        ctx = common["ctx"]
        suggestions = common["suggestions"]
        cred_status = common["cred_status"]
        user_profile = common["user_profile"]
        failures_text = common["failures_text"]
        perf_insights = common["perf_insights"]
        news_ctx = common["news_ctx"]
        pipeline = common["pipeline"]

        # Format credential status with health warnings (web-only enrichment)
        cred_lines = []
        cred_warnings = []
        for service, info in cred_status.items():
            status_str = "CONFIGURED" if info["configured"] else "NOT SET UP"
            wizard = info.get("setup_wizard", "")
            line = f"  {service}: {status_str}"
            if wizard:
                line += f" (wizard: {wizard})"
            # Add health warnings for cookies
            if info.get("age_days") is not None and info["age_days"] >= 25:
                days = info["age_days"]
                severity = "EXPIRED/CRITICAL" if days >= 30 else "EXPIRING SOON"
                line += f" ⚠️ {severity} ({days} days old)"
                cred_warnings.append(f"⚠️ {service} cookie is {days} days old — offer to refresh it via wizard")
            cred_lines.append(line)

        # Format user profile for the prompt
        profile_text = "No profile yet — this is a new or early user."
        if user_profile:
            profile_text = json.dumps(user_profile, indent=2, ensure_ascii=False)

        # Format previous session context
        prev_session_text = "None — this is the user's first session or a continuing session."
        if previous_session_context:
            prev_lines = []
            for m in previous_session_context:
                role = "User" if m["role"] == "user" else "You"
                prev_lines.append(f"  {role}: {m['content']}")
            prev_session_text = "\n".join(prev_lines)

        # Format performance insights
        perf_text = "No performance data yet — user hasn't uploaded enough videos."
        if perf_insights:
            perf_text = json.dumps(perf_insights, indent=2)

        # Build news memory context
        news_text = "No news scouting history yet."
        if news_ctx and news_ctx.get("total_news_scouts", 0) > 0:
            news_text = json.dumps(news_ctx, indent=2, ensure_ascii=False)

        # Live funnel state — where the user is right now (downloaded-not-generated,
        # generated-not-uploaded, etc.) + the single highest-value next step. This
        # is what makes the planner proactive instead of purely reactive.
        pipeline_text = json.dumps(pipeline, indent=2, ensure_ascii=False) if pipeline else "Unknown."

        system = SYSTEM_PROMPT.format(
            user_context=json.dumps(ctx, indent=2),
            pipeline_state=pipeline_text,
            smart_suggestions=json.dumps(suggestions),
            credential_status="\n".join(cred_lines),
            user_profile=profile_text,
            previous_session=prev_session_text,
            recent_failures=failures_text,
            performance_insights=perf_text,
            news_context=news_text,
        )

        # Build messages list
        messages = list(history)
        messages.append({"role": "user", "content": message})

        # Get AI client — BYOK from .env or per-user settings
        try:
            ai = get_ai_client(
                user_settings,
                pinned_provider=pinned_provider,
                pinned_model=pinned_model,
                require_explicit=True,
            )
        except AIProviderUnselectedError as exc:
            err_msg = str(exc)
            logger.warning("Planner rejected turn: %s", err_msg)
            await ws_manager.send({"type": "chat_error", "error": err_msg}, user_id)
            return
        except Exception:
            direct_actions = self._infer_missing_action(message, "")
            if direct_actions:
                for action_json in direct_actions:
                    try:
                        action = json.loads(action_json.strip())
                        await self._dispatch_action(action, user_settings, user_id)
                    except Exception as err:
                        logger.error("Direct action dispatch failed: %s", err)
                clean_msg = message.strip()
                resp = f"Searching trends for '{clean_msg}' directly..."
                await ws_manager.send({"type": "chat_token", "token": resp}, user_id)
                await ws_manager.send({"type": "chat_done", "full_response": resp}, user_id)
                return

            welcome = (
                "Welcome to 6Clips!\n\n"
                "To get started, run Ollama locally (`http://127.0.0.1:11434`), set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your `.env` file, "
                "or configure your provider in **Settings**."
            )
            await ws_manager.send({"type": "chat_token", "token": welcome}, user_id)
            await ws_manager.send({"type": "chat_done", "full_response": welcome}, user_id)
            return

        full_response = ""
        native_tool_calls_executed = []

        async def _on_status(status_name: str):
            if status_name == "thinking":
                await ws_manager.send({"type": "chat_status", "status": "thinking"}, user_id)
            elif status_name.startswith("calling_tool:"):
                tool_called = status_name.split(":", 1)[1]
                await ws_manager.send({"type": "chat_status", "status": f"Executing tool {tool_called}..."}, user_id)

        timeline_steps = []

        if ai.provider.value == "ollama":
            tool_defs = CapabilityRegistry.to_tool_definitions(user_settings=user_settings)
            active_project_id = project_id
            active_revision = None

            async def _planner_tool_executor(fn_name: str, fn_args: dict) -> dict:
                nonlocal active_project_id, active_revision
                logger.info("PLANNER TOOL EXECUTOR called | tool=%s | args=%s", fn_name, fn_args)
                step_idx = len(timeline_steps) + 1
                step_id = f"step_{step_idx}_{uuid4().hex[:6]}"
                tc_id = f"tc_{uuid4().hex[:8]}"
                start_time = time.perf_counter()

                current_sess_id = CHAT_SESSION.get()
                safe_args = _sanitize_payload(fn_args)
                await ws_manager.send({
                    "type": "tool_event",
                    "step_id": step_id,
                    "tool_call_id": tc_id,
                    "tool_name": fn_name,
                    "state": "executing",
                    "arguments": safe_args,
                    "duration_ms": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": current_sess_id,
                }, user_id)

                await ws_manager.send({"type": "chat_status", "status": f"Running tool {fn_name}..."}, user_id)

                cap = CapabilityRegistry.get(fn_name)
                from backend.motion_capabilities.registry import MotionCapabilitiesRegistry
                motion_spec = MotionCapabilitiesRegistry.get(fn_name)

                if not cap and motion_spec:
                    res = await self.execute_motion_tool(
                        capability_id=fn_name,
                        fn_args=fn_args,
                        user_id=user_id,
                        active_project_id=active_project_id,
                    )
                elif not cap:
                    res = {"error": f"Unauthorized or unknown capability '{fn_name}'"}
                elif fn_name in ("upload_youtube", "upload_tiktok"):
                    res = {"status": "error", "error": f"{fn_name} is not available: platform credentials are not configured in Settings."}
                else:
                    try:
                        # Auto-bind project and revision context
                        if not fn_args.get("project_id") and active_project_id:
                            fn_args["project_id"] = active_project_id
                        if fn_args.get("expected_revision") is None and active_revision is not None and fn_name in ("project_operation", "generate_captions"):
                            fn_args["expected_revision"] = active_revision

                        CapabilityRegistry.validate_input(fn_name, fn_args)

                        if fn_name == "project_operation":
                            from backend.services.project_service import ProjectService
                            try:
                                op_res = await ProjectService.apply_operation(
                                    project_id=fn_args["project_id"],
                                    expected_revision=fn_args["expected_revision"],
                                    operation_type=fn_args["operation_type"],
                                    payload=fn_args.get("payload", {}),
                                    idempotency_key=fn_args.get("idempotency_key"),
                                    author=fn_args.get("author", "agent"),
                                )
                                res = {"status": "success", "result": op_res}
                                if op_res.get("revision"):
                                    active_revision = op_res["revision"]
                            except Exception as ex:
                                res = {"status": "error", "error": str(ex)}

                        elif fn_name == "search_catalog":
                            from backend.services.registry_adapter import RegistryAdapter
                            q = fn_args.get("query") or fn_args.get("search")
                            cat = fn_args.get("category")
                            lim = int(fn_args.get("limit") or 20)
                            items = RegistryAdapter.list_catalog_items(category=cat, search=q, limit=lim)
                            result_items = []
                            for it in items[:10]:
                                result_items.append({
                                    "id": it.get("id"),
                                    "title": it.get("title") or it.get("name"),
                                    "category": it.get("category"),
                                    "description": it.get("description", "")[:120],
                                })
                            res = {"status": "success", "items": result_items, "count": len(items)}

                        else:
                            from backend.services.executor_service import ExecutorService
                            run = None
                            try:
                                run = await ExecutorService.create_run(
                                    objective=f"Planner tool execution: {fn_name}",
                                    project_id=fn_args.get("project_id") or project_id,
                                    user_settings=user_settings,
                                    user_id=user_id,
                                    provider=pinned_provider,
                                    model=pinned_model,
                                )
                                step_res = await ExecutorService.execute_step(
                                    run_id=run.id,
                                    step_name=fn_name,
                                    capability_name=fn_name,
                                    payload=fn_args,
                                    user_id=user_id,
                                    authorized=True,
                                )
                                await ExecutorService.complete_run(run.id, status="completed")
                                step_out = step_res.get("output", {})
                                res = {"status": "success", "output": step_out}
                                if step_out.get("project_id"):
                                    active_project_id = step_out["project_id"]
                                if step_out.get("revision"):
                                    active_revision = step_out["revision"]
                                elif isinstance(step_out.get("project_mutation"), dict) and step_out["project_mutation"].get("revision"):
                                    active_revision = step_out["project_mutation"]["revision"]
                            except Exception as ex:
                                if run:
                                    try:
                                        await ExecutorService.complete_run(run.id, status="failed", error_message=str(ex))
                                    except Exception:
                                        pass
                                res = {"status": "error", "error": str(ex)}
                    except Exception as ex:
                        res = {"error": f"Invalid arguments: {ex}"}

                duration_ms = int((time.perf_counter() - start_time) * 1000)
                is_err = "error" in res or (isinstance(res, dict) and res.get("status") == "error")
                tool_state = "output-error" if is_err else "output-available"
                safe_res = _sanitize_payload(res)

                await ws_manager.send({
                    "type": "tool_event",
                    "step_id": step_id,
                    "tool_call_id": tc_id,
                    "tool_name": fn_name,
                    "state": tool_state,
                    "arguments": safe_args,
                    "result": safe_res,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": current_sess_id,
                }, user_id)

                step_title_map = {
                    "inspect_media": "Inspect Gameplay Media",
                    "create_project": "Create Canonical Project",
                    "suggest_clips": "Analyze & Select Gameplay Highlight",
                    "search_catalog": "Search Motion Graphics Catalog",
                    "project_operation": "Apply Timeline Operation",
                    "generate_captions": "Generate Synchronized Captions",
                    "project_render": "Render Frozen Revision MP4",
                }
                step_title = step_title_map.get(fn_name, f"Execute {fn_name}")

                timeline_steps.append({
                    "id": step_id,
                    "title": step_title,
                    "status": "failed" if is_err else "completed",
                    "duration_ms": duration_ms,
                    "tool_calls": [{
                        "id": tc_id,
                        "name": fn_name,
                        "state": tool_state,
                        "arguments": safe_args,
                        "result": safe_res,
                        "duration_ms": duration_ms,
                    }],
                })

                return res

            async def _stream_token(tok: str):
                await ws_manager.send({"type": "chat_token", "token": tok}, user_id)

            tool_res = await ai.chat_with_tools(
                messages=messages,
                system=system,
                tools=tool_defs,
                tool_executor=_planner_tool_executor,
                max_tokens=1024,
                think=pinned_think,
                reasoning_level=reasoning_level,
                on_status=_on_status,
                on_token=_stream_token,
            )
            full_response = tool_res.get("content", "")
            native_tool_calls_executed = tool_res.get("tool_calls", [])

            for tc in native_tool_calls_executed:
                await ws_manager.send({
                    "type": "capability_executed",
                    "capability": tc.get("name"),
                    "status": "success" if "error" not in tc.get("result", {}) else "failed",
                    "output": tc.get("result"),
                }, user_id)

            # Outcome Orchestration: create_project is an intermediate step, not the end of the Run
            create_proj_call = next((tc for tc in native_tool_calls_executed if tc.get("name") == "create_project"), None)
            if create_proj_call:
                from backend.outcome_orchestration import (
                    OutcomeOrchestrator,
                    OutcomeState,
                    SourceAsset,
                )
                p_res = create_proj_call.get("result", {})
                p_out = p_res.get("output", {}) if isinstance(p_res, dict) else {}
                created_pid = p_out.get("project_id") or active_project_id

                contract, intent = OutcomeOrchestrator.get_or_create_contract_for_turn(
                    message,
                    session_id=current_sess_id,
                    user_id=user_id,
                    project_id=created_pid,
                )

                if not contract.source_assets:
                    candidate_title = None
                    for m in messages:
                        c = m.get("content", "")
                        if "Recommended Editable Source" in c or "Fonte Editável Recomendada" in c:
                            m_match = re.search(r'(?:Recommended Editable Source|Fonte Editável Recomendada):\s*\[?([^\]\n]+)', c)
                            if m_match:
                                candidate_title = m_match.group(1).split("—")[0].split("-")[0].strip()

                    if candidate_title:
                        # Candidate from open YouTube trends (Scenario DISC)
                        # We distinguish candidate from physically accessible / authorized bytes
                        contract.source_assets = [
                            SourceAsset(
                                asset_id=f"yt_cand_{uuid4().hex[:8]}",
                                editorial_role="primary_footage",
                                permitted_uses=["clip_extraction", "motion_review"],
                                acquisition_route="trend_candidate",
                                is_accessible=False,      # Not downloaded locally
                                rights_verified=False,    # Unverified external copyright
                            )
                        ]

                async def _on_orch_event(evt):
                    st = evt.get("step")
                    status = evt.get("status")
                    det = evt.get("detail", "")
                    await ws_manager.send({
                        "type": "outcome_state_transition",
                        "step": st,
                        "status": status,
                        "detail": det,
                        "contract_id": contract.contract_id,
                        "project_id": created_pid,
                    }, user_id)

                prod_report = await OutcomeOrchestrator.execute_batch_outcome(
                    contract,
                    on_event=_on_orch_event,
                )

                # Add real step events to timeline
                for se in prod_report.step_events:
                    timeline_steps.append({
                        "id": f"step_{uuid4().hex[:8]}",
                        "title": se.step_name.replace("_", " ").title(),
                        "status": "completed" if se.status in ("PASS", "COMPLETE", "SUCCEEDED") else ("failed" if se.status in ("BLOCKED", "FAIL") else "running"),
                        "duration_ms": 150,
                        "tool_calls": [],
                    })

                # Reflect truthful state in response
                sm = OutcomeOrchestrator.get_state_machine(contract)
                is_pt = any(w in message.lower() for w in ("vídeo", "clipe", "produzir", "sim", "pode", "projeto", "extrair"))
                if sm.current_state == OutcomeState.BLOCKED and sm.blocker:
                    b_msg = (
                        f"\n\n**Status da Operação:** {sm.current_state.value}\n"
                        f"⚠️ **Bloqueio identificado:** {sm.blocker.precise_reason}\n"
                        f"👉 **Próxima ação:** {sm.blocker.next_action}"
                        if is_pt else
                        f"\n\n**Operational Status:** {sm.current_state.value}\n"
                        f"⚠️ **Blocker identified:** {sm.blocker.precise_reason}\n"
                        f"👉 **Next action:** {sm.blocker.next_action}"
                    )
                    full_response += b_msg
                elif sm.current_state == OutcomeState.READY_FOR_REVIEW:
                    succ_msg = (
                        f"\n\n**Status da Operação:** READY_FOR_REVIEW\n"
                        f"✅ Os {contract.output_count} clipes de 60 segundos foram gerados com sucesso e estão prontos para revisão em `/motion`."
                        if is_pt else
                        f"\n\n**Operational Status:** READY_FOR_REVIEW\n"
                        f"✅ All {contract.output_count} 60-second clips have been verified and are ready for creative review in `/motion`."
                    )
                    full_response += succ_msg
                elif sm.current_state == OutcomeState.PARTIAL:
                    part_msg = (
                        f"\n\n**Status da Operação:** PARTIAL\n"
                        f"⚠️ Entrega parcial: alguns clipes foram gerados com sucesso, mas outros precisam de nova tentativa. Verifique em `/motion`."
                        if is_pt else
                        f"\n\n**Operational Status:** PARTIAL\n"
                        f"⚠️ Partial delivery: verified clips are preserved, while failed clips remain queued for retry. Check `/motion`."
                    )
                    full_response += part_msg
        else:
            async for token in ai.chat_stream(
                messages=messages,
                system=system,
                max_tokens=1024,
                think=pinned_think,
                reasoning_level=reasoning_level,
                on_status=_on_status,
            ):
                full_response += token
                await ws_manager.send({"type": "chat_token", "token": token}, user_id)

        # Signal completion. Strip both <action> and <quick_replies> markers from
        # the user-visible text; the chips ride on chat_done as a structured
        # field so the frontend renders them as buttons, not raw markdown.
        # qr_stripped is the single source of truth for "response minus chip
        # markup" — action parsing + the safety net + clean_response all derive
        # from it, so an <action> substring inside a chip label can't dispatch.
        quick_replies = _parse_quick_replies(full_response)
        qr_stripped = QUICK_REPLIES_PATTERN.sub("", full_response)
        clean_response = ACTION_PATTERN.sub("", qr_stripped).strip()
        await ws_manager.send({
            "type": "chat_done",
            "full_response": clean_response,
            "quick_replies": quick_replies,
            "execution_timeline": timeline_steps if timeline_steps else None,
        }, user_id)

        # Parse and dispatch action blocks.
        # If native tool calls were executed, do NOT double-dispatch legacy action blocks.
        if native_tool_calls_executed:
            actions = []
        else:
            actions = ACTION_PATTERN.findall(qr_stripped)
            logger.debug("PLANNER parsed %d action block(s) from AI response", len(actions))

            # Safety net: if AI talked about scouting but forgot the action block,
            # auto-trigger — UNLESS it deliberately offered quick replies (a
            # clarifying question is an intentional no-action turn; inferring one
            # here would clobber it).
            if not actions and not quick_replies:
                actions = self._infer_missing_action(message, qr_stripped, project_id=project_id)
                if actions:
                    logger.info("PLANNER safety-net inferred action: %s", actions)

        # Collect any dispatch-time follow-ups (clarifying questions, no-op
        # notes) so they're folded into the persisted assistant turn — otherwise
        # the model has no memory it asked and the user's reply arrives context-less.
        followups: list[str] = []
        sink_token = _followup_sink.set(followups)
        try:
            for action_json in actions:
                try:
                    action = json.loads(action_json.strip())
                    await self._dispatch_action(
                        action,
                        user_settings,
                        user_id,
                        pinned_provider=pinned_provider,
                        pinned_model=pinned_model,
                        default_project_id=project_id,
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Malformed action JSON, attempting AI repair: {action_json!r}")
                    try:
                        from backend.core.ai_retry import ai_fix_action
                        repaired = await ai_fix_action(action_json, str(e), user_settings)
                        if repaired:
                            await self._dispatch_action(
                                repaired,
                                user_settings,
                                user_id,
                                pinned_provider=pinned_provider,
                                pinned_model=pinned_model,
                                default_project_id=project_id,
                            )
                        else:
                            logger.error(f"AI could not repair action JSON: {action_json!r}")
                    except Exception as repair_err:
                        logger.error(f"Action repair failed: {repair_err}")
        finally:
            _followup_sink.reset(sink_token)

        if followups:
            joined = "\n".join(followups)
            clean_response = f"{clean_response}\n\n{joined}".strip() if clean_response else joined

        # Record conversation event
        await self.intelligence.record_event("chat_message", {
            "user_message": message[:200],
            "actions_triggered": [json.loads(a) for a in actions if self._is_valid_json(a)],
        }, user_id)

        return PlannerAgentResponse(
            content=clean_response,
            execution_timeline=timeline_steps if timeline_steps else None,
        )

    async def handle_message_text(
        self,
        message: str,
        user_settings,
        user_id: str = "local",
        history: list[dict] | None = None,
    ) -> str:
        """
        Non-streaming sibling of handle_message() for messaging channels
        (Telegram, WhatsApp, Discord, Slack) that can't push WebSocket tokens.
        Builds the same system prompt and dispatches the same <action> blocks,
        but returns the full response string with action blocks stripped.

        `history` is the recent phone conversation (MessagingManager.history_for),
        notifications included — without it a bare "yes" or "generate" in reply
        to the bot's own question reaches the model with no context.
        """
        from backend.llm_trace import (
            inference_authorization_context,
            TRIGGER_EXPLICIT_CHAT_SUBMIT,
        )
        async with inference_authorization_context(
            trigger=TRIGGER_EXPLICIT_CHAT_SUBMIT,
            user_id=user_id,
        ):
            return await self._handle_message_text_impl(
                message=message,
                user_settings=user_settings,
                user_id=user_id,
                history=history,
            )

    async def _handle_message_text_impl(
        self,
        message: str,
        user_settings,
        user_id: str = "local",
        history: list[dict] | None = None,
    ) -> str:
        logger.info("PLANNER handle_message_text | user=%s | msg=%s", user_id, message[:100])

        # Same shared fetches as handle_message (via the common helper so the
        # two surfaces can't drift). Messaging then renders the lean variants of
        # the divergent blocks (no cookie-age warnings, one-line-free profile,
        # un-indented funnel state).
        common = await self._gather_common_context(user_settings, user_id)
        ctx = common["ctx"]
        suggestions = common["suggestions"]
        cred_status = common["cred_status"]
        user_profile = common["user_profile"]
        failures_text = common["failures_text"]
        perf_insights = common["perf_insights"]
        news_ctx = common["news_ctx"]
        pipeline = common["pipeline"]

        cred_lines = []
        for service, info in cred_status.items():
            status_str = "CONFIGURED" if info["configured"] else "NOT SET UP"
            wizard = info.get("setup_wizard", "")
            line = f"  {service}: {status_str}"
            if wizard:
                line += f" (wizard: {wizard})"
            cred_lines.append(line)

        profile_text = (
            json.dumps(user_profile, indent=2, ensure_ascii=False)
            if user_profile else "No profile yet."
        )

        perf_text = json.dumps(perf_insights, indent=2) if perf_insights else "No performance data yet."

        news_text = (
            json.dumps(news_ctx, indent=2, ensure_ascii=False)
            if news_ctx and news_ctx.get("total_news_scouts", 0) > 0
            else "No news scouting history yet."
        )

        # Live funnel state — cheap (indexed counts) and high-value even for
        # messaging: it's how the bot proactively nudges the next step.
        pipeline_text = json.dumps(pipeline, ensure_ascii=False) if pipeline else "Unknown."

        system = SYSTEM_PROMPT.format(
            user_context=json.dumps(ctx, indent=2),
            pipeline_state=pipeline_text,
            smart_suggestions=json.dumps(suggestions),
            credential_status="\n".join(cred_lines),
            user_profile=profile_text,
            previous_session="N/A — inbound from messaging channel.",
            recent_failures=failures_text,
            performance_insights=perf_text,
            news_context=news_text,
        )

        try:
            ai = get_ai_client(user_settings)
        except Exception:
            return (
                "AI provider is not configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
                "in your .env, or configure your key in Settings."
            )

        try:
            full_response = await ai.chat(
                messages=_messaging_turns(history, message),
                system=system,
                max_tokens=1024,
            )
        except Exception as e:
            logger.exception("PLANNER text chat failed: %s", e)
            return "Sorry — I couldn't reach the AI backend just now. Try again in a moment."

        # Strip <quick_replies> markup too — messaging channels don't render
        # chips, so the block would otherwise leak into the plain-text reply.
        quick_replies = _parse_quick_replies(full_response)
        qr_stripped = QUICK_REPLIES_PATTERN.sub("", full_response)
        clean_response = ACTION_PATTERN.sub("", qr_stripped).strip()
        actions = ACTION_PATTERN.findall(qr_stripped)
        # Mirror the web path: a deliberate clarifying-question turn (chips, no
        # action block) must NOT get a premature action keyword-inferred.
        if not actions and not quick_replies:
            actions = self._infer_missing_action(message, qr_stripped)

        # Capture dispatch-time follow-ups via the sink. There's no live WS on
        # the messaging path, so the follow-up text is appended to the returned
        # reply (that's the whole point of the sink here).
        followups: list[str] = []
        sink_token = _followup_sink.set(followups)
        try:
            for action_json in actions:
                try:
                    action = json.loads(action_json.strip())
                    await self._dispatch_action(action, user_settings, user_id)
                except json.JSONDecodeError:
                    logger.warning("Malformed action JSON in text path: %r", action_json)
                except Exception as e:
                    logger.exception("Action dispatch failed in text path: %s", e)
        finally:
            _followup_sink.reset(sink_token)

        if followups:
            joined = "\n".join(followups)
            clean_response = f"{clean_response}\n\n{joined}".strip() if clean_response else joined

        await self.intelligence.record_event(
            "chat_message",
            {
                "user_message": message[:200],
                "source": "messaging",
                "actions_triggered": [json.loads(a) for a in actions if self._is_valid_json(a)],
            },
            user_id,
        )

        return clean_response or "Working on it. ✅"

    async def _dispatch_action(
        self,
        action: dict,
        user_settings,
        user_id: str,
        pinned_provider: Optional[str] = None,
        pinned_model: Optional[str] = None,
        default_project_id: Optional[str] = None,
    ):
        action_type = action.get("type")
        if default_project_id and "project_id" not in action:
            action["project_id"] = default_project_id
        logger.info("DISPATCH action=%s | user=%s | payload=%s", action_type, user_id, json.dumps(action, ensure_ascii=False)[:200])

        if action_type in ("start_trend", "start_trends", "start_scout"):
            await self._check_and_start_trend(action, user_settings, user_id)

        elif action_type == "analyze_channel":
            await self._analyze_channel(action, user_id)

        elif action_type == "download_channel_videos":
            await self._download_channel_videos(action, user_id)

        elif action_type == "download_url":
            await self._download_url(action, user_settings, user_id)

        elif action_type == "start_wizard":
            wizard_id = action.get("wizard_id")
            if wizard_id in WIZARDS:
                await ws_manager.send({
                    "type": "wizard_start",
                    "wizard_id": wizard_id,
                    "wizard": WIZARDS[wizard_id],
                }, user_id)

        elif action_type == "start_download":
            trend_result_ids = [
                i for i in (action.get("trend_result_ids") or action.get("scout_result_ids") or [])
                if i
            ]
            if trend_result_ids:
                from backend.agents.job_helper import create_job
                from backend.core.task_runner import run_download, dispatch
                job = await create_job("download", user_id, {"trend_result_ids": trend_result_ids, "scout_result_ids": trend_result_ids})
                dispatch(run_download(job_id=job.id, trend_result_ids=trend_result_ids, scout_result_ids=trend_result_ids, user_id=user_id))
                await ws_manager.send({
                    "type": "job_started",
                    "job_id": job.id,
                    "job_type": "download",
                    "message": f"Downloading {len(trend_result_ids)} videos...",
                }, user_id)

        elif action_type == "start_generate":
            downloaded_video_id = action.get("downloaded_video_id")
            if downloaded_video_id:
                from backend.agents.job_helper import create_job
                from backend.core.task_runner import run_generate, dispatch
                job = await create_job("generate", user_id, {"downloaded_video_id": downloaded_video_id})
                dispatch(run_generate(
                    job_id=job.id, downloaded_video_id=downloaded_video_id, user_id=user_id,
                ))

        elif action_type == "start_upload":
            generated_video_id = action.get("generated_video_id")
            platforms = action.get("platforms", ["youtube"])
            if generated_video_id:
                from backend.agents.job_helper import create_job
                from backend.core.task_runner import run_upload, dispatch
                job = await create_job("upload", user_id, {"generated_video_id": generated_video_id})
                dispatch(run_upload(
                    job_id=job.id, generated_video_id=generated_video_id, platforms=platforms, user_id=user_id,
                ))

        elif action_type in ("show_trend_results", "show_trends_results", "show_scout_results"):
            await self._show_trend_results(action, user_id)

        elif action_type == "show_downloaded":
            await self._show_downloaded(user_id)

        elif action_type == "show_videos":
            await self._show_videos(user_id)

        elif action_type == "content_calendar":
            try:
                days = int(action.get("days", 7))
            except (TypeError, ValueError):
                days = 7
            days = max(1, min(days, 90))
            calendar = await self.intelligence.generate_content_calendar(user_id, days)
            if calendar:
                await ws_manager.send({
                    "type": "content_calendar",
                    "calendar": calendar,
                }, user_id)
            else:
                await self._followup(
                    user_id,
                    "I need more data to generate a personalized content calendar. Try uploading a few videos first so I can learn what works for your audience.",
                )

        elif action_type == "start_news_scout":
            await self._start_news_scout(action, user_id)

        elif action_type == "analyze_url":
            await self._analyze_article_url(action, user_id)

        elif action_type == "save_news_to_library":
            await self._save_news_to_library(action, user_id)

        elif action_type in ("create_original_brief", "original_creation_brief", "create_creator_brief"):
            await self._create_original_brief(action, user_id)

        elif action_type in ("render_original_video", "render_original_brief"):
            await self._render_original_video(action, user_id)

        elif action_type in ("extract_reference_style", "analyze_reference_style"):
            await self._extract_reference_style(action, user_id)

        elif action_type == "project_operation":
            await self._dispatch_project_operation(
                action,
                user_id,
                pinned_provider=pinned_provider,
                pinned_model=pinned_model,
                default_project_id=default_project_id,
            )

        elif CapabilityRegistry.get(action_type):
            await self._dispatch_capability(
                action_type,
                action,
                user_settings,
                user_id,
                pinned_provider=pinned_provider,
                pinned_model=pinned_model,
            )

        elif action_type in ("motion_capability", "dispatch_motion_capability"):
            cap_id = action.get("capability_id") or action.get("capability")
            from backend.motion_capabilities.dispatcher import MotionCapabilityDispatcher
            from backend.services.project_service import ProjectService
            proj_id = action.get("project_id") or default_project_id
            p_doc = None
            p_obj = None
            if proj_id:
                try:
                    p_obj = await ProjectService.verify_project_ownership(proj_id, user_id=user_id)
                    p_doc = json.loads(p_obj.document_json)
                except Exception as pex:
                    logger.warning("Project lookup for motion_capability failed: %s", pex)
            res = await MotionCapabilityDispatcher.dispatch(
                capability_id=cap_id,
                input_path=action.get("input_path") or action.get("video_path"),
                params=action.get("params") or action,
                project_doc=p_doc,
            )
            if p_obj and res.project_mutation:
                try:
                    exp_r = action.get("expected_revision")
                    if exp_r is not None and exp_r != p_obj.revision:
                        logger.warning("Revision conflict for motion capability %s: expected %d, got %d", cap_id, exp_r, p_obj.revision)
                    else:
                        await ProjectService.apply_operation(
                            project_id=p_obj.id,
                            expected_revision=p_obj.revision,
                            operation_type=f"motion_{cap_id}",
                            payload=res.project_mutation,
                            idempotency_key=action.get("idempotency_key"),
                            author="agent",
                        )
                except Exception as aex:
                    logger.error("Failed applying motion capability mutation to project %s: %s", proj_id, aex)
            await ws_manager.send({
                "type": "motion_capability_executed",
                "capability": cap_id,
                "status": "success" if res.status == "SUCCESS" else "failed",
                "message": res.message,
                "output_path": str(res.output_path) if res.output_path else None,
            }, user_id)

        else:
            from backend.core import plugins
            plugin_handler = plugins.get_planner_action(action_type)
            if plugin_handler:
                try:
                    import inspect
                    res = plugin_handler(action, user_settings, user_id)
                    if inspect.isawaitable(res):
                        await res
                except Exception as err:
                    logger.error("Plugin action %s failed: %s", action_type, err, exc_info=True)
            else:
                logger.warning("Unrecognized planner action: %s", action_type)

    async def _dispatch_capability(
        self,
        capability_name: str,
        action: dict,
        user_settings,
        user_id: str,
        pinned_provider: Optional[str] = None,
        pinned_model: Optional[str] = None,
    ):
        from backend.services.executor_service import ExecutorService
        project_id = action.get("project_id")
        objective = action.get("objective") or f"Planner execution of {capability_name}"
        run = None
        try:
            run = await ExecutorService.create_run(
                objective=objective,
                project_id=project_id,
                user_settings=user_settings,
                user_id=user_id,
                provider=pinned_provider,
                model=pinned_model,
            )
            step_res = await ExecutorService.execute_step(
                run_id=run.id,
                step_name=capability_name,
                capability_name=capability_name,
                payload=action,
                user_id=user_id,
                authorized=True,
            )
            await ExecutorService.complete_run(run.id, status="completed")
            await ws_manager.send({
                "type": "capability_executed",
                "capability": capability_name,
                "run_id": run.id,
                "step_id": step_res["step_id"],
                "status": "success",
                "output": step_res["output"],
            }, user_id)
        except Exception as e:
            logger.error("Planner capability %s execution failed: %s", capability_name, e)
            if run:
                try:
                    await ExecutorService.complete_run(run.id, status="failed", error_message=str(e))
                except Exception:
                    pass
            await ws_manager.send({
                "type": "capability_failed",
                "capability": capability_name,
                "error": str(e),
            }, user_id)

    async def _dispatch_project_operation(
        self,
        action: dict,
        user_id: str,
        pinned_provider: Optional[str] = None,
        pinned_model: Optional[str] = None,
        default_project_id: Optional[str] = None,
    ):
        from backend.services.executor_service import ExecutorService
        from backend.services.project_service import ProjectService
        from backend.core.exceptions import RevisionConflictError
        project_id = action.get("project_id") or default_project_id
        if not project_id:
            try:
                projects = await ProjectService.list_projects(user_id=user_id)
                if projects:
                    project_id = projects[0].id
                else:
                    new_p = await ProjectService.create_project("Default Project", user_id=user_id)
                    project_id = new_p.id
            except Exception as pe:
                logger.warning("Could not auto-resolve project for operation: %s", pe)
                return

        action["project_id"] = project_id
        operation_type = action.get("operation_type")
        payload = action.get("payload", {})
        if not operation_type:
            return

        expected_revision = action.get("expected_revision")
        if expected_revision is None or expected_revision < 1:
            try:
                p_current = await ProjectService.get_project(project_id)
                expected_revision = p_current.revision
            except Exception:
                expected_revision = 1

        run = None
        try:
            run = await ExecutorService.create_run(
                objective=f"Apply project operation '{operation_type}' on project {project_id}",
                project_id=project_id,
                input_revision=expected_revision,
                user_id=user_id,
                provider=pinned_provider,
                model=pinned_model,
            )
            step_res = await ExecutorService.execute_step(
                run_id=run.id,
                step_name=f"project_op_{operation_type}",
                capability_name="project_operation",
                payload={
                    "project_id": project_id,
                    "expected_revision": expected_revision,
                    "operation_type": operation_type,
                    "payload": payload,
                    "idempotency_key": action.get("idempotency_key"),
                    "author": "agent",
                },
                user_id=user_id,
                authorized=True,
            )
            res = step_res["output"]
            await ExecutorService.complete_run(run.id, status="completed")
            await ws_manager.send({
                "type": "project_updated",
                "project_id": project_id,
                "revision": res["revision"],
                "operation_type": operation_type,
                "document": res.get("document"),
                "summary": res.get("change_summary", operation_type),
                "run_id": run.id,
                "step_id": step_res["step_id"],
            }, user_id)
        except RevisionConflictError:
            # OBSERVE CONFLICT -> REPLAN WITH LATEST REVISION
            try:
                p_fresh = await ProjectService.get_project(project_id)
                logger.info("Conflict on %s (expected %s): replanning against revision %s", operation_type, expected_revision, p_fresh.revision)
                step_res = await ExecutorService.execute_step(
                    run_id=run.id,
                    step_name=f"project_op_{operation_type}_replan",
                    capability_name="project_operation",
                    payload={
                        "project_id": project_id,
                        "expected_revision": p_fresh.revision,
                        "operation_type": operation_type,
                        "payload": payload,
                        "idempotency_key": action.get("idempotency_key"),
                        "author": "agent",
                    },
                    user_id=user_id,
                    authorized=True,
                )
                res = step_res["output"]
                await ExecutorService.complete_run(run.id, status="completed", context_data={"replanned": True, "conflict_revision": expected_revision})
                await ws_manager.send({
                    "type": "project_updated",
                    "project_id": project_id,
                    "revision": res["revision"],
                    "operation_type": operation_type,
                    "document": res.get("document"),
                    "summary": f"{operation_type} (auto-replanned after conflict)",
                    "run_id": run.id,
                    "step_id": step_res["step_id"],
                }, user_id)
            except Exception as e2:
                logger.error("Planner project operation retry failed: %s", e2)
                if run:
                    await ExecutorService.complete_run(run.id, status="failed", error_message=str(e2))
                await ws_manager.send({
                    "type": "project_error",
                    "project_id": project_id,
                    "error": str(e2),
                }, user_id)
        except Exception as e:
            logger.error("Planner project operation failed: %s", e)
            if run:
                await ExecutorService.complete_run(run.id, status="failed", error_message=str(e))
            await ws_manager.send({
                "type": "project_error",
                "project_id": project_id,
                "error": str(e),
            }, user_id)

    async def execute_plan(
        self,
        objective: str,
        plan_steps: list[dict],
        project_id: Optional[str] = None,
        user_settings=None,
        user_id: str = "local",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_replans: int = 3,
    ) -> dict:
        """
        Execute an agent plan with the full OaaS loop:
        Observe -> Verify -> Replan.
        - Run is created with pinned provider/model
        - Steps are executed through CapabilityRegistry and ExecutorService
        - Verification evidence is observed after each step
        - When a step fails (or has revision conflict), the agent replans and retries
        - Concludes with final status and full execution trace
        """
        from backend.services.executor_service import ExecutorService
        from backend.services.project_service import ProjectService
        from backend.core.exceptions import RevisionConflictError

        run = await ExecutorService.create_run(
            objective=objective,
            project_id=project_id,
            user_settings=user_settings,
            user_id=user_id,
            provider=provider,
            model=model,
        )

        executed_steps = []
        replans_count = 0
        step_idx = 0
        steps_queue = list(plan_steps)

        while steps_queue:
            step_spec = steps_queue.pop(0)
            step_idx += 1
            cap_name = step_spec.get("capability") or step_spec.get("type")
            step_name = step_spec.get("name") or f"Step {step_idx}: {cap_name}"
            payload = dict(step_spec.get("payload") or step_spec)

            if project_id and "project_id" not in payload:
                payload["project_id"] = project_id

            if project_id and cap_name in ("project_operation", "set_bench_ranges"):
                p_current = await ProjectService.get_project(project_id)
                if "expected_revision" not in payload:
                    payload["expected_revision"] = p_current.revision

            step_success = False
            step_attempts = 0

            while not step_success and step_attempts <= max_replans:
                step_attempts += 1
                try:
                    res = await ExecutorService.execute_step(
                        run_id=run.id,
                        step_name=step_name,
                        capability_name=cap_name,
                        payload=payload,
                        user_id=user_id,
                        authorized=True,
                    )
                    verif = res.get("verification", {})
                    # OBSERVE & VERIFY
                    if verif.get("ok"):
                        step_success = True
                        executed_steps.append(res)
                        await ws_manager.send({
                            "type": "agent_step_progress",
                            "run_id": run.id,
                            "step_id": res["step_id"],
                            "status": "verified",
                            "step_name": step_name,
                            "capability": cap_name,
                            "output": res.get("output"),
                        }, user_id)
                    else:
                        logger.warning("Step %s verifier failed: %s; triggering replan", step_name, verif)
                        replans_count += 1
                        if step_attempts <= max_replans:
                            await ws_manager.send({
                                "type": "agent_plan_replan",
                                "run_id": run.id,
                                "step_name": step_name,
                                "reason": "verification_failed",
                                "details": verif,
                            }, user_id)
                        else:
                            raise RuntimeError(f"Step {step_name} verifier failed after retries: {verif}")

                except RevisionConflictError as rce:
                    logger.info("Revision conflict on %s: %s; replanning with latest revision", step_name, rce)
                    replans_count += 1
                    # REPLAN ON REVISION CONFLICT
                    if project_id:
                        p_latest = await ProjectService.get_project(project_id)
                        payload["expected_revision"] = p_latest.revision
                        await ws_manager.send({
                            "type": "agent_plan_replan",
                            "run_id": run.id,
                            "step_name": step_name,
                            "reason": "revision_conflict",
                            "new_expected_revision": p_latest.revision,
                        }, user_id)
                    else:
                        raise

                except Exception as err:
                    logger.error("Step execution error on %s: %s", step_name, err)
                    if step_attempts > max_replans:
                        await ExecutorService.complete_run(
                            run.id,
                            status="failed",
                            error_message=f"Failed at {step_name}: {err}",
                            context_data={"replans": replans_count, "failed_step": step_name},
                        )
                        raise
                    replans_count += 1

        await ExecutorService.complete_run(
            run.id,
            status="completed",
            context_data={"replans": replans_count, "steps_count": len(executed_steps)},
        )
        await ws_manager.send({
            "type": "agent_run_completed",
            "run_id": run.id,
            "objective": objective,
            "replans": replans_count,
            "steps": len(executed_steps),
        }, user_id)

        return {
            "run_id": run.id,
            "status": "completed",
            "replans": replans_count,
            "steps": executed_steps,
        }


    async def _start_news_scout(self, action: dict, user_id: str):
        """Start a news scout job."""
        query = action.get("query", "")
        if not query:
            return
        expanded_queries = action.get("expanded_queries", [])
        sources = action.get("sources")  # None = all 12 sources (default in scraper)

        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_news_scout, dispatch

        job = await create_job("news_scout", user_id, {
            "query": query,
            "expanded_queries": expanded_queries,
            "sources": sources,
        })
        dispatch(run_news_scout(
            job_id=job.id, query=query,
            expanded_queries=expanded_queries or None,
            sources=sources or None,
            user_id=user_id,
        ))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "news_scout",
            "message": f"Researching '{query}' across {', '.join(sources) if sources else 'all 12 news sources'}...",
        }, user_id)
        await self.intelligence.record_event("news_scouted", {
            "query": query,
            "expanded_queries": expanded_queries,
            "sources": sources,
        }, user_id)

    async def _analyze_article_url(self, action: dict, user_id: str):
        """Analyze a single article URL."""
        url = action.get("url", "").strip()
        if not url:
            return

        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_news_scout, dispatch

        job = await create_job("news_scout", user_id, {"direct_url": url})
        dispatch(run_news_scout(
            job_id=job.id, query="direct URL analysis",
            direct_url=url, user_id=user_id,
        ))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "news_scout",
            "message": "Analyzing article...",
        }, user_id)

    async def _save_news_to_library(self, action: dict, user_id: str):
        """Save selected news articles to Library."""
        article_ids = action.get("article_ids", [])
        if not article_ids:
            return

        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_news_save, dispatch

        job = await create_job("news_save", user_id, {"article_ids": article_ids})
        dispatch(run_news_save(job_id=job.id, article_ids=article_ids, user_id=user_id))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "news_save",
            "message": f"Saving {len(article_ids)} article{'s' if len(article_ids) != 1 else ''} to Library...",
        }, user_id)
        await self.intelligence.record_event("news_saved", {
            "article_ids": article_ids,
            "count": len(article_ids),
        }, user_id)

    async def _show_trend_results(self, action: dict, user_id: str):
        """Fetch recent trend results from DB and send them over WS."""
        from backend.database import AsyncSessionLocal
        from backend.models.trends_result import TrendsResult as TrendResult
        from sqlalchemy import select

        job_id = action.get("job_id")
        limit = action.get("limit", 50)

        async with AsyncSessionLocal() as db:
            query = (
                select(TrendResult)
                .where(TrendResult.user_id == user_id)
                .order_by(TrendResult.created_at.desc())
                .limit(limit)
            )
            if job_id:
                query = query.where(TrendResult.job_id == job_id)
            result = await db.execute(query)
            results = result.scalars().all()

        if not results:
            await self._followup(user_id, "No trend results found yet. Try searching for trends first!")
            return

        # Group by platform and send
        from backend.trends_research.ranking import classify_source_suitability
        platforms = {}
        for r in results:
            suit = classify_source_suitability(r.duration_seconds)
            platforms.setdefault(r.platform, []).append({
                "id": r.id,
                "platform": r.platform,
                "video_id": r.video_id,
                "title": r.title,
                "author": r.author,
                "author_url": r.author_url,
                "views": r.views,
                "likes": r.likes,
                "comments": r.comments,
                "duration_seconds": r.duration_seconds,
                "upload_date": r.upload_date.isoformat() if r.upload_date else None,
                "virality_score": r.virality_score,
                "thumbnail_url": r.thumbnail_url,
                "video_url": r.video_url,
                "embed_url": r.embed_url,
                "editorial_role": suit.trend_role.value,
                "role_label": suit.role_label,
                "is_editable_source": suit.is_editable_source,
                "is_reference": suit.is_reference,
                "permitted_use": "reference_only",
                "bytes_availability": "available_local" if getattr(r, "is_downloaded", False) else "not_fetched",
                "highlight_quality": {
                    "status": "NOT_ASSESSED",
                    "assessed": False,
                    "score": None,
                    "reason": "Highlight quality requires media ingestion and transcript scoring; not inferable from search metadata.",
                },
            })

        for platform, items in platforms.items():
            await ws_manager.send({
                "type": "trend_results",
                "job_id": job_id or "",
                "platform": platform,
                "total": len(items),
                "results": items,
            }, user_id)

    _show_scout_results = _show_trend_results

    async def _create_original_brief(self, action: dict, user_id: str):
        """Create a grounded original video composition brief with teleprompter script and shot list."""
        topic = action.get("topic") or action.get("niche") or "Trending Gaming Update"
        creator_context = action.get("creator_context")
        target_duration = int(action.get("target_duration_sec") or action.get("duration") or 60)
        aspect_ratio = action.get("aspect_ratio") or "9:16"
        language = action.get("language") or ("pt" if any(w in str(topic).lower() for w in ["jogo", "atualiz", "video", "noticia", "fortnite"]) else "en")
        voice_asset_id = action.get("voice_asset_id")
        facecam_asset_id = action.get("facecam_asset_id")
        allow_procedural_tts = bool(action.get("allow_procedural_tts", False))

        from backend.original_creation.workflow import OriginalCreatorWorkflow
        spec = OriginalCreatorWorkflow.create_brief(
            topic=topic,
            creator_context=creator_context,
            target_duration_sec=target_duration,
            aspect_ratio=aspect_ratio,
            language=language,
            creator_voice_asset_id=voice_asset_id,
            creator_facecam_asset_id=facecam_asset_id,
            allow_procedural_tts=allow_procedural_tts,
        )

        await ws_manager.send({
            "type": "original_brief_created",
            "spec": spec.model_dump(),
        }, user_id)

        if spec.status == "WAITING_FOR_INPUT":
            msg = (
                f"Original brief for '{topic}' created with {len(spec.evidence_ledger.entries)} grounded claim(s) "
                f"and clean teleprompter script ({spec.spoken_script.word_count} words). "
                f"Status: WAITING_FOR_INPUT. Please upload or record your own voice narration track to proceed to timeline composition."
            ) if language != "pt" else (
                f"Briefing original para '{topic}' criado com {len(spec.evidence_ledger.entries)} fato(s) verificados "
                f"e roteiro limpo para teleprompter ({spec.spoken_script.word_count} palavras). "
                f"Status: WAITING_FOR_INPUT. Por favor, envie ou grave sua própria faixa de voz para prosseguir para a composição."
            )
        else:
            msg = (
                f"Original brief for '{topic}' created and ready for timeline composition."
            ) if language != "pt" else (
                f"Briefing original para '{topic}' criado e pronto para composição na timeline."
            )

        await self._followup(user_id, msg)
        try:
            await self.intelligence.record_event("original_brief_created", {"topic": topic, "spec_id": spec.spec_id}, user_id)
        except Exception as ev_err:
            logger.debug("Failed recording original_brief_created event: %s", ev_err)
        return spec

    async def _render_original_video(self, action: dict, user_id: str):
        """Render original video from specification, validating voice consent and reporting truthful review URL."""
        from pathlib import Path
        from backend.original_creation.models import OriginalCompositionSpec, ProductionV1Adapter
        from backend.original_creation.workflow import OriginalCreatorWorkflow

        raw_spec = action.get("spec")
        if not raw_spec:
            await ws_manager.send({"type": "original_render_error", "error": "Missing 'spec' payload"}, user_id)
            return None

        try:
            spec_obj = OriginalCompositionSpec.model_validate(raw_spec)
        except Exception as e:
            await ws_manager.send({"type": "original_render_error", "error": f"Invalid spec: {e}"}, user_id)
            return None

        custom_voice = Path(action["custom_voice_path"]) if action.get("custom_voice_path") else None
        rendered = await OriginalCreatorWorkflow.render_spec(spec_obj, custom_voice_path=custom_voice)

        if rendered.rendered_result:
            from backend.media_pipeline.producer_adapter import get_media_producer
            producer = get_media_producer()
            art_id = f"art-{rendered.spec_id}"
            width = rendered.rendered_result.probe_stats.width if rendered.rendered_result.probe_stats else 1080
            height = rendered.rendered_result.probe_stats.height if rendered.rendered_result.probe_stats else 1920
            producer.register_completed_artifact(
                job_id=rendered.spec_id,
                output_id=f"out-{rendered.spec_id}",
                artifact_id=art_id,
                file_path=rendered.rendered_result.video_path,
                duration_seconds=rendered.rendered_result.duration_seconds,
                width=width,
                height=height,
                user_id=user_id,
                project_id=action.get("project_id"),
            )
            review_url = f"/motion?jobId={rendered.spec_id}&mode=review"
            canonical_payload = ProductionV1Adapter.to_canonical_project_payload(rendered)
            await ws_manager.send({
                "type": "original_video_rendered",
                "spec_id": rendered.spec_id,
                "job_id": rendered.spec_id,
                "status": rendered.status.value,
                "video_path": str(rendered.rendered_result.video_path),
                "review_url": review_url,
                "duration_seconds": rendered.rendered_result.duration_seconds,
                "canonical_project_payload": canonical_payload,
            }, user_id)
            await self._followup(
                user_id,
                f"Original video successfully rendered ({rendered.rendered_result.duration_seconds:.1f}s)! "
                f"Ready for review at {review_url}."
            )
        else:
            await ws_manager.send({
                "type": "original_render_blocked",
                "spec_id": rendered.spec_id,
                "status": rendered.status.value,
                "status_reason": rendered.status_reason,
            }, user_id)
            await self._followup(user_id, f"Rendering status: {rendered.status.value}. {rendered.status_reason}")
        return rendered

    async def _extract_reference_style(self, action: dict, user_id: str):
        """Extract observable visual features and style hypotheses from an authorized reference video."""
        ref_id = action.get("reference_id") or action.get("video_id") or "ref-1"
        title = action.get("title") or "Reference Video"
        duration = action.get("duration_seconds")
        channel = action.get("channel") or action.get("author") or "Unknown"

        from backend.trends_research.reference_extractor import analyze_reference_style
        hypo = analyze_reference_style(
            reference_id=ref_id,
            title=title,
            duration_seconds=duration,
            channel_or_author=channel,
        )

        await ws_manager.send({
            "type": "reference_style_extracted",
            "hypothesis": {
                "hypothesis_id": hypo.hypothesis_id,
                "reference_title": hypo.reference_title,
                "hook_archetype": hypo.narrative_hook_archetype,
                "pacing_strategy": hypo.pacing_strategy,
                "music_vibe": hypo.music_vibe_suggestion,
                "rendering_status": hypo.rendering_status,
                "rights_notice": hypo.fair_use_and_rights_notice,
            },
        }, user_id)

        await self._followup(
            user_id,
            f"Extracted creative style hypothesis from reference '{title}': "
            f"{hypo.narrative_hook_archetype} Pacing: {hypo.pacing_strategy} "
            f"(Status: analysis complete, physical rendering pending authorized assets)."
        )
        return hypo

    async def _show_downloaded(self, user_id: str):
        """Fetch downloaded videos from DB and send them as a rich list in chat."""
        from backend.database import AsyncSessionLocal
        from backend.models.downloaded_video import DownloadedVideo
        from backend.models.trends_result import TrendsResult as ScoutResult
        from sqlalchemy import select, outerjoin
        import json as _json

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DownloadedVideo)
                .where(DownloadedVideo.user_id == user_id)
                .order_by(DownloadedVideo.created_at.desc())
                .limit(20)
            )
            downloads = result.scalars().all()

            # Fetch associated scout results for titles/thumbnails
            scout_ids = [d.scout_result_id for d in downloads if d.scout_result_id]
            scouts_map = {}
            if scout_ids:
                sr = await db.execute(
                    select(ScoutResult).where(ScoutResult.id.in_(scout_ids))
                )
                for s in sr.scalars().all():
                    scouts_map[s.id] = s

        if not downloads:
            await self._followup(
                user_id,
                "No downloaded videos yet. Try scouting a niche and downloading some videos first!",
            )
            return

        items = []
        for d in downloads:
            scout = scouts_map.get(d.scout_result_id)
            insights = _json.loads(d.insights_json) if d.insights_json else {}
            items.append({
                "id": d.id,
                "title": (scout.title if scout else None) or d.video_path or "Untitled",
                "thumbnail_url": scout.thumbnail_url if scout else None,
                "platform": scout.platform if scout else None,
                "views": scout.views if scout else None,
                "duration_seconds": d.duration_seconds,
                "transcript_preview": (d.transcript or "")[:150],
                "has_insights": bool(d.insights_json),
                "suggested_angle": insights.get("suggested_angle", ""),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            })

        await ws_manager.send({
            "type": "downloaded_list",
            "total": len(items),
            "videos": items,
        }, user_id)

    async def _show_videos(self, user_id: str):
        """Send a nudge to navigate to videos page."""
        await ws_manager.send({
            "type": "action",
            "action": {"type": "navigate", "path": "/videos"},
        }, user_id)

    async def _analyze_channel(self, action: dict, user_id: str):
        """Lightweight channel analysis — fetch metadata + video list without downloading."""
        url = action.get("url", "").strip()
        if not url:
            return

        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_analyze_channel, dispatch

        job = await create_job("analyze", user_id, {"url": url, "type": "channel_analysis"})
        dispatch(run_analyze_channel(job_id=job.id, url=url, user_id=user_id))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "analyze",
            "message": f"Analyzing channel...",
        }, user_id)

    async def _download_channel_videos(self, action: dict, user_id: str):
        """Download top N videos from a channel after user has seen the analysis."""
        url = action.get("url", "").strip()
        max_videos = action.get("max_videos", 5)
        if not url:
            return

        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_download_url, dispatch

        job = await create_job("download", user_id, {"url": url, "channel_download": True, "max_videos": max_videos})
        dispatch(run_download_url(job_id=job.id, url=url, title="", user_id=user_id))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "download",
            "message": f"Downloading top {max_videos} videos from channel...",
        }, user_id)

    async def _download_url(self, action: dict, _user_settings, user_id: str):
        """Download a video directly from a URL provided by the user."""
        url = action.get("url", "").strip()
        title = action.get("title", "")

        if not url:
            return

        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_download_url, dispatch

        job = await create_job("download", user_id, {
            "url": url,
            "title": title,
            "direct_url": True,
        })
        dispatch(run_download_url(job_id=job.id, url=url, title=title, user_id=user_id))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "download",
            "message": f"Downloading video from URL...",
        }, user_id)

    # Platforms that need API credentials — keys come from .env (BYOK).
    _CREDENTIAL_PLATFORMS = {
        "youtube": {
            "check": lambda us: True,
        },
        "tiktok": {
            "check": lambda us: (
                bool(settings.TIKHUB_API_KEY)
                or (us and us.tiktok_cookie_encrypted)
            ),
        },
        "douyin": {
            "check": lambda us: (
                bool(settings.TIKHUB_API_KEY)
                or (us and us.douyin_cookie_encrypted)
            ),
        },
    }

    async def _check_and_start_trend(self, action: dict, user_settings, user_id: str):
        """Start a trend discovery job. Unavailable platforms are skipped gracefully."""
        niche = action.get("niche", "")
        platforms = action.get("platforms", ["youtube"])

        ready_platforms = []
        skipped = []

        for platform in platforms:
            cred_info = self._CREDENTIAL_PLATFORMS.get(platform)
            if cred_info:
                if cred_info["check"](user_settings):
                    ready_platforms.append(platform)
                else:
                    skipped.append(platform)
            else:
                ready_platforms.append(platform)

        if not ready_platforms:
            await self._followup(
                user_id,
                "No platforms available for trends — please configure API keys in Settings.",
            )
            return

        if skipped:
            await self._followup(
                user_id,
                f"Note: {', '.join(skipped)} unavailable (no API key configured) — "
                f"searching on {', '.join(ready_platforms)} only.",
            )

        # Kick off trend
        from backend.agents.job_helper import create_job
        from backend.core.task_runner import run_trend, dispatch
        job = await create_job("trend", user_id, {"niche": niche, "platforms": ready_platforms})
        dispatch(run_trend(job_id=job.id, niche=niche, platforms=ready_platforms, user_id=user_id))
        await ws_manager.send({
            "type": "job_started",
            "job_id": job.id,
            "job_type": "trend",
            "message": f"Finding trends for '{niche}' on {', '.join(ready_platforms)}...",
        }, user_id)
        await self.intelligence.record_event("niche_searched", {"niche": niche, "platforms": ready_platforms}, user_id)

    _check_and_start_scout = _check_and_start_trend

    @staticmethod
    def _infer_missing_action(user_message: str, ai_response: str, project_id: Optional[str] = None) -> list[str]:
        """
        Safety net: if the AI clearly intended to perform an action or edit but forgot
        the <action> block, infer the action. Conversational questions return [].
        """
        msg_lower = user_message.lower().strip()
        resp_lower = ai_response.lower().strip()

        # 1. Direct conversational / inquiry check — strictly NO action
        conversational_prefixes = [
            "explain ", "explain what", "what is ", "what are ", "what does ", "how does ",
            "how do i ", "tell me about ", "why is ", "why do ", "who is ",
            "help me understand ", "can you explain ", "o que é ", "explique ", "como funciona ",
        ]
        if any(msg_lower.startswith(p) for p in conversational_prefixes) or msg_lower in (
            "hi", "hello", "hey", "olá", "ola", "oi", "thanks", "thank you", "obrigado", "valeu"
        ):
            return []

        import re as _re

        # 2. Motion graphics & project edit action intents
        if "lower third" in msg_lower or "lower-third" in msg_lower:
            if any(act in msg_lower for act in ["add", "insert", "adicionar", "insere", "inserir", "put", "colocar"]):
                sec_match = _re.search(r'(?:at|em|aos?)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seg|segundos?|seconds?)?', msg_lower)
                start_time = float(sec_match.group(1)) if sec_match else 2.0
                action = json.dumps({
                    "type": "project_operation",
                    "project_id": project_id,
                    "operation_type": "insert_track_clip",
                    "payload": {
                        "track_id": "overlay_1",
                        "clip": {
                            "id": "clip_lt_1",
                            "block_id": "lower_third_minimal",
                            "block_version": "1.0.0",
                            "start_time": start_time,
                            "duration": 3.0,
                            "variables": {"title": "ViralMint", "subtitle": "Trending"},
                        },
                    },
                })
                return [action]

        if any(act in msg_lower for act in ["add caption", "add captions", "apply caption", "apply captions", "adicionar legendas", "legendas", "colocar legenda"]):
            return [json.dumps({"type": "apply_captions", "video_id": "latest"})]

        if any(act in msg_lower for act in ["cut this into clips", "cut clips", "extract clips", "cortar em clipes", "gerar clipes"]):
            return [json.dumps({"type": "extract_clips", "video_id": "latest"})]

        if any(act in msg_lower for act in ["make this faster", "faster", "speed up", "aumentar velocidade", "mais rápido"]):
            return [json.dumps({"type": "tool_speed", "speed": 1.5, "video_id": "latest"})]

        if any(act in msg_lower for act in ["render video", "render project", "export video", "renderizar vídeo", "renderizar video", "exportar vídeo"]):
            return [json.dumps({"type": "project_render", "project_id": project_id})]

        if any(act in msg_lower for act in ["upload to youtube", "upload youtube", "publicar no youtube"]):
            return [json.dumps({"type": "upload_youtube", "video_id": "latest"})]

        if any(act in msg_lower for act in ["upload to tiktok", "upload tiktok", "publicar no tiktok"]):
            return [json.dumps({"type": "upload_tiktok", "video_id": "latest"})]

        # 3. Detect direct article URL — always trigger analyze_url
        url_match = _re.search(r'(https?://[^\s<>"\']+)', user_message)
        if url_match:
            url = url_match.group(1).rstrip(".,;:)")
            video_domains = ["youtube.com", "youtu.be", "tiktok.com", "douyin.com"]
            is_video_url = any(d in url.lower() for d in video_domains)
            if not is_video_url:
                return [json.dumps({"type": "analyze_url", "url": url})]

        # 4. Detect news intent
        news_keywords = ["news", "article", "headlines", "notícias", "noticias", "新闻", "热点", "资讯"]
        has_news_intent = any(kw in msg_lower for kw in news_keywords)

        # 4b. Detect original video creation intent
        orig_keywords = [
            "create an original video", "create original video", "make an original video",
            "write an original script", "original script", "original brief",
            "crie um vídeo original", "criar um vídeo original", "criar video original",
            "roteiro original", "briefing original",
        ]
        if any(kw in msg_lower for kw in orig_keywords):
            topic = user_message.strip()
            for kw in orig_keywords:
                if kw in topic.lower():
                    parts = _re.split(_re.escape(kw), topic, flags=_re.IGNORECASE)
                    if len(parts) > 1 and parts[-1].strip():
                        topic = parts[-1].strip()
            for filler in ["about the", "about", "explaining", "sobre a", "sobre o", "sobre"]:
                if topic.lower().startswith(filler):
                    topic = topic[len(filler):].strip()
            clean_topic = topic.strip(": -.,") or "Trending Gaming Update"
            lang = "pt" if any(w in msg_lower for w in ["crie", "criar", "vídeo", "video original", "sobre"]) else "en"
            action = json.dumps({
                "type": "create_original_brief",
                "topic": clean_topic,
                "language": lang,
            })
            return [action]

        # 5. Detect trend intent from user message
        trend_keywords = [
            "trend", "trends", "tendencia", "tendencias", "tendência", "tendências",
            "scout", "search", "find", "look for", "trending", "viral",
            "找", "搜索", "搜一下", "查找", "热门", "帮我找",
        ]
        has_trend_intent = any(kw in msg_lower for kw in trend_keywords)

        doing_keywords = [
            "searching", "finding", "scouting", "looking", "on it", "i'll search", "let me find",
            "正在搜索", "正在为您", "开始搜索", "马上", "开始为您",
        ]
        ai_claimed_action = not ai_response or any(kw in resp_lower for kw in doing_keywords)

        if has_trend_intent and ai_claimed_action:
            niche = user_message.strip()
            for prefix in [
                "scout trending videos on youtube", "scout trending videos", "scout ",
                "find trending videos on youtube", "find trending videos", "find trends in ", "find trends on ", "find trends ",
                "search for trending videos", "search trends ", "search ", "find ", "look for ",
                "buscar tendências", "buscar tendencias", "ver tendências", "tendências de ", "tendencias de ",
                "tendências ", "tendencias ", "trends in ", "trends on ", "trends ", "trend ",
                "找一下", "找", "搜索", "搜一下", "帮我找", "查找",
            ]:
                if niche.lower().startswith(prefix):
                    niche = niche[len(prefix):].strip()
                    break

            if not niche:
                niche = "trending"

            if niche:
                if has_news_intent:
                    clean_query = niche
                    for word in ["news", "articles", "headlines", "notícias", "noticias", "新闻", "热点", "资讯"]:
                        clean_query = clean_query.replace(word, "").strip()
                    clean_query = clean_query or niche
                    vague_queries = {"trending", "trending news", "latest", "latest news", "news", "headlines"}
                    if clean_query.lower() in vague_queries:
                        return []
                    action = json.dumps({
                        "type": "start_news_scout",
                        "query": clean_query,
                    })
                    return [action]

                action = json.dumps({
                    "type": "start_trend",
                    "niche": niche,
                    "platforms": ["youtube"],
                })
                return [action]

        return []

    @staticmethod
    def _is_valid_json(s: str) -> bool:
        try:
            json.loads(s)
            return True
        except Exception:
            return False
