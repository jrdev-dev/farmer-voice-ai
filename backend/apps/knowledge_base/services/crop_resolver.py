import re
from typing import Dict, List, Optional, Any

from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vocabulary_service import VocabularyService


class CropResolver:
    """
    Universal crop resolver for Farmer Voice AI.

    Responsibilities:
    - Detect crop references in farmer queries
    - Resolve aliases to canonical crop names
    - Support Hindi / English / Hinglish aliases
    - Use dynamic database vocabulary
    - Distinguish:
        * crop recognized
        * crop knowledge available
        * crop not recognized
    - Detect multiple crops
    - Compare query crop with retrieved knowledge crop
    - Prevent crop-mismatch retrieval
    - Support newly imported crops without code changes

    Important:
    There is intentionally NO hardcoded SUPPORTED_CROPS list.

    Crop vocabulary comes from:
    - crop_aliases.json
    - active Knowledge database records
    """

    def __init__(self):
        self.normalizer = QuestionNormalizer()
        self.vocabulary = VocabularyService()

    # =========================================================
    # Basic Helpers
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
    # Resolve Single Crop
    # =========================================================

    def resolve(
        self,
        value: str,
    ) -> Optional[str]:
        """
        Resolve a crop name or alias to a canonical crop.

        Examples may include:
            soybean
            soyabeen
            सोयाबीन

        Unknown values return None rather than being guessed.
        """

        value = self._clean_value(value)

        if not value:
            return None

        resolved = self.vocabulary.resolve_crop(value)

        if resolved:
            return resolved

        # -----------------------------------------------------
        # A crop may have been newly imported into the DB
        # without yet existing in crop_aliases.json.
        # -----------------------------------------------------

        normalized_value = self._normalize(value)

        if not normalized_value:
            return None

        for database_crop in self.vocabulary.get_database_crops():

            if self._normalize(database_crop) == normalized_value:
                return self.vocabulary.canonicalize_database_crop(database_crop)

        return None

    # =========================================================
    # Detect Crops In Query
    # =========================================================

    def detect(
        self,
        text: str,
    ) -> List[str]:
        """
        Detect crop references appearing in text.

        Returns canonical crop names without duplicates.
        """

        text = self._clean_value(text)

        if not text:
            return []

        detected = self.vocabulary.detect_crops(text)

        results = []

        for crop in detected:
            canonical = self.resolve(
                crop
            ) or self.vocabulary.canonicalize_database_crop(crop)

            if canonical and not self._contains_crop(
                results,
                canonical,
            ):
                results.append(canonical)

        return results

    # =========================================================
    # Primary Crop
    # =========================================================

    def get_primary_crop(
        self,
        text: str,
    ) -> Optional[str]:
        """
        Return the primary explicit crop in a query.

        When multiple crops occur, the first explicit crop
        occurrence is returned.

        Multi-crop information remains available through detect().
        """

        crops = self.detect(text)

        if not crops:
            return None

        return crops[0]

    # =========================================================
    # Detailed Query Resolution
    # =========================================================

    def resolve_query(
        self,
        text: str,
    ) -> Dict:
        """
        Analyze crop information in a farmer query.

        Example response:

        {
            "crop": "Wheat",
            "crops": ["Wheat"],
            "crop_detected": True,
            "multiple_crops": False,
            "knowledge_available": False,
            "normalized_crop": "wheat"
        }
        """

        crops = self.detect(text)

        primary_crop = crops[0] if crops else None

        knowledge_available = False

        if primary_crop:
            knowledge_available = self.has_knowledge(primary_crop)

        return {
            "crop": primary_crop,
            "crops": crops,
            "crop_detected": bool(crops),
            "multiple_crops": len(crops) > 1,
            "knowledge_available": knowledge_available,
            "normalized_crop": (self._normalize(primary_crop) if primary_crop else ""),
        }

    # =========================================================
    # Knowledge Availability
    # =========================================================

    def has_knowledge(
        self,
        crop: str,
    ) -> bool:
        """
        Return True only when active Knowledge records exist
        for the crop.

        A recognized vocabulary crop is not automatically
        considered knowledge-supported.
        """

        crop = self._clean_value(crop)

        if not crop:
            return False

        return self.vocabulary.has_crop_knowledge(crop)

    # =========================================================
    # Compare Crops
    # =========================================================

    def same_crop(
        self,
        crop_a: str,
        crop_b: str,
    ) -> bool:
        """
        Alias-aware crop equality.

        Example:
            सोयाबीन == soybean
        """

        crop_a = self._clean_value(crop_a)
        crop_b = self._clean_value(crop_b)

        if not crop_a or not crop_b:
            return False

        resolved_a = self.resolve(crop_a) or crop_a

        resolved_b = self.resolve(crop_b) or crop_b

        normalized_a = self._normalize(resolved_a)

        normalized_b = self._normalize(resolved_b)

        return bool(normalized_a and normalized_b and normalized_a == normalized_b)

    # =========================================================
    # Crop Compatibility
    # =========================================================

    def check_compatibility(
        self,
        query_text: str,
        knowledge_crop: str,
    ) -> Dict:
        """
        Determine whether retrieved knowledge belongs to the
        crop explicitly requested by the farmer.

        This is an important retrieval safety check.

        Rules:
        - No crop in query:
            do not reject solely on crop.
        - Crop in query + no crop in knowledge:
            neutral/unknown.
        - Crop in query + matching knowledge crop:
            compatible.
        - Crop in query + different knowledge crop:
            incompatible.
        """

        query_crops = self.detect(query_text)

        knowledge_crop = self._clean_value(knowledge_crop)

        # -----------------------------------------------------
        # Query has no explicit crop.
        # Conversation context may resolve it elsewhere.
        # -----------------------------------------------------

        if not query_crops:
            return {
                "is_compatible": True,
                "status": "query_crop_not_explicit",
                "query_crops": [],
                "knowledge_crop": knowledge_crop or None,
                "reason": (
                    "No explicit crop detected in query; "
                    "crop compatibility was not used to reject."
                ),
            }

        # -----------------------------------------------------
        # Retrieved record has no crop metadata.
        # -----------------------------------------------------

        if not knowledge_crop:
            return {
                "is_compatible": True,
                "status": "knowledge_crop_missing",
                "query_crops": query_crops,
                "knowledge_crop": None,
                "reason": (
                    "Query contains a crop but retrieved knowledge "
                    "has no crop metadata."
                ),
            }

        # -----------------------------------------------------
        # Match against every crop explicitly mentioned.
        # -----------------------------------------------------

        for query_crop in query_crops:

            if self.same_crop(
                query_crop,
                knowledge_crop,
            ):
                return {
                    "is_compatible": True,
                    "status": "crop_match",
                    "query_crops": query_crops,
                    "knowledge_crop": (self.resolve(knowledge_crop) or knowledge_crop),
                    "reason": "Query crop matches knowledge crop.",
                }

        return {
            "is_compatible": False,
            "status": "crop_mismatch",
            "query_crops": query_crops,
            "knowledge_crop": (self.resolve(knowledge_crop) or knowledge_crop),
            "reason": ("Query crop does not match retrieved " "knowledge crop."),
        }

    # =========================================================
    # Compare Query Crop Against Knowledge Object
    # =========================================================

    def check_knowledge(
        self,
        query_text: str,
        knowledge,
    ) -> Dict:
        """
        Convenience wrapper accepting a Knowledge model object.
        """

        if knowledge is None:
            return {
                "is_compatible": False,
                "status": "knowledge_missing",
                "query_crops": self.detect(query_text),
                "knowledge_crop": None,
                "reason": "Knowledge object is missing.",
            }

        knowledge_crop = getattr(
            knowledge,
            "crop",
            "",
        )

        return self.check_compatibility(
            query_text=query_text,
            knowledge_crop=knowledge_crop,
        )

    # =========================================================
    # Detect Crop Switch
    # =========================================================

    def detect_crop_switch(
        self,
        current_text: str,
        previous_crop: Optional[str],
    ) -> Dict:
        """
        Detect an explicit crop change during conversation.

        Example:
            Previous context: Soybean
            New message: गेहूं में कौन सी खाद डालूं?

        Result:
            crop_switched = True
        """

        current_crops = self.detect(current_text)

        current_crop = current_crops[0] if current_crops else None

        previous_crop = self._clean_value(previous_crop)

        if not current_crop:
            return {
                "crop_switched": False,
                "current_crop": None,
                "previous_crop": previous_crop or None,
                "explicit_crop": False,
            }

        if not previous_crop:
            return {
                "crop_switched": False,
                "current_crop": current_crop,
                "previous_crop": None,
                "explicit_crop": True,
            }

        switched = not self.same_crop(
            current_crop,
            previous_crop,
        )

        return {
            "crop_switched": switched,
            "current_crop": current_crop,
            "previous_crop": (self.resolve(previous_crop) or previous_crop),
            "explicit_crop": True,
        }

    # =========================================================
    # Canonicalize Crop
    # =========================================================

    def canonicalize(
        self,
        crop: str,
    ) -> str:
        """
        Canonicalize a crop without losing newly imported
        database values.
        """

        crop = self._clean_value(crop)

        if not crop:
            return ""

        resolved = self.resolve(crop)

        if resolved:
            return resolved

        return self.vocabulary.canonicalize_database_crop(crop)

    # =========================================================
    # Internal Duplicate Helper
    # =========================================================

    def _contains_crop(
        self,
        crops: List[str],
        candidate: str,
    ) -> bool:

        for crop in crops:

            if self.same_crop(
                crop,
                candidate,
            ):
                return True

        return False

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        text: str,
    ) -> Dict:

        result = self.resolve_query(text)

        print("\n" + "=" * 80)
        print("CROP RESOLVER")
        print("=" * 80)

        print(
            "Text                :",
            text,
        )

        print(
            "Detected Crops      :",
            result["crops"],
        )

        print(
            "Primary Crop        :",
            result["crop"],
        )

        print(
            "Multiple Crops      :",
            result["multiple_crops"],
        )

        print(
            "Knowledge Available :",
            result["knowledge_available"],
        )

        print("=" * 80 + "\n")

        return result
