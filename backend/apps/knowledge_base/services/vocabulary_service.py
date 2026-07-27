import re
import threading
import time
from typing import Any, Dict, List, Optional, Set

from apps.knowledge_base.services.normalizer import QuestionNormalizer


class VocabularyService:
    """
    Universal, dynamic and cached agricultural vocabulary service.

    Vocabulary sources
    ------------------
    1. Active Knowledge database
    2. crop_aliases.json through QuestionNormalizer
    3. agriculture_terms.json through QuestionNormalizer

    Design principles
    -----------------
    - No supported-crop whitelist
    - No crop-specific Python rules
    - No STT typo-specific Python rules
    - New DB knowledge automatically becomes vocabulary
    - JSON aliases remain configurable outside Python
    - Expensive DB vocabulary is cached
    - Cache can be explicitly refreshed after imports
    - Existing public API remains backward compatible

    This service provides vocabulary/canonicalization only.
    It does not decide retrieval relevance.
    """

    # =========================================================
    # Cache Configuration
    # =========================================================

    # Development-friendly default.
    # Database vocabulary automatically refreshes after this
    # many seconds.
    CACHE_TTL_SECONDS = 300

    _cache: Dict[str, Any] = {}
    _cache_created_at: Dict[str, float] = {}

    _cache_lock = threading.RLock()

    # =========================================================
    # Initialization
    # =========================================================

    def __init__(self):
        self.normalizer = QuestionNormalizer()

    # =========================================================
    # Cache Helpers
    # =========================================================

    @classmethod
    def _is_cache_valid(
        cls,
        key: str,
    ) -> bool:

        if key not in cls._cache:
            return False

        created_at = cls._cache_created_at.get(
            key,
            0.0,
        )

        age = time.monotonic() - created_at

        return age < cls.CACHE_TTL_SECONDS

    @classmethod
    def _cache_get(
        cls,
        key: str,
    ):

        with cls._cache_lock:

            if not cls._is_cache_valid(key):
                return None

            return cls._cache.get(key)

    @classmethod
    def _cache_set(
        cls,
        key: str,
        value,
    ):

        with cls._cache_lock:

            cls._cache[key] = value

            cls._cache_created_at[key] = (
                time.monotonic()
            )

        return value

    @classmethod
    def clear_cache(cls):
        """
        Clear all cached vocabulary.

        Call this after:
        - knowledge import
        - knowledge update/delete
        - alias configuration changes
        - rebuilding the knowledge base
        """

        with cls._cache_lock:

            cls._cache.clear()

            cls._cache_created_at.clear()

    @classmethod
    def invalidate_cache(cls):
        """
        Backward/readability alias for clear_cache().
        """

        cls.clear_cache()

    @classmethod
    def refresh_cache(cls):
        """
        Clear shared vocabulary cache.

        The next VocabularyService request rebuilds it lazily.
        """

        cls.clear_cache()

    # =========================================================
    # Safe Knowledge Model Import
    # =========================================================

    @staticmethod
    def _get_knowledge_model():
        """
        Import lazily to reduce circular-import problems.
        """

        try:
            from apps.knowledge_base.models import Knowledge

            return Knowledge

        except Exception:
            return None

    # =========================================================
    # Generic Helpers
    # =========================================================

    @staticmethod
    def _clean_value(value) -> str:

        if value is None:
            return ""

        value = str(value)

        value = value.replace(
            "\x00",
            " ",
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    def _normalize_value(
        self,
        value,
    ) -> str:

        value = self._clean_value(value)

        if not value:
            return ""

        try:

            normalized = self.normalizer.normalize(
                value
            )

        except Exception:

            normalized = value.casefold()

        return self._clean_value(
            normalized
        )

    @staticmethod
    def _copy_set(value) -> Set[str]:
        """
        Prevent callers from modifying cached sets.
        """

        if not value:
            return set()

        return set(value)

    @staticmethod
    def _copy_dict(value) -> Dict:
        """
        Prevent callers from modifying cached dictionaries.
        """

        if not value:
            return {}

        return dict(value)

    # =========================================================
    # Database Vocabulary
    # =========================================================

    def _get_distinct_database_values(
        self,
        field_name: str,
    ) -> Set[str]:
        """
        Read distinct active values from a Knowledge field.

        Results are cached per field.

        Returns an empty set if Django/database is unavailable.
        """

        field_name = self._clean_value(
            field_name
        )

        if not field_name:
            return set()

        cache_key = (
            f"database_field::{field_name}"
        )

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_set(cached)

        Knowledge = self._get_knowledge_model()

        if Knowledge is None:
            return set()

        try:

            valid_fields = {
                field.name
                for field
                in Knowledge._meta.get_fields()
            }

            if field_name not in valid_fields:
                return set()

            queryset = (
                Knowledge.objects
                .filter(
                    is_active=True,
                )
                .exclude(
                    **{
                        f"{field_name}__isnull": True,
                    }
                )
                .exclude(
                    **{
                        field_name: "",
                    }
                )
                .values_list(
                    field_name,
                    flat=True,
                )
                .distinct()
            )

            values = set()

            for value in queryset:

                cleaned = self._clean_value(
                    value
                )

                if cleaned:
                    values.add(cleaned)

            self._cache_set(
                cache_key,
                frozenset(values),
            )

            return values

        except Exception as exc:

            print(
                "VOCABULARY DATABASE ERROR:",
                field_name,
                str(exc),
            )

            return set()

    # =========================================================
    # Crops
    # =========================================================

    def get_database_crops(self) -> Set[str]:
        """
        Crops represented by active Knowledge records.
        """

        return self._get_distinct_database_values(
            "crop"
        )

    def get_json_crops(self) -> Set[str]:
        """
        Canonical crops configured outside Python through
        crop_aliases.json / QuestionNormalizer.
        """

        cache_key = "json_crops"

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_set(cached)

        crops = set()

        crop_aliases = getattr(
            self.normalizer,
            "crop_aliases",
            {},
        )

        if isinstance(
            crop_aliases,
            dict,
        ):

            for canonical in crop_aliases.keys():

                cleaned = self._clean_value(
                    canonical
                )

                if cleaned:
                    crops.add(cleaned)

        self._cache_set(
            cache_key,
            frozenset(crops),
        )

        return crops

    def get_known_crops(self) -> Set[str]:
        """
        Return all dynamically known crops.

        Sources:
        - active Knowledge DB
        - external crop alias configuration
        """

        cache_key = "known_crops"

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_set(cached)

        crops = set()

        crops.update(
            self.get_database_crops()
        )

        crops.update(
            self.get_json_crops()
        )

        self._cache_set(
            cache_key,
            frozenset(crops),
        )

        return crops

    # =========================================================
    # Crop Alias Map
    # =========================================================

    def get_crop_alias_map(
        self,
    ) -> Dict[str, str]:
        """
        Build:

            normalized alias -> canonical crop

        Sources:
        - canonical JSON crop names
        - JSON aliases
        - active database crop values

        No crop is hardcoded in this service.
        """

        cache_key = "crop_alias_map"

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_dict(cached)

        alias_map: Dict[str, str] = {}

        crop_aliases = getattr(
            self.normalizer,
            "crop_aliases",
            {},
        )

        # -----------------------------------------------------
        # Configured Crop Vocabulary
        # -----------------------------------------------------

        if isinstance(
            crop_aliases,
            dict,
        ):

            for canonical, aliases in (
                crop_aliases.items()
            ):

                canonical_clean = (
                    self._clean_value(
                        canonical
                    )
                )

                if not canonical_clean:
                    continue

                canonical_normalized = (
                    self._normalize_value(
                        canonical_clean
                    )
                )

                if canonical_normalized:

                    alias_map[
                        canonical_normalized
                    ] = canonical_clean

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

                    normalized_alias = (
                        self._normalize_value(
                            alias
                        )
                    )

                    if normalized_alias:

                        alias_map[
                            normalized_alias
                        ] = canonical_clean

        # -----------------------------------------------------
        # Database Crop Vocabulary
        # -----------------------------------------------------

        for crop in self.get_database_crops():

            normalized_crop = (
                self._normalize_value(
                    crop
                )
            )

            if normalized_crop:

                # Config aliases have priority.
                alias_map.setdefault(
                    normalized_crop,
                    crop,
                )

        self._cache_set(
            cache_key,
            dict(alias_map),
        )

        return alias_map

    # =========================================================
    # Resolve Crop
    # =========================================================

    def resolve_crop(
        self,
        value: str,
    ) -> Optional[str]:
        """
        Resolve an exact known crop/alias.

        This intentionally does NOT perform fuzzy guessing.
        Approximate STT correction belongs to a separate
        confidence-based candidate matcher.
        """

        normalized_value = (
            self._normalize_value(
                value
            )
        )

        if not normalized_value:
            return None

        return self.get_crop_alias_map().get(
            normalized_value
        )

    # =========================================================
    # Universal Alias Detection Helper
    # =========================================================

    def _detect_aliases(
        self,
        text: str,
        alias_map: Dict[str, str],
    ) -> List[str]:

        normalized_text = (
            self._normalize_value(
                text
            )
        )

        if not normalized_text:
            return []

        if not alias_map:
            return []

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

            if not alias:
                continue

            pattern = (
                r"(?<!\w)"
                + re.escape(alias)
                + r"(?!\w)"
            )

            if re.search(
                pattern,
                normalized_text,
                flags=(
                    re.UNICODE
                    | re.IGNORECASE
                ),
            ):

                canonical = alias_map[
                    alias
                ]

                if canonical not in matches:
                    matches.append(
                        canonical
                    )

        return matches

    # =========================================================
    # Crop Detection
    # =========================================================

    def detect_crops(
        self,
        text: str,
    ) -> List[str]:
        """
        Detect exact configured/database crop aliases in text.

        No crop-specific rules are present here.
        """

        return self._detect_aliases(
            text=text,
            alias_map=(
                self.get_crop_alias_map()
            ),
        )

    # =========================================================
    # Agriculture Term Alias Map
    # =========================================================

    def get_term_alias_map(
        self,
    ) -> Dict[str, str]:
        """
        Dynamic agricultural concept alias map from
        agriculture_terms.json / QuestionNormalizer.

        The Python service does not define fertilizer,
        disease, pest, irrigation, etc. lists.
        """

        cache_key = "term_alias_map"

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_dict(cached)

        alias_map: Dict[str, str] = {}

        term_aliases = getattr(
            self.normalizer,
            "term_aliases",
            {},
        )

        if isinstance(
            term_aliases,
            dict,
        ):

            for canonical, aliases in (
                term_aliases.items()
            ):

                canonical_clean = (
                    self._clean_value(
                        canonical
                    )
                )

                if not canonical_clean:
                    continue

                normalized_canonical = (
                    self._normalize_value(
                        canonical_clean
                    )
                )

                if normalized_canonical:

                    alias_map[
                        normalized_canonical
                    ] = canonical_clean

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

                    normalized_alias = (
                        self._normalize_value(
                            alias
                        )
                    )

                    if normalized_alias:

                        alias_map[
                            normalized_alias
                        ] = canonical_clean

        self._cache_set(
            cache_key,
            dict(alias_map),
        )

        return alias_map

    # =========================================================
    # Detect Agricultural Terms
    # =========================================================

    def detect_terms(
        self,
        text: str,
    ) -> List[str]:

        return self._detect_aliases(
            text=text,
            alias_map=(
                self.get_term_alias_map()
            ),
        )

    # =========================================================
    # Categories
    # =========================================================

    def get_categories(
        self,
    ) -> Set[str]:

        return (
            self._get_distinct_database_values(
                "category"
            )
        )

    # =========================================================
    # Subcategories
    # =========================================================

    def get_subcategories(
        self,
    ) -> Set[str]:

        return (
            self._get_distinct_database_values(
                "subcategory"
            )
        )

    # =========================================================
    # Domains
    # =========================================================

    def get_domains(
        self,
    ) -> Set[str]:

        return (
            self._get_distinct_database_values(
                "domain"
            )
        )

    # =========================================================
    # Stages
    # =========================================================

    def get_stages(
        self,
    ) -> Set[str]:

        return (
            self._get_distinct_database_values(
                "stage"
            )
        )

    # =========================================================
    # Keywords
    # =========================================================

    def get_keywords(
        self,
    ) -> Set[str]:
        """
        Extract keywords from active Knowledge records.

        Supports:
        - comma
        - semicolon
        - newline
        - pipe

        Keyword values themselves remain DB-driven.
        """

        cache_key = "parsed_keywords"

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_set(cached)

        raw_values = (
            self._get_distinct_database_values(
                "keywords"
            )
        )

        keywords = set()

        for raw_value in raw_values:

            parts = re.split(
                r"[,;\n|]+",
                raw_value,
            )

            for part in parts:

                cleaned = (
                    self._clean_value(
                        part
                    )
                )

                if cleaned:
                    keywords.add(cleaned)

        self._cache_set(
            cache_key,
            frozenset(keywords),
        )

        return keywords

    # =========================================================
    # Database Vocabulary
    # =========================================================

    def get_database_vocabulary(
        self,
    ) -> Dict[str, List[str]]:
        """
        Return current DB-driven agricultural vocabulary.
        """

        cache_key = (
            "database_vocabulary"
        )

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:

            return {
                key: list(value)
                for key, value
                in cached.items()
            }

        vocabulary = {
            "crops": sorted(
                self.get_database_crops(),
                key=str.casefold,
            ),
            "categories": sorted(
                self.get_categories(),
                key=str.casefold,
            ),
            "subcategories": sorted(
                self.get_subcategories(),
                key=str.casefold,
            ),
            "domains": sorted(
                self.get_domains(),
                key=str.casefold,
            ),
            "stages": sorted(
                self.get_stages(),
                key=str.casefold,
            ),
            "keywords": sorted(
                self.get_keywords(),
                key=str.casefold,
            ),
        }

        cached_value = {
            key: tuple(value)
            for key, value
            in vocabulary.items()
        }

        self._cache_set(
            cache_key,
            cached_value,
        )

        return vocabulary

    # =========================================================
    # Universal Search Vocabulary
    # =========================================================

    def get_search_vocabulary(
        self,
    ) -> Set[str]:
        """
        Return a unified dynamic vocabulary suitable for:

        - speech correction candidate generation
        - query normalization
        - fuzzy matching
        - domain-aware STT post-processing

        No crop/term values are defined in Python.
        """

        cache_key = (
            "unified_search_vocabulary"
        )

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_set(cached)

        vocabulary = set()

        # Canonical + alias forms.
        vocabulary.update(
            self.get_crop_alias_map().keys()
        )

        vocabulary.update(
            self.get_crop_alias_map().values()
        )

        vocabulary.update(
            self.get_term_alias_map().keys()
        )

        vocabulary.update(
            self.get_term_alias_map().values()
        )

        # DB metadata.
        database_vocabulary = (
            self.get_database_vocabulary()
        )

        for values in (
            database_vocabulary.values()
        ):

            vocabulary.update(values)

        # Clean empty values.
        vocabulary = {
            self._clean_value(value)
            for value in vocabulary
            if self._clean_value(value)
        }

        self._cache_set(
            cache_key,
            frozenset(vocabulary),
        )

        return vocabulary

    # =========================================================
    # Canonical Alias Lookup
    # =========================================================

    def get_canonical_alias_map(
        self,
    ) -> Dict[str, str]:
        """
        Unified alias -> canonical map.

        Useful for the future universal speech normalizer.

        Includes:
        - crop aliases
        - agricultural concept aliases

        Database-only metadata remains available through
        get_search_vocabulary().
        """

        cache_key = (
            "canonical_alias_map"
        )

        cached = self._cache_get(
            cache_key
        )

        if cached is not None:
            return self._copy_dict(cached)

        alias_map = {}

        alias_map.update(
            self.get_term_alias_map()
        )

        alias_map.update(
            self.get_crop_alias_map()
        )

        self._cache_set(
            cache_key,
            dict(alias_map),
        )

        return alias_map

    # =========================================================
    # Vocabulary Snapshot
    # =========================================================

    def get_vocabulary_snapshot(
        self,
    ) -> Dict:
        """
        Complete runtime vocabulary snapshot.

        Useful for:
        - debugging
        - tests
        - APIs
        - speech normalizer initialization
        """

        database_vocabulary = (
            self.get_database_vocabulary()
        )

        known_crops = sorted(
            self.get_known_crops(),
            key=str.casefold,
        )

        search_vocabulary = (
            self.get_search_vocabulary()
        )

        return {
            "known_crops": known_crops,

            "database_crops": (
                database_vocabulary[
                    "crops"
                ]
            ),

            "categories": (
                database_vocabulary[
                    "categories"
                ]
            ),

            "subcategories": (
                database_vocabulary[
                    "subcategories"
                ]
            ),

            "domains": (
                database_vocabulary[
                    "domains"
                ]
            ),

            "stages": (
                database_vocabulary[
                    "stages"
                ]
            ),

            "keywords": (
                database_vocabulary[
                    "keywords"
                ]
            ),

            "crop_alias_count": len(
                self.get_crop_alias_map()
            ),

            "term_alias_count": len(
                self.get_term_alias_map()
            ),

            "search_vocabulary_count": len(
                search_vocabulary
            ),
        }

    # =========================================================
    # Knowledge Availability
    # =========================================================

    def has_crop_knowledge(
        self,
        crop: str,
    ) -> bool:
        """
        Check whether active trusted knowledge exists for crop.

        known crop != knowledge available
        """

        resolved_crop = self.resolve_crop(
            crop
        )

        candidate = (
            resolved_crop
            or self._clean_value(crop)
        )

        if not candidate:
            return False

        candidate_normalized = (
            self._normalize_value(
                candidate
            )
        )

        for database_crop in (
            self.get_database_crops()
        ):

            database_normalized = (
                self._normalize_value(
                    database_crop
                )
            )

            if (
                database_normalized
                == candidate_normalized
            ):
                return True

        return False

    # =========================================================
    # Canonicalize Database Crop
    # =========================================================

    def canonicalize_database_crop(
        self,
        crop: str,
    ) -> str:
        """
        Return configured canonical crop when available.

        Otherwise preserve the DB value so newly imported crops
        continue working without Python changes.
        """

        crop = self._clean_value(
            crop
        )

        if not crop:
            return ""

        resolved = self.resolve_crop(
            crop
        )

        return resolved or crop

    # =========================================================
    # Debug
    # =========================================================

    def debug(self):
        """
        Print runtime vocabulary information.
        """

        snapshot = (
            self.get_vocabulary_snapshot()
        )

        print()
        print("=" * 80)
        print("VOCABULARY SERVICE")
        print("=" * 80)

        print(
            "Known Crops       :",
            snapshot["known_crops"],
        )

        print(
            "Database Crops    :",
            snapshot["database_crops"],
        )

        print(
            "Categories        :",
            snapshot["categories"],
        )

        print(
            "Domains           :",
            snapshot["domains"],
        )

        print(
            "Stages            :",
            snapshot["stages"],
        )

        print(
            "Crop Alias Count  :",
            snapshot[
                "crop_alias_count"
            ],
        )

        print(
            "Term Alias Count  :",
            snapshot[
                "term_alias_count"
            ],
        )

        print(
            "Search Vocab Count:",
            snapshot[
                "search_vocabulary_count"
            ],
        )

        print(
            "Cache TTL Seconds :",
            self.CACHE_TTL_SECONDS,
        )

        print("=" * 80)
        print()

        return snapshot