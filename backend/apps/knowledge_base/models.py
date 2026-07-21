from django.db import models


class KnowledgeSource(models.Model):
    SOURCE_TYPES = [
        ("excel", "Excel"),
        ("csv", "CSV"),
        ("pdf", "PDF"),
        ("docx", "DOCX"),
        ("website", "Website"),
        ("api", "API"),
        ("image", "Image"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPES
    )

    source_name = models.CharField(
        max_length=255,
        blank=True
    )

    file = models.FileField(
        upload_to="knowledge_sources/",
        blank=True,
        null=True
    )

    language = models.CharField(
        max_length=20,
        default="en"
    )

    version = models.CharField(
        max_length=20,
        default="1.0"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Knowledge(models.Model):

    CATEGORY_CHOICES = [
        ("Disease", "Disease"),
        ("Pest", "Pest"),
        ("Fertilizer", "Fertilizer"),
        ("Seed", "Seed"),
        ("Soil", "Soil"),
        ("Weather", "Weather"),
        ("Market", "Market"),
        ("Scheme", "Government Scheme"),
        ("Irrigation", "Irrigation"),
        ("Harvest", "Harvest"),
        ("Storage", "Storage"),
        ("General", "General"),
    ]

    knowledge_source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="knowledge_items"
    )

    crop = models.CharField(max_length=100)

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="General"
    )

    subcategory = models.CharField(
        max_length=100,
        blank=True
    )

    stage = models.CharField(
        max_length=100,
        blank=True
    )

    question = models.TextField()

    answer = models.TextField()

    keywords = models.TextField(
        blank=True
    )

    language = models.CharField(
        max_length=20,
        default="en"
    )

    priority = models.PositiveIntegerField(
        default=1
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.crop} - {self.question[:50]}"