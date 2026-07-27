from typing import Any, Dict, List

from apps.knowledge_base.services.question_similarity import (
    QuestionSimilarity,
)


class HybridRanker:
    """
    Production hybrid ranker for Farmer Voice AI.

    Combines
    --------
    1. Keyword retrieval
    2. BM25 retrieval
    3. Fuzzy retrieval
    4. Semantic retrieval
    5. Direct question similarity

    Design
    ------
    Every retriever can expose two different values:

        score
            Ranking score used inside that retriever.

        *_raw_score
            Actual evidence score before metadata/crop bonuses.

    Hybrid ranking uses normalized raw retrieval evidence.

    RelevanceService receives the original raw values.

    This prevents crop bonuses or retriever-specific ranking
    adjustments from accidentally becoming evidence of
    relevance.
    """

    # =========================================================
    # Hybrid Weights
    # =========================================================

    KEYWORD_WEIGHT = 0.20

    BM25_WEIGHT = 0.25

    FUZZY_WEIGHT = 0.10

    SEMANTIC_WEIGHT = 0.20

    QUESTION_WEIGHT = 0.25

    # =========================================================
    # Retriever Agreement
    # =========================================================

    AGREEMENT_BONUS_PER_RETRIEVER = 0.015

    MAX_AGREEMENT_BONUS = 0.045

    # Signals considered meaningful enough to count toward
    # independent retriever agreement.

    KEYWORD_AGREEMENT_MIN = 1.0

    BM25_AGREEMENT_MIN = 0.01

    FUZZY_AGREEMENT_MIN = 55.0

    SEMANTIC_AGREEMENT_MIN = 0.50

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.question_similarity = QuestionSimilarity()

    # =========================================================
    # Create Score Item
    # =========================================================

    @staticmethod
    def _create_item(
        obj,
    ) -> Dict[str, Any]:
        """
        Create score structure for a Knowledge record.
        """

        return {
            "knowledge": obj,
            # ---------------------------------------------
            # Normalized retrieval scores
            # ---------------------------------------------
            "keyword_score": 0.0,
            "bm25_score": 0.0,
            "fuzzy_score": 0.0,
            "semantic_score": 0.0,
            "question_score": 0.0,
            # ---------------------------------------------
            # Raw retrieval evidence
            # ---------------------------------------------
            "keyword_raw_score": 0.0,
            "bm25_raw_score": 0.0,
            "fuzzy_raw_score": 0.0,
            "semantic_raw_score": 0.0,
            "question_raw_score": 0.0,
            # ---------------------------------------------
            # Retriever metadata
            # ---------------------------------------------
            "retrievers": set(),
            "crop_match": None,
        }

    # =========================================================
    # Safe Float
    # =========================================================

    @staticmethod
    def _safe_float(
        value,
        default=0.0,
    ) -> float:

        try:

            number = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return float(default)

        # NaN protection
        if number != number:
            return float(default)

        return number

    # =========================================================
    # Extract Results
    # =========================================================

    @staticmethod
    def _get_results(
        retrieval_result,
    ) -> List[Dict[str, Any]]:
        """
        Safely extract retriever results.
        """

        if not retrieval_result:
            return []

        if isinstance(
            retrieval_result,
            list,
        ):

            return [
                item
                for item in retrieval_result
                if isinstance(
                    item,
                    dict,
                )
            ]

        if isinstance(
            retrieval_result,
            dict,
        ):

            results = retrieval_result.get(
                "results",
                [],
            )

            if isinstance(
                results,
                list,
            ):

                return [
                    item
                    for item in results
                    if isinstance(
                        item,
                        dict,
                    )
                ]

        return []

    # =========================================================
    # Raw Score Extraction
    # =========================================================

    def _extract_raw_score(
        self,
        result,
        raw_key,
    ) -> float:
        """
        Prefer explicit retriever raw score.

        Fall back to `score` for backward compatibility with
        retrievers that have not yet been migrated.
        """

        if raw_key in result:

            return self._safe_float(result.get(raw_key))

        return self._safe_float(
            result.get(
                "score",
                0.0,
            )
        )

    # =========================================================
    # Normalize Retriever Scores
    # =========================================================

    def _add_retriever_results(
        self,
        final_scores,
        retrieval_result,
        retriever_name,
        raw_key,
        normalized_key,
    ):
        """
        Merge one retriever into the hybrid score structure.

        Normalization is performed using RAW evidence rather
        than retriever ranking score.
        """

        results = self._get_results(retrieval_result)

        valid_results = []

        # -----------------------------------------------------
        # Collect valid raw scores
        # -----------------------------------------------------

        for result in results:

            obj = result.get("knowledge")

            if obj is None:
                continue

            obj_id = getattr(
                obj,
                "id",
                None,
            )

            if obj_id is None:
                continue

            raw_score = self._extract_raw_score(
                result=result,
                raw_key=raw_key,
            )

            # Negative scores should not create positive
            # hybrid evidence.
            normalization_value = max(
                0.0,
                raw_score,
            )

            valid_results.append(
                (
                    result,
                    obj,
                    obj_id,
                    raw_score,
                    normalization_value,
                )
            )

        if not valid_results:
            return

        # -----------------------------------------------------
        # Maximum positive score
        # -----------------------------------------------------

        max_score = max(item[4] for item in valid_results)

        if max_score <= 0.0:
            max_score = 1.0

        # -----------------------------------------------------
        # Merge
        # -----------------------------------------------------

        for (
            result,
            obj,
            obj_id,
            raw_score,
            normalization_value,
        ) in valid_results:

            if obj_id not in final_scores:

                final_scores[obj_id] = self._create_item(obj)

            item = final_scores[obj_id]

            item[raw_key] = float(raw_score)

            item[normalized_key] = min(
                1.0,
                max(
                    0.0,
                    normalization_value / max_score,
                ),
            )

            if normalization_value > 0:

                item["retrievers"].add(retriever_name)

            # ---------------------------------------------
            # Preserve crop metadata
            # ---------------------------------------------

            crop_match = result.get("crop_match")

            if crop_match is True:

                item["crop_match"] = True

            elif crop_match is False and item["crop_match"] is None:

                item["crop_match"] = False

    # =========================================================
    # Main Ranking
    # =========================================================

    def rank(
        self,
        question,
        keyword_result,
        bm25_result,
        fuzzy_result,
        semantic_result,
    ):
        """
        Combine all retrieval signals into one ranked list.
        """

        final_scores = {}

        # =====================================================
        # 1. Keyword
        # =====================================================

        self._add_retriever_results(
            final_scores=final_scores,
            retrieval_result=keyword_result,
            retriever_name="keyword",
            raw_key="keyword_raw_score",
            normalized_key="keyword_score",
        )

        # =====================================================
        # 2. BM25
        # =====================================================

        self._add_retriever_results(
            final_scores=final_scores,
            retrieval_result=bm25_result,
            retriever_name="bm25",
            raw_key="bm25_raw_score",
            normalized_key="bm25_score",
        )

        # =====================================================
        # 3. Fuzzy
        # =====================================================

        self._add_retriever_results(
            final_scores=final_scores,
            retrieval_result=fuzzy_result,
            retriever_name="fuzzy",
            raw_key="fuzzy_raw_score",
            normalized_key="fuzzy_score",
        )

        # =====================================================
        # 4. Semantic
        # =====================================================

        self._add_retriever_results(
            final_scores=final_scores,
            retrieval_result=semantic_result,
            retriever_name="semantic",
            raw_key="semantic_raw_score",
            normalized_key="semantic_score",
        )

        # =====================================================
        # No Retrieval Candidates
        # =====================================================

        if not final_scores:

            return []

        # =====================================================
        # 5. Direct Question Similarity
        # =====================================================

        for item in final_scores.values():

            obj = item["knowledge"]

            try:

                question_score = self.question_similarity.score(
                    question,
                    obj,
                )

            except Exception as exc:

                print(
                    "QUESTION SIMILARITY ERROR:",
                    getattr(
                        obj,
                        "id",
                        None,
                    ),
                    str(exc),
                )

                question_score = 0.0

            question_score = self._safe_float(question_score)

            # QuestionSimilarity is expected to return
            # 0.0 -> 1.0.

            question_score = min(
                1.0,
                max(
                    0.0,
                    question_score,
                ),
            )

            item["question_raw_score"] = question_score

            item["question_score"] = question_score

        # =====================================================
        # 6. Calculate Hybrid Scores
        # =====================================================

        ranked = []

        for item in final_scores.values():

            base_score = (
                item["keyword_score"] * self.KEYWORD_WEIGHT
                + item["bm25_score"] * self.BM25_WEIGHT
                + item["fuzzy_score"] * self.FUZZY_WEIGHT
                + item["semantic_score"] * self.SEMANTIC_WEIGHT
                + item["question_score"] * self.QUESTION_WEIGHT
            )

            # =================================================
            # Retriever Agreement
            # =================================================

            agreement_count = self._agreement_count(item)

            agreement_bonus = (
                max(
                    0,
                    agreement_count - 1,
                )
                * self.AGREEMENT_BONUS_PER_RETRIEVER
            )

            agreement_bonus = min(
                agreement_bonus,
                self.MAX_AGREEMENT_BONUS,
            )

            final_score = min(
                1.0,
                base_score + agreement_bonus,
            )

            ranked.append(
                {
                    "knowledge": (item["knowledge"]),
                    # -------------------------------------
                    # Final hybrid score
                    # -------------------------------------
                    "score": float(final_score),
                    "hybrid_score": float(final_score),
                    "base_hybrid_score": float(base_score),
                    "agreement_bonus": float(agreement_bonus),
                    "agreement_count": int(agreement_count),
                    "retrievers": sorted(item["retrievers"]),
                    "crop_match": item["crop_match"],
                    # -------------------------------------
                    # Normalized scores
                    # -------------------------------------
                    "keyword_score": float(item["keyword_score"]),
                    "bm25_score": float(item["bm25_score"]),
                    "fuzzy_score": float(item["fuzzy_score"]),
                    "semantic_score": float(item["semantic_score"]),
                    "question_score": float(item["question_score"]),
                    # -------------------------------------
                    # Raw evidence
                    # -------------------------------------
                    "keyword_raw_score": float(item["keyword_raw_score"]),
                    "bm25_raw_score": float(item["bm25_raw_score"]),
                    "fuzzy_raw_score": float(item["fuzzy_raw_score"]),
                    "semantic_raw_score": float(item["semantic_raw_score"]),
                    "question_raw_score": float(item["question_raw_score"]),
                }
            )

        # =====================================================
        # 7. Final Sorting
        # =====================================================

        ranked.sort(
            key=self._sort_key,
            reverse=True,
        )

        # =====================================================
        # 8. Debug
        # =====================================================

        self._debug(
            question=question,
            ranked=ranked,
        )

        return ranked

    # =========================================================
    # Independent Retriever Agreement
    # =========================================================

    def _agreement_count(
        self,
        item,
    ) -> int:
        """
        Count meaningful independent retrieval signals.

        This is stricter than simply counting which retrievers
        returned the record.
        """

        count = 0

        if item["keyword_raw_score"] >= self.KEYWORD_AGREEMENT_MIN:
            count += 1

        if item["bm25_raw_score"] >= self.BM25_AGREEMENT_MIN:
            count += 1

        if item["fuzzy_raw_score"] >= self.FUZZY_AGREEMENT_MIN:
            count += 1

        if item["semantic_raw_score"] >= self.SEMANTIC_AGREEMENT_MIN:
            count += 1

        return count

    # =========================================================
    # Sorting
    # =========================================================

    @staticmethod
    def _sort_key(
        result,
    ):

        knowledge = result["knowledge"]

        try:

            priority = int(
                getattr(
                    knowledge,
                    "priority",
                    0,
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            priority = 0

        return (
            float(
                result.get(
                    "score",
                    0.0,
                )
            ),
            int(
                result.get(
                    "agreement_count",
                    0,
                )
            ),
            float(
                result.get(
                    "semantic_raw_score",
                    0.0,
                )
            ),
            float(
                result.get(
                    "question_raw_score",
                    0.0,
                )
            ),
            priority,
        )

    # =========================================================
    # Debug
    # =========================================================

    @staticmethod
    def _debug(
        question,
        ranked,
    ):

        print("\n" + "=" * 80)

        print("HYBRID RANKING")

        print("=" * 80)

        print(
            "Question :",
            question,
        )

        print(
            "Candidates:",
            len(ranked),
        )

        print("-" * 80)

        if not ranked:

            print("No hybrid candidates.")

        for result in ranked[:10]:

            knowledge = result["knowledge"]

            print(
                "Hybrid Score :",
                round(
                    result["score"],
                    4,
                ),
            )

            print(
                "Agreement    :",
                result["agreement_count"],
            )

            print(
                "Retrievers   :",
                result["retrievers"],
            )

            print(
                "Crop         :",
                getattr(
                    knowledge,
                    "crop",
                    "",
                ),
            )

            print(
                "Question     :",
                getattr(
                    knowledge,
                    "question",
                    "",
                ),
            )

            print(
                "RAW -> "
                f"KW={result['keyword_raw_score']:.4f} | "
                f"BM25={result['bm25_raw_score']:.4f} | "
                f"FUZZY={result['fuzzy_raw_score']:.4f} | "
                f"SEM={result['semantic_raw_score']:.4f} | "
                f"Q={result['question_raw_score']:.4f}"
            )

            print("-" * 80)

        print("=" * 80 + "\n")
