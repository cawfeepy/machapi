## models.py

```python
from django.db import models
from django.conf import settings


class ParsingSession(models.Model):
    class Status(models.TextChoices):
        UPLOADING = "uploading"
        PROCESSING = "processing"
        COMPLETED = "completed"
        PARTIALLY_FAILED = "partially_failed"
        FAILED = "failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parsing_sessions",
    )
    name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPLOADING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total_documents(self):
        return self.documents.count()

    @property
    def completed_documents(self):
        return self.documents.filter(status=Document.Status.COMPLETED).count()

    @property
    def progress(self):
        total = self.total_documents
        if total == 0:
            return 0
        return int((self.completed_documents / total) * 100)

    def recompute_status(self):
        """Call this every time a child document's status changes."""
        statuses = set(self.documents.values_list("status", flat=True))

        if statuses <= {Document.Status.COMPLETED}:
            self.status = self.Status.COMPLETED
        elif statuses <= {Document.Status.FAILED}:
            self.status = self.Status.FAILED
        elif (
            Document.Status.FAILED in statuses
            and Document.Status.COMPLETED in statuses
        ):
            if not statuses & {
                Document.Status.UPLOADING,
                Document.Status.PENDING,
                Document.Status.PROCESSING,
            }:
                self.status = self.Status.PARTIALLY_FAILED
            else:
                self.status = self.Status.PROCESSING
        else:
            self.status = self.Status.PROCESSING

        self.save(update_fields=["status", "updated_at"])


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADING = "uploading"
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    session = models.ForeignKey(
        ParsingSession, on_delete=models.CASCADE, related_name="documents"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    original_filename = models.CharField(max_length=512)
    s3_key = models.CharField(max_length=1024, unique=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPLOADING
    )
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ParsedContent(models.Model):
    """Separated from Document so the main table stays lightweight for listing."""

    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="parsed_content"
    )
    raw_text = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
```

## tasks.py

```python
import boto3
from celery import shared_task
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

from .models import Document, ParsedContent, ParsingSession


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def parse_document(self, document_id):
    doc = Document.objects.select_related("session").get(id=document_id)
    doc.status = Document.Status.PROCESSING
    doc.celery_task_id = self.request.id
    doc.save(update_fields=["status", "celery_task_id", "updated_at"])

    try:
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=doc.s3_key)
        file_bytes = response["Body"].read()

        raw_text = your_parser(file_bytes, doc.mime_type)

        ParsedContent.objects.create(
            document=doc,
            raw_text=raw_text,
            metadata={"pages": count_pages(file_bytes), "chars": len(raw_text)},
        )

        doc.status = Document.Status.COMPLETED
        doc.processed_at = timezone.now()
        doc.save(update_fields=["status", "processed_at", "updated_at"])

    except Exception as exc:
        doc.status = Document.Status.FAILED
        doc.error_message = str(exc)[:2000]
        doc.save(update_fields=["status", "error_message", "updated_at"])
        raise self.retry(exc=exc)

    finally:
        doc.session.recompute_status()


@shared_task
def cleanup_stale_uploads():
    """Runs every 10 minutes via Celery Beat."""
    cutoff = timezone.now() - timedelta(minutes=15)
    stale = Document.objects.filter(
        status=Document.Status.UPLOADING,
        created_at__lt=cutoff,
    )

    session_ids = set(stale.values_list("session_id", flat=True))
    stale.update(status=Document.Status.FAILED, error_message="Upload never completed")

    for session in ParsingSession.objects.filter(id__in=session_ids):
        session.recompute_status()


@shared_task
def retry_stuck_tasks():
    """Re-enqueues tasks stuck in PROCESSING state."""
    cutoff = timezone.now() - timedelta(minutes=30)
    stuck = Document.objects.filter(
        status=Document.Status.PROCESSING,
        updated_at__lt=cutoff,
    )
    for doc in stuck:
        doc.status = Document.Status.PENDING
        doc.save(update_fields=["status", "updated_at"])
        parse_document.delay(doc.id)


# ── Placeholders — replace with your actual logic ─────────────────────

def your_parser(file_bytes, mime_type):
    raise NotImplementedError("Replace with your actual parser")

def count_pages(file_bytes):
    raise NotImplementedError("Replace with your actual page counter")
```

