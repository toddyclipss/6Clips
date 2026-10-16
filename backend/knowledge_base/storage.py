# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2025-2026 ViralMint Contributors
"""
Airgapped storage repository for local knowledge snapshots.
Zero external network access.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from .models import CapabilityFamily, KnowledgeDoc, RightsFlag

DEFAULT_SNAPSHOT_PATH = Path(__file__).parent / "data" / "knowledge_snapshot.json"


class KnowledgeRepository:
    def __init__(self, snapshot_path: Optional[Path] = None):
        self.snapshot_path = snapshot_path or DEFAULT_SNAPSHOT_PATH
        self.docs_by_id: Dict[str, KnowledgeDoc] = {}
        self.docs_by_family: Dict[str, List[KnowledgeDoc]] = {}
        self.docs_by_group: Dict[str, List[KnowledgeDoc]] = {}
        self.docs_by_rights: Dict[str, List[KnowledgeDoc]] = {}
        self.docs_by_tag: Dict[str, List[KnowledgeDoc]] = {}
        self.metadata: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if not self.snapshot_path.exists():
            raise FileNotFoundError(f"Knowledge snapshot not found at: {self.snapshot_path}")

        raw_data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        self.metadata = {
            "schema_version": raw_data.get("schema_version", "1.0.0"),
            "generated_at": raw_data.get("generated_at", ""),
            "total_documents": raw_data.get("total_documents", 0),
            "capability_family_breakdown": raw_data.get("capability_family_breakdown", {}),
            "donor_group_breakdown": raw_data.get("donor_group_breakdown", {}),
            "rights_breakdown": raw_data.get("rights_breakdown", {})
        }

        docs_list = raw_data.get("documents", [])
        for item in docs_list:
            doc = KnowledgeDoc.model_validate(item)
            self.docs_by_id[doc.knowledge_doc_id] = doc

            # Index by capability family
            fam = str(doc.capability_family.value if isinstance(doc.capability_family, CapabilityFamily) else doc.capability_family)
            self.docs_by_family.setdefault(fam, []).append(doc)

            # Index by donor group
            self.docs_by_group.setdefault(doc.donor_group, []).append(doc)

            # Index by rights
            r = str(doc.rights.value if isinstance(doc.rights, RightsFlag) else doc.rights)
            self.docs_by_rights.setdefault(r, []).append(doc)

            # Index by tags
            for t in doc.tags:
                self.docs_by_tag.setdefault(t.lower(), []).append(doc)

    def get_by_id(self, doc_id: str) -> Optional[KnowledgeDoc]:
        """Lookup document by ID."""
        return self.docs_by_id.get(doc_id)

    def list_all(self) -> List[KnowledgeDoc]:
        """Return all indexed documents."""
        return list(self.docs_by_id.values())

    def get_by_family(self, family: str) -> List[KnowledgeDoc]:
        return self.docs_by_family.get(family, [])

    def get_by_group(self, group: str) -> List[KnowledgeDoc]:
        return self.docs_by_group.get(group, [])

    def get_by_rights(self, rights: str) -> List[KnowledgeDoc]:
        return self.docs_by_rights.get(rights, [])

    def get_by_tag(self, tag: str) -> List[KnowledgeDoc]:
        return self.docs_by_tag.get(tag.lower(), [])

    def count(self) -> int:
        return len(self.docs_by_id)
