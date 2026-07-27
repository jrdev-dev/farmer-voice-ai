from django.urls import path

from .views import OCRAPIView

urlpatterns = [
    path(
        "",
        OCRAPIView.as_view(),
        name="ocr",
    ),
]
