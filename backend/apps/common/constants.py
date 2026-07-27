"""
Project-wide constants for Farmer Voice AI.

IMPORTANT DESIGN RULE:
----------------------
Do NOT maintain a fixed master list of crops here.

The system is designed to support arbitrary crops from:
- Knowledge database
- Imported datasets
- VocabularyService
- CropResolver
- Future agricultural knowledge sources

This module should contain only stable application-level
constants.
"""

# ============================================================
# APPLICATION
# ============================================================

APP_NAME = "Farmer Voice AI"

APP_VERSION = "1.0.0"


# ============================================================
# SUPPORTED LANGUAGES
# ============================================================

LANGUAGE_ENGLISH = "en"
LANGUAGE_HINDI = "hi"
LANGUAGE_GUJARATI = "gu"
LANGUAGE_MARATHI = "mr"
LANGUAGE_PUNJABI = "pa"
LANGUAGE_TAMIL = "ta"
LANGUAGE_TELUGU = "te"


SUPPORTED_LANGUAGES = {
    LANGUAGE_ENGLISH,
    LANGUAGE_HINDI,
    LANGUAGE_GUJARATI,
    LANGUAGE_MARATHI,
    LANGUAGE_PUNJABI,
    LANGUAGE_TAMIL,
    LANGUAGE_TELUGU,
}


DEFAULT_LANGUAGE = LANGUAGE_HINDI


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "gu": "Gujarati",
    "mr": "Marathi",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
}


# ============================================================
# USER ROLES
# ============================================================

ROLE_ADMIN = "ADMIN"
ROLE_FARMER = "FARMER"
ROLE_EXPERT = "EXPERT"


USER_ROLES = {
    ROLE_ADMIN,
    ROLE_FARMER,
    ROLE_EXPERT,
}


# ============================================================
# CHAT INTENTS
# ============================================================

INTENT_QUESTION = "question"

INTENT_GREETING = "greeting"

INTENT_THANKS = "thanks"

INTENT_GOODBYE = "goodbye"

INTENT_HELP = "help"

INTENT_UNKNOWN = "unknown"


CHAT_INTENTS = {
    INTENT_QUESTION,
    INTENT_GREETING,
    INTENT_THANKS,
    INTENT_GOODBYE,
    INTENT_HELP,
    INTENT_UNKNOWN,
}


# ============================================================
# AGRICULTURAL TOPICS
# ============================================================

TOPIC_DISEASE = "disease"

TOPIC_PEST = "pest"

TOPIC_FERTILIZER = "fertilizer"

TOPIC_SEED = "seed"

TOPIC_SOIL = "soil"

TOPIC_WEATHER = "weather"

TOPIC_MARKET = "market"

TOPIC_SCHEME = "scheme"

TOPIC_IRRIGATION = "irrigation"

TOPIC_HARVEST = "harvest"

TOPIC_STORAGE = "storage"

TOPIC_WEED = "weed"

TOPIC_CULTIVATION = "cultivation"

TOPIC_GENERAL = "general"


AGRICULTURE_TOPICS = {
    TOPIC_DISEASE,
    TOPIC_PEST,
    TOPIC_FERTILIZER,
    TOPIC_SEED,
    TOPIC_SOIL,
    TOPIC_WEATHER,
    TOPIC_MARKET,
    TOPIC_SCHEME,
    TOPIC_IRRIGATION,
    TOPIC_HARVEST,
    TOPIC_STORAGE,
    TOPIC_WEED,
    TOPIC_CULTIVATION,
    TOPIC_GENERAL,
}


# ============================================================
# KNOWLEDGE CATEGORIES
# ============================================================
#
# These values intentionally match the current Knowledge model
# Category values where applicable.
# ============================================================

CATEGORY_DISEASE = "Disease"

CATEGORY_PEST = "Pest"

CATEGORY_FERTILIZER = "Fertilizer"

CATEGORY_SEED = "Seed"

CATEGORY_SOIL = "Soil"

CATEGORY_WEATHER = "Weather"

CATEGORY_MARKET = "Market"

CATEGORY_SCHEME = "Scheme"

CATEGORY_IRRIGATION = "Irrigation"

CATEGORY_HARVEST = "Harvest"

CATEGORY_STORAGE = "Storage"

CATEGORY_GENERAL = "General"


