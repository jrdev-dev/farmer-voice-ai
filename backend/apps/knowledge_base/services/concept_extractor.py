import re
from typing import Any, Dict, List, Optional

from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vocabulary_service import VocabularyService
from apps.knowledge_base.services.crop_resolver import CropResolver
from apps.knowledge_base.services.topic_classifier import TopicClassifier


class ConceptExtractor:
    """
    Universal agricultural concept extractor.

    Converts a farmer query into structured information that
    can later be used by:

    - QueryAnalyzer
    - SearchEngine
    - RetrieverService
    - RelevanceService
    - Conversation memory
    - RAG generation

    Extracts:
    - Crop / crops
    - Agricultural topic / topics
    - Agricultural vocabulary terms
    - Numbers
    - Numeric ranges
    - Percentages
    - Quantities
    - Units
    - Time expressions
    - Growth stages
    - Database vocabulary matches

    Important:
    This service does NOT generate agricultural advice.

    It only extracts information explicitly present in the
    farmer's query or recognized by trusted project vocabulary.
    """

    # =========================================================
    # Units
    # =========================================================

    UNIT_ALIASES = {
        # Weight
        "kg": {
            "kg",
            "kgs",
            "kilogram",
            "kilograms",
            "किलो",
            "किलोग्राम",
        },
        "g": {
            "g",
            "gm",
            "gms",
            "gram",
            "grams",
            "ग्राम",
        },
        "mg": {
            "mg",
            "milligram",
            "milligrams",
            "मिलीग्राम",
        },
        "quintal": {
            "quintal",
            "quintals",
            "क्विंटल",
        },
        "ton": {
            "ton",
            "tons",
            "tonne",
            "tonnes",
            "टन",
        },
        # Liquid
        "ml": {
            "ml",
            "millilitre",
            "millilitres",
            "milliliter",
            "milliliters",
            "मिलीलीटर",
        },
        "l": {
            "l",
            "ltr",
            "litre",
            "litres",
            "liter",
            "liters",
            "लीटर",
        },
        # Land
        "acre": {
            "acre",
            "acres",
            "एकड़",
            "एकड़",
        },
        "hectare": {
            "hectare",
            "hectares",
            "ha",
            "हेक्टेयर",
        },
        "bigha": {
            "bigha",
            "बीघा",
        },
        # Length
        "mm": {
            "mm",
            "millimeter",
            "millimeters",
            "millimetre",
            "millimetres",
            "मिमी",
            "मिलीमीटर",
        },
        "cm": {
            "cm",
            "centimeter",
            "centimeters",
            "centimetre",
            "centimetres",
            "सेमी",
            "सेंटीमीटर",
        },
        "m": {
            "meter",
            "meters",
            "metre",
            "metres",
            "मीटर",
        },
        # Time
        "day": {
            "day",
            "days",
            "दिन",
        },
        "week": {
            "week",
            "weeks",
            "सप्ताह",
            "हफ्ता",
            "हफ्ते",
        },
        "month": {
            "month",
            "months",
            "महीना",
            "महीने",
            "माह",
        },
        "hour": {
            "hour",
            "hours",
            "hr",
            "hrs",
            "घंटा",
            "घंटे",
        },
        # Percentage
        "percent": {
            "%",
            "percent",
            "percentage",
            "प्रतिशत",
        },
        # Temperature
        "celsius": {
            "°c",
            "celsius",
            "सेल्सियस",
        },
    }

    # =========================================================
    # Generic agricultural stage vocabulary
    # =========================================================

    STAGE_ALIASES = {
        "pre_sowing": {
            "before sowing",
            "pre sowing",
            "pre-sowing",
            "बुवाई से पहले",
            "बोवाई से पहले",
        },
        "sowing": {
            "sowing",
            "बुवाई",
            "बोवाई",
            "बोते समय",
            "बुवाई के समय",
        },
        "germination": {
            "germination",
            "अंकुरण",
            "अंकुर निकलना",
        },
        "seedling": {
            "seedling",
            "seedling stage",
            "पौध अवस्था",
            "पौधा अवस्था",
        },
        "vegetative": {
            "vegetative",
            "vegetative stage",
            "वानस्पतिक अवस्था",
        },
        "flowering": {
            "flowering",
            "flowering stage",
            "फूल",
            "फूल आना",
            "फूल आने",
            "फूल अवस्था",
        },
        "fruiting": {
            "fruiting",
            "fruiting stage",
            "फल अवस्था",
            "फल लगना",
            "फल आने",
        },
        "pod_formation": {
            "pod formation",
            "pod stage",
            "फली बनना",
            "फली अवस्था",
        },
        "grain_filling": {
            "grain filling",
            "grain filling stage",
            "दाना भरना",
            "दाना भरने",
        },
        "maturity": {
            "maturity",
            "maturity stage",
            "mature",
            "पकने",
            "पकना",
            "परिपक्वता",
        },
        "harvest": {
            "harvest",
            "harvesting",
            "कटाई",
            "कटाई के समय",
        },
        "post_harvest": {
            "post harvest",
            "post-harvest",
            "कटाई के बाद",
        },
    }

    def __init__(self):
        self.normalizer = QuestionNormalizer()
        self.vocabulary = VocabularyService()
        self.crop_resolver = CropResolver()
        self.topic_classifier = TopicClassifier()

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
    def _unique(values: List[Any]) -> List[Any]:

        result = []

        for value in values:

            if value not in result:
                result.append(value)

        return result

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
    # Numbers
    # =========================================================

    def extract_numbers(
        self,
        text: str,
    ) -> List[str]:
        """
        Extract standalone numeric values.

        Examples:
            5
            2.5
            20
        """

        text = self._clean_value(text)

        if not text:
            return []

        pattern = r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])"

        numbers = re.findall(
            pattern,
            text,
        )

        return self._unique(numbers)

    # =========================================================
    # Numeric Ranges
    # =========================================================

    def extract_ranges(
        self,
        text: str,
    ) -> List[Dict]:
        """
        Extract numeric ranges.

        Examples:
            15-20
            15 – 20
            2.5 to 3
            10 से 15
        """

        text = self._clean_value(text)

        if not text:
            return []

        pattern = r"(\d+(?:\.\d+)?)" r"\s*(?:-|–|—|to|से)\s*" r"(\d+(?:\.\d+)?)"

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        results = []

        for start, end in matches:

            results.append(
                {
                    "start": start,
                    "end": end,
                    "normalized": f"{start}-{end}",
                }
            )

        return results

    # =========================================================
    # Percentages
    # =========================================================

    def extract_percentages(
        self,
        text: str,
    ) -> List[str]:

        text = self._clean_value(text)

        if not text:
            return []

        pattern = r"\d+(?:\.\d+)?" r"\s*(?:%|percent|प्रतिशत)"

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        return self._unique([re.sub(r"\s+", " ", item).strip() for item in matches])

    # =========================================================
    # Unit Alias Map
    # =========================================================

    def _build_unit_alias_map(
        self,
    ) -> Dict[str, str]:

        alias_map = {}

        for canonical, aliases in self.UNIT_ALIASES.items():

            candidates = set(aliases)
            candidates.add(canonical)

            for alias in candidates:

                cleaned = self._clean_value(alias)

                if not cleaned:
                    continue

                normalized = cleaned.lower()

                alias_map[normalized] = canonical

        return alias_map

    # =========================================================
    # Unit Detection
    # =========================================================

    def extract_units(
        self,
        text: str,
    ) -> List[str]:

        text = self._clean_value(text)

        if not text:
            return []

        text_lower = text.lower()

        alias_map = self._build_unit_alias_map()

        matches = []

        aliases = sorted(
            alias_map.keys(),
            key=lambda item: (
                len(item.split()),
                len(item),
            ),
            reverse=True,
        )

        for alias in aliases:

            if alias == "%":

                if "%" in text_lower:
                    canonical = alias_map[alias]

                    if canonical not in matches:
                        matches.append(canonical)

                continue

            if self._contains_phrase(
                text_lower,
                alias,
            ):

                canonical = alias_map[alias]

                if canonical not in matches:
                    matches.append(canonical)

        return matches

    # =========================================================
    # Quantity Extraction
    # =========================================================

    def extract_quantities(
        self,
        text: str,
    ) -> List[Dict]:
        """
        Extract number + unit pairs.

        Examples:
            5 किलो
            2.5 kg
            20 लीटर
            15 दिन
            10 प्रतिशत

        This does not infer missing units.
        """

        text = self._clean_value(text)

        if not text:
            return []

        alias_map = self._build_unit_alias_map()

        aliases = sorted(
            alias_map.keys(),
            key=len,
            reverse=True,
        )

        escaped_aliases = [re.escape(alias) for alias in aliases if alias != "%"]

        unit_pattern = "|".join(escaped_aliases)

        if not unit_pattern:
            return []

        pattern = r"(?P<value>\d+(?:\.\d+)?)" r"\s*" r"(?P<unit>" + unit_pattern + r")"

        results = []

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        ):

            value = match.group("value")

            raw_unit = match.group("unit")

            canonical_unit = alias_map.get(
                raw_unit.lower(),
                raw_unit.lower(),
            )

            item = {
                "value": value,
                "unit": canonical_unit,
                "raw_unit": raw_unit,
                "text": match.group(0),
            }

            if item not in results:
                results.append(item)

        # Explicit percentage sign
        percent_pattern = r"(?P<value>\d+(?:\.\d+)?)" r"\s*%"

        for match in re.finditer(
            percent_pattern,
            text,
        ):

            item = {
                "value": match.group("value"),
                "unit": "percent",
                "raw_unit": "%",
                "text": match.group(0),
            }

            if item not in results:
                results.append(item)

        return results

    # =========================================================
    # Per-area / Rate Expressions
    # =========================================================

    def extract_rates(
        self,
        text: str,
    ) -> List[Dict]:
        """
        Detect common agricultural rate expressions.

        Examples:
            5 किलो प्रति एकड़
            20 kg per hectare
            2 litre/acre
        """

        text = self._clean_value(text)

        if not text:
            return []

        quantity_units = (
            r"kg|kgs|kilogram|kilograms|"
            r"किलो|किलोग्राम|"
            r"g|gm|gram|grams|ग्राम|"
            r"ml|millilitre|milliliter|मिलीलीटर|"
            r"l|ltr|litre|liter|लीटर"
        )

        area_units = (
            r"acre|acres|एकड़|एकड़|" r"hectare|hectares|ha|हेक्टेयर|" r"bigha|बीघा"
        )

        pattern = (
            r"(?P<value>\d+(?:\.\d+)?)"
            r"\s*"
            r"(?P<quantity_unit>" + quantity_units + r")"
            r"\s*"
            r"(?:/|per|प्रति)"
            r"\s*"
            r"(?P<area_unit>" + area_units + r")"
        )

        results = []

        unit_map = self._build_unit_alias_map()

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        ):

            quantity_unit_raw = match.group("quantity_unit")

            area_unit_raw = match.group("area_unit")

            results.append(
                {
                    "value": match.group("value"),
                    "quantity_unit": unit_map.get(
                        quantity_unit_raw.lower(),
                        quantity_unit_raw.lower(),
                    ),
                    "area_unit": unit_map.get(
                        area_unit_raw.lower(),
                        area_unit_raw.lower(),
                    ),
                    "text": match.group(0),
                }
            )

        return results

    # =========================================================
    # Time Expressions
    # =========================================================

    def extract_time_expressions(
        self,
        text: str,
    ) -> List[Dict]:

        quantities = self.extract_quantities(text)

        time_units = {
            "day",
            "week",
            "month",
            "hour",
        }

        results = []

        for item in quantities:

            if item["unit"] in time_units:
                results.append(item)

        return results

    # =========================================================
    # Stage Detection
    # =========================================================

    def extract_stages(
        self,
        text: str,
    ) -> List[str]:
        """
        Detect generic growth stages plus stage values dynamically
        discovered from the Knowledge database.
        """

        normalized_text = self._normalize(text)

        if not normalized_text:
            return []

        stage_aliases = {
            stage: set(aliases) for stage, aliases in self.STAGE_ALIASES.items()
        }

        # -----------------------------------------------------
        # Add database stages dynamically
        # -----------------------------------------------------

        try:
            database_stages = self.vocabulary.get_stages()

        except Exception:
            database_stages = set()

        for database_stage in database_stages:

            database_stage = self._clean_value(database_stage)

            if not database_stage:
                continue

            canonical = self._normalize(database_stage)

            if not canonical:
                continue

            stage_aliases.setdefault(
                canonical,
                set(),
            )

            stage_aliases[canonical].add(database_stage)

        detected = []

        for canonical, aliases in stage_aliases.items():

            candidates = set(aliases)
            candidates.add(canonical)

            candidates = sorted(
                candidates,
                key=lambda value: (
                    len(str(value).split()),
                    len(str(value)),
                ),
                reverse=True,
            )

            for alias in candidates:

                normalized_alias = self._normalize(alias)

                if not normalized_alias:
                    continue

                if self._contains_phrase(
                    normalized_text,
                    normalized_alias,
                ):

                    if canonical not in detected:
                        detected.append(canonical)

                    break

        return detected

    # =========================================================
    # Agricultural Vocabulary Terms
    # =========================================================

    def extract_agriculture_terms(
        self,
        text: str,
    ) -> List[str]:

        try:
            return self.vocabulary.detect_terms(text)

        except Exception:
            return []

    # =========================================================
    # Database Keyword Matches
    # =========================================================

    def extract_database_keywords(
        self,
        text: str,
    ) -> List[str]:
        """
        Match query against keywords already present in trusted
        Knowledge records.

        This lets imported datasets expand the vocabulary.
        """

        normalized_text = self._normalize(text)

        if not normalized_text:
            return []

        try:
            keywords = self.vocabulary.get_keywords()

        except Exception:
            return []

        matches = []

        sorted_keywords = sorted(
            keywords,
            key=lambda value: (
                len(str(value).split()),
                len(str(value)),
            ),
            reverse=True,
        )

        for keyword in sorted_keywords:

            normalized_keyword = self._normalize(keyword)

            if not normalized_keyword:
                continue

            if self._contains_phrase(
                normalized_text,
                normalized_keyword,
            ):

                if keyword not in matches:
                    matches.append(keyword)

        return matches

    # =========================================================
    # Main Extraction
    # =========================================================

    def extract(
        self,
        text: str,
    ) -> Dict:
        """
        Main public method.

        Example output:

        {
            "original_text": "...",
            "normalized_text": "...",

            "crop": "Soybean",
            "crops": ["Soybean"],
            "crop_detected": True,
            "crop_knowledge_available": True,

            "topic": "fertilizer",
            "topics": ["fertilizer"],
            "topic_detected": True,

            "agriculture_terms": [...],
            "database_keywords": [...],

            "numbers": ["5"],
            "ranges": [],
            "percentages": [],
            "quantities": [...],
            "rates": [...],
            "units": ["kg", "acre"],
            "time_expressions": [],
            "stages": []
        }
        """

        original_text = self._clean_value(text)

        normalized_text = self._normalize(original_text)

        # -----------------------------------------------------
        # Crop
        # -----------------------------------------------------

        crop_result = self.crop_resolver.resolve_query(original_text)

        # -----------------------------------------------------
        # Topic
        # -----------------------------------------------------

        topic_result = self.topic_classifier.classify(original_text)

        # -----------------------------------------------------
        # Other concepts
        # -----------------------------------------------------

        agriculture_terms = self.extract_agriculture_terms(original_text)

        database_keywords = self.extract_database_keywords(original_text)

        numbers = self.extract_numbers(original_text)

        ranges = self.extract_ranges(original_text)

        percentages = self.extract_percentages(original_text)

        quantities = self.extract_quantities(original_text)

        rates = self.extract_rates(original_text)

        units = self.extract_units(original_text)

        time_expressions = self.extract_time_expressions(original_text)

        stages = self.extract_stages(original_text)

        return {
            "original_text": original_text,
            "normalized_text": normalized_text,
            # Crop
            "crop": crop_result["crop"],
            "crops": crop_result["crops"],
            "crop_detected": crop_result["crop_detected"],
            "multiple_crops": crop_result["multiple_crops"],
            "crop_knowledge_available": crop_result["knowledge_available"],
            # Topic
            "topic": topic_result["topic"],
            "topics": topic_result["topics"],
            "topic_detected": topic_result["topic_detected"],
            "multiple_topics": topic_result["multiple_topics"],
            "topic_confidence": topic_result["confidence"],
            "topic_matched_terms": topic_result["matched_terms"],
            # Vocabulary
            "agriculture_terms": agriculture_terms,
            "database_keywords": database_keywords,
            # Numeric concepts
            "numbers": numbers,
            "ranges": ranges,
            "percentages": percentages,
            "quantities": quantities,
            "rates": rates,
            "units": units,
            # Contextual concepts
            "time_expressions": time_expressions,
            "stages": stages,
        }

    # =========================================================
    # Compact Retrieval Concepts
    # =========================================================

    def get_retrieval_concepts(
        self,
        text: str,
    ) -> Dict:
        """
        Return only concepts useful to retrieval/ranking.

        This prevents downstream services from needing to know
        every detail of the full extraction result.
        """

        result = self.extract(text)

        return {
            "crop": result["crop"],
            "crops": result["crops"],
            "topic": result["topic"],
            "topics": result["topics"],
            "stages": result["stages"],
            "agriculture_terms": result["agriculture_terms"],
            "database_keywords": result["database_keywords"],
            "numbers": result["numbers"],
            "units": result["units"],
        }

    # =========================================================
    # Does Query Contain Agricultural Concepts?
    # =========================================================

    def has_agricultural_concepts(
        self,
        text: str,
    ) -> bool:

        result = self.extract(text)

        return bool(
            result["crop_detected"]
            or result["topic_detected"]
            or result["agriculture_terms"]
            or result["database_keywords"]
            or result["stages"]
        )

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        text: str,
    ) -> Dict:

        result = self.extract(text)

        print("\n" + "=" * 80)
        print("CONCEPT EXTRACTOR")
        print("=" * 80)

        print(
            "Original       :",
            result["original_text"],
        )

        print(
            "Normalized     :",
            result["normalized_text"],
        )

        print("-" * 80)

        print(
            "Crop           :",
            result["crop"],
        )

        print(
            "Crops          :",
            result["crops"],
        )

        print(
            "Crop Knowledge :",
            result["crop_knowledge_available"],
        )

        print("-" * 80)

        print(
            "Topic          :",
            result["topic"],
        )

        print(
            "Topics         :",
            result["topics"],
        )

        print(
            "Topic Confidence:",
            result["topic_confidence"],
        )

        print("-" * 80)

        print(
            "Terms          :",
            result["agriculture_terms"],
        )

        print(
            "DB Keywords    :",
            result["database_keywords"],
        )

        print(
            "Stages         :",
            result["stages"],
        )

        print("-" * 80)

        print(
            "Numbers        :",
            result["numbers"],
        )

        print(
            "Ranges         :",
            result["ranges"],
        )

        print(
            "Quantities     :",
            result["quantities"],
        )

        print(
            "Rates          :",
            result["rates"],
        )

        print(
            "Units          :",
            result["units"],
        )

        print(
            "Time           :",
            result["time_expressions"],
        )

        print("=" * 80 + "\n")

        return result
