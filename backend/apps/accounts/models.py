from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):

    class Roles(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        FARMER = "FARMER", "Farmer"
        EXPERT = "EXPERT", "Expert"

    email = models.EmailField(unique=True)

    first_name = models.CharField(max_length=100)

    last_name = models.CharField(max_length=100, blank=True)

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.FARMER,
    )

    phone_number = models.CharField(
        max_length=15,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email