from django.db import models
from django.utils import timezone
from machtms.core.base.models import TMSModel


class SessionStatus(models.TextChoices):
    UPLOADING = 'uploading', 'Uploading'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    PARTIALLY_FAILED = 'partially_failed', 'Partially Failed'
    FAILED = 'failed', 'Failed'


class DocumentStatus(models.TextChoices):
    UPLOADING = 'uploading', 'Uploading'
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    PARSED = 'parsed', 'Parsed'
    MISCLASSIFIED = 'misclassified', 'Misclassified'
    FAILED = 'failed', 'Failed'


class ParsingSession(TMSModel):
    """Represents a batch upload session for rate confirmation documents."""

    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.UPLOADING,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_documents(self):
        return self.documents.count()

    @property
    def completed_documents(self):
        return self.documents.filter(
            status__in=[
                DocumentStatus.PARSED,
                DocumentStatus.MISCLASSIFIED,
                DocumentStatus.FAILED,
            ]
        ).count()

    @property
    def progress(self):
        total = self.total_documents
        if total == 0:
            return 0
        return round((self.completed_documents / total) * 100, 1)

    def recompute_status(self):
        """Recompute session status based on the statuses of all child documents."""
        docs = self.documents.all()
        if not docs.exists():
            return
        statuses = set(docs.values_list('status', flat=True))
        terminal = {
            DocumentStatus.PARSED,
            DocumentStatus.MISCLASSIFIED,
            DocumentStatus.FAILED,
        }
        if statuses <= terminal:
            if statuses == {DocumentStatus.PARSED} or statuses <= {
                DocumentStatus.PARSED,
                DocumentStatus.MISCLASSIFIED,
            }:
                self.status = SessionStatus.COMPLETED
            elif DocumentStatus.PARSED in statuses or DocumentStatus.MISCLASSIFIED in statuses:
                self.status = SessionStatus.PARTIALLY_FAILED
            else:
                self.status = SessionStatus.FAILED
            self.save(update_fields=['status', 'updated_at'])

    class Meta:
        app_label = 'machtms'

    def __str__(self):
        return f"ParsingSession {self.pk} ({self.status})"


class RateConDocument(TMSModel):
    """Represents a single uploaded rate confirmation document within a session."""

    session = models.ForeignKey(
        ParsingSession,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADING,
    )
    original_filename = models.TextField()
    s3_key = models.TextField()
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, default='application/pdf')
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'machtms'

    def __str__(self):
        return f"RateConDocument {self.pk} ({self.original_filename})"


class ParsedRateCon(TMSModel):
    """Stores the parsed output from a rate confirmation document."""

    document = models.OneToOneField(
        RateConDocument,
        on_delete=models.CASCADE,
        related_name='parsed_content',
    )
    raw_text = models.TextField(blank=True)
    structured_data = models.JSONField(null=True, blank=True)
    load = models.ForeignKey(
        'machtms.Load',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    classification_passed = models.BooleanField(default=True)
    classification_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'machtms'

    def __str__(self):
        return f"ParsedRateCon for Document {self.document_id}"
