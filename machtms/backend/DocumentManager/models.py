from django.db.models.query import QuerySet
from django.db.models.fields.related import OneToOneField
from django.utils import timezone
from django.db import models
from machtms.core.base.models import TMSModel
from datetime import timedelta

"""
Create a model that creates a document context

A context will contain document images
will have a merged choice
will have the image hash keys assigned into the context
"""


CATEGORIES = [
    ("RC", 'Customer Rate Confirmation'),
    ("CRC", 'Carrier Rate Confirmation'),
    ("INVOICE", 'Invoice'),
    ("POD", "Proof of Delivery"),
    ("LUMPER", "Lumper"),
    ("RECEIPT", "Receipts"),
    ("OTHER", "Other")
]

def get_expiration_time():
    return timezone.now() + timedelta(minutes=5)


class DocumentContext(TMSModel):
    created_on = models.DateTimeField(default=timezone.now)


class DocumentQueue(TMSModel):
    queue_hash_id = models.TextField()
    is_complete = models.BooleanField(default=False)
    document_context = models.ForeignKey(
            DocumentContext,
            on_delete=models.CASCADE,
            related_name="document_queues"
            )


class S3UploadImage(TMSModel):
    queue = models.ForeignKey(
            DocumentQueue,
            on_delete=models.CASCADE,
            related_name="s3_uploads"
            )
    object_key = models.CharField(max_length=200)
    filename = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORIES)
    content_type = models.TextField()
    created_on = models.DateTimeField(default=timezone.now)


class DocumentResults(TMSModel):
    queue = models.ForeignKey(DocumentQueue, on_delete=models.CASCADE)
    load = models.ForeignKey('machtms.Load', on_delete=models.CASCADE, null=True, blank=True)
    extracted = models.TextField()
    # status = models.Choices()
    status_message = models.TextField()
    created_on = models.DateTimeField(default=timezone.now)
    matched_loads = models.JSONField()


# if multiple files uploaded, assume merged.
# It's still assigned to same load, but will
# merge into one PDF document
# if a POD already exists
# prompt user to:
# replace or merge with existing POD
# lumpers/receipts will be merged into document
class DirectUpload(TMSModel):
    upload_log: "OneToOneField[UploadLog]"

    load = models.ForeignKey('machtms.Load', on_delete=models.CASCADE, related_name="uploads")

    queue_hash_id = models.TextField()

    object_key = models.TextField()
    filename = models.TextField()
    content_type = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORIES)

    created_on = models.DateTimeField(default=timezone.now)

# once this model is saved in a view, the view
# will call Celery to process this.
# 1. get the content from image or PDF (return Content)
# 2. turn it into a PDF with PDFPlumber
# 3. Save it to PostShipmentDocument


# this will be created in a Celery task,
# where the Celery task uploads the document
# to post_shipment specific bucket
class PostShipmentDocument(TMSModel):
    load = models.ForeignKey('machtms.Load', null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")

    object_key = models.TextField()
    filename = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORIES)
    content_type = models.TextField()

    created_on = models.DateTimeField(default=timezone.now)
    content = models.TextField(blank=True)


class SessionUploadLog(TMSModel):
    upload_logs: "QuerySet[UploadLog]"

    created_on = models.DateTimeField(default=timezone.now)
    load = models.ForeignKey('machtms.Load', on_delete=models.CASCADE)
    expiration = models.DateTimeField(default=get_expiration_time)


class UploadLog(TMSModel):

    STATUS = [
        ('idle', 'IDLE'),
        ('processing', 'PROCESSING'),
        ('success', 'COMPLETE'),
        ('error', 'ERROR')
    ]
    session = models.ForeignKey(
        SessionUploadLog,
        on_delete=models.CASCADE,
        related_name="upload_logs"
    )

    direct_upload = models.OneToOneField(
        DirectUpload,
        on_delete=models.CASCADE,
        related_name="upload_log"
    )

    status = models.CharField(max_length=20, default='idle', choices=STATUS)
    message = models.TextField(default='idling', blank=True)
    created_on = models.DateTimeField(default=timezone.now)

    expiration = models.DateTimeField(default=get_expiration_time)

