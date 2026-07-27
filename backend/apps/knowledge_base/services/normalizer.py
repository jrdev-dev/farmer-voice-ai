import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class QuestionNormalizer:
    """
    Universal text normalizer for Farmer Voice AI.

    Responsibilities
    ----------------
    - Unicode normalization
    - Case normalization
    - Safe punctuation cleanup
    - Whitespace normalization
    - Number / decimal / percentage / range preservation
    - Configuration-driven alias normalization
    - Crop alias normalization
    - Agricultural terminology normalization
    - Phrase-level alias replacement
    - Search-text generation

    Design principles
    -----------------
    - No crop-specific Python rules
    - No supported crop whitelist
    - No individual STT-error patches
    - No Hindi/Hinglish word dictionary embedded in Python
    - No language-specific verb dictionary embedded in Python
    - Vocabulary comes from external configuration
    - Unknown words are preserved
    - Approximate/fuzzy STT correction is NOT performed here

    Important
    ---------
    This class performs deterministic normalization only.

    Approximate speech correction belongs to the speech layer,
    where candidate similarity, dynamic agricultural vocabulary,
    context and confidence can be considered safely.
    """

    DATA_DIR = Path(__file__).resolve().parent.parent / "data"

    # =========================================================
    # Config files
    # =========================================================

    CROP_ALIAS_FILE = "crop_aliases.json"

    TERM_ALIAS_FILE = "agriculture_terms.json"

    # Optional generic language/query normalization file.
    #
    # This allows things such as Roman Hindi aliases or
    # grammatical variants to be configured outside Python.
    #
    # The file is optional. Missing file does not break startup.
    LANGUAGE_ALIAS_FILE = "language_aliases.json"

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):

        self.crop_aliases = self.load_json(
            self.CROP_ALIAS_FILE,
            default={},
        )

        self.term_aliases = self.load_json(
            self.TERM_ALIAS_FILE,
            default={},
        )

        self.language_aliases = self.load_json(
            self.LANGUAGE_ALIAS_FILE,
            default={},
        )

        # Single-token alias -> canonical
        self.alias_lookup: Dict[str, str] = {}

        # Multi-token alias -> canonical
        self.phrase_aliases: Dict[str, str] = {}

        self.build_lookup()

    # =========================================================
    # JSON Loading
    # =========================================================

    def load_json(
        self,
        filename: str,
        default: Optional[Any] = None,
    ):
        """
        Safely load external normalization configuration.

        Missing or invalid optional vocabulary files do not
        crash the application.
        """

        if default is None:
            default = {}

        file_path = self.DATA_DIR / filename

        if not file_path.exists():
            return default

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            if not isinstance(data, dict):
                return default

            return data

        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ):

            return default

    # =========================================================
    # Unicode Normalization
    # =========================================================

    @staticmethod
    def normalize_unicode(
        text: str,
    ) -> str:
        """
        Normalize Unicode without translating,
        transliterating or changing language.
        """

        if text is None:
            return ""

        text = str(text)

        text = unicodedata.normalize(
            "NFC",
            text,
        )

        # BOM
        text = text.replace(
            "\ufeff",
            "",
        )

        # Zero-width characters
        text = text.replace(
            "\u200b",
            "",
        )

        text = text.replace(
            "\u200c",
            "",
        )

        text = text.replace(
            "\u200d",
            "",
        )

        text = text.replace(
            "\u2060",
            "",
        )

        # Non-breaking space
        text = text.replace(
            "\u00a0",
            " ",
        )

        return text

    # =========================================================
    # Generic Value Preparation
    # =========================================================

    def _prepare_lookup_value(
        self,
        value: Any,
    ) -> str:

        if value is None:
            return ""

        value = self.normalize_unicode(str(value))

        value = value.casefold()

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    # =========================================================
    # Lookup Construction
    # =========================================================

    def build_lookup(self):
        """
        Build one unified alias engine from external data.

        Sources:
        - crop_aliases.json
        - agriculture_terms.json
        - language_aliases.json

        Expected JSON structure:

        {
            "canonical value": [
                "alias one",
                "alias two"
            ]
        }

        No agricultural vocabulary is defined here.
        """

        self.alias_lookup = {}

        self.phrase_aliases = {}

        self._register_alias_group(self.crop_aliases)

        self._register_alias_group(self.term_aliases)

        self._register_alias_group(self.language_aliases)

    def _register_alias_group(
        self,
        alias_group: Dict[str, Iterable[str]],
    ):
        """
        Register canonical terms and their aliases.
        """

        if not isinstance(
            alias_group,
            dict,
        ):
            return

        for canonical, aliases in alias_group.items():

            canonical_text = self._prepare_lookup_value(canonical)

            if not canonical_text:
                continue

            # Canonical term resolves to itself.
            self._register_alias(
                canonical_text,
                canonical_text,
            )

            if isinstance(
                aliases,
                str,
            ):
                aliases = [aliases]

            if not isinstance(
                aliases,
                (
                    list,
                    tuple,
                    set,
                ),
            ):
                continue

            for alias in aliases:

                alias_text = self._prepare_lookup_value(alias)

                if not alias_text:
                    continue

                self._register_alias(
                    alias_text,
                    canonical_text,
                )

    def _register_alias(
        self,
        alias: str,
        canonical: str,
    ):
        """
        Automatically separate word and phrase aliases.
        """

        if not alias:
            return

        if not canonical:
            return

        if re.search(
            r"\s",
            alias,
        ):

            self.phrase_aliases[alias] = canonical

        else:

            self.alias_lookup[alias] = canonical

    # =========================================================
    # Text Cleaning
    # =========================================================

    def clean_text(
        self,
        text: str,
    ) -> str:
        """
        Generic multilingual text cleanup.

        Preserves:
        - Unicode letters
        - Unicode combining marks
        - numbers
        - decimal points
        - percentages
        - numeric ranges

        Examples preserved:

            2.5 kg
            10%
            15-20 days
            15–20 days
        """

        if not text:
            return ""

        text = self.normalize_unicode(text)

        text = text.casefold().strip()

        # -----------------------------------------------------
        # Normalize common dash variants
        # -----------------------------------------------------

        text = text.replace(
            "–",
            "-",
        )

        text = text.replace(
            "—",
            "-",
        )

        text = text.replace(
            "−",
            "-",
        )

        # -----------------------------------------------------
        # Generic Unicode-safe character filtering
        # -----------------------------------------------------

        cleaned_characters = []

        for character in text:

            # Keep whitespace.
            if character.isspace():

                cleaned_characters.append(" ")

                continue

            # Keep numeric/search punctuation.
            if character in {
                ".",
                "-",
                "%",
            }:

                cleaned_characters.append(character)

                continue

            category = unicodedata.category(character)

            # L* = Unicode letters
            # M* = Unicode combining marks
            # N* = Unicode numbers
            # Pc = connector punctuation such as underscore
            if (
                category.startswith("L")
                or category.startswith("M")
                or category.startswith("N")
                or category == "Pc"
            ):

                cleaned_characters.append(character)

            else:

                cleaned_characters.append(" ")

        text = "".join(cleaned_characters)

        # -----------------------------------------------------
        # Period preservation
        #
        # Keep decimal:
        # 2.5
        #
        # Remove sentence punctuation:
        # hello.
        # -----------------------------------------------------

        text = re.sub(
            r"(?<!\d)\.(?!\d)",
            " ",
            text,
        )

        # -----------------------------------------------------
        # Hyphen preservation
        #
        # Keep:
        # 15-20
        #
        # Convert other hyphens into spaces.
        # -----------------------------------------------------

        text = re.sub(
            r"(?<!\d)-(?!\d)",
            " ",
            text,
        )

        # Normalize spaces around numeric ranges.
        text = re.sub(
            r"(?<=\d)\s*-\s*(?=\d)",
            "-",
            text,
        )

        # Normalize:
        # 10 % -> 10%
        text = re.sub(
            r"(?<=\d)\s+%",
            "%",
            text,
        )

        # Collapse whitespace.
        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # =========================================================
    # Phrase Matching
    # =========================================================

    @staticmethod
    def _phrase_pattern(
        phrase: str,
    ) -> str:
        """
        Unicode-safe alias boundary.

        Explicit word boundaries are preferred over relying
        solely on \\b for mixed-script input.
        """

        escaped = re.escape(phrase)

        return rf"(?<!\w)" rf"{escaped}" rf"(?!\w)"

    # =========================================================
    # Phrase Normalization
    # =========================================================

    def normalize_phrases(
        self,
        text: str,
    ) -> str:
        """
        Resolve configured multi-token aliases.

        Longest aliases run first.

        This is deterministic exact alias normalization.
        It does NOT perform fuzzy correction.
        """

        if not text:
            return ""

        if not self.phrase_aliases:
            return text

        aliases = sorted(
            self.phrase_aliases.keys(),
            key=lambda value: (
                len(value.split()),
                len(value),
            ),
            reverse=True,
        )

        for alias in aliases:

            canonical = self.phrase_aliases[alias]

            pattern = self._phrase_pattern(alias)

            text = re.sub(
                pattern,
                lambda _match, replacement=canonical: replacement,
                text,
                flags=(re.IGNORECASE | re.UNICODE),
            )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # =========================================================
    # Single Word Normalization
    # =========================================================

    def normalize_word(
        self,
        word: str,
    ) -> str:
        """
        Normalize one token.

        Only exact configured aliases are changed.

        Unknown tokens are preserved.

        There is intentionally no:
        - typo dictionary
        - crop guessing
        - fuzzy matching
        - phonetic guessing
        - STT correction
        """

        if not word:
            return ""

        word = self.normalize_unicode(word)

        word = word.casefold().strip()

        if not word:
            return ""

        return self.alias_lookup.get(
            word,
            word,
        )

    # =========================================================
    # Full Normalization
    # =========================================================

    def normalize(
        self,
        text: str,
    ) -> str:
        """
        Deterministically normalize complete text.
        """

        text = self.clean_text(text)

        if not text:
            return ""

        # Resolve configured phrases first.
        text = self.normalize_phrases(text)

        normalized_words: List[str] = []

        for word in text.split():

            normalized_word = self.normalize_word(word)

            if normalized_word:

                normalized_words.append(normalized_word)

        text = " ".join(normalized_words)

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # =========================================================
    # Batch Normalization
    # =========================================================

    def normalize_many(
        self,
        texts: Iterable[Any],
    ) -> List[str]:
        """
        Normalize multiple text values.
        """

        if texts is None:
            return []

        results: List[str] = []

        for text in texts:

            if text is None:
                continue

            normalized = self.normalize(str(text))

            if normalized:

                results.append(normalized)

        return results

    # =========================================================
    # Search Text Generation
    # =========================================================

    def build_search_text(
        self,
        question="",
        answer="",
        crop="",
        stage="",
        domain="",
        category="",
        subcategory="",
        keywords="",
    ) -> str:
        """
        Build normalized searchable Knowledge text.

        Existing method signature is preserved.
        """

        values = [
            question,
            answer,
            crop,
            category,
            subcategory,
            stage,
            domain,
            keywords,
        ]

        combined = " ".join(
            str(value) for value in values if (value is not None and str(value).strip())
        )

        return self.normalize(combined)

    # =========================================================
    # Alias Resolution
    # =========================================================

    def resolve_alias(
        self,
        value: str,
    ) -> str:
        """
        Resolve configured word/phrase aliases.

        Unknown values are normalized and preserved.
        """

        cleaned = self.clean_text(value)

        if not cleaned:
            return ""

        # Exact phrase alias.
        exact_phrase = self.phrase_aliases.get(cleaned)

        if exact_phrase:
            return exact_phrase

        # Exact single-token alias.
        if " " not in cleaned:

            return self.alias_lookup.get(
                cleaned,
                cleaned,
            )

        return self.normalize(cleaned)

    # =========================================================
    # Runtime Reload
    # =========================================================

    def reload_configuration(self):
        """
        Reload alias configuration without changing Python code.

        Useful after editing JSON vocabulary files.
        """

        self.crop_aliases = self.load_json(
            self.CROP_ALIAS_FILE,
            default={},
        )

        self.term_aliases = self.load_json(
            self.TERM_ALIAS_FILE,
            default={},
        )

        self.language_aliases = self.load_json(
            self.LANGUAGE_ALIAS_FILE,
            default={},
        )

        self.build_lookup()

    # =========================================================
    # Vocabulary Inspection
    # =========================================================

    def get_crop_aliases(
        self,
    ) -> Dict[str, Any]:

        return dict(self.crop_aliases)

    def get_term_aliases(
        self,
    ) -> Dict[str, Any]:

        return dict(self.term_aliases)

    def get_language_aliases(
        self,
    ) -> Dict[str, Any]:

        return dict(self.language_aliases)

    def get_alias_lookup(
        self,
    ) -> Dict[str, str]:

        return dict(self.alias_lookup)

    def get_phrase_aliases(
        self,
    ) -> Dict[str, str]:

        return dict(self.phrase_aliases)

    # =========================================================
    # Debug Snapshot
    # =========================================================

    def get_debug_snapshot(
        self,
    ) -> Dict[str, Any]:
        """
        Inspect currently loaded configuration.
        """

        return {
            "crop_groups": len(self.crop_aliases),
            "term_groups": len(self.term_aliases),
            "language_groups": len(self.language_aliases),
            "word_aliases": len(self.alias_lookup),
            "phrase_aliases": len(self.phrase_aliases),
        }
