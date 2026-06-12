import logging
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from celery import shared_task, group
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    ParsingSession,
    RateConDocument,
    DocumentStatus,
    SessionStatus,
)

logger = logging.getLogger(__name__)

PT = ZoneInfo("America/Los_Angeles")

STUCK_PROCESSING_MINUTES = 15

TRAILER_TYPE_MAP = {
    '53': 'LARGE_53',
    '48': 'LARGE_48',
    '45': 'MEDIUM_45',
    '40': 'MEDIUM_40',
    '28': 'SMALL_28',
    '20': 'SMALL_20',
}


def _map_trailer_type(trailer_type_str: str) -> str:
    """Map a raw trailer type string to a TrailerType choice value."""
    for size, choice in TRAILER_TYPE_MAP.items():
        if size in trailer_type_str:
            return choice
    return ""


def _parse_appointment(appointment_str: str) -> str | None:
    """Parse an appointment string to ISO8601 UTC.

    Accepts MM/DD/YYYY HH:MM format, assumes America/Los_Angeles timezone.
    Returns None for empty, 'UNKNOWN', or unparseable values.
    """
    if not appointment_str or appointment_str.strip().upper() == "UNKNOWN":
        return None
    try:
        dt = datetime.strptime(appointment_str.strip(), "%m/%d/%Y %H:%M")
        localized = dt.replace(tzinfo=PT)
        return localized.astimezone(ZoneInfo("UTC")).isoformat()
    except ValueError:
        # Try ISO format as fallback
        try:
            datetime.fromisoformat(appointment_str.strip())
            return appointment_str.strip()
        except ValueError:
            return None


def _get_suggested_action(organization, address_id: int) -> str | None:
    """Query stop history for the most common action at an address."""
    from machtms.backend.routes.models import Stop

    recent_pks = list(
        Stop.objects.filter(
            organization=organization,
            address_id=address_id,
        )
        .order_by('-timestamp')
        .values_list('pk', flat=True)[:10]
    )
    if not recent_pks:
        return None

    top = (
        Stop.objects.filter(pk__in=recent_pks)
        .values('action')
        .annotate(count=Count('action'))
        .order_by('-count')
        .first()
    )
    return top['action'] if top else None


def create_load_from_ratecon_data(parsed_data, organization, ratecon_document_id: int):
    """Create a Load from parsed rate confirmation data.

    Args:
        parsed_data: ParsedRateConData instance with extracted fields.
        organization: Organization model instance.
        ratecon_document_id: PK of the RateConDocument to link.

    Raises:
        Exception: On validation errors so the caller can handle failure.
    """
    from machtms.backend.addresses.models import Address
    from machtms.backend.customers.models import Customer
    from machtms.backend.loads.serializers import LoadSerializer

    # 1. Resolve customer
    customer_id = None
    name = parsed_data.customer_name
    if name and name.strip().upper() != "UNKNOWN":
        customer = Customer.objects.filter(
            organization=organization,
            customer_name__icontains=name,
        ).first()
        if not customer:
            customer = Customer.objects.create(
                organization=organization,
                customer_name=name,
            )
        customer_id = customer.pk

    # 2. Build stops
    stops_payload = []
    total_stops = len(parsed_data.stops)

    for idx, stop in enumerate(parsed_data.stops):
        # Resolve address via get_or_create
        addr, _ = Address.objects.get_or_create(
            organization=organization,
            street=stop.street_address,
            city=stop.city,
            state=stop.state,
            zip_code=stop.zip_code,
            defaults={
                'place_name': stop.place_name,
                'country': 'US',
            },
        )

        # Determine action code from history or defaults
        suggested = _get_suggested_action(organization, addr.pk)
        if suggested:
            action = suggested
        elif idx == 0:
            action = 'LL'
        elif idx == total_stops - 1:
            action = 'LU'
        else:
            action = 'LL'

        # Parse appointment
        start_range = _parse_appointment(stop.appointment)
        if not start_range:
            start_range = timezone.now().isoformat()

        # Join PO numbers
        po_numbers = ", ".join(stop.po_numbers) if stop.po_numbers else ""

        stops_payload.append({
            'stop_number': idx + 1,
            'address': addr.pk,
            'action': action,
            'start_range': start_range,
            'end_range': None,
            'po_numbers': po_numbers,
            'driver_notes': stop.notes or "",
        })

    # 3. Build load payload
    payload = {
        'customer': customer_id,
        'reference_number': parsed_data.reference_number if parsed_data.reference_number != "UNKNOWN" else "",
        'bol_number': parsed_data.bol_number if parsed_data.bol_number != "UNKNOWN" else "",
        'trailer_type': _map_trailer_type(parsed_data.trailer_type),
        'status': 'pending',
        'billing_status': 'pending_delivery',
        'legs': [{'stops': stops_payload}],
    }

    # 4. Create via LoadSerializer
    mock_request = SimpleNamespace(
        organization=organization.id,
        user=SimpleNamespace(userprofile=None),
    )
    serializer = LoadSerializer(
        data=payload,
        context={'request': mock_request},
    )

    if not serializer.is_valid():
        raise ValueError(f"Load validation failed: {serializer.errors}")

    load = serializer.save()

    # 5. Link load to document
    doc = RateConDocument.objects.get(pk=ratecon_document_id)
    doc.load = load
    doc.save(update_fields=['load_id', 'updated_at'])

    logger.info(f"Created load {load.pk} (ref: {load.reference_number}) from ratecon doc {ratecon_document_id}")
    return load


