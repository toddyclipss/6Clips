# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Deterministic BM25 lexical ranking and multi-faceted filtering engine.
Fully offline and reproducible.
"""
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from .models import CapabilityFamily, KnowledgeDoc, RightsFlag, SearchFilter, SearchResult
from .storage import KnowledgeRepository

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into",
    "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
    "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself"
}


def tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric tokens, filtering stop words."""
    words = re.findall(r"[a-zA-Z0-9_\-]+", text.lower())
    tokens = []
    for w in words:
        clean = w.strip("-")
        if len(clean) >= 2 and clean not in STOP_WORDS:
            tokens.append(clean)
    return tokens


class BM25SearchEngine:
    def __init__(self, repository: KnowledgeRepository, k1: float = 1.5, b: float = 0.75):
        self.repo = repository
        self.k1 = k1
        self.b = b
        self.corpus: List[KnowledgeDoc] = self.repo.list_all()
        self.N = len(self.corpus)

        # Inverted index: term -> list of (doc_index, term_frequency)
        self.inverted_index: Dict[str, List[Tuple[int, float]]] = {}
        # Document lengths and average length
        self.doc_lengths: List[float] = []
        self.avg_doc_length: float = 0.0

        self._build_index()

    def _build_index(self):
        total_len = 0.0
        doc_term_freqs: List[Dict[str, float]] = []

        for idx, doc in enumerate(self.corpus):
            tf: Dict[str, float] = {}

            # Weighted field tokens
            # Title tokens boost x 3.0
            for t in tokenize(doc.title):
                tf[t] = tf.get(t, 0.0) + 3.0

            # Tags boost x 2.5
            for tag in doc.tags:
                for t in tokenize(tag):
                    tf[t] = tf.get(t, 0.0) + 2.5

            # Principles boost x 2.0
            for p in doc.principles:
                for t in tokenize(p):
                    tf[t] = tf.get(t, 0.0) + 2.0

            # Algorithms boost x 2.0
            for a in doc.algorithms:
                for t in tokenize(a):
                    tf[t] = tf.get(t, 0.0) + 2.0

            # Summary boost x 1.5
            for t in tokenize(doc.summary):
                tf[t] = tf.get(t, 0.0) + 1.5

            # Chunks boost x 1.0
            for c in doc.chunks:
                for t in tokenize(c.content):
                    tf[t] = tf.get(t, 0.0) + 1.0

            length = sum(tf.values())
            self.doc_lengths.append(length)
            total_len += length
            doc_term_freqs.append(tf)

        self.avg_doc_length = total_len / max(1, self.N)

        for doc_idx, tf in enumerate(doc_term_freqs):
            for term, freq in tf.items():
                self.inverted_index.setdefault(term, []).append((doc_idx, freq))

    def _compute_idf(self, term: str) -> float:
        n_q = len(self.inverted_index.get(term, []))
        if n_q == 0:
            return 0.0
        return math.log(1.0 + (self.N - n_q + 0.5) / (n_q + 0.5))

    def search(
        self,
        query: str,
        filters: Optional[SearchFilter] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        doc_scores: Dict[int, float] = {}
        matched_terms_per_doc: Dict[int, Set[str]] = {}

        for token in query_tokens:
            postings = self.inverted_index.get(token, [])
            idf = self._compute_idf(token)
            if idf <= 0.0:
                continue

            for doc_idx, tf in postings:
                dl = self.doc_lengths[doc_idx]
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / max(1e-6, self.avg_doc_length)))
                score = idf * (tf * (self.k1 + 1.0)) / denom

                doc_scores[doc_idx] = doc_scores.get(doc_idx, 0.0) + score
                matched_terms_per_doc.setdefault(doc_idx, set()).add(token)

        # Boost for exact multi-token matches in title or ID
        q_lower = query.lower()
        for doc_idx in list(doc_scores.keys()):
            doc = self.corpus[doc_idx]
            if q_lower in doc.title.lower():
                doc_scores[doc_idx] *= 1.5
            if q_lower in doc.knowledge_doc_id.lower():
                doc_scores[doc_idx] *= 1.8

        # Filter and rank candidates
        results: List[SearchResult] = []
        ranked_doc_indices = sorted(doc_scores.keys(), key=lambda idx: doc_scores[idx], reverse=True)

        for doc_idx in ranked_doc_indices:
            doc = self.corpus[doc_idx]
            score = doc_scores[doc_idx]

            # Apply filters
            if not self._passes_filter(doc, filters):
                continue

            # Matched chunk
            matched_chunk_text = None
            if doc.chunks:
                # Find chunk with most matched terms
                best_chunk = None
                max_term_hits = -1
                for c in doc.chunks:
                    hits = sum(1 for t in query_tokens if t in c.content.lower())
                    if hits > max_term_hits:
                        max_term_hits = hits
                        best_chunk = c
                if best_chunk:
                    matched_chunk_text = best_chunk.content[:300]

            matched_terms = sorted(list(matched_terms_per_doc.get(doc_idx, [])))
            explanation = f"Matched terms: {', '.join(matched_terms)} | Capability: {doc.capability_family.value} | Donor: {doc.donor_group}"

            # Aggregate techniques
            techs = list(doc.algorithms) + [f"Easing: {e}" for e in doc.equations if "easing" in e.lower()]
            if not techs:
                techs = doc.principles[:3]

            results.append(SearchResult(
                knowledge_doc_id=doc.knowledge_doc_id,
                title=doc.title,
                score=round(score, 4),
                source_hash=doc.source_hash,
                source_ref=doc.source_path,
                donor_group=doc.donor_group,
                donor_section=doc.donor_section,
                capability_family=doc.capability_family.value,
                techniques=techs[:5],
                principles=doc.principles[:3],
                algorithms=doc.algorithms[:3],
                equations=doc.equations[:3],
                parameters=doc.parameters[:5],
                rights=doc.rights.value,
                runtime_constraints=doc.runtime_constraints,
                retrieval_explanation=explanation,
                matched_chunk=matched_chunk_text
            ))

            if len(results) >= limit:
                break

        return results

    def _passes_filter(self, doc: KnowledgeDoc, filters: Optional[SearchFilter]) -> bool:
        if not filters:
            return True

        # Capability family
        if filters.capability_family:
            req_fam = filters.capability_family.value if isinstance(filters.capability_family, CapabilityFamily) else str(filters.capability_family)
            doc_fam = doc.capability_family.value if isinstance(doc.capability_family, CapabilityFamily) else str(doc.capability_family)
            if req_fam != doc_fam:
                return False

        # Donor group
        if filters.donor_group and filters.donor_group.lower() != doc.donor_group.lower():
            return False

        # Rights
        if filters.rights:
            req_r = filters.rights.value if isinstance(filters.rights, RightsFlag) else str(filters.rights)
            doc_r = doc.rights.value if isinstance(doc.rights, RightsFlag) else str(doc.rights)
            if req_r != doc_r:
                return False

        # Aspect ratio
        if filters.aspect_ratio:
            supported = doc.runtime_constraints.get("aspect_ratios", [])
            if supported and filters.aspect_ratio not in supported:
                return False

        # Captions suitability
        if filters.captions_suitability is not None:
            is_cap = (
                doc.capability_family == CapabilityFamily.CAPTIONS_WORD_HIGHLIGHT or
                any("caption" in t.lower() for t in doc.tags)
            )
            if filters.captions_suitability != is_cap:
                return False

        # Technique
        if filters.technique:
            req_tech = filters.technique.lower()
            all_tech = " ".join(doc.algorithms + doc.principles + doc.tags).lower()
            if req_tech not in all_tech:
                return False

        # Tag
        if filters.tag:
            req_tag = filters.tag.lower()
            if not any(req_tag == t.lower() for t in doc.tags):
                return False

        # WebGPU
        if filters.requires_webgpu is not None:
            doc_webgpu = bool(doc.runtime_constraints.get("requires_webgpu", False))
            if filters.requires_webgpu != doc_webgpu:
                return False

        return True
