import math
from typing import Any, Dict, List, Optional, Set


class EvidenceSelector:
    """
    Select trustworthy supporting evidence before RAG generation.

    Pipeline position
    -----------------
    HybridRanker
        ↓
    RetrieverService
        ↓
    RelevanceService
        ↓
    EvidenceSelector
        ↓
    PromptBuilder / LLM

    Goals
    -----
    1. Never blindly send top-N retrieval results to the LLM.
    2. Preserve the strongest relevant result.
    3. Reject dramatically weaker supporting documents.
    4. Prefer semantic/question-level agreement.
    5. Prevent explicit cross-crop evidence mixing.
    6. Remove duplicate knowledge.
    7. Reduce conflicting evidence.
    8. Keep RAG context compact.
    9. Preserve raw retrieval evidence.
    """

    # =========================================================
    # Context Limits
    # =========================================================

    MAX_DOCUMENTS = 3

    # =========================================================
    # Relative Hybrid Strength
    # =========================================================

    MIN_RELATIVE_SCORE = 0.72

    # =========================================================
    # Raw Evidence Thresholds
    # =========================================================

    MIN_QUESTION_SCORE = 0.45

    MIN_SEMANTIC_SCORE = 0.72

    MIN_BM25_SCORE = 1.0

    MIN_KEYWORD_SCORE = 5.0

    MIN_FUZZY_SCORE = 65.0

    # Additional documents should normally have at least
    # two meaningful independent evidence signals.
    MIN_SUPPORT_SIGNALS = 2

    # =========================================================
    # Main Selection
    # =========================================================

    def select(
        self,
        ranked_results,
    ) -> List[Dict[str, Any]]:
        """
        Select final evidence documents.

        `ranked_results` should already be sorted strongest
        to weakest.

        Returns the same result dictionaries so downstream
        services retain all ranking metadata.
        """

        if not isinstance(
            ranked_results,
            list,
        ):

            return []

        if not ranked_results:

            return []

        # =====================================================
        # 1. Remove malformed / duplicate candidates
        # =====================================================

        candidates = self._prepare_candidates(ranked_results)

        if not candidates:

            return []

        # =====================================================
        # 2. Strongest Candidate
        # =====================================================

        best = candidates[0]

        best_score = self._safe_float(
            best.get(
                "score",
                best.get(
                    "hybrid_score",
                    0.0,
                ),
            )
        )

        # Minimum relevance threshold for trusted DB evidence
        if best_score < 0.45:
            return []

        best_knowledge = best.get("knowledge")

        best_crop = self._normalize_text(
            getattr(
                best_knowledge,
                "crop",
                "",
            )
            if best_knowledge
            else ""
        )

        selected = [best]

        selected_ids: Set[Any] = set()

        best_id = self._knowledge_id(best)

        if best_id is not None:

            selected_ids.add(best_id)

        # If the best result itself has no usable ranking
        # strength, don't expand context with weaker records.

        if best_score <= 0.0:

            return selected

        # =====================================================
        # 3. Evaluate Supporting Candidates
        # =====================================================

        for candidate in candidates[1:]:

            if len(selected) >= self.MAX_DOCUMENTS:

                break

            knowledge = candidate.get("knowledge")

            if knowledge is None:

                continue

            knowledge_id = self._knowledge_id(candidate)

            if knowledge_id is not None and knowledge_id in selected_ids:

                continue

            # =================================================
            # Candidate Hybrid Strength
            # =================================================

            candidate_score = self._safe_float(
                candidate.get(
                    "score",
                    candidate.get(
                        "hybrid_score",
                        0.0,
                    ),
                )
            )

            if candidate_score <= 0.0:

                continue

            relative_score = candidate_score / best_score

            # =================================================
            # Rule 1:
            # Candidate must remain reasonably close to best.
            # =================================================

            if relative_score < self.MIN_RELATIVE_SCORE:

                continue

            # =================================================
            # Rule 2:
            # Prevent explicit crop conflicts.
            # =================================================

            candidate_crop = self._normalize_text(
                getattr(
                    knowledge,
                    "crop",
                    "",
                )
            )

            if best_crop and candidate_crop and candidate_crop != best_crop:

                continue

            # =================================================
            # Raw Retrieval Evidence
            # =================================================

            question_score = self._safe_float(
                candidate.get(
                    "question_raw_score",
                    candidate.get(
                        "question_score",
                        0.0,
                    ),
                )
            )

            semantic_score = self._safe_float(
                candidate.get(
                    "semantic_raw_score",
                    0.0,
                )
            )

            bm25_score = self._safe_float(
                candidate.get(
                    "bm25_raw_score",
                    0.0,
                )
            )

            keyword_score = self._safe_float(
                candidate.get(
                    "keyword_raw_score",
                    0.0,
                )
            )

            fuzzy_score = self._safe_float(
                candidate.get(
                    "fuzzy_raw_score",
                    0.0,
                )
            )

            # =================================================
            # Rule 3:
            # Require direct question similarity OR strong
            # semantic evidence.
            # =================================================

            if (
                question_score < self.MIN_QUESTION_SCORE
                and semantic_score < self.MIN_SEMANTIC_SCORE
            ):

                continue

            # =================================================
            # Rule 4:
            # Require independent supporting evidence.
            # =================================================

            support_signals = 0

            if question_score >= self.MIN_QUESTION_SCORE:

                support_signals += 1

            if semantic_score >= self.MIN_SEMANTIC_SCORE:

                support_signals += 1

            if bm25_score >= self.MIN_BM25_SCORE:

                support_signals += 1

            if keyword_score >= self.MIN_KEYWORD_SCORE:

                support_signals += 1

            if fuzzy_score >= self.MIN_FUZZY_SCORE:

                support_signals += 1

            if support_signals < self.MIN_SUPPORT_SIGNALS:

                continue

            # =================================================
            # Rule 5:
            # Avoid duplicate evidence text.
            # =================================================

            if self._is_duplicate_evidence(
                candidate=candidate,
                selected=selected,
            ):

                continue

            # =================================================
            # Accept Candidate
            # =================================================

            candidate = dict(candidate)

            candidate["evidence_relative_score"] = float(relative_score)

            candidate["evidence_support_signals"] = int(support_signals)

            selected.append(candidate)

            if knowledge_id is not None:

                selected_ids.add(knowledge_id)

        # =====================================================
        # Debug
        # =====================================================

        self._debug(
            candidates=candidates,
            selected=selected,
            best_score=best_score,
        )

        return selected

    # =========================================================
    # Candidate Preparation
    # =========================================================

    def _prepare_candidates(
        self,
        ranked_results,
    ) -> List[Dict[str, Any]]:
        """
        Remove malformed results and duplicate Knowledge IDs.
        """

        prepared = []

        seen_ids = set()

        for result in ranked_results:

            if not isinstance(
                result,
                dict,
            ):

                continue

            knowledge = result.get("knowledge")

            if knowledge is None:

                continue

            knowledge_id = self._knowledge_id(result)

            if knowledge_id is not None and knowledge_id in seen_ids:

                continue

            if knowledge_id is not None:

                seen_ids.add(knowledge_id)

            prepared.append(result)

        # Do not assume caller always sorted correctly.

        prepared.sort(
            key=lambda item: self._safe_float(
                item.get(
                    "score",
                    item.get(
                        "hybrid_score",
                        0.0,
                    ),
                )
            ),
            reverse=True,
        )

        return prepared

    # =========================================================
    # Duplicate Evidence Detection
    # =========================================================

    def _is_duplicate_evidence(
        self,
        candidate,
        selected,
    ) -> bool:
        """
        Prevent multiple nearly identical Knowledge records
        from wasting prompt context.
        """

        candidate_signature = self._evidence_signature(candidate)

        if not candidate_signature:

            return False

        for existing in selected:

            existing_signature = self._evidence_signature(existing)

            if existing_signature and candidate_signature == existing_signature:

                return True

        return False

    # =========================================================
    # Evidence Signature
    # =========================================================

    def _evidence_signature(
        self,
        result,
    ) -> str:

        knowledge = result.get("knowledge")

        if knowledge is None:

            return ""

        crop = self._normalize_text(
            getattr(
                knowledge,
                "crop",
                "",
            )
        )

        question = self._normalize_text(
            getattr(
                knowledge,
                "question",
                "",
            )
        )

        answer = self._normalize_text(
            getattr(
                knowledge,
                "answer",
                "",
            )
        )

        return f"{crop}|" f"{question}|" f"{answer}"

    # =========================================================
    # Knowledge ID
    # =========================================================

    @staticmethod
    def _knowledge_id(
        result,
    ) -> Optional[Any]:

        knowledge = result.get("knowledge")

        if knowledge is None:

            return None

        return getattr(
            knowledge,
            "id",
            None,
        )

    # =========================================================
    # Text Normalization
    # =========================================================

    @staticmethod
    def _normalize_text(
        value,
    ) -> str:

        if value is None:

            return ""

        return " ".join(str(value).casefold().strip().split())

    # =========================================================
    # Safe Float
    # =========================================================

    @staticmethod
    def _safe_float(
        value,
        default=0.0,
    ) -> float:

        try:

            value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return float(default)

        if not math.isfinite(value):

            return float(default)

        return value

    # =========================================================
    # Debug
    # =========================================================

    def _debug(
        self,
        candidates,
        selected,
        best_score,
    ):

        print("\n" + "=" * 80)

        print("EVIDENCE SELECTOR")

        print("=" * 80)

        print(
            "Candidates :",
            len(candidates),
        )

        print(
            "Selected   :",
            len(selected),
        )

        print(
            "Best Score :",
            round(
                best_score,
                4,
            ),
        )

        print("-" * 80)

        for index, result in enumerate(
            selected,
            start=1,
        ):

            knowledge = result.get("knowledge")

            print(f"Evidence #{index}")

            print(
                "Crop     :",
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
            )

            print(
                "Question :",
                getattr(
                    knowledge,
                    "question",
                    "",
                ),
            )

            print(
                "Hybrid   :",
                round(
                    self._safe_float(
                        result.get(
                            "score",
                            0.0,
                        )
                    ),
                    4,
                ),
            )

            print(
                "Semantic :",
                round(
                    self._safe_float(
                        result.get(
                            "semantic_raw_score",
                            0.0,
                        )
                    ),
                    4,
                ),
            )

            print(
                "Question :",
                round(
                    self._safe_float(
                        result.get(
                            "question_raw_score",
                            0.0,
                        )
                    ),
                    4,
                ),
            )

            print("-" * 80)

        print("=" * 80 + "\n")
