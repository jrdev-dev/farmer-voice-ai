from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views.auth_views import (
    LoginAPIView,
    LogoutAPIView,
    RegisterAPIView,
    ChangePasswordAPIView
)
from apps.accounts.views.profile_views import ProfileAPIView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change_password"),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
]