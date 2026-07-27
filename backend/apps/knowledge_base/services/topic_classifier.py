import re
from typing import Any, Dict, List, Optional, Set, Tuple

from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vocabulary_service import VocabularyService


class TopicClassifier:
    """
    Universal agricultural topic classifier.

    Responsibilities:
    - Detect the agricultural topic of a farmer query
    - Support Hindi / English / Hinglish queries
    - Use dynamic vocabulary from VocabularyService
    - Use Knowledge database categories/domains/subcategories
    - Support multiple topics in one query
    - Return confidence and matched evidence
    - Avoid crop-specific hardcoding

    Examples of topics:
    - fertilizer
    - disease
    - pest
    - irrigation
    - seed
    - soil
    - weather
    - market
    - scheme
    - harvest
    - storage
    - weed
    - general

    Important:
    Topic classification helps retrieval filtering/ranking.
    It does NOT generate agricultural advice.
    """

    GENERAL_TOPIC = "general"

    # =========================================================
    # Core universal topic vocabulary
    # =========================================================
    #
    # This is topic vocabulary, NOT crop vocabulary.
    #
    # It is safe to keep generic agricultural concepts here
    # because they represent query intent/categories rather
    # than a fixed list of supported crops.
    # =========================================================

    TOPIC_ALIASES = {
        "fertilizer": {
            "fertilizer",
            "fertiliser",
            "fertilizers",
            "fertilisers",
            "खाद",
            "उर्वरक",
            "पोषक तत्व",
            "nutrient",
            "nutrients",
            "manure",
            "खाद डालें",
            "खाद डालना",
            "उर्वरक डालें",
            "fertilizer dose",
        },
        "disease": {
            "disease",
            "diseases",
            "रोग",
            "बीमारी",
            "बीमार",
            "फसल रोग",
            "crop disease",
            "infection",
            "संक्रमण",
            "fungal disease",
            "bacterial disease",
            "viral disease",
            "फफूंद",
            "फफूंदी",
        },
        "pest": {
            "pest",
            "pests",
            "कीट",
            "कीड़ा",
            "कीड़े",
            "कीट नियंत्रण",
            "pest control",
            "insect",
            "insects",
            "इल्ली",
            "सुंडी",
        },
        "irrigation": {
            "irrigation",
            "सिंचाई",
            "पानी",
            "पानी देना",
            "पानी दें",
            "water requirement",
            "watering",
            "drip irrigation",
            "sprinkler",
            "ड्रिप",
        },
        "seed": {
            "seed",
            "seeds",
            "बीज",
            "बीज उपचार",
            "seed treatment",
            "variety",
            "varieties",
            "किस्म",
            "किस्में",
            "बुवाई",
            "बोवाई",
            "sowing",
            "germination",
            "अंकुरण",
        },
        "soil": {
            "soil",
            "मिट्टी",
            "मृदा",
            "soil test",
            "soil testing",
            "मिट्टी परीक्षण",
            "मृदा परीक्षण",
            "ph",
            "soil ph",
            "भूमि",
        },
        "weather": {
            "weather",
            "मौसम",
            "बारिश",
            "वर्षा",
            "rain",
            "rainfall",
            "temperature",
            "तापमान",
            "humidity",
            "नमी",
            "forecast",
            "पूर्वानुमान",
        },
        "market": {
            "market",
            "मंडी",
            "भाव",
            "कीमत",
            "price",
            "prices",
            "market price",
            "mandi price",
            "रेट",
            "rate",
            "बाजार",
            "बाजार भाव",
        },
        "scheme": {
            "scheme",
            "schemes",
            "योजना",
            "सरकारी योजना",
            "government scheme",
            "subsidy",
            "सब्सिडी",
            "अनुदान",
            "insurance",
            "बीमा",
            "crop insurance",
            "फसल बीमा",
        },
        "harvest": {
            "harvest",
            "harvesting",
            "कटाई",
            "फसल कटाई",
            "maturity",
            "पकना",
            "पकने",
            "mature",
            "ready for harvest",
        },
        "storage": {
            "storage",
            "भंडारण",
            "स्टोरेज",
            "store",
            "गोदाम",
            "warehouse",
            "grain storage",
            "अनाज भंडारण",
            "संग्रहण",
        },
        "weed": {
            "weed",
            "weeds",
            "खरपतवार",
            "खरपतवारनाशी",
            "weedicide",
            "herbicide",
            "weed control",
            "खरपतवार नियंत्रण",
        },
    }

    # =========================================================
    # Django category/domain -> canonical topic
    # =========================================================

    TOPIC_CANONICAL_MAP = {
        "fertilizer": "fertilizer",
        "fertiliser": "fertilizer",
        "nutrient": "fertilizer",
        "nutrients": "fertilizer",
        "disease": "disease",
        "diseases": "disease",
        "pest": "pest",
        "pests": "pest",
        "insect": "pest",
        "irrigation": "irrigation",
        "water": "irrigation",
        "seed": "seed",
        "seeds": "seed",
        "sowing": "seed",
        "variety": "seed",
        "soil": "soil",
        "weather": "weather",
        "market": "market",
        "scheme": "scheme",
        "government scheme": "scheme",
        "harvest": "harvest",
        "harvesting": "harvest",
        "storage": "storage",
        "weed": "weed",
        "weeds": "weed",
        "herbicide": "weed",
        "general": "general",
    }

    def __init__(self):
        self.normalizer = QuestionNormalizer()
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

    # =========================================================
    # Canonical Topic
    # =========================================================

    def canonicalize(
        self,
        topic: str,
    ) -> str:
        """
        Convert database/category/domain values into a stable
        canonical topic when possible.
        """

        topic = self._clean_value(topic)

        if not topic:
            return self.GENERAL_TOPIC

        normalized = self._normalize(topic)

        # Direct mapping
        if normalized in self.TOPIC_CANONICAL_MAP:
            return self.TOPIC_CANONICAL_MAP[normalized]

        lower_topic = topic.lower()

        if lower_topic in self.TOPIC_CANONICAL_MAP:
            return self.TOPIC_CANONICAL_MAP[lower_topic]

        # Check known topic aliases
        for canonical, aliases in self._build_topic_aliases().items():

            canonical_normalized = self._normalize(canonical)

            if normalized == canonical_normalized:
                return canonical

            for alias in aliases:

                if normalized == self._normalize(alias):
                    return canonical

        # Preserve unknown database topic rather than deleting it.
        return lower_topic

    # =========================================================
    # Dynamic Topic Vocabulary
    # =========================================================

    def _build_topic_aliases(
        self,
    ) -> Dict[str, Set[str]]:
        """
        Combine:
        - generic agricultural topic vocabulary
        - agriculture_terms.json vocabulary
        - current database categories
        - current database domains
        - current database subcategories

        This allows future knowledge imports to extend the
        classifier without requiring crop-specific code changes.
        """

        result: Dict[str, Set[str]] = {
            topic: set(aliases) for topic, aliases in self.TOPIC_ALIASES.items()
        }

        # -----------------------------------------------------
        # Agriculture term vocabulary
        # -----------------------------------------------------

        try:
            term_alias_map = self.vocabulary.get_term_alias_map()

            for alias, canonical in term_alias_map.items():

                canonical_topic = self._canonicalize_without_dynamic_lookup(canonical)

                if canonical_topic in result:

                    result[canonical_topic].add(alias)
                    result[canonical_topic].add(canonical)

        except Exception:
            pass

        # -----------------------------------------------------
        # Database vocabulary
        # -----------------------------------------------------

        dynamic_values = []

        try:
            dynamic_values.extend(self.vocabulary.get_categories())
        except Exception:
            pass

        try:
            dynamic_values.extend(self.vocabulary.get_domains())
        except Exception:
            pass

        try:
            dynamic_values.extend(self.vocabulary.get_subcategories())
        except Exception:
            pass

        for value in dynamic_values:

            value = self._clean_value(value)

            if not value:
                continue

            canonical = self._canonicalize_without_dynamic_lookup(value)

            if canonical == self.GENERAL_TOPIC:
                continue

            result.setdefault(
                canonical,
                set(),
            )

            result[canonical].add(value)

        return result

    def _canonicalize_without_dynamic_lookup(
        self,
        value: str,
    ) -> str:
        """
        Internal canonicalizer that avoids recursive calls to
        _build_topic_aliases().
        """

        value = self._clean_value(value)

        if not value:
            return self.GENERAL_TOPIC

        normalized = self._normalize(value)
        lower_value = value.lower()

        if normalized in self.TOPIC_CANONICAL_MAP:
            return self.TOPIC_CANONICAL_MAP[normalized]

        if lower_value in self.TOPIC_CANONICAL_MAP:
            return self.TOPIC_CANONICAL_MAP[lower_value]

        # Check static aliases only.
        for canonical, aliases in self.TOPIC_ALIASES.items():

            if normalized == self._normalize(canonical):
                return canonical

            for alias in aliases:

                if normalized == self._normalize(alias):
                    return canonical

        return lower_value

    # =========================================================
    # Phrase Matching
    # =========================================================

    @staticmethod
    def _contains_phrase(
        text: str,
        phrase: str,
    ) -> bool:

        if not text or not phrase:
            return False

        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"

        return bool(
            re.search(
                pattern,
                text,
                flags=re.UNICODE | re.IGNORECASE,
            )
        )

    # =========================================================
    # Topic Scoring
    # =========================================================

    def _score_topics(
        self,
        text: str,
    ) -> Dict[str, Dict]:
        """
        Score all topics against a query.

        Longer/multi-word phrases receive more weight because
        they usually carry stronger intent.

        Example:
            "मिट्टी परीक्षण"
        is stronger evidence than:
            "मिट्टी"
        """

        normalized_text = self._normalize(text)

        if not normalized_text:
            return {}

        topic_aliases = self._build_topic_aliases()

        results = {}

        for topic, aliases in topic_aliases.items():

            matched_terms = []
            score = 0.0

            candidates = set(aliases)
            candidates.add(topic)

            # Longest phrases first
            candidates = sorted(
                candidates,
                key=lambda value: (
                    len(str(value).split()),
                    len(str(value)),
                ),
                reverse=True,
            )

            used_normalized_terms = set()

            for alias in candidates:

                normalized_alias = self._normalize(alias)

                if not normalized_alias:
                    continue

                if normalized_alias in used_normalized_terms:
                    continue

                if not self._contains_phrase(
                    normalized_text,
                    normalized_alias,
                ):
                    continue

                used_normalized_terms.add(normalized_alias)

                word_count = len(normalized_alias.split())

                # Multi-word phrases are stronger.
                if word_count >= 3:
                    weight = 4.0
                elif word_count == 2:
                    weight = 3.0
                else:
                    weight = 2.0

                # Longer single concepts get a small bonus.
                if len(normalized_alias) >= 8:
                    weight += 0.5

                score += weight

                matched_terms.append(self._clean_value(alias))

            if score > 0:

                results[topic] = {
                    "score": round(score, 4),
                    "matched_terms": list(dict.fromkeys(matched_terms)),
                }

        return results

    # =========================================================
    # Detect Topics
    # =========================================================

    def detect_topics(
        self,
        text: str,
    ) -> List[Dict]:
        """
        Return all detected topics ordered by confidence.

        Example:

        [
            {
                "topic": "fertilizer",
                "score": 5.0,
                "confidence": 1.0,
                "matched_terms": ["खाद"]
            }
        ]
        """

        scores = self._score_topics(text)

        if not scores:
            return []

        maximum_score = max(item["score"] for item in scores.values())

        results = []

        for topic, data in scores.items():

            if maximum_score > 0:
                confidence = data["score"] / maximum_score
            else:
                confidence = 0.0

            results.append(
                {
                    "topic": topic,
                    "score": data["score"],
                    "confidence": round(
                        min(confidence, 1.0),
                        4,
                    ),
                    "matched_terms": data["matched_terms"],
                }
            )

        results.sort(
            key=lambda item: (
                item["score"],
                len(item["matched_terms"]),
            ),
            reverse=True,
        )

        return results

    # =========================================================
    # Main Classification
    # =========================================================

    def classify(
        self,
        text: str,
    ) -> Dict:
        """
        Main public classifier.

        Returns:

        {
            "topic": "fertilizer",
            "topics": ["fertilizer"],
            "topic_detected": True,
            "multiple_topics": False,
            "confidence": 1.0,
            "matched_terms": ["खाद"],
            "details": [...]
        }
        """

        text = self._clean_value(text)

        if not text:

            return {
                "topic": self.GENERAL_TOPIC,
                "topics": [],
                "topic_detected": False,
                "multiple_topics": False,
                "confidence": 0.0,
                "matched_terms": [],
                "details": [],
            }

        detected = self.detect_topics(text)

        if not detected:

            return {
                "topic": self.GENERAL_TOPIC,
                "topics": [],
                "topic_detected": False,
                "multiple_topics": False,
                "confidence": 0.0,
                "matched_terms": [],
                "details": [],
            }

        primary = detected[0]

        topics = [item["topic"] for item in detected]

        return {
            "topic": primary["topic"],
            "topics": topics,
            "topic_detected": True,
            "multiple_topics": len(topics) > 1,
            "confidence": primary["confidence"],
            "matched_terms": primary["matched_terms"],
            "details": detected,
        }

    # =========================================================
    # Primary Topic
    # =========================================================

    def get_primary_topic(
        self,
        text: str,
    ) -> str:

        return self.classify(text)["topic"]

    # =========================================================
    # Topic Equality
    # =========================================================

    def same_topic(
        self,
        topic_a: str,
        topic_b: str,
    ) -> bool:

        if not topic_a or not topic_b:
            return False

        canonical_a = self.canonicalize(topic_a)

        canonical_b = self.canonicalize(topic_b)

        return canonical_a == canonical_b

    # =========================================================
    # Knowledge Topic Extraction
    # =========================================================

    def get_knowledge_topics(
        self,
        knowledge,
    ) -> List[str]:
        """
        Extract possible topics from a Knowledge object using:

        - category
        - domain
        - subcategory
        - question
        - keywords

        This helps when imported data uses slightly different
        metadata structures.
        """

        if knowledge is None:
            return []

        topics = []

        # -----------------------------------------------------
        # Structured metadata first
        # -----------------------------------------------------

        structured_fields = [
            getattr(
                knowledge,
                "category",
                "",
            ),
            getattr(
                knowledge,
                "domain",
                "",
            ),
            getattr(
                knowledge,
                "subcategory",
                "",
            ),
        ]

        for value in structured_fields:

            value = self._clean_value(value)

            if not value:
                continue

            canonical = self.canonicalize(value)

            if (
                canonical
                and canonical != self.GENERAL_TOPIC
                and canonical not in topics
            ):
                topics.append(canonical)

        # -----------------------------------------------------
        # Detect topic from question/keywords if metadata
        # is missing or incomplete.
        # -----------------------------------------------------

        text_fields = [
            getattr(
                knowledge,
                "question",
                "",
            ),
            getattr(
                knowledge,
                "keywords",
                "",
            ),
        ]

        combined_text = " ".join(str(value) for value in text_fields if value)

        if combined_text:

            detected = self.detect_topics(combined_text)

            for item in detected:

                topic = item["topic"]

                if topic != self.GENERAL_TOPIC and topic not in topics:
                    topics.append(topic)

        return topics

    # =========================================================
    # Topic Compatibility
    # =========================================================

    def check_compatibility(
        self,
        query_text: str,
        knowledge,
    ) -> Dict:
        """
        Compare query topic with retrieved Knowledge topic.

        Important:
        Topic mismatch is useful evidence, but should generally
        be combined with crop/retrieval scores before hard
        rejection.

        Example:
            Query:
                soybean disease treatment

            Retrieved:
                category = Fertilizer

            Result:
                is_compatible = False
        """

        query_result = self.classify(query_text)

        query_topics = query_result["topics"]

        knowledge_topics = self.get_knowledge_topics(knowledge)

        # No explicit topic in query.
        if not query_topics:

            return {
                "is_compatible": True,
                "status": "query_topic_not_explicit",
                "query_topic": self.GENERAL_TOPIC,
                "query_topics": [],
                "knowledge_topics": knowledge_topics,
                "reason": (
                    "No explicit agricultural topic " "was detected in the query."
                ),
            }

        # Knowledge has no usable topic metadata.
        if not knowledge_topics:

            return {
                "is_compatible": True,
                "status": "knowledge_topic_unknown",
                "query_topic": query_result["topic"],
                "query_topics": query_topics,
                "knowledge_topics": [],
                "reason": ("Retrieved knowledge has no " "detectable topic metadata."),
            }

        for query_topic in query_topics:

            for knowledge_topic in knowledge_topics:

                if self.same_topic(
                    query_topic,
                    knowledge_topic,
                ):

                    return {
                        "is_compatible": True,
                        "status": "topic_match",
                        "query_topic": query_result["topic"],
                        "query_topics": query_topics,
                        "knowledge_topics": (knowledge_topics),
                        "reason": ("Query topic matches " "retrieved knowledge topic."),
                    }

        return {
            "is_compatible": False,
            "status": "topic_mismatch",
            "query_topic": query_result["topic"],
            "query_topics": query_topics,
            "knowledge_topics": knowledge_topics,
            "reason": (
                "Query agricultural topic does not " "match retrieved knowledge topic."
            ),
        }

    # =========================================================
    # Topic Switch Detection
    # =========================================================

    def detect_topic_switch(
        self,
        current_text: str,
        previous_topic: Optional[str],
    ) -> Dict:
        """
        Detect explicit topic changes in a conversation.

        Example:
            Previous topic: fertilizer
            New question: इसमें कौन सा रोग लगता है?

        Result:
            topic_switched = True
            current_topic = disease
        """

        result = self.classify(current_text)

        current_topic = result["topic"] if result["topic_detected"] else None

        previous_topic = self._clean_value(previous_topic)

        if not current_topic:

            return {
                "topic_switched": False,
                "current_topic": None,
                "previous_topic": (previous_topic or None),
                "explicit_topic": False,
            }

        if not previous_topic:

            return {
                "topic_switched": False,
                "current_topic": current_topic,
                "previous_topic": None,
                "explicit_topic": True,
            }

        switched = not self.same_topic(
            current_topic,
            previous_topic,
        )

        return {
            "topic_switched": switched,
            "current_topic": current_topic,
            "previous_topic": self.canonicalize(previous_topic),
            "explicit_topic": True,
        }

    # =========================================================
    # Database Topics
    # =========================================================

    def get_database_topics(
        self,
    ) -> List[str]:
        """
        Return canonical topics represented in active
        database knowledge.
        """

        values = set()

        try:
            values.update(self.vocabulary.get_categories())
        except Exception:
            pass

        try:
            values.update(self.vocabulary.get_domains())
        except Exception:
            pass

        topics = []

        for value in values:

            canonical = self.canonicalize(value)

            if canonical and canonical not in topics:
                topics.append(canonical)

        return sorted(
            topics,
            key=str.casefold,
        )

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        text: str,
    ) -> Dict:

        result = self.classify(text)

        print("\n" + "=" * 80)
        print("TOPIC CLASSIFIER")
        print("=" * 80)

        print(
            "Text             :",
            text,
        )

        print(
            "Primary Topic    :",
            result["topic"],
        )

        print(
            "Detected Topics  :",
            result["topics"],
        )

        print(
            "Multiple Topics  :",
            result["multiple_topics"],
        )

        print(
            "Confidence       :",
            result["confidence"],
        )

        print(
            "Matched Terms    :",
            result["matched_terms"],
        )

        print("=" * 80 + "\n")

        return result