KNOWLEDGE_CATEGORIES = {
    CATEGORY_DISEASE,
    CATEGORY_PEST,
    CATEGORY_FERTILIZER,
    CATEGORY_SEED,
    CATEGORY_SOIL,
    CATEGORY_WEATHER,
    CATEGORY_MARKET,
    CATEGORY_SCHEME,
    CATEGORY_IRRIGATION,
    CATEGORY_HARVEST,
    CATEGORY_STORAGE,
    CATEGORY_GENERAL,
}


# ============================================================
# KNOWLEDGE SOURCE TYPES
# ============================================================

SOURCE_EXCEL = "excel"

SOURCE_CSV = "csv"

SOURCE_PDF = "pdf"

SOURCE_DOCX = "docx"

SOURCE_WEBSITE = "website"

SOURCE_API = "api"

SOURCE_IMAGE = "image"


KNOWLEDGE_SOURCE_TYPES = {
    SOURCE_EXCEL,
    SOURCE_CSV,
    SOURCE_PDF,
    SOURCE_DOCX,
    SOURCE_WEBSITE,
    SOURCE_API,
    SOURCE_IMAGE,
}


# ============================================================
# KNOWLEDGE SOURCE STATUS
# ============================================================

SOURCE_STATUS_PENDING = "pending"

SOURCE_STATUS_PROCESSING = "processing"

SOURCE_STATUS_COMPLETED = "completed"

SOURCE_STATUS_FAILED = "failed"


KNOWLEDGE_SOURCE_STATUSES = {
    SOURCE_STATUS_PENDING,
    SOURCE_STATUS_PROCESSING,
    SOURCE_STATUS_COMPLETED,
    SOURCE_STATUS_FAILED,
}


# ============================================================
# RETRIEVAL METHODS
# ============================================================

RETRIEVAL_KEYWORD = "keyword"

RETRIEVAL_BM25 = "bm25"

RETRIEVAL_FUZZY = "fuzzy"

RETRIEVAL_SEMANTIC = "semantic"

RETRIEVAL_HYBRID = "hybrid"


RETRIEVAL_METHODS = {
    RETRIEVAL_KEYWORD,
    RETRIEVAL_BM25,
    RETRIEVAL_FUZZY,
    RETRIEVAL_SEMANTIC,
    RETRIEVAL_HYBRID,
}


# ============================================================
# MATCH TYPES
# ============================================================

MATCH_EXACT = "exact"

MATCH_SEMANTIC = "semantic"

MATCH_HYBRID = "hybrid"

MATCH_KEYWORD = "keyword"

MATCH_BM25 = "bm25"

MATCH_FUZZY = "fuzzy"

MATCH_FALLBACK = "fallback"

MATCH_IRRELEVANT = "irrelevant"

MATCH_NONE = "none"


MATCH_TYPES = {
    MATCH_EXACT,
    MATCH_SEMANTIC,
    MATCH_HYBRID,
    MATCH_KEYWORD,
    MATCH_BM25,
    MATCH_FUZZY,
    MATCH_FALLBACK,
    MATCH_IRRELEVANT,
    MATCH_NONE,
}


# ============================================================
# CONFIDENCE
# ============================================================

CONFIDENCE_VERY_HIGH = "very_high"

CONFIDENCE_HIGH = "high"

CONFIDENCE_MEDIUM = "medium"

CONFIDENCE_LOW = "low"

CONFIDENCE_VERY_LOW = "very_low"


CONFIDENCE_LABELS = {
    CONFIDENCE_VERY_HIGH,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_VERY_LOW,
}


CONFIDENCE_VERY_HIGH_THRESHOLD = 90

CONFIDENCE_HIGH_THRESHOLD = 80

CONFIDENCE_MEDIUM_THRESHOLD = 65

CONFIDENCE_LOW_THRESHOLD = 45


# ============================================================
# RETRIEVAL DEFAULTS
# ============================================================

DEFAULT_RETRIEVAL_LIMIT = 5

DEFAULT_SOURCE_LIMIT = 3

MAX_RETRIEVAL_LIMIT = 20

MAX_PUBLIC_SOURCES = 5


# ============================================================
# RELEVANCE DEFAULTS
# ============================================================
#
# These correspond to the current RelevanceService architecture.
# RelevanceService may still own its exact thresholds.
#
# Keeping these here allows future centralization.
# ============================================================

MIN_SEMANTIC_SCORE = 0.72

STRONG_SEMANTIC_SCORE = 0.82

MIN_BM25_SCORE = 1.0

STRONG_BM25_SCORE = 2.0

