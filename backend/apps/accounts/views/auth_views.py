import logging

from rest_framework import status
from rest_framework.generics import (
    CreateAPIView,
    GenericAPIView,
)
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.serializers.auth_serializer import (
    RegisterSerializer,
    LoginSerializer,
    LogoutSerializer,
    ChangePasswordSerializer,
)
from apps.accounts.services.auth_service import AuthService

logger = logging.getLogger(__name__)


# ============================================================
# Register
# ============================================================


class RegisterAPIView(CreateAPIView):
    """
    Register a new Farmer Voice AI user.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        token_data = AuthService.login_user(user)

        return Response(
            {
                "success": True,
                "message": "User registered successfully.",
                "data": token_data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# Login
# ============================================================


class LoginAPIView(GenericAPIView):
    """
    Authenticate a user and return JWT tokens.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        data = AuthService.login_user(user)

        return Response(
            {
                "success": True,
                "message": "Login successful.",
                "data": data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# Logout
# ============================================================


class LogoutAPIView(GenericAPIView):
    """
    Logout authenticated user by blacklisting
    the supplied refresh token.
    """

    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh"]

        try:

            AuthService.logout_user(refresh_token)

        except TokenError:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Refresh token is invalid " "or has already been revoked."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:

            logger.exception("Unexpected logout failure.")

            return Response(
                {
                    "success": False,
                    "message": ("Unable to logout at this time."),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "message": "Logout successful.",
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# Change Password
# ============================================================


class ChangePasswordAPIView(GenericAPIView):
    """
    Change password for the authenticated user.
    """

    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(raise_exception=True)

        AuthService.change_password(
            user=request.user,
            new_password=(serializer.validated_data["new_password"]),
        )

        return Response(
            {
                "success": True,
                "message": ("Password changed successfully."),
            },
            status=status.HTTP_200_OK,
        )