def extract_text_from_pdf(file_buffer: BytesIO) -> str:
    """Extract text from a PDF file buffer using LiteParse CLI."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(file_buffer.read())
        temp_file_path = temp_file.name
    
    try:
        result = subprocess.run(
            ["lit", "parse", temp_file_path, "-q"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LiteParse failed: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError("LiteParse CLI not found. Make sure 'lit' is installed and available on PATH.") from None
    finally:
        try:
            os.unlink(temp_file_path)
        except Exception:
            pass  # Best effort cleanup


def send_pdf_url_to_agent(s3_key: str, agent, session_id: str, dependencies: dict):
    """Send a PDF to the agent via S3 presigned GET URL."""
    from agno.media import File
    from machtms.core.utils import s3_utils

    presigned_url = s3_utils.generate_presigned_url(
        'get_object',
        bucket_name=settings.AWS_RATECON_PARSE_BUCKET,
        object_key=s3_key,
        expires=300,
    )
    return agent.run(
        "Process this rate confirmation document.",
        files=[File(url=presigned_url)],
        session_id=session_id,
        dependencies=dependencies,
    )


def process_single_document(document_id: int, use_raw_text: bool = True):
    """Process a single rate confirmation document.

    This is a plain function (not a Celery task) that:
    1. Downloads from S3 and extracts text (use_raw_text=True), OR
       generates a presigned URL for direct PDF input (use_raw_text=False)
    2. Calls the rate_con_processor agent
    3. Parses agent response
    4. Stores classification on the document
    5. Updates document status

    Args:
        document_id: PK of the RateConDocument to process.
        use_raw_text: If True (default), download PDF and extract text via LiteParse.
            If False, send the PDF directly to the agent via a presigned S3 URL.
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

        from machtms.agents.members.rate_con_processor import rate_con_processor

        agent_dependencies = {
            "organization": organization,
            "celery_task_id": doc.celery_task_id,
            "ratecon_id": doc.pk,
        }

        if use_raw_text:
            # Existing path: download from S3, extract text, send text to agent
            file_buffer = s3_utils.download_from_buffer(
                doc.s3_key,
                bucket_name=settings.AWS_RATECON_PARSE_BUCKET,
            )

            text = extract_text_from_pdf(file_buffer)

            if not text.strip():
                doc.status = DocumentStatus.FAILED
                doc.error_message = "No text could be extracted from the PDF."
                doc.processed_at = timezone.now()
                doc.save(update_fields=['status', 'error_message', 'processed_at', 'updated_at'])
                return

            response = rate_con_processor.run(
                text,
                session_id=str(uuid.uuid4()),
                dependencies=agent_dependencies,
            )
        else:
            # New path: send PDF directly via presigned URL
            response = send_pdf_url_to_agent(
                s3_key=doc.s3_key,
                agent=rate_con_processor,
                session_id=str(uuid.uuid4()),
                dependencies=agent_dependencies,
            )

        parsed_data = response.content  # ParsedRateConData instance

        # Store classification on the document
        doc.classification_passed = (parsed_data.classification == 'PASS')
        doc.classification_reason = parsed_data.classification_reason
        doc.save(update_fields=['classification_passed', 'classification_reason', 'updated_at'])

        if parsed_data.classification == 'PASS':
            try:
                create_load_from_ratecon_data(parsed_data, organization, doc.pk)
                # Load created and linked -- NOW set PARSED
                doc.status = DocumentStatus.PARSED
                doc.processed_at = timezone.now()
                doc.save(update_fields=['status', 'processed_at', 'updated_at'])
            except Exception as load_err:
                logger.exception(
                    f"Load creation failed for doc {document_id}: {load_err}"
                )
                doc.status = DocumentStatus.FAILED
                doc.error_message = f"Parsed OK but load creation failed: {str(load_err)[:400]}"
                doc.processed_at = timezone.now()
                doc.save(update_fields=['status', 'error_message', 'processed_at', 'updated_at'])
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
def process_document(document_id: int, use_raw_text: bool = True):
    """Celery task wrapper around process_single_document."""
    process_single_document(document_id, use_raw_text=use_raw_text)


