# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Public service interface for the 6Clips HyperFrames Motion Design Knowledge Base.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from .models import CapabilityFamily, KnowledgeDoc, RightsFlag, SearchFilter, SearchResult
from .search import BM25SearchEngine
from .storage import KnowledgeRepository


class KnowledgeBase:
    """Unified service interface for local knowledge retrieval."""

    def __init__(self, snapshot_path: Optional[Path] = None):
        self.repository = KnowledgeRepository(snapshot_path)
        self.search_engine = BM25SearchEngine(self.repository)

    def search(
        self,
        query: str,
        filters: Optional[Union[SearchFilter, Dict[str, Any]]] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Execute deterministic lexical BM25 search across curated knowledge documents.

        Args:
            query: Natural language or keyword search query.
            filters: Optional SearchFilter model or dictionary of filter criteria.
            limit: Maximum number of ranked results to return.

        Returns:
            List of SearchResult objects with source hash, technique references, and explanations.
        """
        parsed_filters = None
        if filters:
            if isinstance(filters, SearchFilter):
                parsed_filters = filters
            elif isinstance(filters, dict):
                parsed_filters = SearchFilter(**filters)

        return self.search_engine.search(query, filters=parsed_filters, limit=limit)

    def get_by_id(self, doc_id: str) -> Optional[KnowledgeDoc]:
        """Lookup a knowledge document directly by its stable ID."""
        return self.repository.get_by_id(doc_id)

    def list_categories(self) -> Dict[str, List[str]]:
        """
        List categories preserving donor canonical groups distinct from 6Clips query taxonomy.
        """
        donor_groups = sorted(list(self.repository.docs_by_group.keys()))
        capability_families = sorted([fam.value for fam in CapabilityFamily])
        return {
            "donor_canonical_groups": donor_groups,
            "derived_6clips_capability_families": capability_families
        }

    def get_techniques(
        self,
        capability_family: Optional[Union[CapabilityFamily, str]] = None,
        rights: Optional[Union[RightsFlag, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve permitted technique snippets with citations.
        """
        docs = self.repository.list_all()
        if capability_family:
            fam_val = capability_family.value if isinstance(capability_family, CapabilityFamily) else str(capability_family)
            docs = [d for d in docs if (d.capability_family.value if isinstance(d.capability_family, CapabilityFamily) else d.capability_family) == fam_val]

        if rights:
            r_val = rights.value if isinstance(rights, RightsFlag) else str(rights)
            docs = [d for d in docs if (d.rights.value if isinstance(d.rights, RightsFlag) else d.rights) == r_val]

        techniques = []
        for d in docs:
            for ref in d.code_references:
                techniques.append({
                    "knowledge_doc_id": d.knowledge_doc_id,
                    "title": d.title,
                    "capability_family": d.capability_family.value if isinstance(d.capability_family, CapabilityFamily) else d.capability_family,
                    "donor_group": d.donor_group,
                    "citation": ref.get("citation", d.source_path),
                    "source_hash": d.source_hash,
                    "lang": ref.get("lang", "text"),
                    "snippet": ref.get("snippet", ""),
                    "principles": d.principles,
                    "algorithms": d.algorithms,
                    "rights": d.rights.value if isinstance(d.rights, RightsFlag) else d.rights
                })
        return techniques

    def get_stats(self) -> Dict[str, Any]:
        """Return corpus metadata, document counts, and distribution summaries."""
        total_chunks = sum(len(d.chunks) for d in self.repository.list_all())
        return {
            "total_documents": self.repository.count(),
            "total_chunks": total_chunks,
            "metadata": self.repository.metadata
        }
