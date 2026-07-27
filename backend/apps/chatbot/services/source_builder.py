from typing import Any, Dict, List, Optional


class SourceBuilder:
    """
    Builds safe, farmer-facing source information from
    retrieved Knowledge records.

    Responsibilities:
    - Extract KnowledgeSource metadata
    - Build citations for RAG responses
    - Attach crop/category/domain information
    - Attach retrieval confidence when available
    - Remove duplicate sources
    - Never invent missing source metadata

    Important:
    This service only exposes metadata that actually exists
    in the database/retrieval result.

    It must NOT invent:
    - page numbers
    - URLs
    - organizations
    - authors
    - document titles
    - confidence scores
    """

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean(value: Any) -> str:
        if value is None:
            return ""

        return " ".join(str(value).strip().split())

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            return float(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(
        value: Any,
        default: Optional[int] = None,
    ) -> Optional[int]:
        try:
            if value is None:
                return default

            return int(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get(
        obj: Any,
        field: str,
        default=None,
    ):
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(
                field,
                default,
            )

        return getattr(
            obj,
            field,
            default,
        )

    # =========================================================
    # Knowledge Extraction
    # =========================================================

    def _get_knowledge(
        self,
        result: Any,
    ):
        """
        Retrieval results currently normally contain:

        {
            "knowledge": Knowledge(...),
            ...
        }

        But supporting direct Knowledge objects makes the
        service reusable.
        """

        if result is None:
            return None

        if isinstance(result, dict):
            knowledge = result.get("knowledge")

            if knowledge is not None:
                return knowledge

        # Direct Django Knowledge object.
        if hasattr(result, "question") and hasattr(
            result,
            "answer",
        ):
            return result

        return None

    # =========================================================
    # Knowledge Source Extraction
    # =========================================================

    def _get_knowledge_source(
        self,
        knowledge: Any,
    ):
        if knowledge is None:
            return None

        return self._get(
            knowledge,
            "knowledge_source",
        )

    # =========================================================
    # Retrieval Scores
    # =========================================================

    def _extract_scores(
        self,
        result: Any,
    ) -> Dict[str, float]:
        if not isinstance(
            result,
            dict,
        ):
            return {}

        score_mapping = {
            "score": "score",
            "hybrid_score": "hybrid_score",
            "keyword_raw_score": "keyword_raw",
            "bm25_raw_score": "bm25_raw",
            "fuzzy_raw_score": "fuzzy_raw",
            "semantic_raw_score": "semantic_raw",
        }

        scores = {}

        for source_key, output_key in score_mapping.items():
            if source_key not in result:
                continue

            value = result.get(source_key)

            try:
                scores[output_key] = round(
                    float(value),
                    4,
                )

            except (TypeError, ValueError):
                continue

        # Some services may already expose nested raw scores.
        nested = result.get("scores", {})

        if isinstance(nested, dict):
            for key in [
                "keyword_raw",
                "bm25_raw",
                "fuzzy_raw",
                "semantic_raw",
            ]:
                if key in scores:
                    continue

                if key not in nested:
                    continue

                try:
                    scores[key] = round(
                        float(nested[key]),
                        4,
                    )

                except (TypeError, ValueError):
                    continue

        return scores

    # =========================================================
    # Page Metadata
    # =========================================================

    def _extract_page_number(
        self,
        result: Any,
        knowledge: Any,
    ) -> Optional[int]:
        """
        Page number is returned ONLY when actual metadata exists.

        Current Knowledge model does not contain a page_number
        field, therefore most existing records will return None.

        This method makes SourceBuilder forward-compatible with
        future PDF/document chunk metadata.
        """

        possible_fields = [
            "page_number",
            "page",
            "source_page",
        ]

        # Retrieval result metadata first.
        if isinstance(result, dict):
            for field in possible_fields:
                value = result.get(field)

                page = self._safe_int(value)

                if page is not None and page > 0:
                    return page

            metadata = result.get("metadata", {})

            if isinstance(metadata, dict):
                for field in possible_fields:
                    page = self._safe_int(metadata.get(field))

                    if page is not None and page > 0:
                        return page

        # Future Knowledge model compatibility.
        if knowledge is not None:
            for field in possible_fields:
                value = self._get(
                    knowledge,
                    field,
                )

                page = self._safe_int(value)

                if page is not None and page > 0:
                    return page

        return None

    # =========================================================
    # Build One Source
    # =========================================================

    def build_source(
        self,
        result: Any,
        rank: Optional[int] = None,
    ) -> Optional[Dict]:
        """
        Build one normalized source dictionary.
        """

        knowledge = self._get_knowledge(result)

        if knowledge is None:
            return None

        source = self._get_knowledge_source(knowledge)

        # -----------------------------------------------------
        # Knowledge metadata
        # -----------------------------------------------------

        knowledge_id = self._get(
            knowledge,
            "id",
        )

        crop = self._clean(
            self._get(
                knowledge,
                "crop",
                "",
            )
        )

        category = self._clean(
            self._get(
                knowledge,
                "category",
                "",
            )
        )

        subcategory = self._clean(
            self._get(
                knowledge,
                "subcategory",
                "",
            )
        )

        domain = self._clean(
            self._get(
                knowledge,
                "domain",
                "",
            )
        )

        stage = self._clean(
            self._get(
                knowledge,
                "stage",
                "",
            )
        )

        language = self._clean(
            self._get(
                knowledge,
                "language",
                "",
            )
        )

        question = self._clean(
            self._get(
                knowledge,
                "question",
                "",
            )
        )

        # -----------------------------------------------------
        # Source metadata
        # -----------------------------------------------------

        source_id = None
        title = ""
        source_name = ""
        source_type = ""
        version = ""

        if source is not None:
            source_id = self._get(
                source,
                "id",
            )

            title = self._clean(
                self._get(
                    source,
                    "title",
                    "",
                )
            )

            source_name = self._clean(
                self._get(
                    source,
                    "source_name",
                    "",
                )
            )

            source_type = self._clean(
                self._get(
                    source,
                    "source_type",
                    "",
                )
            )

            version = self._clean(
                self._get(
                    source,
                    "version",
                    "",
                )
            )

        page_number = self._extract_page_number(
            result=result,
            knowledge=knowledge,
        )

        scores = self._extract_scores(result)

        # -----------------------------------------------------
        # Human-readable source label
        # -----------------------------------------------------

        display_name = source_name or title or "Agricultural Knowledge Base"

        citation = display_name

        if page_number is not None:
            citation = f"{citation}, page {page_number}"

        # -----------------------------------------------------
        # Final structure
        # -----------------------------------------------------

        source_data = {
            "knowledge_id": knowledge_id,
            "source_id": source_id,
            "title": title,
            "source_name": source_name,
            "display_name": display_name,
            "source_type": source_type,
            "version": version,
            "page_number": page_number,
            "citation": citation,
            "crop": crop,
            "category": category,
            "subcategory": subcategory,
            "domain": domain,
            "stage": stage,
            "language": language,
            "matched_question": question,
            "scores": scores,
        }

        if rank is not None:
            source_data["rank"] = rank

        return source_data

    # =========================================================
    # Duplicate Identity
    # =========================================================

    def _source_identity(
        self,
        source: Dict,
    ):
        """
        Keep different knowledge records when they provide
        different evidence, while removing accidental duplicate
        retrieval entries.
        """

        knowledge_id = source.get("knowledge_id")

        if knowledge_id is not None:
            return (
                "knowledge",
                str(knowledge_id),
            )

        return (
            "fallback",
            source.get("source_id"),
            source.get(
                "matched_question",
                "",
            ).lower(),
            source.get("page_number"),
        )

    # =========================================================
    # Build Multiple Sources
    # =========================================================

    def build(
        self,
        retrieved_documents,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Convert retrieval results into normalized source data.
        """

        if not retrieved_documents:
            return []

        sources = []

        seen = set()

        for result in retrieved_documents:
            source = self.build_source(
                result=result,
                rank=len(sources) + 1,
            )

            if source is None:
                continue

            identity = self._source_identity(source)

            if identity in seen:
                continue

            seen.add(identity)

            sources.append(source)

            if limit is not None and len(sources) >= limit:
                break

        return sources

    # =========================================================
    # Build Farmer-Facing Sources
    # =========================================================

    def build_public(
        self,
        retrieved_documents,
        limit: int = 3,
    ) -> List[Dict]:
        """
        Return compact source metadata suitable for API/UI.

        Internal retrieval details are intentionally omitted.
        """

        sources = self.build(
            retrieved_documents,
            limit=limit,
        )

        public_sources = []

        for source in sources:
            item = {
                "name": source["display_name"],
                "citation": source["citation"],
                "type": source["source_type"],
            }

            if source.get("page_number") is not None:
                item["page_number"] = source["page_number"]

            if source.get("crop"):
                item["crop"] = source["crop"]

            if source.get("category"):
                item["category"] = source["category"]

            if source.get("matched_question"):
                item["matched_question"] = source["matched_question"]

            public_sources.append(item)

        return public_sources

    # =========================================================
    # Build Source Names Only
    # =========================================================

    def get_source_names(
        self,
        retrieved_documents,
    ) -> List[str]:
        """
        Useful for speech/UI responses where only source names
        are required.
        """

        sources = self.build(retrieved_documents)

        names = []

        for source in sources:
            name = source.get("display_name")

            if name and name not in names:
                names.append(name)

        return names

    # =========================================================
    # Best Source
    # =========================================================

    def get_best_source(
        self,
        retrieved_documents,
    ) -> Optional[Dict]:

        sources = self.build(
            retrieved_documents,
            limit=1,
        )

        if not sources:
            return None

        return sources[0]

    # =========================================================
    # Citation List
    # =========================================================

    def get_citations(
        self,
        retrieved_documents,
        limit: int = 3,
    ) -> List[str]:

        sources = self.build(
            retrieved_documents,
            limit=limit,
        )

        citations = []

        for source in sources:
            citation = source.get("citation")

            if citation and citation not in citations:
                citations.append(citation)

        return citations

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        retrieved_documents,
        limit: int = 3,
    ) -> List[Dict]:

        sources = self.build(
            retrieved_documents,
            limit=limit,
        )

        print("\n" + "=" * 80)

        print("SOURCE BUILDER")

        print("=" * 80)

        print(
            "Retrieved Documents :",
            len(retrieved_documents) if retrieved_documents else 0,
        )

        print(
            "Sources Built       :",
            len(sources),
        )

        print("-" * 80)

        for source in sources:
            print(
                "Rank       :",
                source.get("rank"),
            )

            print(
                "Source     :",
                source.get("display_name"),
            )

            print(
                "Citation   :",
                source.get("citation"),
            )

            print(
                "Page       :",
                source.get("page_number"),
            )

            print(
                "Crop       :",
                source.get("crop"),
            )

            print(
                "Category   :",
                source.get("category"),
            )

            print(
                "Question   :",
                source.get("matched_question"),
            )

            print(
                "Scores     :",
                source.get("scores"),
            )

            print("-" * 80)

        print("=" * 80 + "\n")

        return sources
