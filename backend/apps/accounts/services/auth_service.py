from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AuthService:
    @staticmethod
    def create_user(validated_data):
        """
        Create a new user with hashed password.
        """

        validated_data.pop("confirm_password", None)

        user = User.objects.create_user(
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone_number=validated_data.get("phone_number"),
            role=validated_data.get("role", User.Roles.FARMER),
            password=validated_data["password"],
        )

        return user

    @staticmethod
    def login_user(user):
        """
        Generate JWT Access & Refresh Tokens.
        """

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
    @staticmethod
    def logout_user(refresh_token):
        token = RefreshToken(refresh_token)
        token.blacklist()
    
    @staticmethod
    def change_password(user, new_password):
        user.set_password(new_password)
        user.save(update_fields=["password"])