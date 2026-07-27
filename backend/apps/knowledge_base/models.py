from django.db import models


class KnowledgeSource(models.Model):

    class SourceType(models.TextChoices):
        EXCEL = "excel", "Excel"
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"
        DOCX = "docx", "DOCX"
        WEBSITE = "website", "Website"
        API = "api", "API"
        IMAGE = "image", "Image"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    title = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True
    )

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
    )

    source_name = models.CharField(
        max_length=255,
        blank=True,
    )

    file = models.FileField(
        upload_to="knowledge_sources/",
        blank=True,
        null=True,
    )

    language = models.CharField(
        max_length=20,
        default="en",
    )

    version = models.CharField(
        max_length=20,
        default="1.0",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # ---------------------------------------------------------
    # Import Statistics
    # ---------------------------------------------------------

    total_records = models.PositiveIntegerField(
        default=0,
    )

    processed_records = models.PositiveIntegerField(
        default=0,
    )

    failed_records = models.PositiveIntegerField(
        default=0,
    )

    # ---------------------------------------------------------
    # Processing Information
    # ---------------------------------------------------------

    error_message = models.TextField(
        blank=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # ---------------------------------------------------------
    # Audit Fields
    # ---------------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.title


class Knowledge(models.Model):

    class Category(models.TextChoices):
        DISEASE = "Disease", "Disease"
        PEST = "Pest", "Pest"
        FERTILIZER = "Fertilizer", "Fertilizer"
        SEED = "Seed", "Seed"
        SOIL = "Soil", "Soil"
        WEATHER = "Weather", "Weather"
        MARKET = "Market", "Market"
        SCHEME = "Scheme", "Government Scheme"
        IRRIGATION = "Irrigation", "Irrigation"
        HARVEST = "Harvest", "Harvest"
        STORAGE = "Storage", "Storage"
        GENERAL = "General", "General"

    knowledge_source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="knowledge_items",
    )

    # =========================================================
    # Agriculture Information
    # =========================================================

    crop = models.CharField(
        max_length=100,
        blank=True,
    )

    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.GENERAL,
    )

    subcategory = models.CharField(
        max_length=100,
        blank=True,
    )

    domain = models.CharField(
        max_length=100,
        blank=True,
        help_text="Disease, Pest, Fertilizer, Irrigation, Weather, etc.",
    )

    stage = models.CharField(
        max_length=100,
        blank=True,
    )

    # =========================================================
    # Question & Answer
    # =========================================================

    question = models.TextField()

    normalized_question = models.TextField(
        blank=True,
        help_text="Normalized question used for multilingual search.",
    )

    answer = models.TextField()

    search_text = models.TextField(
        blank=True,
        help_text="Combined searchable text used for embeddings and semantic search.",
    )

    # =========================================================
    # Metadata
    # =========================================================

    keywords = models.TextField(
        blank=True,
    )

    prepared_by = models.CharField(
        max_length=255,
        blank=True,
    )

    language = models.CharField(
        max_length=20,
        default="en",
    )

    priority = models.PositiveIntegerField(
        default=1,
    )

    is_active = models.BooleanField(
        default=True,
    )

    # =========================================================
    # Audit Fields
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.crop or 'General'} - {self.question[:60]}"