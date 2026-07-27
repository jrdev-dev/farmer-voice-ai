from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    Custom user manager using email as the unique
    authentication identifier.
    """

    # =========================================================
    # Create User
    # =========================================================

    def create_user(
        self,
        email,
        password=None,
        **extra_fields,
    ):

        if not email:
            raise ValueError("Email address is required.")

        # Normalize + consistently lowercase email
        email = self.normalize_email(str(email).strip()).lower()

        user = self.model(
            email=email,
            **extra_fields,
        )

        user.set_password(password)

        user.save(using=self._db)

        return user

    # =========================================================
    # Create Superuser
    # =========================================================

    def create_superuser(
        self,
        email,
        password=None,
        **extra_fields,
    ):

        extra_fields.setdefault(
            "is_staff",
            True,
        )

        extra_fields.setdefault(
            "is_superuser",
            True,
        )

        extra_fields.setdefault(
            "is_active",
            True,
        )

        # Keep application-level role consistent
        # with Django superuser privileges.
        extra_fields.setdefault(
            "role",
            "ADMIN",
        )

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        if extra_fields.get("is_active") is not True:
            raise ValueError("Superuser must have is_active=True.")

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )
