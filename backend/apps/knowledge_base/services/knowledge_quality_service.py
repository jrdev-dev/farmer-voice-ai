import re
from typing import Any, Dict, List, Optional


class KnowledgeQualityService:
    """
    Quality validation service for agricultural knowledge records.

    Purpose
    -------
    Checks whether a Knowledge record is suitable for:

    - Search indexing
    - BM25 retrieval
    - Semantic retrieval
    - RAG evidence
    - Farmer-facing answer generation

    Design principles
    -----------------
    1. No hardcoded crop list.
    2. No agricultural facts are invented.
    3. Missing optional metadata does not automatically reject
       otherwise useful knowledge.
    4. Critical missing fields are treated more seriously.
    5. Suspicious / malformed records can be rejected.
    6. Quality score is separate from factual correctness.

    Important
    ---------
    This service checks STRUCTURAL and TEXT QUALITY.

    It does NOT independently verify whether an agricultural
    recommendation is scientifically correct.

    Scientific trust should ultimately depend on:
    - source provenance
    - curated datasets
    - government/agricultural institution data
    - expert-reviewed knowledge
    """

    # =========================================================
    # Configuration
    # =========================================================

    MIN_QUESTION_LENGTH = 3

    MIN_ANSWER_LENGTH = 5

    MIN_SEARCH_TEXT_LENGTH = 5

    MAX_QUESTION_LENGTH = 2000

    MAX_ANSWER_LENGTH = 15000

    MAX_SEARCH_TEXT_LENGTH = 25000

    # Record can still be accepted with warnings.
    ACCEPTABLE_SCORE = 0.60

    # Below this score, record should generally not be used
    # as trusted RAG evidence.
    MIN_TRUSTED_SCORE = 0.45

    # =========================================================
    # Supported categories
    # =========================================================
    #
    # These mirror the current Knowledge.Category choices.
    # Unknown categories are WARNED rather than automatically
    # rejected, making future category expansion possible.
    # =========================================================

    KNOWN_CATEGORIES = {
        "disease",
        "pest",
        "fertilizer",
        "seed",
        "soil",
        "weather",
        "market",
        "scheme",
        "irrigation",
        "harvest",
        "storage",
        "general",
    }

    # =========================================================
    # Placeholder / low-quality values
    # =========================================================

    PLACEHOLDER_VALUES = {
        "",
        "-",
        "--",
        "---",
        "n/a",
        "na",
        "none",
        "null",
        "unknown",
        "undefined",
        "not available",
        "not applicable",
        "tbd",
        "todo",
        "test",
        "dummy",
        "sample",
        "placeholder",
        "जानकारी उपलब्ध नहीं",
        "उपलब्ध नहीं",
        "पता नहीं",
    }

    # =========================================================
    # Suspicious text patterns
    # =========================================================

    SUSPICIOUS_PATTERNS = {
        "html_script": re.compile(
            r"<\s*script\b",
            flags=re.IGNORECASE,
        ),
        "javascript": re.compile(
            r"javascript\s*:",
            flags=re.IGNORECASE,
        ),
        "sql_statement": re.compile(
            r"\b(?:drop|truncate)\s+table\b",
            flags=re.IGNORECASE,
        ),
        "template_placeholder": re.compile(
            r"\{\{.*?\}\}|\$\{.*?\}",
            flags=re.DOTALL,
        ),
    }

    def __init__(self):
        pass

    # =========================================================
    # Generic Helpers
    # =========================================================

    @staticmethod
    def _clean(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        value = str(value).strip()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    def _is_placeholder(
        self,
        value: Any,
    ) -> bool:

        value = self._clean(value).lower()

        return value in self.PLACEHOLDER_VALUES

    @staticmethod
    def _unique(
        values: List[Any],
    ) -> List[Any]:

        result = []

        for value in values:

            if value not in result:
                result.append(value)

        return result

    # =========================================================
    # Get Field Safely
    # =========================================================

    def _get(
        self,
        knowledge: Any,
        field: str,
        default=None,
    ):

        if knowledge is None:
            return default

        # Dictionary support
        if isinstance(
            knowledge,
            dict,
        ):

            return knowledge.get(
                field,
                default,
            )

        # Django model / object support
        return getattr(
            knowledge,
            field,
            default,
        )

    # =========================================================
    # Text Validation
    # =========================================================

    def _validate_text(
        self,
        value: Any,
        field_name: str,
        required: bool = False,
        min_length: int = 0,
        max_length: Optional[int] = None,
    ) -> Dict:

        text = self._clean(value)

        errors = []

        warnings = []

        if not text:

            if required:

                errors.append(f"{field_name} is missing.")

            return {
                "value": text,
                "errors": errors,
                "warnings": warnings,
            }

        if self._is_placeholder(text):

            if required:

                errors.append(f"{field_name} contains a placeholder value.")

            else:

                warnings.append(f"{field_name} contains a placeholder value.")

        if min_length and len(text) < min_length:

            if required:

                errors.append(f"{field_name} is too short.")

            else:

                warnings.append(f"{field_name} is unusually short.")

        if max_length and len(text) > max_length:

            warnings.append(f"{field_name} is unusually long.")

        return {
            "value": text,
            "errors": errors,
            "warnings": warnings,
        }

    # =========================================================
    # Suspicious Content Detection
    # =========================================================

    def _find_suspicious_patterns(
        self,
        text: Any,
    ) -> List[str]:

        text = self._clean(text)

        if not text:
            return []

        detected = []

        for (
            name,
            pattern,
        ) in self.SUSPICIOUS_PATTERNS.items():

            if pattern.search(text):

                detected.append(name)

        return detected

    # =========================================================
    # Repetition Detection
    # =========================================================

    def _has_excessive_repetition(
        self,
        text: Any,
    ) -> bool:

        text = self._clean(text)

        if not text:
            return False

        words = text.split()

        if len(words) < 12:
            return False

        # Detect immediate repeated 3-word sequences.
        for index in range(len(words) - 5):

            first = words[index : index + 3]

            second = words[index + 3 : index + 6]

            if first == second:
                return True

        # Detect one word dominating an answer.
        normalized_words = [word.lower() for word in words if len(word) > 1]

        if len(normalized_words) >= 15:

            counts = {}

            for word in normalized_words:

                counts[word] = (
                    counts.get(
                        word,
                        0,
                    )
                    + 1
                )

            maximum = max(
                counts.values(),
                default=0,
            )

            ratio = maximum / len(normalized_words)

            if ratio >= 0.40:
                return True

        return False

    # =========================================================
    # Question / Answer Duplication
    # =========================================================

    def _question_answer_identical(
        self,
        question: str,
        answer: str,
    ) -> bool:

        question = self._clean(question).lower()

        answer = self._clean(answer).lower()

        if not question or not answer:
            return False

        return question == answer

    # =========================================================
    # Category Validation
    # =========================================================

    def _validate_category(
        self,
        category: Any,
    ) -> List[str]:

        category = self._clean(category)

        if not category:
            return ["Category is missing; General may be used."]

        normalized = category.lower()

        if normalized not in self.KNOWN_CATEGORIES:

            return ["Unknown category " f"'{category}'. Verify category mapping."]

        return []

    # =========================================================
    # Source Quality
    # =========================================================

    def _evaluate_source(
        self,
        knowledge: Any,
    ) -> Dict:

        source = self._get(
            knowledge,
            "knowledge_source",
        )

        if not source:

            return {
                "available": False,
                "title": "",
                "source_name": "",
                "source_type": "",
                "status": "",
                "warnings": ["Knowledge source is missing."],
            }

        title = self._clean(
            getattr(
                source,
                "title",
                "",
            )
        )

        source_name = self._clean(
            getattr(
                source,
                "source_name",
                "",
            )
        )

        source_type = self._clean(
            getattr(
                source,
                "source_type",
                "",
            )
        )

        status = self._clean(
            getattr(
                source,
                "status",
                "",
            )
        )

        warnings = []

        if not title:
            warnings.append("Knowledge source title is missing.")

        if not source_name:
            warnings.append("Knowledge source name is missing.")

        if status and status.lower() not in {
            "completed",
            "processing",
        }:
            warnings.append(("Knowledge source status is " f"'{status}'."))

        return {
            "available": True,
            "title": title,
            "source_name": source_name,
            "source_type": source_type,
            "status": status,
            "warnings": warnings,
        }

    # =========================================================
    # Score Calculation
    # =========================================================

    def _calculate_score(
        self,
        knowledge: Any,
        errors: List[str],
        warnings: List[str],
        source_info: Dict,
    ) -> float:
        """
        Structural quality score.

        This score does NOT represent scientific correctness.
        """

        score = 0.0

        question = self._clean(
            self._get(
                knowledge,
                "question",
                "",
            )
        )

        answer = self._clean(
            self._get(
                knowledge,
                "answer",
                "",
            )
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

        domain = self._clean(
            self._get(
                knowledge,
                "domain",
                "",
            )
        )

        keywords = self._clean(
            self._get(
                knowledge,
                "keywords",
                "",
            )
        )

        search_text = self._clean(
            self._get(
                knowledge,
                "search_text",
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

        # -----------------------------------------------------
        # Core content - 55%
        # -----------------------------------------------------

        if question:
            score += 0.20

        if answer:
            score += 0.30

        if (
            question
            and answer
            and not self._question_answer_identical(
                question,
                answer,
            )
        ):
            score += 0.05

        # -----------------------------------------------------
        # Agricultural metadata - 15%
        # -----------------------------------------------------

        if crop:
            score += 0.07

        if category:
            score += 0.04

        if domain:
            score += 0.04

        # -----------------------------------------------------
        # Retrieval quality - 15%
        # -----------------------------------------------------

        if search_text:
            score += 0.08

        if keywords:
            score += 0.04

        normalized_question = self._clean(
            self._get(
                knowledge,
                "normalized_question",
                "",
            )
        )

        if normalized_question:
            score += 0.03

        # -----------------------------------------------------
        # Metadata - 5%
        # -----------------------------------------------------

        if language:
            score += 0.05

        # -----------------------------------------------------
        # Provenance - 10%
        # -----------------------------------------------------

        if source_info.get("available"):
            score += 0.04

        if source_info.get("title"):
            score += 0.02

        if source_info.get("source_name"):
            score += 0.02

        if (
            source_info.get(
                "status",
                "",
            ).lower()
            == "completed"
        ):
            score += 0.02

        # -----------------------------------------------------
        # Penalties
        # -----------------------------------------------------

        score -= len(errors) * 0.20

        score -= len(warnings) * 0.025

        score = max(
            0.0,
            min(
                score,
                1.0,
            ),
        )

        return round(
            score,
            4,
        )

    # =========================================================
    # Main Validation
    # =========================================================

    def evaluate(
        self,
        knowledge: Any,
    ) -> Dict:
        """
        Evaluate one Knowledge object or dictionary.

        Returns:

        {
            "is_valid": bool,
            "is_trusted": bool,
            "quality_score": float,
            "grade": str,
            "errors": [],
            "warnings": [],
            "source": {...}
        }
        """

        if knowledge is None:

            return {
                "is_valid": False,
                "is_trusted": False,
                "quality_score": 0.0,
                "grade": "invalid",
                "errors": ["Knowledge record is missing."],
                "warnings": [],
                "source": {},
            }

        errors = []

        warnings = []

        # =====================================================
        # Question
        # =====================================================

        question_result = self._validate_text(
            self._get(
                knowledge,
                "question",
            ),
            "Question",
            required=True,
            min_length=self.MIN_QUESTION_LENGTH,
            max_length=self.MAX_QUESTION_LENGTH,
        )

        errors.extend(question_result["errors"])

        warnings.extend(question_result["warnings"])

        question = question_result["value"]

        # =====================================================
        # Answer
        # =====================================================

        answer_result = self._validate_text(
            self._get(
                knowledge,
                "answer",
            ),
            "Answer",
            required=True,
            min_length=self.MIN_ANSWER_LENGTH,
            max_length=self.MAX_ANSWER_LENGTH,
        )

        errors.extend(answer_result["errors"])

        warnings.extend(answer_result["warnings"])

        answer = answer_result["value"]

        # =====================================================
        # Search Text
        # =====================================================

        search_text_result = self._validate_text(
            self._get(
                knowledge,
                "search_text",
            ),
            "Search text",
            required=False,
            min_length=self.MIN_SEARCH_TEXT_LENGTH,
            max_length=self.MAX_SEARCH_TEXT_LENGTH,
        )

        warnings.extend(search_text_result["warnings"])

        # =====================================================
        # Crop
        # =====================================================

        crop = self._clean(
            self._get(
                knowledge,
                "crop",
                "",
            )
        )

        if not crop:

            warnings.append(
                (
                    "Crop is missing. This is acceptable "
                    "only for crop-independent knowledge."
                )
            )

        elif self._is_placeholder(crop):

            warnings.append("Crop contains a placeholder value.")

        # =====================================================
        # Category
        # =====================================================

        category = self._get(
            knowledge,
            "category",
            "",
        )

        warnings.extend(self._validate_category(category))

        # =====================================================
        # Language
        # =====================================================

        language = self._clean(
            self._get(
                knowledge,
                "language",
                "",
            )
        )

        if not language:

            warnings.append("Knowledge language is missing.")

        # =====================================================
        # Active Status
        # =====================================================

        is_active = self._get(
            knowledge,
            "is_active",
            True,
        )

        if is_active is False:

            warnings.append("Knowledge record is inactive.")

        # =====================================================
        # Question == Answer
        # =====================================================

        if (
            question
            and answer
            and self._question_answer_identical(
                question,
                answer,
            )
        ):

            warnings.append(
                (
                    "Question and answer are identical; "
                    "record may have poor information value."
                )
            )

        # =====================================================
        # Repetition
        # =====================================================

        if self._has_excessive_repetition(answer):

            warnings.append(("Answer contains excessive " "text repetition."))

        # =====================================================
        # Suspicious Content
        # =====================================================

        combined_text = " ".join(
            value
            for value in [
                question,
                answer,
                search_text_result["value"],
            ]
            if value
        )

        suspicious = self._find_suspicious_patterns(combined_text)

        if suspicious:

            errors.append(("Suspicious content detected: " f"{suspicious}"))

        # =====================================================
        # Source / Provenance
        # =====================================================

        source_info = self._evaluate_source(knowledge)

        warnings.extend(
            source_info.get(
                "warnings",
                [],
            )
        )

        # =====================================================
        # Remove duplicates
        # =====================================================

        errors = self._unique(errors)

        warnings = self._unique(warnings)

        # =====================================================
        # Quality Score
        # =====================================================

        score = self._calculate_score(
            knowledge=knowledge,
            errors=errors,
            warnings=warnings,
            source_info=source_info,
        )

        # =====================================================
        # Validity
        # =====================================================

        is_valid = len(errors) == 0

        # Trusted means structurally valid AND sufficiently
        # useful as RAG evidence.
        is_trusted = (
            is_valid and score >= self.MIN_TRUSTED_SCORE and is_active is not False
        )

        # =====================================================
        # Grade
        # =====================================================

        grade = self._grade(
            score=score,
            is_valid=is_valid,
        )

        return {
            "is_valid": is_valid,
            "is_trusted": is_trusted,
            "quality_score": score,
            "grade": grade,
            "errors": errors,
            "warnings": warnings,
            "source": source_info,
            "metadata": {
                "crop": crop,
                "category": self._clean(category),
                "language": language,
                "is_active": bool(is_active),
            },
        }

    # =========================================================
    # Grade
    # =========================================================

    @staticmethod
    def _grade(
        score: float,
        is_valid: bool,
    ) -> str:

        if not is_valid:
            return "invalid"

        if score >= 0.90:
            return "excellent"

        if score >= 0.75:
            return "good"

        if score >= 0.60:
            return "acceptable"

        if score >= 0.45:
            return "weak"

        return "poor"

    # =========================================================
    # Boolean Convenience Methods
    # =========================================================

    def is_valid(
        self,
        knowledge: Any,
    ) -> bool:

        return self.evaluate(knowledge)["is_valid"]

    def is_trusted(
        self,
        knowledge: Any,
    ) -> bool:

        return self.evaluate(knowledge)["is_trusted"]

    # =========================================================
    # Batch Evaluation
    # =========================================================

    def evaluate_many(
        self,
        records,
    ) -> Dict:

        results = []

        valid_count = 0
        trusted_count = 0
        invalid_count = 0

        total_score = 0.0

        for knowledge in records:

            result = self.evaluate(knowledge)

            results.append(result)

            total_score += result["quality_score"]

            if result["is_valid"]:

                valid_count += 1

            else:

                invalid_count += 1

            if result["is_trusted"]:

                trusted_count += 1

        total = len(results)

        average_score = total_score / total if total else 0.0

        return {
            "total": total,
            "valid": valid_count,
            "invalid": invalid_count,
            "trusted": trusted_count,
            "average_quality_score": round(
                average_score,
                4,
            ),
            "results": results,
        }

    # =========================================================
    # Filter Trusted Records
    # =========================================================

    def filter_trusted(
        self,
        records,
    ) -> List[Any]:

        trusted = []

        for knowledge in records:

            if self.is_trusted(knowledge):

                trusted.append(knowledge)

        return trusted

    # =========================================================
    # Retrieval Eligibility
    # =========================================================

    def can_use_for_retrieval(
        self,
        knowledge: Any,
    ) -> bool:
        """
        Determines whether record should participate in
        retrieval.

        Inactive or structurally invalid records are excluded.
        """

        result = self.evaluate(knowledge)

        if not result["is_valid"]:
            return False

        if not result["metadata"]["is_active"]:
            return False

        return result["quality_score"] >= self.MIN_TRUSTED_SCORE

    # =========================================================
    # RAG Evidence Eligibility
    # =========================================================

    def can_use_as_evidence(
        self,
        knowledge: Any,
    ) -> bool:
        """
        Stricter check for evidence that may eventually
        influence farmer-facing generated answers.
        """

        result = self.evaluate(knowledge)

        if not result["is_trusted"]:
            return False

        question = self._clean(
            self._get(
                knowledge,
                "question",
                "",
            )
        )

        answer = self._clean(
            self._get(
                knowledge,
                "answer",
                "",
            )
        )

        if not question:
            return False

        if not answer:
            return False

        return True

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        knowledge: Any,
    ) -> Dict:

        result = self.evaluate(knowledge)

        print("\n" + "=" * 80)
        print("KNOWLEDGE QUALITY SERVICE")
        print("=" * 80)

        print(
            "Valid         :",
            result["is_valid"],
        )

        print(
            "Trusted       :",
            result["is_trusted"],
        )

        print(
            "Quality Score :",
            result["quality_score"],
        )

        print(
            "Grade         :",
            result["grade"],
        )

        print("-" * 80)

        print(
            "Metadata      :",
            result["metadata"],
        )

        print(
            "Source        :",
            result["source"],
        )

        print("-" * 80)

        print(
            "Errors        :",
            result["errors"],
        )

        print(
            "Warnings      :",
            result["warnings"],
        )

        print("=" * 80 + "\n")

        return result
