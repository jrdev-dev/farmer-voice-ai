import re
from typing import Any, Dict, List

from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.concept_extractor import ConceptExtractor
from apps.knowledge_base.services.crop_resolver import CropResolver
from apps.knowledge_base.services.topic_classifier import TopicClassifier
from apps.knowledge_base.services.vocabulary_service import VocabularyService


class QueryAnalyzer:
    """
    Universal agricultural query analyzer.

    Converts a farmer's raw question into a structured,
    retrieval-ready representation.

    Responsibilities:
    - Normalize farmer query
    - Extract agricultural concepts
    - Detect crop and topic
    - Build retrieval keywords
    - Build semantic query
    - Build lexical query
    - Identify crop/topic filters
    - Detect numeric constraints
    - Preserve multilingual query information
    - Avoid hardcoded crop dependencies

    This service does NOT:
    - Search the database
    - Decide final relevance
    - Generate agricultural advice
    """

    # Words that usually add little retrieval value.
    #
    # These are generic conversational/question words,
    # not agricultural vocabulary.
    STOPWORDS = {
        # Hindi
        "क्या",
        "कौन",
        "कौनसा",
        "कौनसी",
        "कौनसे",
        "कैसे",
        "कितना",
        "कितनी",
        "कितने",
        "कब",
        "कहाँ",
        "कहा",
        "क्यों",
        "मुझे",
        "मेरे",
        "मेरी",
        "मेरा",
        "हम",
        "हमें",
        "आप",
        "इसमें",
        "इसका",
        "इसके",
        "इसकेलिए",
        "के",
        "की",
        "का",
        "को",
        "से",
        "में",
        "पर",
        "और",
        "या",
        "तो",
        "है",
        "हैं",
        "था",
        "थी",
        "थे",
        "हो",
        "होगा",
        "होगी",
        "करें",
        "करना",
        "करूं",
        "करूँ",
        "बताओ",
        "बताएं",
        "बताइए",
        # English
        "what",
        "which",
        "when",
        "where",
        "why",
        "who",
        "whom",
        "whose",
        "how",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "the",
        "a",
        "an",
        "of",
        "to",
        "for",
        "from",
        "in",
        "on",
        "at",
        "with",
        "and",
        "or",
        "my",
        "me",
        "i",
        "we",
        "our",
        "you",
        "your",
        "please",
        "tell",
        "give",
        "should",
        "can",
        "could",
        "would",
    }

    def __init__(self):
        self.normalizer = QuestionNormalizer()
        self.concept_extractor = ConceptExtractor()
        self.crop_resolver = CropResolver()
        self.topic_classifier = TopicClassifier()
        self.vocabulary = VocabularyService()

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_value(value: Any) -> str:

        if value is None:
            return ""

        value = str(value).strip()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    def _normalize(
        self,
        value: Any,
    ) -> str:

        value = self._clean_value(value)

        if not value:
            return ""

        return self.normalizer.normalize(value)

    @staticmethod
    def _unique(
        values: List[Any],
    ) -> List[Any]:

        result = []

        for value in values:

            if value is None:
                continue

            if value not in result:
                result.append(value)

        return result

    # =========================================================
    # Tokenization
    # =========================================================

    def tokenize(
        self,
        text: str,
    ) -> List[str]:
        """
        Lightweight multilingual tokenizer.

        Keeps:
        - English words
        - Devanagari words
        - numbers
        - decimal numbers
        """

        text = self._clean_value(text)

        if not text:
            return []

        tokens = re.findall(
            r"[A-Za-z]+(?:[-'][A-Za-z]+)*" r"|[\u0900-\u097F]+" r"|\d+(?:\.\d+)?",
            text,
            flags=re.UNICODE,
        )

        return [token.strip() for token in tokens if token.strip()]

    # =========================================================
    # Stopword Detection
    # =========================================================

    def _is_stopword(
        self,
        token: str,
    ) -> bool:

        token = self._clean_value(token).lower()

        if not token:
            return True

        return token in self.STOPWORDS

    # =========================================================
    # Base Keywords
    # =========================================================

    def _extract_base_keywords(
        self,
        normalized_text: str,
    ) -> List[str]:

        tokens = self.tokenize(normalized_text)

        keywords = []

        for token in tokens:

            token = self._clean_value(token)

            if not token:
                continue

            if self._is_stopword(token):
                continue

            # Ignore isolated punctuation-like values.
            if not re.search(
                r"[A-Za-z\u0900-\u097F0-9]",
                token,
            ):
                continue

            keywords.append(token)

        return self._unique(keywords)

    # =========================================================
    # Retrieval Keywords
    # =========================================================

    def build_retrieval_keywords(
        self,
        concepts: Dict,
    ) -> List[str]:
        """
        Build high-value lexical retrieval keywords.

        Sources:
        - normalized query
        - crop
        - topic
        - agriculture vocabulary
        - DB keywords
        - growth stages

        Numeric values are intentionally handled separately.
        """

        keywords = []

        # -----------------------------------------------------
        # Base normalized query words
        # -----------------------------------------------------

        normalized_text = concepts.get(
            "normalized_text",
            "",
        )

        keywords.extend(self._extract_base_keywords(normalized_text))

        # -----------------------------------------------------
        # Crop concepts
        # -----------------------------------------------------

        for crop in concepts.get(
            "crops",
            [],
        ):

            normalized_crop = self._normalize(crop)

            if normalized_crop:
                keywords.append(normalized_crop)

        # -----------------------------------------------------
        # Topic concepts
        # -----------------------------------------------------

        for topic in concepts.get(
            "topics",
            [],
        ):

            normalized_topic = self._normalize(topic)

            if normalized_topic:
                keywords.append(normalized_topic)

        # -----------------------------------------------------
        # Agriculture vocabulary
        # -----------------------------------------------------

        for term in concepts.get(
            "agriculture_terms",
            [],
        ):

            normalized_term = self._normalize(term)

            if normalized_term:
                keywords.append(normalized_term)

        # -----------------------------------------------------
        # Database keywords
        # -----------------------------------------------------

        for keyword in concepts.get(
            "database_keywords",
            [],
        ):

            normalized_keyword = self._normalize(keyword)

            if normalized_keyword:
                keywords.append(normalized_keyword)

        # -----------------------------------------------------
        # Growth stages
        # -----------------------------------------------------

        for stage in concepts.get(
            "stages",
            [],
        ):

            normalized_stage = self._normalize(stage)

            if normalized_stage:
                keywords.append(normalized_stage)

        return self._unique([keyword for keyword in keywords if keyword])

    # =========================================================
    # Lexical Query
    # =========================================================

    def build_lexical_query(
        self,
        retrieval_keywords: List[str],
    ) -> str:
        """
        Compact query for keyword/BM25/fuzzy retrieval.
        """

        return " ".join(self._unique(retrieval_keywords)).strip()

    # =========================================================
    # Semantic Query
    # =========================================================

    def build_semantic_query(
        self,
        original_text: str,
        normalized_text: str,
        concepts: Dict,
    ) -> str:
        """
        Build semantic-search query.

        We preserve the normalized farmer question because
        sentence embeddings benefit from sentence context.

        Important concepts are appended only when they are not
        already represented in normalized text.
        """

        parts = []

        normalized_text = self._clean_value(normalized_text)

        if normalized_text:
            parts.append(normalized_text)

        concept_values = []

        concept_values.extend(
            concepts.get(
                "crops",
                [],
            )
        )

        concept_values.extend(
            concepts.get(
                "topics",
                [],
            )
        )

        concept_values.extend(
            concepts.get(
                "agriculture_terms",
                [],
            )
        )

        concept_values.extend(
            concepts.get(
                "stages",
                [],
            )
        )

        current_normalized = normalized_text.lower() if normalized_text else ""

        for value in concept_values:

            normalized_value = self._normalize(value)

            if not normalized_value:
                continue

            if normalized_value.lower() in current_normalized:
                continue

            parts.append(normalized_value)

        semantic_query = " ".join(self._unique(parts)).strip()

        # Fallback to original text.
        if not semantic_query:
            semantic_query = self._clean_value(original_text)

        return semantic_query

    # =========================================================
    # Retrieval Filters
    # =========================================================

    def build_filters(
        self,
        concepts: Dict,
    ) -> Dict:
        """
        Build safe structured retrieval hints.

        These are HINTS.

        Search services may use them for:
        - filtering
        - boosting
        - post-retrieval validation

        They should not automatically force a hard database
        filter unless the downstream service intentionally
        chooses to do so.
        """

        crop = concepts.get("crop")

        topic = concepts.get("topic")

        stages = concepts.get(
            "stages",
            [],
        )

        filters = {
            "crop": crop,
            "topic": (
                topic
                if concepts.get(
                    "topic_detected",
                    False,
                )
                else None
            ),
            "stages": stages,
        }

        return filters

    # =========================================================
    # Numeric Constraints
    # =========================================================

    def build_numeric_constraints(
        self,
        concepts: Dict,
    ) -> Dict:
        """
        Preserve explicitly stated numeric constraints.

        Useful for:
        - evidence validation
        - dose/rate retrieval
        - AnswerGuard
        """

        return {
            "numbers": concepts.get(
                "numbers",
                [],
            ),
            "ranges": concepts.get(
                "ranges",
                [],
            ),
            "percentages": concepts.get(
                "percentages",
                [],
            ),
            "quantities": concepts.get(
                "quantities",
                [],
            ),
            "rates": concepts.get(
                "rates",
                [],
            ),
            "units": concepts.get(
                "units",
                [],
            ),
            "time_expressions": concepts.get(
                "time_expressions",
                [],
            ),
        }

    # =========================================================
    # Query Specificity
    # =========================================================

    def calculate_specificity(
        self,
        concepts: Dict,
        retrieval_keywords: List[str],
    ) -> float:
        """
        Estimate how specific the farmer query is.

        This is NOT retrieval confidence.

        Higher specificity means the query contains more useful
        structured information such as crop/topic/stage/rate.
        """

        score = 0.0

        if concepts.get("crop_detected"):
            score += 0.30

        if concepts.get("topic_detected"):
            score += 0.25

        if concepts.get("stages"):
            score += 0.15

        if concepts.get("quantities"):
            score += 0.10

        if concepts.get("rates"):
            score += 0.10

        if concepts.get("database_keywords"):
            score += 0.05

        if len(retrieval_keywords) >= 3:
            score += 0.05

        return round(
            min(score, 1.0),
            4,
        )

    # =========================================================
    # Query Flags
    # =========================================================

    def build_flags(
        self,
        concepts: Dict,
    ) -> Dict:

        return {
            "has_crop": bool(concepts.get("crop_detected")),
            "multiple_crops": bool(concepts.get("multiple_crops")),
            "crop_knowledge_available": bool(concepts.get("crop_knowledge_available")),
            "has_topic": bool(concepts.get("topic_detected")),
            "multiple_topics": bool(concepts.get("multiple_topics")),
            "has_stage": bool(concepts.get("stages")),
            "has_numbers": bool(concepts.get("numbers")),
            "has_quantities": bool(concepts.get("quantities")),
            "has_rates": bool(concepts.get("rates")),
            "has_agricultural_concepts": bool(
                concepts.get("crop_detected")
                or concepts.get("topic_detected")
                or concepts.get("agriculture_terms")
                or concepts.get("database_keywords")
                or concepts.get("stages")
            ),
        }

    # =========================================================
    # Main Analyze
    # =========================================================

    def analyze(
        self,
        question: str,
    ) -> Dict:
        """
        Main public API.

        Returns a complete retrieval-ready query object.
        """

        original_question = self._clean_value(question)

        if not original_question:

            return self._empty_result()

        # -----------------------------------------------------
        # 1. Extract concepts
        # -----------------------------------------------------

        concepts = self.concept_extractor.extract(original_question)

        normalized_question = concepts.get(
            "normalized_text",
            "",
        )

        # -----------------------------------------------------
        # 2. Retrieval keywords
        # -----------------------------------------------------

        retrieval_keywords = self.build_retrieval_keywords(concepts)

        # -----------------------------------------------------
        # 3. Lexical query
        # -----------------------------------------------------

        lexical_query = self.build_lexical_query(retrieval_keywords)

        # -----------------------------------------------------
        # 4. Semantic query
        # -----------------------------------------------------

        semantic_query = self.build_semantic_query(
            original_text=original_question,
            normalized_text=normalized_question,
            concepts=concepts,
        )

        # -----------------------------------------------------
        # 5. Filters
        # -----------------------------------------------------

        filters = self.build_filters(concepts)

        # -----------------------------------------------------
        # 6. Numeric constraints
        # -----------------------------------------------------

        numeric_constraints = self.build_numeric_constraints(concepts)

        # -----------------------------------------------------
        # 7. Flags
        # -----------------------------------------------------

        flags = self.build_flags(concepts)

        # -----------------------------------------------------
        # 8. Query specificity
        # -----------------------------------------------------

        specificity = self.calculate_specificity(
            concepts,
            retrieval_keywords,
        )

        return {
            "original_question": (original_question),
            "normalized_question": (normalized_question),
            # Retrieval representations
            "lexical_query": lexical_query,
            "semantic_query": semantic_query,
            "retrieval_keywords": (retrieval_keywords),
            # Main concepts
            "crop": concepts.get("crop"),
            "crops": concepts.get(
                "crops",
                [],
            ),
            "topic": concepts.get(
                "topic",
                "general",
            ),
            "topics": concepts.get(
                "topics",
                [],
            ),
            "stages": concepts.get(
                "stages",
                [],
            ),
            # Additional vocabulary
            "agriculture_terms": concepts.get(
                "agriculture_terms",
                [],
            ),
            "database_keywords": concepts.get(
                "database_keywords",
                [],
            ),
            # Retrieval metadata
            "filters": filters,
            "numeric_constraints": (numeric_constraints),
            "flags": flags,
            "specificity": specificity,
            # Full extraction retained for downstream
            # debugging and future expansion.
            "concepts": concepts,
        }

    # =========================================================
    # Empty Result
    # =========================================================

    def _empty_result(
        self,
    ) -> Dict:

        return {
            "original_question": "",
            "normalized_question": "",
            "lexical_query": "",
            "semantic_query": "",
            "retrieval_keywords": [],
            "crop": None,
            "crops": [],
            "topic": "general",
            "topics": [],
            "stages": [],
            "agriculture_terms": [],
            "database_keywords": [],
            "filters": {
                "crop": None,
                "topic": None,
                "stages": [],
            },
            "numeric_constraints": {
                "numbers": [],
                "ranges": [],
                "percentages": [],
                "quantities": [],
                "rates": [],
                "units": [],
                "time_expressions": [],
            },
            "flags": {
                "has_crop": False,
                "multiple_crops": False,
                "crop_knowledge_available": False,
                "has_topic": False,
                "multiple_topics": False,
                "has_stage": False,
                "has_numbers": False,
                "has_quantities": False,
                "has_rates": False,
                "has_agricultural_concepts": False,
            },
            "specificity": 0.0,
            "concepts": {},
        }

    # =========================================================
    # Retrieval Query Convenience
    # =========================================================

    def get_retrieval_query(
        self,
        question: str,
    ) -> Dict:
        """
        Smaller representation for retrieval services.
        """

        analysis = self.analyze(question)

        return {
            "original_question": analysis["original_question"],
            "normalized_question": analysis["normalized_question"],
            "lexical_query": analysis["lexical_query"],
            "semantic_query": analysis["semantic_query"],
            "keywords": analysis["retrieval_keywords"],
            "crop": analysis["crop"],
            "crops": analysis["crops"],
            "topic": analysis["topic"],
            "topics": analysis["topics"],
            "stages": analysis["stages"],
            "filters": analysis["filters"],
            "numeric_constraints": analysis["numeric_constraints"],
            "specificity": analysis["specificity"],
        }

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        question: str,
    ) -> Dict:

        result = self.analyze(question)

        print("\n" + "=" * 80)
        print("QUERY ANALYZER")
        print("=" * 80)

        print(
            "Original Question   :",
            result["original_question"],
        )

        print(
            "Normalized Question :",
            result["normalized_question"],
        )

        print("-" * 80)

        print(
            "Crop                :",
            result["crop"],
        )

        print(
            "Crops               :",
            result["crops"],
        )

        print(
            "Topic               :",
            result["topic"],
        )

        print(
            "Topics              :",
            result["topics"],
        )

        print(
            "Stages              :",
            result["stages"],
        )

        print("-" * 80)

        print(
            "Keywords            :",
            result["retrieval_keywords"],
        )

        print(
            "Lexical Query       :",
            result["lexical_query"],
        )

        print(
            "Semantic Query      :",
            result["semantic_query"],
        )

        print("-" * 80)

        print(
            "Filters             :",
            result["filters"],
        )

        print(
            "Numeric Constraints :",
            result["numeric_constraints"],
        )

        print(
            "Specificity         :",
            result["specificity"],
        )

        print(
            "Flags               :",
            result["flags"],
        )

        print("=" * 80 + "\n")

        return result
