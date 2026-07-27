import re
from typing import Any, Dict, List, Optional, Tuple


class UnitNormalizer:
    """
    Universal unit normalization service for agricultural queries
    and knowledge-base content.

    Responsibilities:
    - Normalize common agricultural units
    - Recognize Hindi + English unit aliases
    - Parse quantities
    - Parse numeric ranges
    - Parse per-area application rates
    - Normalize weight, volume, area, time, percentage,
      length and temperature units
    - Convert compatible units into canonical base units

    Important:
    This service performs UNIT conversion only.

    It does NOT:
    - Recommend agricultural dosage
    - Infer missing quantities
    - Change unsupported agricultural facts
    - Generate farming advice
    """

    # =========================================================
    # Canonical Unit Definitions
    # =========================================================

    UNIT_DEFINITIONS = {
        # -----------------------------------------------------
        # Weight
        # Base unit: gram
        # -----------------------------------------------------
        "mg": {
            "dimension": "weight",
            "base_unit": "g",
            "factor": 0.001,
            "aliases": {
                "mg",
                "milligram",
                "milligrams",
                "मिलीग्राम",
            },
        },
        "g": {
            "dimension": "weight",
            "base_unit": "g",
            "factor": 1.0,
            "aliases": {
                "g",
                "gm",
                "gms",
                "gram",
                "grams",
                "ग्राम",
            },
        },
        "kg": {
            "dimension": "weight",
            "base_unit": "g",
            "factor": 1000.0,
            "aliases": {
                "kg",
                "kgs",
                "kilogram",
                "kilograms",
                "किलो",
                "किलोग्राम",
            },
        },
        "quintal": {
            "dimension": "weight",
            "base_unit": "g",
            "factor": 100000.0,
            "aliases": {
                "quintal",
                "quintals",
                "qtl",
                "क्विंटल",
            },
        },
        "tonne": {
            "dimension": "weight",
            "base_unit": "g",
            "factor": 1000000.0,
            "aliases": {
                "ton",
                "tons",
                "tonne",
                "tonnes",
                "metric ton",
                "metric tonne",
                "टन",
            },
        },
        # -----------------------------------------------------
        # Volume
        # Base unit: millilitre
        # -----------------------------------------------------
        "ml": {
            "dimension": "volume",
            "base_unit": "ml",
            "factor": 1.0,
            "aliases": {
                "ml",
                "milliliter",
                "milliliters",
                "millilitre",
                "millilitres",
                "मिलीलीटर",
                "मि.ली.",
                "मिली लीटर",
            },
        },
        "l": {
            "dimension": "volume",
            "base_unit": "ml",
            "factor": 1000.0,
            "aliases": {
                "l",
                "lt",
                "ltr",
                "ltrs",
                "liter",
                "liters",
                "litre",
                "litres",
                "लीटर",
            },
        },
        # -----------------------------------------------------
        # Area
        # Base unit: square metre
        # -----------------------------------------------------
        "sqm": {
            "dimension": "area",
            "base_unit": "sqm",
            "factor": 1.0,
            "aliases": {
                "sqm",
                "sq m",
                "square meter",
                "square meters",
                "square metre",
                "square metres",
                "वर्ग मीटर",
            },
        },
        "acre": {
            "dimension": "area",
            "base_unit": "sqm",
            "factor": 4046.8564224,
            "aliases": {
                "acre",
                "acres",
                "एकड़",
                "एकड़",
            },
        },
        "hectare": {
            "dimension": "area",
            "base_unit": "sqm",
            "factor": 10000.0,
            "aliases": {
                "hectare",
                "hectares",
                "ha",
                "हेक्टेयर",
            },
        },
        # Bigha is intentionally NOT converted to sqm because
        # its size varies by region.
        "bigha": {
            "dimension": "regional_area",
            "base_unit": "bigha",
            "factor": 1.0,
            "aliases": {
                "bigha",
                "bighas",
                "बीघा",
            },
        },
        # -----------------------------------------------------
        # Length
        # Base unit: millimetre
        # -----------------------------------------------------
        "mm": {
            "dimension": "length",
            "base_unit": "mm",
            "factor": 1.0,
            "aliases": {
                "mm",
                "millimeter",
                "millimeters",
                "millimetre",
                "millimetres",
                "मिमी",
                "मिलीमीटर",
            },
        },
        "cm": {
            "dimension": "length",
            "base_unit": "mm",
            "factor": 10.0,
            "aliases": {
                "cm",
                "centimeter",
                "centimeters",
                "centimetre",
                "centimetres",
                "सेमी",
                "सेंटीमीटर",
            },
        },
        "m": {
            "dimension": "length",
            "base_unit": "mm",
            "factor": 1000.0,
            "aliases": {
                "meter",
                "meters",
                "metre",
                "metres",
                "मीटर",
            },
        },
        # -----------------------------------------------------
        # Time
        # Base unit: day
        # -----------------------------------------------------
        "hour": {
            "dimension": "time",
            "base_unit": "day",
            "factor": 1.0 / 24.0,
            "aliases": {
                "hour",
                "hours",
                "hr",
                "hrs",
                "घंटा",
                "घंटे",
                "घंटों",
            },
        },
        "day": {
            "dimension": "time",
            "base_unit": "day",
            "factor": 1.0,
            "aliases": {
                "day",
                "days",
                "दिन",
                "दिनों",
            },
        },
        "week": {
            "dimension": "time",
            "base_unit": "day",
            "factor": 7.0,
            "aliases": {
                "week",
                "weeks",
                "सप्ताह",
                "हफ्ता",
                "हफ्ते",
                "हफ्तों",
            },
        },
        # Month length is not fixed, therefore we recognize it
        # but do not convert it into days.
        "month": {
            "dimension": "calendar_time",
            "base_unit": "month",
            "factor": 1.0,
            "aliases": {
                "month",
                "months",
                "महीना",
                "महीने",
                "महीनों",
                "माह",
            },
        },
        # -----------------------------------------------------
        # Percentage
        # -----------------------------------------------------
        "percent": {
            "dimension": "percentage",
            "base_unit": "percent",
            "factor": 1.0,
            "aliases": {
                "%",
                "percent",
                "percentage",
                "प्रतिशत",
            },
        },
        # -----------------------------------------------------
        # Temperature
        # -----------------------------------------------------
        "celsius": {
            "dimension": "temperature",
            "base_unit": "celsius",
            "factor": 1.0,
            "aliases": {
                "°c",
                "c",
                "celsius",
                "degree celsius",
                "degrees celsius",
                "सेल्सियस",
                "डिग्री सेल्सियस",
            },
        },
    }

    RATE_SEPARATORS = {
        "/",
        "per",
        "प्रति",
    }

    def __init__(self):
        self.alias_map = self._build_alias_map()

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _clean_text(value: Any) -> str:

        if value is None:
            return ""

        value = str(value).strip()

        value = value.replace("–", "-")
        value = value.replace("—", "-")

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value

    @staticmethod
    def _clean_number(
        value: Any,
    ) -> Optional[float]:

        try:
            return float(str(value).replace(",", "").strip())

        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def _display_number(
        value: Optional[float],
    ):

        if value is None:
            return None

        if float(value).is_integer():
            return int(value)

        return round(
            float(value),
            8,
        )

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
    # Alias Map
    # =========================================================

    def _build_alias_map(
        self,
    ) -> Dict[str, str]:

        alias_map = {}

        for canonical, config in self.UNIT_DEFINITIONS.items():

            aliases = set(
                config.get(
                    "aliases",
                    set(),
                )
            )

            aliases.add(canonical)

            for alias in aliases:

                cleaned = self._clean_text(alias).lower()

                if cleaned:
                    alias_map[cleaned] = canonical

        return alias_map

    # =========================================================
    # Unit Regex
    # =========================================================

    def _unit_regex(
        self,
    ) -> str:

        aliases = sorted(
            self.alias_map.keys(),
            key=len,
            reverse=True,
        )

        aliases = [alias for alias in aliases if alias != "%"]

        return "|".join(re.escape(alias) for alias in aliases)

    # =========================================================
    # Normalize Unit
    # =========================================================

    def normalize_unit(
        self,
        unit: Any,
    ) -> Optional[str]:

        cleaned = self._clean_text(unit).lower()

        if not cleaned:
            return None

        return self.alias_map.get(cleaned)

    # =========================================================
    # Unit Information
    # =========================================================

    def get_unit_info(
        self,
        unit: Any,
    ) -> Optional[Dict]:

        canonical = self.normalize_unit(unit)

        if not canonical:
            return None

        config = self.UNIT_DEFINITIONS[canonical]

        return {
            "unit": canonical,
            "dimension": config["dimension"],
            "base_unit": config["base_unit"],
            "factor": config["factor"],
        }

    # =========================================================
    # Convert to Base Unit
    # =========================================================

    def to_base(
        self,
        value: Any,
        unit: Any,
    ) -> Optional[Dict]:

        numeric_value = self._clean_number(value)

        if numeric_value is None:
            return None

        canonical = self.normalize_unit(unit)

        if not canonical:
            return None

        config = self.UNIT_DEFINITIONS[canonical]

        base_value = numeric_value * config["factor"]

        return {
            "original_value": self._display_number(numeric_value),
            "original_unit": canonical,
            "dimension": config["dimension"],
            "base_value": self._display_number(base_value),
            "base_unit": config["base_unit"],
        }

    # =========================================================
    # Convert Between Compatible Units
    # =========================================================

    def convert(
        self,
        value: Any,
        from_unit: Any,
        to_unit: Any,
    ) -> Optional[float]:

        numeric_value = self._clean_number(value)

        if numeric_value is None:
            return None

        source = self.normalize_unit(from_unit)

        target = self.normalize_unit(to_unit)

        if not source or not target:
            return None

        source_config = self.UNIT_DEFINITIONS[source]

        target_config = self.UNIT_DEFINITIONS[target]

        if source_config["dimension"] != target_config["dimension"]:
            return None

        base_value = numeric_value * source_config["factor"]

        converted = base_value / target_config["factor"]

        return self._display_number(converted)

    # =========================================================
    # Quantity Extraction
    # =========================================================

    def extract_quantities(
        self,
        text: str,
    ) -> List[Dict]:

        text = self._clean_text(text)

        if not text:
            return []

        unit_regex = self._unit_regex()

        pattern = (
            r"(?P<value>\d+(?:\.\d+)?)"
            r"\s*"
            r"(?P<unit>" + unit_regex + r")"
            r"(?![\w\u0900-\u097F])"
        )

        results = []

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        ):

            value = self._clean_number(match.group("value"))

            raw_unit = match.group("unit")

            canonical = self.normalize_unit(raw_unit)

            if value is None or not canonical:
                continue

            base = self.to_base(
                value,
                canonical,
            )

            item = {
                "text": match.group(0),
                "value": self._display_number(value),
                "raw_unit": raw_unit,
                "unit": canonical,
                "dimension": (self.UNIT_DEFINITIONS[canonical]["dimension"]),
                "base_value": (base["base_value"] if base else None),
                "base_unit": (base["base_unit"] if base else None),
            }

            if item not in results:
                results.append(item)

        # -----------------------------------------------------
        # Percentage with %
        # -----------------------------------------------------

        percentage_pattern = r"(?P<value>\d+(?:\.\d+)?)" r"\s*%"

        for match in re.finditer(
            percentage_pattern,
            text,
        ):

            value = self._clean_number(match.group("value"))

            if value is None:
                continue

            item = {
                "text": match.group(0),
                "value": self._display_number(value),
                "raw_unit": "%",
                "unit": "percent",
                "dimension": "percentage",
                "base_value": self._display_number(value),
                "base_unit": "percent",
            }

            if item not in results:
                results.append(item)

        return results

    # =========================================================
    # Range Extraction
    # =========================================================

    def extract_ranges(
        self,
        text: str,
    ) -> List[Dict]:

        text = self._clean_text(text)

        if not text:
            return []

        unit_regex = self._unit_regex()

        pattern = (
            r"(?P<start>\d+(?:\.\d+)?)"
            r"\s*"
            r"(?:-|to|से)"
            r"\s*"
            r"(?P<end>\d+(?:\.\d+)?)"
            r"(?:\s*"
            r"(?P<unit>" + unit_regex + r"))?"
        )

        results = []

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        ):

            start = self._clean_number(match.group("start"))

            end = self._clean_number(match.group("end"))

            raw_unit = match.group("unit")

            if start is None or end is None:
                continue

            canonical = self.normalize_unit(raw_unit) if raw_unit else None

            item = {
                "text": match.group(0),
                "start": self._display_number(start),
                "end": self._display_number(end),
                "unit": canonical,
                "base_start": None,
                "base_end": None,
                "base_unit": None,
            }

            if canonical:

                start_base = self.to_base(
                    start,
                    canonical,
                )

                end_base = self.to_base(
                    end,
                    canonical,
                )

                if start_base:
                    item["base_start"] = start_base["base_value"]

                    item["base_unit"] = start_base["base_unit"]

                if end_base:
                    item["base_end"] = end_base["base_value"]

            if item not in results:
                results.append(item)

        return results

    # =========================================================
    # Rate Extraction
    # =========================================================

    def extract_rates(
        self,
        text: str,
    ) -> List[Dict]:
        """
        Extract agricultural application rates.

        Examples:
            5 kg/acre
            5 किलो प्रति एकड़
            20 litre per hectare
            500 ग्राम/एकड़
        """

        text = self._clean_text(text)

        if not text:
            return []

        unit_regex = self._unit_regex()

        pattern = (
            r"(?P<value>\d+(?:\.\d+)?)"
            r"\s*"
            r"(?P<numerator>" + unit_regex + r")"
            r"\s*"
            r"(?:/|per|प्रति)"
            r"\s*"
            r"(?P<denominator>" + unit_regex + r")"
        )

        results = []

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        ):

            value = self._clean_number(match.group("value"))

            numerator_raw = match.group("numerator")

            denominator_raw = match.group("denominator")

            numerator = self.normalize_unit(numerator_raw)

            denominator = self.normalize_unit(denominator_raw)

            if value is None or not numerator or not denominator:
                continue

            numerator_config = self.UNIT_DEFINITIONS[numerator]

            denominator_config = self.UNIT_DEFINITIONS[denominator]

            numerator_base_value = value * numerator_config["factor"]

            denominator_base_value = denominator_config["factor"]

            base_rate = None

            if denominator_base_value:

                base_rate = numerator_base_value / denominator_base_value

            item = {
                "text": match.group(0),
                "value": self._display_number(value),
                "numerator_unit": numerator,
                "denominator_unit": denominator,
                "numerator_dimension": (numerator_config["dimension"]),
                "denominator_dimension": (denominator_config["dimension"]),
                "base_value": self._display_number(base_rate),
                "base_numerator_unit": (numerator_config["base_unit"]),
                "base_denominator_unit": (denominator_config["base_unit"]),
            }

            if item not in results:
                results.append(item)

        return results

    # =========================================================
    # Rate Conversion
    # =========================================================

    def convert_rate(
        self,
        value: Any,
        numerator_from: str,
        denominator_from: str,
        numerator_to: str,
        denominator_to: str,
    ) -> Optional[float]:
        """
        Convert compatible agricultural rates.

        Example:
            kg/acre -> kg/hectare

        Regional units such as bigha are intentionally not
        converted into acre/hectare.
        """

        numeric_value = self._clean_number(value)

        if numeric_value is None:
            return None

        num_from = self.normalize_unit(numerator_from)

        den_from = self.normalize_unit(denominator_from)

        num_to = self.normalize_unit(numerator_to)

        den_to = self.normalize_unit(denominator_to)

        if not all(
            [
                num_from,
                den_from,
                num_to,
                den_to,
            ]
        ):
            return None

        nf = self.UNIT_DEFINITIONS[num_from]

        df = self.UNIT_DEFINITIONS[den_from]

        nt = self.UNIT_DEFINITIONS[num_to]

        dt = self.UNIT_DEFINITIONS[den_to]

        if nf["dimension"] != nt["dimension"]:
            return None

        if df["dimension"] != dt["dimension"]:
            return None

        # Regional area conversions are unsafe without
        # location-specific definitions.
        if df["dimension"] == "regional_area" or dt["dimension"] == "regional_area":

            if den_from != den_to:
                return None

        numerator_base = numeric_value * nf["factor"]

        # value is numerator / denominator.
        # Convert denominator scale into base denominator.
        base_rate = numerator_base / df["factor"]

        converted = base_rate * dt["factor"] / nt["factor"]

        return self._display_number(converted)

    # =========================================================
    # Detect Units
    # =========================================================

    def detect_units(
        self,
        text: str,
    ) -> List[str]:

        text = self._clean_text(text)

        if not text:
            return []

        text_lower = text.lower()

        detected = []

        aliases = sorted(
            self.alias_map.keys(),
            key=len,
            reverse=True,
        )

        for alias in aliases:

            canonical = self.alias_map[alias]

            if alias == "%":

                if "%" in text_lower:

                    if canonical not in detected:
                        detected.append(canonical)

                continue

            pattern = (
                r"(?<![\w\u0900-\u097F])" + re.escape(alias) + r"(?![\w\u0900-\u097F])"
            )

            if re.search(
                pattern,
                text_lower,
                flags=re.IGNORECASE | re.UNICODE,
            ):

                if canonical not in detected:
                    detected.append(canonical)

        return detected

    # =========================================================
    # Normalize Text Units
    # =========================================================

    def normalize_text_units(
        self,
        text: str,
    ) -> str:
        """
        Replace recognized unit aliases with canonical names.

        Example:
            "5 किलो प्रति एकड़"
            ->
            "5 kg प्रति acre"

        This is intended for retrieval/index normalization,
        not farmer-facing display.
        """

        result = self._clean_text(text)

        if not result:
            return ""

        aliases = sorted(
            self.alias_map.keys(),
            key=len,
            reverse=True,
        )

        for alias in aliases:

            if alias == "%":
                continue

            canonical = self.alias_map[alias]

            pattern = (
                r"(?<![\w\u0900-\u097F])" + re.escape(alias) + r"(?![\w\u0900-\u097F])"
            )

            result = re.sub(
                pattern,
                canonical,
                result,
                flags=re.IGNORECASE | re.UNICODE,
            )

        result = re.sub(
            r"\s+",
            " ",
            result,
        ).strip()

        return result

    # =========================================================
    # Full Analysis
    # =========================================================

    def analyze(
        self,
        text: str,
    ) -> Dict:

        original_text = self._clean_text(text)

        return {
            "original_text": original_text,
            "normalized_unit_text": (self.normalize_text_units(original_text)),
            "units": self.detect_units(original_text),
            "quantities": (self.extract_quantities(original_text)),
            "ranges": self.extract_ranges(original_text),
            "rates": self.extract_rates(original_text),
        }

    # =========================================================
    # Quantity Equivalence
    # =========================================================

    def quantities_equivalent(
        self,
        value1: Any,
        unit1: str,
        value2: Any,
        unit2: str,
        tolerance: float = 1e-6,
    ) -> bool:
        """
        Determine whether two quantities represent
        approximately the same physical value.

        Examples:
            5 kg == 5000 g
            1 litre == 1000 ml
        """

        first = self.to_base(
            value1,
            unit1,
        )

        second = self.to_base(
            value2,
            unit2,
        )

        if not first or not second:
            return False

        if first["dimension"] != second["dimension"]:
            return False

        if first["base_unit"] != second["base_unit"]:
            return False

        difference = abs(float(first["base_value"]) - float(second["base_value"]))

        return difference <= tolerance

    # =========================================================
    # Debug
    # =========================================================

    def debug(
        self,
        text: str,
    ) -> Dict:

        result = self.analyze(text)

        print("\n" + "=" * 80)
        print("UNIT NORMALIZER")
        print("=" * 80)

        print(
            "Original        :",
            result["original_text"],
        )

        print(
            "Normalized      :",
            result["normalized_unit_text"],
        )

        print(
            "Units           :",
            result["units"],
        )

        print(
            "Quantities      :",
            result["quantities"],
        )

        print(
            "Ranges          :",
            result["ranges"],
        )

        print(
            "Rates           :",
            result["rates"],
        )

        print("=" * 80 + "\n")

        return result