@shared_task
def process_session_sync(session_id: int, use_raw_text: bool = True):
    """Process all pending documents in a session sequentially (Mode A)."""
    session = ParsingSession.objects.get(pk=session_id)
    session.status = SessionStatus.PROCESSING
    session.save(update_fields=['status', 'updated_at'])

    pending_docs = session.documents.filter(
        status=DocumentStatus.PENDING
    ).order_by('created_at')

    for doc in pending_docs:
        process_single_document(doc.pk, use_raw_text=use_raw_text)

    session.recompute_status()


@shared_task
def process_session_async(session_id: int, max_workers: int = 5, use_raw_text: bool = True):
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
            process_document_worker.s(session_id, use_raw_text) for _ in range(worker_count)
        )
        job.apply_async()


def _claim_and_process(session, use_raw_text: bool, include_stuck: bool = False):
    """Claim and process documents for a session.

    Args:
        session: The ParsingSession instance.
        use_raw_text: Passed through to process_single_document.
        include_stuck: If True, also claim PROCESSING docs stuck beyond
            STUCK_PROCESSING_MINUTES (rescue mode).
    """
    while True:
        with transaction.atomic():
            qs = RateConDocument.objects.select_for_update(skip_locked=True)

            if include_stuck:
                stuck_cutoff = timezone.now() - timedelta(minutes=STUCK_PROCESSING_MINUTES)
                doc = qs.filter(
                    Q(status=DocumentStatus.PENDING) |
                    Q(status=DocumentStatus.PROCESSING, updated_at__lt=stuck_cutoff),
                    session=session,
                ).first()
            else:
                doc = qs.filter(session=session, status=DocumentStatus.PENDING).first()

            if doc is None:
                break
            doc.status = DocumentStatus.PROCESSING
            doc.save(update_fields=['status', 'updated_at'])

        process_single_document(doc.pk, use_raw_text=use_raw_text)

    session.recompute_status()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    task_reject_on_worker_lost=True,
)
def process_document_worker(self, session_id: int, use_raw_text: bool = True):
    """Worker for parallel processing mode.

    Claims and processes PENDING documents one at a time using
    SELECT FOR UPDATE SKIP LOCKED.

    Retries up to 3 times (60 s delay) on unexpected exception.
    acks_late + task_reject_on_worker_lost ensure the task is re-queued
    if the worker process is hard-killed (OOM, SIGKILL) before it finishes.
    Retries are routed to the 'rescue' queue to isolate retry traffic
    from the main processing queue.
    """
    try:
        session = ParsingSession.objects.get(pk=session_id)
        _claim_and_process(session, use_raw_text)
    except Exception as exc:
        raise self.retry(exc=exc, queue='rescue')


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    task_reject_on_worker_lost=True,
    queue='rescue',
)
def rescue_document_worker(self, session_id: int, use_raw_text: bool = True):
    """Rescue worker that claims both PENDING and stuck PROCESSING documents.

    Routes to the 'rescue' queue by default (set in the decorator).
    A document is considered stuck if it has been in PROCESSING status
    for longer than STUCK_PROCESSING_MINUTES without being updated.

    Retries up to 3 times (60 s delay) on unexpected exception.
    """
    try:
        session = ParsingSession.objects.get(pk=session_id)
        _claim_and_process(session, use_raw_text, include_stuck=True)
    except Exception as exc:
        raise self.retry(exc=exc, queue='rescue')


@shared_task
def run_orphan_check_for_org(org_id: int):
    """Process orphaned presigned-URL entry points for a single organization.

    Triggered by the frontend's orphan-check endpoint when it suspects the user
    uploaded files to S3 but did not complete the session-creation flow.
    Creates a new ParsingSession for any unexpired orphaned entrypoints and
    auto-dispatches processing; deletes expired ones (with best-effort S3 cleanup).
    """
    from machtms.backend.auth.models import Organization
    from machtms.backend.RateConParser.views import _process_orphaned_entrypoints

    try:
        org = Organization.objects.get(pk=org_id)
    except Organization.DoesNotExist:
        logger.warning(f"run_orphan_check_for_org: organization {org_id} not found, skipping.")
        return

    _process_orphaned_entrypoints(organization=org)
