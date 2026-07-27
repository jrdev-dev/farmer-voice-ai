import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vocabulary_service import VocabularyService


class SpeechTextNormalizer:
    """
    Universal and soft-coded STT post-processor.

    Vocabulary comes dynamically from VocabularyService.

    No crop-specific corrections.
    No fixed agriculture vocabulary.
    No Hindi typo dictionary.
    No hardcoded STT correction map.
    """

    MIN_WORD_SCORE = 86.0
    MIN_PHRASE_SCORE = 82.0
    HIGH_CONFIDENCE_SCORE = 93.0
    MIN_AMBIGUITY_MARGIN = 5.0

    MIN_TOKEN_LENGTH = 4
    MAX_NGRAM_SIZE = 3
    MAX_LENGTH_RATIO = 2.2

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.question_normalizer = QuestionNormalizer()
        self.vocabulary_service = VocabularyService()

        self.alias_map: Dict[str, str] = {}

        self.search_vocabulary: List[str] = []
        self.single_candidates: List[str] = []
        self.phrase_candidates: List[str] = []

        self._build_runtime_vocabulary()

    # =========================================================
    # Generic Unicode Helpers
    # =========================================================

    @staticmethod
    def _unicode_cleanup(text: str) -> str:

        if text is None:
            return ""

        text = str(text)

        text = unicodedata.normalize(
            "NFC",
            text,
        )

        for character in (
            "\ufeff",
            "\u200b",
            "\u200c",
            "\u200d",
            "\u2060",
        ):
            text = text.replace(
                character,
                "",
            )

        text = text.replace(
            "\u00a0",
            " ",
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    @classmethod
    def _clean_candidate(
        cls,
        value,
    ) -> str:

        if value is None:
            return ""

        value = cls._unicode_cleanup(str(value))

        value = value.casefold()

        cleaned = []

        for character in value:

            if character.isspace():

                cleaned.append(" ")
                continue

            category = unicodedata.category(character)

            if (
                category.startswith("L")
                or category.startswith("M")
                or category.startswith("N")
            ):
                cleaned.append(character)

            else:
                cleaned.append(" ")

        value = "".join(cleaned)

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    # =========================================================
    # Dynamic Runtime Vocabulary
    # =========================================================

    def _build_runtime_vocabulary(self):

        try:
            raw_alias_map = self.vocabulary_service.get_canonical_alias_map()
        except Exception:
            raw_alias_map = {}

        try:
            raw_vocabulary = self.vocabulary_service.get_search_vocabulary()
        except Exception:
            raw_vocabulary = set()

        alias_map: Dict[str, str] = {}

        # -----------------------------------------------------
        # Alias vocabulary
        # -----------------------------------------------------

        if isinstance(
            raw_alias_map,
            dict,
        ):

            for alias, canonical in raw_alias_map.items():

                clean_alias = self._clean_candidate(alias)

                clean_canonical = self._clean_candidate(canonical)

                if not clean_alias:
                    continue

                if not clean_canonical:
                    clean_canonical = clean_alias

                alias_map[clean_alias] = clean_canonical

        # -----------------------------------------------------
        # Search vocabulary
        # -----------------------------------------------------

        vocabulary = set()

        if raw_vocabulary:

            for value in raw_vocabulary:

                cleaned = self._clean_candidate(value)

                if cleaned:
                    vocabulary.add(cleaned)

        vocabulary.update(alias_map.keys())

        vocabulary.update(alias_map.values())

        # Canonical values resolve to themselves.
        for value in vocabulary:

            alias_map.setdefault(
                value,
                value,
            )

        self.alias_map = alias_map

        self.search_vocabulary = sorted(
            vocabulary,
            key=lambda value: (
                len(value.split()),
                len(value),
            ),
            reverse=True,
        )

        self.single_candidates = [
            value for value in self.search_vocabulary if " " not in value
        ]

        self.phrase_candidates = [
            value for value in self.search_vocabulary if " " in value
        ]

    # =========================================================
    # Vocabulary Refresh
    # =========================================================

    def refresh_vocabulary(self):

        try:
            self.vocabulary_service.clear_cache()
        except Exception:
            pass

        try:
            self.question_normalizer.reload_configuration()
        except Exception:
            pass

        self._build_runtime_vocabulary()

    # =========================================================
    # Script Detection
    # =========================================================

    @staticmethod
    def _script_type(
        text: str,
    ) -> str:

        if not text:
            return "unknown"

        if re.search(
            r"[\u0900-\u097F]",
            text,
        ):
            return "devanagari"

        if re.search(
            r"[\u0A80-\u0AFF]",
            text,
        ):
            return "gujarati"

        if re.search(
            r"[\u0A00-\u0A7F]",
            text,
        ):
            return "gurmukhi"

        if re.search(
            r"[\u0B80-\u0BFF]",
            text,
        ):
            return "tamil"

        if re.search(
            r"[\u0C00-\u0C7F]",
            text,
        ):
            return "telugu"

        if re.search(
            r"[\u0600-\u06FF]",
            text,
        ):
            return "arabic"

        if re.search(
            r"[A-Za-z]",
            text,
        ):
            return "latin"

        return "other"

    # =========================================================
    # Garbage Detection
    # =========================================================

    @staticmethod
    def _is_meaningful_character(
        character: str,
    ) -> bool:

        category = unicodedata.category(character)

        return category.startswith("L") or category.startswith("N")

    @classmethod
    def is_garbage_text(
        cls,
        text: str,
    ) -> bool:

        if not text:
            return True

        text = cls._unicode_cleanup(text)

        meaningful = [
            character for character in text if cls._is_meaningful_character(character)
        ]

        # Example:
        # । । । । । ।
        if not meaningful:
            return True

        cleaned = cls._clean_candidate(text)

        tokens = cleaned.split()

        if not tokens:
            return True

        # Obvious repeated-token hallucination.
        if len(tokens) >= 8:

            unique_tokens = set(tokens)

            if len(unique_tokens) <= 1:
                return True

        # Very long text made from almost the same characters.
        if len(meaningful) >= 20:

            unique_characters = set(meaningful)

            if len(unique_characters) <= 2:
                return True

        return False

    # =========================================================
    # Repetition Cleanup
    # =========================================================

    @classmethod
    def cleanup_repetition(
        cls,
        text: str,
    ) -> str:

        text = cls._unicode_cleanup(text)

        if not text:
            return ""

        text = re.sub(
            r"([!?.,।])(?:\s*\1){3,}",
            r"\1",
            text,
        )

        tokens = text.split()

        output = []

        previous = None
        repeat_count = 0

        for token in tokens:

            normalized_token = cls._clean_candidate(token)

            if normalized_token and normalized_token == previous:

                repeat_count += 1

                if repeat_count >= 2:
                    continue

            else:
                repeat_count = 0

            output.append(token)

            previous = normalized_token

        return " ".join(output).strip()

    # =========================================================
    # Candidate Filtering
    # =========================================================

    def _compatible_candidates(
        self,
        source: str,
        candidates: List[str],
    ) -> List[str]:

        source_script = self._script_type(source)

        source_length = max(
            len(source),
            1,
        )

        compatible = []

        for candidate in candidates:

            candidate_script = self._script_type(candidate)

            # ---------------------------------------------
            # Prevent unsafe cross-script fuzzy matching.
            # ---------------------------------------------

            if (
                source_script
                not in {
                    "unknown",
                    "other",
                }
                and candidate_script
                not in {
                    "unknown",
                    "other",
                }
                and source_script != candidate_script
            ):
                continue

            candidate_length = max(
                len(candidate),
                1,
            )

            ratio = max(
                source_length,
                candidate_length,
            ) / min(
                source_length,
                candidate_length,
            )

            if ratio > self.MAX_LENGTH_RATIO:
                continue

            compatible.append(candidate)

        return compatible

    # =========================================================
    # Candidate Score
    # =========================================================

    @staticmethod
    def _score_candidate(
        source: str,
        candidate: str,
    ) -> float:

        ratio_score = fuzz.ratio(
            source,
            candidate,
        )

        weighted_score = fuzz.WRatio(
            source,
            candidate,
        )

        return float(
            max(
                ratio_score,
                weighted_score,
            )
        )

    # =========================================================
    # Find Best Candidate
    # =========================================================

    def _find_best_candidate(
        self,
        source: str,
        candidates: List[str],
        minimum_score: float,
    ) -> Optional[Tuple[str, float, float]]:

        source = self._clean_candidate(source)

        if not source:
            return None

        compatible = self._compatible_candidates(
            source,
            candidates,
        )

        if not compatible:
            return None

        matches = process.extract(
            source,
            compatible,
            scorer=fuzz.WRatio,
            limit=2,
        )

        if not matches:
            return None

        best_candidate = matches[0][0]

        best_score = self._score_candidate(
            source,
            best_candidate,
        )

        second_score = 0.0

        if len(matches) > 1:

            second_candidate = matches[1][0]

            second_score = self._score_candidate(
                source,
                second_candidate,
            )

        if best_score < minimum_score:
            return None

        margin = best_score - second_score

        if (
            best_score < self.HIGH_CONFIDENCE_SCORE
            and margin < self.MIN_AMBIGUITY_MARGIN
        ):
            return None

        return (
            best_candidate,
            best_score,
            second_score,
        )

    # =========================================================
    # Canonical Resolution
    # =========================================================

    def _canonical_for(
        self,
        candidate: str,
    ) -> str:

        candidate = self._clean_candidate(candidate)

        return self.alias_map.get(
            candidate,
            candidate,
        )

    # =========================================================
    # Exact Phrase Aliases
    # =========================================================

    def correct_exact_aliases(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        normalized_text = self._clean_candidate(text)

        if not normalized_text:
            return ""

        aliases = sorted(
            self.alias_map.keys(),
            key=lambda value: (
                len(value.split()),
                len(value),
            ),
            reverse=True,
        )

        # Only multi-word aliases here.
        # Single words are handled later token-by-token.
        for alias in aliases:

            if " " not in alias:
                continue

            canonical = self._canonical_for(alias)

            pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"

            normalized_text = re.sub(
                pattern,
                lambda _match, value=canonical: value,
                normalized_text,
                flags=(re.UNICODE | re.IGNORECASE),
            )

        normalized_text = re.sub(
            r"\s+",
            " ",
            normalized_text,
        )

        return normalized_text.strip()

    # =========================================================
    # Single Token Correction
    # =========================================================

    def _correct_single_token(
        self,
        token: str,
    ) -> str:

        cleaned = self._clean_candidate(token)

        if not cleaned:
            return token

        # Exact known alias/canonical term.
        if cleaned in self.alias_map:

            return self._canonical_for(cleaned)

        # Short words are dangerous to fuzzy-correct.
        if len(cleaned) < self.MIN_TOKEN_LENGTH:
            return token

        match = self._find_best_candidate(
            source=cleaned,
            candidates=self.single_candidates,
            minimum_score=self.MIN_WORD_SCORE,
        )

        if match is None:
            return token

        candidate, _, _ = match

        return self._canonical_for(candidate)

    # =========================================================
    # SAFE N-GRAM RECOVERY
    # =========================================================

    def _find_ngram_replacement(
        self,
        words: List[str],
        start_index: int,
    ) -> Optional[Tuple[int, str, float]]:
        """
        Recover terms split by STT.

        Critical safety:
        Valid known sequences such as

            soybean fertilizer

        must NOT collapse into one word.

        Multi-token -> single-token correction is considered
        only when enough source tokens are unknown.
        """

        remaining = len(words) - start_index

        max_size = min(
            self.MAX_NGRAM_SIZE,
            remaining,
        )

        best_result = None

        for size in range(
            max_size,
            1,
            -1,
        ):

            source_words = words[start_index : start_index + size]

            cleaned_words = [self._clean_candidate(word) for word in source_words]

            if not all(cleaned_words):
                continue

            # =============================================
            # CRITICAL FIX
            #
            # soybean + fertilizer are independently valid.
            # Never collapse them.
            # =============================================

            if all(word in self.alias_map for word in cleaned_words):
                continue

            source_phrase = " ".join(cleaned_words)

            # =============================================
            # Exact configured phrase alias
            # =============================================

            if source_phrase in self.alias_map:

                canonical = self._canonical_for(source_phrase)

                return (
                    size,
                    canonical,
                    100.0,
                )

            candidates = []

            # =============================================
            # Real multi-word vocabulary candidates
            # =============================================

            candidates.extend(self.phrase_candidates)

            unknown_count = sum(
                1 for word in cleaned_words if word not in self.alias_map
            )

            # =============================================
            # STT may split ONE canonical word:
            #
            # source:
            #     some split term
            #
            # candidate:
            #     someterm
            #
            # But don't collapse a mostly-valid phrase.
            # =============================================

            if unknown_count >= 2:

                candidates.extend(self.single_candidates)

            if not candidates:
                continue

            # Remove duplicates.
            candidates = list(dict.fromkeys(candidates))

            match = self._find_best_candidate(
                source=source_phrase,
                candidates=candidates,
                minimum_score=(self.MIN_PHRASE_SCORE),
            )

            if match is None:
                continue

            candidate, score, _ = match

            canonical = self._canonical_for(candidate)

            candidate_word_count = len(candidate.split())

            # =============================================
            # Extra protection against destructive collapse
            # =============================================

            if candidate_word_count == 1:

                known_count = sum(1 for word in cleaned_words if word in self.alias_map)

                if known_count >= (len(cleaned_words) - 1):
                    continue

            result = (
                size,
                canonical,
                score,
            )

            if best_result is None or score > best_result[2]:
                best_result = result

        return best_result

    # =========================================================
    # Dynamic Vocabulary Correction
    # =========================================================

    def correct_dynamic_vocabulary(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        text = self.correct_exact_aliases(text)

        words = text.split()

        if not words:
            return ""

        corrected = []

        index = 0

        while index < len(words):

            # ---------------------------------------------
            # First try safe phrase recovery.
            # ---------------------------------------------

            phrase_match = self._find_ngram_replacement(
                words,
                index,
            )

            if phrase_match is not None:

                size, canonical, _ = phrase_match

                corrected.append(canonical)

                index += size

                continue

            # ---------------------------------------------
            # Otherwise process only current token.
            # ---------------------------------------------

            corrected.append(self._correct_single_token(words[index]))

            index += 1

        return " ".join(corrected).strip()

    # =========================================================
    # Change Detection
    # =========================================================

    @staticmethod
    def _changed(
        original: str,
        corrected: str,
    ) -> bool:

        original = (
            re.sub(
                r"\s+",
                " ",
                original or "",
            )
            .strip()
            .casefold()
        )

        corrected = (
            re.sub(
                r"\s+",
                " ",
                corrected or "",
            )
            .strip()
            .casefold()
        )

        return original != corrected

    # =========================================================
    # Human-readable Correction
    # =========================================================

    def correct_transcription(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        text = self._unicode_cleanup(text)

        if not text:
            return ""

        # ---------------------------------------------
        # Reject obvious Whisper garbage.
        # ---------------------------------------------

        if self.is_garbage_text(text):
            return ""

        # ---------------------------------------------
        # Generic repetition cleanup.
        # ---------------------------------------------

        text = self.cleanup_repetition(text)

        if not text:
            return ""

        # ---------------------------------------------
        # DB/config-driven vocabulary correction.
        # ---------------------------------------------

        text = self.correct_dynamic_vocabulary(text)

        text = self._unicode_cleanup(text)

        return text

    # =========================================================
    # Public Interface
    # =========================================================

    def normalize(
        self,
        text: str,
    ):
        """
        Backward-compatible public interface.
        """

        original_text = "" if text is None else str(text)

        corrected_text = self.correct_transcription(original_text)

        if corrected_text:

            try:

                normalized_text = self.question_normalizer.normalize(corrected_text)

            except Exception:

                normalized_text = corrected_text

        else:

            normalized_text = ""

        if not normalized_text and corrected_text:
            normalized_text = corrected_text

        return {
            "original_text": original_text,
            "corrected_text": corrected_text,
            "normalized_text": normalized_text,
            "changed": self._changed(
                original_text,
                corrected_text,
            ),
            "is_garbage": (bool(original_text) and not bool(corrected_text)),
            "vocabulary_size": len(self.search_vocabulary),
        }

    # =========================================================
    # Debug
    # =========================================================

    def debug(self):

        snapshot = {
            "vocabulary_size": len(self.search_vocabulary),
            "alias_count": len(self.alias_map),
            "single_candidates": len(self.single_candidates),
            "phrase_candidates": len(self.phrase_candidates),
            "min_word_score": (self.MIN_WORD_SCORE),
            "min_phrase_score": (self.MIN_PHRASE_SCORE),
            "high_confidence_score": (self.HIGH_CONFIDENCE_SCORE),
            "ambiguity_margin": (self.MIN_AMBIGUITY_MARGIN),
        }

        print()
        print("=" * 80)
        print("SPEECH TEXT NORMALIZER")
        print("=" * 80)

        for key, value in snapshot.items():

            print(f"{key:<24}: {value}")

        print("=" * 80)
        print()

        return snapshot