## serializers.py

```python
from rest_framework import serializers
from .models import Document, ParsedContent, ParsingSession


class ParsedContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParsedContent
        fields = ["raw_text", "metadata", "created_at"]


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id",
            "original_filename",
            "status",
            "error_message",
            "created_at",
            "processed_at",
        ]


class DocumentDetailSerializer(DocumentSerializer):
    parsed_content = ParsedContentSerializer(read_only=True)

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ["parsed_content"]


class SessionSerializer(serializers.ModelSerializer):
    total_documents = serializers.IntegerField(read_only=True)
    completed_documents = serializers.IntegerField(read_only=True)
    progress = serializers.IntegerField(read_only=True)

    class Meta:
        model = ParsingSession
        fields = [
            "id",
            "name",
            "status",
            "total_documents",
            "completed_documents",
            "progress",
            "created_at",
        ]


class SessionDetailSerializer(SessionSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta(SessionSerializer.Meta):
        fields = SessionSerializer.Meta.fields + ["documents"]


class FileUploadRequestSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=512)
    mime_type = serializers.CharField(max_length=128, required=False, default="")


class CreateSessionRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, default="")
    files = FileUploadRequestSerializer(many=True, min_length=1)
```

## views.py

```python
from uuid import uuid4

import boto3
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document, ParsingSession
from .serializers import (
    CreateSessionRequestSerializer,
    SessionDetailSerializer,
    SessionSerializer,
)
from .tasks import parse_document


class CreateSessionView(APIView):
    """
    POST /api/sessions/create/
    Body: {
        "name": "Q4 Reports",
        "files": [
            {"filename": "report.pdf", "mime_type": "application/pdf"},
            {"filename": "data.csv", "mime_type": "text/csv"}
        ]
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ParsingSession.objects.create(
            owner=request.user,
            name=serializer.validated_data.get("name", ""),
        )

        s3 = boto3.client("s3")
        documents = []

        for f in serializer.validated_data["files"]:
            s3_key = f"uploads/{request.user.id}/{session.id}/{uuid4().hex}/{f['filename']}"

            presigned_url = s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": s3_key},
                ExpiresIn=300,
            )

            doc = Document.objects.create(
                session=session,
                owner=request.user,
                original_filename=f["filename"],
                s3_key=s3_key,
                mime_type=f.get("mime_type", ""),
            )

            documents.append(
                {
                    "document_id": doc.id,
                    "filename": f["filename"],
                    "presigned_url": presigned_url,
                }
            )

        return Response(
            {"session_id": session.id, "documents": documents},
            status=status.HTTP_201_CREATED,
        )


class SessionListView(ListAPIView):
    """
    GET /api/sessions/
    GET /api/sessions/?status=uploading,processing
    """

    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ParsingSession.objects.filter(owner=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status__in=status_filter.split(","))
        return qs.prefetch_related("documents")


class SessionDetailView(RetrieveAPIView):
    """
    GET /api/sessions/<id>/
    """

    serializer_class = SessionDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ParsingSession.objects.filter(owner=self.request.user).prefetch_related(
            "documents__parsed_content"
        )


class DocumentUploadCompleteView(APIView):
    """
    POST /api/documents/<id>/upload-complete/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        doc = get_object_or_404(Document, pk=pk, owner=request.user)

        if doc.status != Document.Status.UPLOADING:
            return Response(
                {"error": "Document is not in uploading state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc.status = Document.Status.PENDING
        doc.save(update_fields=["status", "updated_at"])
        doc.session.recompute_status()

        parse_document.delay(doc.id)

        return Response({"status": "queued"})
```
