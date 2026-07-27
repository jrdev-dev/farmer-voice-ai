from django.contrib.auth import (
    authenticate,
    get_user_model,
)
from django.contrib.auth.password_validation import (
    validate_password,
)

from rest_framework import serializers

from apps.accounts.services.auth_service import AuthService

User = get_user_model()


# ============================================================
# Register
# ============================================================


class RegisterSerializer(serializers.ModelSerializer):
    """
    Validate and create a new user account.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={
            "input_type": "password",
        },
    )

    confirm_password = serializers.CharField(
        write_only=True,
        style={
            "input_type": "password",
        },
    )

    class Meta:
        model = User

        fields = (
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "password",
            "confirm_password",
        )

    # ========================================================
    # Email
    # ========================================================

    def validate_email(self, value):

        email = value.strip().lower()

        if User.objects.filter(email__iexact=email).exists():

            raise serializers.ValidationError("User with this email already exists.")

        return email

    # ========================================================
    # Object Validation
    # ========================================================

    def validate(self, attrs):

        password = attrs.get("password")

        confirm_password = attrs.get("confirm_password")

        # ----------------------------------------------------
        # Password confirmation
        # ----------------------------------------------------

        if password != confirm_password:

            raise serializers.ValidationError(
                {"confirm_password": ("Passwords do not match.")}
            )

        # ----------------------------------------------------
        # Django password validation
        # ----------------------------------------------------

        temporary_user = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )

        validate_password(
            password,
            user=temporary_user,
        )

        return attrs

    # ========================================================
    # Create
    # ========================================================

    def create(
        self,
        validated_data,
    ):

        # confirm_password must never reach
        # the model/service creation layer.

        validated_data.pop(
            "confirm_password",
            None,
        )

        return AuthService.create_user(validated_data)


# ============================================================
# Login
# ============================================================


class LoginSerializer(serializers.Serializer):
    """
    Authenticate user using email and password.
    """

    email = serializers.EmailField()

    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    def validate_email(
        self,
        value,
    ):

        return value.strip().lower()

    def validate(
        self,
        attrs,
    ):

        email = attrs.get("email")

        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if user is None:

            raise serializers.ValidationError(
                {"detail": ("Invalid email or password.")}
            )

        if not user.is_active:

            raise serializers.ValidationError({"detail": ("User account is inactive.")})

        attrs["user"] = user

        return attrs


# ============================================================
# Logout
# ============================================================


class LogoutSerializer(serializers.Serializer):
    """
    Validate refresh token supplied during logout.
    """

    refresh = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )


# ============================================================
# Change Password
# ============================================================


class ChangePasswordSerializer(serializers.Serializer):
    """
    Validate authenticated password change request.
    """

    old_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
        style={
            "input_type": "password",
        },
    )

    confirm_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={
            "input_type": "password",
        },
    )

    def validate(
        self,
        attrs,
    ):

        request = self.context.get("request")

        if request is None:

            raise serializers.ValidationError("Request context is required.")

        user = request.user

        old_password = attrs["old_password"]

        new_password = attrs["new_password"]

        confirm_password = attrs["confirm_password"]

        # ----------------------------------------------------
        # Verify current password
        # ----------------------------------------------------

        if not user.check_password(old_password):

            raise serializers.ValidationError(
                {"old_password": ("Old password is incorrect.")}
            )

        # ----------------------------------------------------
        # New password confirmation
        # ----------------------------------------------------

        if new_password != confirm_password:

            raise serializers.ValidationError(
                {"confirm_password": ("Passwords do not match.")}
            )

        # ----------------------------------------------------
        # Prevent reusing current password
        # ----------------------------------------------------

        if user.check_password(new_password):

            raise serializers.ValidationError(
                {
                    "new_password": (
                        "New password must be different " "from the current password."
                    )
                }
            )

        # ----------------------------------------------------
        # Django password validators
        # ----------------------------------------------------

        validate_password(
            new_password,
            user=user,
        )

        return attrs
