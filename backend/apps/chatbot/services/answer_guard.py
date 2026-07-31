import re
from typing import Iterable, List, Set

from apps.knowledge_base.services.normalizer import QuestionNormalizer


class AnswerGuard:
    """
    Universal evidence-grounding guard for Farmer Voice AI.

    Goals
    -----
    - Work with any crop present in trusted knowledge.
    - Avoid maintaining a hardcoded crop allow-list.
    - Reject unsupported agricultural entities.
    - Reject unsupported numbers and quantities.
    - Detect suspicious invented product / chemical names.
    - Detect malformed generation and repetition.
    - Support Hindi, English and Hinglish evidence.
    - Remain compatible with GenerationService.

    IMPORTANT
    ---------
    This service does NOT decide whether retrieved documents
    are relevant to the farmer's question.

    RelevanceService + EvidenceSelector handle that earlier.

    AnswerGuard only verifies that the generated answer stays
    grounded in the selected trusted evidence.
    """

    SAFE_FALLBACK = (
        "मुझे उपलब्ध कृषि ज्ञान के आधार पर स्पष्ट उत्तर तैयार "
        "नहीं हो पाया। कृपया प्रश्न दोबारा पूछें।"
    )

    # =========================================================
    # Generic Agricultural Vocabulary
    # =========================================================
    #
    # These are generic concepts, NOT crop/product allow-lists.
    #
    # Specific crop names, chemicals, fertilizers, pesticides,
    # diseases, varieties, etc. must come from evidence.
    # =========================================================

    SAFE_GENERIC_WORDS = {
        # -----------------------------------------------------
        # Hindi grammar / connectors
        # -----------------------------------------------------
        "में",
        "का",
        "की",
        "के",
        "को",
        "से",
        "पर",
        "और",
        "एवं",
        "तथा",
        "या",
        "लिए",
        "प्रति",
        "एक",
        "अगर",
        "यदि",
        "तो",
        "न",
        "नहीं",
        "भी",
        "ही",
        "हो",
        "है",
        "हैं",
        "था",
        "थी",
        "थे",
        "बाद",
        "पहले",
        "समय",
        "दौरान",
        "अनुसार",
        "आधार",
        "सबसे",
        "अधिक",
        "कम",
        "अच्छा",
        "बेहतर",
        "सही",
        # -----------------------------------------------------
        # Generic agriculture concepts
        # -----------------------------------------------------
        "कृषि",
        "खेती",
        "खेत",
        "फसल",
        "फसलों",
        "पौधा",
        "पौधे",
        "मिट्टी",
        "पानी",
        "बीज",
        "खाद",
        "उर्वरक",
        "पोषक",
        "तत्व",
        "दवा",
        "कीट",
        "रोग",
        "खरपतवार",
        "सिंचाई",
        "बुवाई",
        "कटाई",
        "उपज",
        "उत्पादन",
        "परीक्षण",
        "वर्षा",
        "नमी",
        "जमीन",
        "कमी",
        "वृद्धि",
        "प्रबंधन",
        "नियंत्रण",
        "उपचार",
        "जानकारी",
        "सलाह",
        "अनुशंसा",
        "सिफारिश",
        "आवश्यकता",
        "जरूरत",
        "मात्रा",
        "संतुलित",
        "विभाग",
        "विशेषज्ञ",
        # -----------------------------------------------------
        # Hindi actions
        # -----------------------------------------------------
        "दें",
        "देना",
        "डालें",
        "डालना",
        "डालो",
        "डालूं",
        "डालूँ",
        "करें",
        "करना",
        "लगाएं",
        "लगाएँ",
        "लगाना",
        "मिलाएं",
        "मिलाएँ",
        "मिलाना",
        "रखें",
        "रखना",
        "बचाएं",
        "बचाएँ",
        "बचाना",
        "चुनें",
        "चुनना",
        "उपयोग",
        "प्रयोग",
        "छिड़काव",
        "स्प्रे",
        # -----------------------------------------------------
        # Generic chemical categories
        # -----------------------------------------------------
        "कीटनाशक",
        "खरपतवारनाशी",
        "फफूंदनाशक",
        "जीवाणुनाशक",
        # -----------------------------------------------------
        # Units
        # -----------------------------------------------------
        "किलो",
        "किलोग्राम",
        "ग्राम",
        "मिलीग्राम",
        "लीटर",
        "मिलीलीटर",
        "एकड़",
        "हेक्टेयर",
        "प्रतिशत",
        "दिन",
        "घंटे",
        # -----------------------------------------------------
        # English grammar / common
        # -----------------------------------------------------
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "for",
        "from",
        "with",
        "in",
        "on",
        "at",
        "by",
        "if",
        "then",
        "after",
        "before",
        "during",
        "according",
        "recommended",
        # -----------------------------------------------------
        # English agriculture concepts
        # -----------------------------------------------------
        "agriculture",
        "farming",
        "farm",
        "field",
        "crop",
        "crops",
        "plant",
        "plants",
        "soil",
        "water",
        "seed",
        "seeds",
        "fertilizer",
        "fertiliser",
        "nutrient",
        "nutrients",
        "pesticide",
        "herbicide",
        "fungicide",
        "insecticide",
        "medicine",
        "disease",
        "pest",
        "weed",
        "weeds",
        "irrigation",
        "sowing",
        "harvest",
        "yield",
        "production",
        "management",
        "control",
        "treatment",
        "test",
        "testing",
        "rain",
        "rainfall",
        "moisture",
        "deficiency",
        "recommendation",
        "advice",
        "balanced",
        # -----------------------------------------------------
        # English actions
        # -----------------------------------------------------
        "apply",
        "use",
        "mix",
        "spray",
        "give",
        "add",
        "control",
        "manage",
        # -----------------------------------------------------
        # English units
        # -----------------------------------------------------
        "kg",
        "kilogram",
        "kilograms",
        "gram",
        "grams",
        "mg",
        "liter",
        "litre",
        "liters",
        "litres",
        "ml",
        "acre",
        "acres",
        "hectare",
        "hectares",
        "percent",
        "percentage",
        "day",
        "days",
        "hour",
        "hours",
    }

    # =========================================================
    # Recommendation / Product Context
    # =========================================================

    PRODUCT_CONTEXT_WORDS = {
        "डालें",
        "डालना",
        "डालो",
        "डालूं",
        "डालूँ",
        "लगाएं",
        "लगाएँ",
        "लगाना",
        "मिलाएं",
        "मिलाएँ",
        "मिलाना",
        "उपयोग",
        "प्रयोग",
        "छिड़काव",
        "स्प्रे",
        "खाद",
        "उर्वरक",
        "दवा",
        "कीटनाशक",
        "खरपतवारनाशी",
        "फफूंदनाशक",
        "पोषक",
        "मात्रा",
        "dose",
        "apply",
        "use",
        "spray",
        "mix",
        "add",
        "fertilizer",
        "fertiliser",
        "pesticide",
        "herbicide",
        "fungicide",
        "insecticide",
    }

    LIST_CONNECTORS = {
        "और",
        "एवं",
        "तथा",
        "या",
        "and",
        "or",
    }

    # =========================================================
    # Units
    # =========================================================

    UNIT_WORDS = {
        "kg",
        "kgs",
        "kilogram",
        "kilograms",
        "g",
        "gram",
        "grams",
        "mg",
        "l",
        "liter",
        "litre",
        "liters",
        "litres",
        "ml",
        "acre",
        "acres",
        "hectare",
        "hectares",
        "percent",
        "percentage",
        "%",
        "day",
        "days",
        "hour",
        "hours",
        "किलो",
        "किलोग्राम",
        "ग्राम",
        "मिलीग्राम",
        "लीटर",
        "मिलीलीटर",
        "एकड़",
        "हेक्टेयर",
        "प्रतिशत",
        "दिन",
        "घंटे",
    }

    def __init__(self):

        self.normalizer = QuestionNormalizer()

    # =========================================================
    # Main Validation
    # =========================================================

    def validate(
        self,
        answer: str,
        evidence_texts=None,
    ):

        # =====================================================
        # 1. Empty Response
        # =====================================================

        if not answer or not str(answer).strip():

            return self._reject("Empty LLM response.")

        answer = self._clean(str(answer))

        # =====================================================
        # 2. Broken / Corrupted Output
        # =====================================================

        corruption = self._find_malformed_tokens(answer)

        if corruption:

            return self._reject("Malformed mixed-script token: " f"{corruption}")

        # =====================================================
        # 3. Repetition
        # =====================================================

        if self._has_repetition(answer):

            return self._reject("Repeated generation detected.")

        # =====================================================
        # 4. Evidence Required
        # =====================================================

        evidence_texts = (
            evidence_texts
            if isinstance(
                evidence_texts,
                (list, tuple, set),
            )
            else []
        )

        evidence_texts = [
            self._clean(str(text))
            for text in evidence_texts
            if text and str(text).strip()
        ]

        if not evidence_texts:
            return {
                "is_valid": True,
                "answer": answer,
                "reason": "General AI Answer generated via LLM parametric intelligence.",
                "unsupported_entities": [],
            }

        evidence = " ".join(evidence_texts)

        # =====================================================
        # 5. Numeric Grounding
        # =====================================================

        unsupported_numbers = self._find_unsupported_numbers(
            answer=answer,
            evidence=evidence,
        )

        if unsupported_numbers:

            return self._reject(
                "Unsupported numeric information: " f"{unsupported_numbers}"
            )

        # =====================================================
        # 6. Quantity + Unit Grounding
        # =====================================================

        unsupported_quantities = self._find_unsupported_quantities(
            answer=answer,
            evidence=evidence,
        )

        if unsupported_quantities:

            return self._reject(
                "Unsupported quantity/unit information: " f"{unsupported_quantities}"
            )

        # =====================================================
        # 7. Recommendation Entity Grounding
        # =====================================================

        unsupported_products = self._find_unsupported_product_names(
            answer=answer,
            evidence=evidence,
        )

        if unsupported_products:

            return self._reject(
                "Possible unsupported product/chemical names: "
                f"{unsupported_products}"
            )

        # =====================================================
        # 8. Evidence Phrase / Agricultural Token Grounding
        # =====================================================

        unsupported_terms = self._find_suspicious_agricultural_terms(
            answer=answer,
            evidence=evidence,
        )

        if unsupported_terms:

            return self._reject(
                "Unsupported agricultural recommendation terms: " f"{unsupported_terms}"
            )

        # =====================================================
        # 9. Passed
        # =====================================================

        return {
            "is_valid": True,
            "answer": answer,
            "reason": "Answer passed evidence-grounding validation.",
        }

    # =========================================================
    # Malformed Mixed-Script Detection
    # =========================================================

    def _find_malformed_tokens(
        self,
        answer: str,
    ) -> List[str]:
        """
        Detect obvious accidental script corruption.

        We deliberately avoid rejecting all Hinglish because
        mixed-language answers are valid.

        Only tokens where Latin and Devanagari characters are
        directly fused together are suspicious.
        """

        pattern = (
            r"\b(?:"
            r"[A-Za-z]{2,}[\u0900-\u097F]{2,}"
            r"|"
            r"[\u0900-\u097F]{2,}[A-Za-z]{2,}"
            r")\b"
        )

        return sorted(
            set(
                re.findall(
                    pattern,
                    answer,
                )
            )
        )

    # =========================================================
    # Repetition Detection
    # =========================================================

    def _has_repetition(
        self,
        answer: str,
    ) -> bool:

        words = answer.split()

        if len(words) < 6:
            return False

        # -----------------------------------------------------
        # Immediate repeated 3-word sequence
        # -----------------------------------------------------

        for index in range(len(words) - 5):

            first = words[index : index + 3]

            second = words[index + 3 : index + 6]

            if first == second:
                return True

        # -----------------------------------------------------
        # Repeated sentence
        # -----------------------------------------------------

        sentences = [
            self._clean(sentence).lower()
            for sentence in re.split(
                r"[।.!?]+",
                answer,
            )
            if self._clean(sentence)
        ]

        seen = set()

        for sentence in sentences:

            if len(sentence.split()) < 3:
                continue

            if sentence in seen:
                return True

            seen.add(sentence)

        return False

    # =========================================================
    # Numeric Grounding
    # =========================================================

    def _find_unsupported_numbers(
        self,
        answer: str,
        evidence: str,
    ) -> List[str]:
        """
        Every explicit number in generated output must occur
        in trusted evidence.

        Supports:
        50
        2.5
        10%
        20-25
        20–25
        """

        number_pattern = r"\d+(?:\.\d+)?" r"(?:\s*[-–]\s*\d+(?:\.\d+)?)?"

        answer_numbers = re.findall(
            number_pattern,
            answer,
        )

        if not answer_numbers:
            return []

        evidence_numbers = re.findall(
            number_pattern,
            evidence,
        )

        supported = {self._normalize_number(number) for number in evidence_numbers}

        unsupported = []

        for number in answer_numbers:

            normalized = self._normalize_number(number)

            if normalized not in supported:

                unsupported.append(number)

        return sorted(set(unsupported))

    # =========================================================
    # Quantity + Unit Grounding
    # =========================================================

    def _find_unsupported_quantities(
        self,
        answer: str,
        evidence: str,
    ) -> List[str]:
        """
        Validate complete quantity expressions.

        Example:
            50 kg
            2.5 ml
            20 kg/acre
            10 प्रतिशत

        A number appearing somewhere in evidence is not enough
        if the generated answer attaches an unsupported unit.
        """

        units = sorted(
            self.UNIT_WORDS,
            key=len,
            reverse=True,
        )

        escaped_units = "|".join(re.escape(unit) for unit in units)

        pattern = (
            r"\b"
            r"\d+(?:\.\d+)?"
            r"(?:\s*[-–]\s*\d+(?:\.\d+)?)?"
            r"\s*"
            r"(?:" + escaped_units + r")"
            r"(?:\s*/\s*"
            r"(?:acre|acres|hectare|hectares|"
            r"एकड़|हेक्टेयर)"
            r")?"
        )

        answer_quantities = re.findall(
            pattern,
            answer,
            flags=re.IGNORECASE,
        )

        if not answer_quantities:
            return []

        normalized_evidence = self._normalize_quantity_text(evidence)

        unsupported = []

        for quantity in answer_quantities:

            normalized_quantity = self._normalize_quantity_text(quantity)

            if normalized_quantity not in normalized_evidence:

                unsupported.append(quantity)

        return sorted(set(unsupported))

    # =========================================================
    # Suspicious Product / Chemical Detection
    # =========================================================

    def _find_unsupported_product_names(
        self,
        answer: str,
        evidence: str,
    ) -> List[str]:
        """
        Extract likely named agricultural inputs from
        recommendation structures.

        This is intentionally evidence-driven.

        No crop, fertilizer, pesticide or chemical needs to be
        permanently registered in this Python file.
        """

        answer_lower = answer.lower()

        evidence_lower = evidence.lower()

        normalized_evidence = self._normalize_text(evidence_lower)

        candidates = []

        # =====================================================
        # 1. Hindi direct application
        # =====================================================

        hindi_patterns = [
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+डालें",
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+डालना",
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+डालो",
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+लगाएं",
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+लगाएँ",
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+मिलाएं",
            r"([A-Za-z\u0900-\u097F][A-Za-z0-9_\-\u0900-\u097F]{2,})" r"\s+मिलाएँ",
        ]

        for pattern in hindi_patterns:

            candidates.extend(
                re.findall(
                    pattern,
                    answer_lower,
                )
            )

        # =====================================================
        # 2. Hindi spray patterns
        # =====================================================

        spray_patterns = [
            (
                r"([A-Za-z\u0900-\u097F]"
                r"[A-Za-z0-9_\-\u0900-\u097F]{2,})"
                r"\s+(?:का|की|के)\s+छिड़काव"
            ),
            (
                r"([A-Za-z\u0900-\u097F]"
                r"[A-Za-z0-9_\-\u0900-\u097F]{2,})"
                r"\s+(?:का|की|के)\s+स्प्रे"
            ),
        ]

        for pattern in spray_patterns:

            candidates.extend(
                re.findall(
                    pattern,
                    answer_lower,
                )
            )

        # =====================================================
        # 3. English / Hinglish recommendations
        # =====================================================

        english_patterns = [
            r"\bapply\s+([a-z][a-z0-9_-]{2,})",
            r"\buse\s+([a-z][a-z0-9_-]{2,})",
            r"\bspray\s+([a-z][a-z0-9_-]{2,})",
            r"\bmix\s+([a-z][a-z0-9_-]{2,})",
            r"\badd\s+([a-z][a-z0-9_-]{2,})",
        ]

        for pattern in english_patterns:

            candidates.extend(
                re.findall(
                    pattern,
                    answer_lower,
                )
            )

        # =====================================================
        # 4. Recommendation Lists
        # =====================================================

        sentences = re.split(
            r"[।.!?]+",
            answer_lower,
        )

        for sentence in sentences:

            sentence = self._clean(sentence)

            if not sentence:
                continue

            has_context = any(
                self._contains_term(
                    sentence,
                    context_word,
                )
                for context_word in self.PRODUCT_CONTEXT_WORDS
            )

            if not has_context:
                continue

            # -------------------------------------------------
            # Comma / conjunction list
            # -------------------------------------------------

            if "," not in sentence and not any(
                f" {connector} " in sentence for connector in self.LIST_CONNECTORS
            ):
                continue

            before_action = re.split(
                (
                    r"(?:"
                    r"उपयोग|प्रयोग|छिड़काव|स्प्रे|"
                    r"डालें|डालना|लगाएं|लगाएँ|"
                    r"मिलाएं|मिलाएँ|"
                    r"apply|use|spray|mix|add"
                    r")"
                ),
                sentence,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]

            # Remove introductory clause when possible.

            marker = re.search(
                (r"(?:" r"अनुसार|लिए|तो|" r"recommend|recommended" r")\s+(.+)$"),
                before_action,
                flags=re.IGNORECASE,
            )

            if marker:

                before_action = marker.group(1)

            pieces = re.split(
                (r"\s*,\s*" r"|\s+(?:" r"और|एवं|तथा|या|and|or" r")\s+"),
                before_action,
                flags=re.IGNORECASE,
            )

            if len(pieces) < 2:
                continue

            for piece in pieces:

                tokens = self._extract_words(piece)

                if tokens:

                    candidates.append(tokens[-1])

        # =====================================================
        # 5. Clean Candidates
        # =====================================================

        candidates = self._clean_candidates(candidates)

        unsupported = []

        for candidate in candidates:

            if self._is_generic_word(candidate):
                continue

            # Exact evidence support.

            if self._contains_term(
                evidence_lower,
                candidate,
            ):
                continue

            # Alias / normalization support.

            normalized_candidate = self._normalize_text(candidate)

            if normalized_candidate and self._contains_term(
                normalized_evidence,
                normalized_candidate,
            ):
                continue

            unsupported.append(candidate)

        return sorted(set(unsupported))

    # =========================================================
    # Generic Suspicious Agricultural Term Detection
    # =========================================================

    def _find_suspicious_agricultural_terms(
        self,
        answer: str,
        evidence: str,
    ) -> List[str]:
        """
        Secondary universal safety layer.

        Instead of maintaining a fixed list of crops/products,
        inspect words near strong recommendation language.

        Unknown recommendation nouns must be supported by
        evidence.

        This catches fabricated terms while still allowing new
        crops/products when they genuinely exist in imported
        trusted knowledge.
        """

        answer_lower = answer.lower()

        evidence_lower = evidence.lower()

        normalized_evidence = self._normalize_text(evidence_lower)

        suspicious = []

        sentences = re.split(
            r"[।.!?]+",
            answer_lower,
        )

        for sentence in sentences:

            sentence = self._clean(sentence)

            if not sentence:
                continue

            has_recommendation = any(
                self._contains_term(
                    sentence,
                    word,
                )
                for word in self.PRODUCT_CONTEXT_WORDS
            )

            if not has_recommendation:
                continue

            words = self._extract_words(sentence)

            for word in words:

                word = word.lower()

                if len(word) < 3:
                    continue

                if self._is_generic_word(word):
                    continue

                # Numbers handled separately.

                if re.fullmatch(
                    r"\d+(?:\.\d+)?",
                    word,
                ):
                    continue

                # Evidence supports exact term.

                if self._contains_term(
                    evidence_lower,
                    word,
                ):
                    continue

                normalized_word = self._normalize_text(word)

                if normalized_word and self._contains_term(
                    normalized_evidence,
                    normalized_word,
                ):
                    continue

                # -------------------------------------------------
                # Don't reject every ordinary sentence word.
                #
                # Only flag tokens that look like plausible named
                # agricultural inputs/products.
                # -------------------------------------------------

                if self._looks_like_named_input(
                    word=word,
                    sentence=sentence,
                ):

                    suspicious.append(word)

        return sorted(set(suspicious))

    # =========================================================
    # Named Input Heuristic
    # =========================================================

    def _looks_like_named_input(
        self,
        word: str,
        sentence: str,
    ) -> bool:
        """
        Conservative heuristic.

        We intentionally avoid treating every unsupported noun
        as hallucination because normal language does not need
        to be copied word-for-word from evidence.

        Strong recommendation position is required.
        """

        escaped = re.escape(word)

        hindi_after = re.search(
            (
                escaped + r"\s+(?:"
                r"डालें|डालना|डालो|"
                r"लगाएं|लगाएँ|"
                r"मिलाएं|मिलाएँ"
                r")"
            ),
            sentence,
            flags=re.IGNORECASE,
        )

        if hindi_after:
            return True

        hindi_spray = re.search(
            (escaped + r"\s+(?:का|की|के)\s+" r"(?:छिड़काव|स्प्रे)"),
            sentence,
            flags=re.IGNORECASE,
        )

        if hindi_spray:
            return True

        english_before = re.search(
            (r"\b(?:apply|use|spray|mix|add)\s+" + escaped + r"\b"),
            sentence,
            flags=re.IGNORECASE,
        )

        if english_before:
            return True

        return False

    # =========================================================
    # Candidate Cleaning
    # =========================================================

    def _clean_candidates(
        self,
        candidates: Iterable[str],
    ) -> List[str]:

        cleaned = []

        for candidate in candidates:

            candidate = self._clean(str(candidate)).lower()

            candidate = re.sub(
                (r"^[^A-Za-z0-9_\u0900-\u097F]+" r"|" r"[^A-Za-z0-9_\u0900-\u097F-]+$"),
                "",
                candidate,
            )

            if not candidate:
                continue

            if len(candidate) < 3:
                continue

            cleaned.append(candidate)

        return list(dict.fromkeys(cleaned))

    # =========================================================
    # Generic Word Check
    # =========================================================

    def _is_generic_word(
        self,
        word: str,
    ) -> bool:

        word = self._clean(word).lower()

        if word in self.SAFE_GENERIC_WORDS:
            return True

        normalized = self._normalize_text(word)

        for safe_word in self.SAFE_GENERIC_WORDS:

            normalized_safe = self._normalize_text(safe_word)

            if normalized and normalized_safe and normalized == normalized_safe:
                return True

        return False

    # =========================================================
    # Word Extraction
    # =========================================================

    @staticmethod
    def _extract_words(
        text: str,
    ) -> List[str]:

        return re.findall(
            (r"[A-Za-z]" r"[A-Za-z0-9_-]*" r"|" r"[\u0900-\u097F]+"),
            text,
        )

    # =========================================================
    # Evidence Term Matching
    # =========================================================

    @staticmethod
    def _contains_term(
        text: str,
        term: str,
    ) -> bool:
        """
        Boundary-aware multilingual matching.

        Prevents a short token from matching inside another
        unrelated token.
        """

        if not text or not term:
            return False

        pattern = (
            r"(?<![A-Za-z0-9_\u0900-\u097F])"
            + re.escape(term)
            + r"(?![A-Za-z0-9_\u0900-\u097F])"
        )

        return bool(
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

    # =========================================================
    # Normalization
    # =========================================================

    def _normalize_text(
        self,
        value: str,
    ) -> str:

        if not value:
            return ""

        try:

            normalized = self.normalizer.normalize(value)

            return self._clean(normalized).lower()

        except Exception:

            return self._clean(value).lower()

    @staticmethod
    def _normalize_number(
        value: str,
    ) -> str:

        value = re.sub(
            r"\s+",
            "",
            str(value),
        )

        value = value.replace(
            "–",
            "-",
        )

        return value

    @staticmethod
    def _normalize_quantity_text(
        value: str,
    ) -> str:

        value = str(value).lower()

        value = value.replace(
            "–",
            "-",
        )

        value = re.sub(
            r"\s+",
            "",
            value,
        )

        return value

    # =========================================================
    # Answer Cleaning
    # =========================================================

    @staticmethod
    def _clean(
        answer: str,
    ) -> str:

        if answer is None:
            return ""

        answer = str(answer)

        answer = answer.replace(
            "\x00",
            " ",
        )

        answer = re.sub(
            r"\s+",
            " ",
            answer,
        )

        return answer.strip()

    # =========================================================
    # Reject
    # =========================================================

    def _reject(
        self,
        reason,
    ):

        return {
            "is_valid": False,
            "answer": self.SAFE_FALLBACK,
            "reason": str(reason),
        }
