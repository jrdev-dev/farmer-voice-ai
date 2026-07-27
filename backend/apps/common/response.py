"""
Common response utilities for Farmer Voice AI.

Provides a consistent response structure across:
- Chat APIs
- Knowledge APIs
- Speech APIs
- OCR APIs
- Authentication APIs
- Future mobile/Ionic APIs

This module does not contain Django HttpResponse logic.
It builds plain Python dictionaries that can later be passed
to JsonResponse or Django REST Framework Response.
"""

from typing import Any, Dict, List, Optional

# ============================================================
# Helpers
# ============================================================


def _clean_text(value: Any) -> str:
    """
    Normalize a value into clean single-line text.
    """

    if value is None:
        return ""

    return " ".join(str(value).strip().split())


def _normalize_confidence(value: Any) -> int:
    """
    Normalize confidence into public 0-100 format.

    Supports:
        0.85 -> 85
        85   -> 85
        100  -> 100
    """

    try:
        confidence = float(value)

    except (TypeError, ValueError):
        return 0

    if 0.0 <= confidence <= 1.0:
        confidence *= 100.0

    confidence = max(
        0.0,
        min(confidence, 100.0),
    )

    return int(round(confidence))


def _confidence_label(
    confidence: int,
) -> str:
    """
    Convert confidence percentage to a public label.
    """

    if confidence >= 90:
        return "very_high"

    if confidence >= 80:
        return "high"

    if confidence >= 65:
        return "medium"

    if confidence >= 45:
        return "low"

    return "very_low"


# ============================================================
# Generic Success Response
# ============================================================


def success_response(
    data: Any = None,
    message: str = "",
    *,
    status_code: int = 200,
) -> Dict:
    """
    Build a generic successful application response.
    """

    response = {
        "success": True,
        "status_code": status_code,
    }

    message = _clean_text(message)

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    return response


# ============================================================
# Generic Error Response
# ============================================================


def error_response(
    message: str,
    *,
    error_code: str = "application_error",
    status_code: int = 400,
    details: Any = None,
) -> Dict:
    """
    Build a generic application error response.
    """

    message = _clean_text(message)

    if not message:
        message = "An application error occurred."

    response = {
        "success": False,
        "status_code": status_code,
        "error": error_code,
        "message": message,
    }

    if details is not None:
        response["details"] = details

    return response


# ============================================================
# Exception Response
# ============================================================


def exception_response(
    exc: Exception,
    *,
    status_code: int = 500,
    expose_details: bool = False,
) -> Dict:
    """
    Convert an exception into a normalized response.

    Custom FarmerVoiceAIException classes expose:
        error_code
        message
        details

    Unknown exceptions are not exposed directly unless
    expose_details=True.
    """

    error_code = getattr(
        exc,
        "error_code",
        "internal_error",
    )

    message = getattr(
        exc,
        "message",
        None,
    )

    details = getattr(
        exc,
        "details",
        None,
    )

    if not message:
        if expose_details:
            message = str(exc)

        else:
            message = "An internal application error occurred."

    response = error_response(
        message=message,
        error_code=error_code,
        status_code=status_code,
    )

    if expose_details and details is not None:
        response["details"] = details

    return response


# ============================================================
# Farmer Chat Success Response
# ============================================================


def chat_success_response(
    answer: str,
    *,
    confidence: Any = 0,
    sources: Optional[List[Dict]] = None,
    match_type: str = "hybrid",
    language: str = "",
    conversation_id: Any = None,
    message_id: Any = None,
    intent: str = "question",
    fallback_used: bool = False,
) -> Dict:
    """
    Build a successful farmer-facing chat response.

    Confidence is always returned as 0-100.
    """

    answer = _clean_text(answer)

    confidence = _normalize_confidence(confidence)

    response = {
        "success": True,
        "answer": answer,
        "confidence": confidence,
        "confidence_label": (_confidence_label(confidence)),
        "match_type": (_clean_text(match_type) or "hybrid"),
        "sources": (sources if isinstance(sources, list) else []),
        "fallback_used": bool(fallback_used),
    }

    language = _clean_text(language)

    intent = _clean_text(intent)

    if language:
        response["language"] = language

    if conversation_id is not None:
        response["conversation_id"] = str(conversation_id)

    if message_id is not None:
        response["message_id"] = str(message_id)

    if intent:
        response["intent"] = intent

    return response


# ============================================================
# Farmer Chat Failure Response
# ============================================================


