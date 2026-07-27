from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AuthService:
    """
    Authentication service for Farmer Voice AI.

    Responsibilities
    ----------------
    - Create users securely
    - Generate JWT access/refresh tokens
    - Blacklist refresh tokens on logout
    - Change user passwords
    """

    # =========================================================
    # Create User
    # =========================================================

    @staticmethod
    @transaction.atomic
    def create_user(validated_data):
        """
        Create a new user using the custom UserManager.

        Password hashing is handled by create_user().
        """

        data = validated_data.copy()

        # Defensive cleanup.
        # Serializer already removes this field.
        data.pop(
            "confirm_password",
            None,
        )

        email = str(data.get("email", "")).strip().lower()

        password = data.pop("password")

        if not email:
            raise ValueError("Email is required.")

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=data.get(
                "first_name",
                "",
            ),
            last_name=data.get(
                "last_name",
                "",
            ),
            phone_number=data.get("phone_number"),
            role=data.get(
                "role",
                User.Roles.FARMER,
            ),
        )

        return user

    # =========================================================
    # Login / JWT Generation
    # =========================================================

    @staticmethod
    def login_user(user):
        """
        Generate JWT access and refresh tokens
        for an authenticated active user.
        """

        if user is None:
            raise ValueError("User is required.")

        if not user.is_active:
            raise ValueError("Inactive users cannot login.")

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number,
                "role": user.role,
            },
        }

    # =========================================================
    # Logout
    # =========================================================

    @staticmethod
    def logout_user(refresh_token):
        """
        Blacklist a refresh token.

        Requires:
        rest_framework_simplejwt.token_blacklist
        to be enabled in INSTALLED_APPS.
        """

        if not refresh_token:
            raise ValueError("Refresh token is required.")

        token = RefreshToken(str(refresh_token).strip())

        token.blacklist()

        return True

    # =========================================================
    # Change Password
    # =========================================================

    @staticmethod
    @transaction.atomic
    def change_password(
        user,
        new_password,
    ):
        """
        Securely update the authenticated user's password.

        Password validation is performed by
        ChangePasswordSerializer before this method is called.
        """

        if user is None:
            raise ValueError("User is required.")

        if not new_password:
            raise ValueError("New password is required.")

        user.set_password(new_password)

        user.save(
            update_fields=[
                "password",
            ]
        )

        return user
