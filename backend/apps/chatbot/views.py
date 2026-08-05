import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from apps.analytics.models import AnalyticsEvent
from apps.analytics.services.analytics_service import AnalyticsService

from .serializers import ChatRequestSerializer
from .services.chat_service import ChatService
from .services.response_formatter import ResponseFormatter
from .services.response_validator import ResponseValidator

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["Chat"],
    summary="Chat with Farmer Voice AI",
    description="""
Send a farmer message to Farmer Voice AI.

The endpoint supports:
- authenticated farmer conversations
- multilingual input
- automatic language detection
- conversation memory
- contextual follow-up questions
- hybrid agricultural knowledge retrieval
- relevance validation
- grounded answer generation
- confidence score
- trusted source metadata

Supported language codes:
hi, en, hinglish, gu, mr, pa, ta, te

If language is not provided, the backend automatically
detects the language from the farmer's message.
""",
    request=ChatRequestSerializer,
    responses={
        200: OpenApiResponse(description="Chat response returned successfully."),
        400: OpenApiResponse(description="Invalid chat request."),
        401: OpenApiResponse(
            description=("Authentication credentials were not provided.")
        ),
        500: OpenApiResponse(description="Unexpected server error."),
    },
)
class ChatAPIView(APIView):
    """
    Main authenticated Farmer Voice AI chat endpoint.

    Flow
    ----
    Request
        -> Serializer Validation
        -> Authenticated User
        -> ChatService
        -> Analytics Event
        -> Final Public Response
    """

    permission_classes = [
        IsAuthenticated,
    ]

    # =========================================================
    # POST
    # =========================================================

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):

        # =====================================================
        # 1. Validate Request
        # =====================================================

        serializer = ChatRequestSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]

        # None means ChatService should automatically
        # detect the farmer's language.
        language = serializer.validated_data.get("language")

        # =====================================================
        # 2. Run Chat Pipeline
        # =====================================================

        try:

            service = ChatService()

            result = service.chat(
                user=request.user,
                message=message,
                language=language,
            )

        except Exception:

            logger.exception("Unexpected ChatService failure.")

            result = self._build_server_error(
                language=language,
            )

        # =====================================================
        # 3. Defensive Response Validation
        # =====================================================

        if not isinstance(
            result,
            dict,
        ):

            logger.error("ChatService returned a non-dictionary response.")

            result = self._build_server_error(
                language=language,
            )

        # =====================================================
        # 4. Record Text Chat Analytics
        # =====================================================
        #
        # AnalyticsService handles its own exceptions.
        # Analytics failure must never break chat.
        # =====================================================

        AnalyticsService.record_event(
            user=request.user,
            event_type=AnalyticsEvent.EventType.TEXT_CHAT,
            language=result.get(
                "language",
                language or "",
            ),
            success=result.get(
                "success",
                False,
            ),
            metadata={
                "confidence": result.get(
                    "confidence",
                    0,
                ),
                "confidence_label": result.get(
                    "confidence_label",
                    "",
                ),
                "match_type": result.get(
                    "match_type",
                    "",
                ),
                "fallback_used": result.get(
                    "fallback_used",
                    False,
                ),
                "fallback_source": result.get(
                    "fallback_source",
                ),
                "intent": result.get(
                    "intent",
                    "",
                ),
                "conversation_id": str(
                    result.get(
                        "conversation_id",
                        "",
                    )
                    or ""
                ),
                "message_id": result.get(
                    "message_id",
                ),
                "source_count": len(
                    result.get(
                        "sources",
                        [],
                    )
                    or []
                ),
            },
        )

        # =====================================================
        # 5. Return Stable API Response
        # =====================================================

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    # =========================================================
    # Controlled Server Error
    # =========================================================

    @staticmethod
    def _build_server_error(
        language=None,
    ):
        formatter = ResponseFormatter()
        validator = ResponseValidator()

        response = formatter.format_error(
            message=None,
            language=language,
            error_code="internal_server_error",
        )

        return validator.sanitize(response)


class ConversationListAPIView(APIView):
    """
    List user's past conversations or start a new conversation.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import Conversation

        conversations = (
            Conversation.objects.filter(user=request.user)
            .order_by("-updated_at", "-created_at")[:30]
        )
        data = []
        for conv in conversations:
            first_msg = conv.messages.filter(role="USER").first()
            title = conv.title or (first_msg.content[:40] if first_msg else "New Conversation")
            data.append({
                "id": str(conv.id),
                "title": title,
                "is_active": conv.is_active,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "message_count": conv.messages.count(),
            })
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        from .services.memory_service import MemoryService

        memory_service = MemoryService()
        new_conv = memory_service.start_new_conversation(user=request.user)
        return Response({
            "id": str(new_conv.id),
            "title": "New Conversation",
            "is_active": True,
        }, status=status.HTTP_201_CREATED)


class ConversationDetailAPIView(APIView):
    """
    Retrieve past messages or delete a specific conversation.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        from .models import Conversation

        try:
            conv = Conversation.objects.get(id=conversation_id, user=request.user)
        except (Conversation.DoesNotExist, ValueError):
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        # Mark as active conversation
        Conversation.objects.filter(user=request.user, is_active=True).update(is_active=False)
        conv.is_active = True
        conv.save(update_fields=["is_active"])

        messages_qs = conv.messages.order_by("created_at")
        messages_data = [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
            }
            for msg in messages_qs
        ]

        first_msg = conv.messages.filter(role="USER").first()
        title = conv.title or (first_msg.content[:40] if first_msg else "New Conversation")

        return Response({
            "id": str(conv.id),
            "title": title,
            "is_active": conv.is_active,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "messages": messages_data,
        }, status=status.HTTP_200_OK)

    def delete(self, request, conversation_id):
        from .models import Conversation

        try:
            conv = Conversation.objects.get(id=conversation_id, user=request.user)
            conv.delete()
            return Response({"detail": "Conversation deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except (Conversation.DoesNotExist, ValueError):
            return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