MIN_KEYWORD_SCORE = 5.0

MIN_FUZZY_SCORE = 65.0

MIN_RETRIEVAL_EVIDENCE_COUNT = 2


# ============================================================
# RESPONSE LIMITS
# ============================================================

MIN_ANSWER_LENGTH = 2

MAX_ANSWER_LENGTH = 10000

MAX_CONVERSATION_CONTEXT_LENGTH = 8000


# ============================================================
# KNOWLEDGE QUALITY
# ============================================================

QUALITY_EXCELLENT = "excellent"

QUALITY_GOOD = "good"

QUALITY_ACCEPTABLE = "acceptable"

QUALITY_POOR = "poor"

QUALITY_INVALID = "invalid"


KNOWLEDGE_QUALITY_LEVELS = {
    QUALITY_EXCELLENT,
    QUALITY_GOOD,
    QUALITY_ACCEPTABLE,
    QUALITY_POOR,
    QUALITY_INVALID,
}


# ============================================================
# UNIT TYPES
# ============================================================

UNIT_WEIGHT = "weight"

UNIT_AREA = "area"

UNIT_VOLUME = "volume"

UNIT_LENGTH = "length"

UNIT_PERCENTAGE = "percentage"

UNIT_TEMPERATURE = "temperature"

UNIT_TIME = "time"

UNIT_COUNT = "count"

UNIT_UNKNOWN = "unknown"


UNIT_TYPES = {
    UNIT_WEIGHT,
    UNIT_AREA,
    UNIT_VOLUME,
    UNIT_LENGTH,
    UNIT_PERCENTAGE,
    UNIT_TEMPERATURE,
    UNIT_TIME,
    UNIT_COUNT,
    UNIT_UNKNOWN,
}


# ============================================================
# MESSAGE TYPES
# ============================================================

MESSAGE_USER = "user"

MESSAGE_ASSISTANT = "assistant"

MESSAGE_SYSTEM = "system"


MESSAGE_TYPES = {
    MESSAGE_USER,
    MESSAGE_ASSISTANT,
    MESSAGE_SYSTEM,
}


# ============================================================
# SAFE FARMER-FACING RESPONSES
# ============================================================

SAFE_FALLBACK_HI = (
    "मुझे उपलब्ध कृषि ज्ञान के आधार पर स्पष्ट उत्तर तैयार "
    "नहीं हो पाया। कृपया प्रश्न दोबारा पूछें।"
)


NO_KNOWLEDGE_FALLBACK_HI = (
    "मुझे इस प्रश्न का विश्वसनीय उत्तर उपलब्ध कृषि ज्ञान "
    "स्रोतों में नहीं मिला। कृपया अपने नजदीकी कृषि विशेषज्ञ "
    "या कृषि विज्ञान केंद्र (KVK) से संपर्क करें।"
)


SAFE_FALLBACK_EN = (
    "I could not prepare a reliable answer from the available "
    "agricultural knowledge. Please ask the question again."
)


NO_KNOWLEDGE_FALLBACK_EN = (
    "I could not find a reliable answer to this question in "
    "the available agricultural knowledge sources. Please "
    "consult a nearby agricultural expert."
)


# ============================================================
# BOOLEAN VALUES USED DURING IMPORT
# ============================================================

TRUE_VALUES = {
    "true",
    "1",
    "yes",
    "y",
    "active",
}

FALSE_VALUES = {
    "false",
    "0",
    "no",
    "n",
    "inactive",
}


# ============================================================
# TEXT / NORMALIZATION
# ============================================================

EMPTY_VALUES = {
    "",
    "none",
    "null",
    "nan",
    "n/a",
    "na",
    "-",
}


# ============================================================
# UNIVERSAL CROP DESIGN
# ============================================================
#
# DO NOT add something like:
#
# CROPS = {
#     "soybean",
#     "wheat",
#     "rice",
# }
#
# Doing that would make the system dependent on a manually
# maintained crop list.
#
# Crop knowledge must instead come dynamically from:
#
# Knowledge.crop
# VocabularyService
# CropResolver
# imported agricultural datasets
# aliases/synonyms discovered from knowledge
#
# This allows future data such as:
#
# onion
# garlic
# tomato
# potato
# sugarcane
# mustard
# groundnut
# banana
# mango
# vegetables
# fruits
# pulses
# cereals
# horticultural crops
# regional crops
#
# without changing this constants file.
# ============================================================
