import logging
import uuid
from datetime import timedelta
from io import BytesIO

import pymupdf
from celery import shared_task, group
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    ParsingSession,
    RateConDocument,
    ParsedRateCon,
    DocumentStatus,
    SessionStatus,
)

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_buffer: BytesIO) -> str:
    """Extract text from a PDF file buffer using pymupdf."""
    doc = pymupdf.open(stream=file_buffer.read(), filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def process_single_document(document_id: int):
    """Process a single rate confirmation document.

    This is a plain function (not a Celery task) that:
    1. Downloads from S3
    2. Extracts text via pymupdf
    3. Calls the rate_con_processor agent
    4. Parses agent response
    5. Creates ParsedRateCon record
    6. Updates document status
    """
    from machtms.core.utils import s3_utils

    doc = RateConDocument.objects.select_related(
        'session', 'session__organization'
    ).get(pk=document_id)
    session = doc.session
    organization = session.organization

    # Guard against double-processing (e.g. concurrent task dispatch)
    if doc.status not in (DocumentStatus.PENDING, DocumentStatus.PROCESSING):
        return

    try:
        doc.status = DocumentStatus.PROCESSING
        doc.save(update_fields=['status', 'updated_at'])

        # Download from S3
        file_buffer = s3_utils.download_from_buffer(
            doc.s3_key,
            bucket_name=settings.AWS_UPLOAD_BUCKET,
        )

        # Extract text
        text = extract_text_from_pdf(file_buffer)

        if not text.strip():
            doc.status = DocumentStatus.FAILED
            doc.error_message = "No text could be extracted from the PDF."
            doc.processed_at = timezone.now()
            doc.save(update_fields=['status', 'error_message', 'processed_at', 'updated_at'])
            return

        # Call the agent (returns ParsedRateConData via output_schema)
        from machtms.agents.members.rate_con_processor import rate_con_processor

        response = rate_con_processor.run(
            text,
            session_id=str(uuid.uuid4()),
            dependencies={
                "organization": organization,
                "celery_task_id": doc.celery_task_id,
                "ratecon_id": doc.pk,
            },
        )

        parsed_data = response.content  # ParsedRateConData instance

        # Create ParsedRateCon record
        ParsedRateCon.objects.create(
            organization=organization,
            document=doc,
            raw_text=parsed_data.model_dump_json(),
            structured_data=parsed_data.model_dump(),
            classification_passed=(parsed_data.classification == 'PASS'),
            classification_reason=parsed_data.classification_reason,
        )

        if parsed_data.classification == 'PASS':
            doc.status = DocumentStatus.PARSED
            doc.processed_at = timezone.now()
            doc.save(update_fields=['status', 'processed_at', 'updated_at'])

            # Trigger load creation from parsed rate con data
            try:
                from machtms.agents.members.ratecon_load_creator import ratecon_load_creator

                creator_prompt = (
                    f"Create a load from this parsed rate confirmation data (JSON):\n\n"
                    f"{parsed_data.model_dump_json(indent=2)}"
                )

                ratecon_load_creator.run(
                    creator_prompt,
                    session_id=str(uuid.uuid4()),
                    dependencies={
                        "organization": organization,
                        "celery_task_id": doc.celery_task_id,
                        "ratecon_id": doc.pk,
                    },
                )
            except Exception as load_err:
                logger.exception(
                    f"Load creation failed for document {document_id}: {load_err}"
                )
        else:
            doc.status = DocumentStatus.MISCLASSIFIED
            doc.processed_at = timezone.now()
            doc.save(update_fields=['status', 'processed_at', 'updated_at'])

    except Exception as e:
        logger.exception(f"Error processing document {document_id}: {e}")
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)[:500]
        doc.processed_at = timezone.now()
        doc.save(update_fields=['status', 'error_message', 'processed_at', 'updated_at'])

    finally:
        session.recompute_status()


@shared_task
def process_document(document_id: int):
    """Celery task wrapper around process_single_document."""
    process_single_document(document_id)


@shared_task
def process_session_sync(session_id: int):
    """Process all pending documents in a session sequentially (Mode A)."""
    session = ParsingSession.objects.get(pk=session_id)
    session.status = SessionStatus.PROCESSING
    session.save(update_fields=['status', 'updated_at'])

    pending_docs = session.documents.filter(
        status=DocumentStatus.PENDING
    ).order_by('created_at')

    for doc in pending_docs:
        process_single_document(doc.pk)

    session.recompute_status()


@shared_task
def process_session_async(session_id: int, max_workers: int = 5):
    """Process all pending documents in a session in parallel (Mode B).

    Dispatches up to max_workers process_document_worker tasks.
    """
    session = ParsingSession.objects.get(pk=session_id)
    session.status = SessionStatus.PROCESSING
    session.save(update_fields=['status', 'updated_at'])

    pending_count = session.documents.filter(status=DocumentStatus.PENDING).count()
    worker_count = min(pending_count, max_workers)

    if worker_count > 0:
        job = group(
            process_document_worker.s(session_id) for _ in range(worker_count)
        )
        job.apply_async()


@shared_task
def process_document_worker(session_id: int):
    """Worker for parallel processing mode.

    Claims and processes PENDING documents one at a time using
    SELECT FOR UPDATE SKIP LOCKED.
    """
    session = ParsingSession.objects.get(pk=session_id)

    while True:
        with transaction.atomic():
            doc = (
                RateConDocument.objects
                .select_for_update(skip_locked=True)
                .filter(session=session, status=DocumentStatus.PENDING)
                .first()
            )
            if doc is None:
                break
            doc.status = DocumentStatus.PROCESSING
            doc.save(update_fields=['status', 'updated_at'])

        # Process outside the transaction (LLM call is long-running)
        process_single_document(doc.pk)

    session.recompute_status()


@shared_task
def cleanup_stale_uploads():
    """Periodic cleanup of documents stuck in UPLOADING state for more than 1 hour."""
    cutoff = timezone.now() - timedelta(hours=1)
    stale_qs = RateConDocument.objects.filter(
        status=DocumentStatus.UPLOADING,
        created_at__lt=cutoff,
    )
    # Capture affected session IDs before the bulk update
    session_ids = set(stale_qs.values_list('session_id', flat=True))
    count = stale_qs.update(
        status=DocumentStatus.FAILED,
        error_message='Upload timed out.',
    )
    for sid in session_ids:
        try:
            session = ParsingSession.objects.get(pk=sid)
            session.recompute_status()
        except ParsingSession.DoesNotExist:
            pass

    if count > 0:
        logger.info(f"Cleaned up {count} stale upload(s).")