def chat_failure_response(
    answer: str,
    *,
    language: str = "",
    conversation_id: Any = None,
    message_id: Any = None,
    intent: str = "question",
    match_type: str = "irrelevant",
    fallback_used: bool = True,
) -> Dict:
    """
    Build a controlled farmer-facing failed/irrelevant response.

    Important:
    A failed retrieval response always has:
        confidence = 0
        sources = []
    """

    answer = _clean_text(answer)

    if not answer:
        answer = (
            "मुझे इस प्रश्न का विश्वसनीय उत्तर उपलब्ध "
            "कृषि ज्ञान स्रोतों में नहीं मिला। कृपया अपने "
            "नजदीकी कृषि विशेषज्ञ या कृषि विज्ञान केंद्र "
            "(KVK) से संपर्क करें।"
        )

    response = {
        "success": False,
        "answer": answer,
        "confidence": 0,
        "confidence_label": "very_low",
        "match_type": (_clean_text(match_type) or "irrelevant"),
        "sources": [],
        "fallback_used": bool(fallback_used),
    }

    language = _clean_text(language)

    intent = _clean_text(intent)

    if language:
        response["language"] = language

    if conversation_id is not None:
        response["conversation_id"] = str(conversation_id)

    if message_id is not None:
        response["message_id"] = str(message_id)

    if intent:
        response["intent"] = intent

    return response


# ============================================================
# Validation Error Response
# ============================================================


def validation_error_response(
    message: str,
    *,
    fields: Optional[Dict] = None,
) -> Dict:
    """
    Build response for invalid incoming request data.
    """

    response = error_response(
        message=message,
        error_code="validation_error",
        status_code=400,
    )

    if fields:
        response["fields"] = fields

    return response


# ============================================================
# Authentication Responses
# ============================================================


def authentication_required_response() -> Dict:
    """
    Response when login/authentication is required.
    """

    return error_response(
        message="Authentication is required.",
        error_code="authentication_required",
        status_code=401,
    )


def permission_denied_response() -> Dict:
    """
    Response when authenticated user lacks permission.
    """

    return error_response(
        message=("You do not have permission to perform " "this action."),
        error_code="permission_denied",
        status_code=403,
    )


# ============================================================
# Not Found Response
# ============================================================


def not_found_response(
    message: str = "Requested resource was not found.",
) -> Dict:

    return error_response(
        message=message,
        error_code="not_found",
        status_code=404,
    )


# ============================================================
# Service Unavailable Response
# ============================================================


def service_unavailable_response(
    message: str = "Service is temporarily unavailable.",
) -> Dict:

    return error_response(
        message=message,
        error_code="service_unavailable",
        status_code=503,
    )


# ============================================================
# Pagination Response
# ============================================================


def paginated_response(
    items: List[Any],
    *,
    page: int,
    page_size: int,
    total: int,
) -> Dict:
    """
    Generic pagination structure for knowledge/history APIs.
    """

    try:
        page = max(
            1,
            int(page),
        )

    except (TypeError, ValueError):
        page = 1

    try:
        page_size = max(
            1,
            int(page_size),
        )

    except (TypeError, ValueError):
        page_size = 1

    try:
        total = max(
            0,
            int(total),
        )

    except (TypeError, ValueError):
        total = 0

    total_pages = (total + page_size - 1) // page_size if page_size else 0

    return {
        "success": True,
        "data": (items if isinstance(items, list) else []),
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": (page < total_pages),
            "has_previous": (page > 1),
        },
    }


# ============================================================
# Knowledge Import Response
# ============================================================


def import_response(
    *,
    success: bool,
    source_id: Any = None,
    total_records: int = 0,
    processed_records: int = 0,
    failed_records: int = 0,
    errors: Optional[List] = None,
) -> Dict:
    """
    Standard response for dataset/knowledge imports.
    """

    response = {
        "success": bool(success),
        "source_id": (str(source_id) if source_id is not None else None),
        "total_records": int(total_records or 0),
        "processed_records": int(processed_records or 0),
        "failed_records": int(failed_records or 0),
        "errors": (errors if isinstance(errors, list) else []),
    }

    return response


# ============================================================
# Speech Response
# ============================================================


def speech_response(
    *,
    text: str,
    language: str,
    audio_url: Optional[str] = None,
    transcription: Optional[str] = None,
) -> Dict:
    """
    Common response structure for STT/TTS/voice-chat APIs.
    """

    response = {
        "success": True,
        "text": _clean_text(text),
        "language": _clean_text(language),
    }

    if audio_url:
        response["audio_url"] = str(audio_url)

    if transcription:
        response["transcription"] = _clean_text(transcription)

    return response


# ============================================================
# API Envelope
# ============================================================


def api_response(
    *,
    success: bool,
    data: Any = None,
    message: str = "",
    error: Optional[str] = None,
    status_code: int = 200,
) -> Dict:
    """
    General-purpose API envelope.

    Prefer the specialized helpers above where possible.
    """

    response = {
        "success": bool(success),
        "status_code": int(status_code),
    }

    message = _clean_text(message)

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    if error:
        response["error"] = _clean_text(error)

    return response
