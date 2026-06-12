import logging
import os
import uuid
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from machtms.core.utils import s3_utils as s3
from .models import (
    ParsingSession,
    RateConDocument,
    DocumentStatus,
    SessionStatus,
    PresignedURLEntryPoint,
    PresignedURLEntryPointStatus,
)
from .serializers import (
    ProcessSessionRequestSerializer,
    ParsingSessionSerializer,
    RateConDocumentSerializer,
    PresignedURLRequestSerializer,
    PresignedURLEntryPointSerializer,
    CreateSessionFromPresignedRequestSerializer,
)

logger = logging.getLogger(__name__)


class ProcessSessionView(APIView):
    """Trigger processing of a parsing session (sync or async mode) using raw text."""

    @extend_schema(
        operation_id="RateConProcessSessionTextMode",
        request=ProcessSessionRequestSerializer,
        responses={202: inline_serializer(
            name="RateConProcessSessionResponse",
            fields={
                'session_id': serializers.IntegerField(),
                'mode': serializers.CharField(),
                'message': serializers.CharField(),
            }
        )},
    )
    def post(self, request, session_id):
        session = get_object_or_404(
            ParsingSession.objects.filter(organization=request.organization),
            pk=session_id,
        )

        serializer = ProcessSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mode = serializer.validated_data['mode']

        pending_count = session.documents.filter(status=DocumentStatus.PENDING).count()
        if pending_count == 0:
            return Response(
                {'detail': 'No pending documents to process.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import process_session_sync, process_session_async
        from machtms.core.celerycontroller.controller import CeleryController

        controller = CeleryController()

        if mode == 'sync':
            controller.delay(process_session_sync, session.pk)
        else:
            controller.delay(process_session_async, session.pk)

        return Response({
            'session_id': session.pk,
            'mode': mode,
            'message': f'Processing started for {pending_count} document(s).',
        }, status=status.HTTP_202_ACCEPTED)


class ProcessSessionPdfView(APIView):
    """Trigger processing of a parsing session using direct PDF mode (presigned URL)."""

    @extend_schema(
        operation_id="RateConProcessSessionPdf",
        request=ProcessSessionRequestSerializer,
        responses={202: inline_serializer(
            name="RateConProcessSessionPdfResponse",
            fields={
                'session_id': serializers.IntegerField(),
                'mode': serializers.CharField(),
                'message': serializers.CharField(),
            }
        )},
    )
    def post(self, request, session_id):
        session = get_object_or_404(
            ParsingSession.objects.filter(organization=request.organization),
            pk=session_id,
        )

        serializer = ProcessSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mode = serializer.validated_data['mode']

        pending_count = session.documents.filter(status=DocumentStatus.PENDING).count()
        if pending_count == 0:
            return Response(
                {'detail': 'No pending documents to process.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import process_session_sync, process_session_async
        from machtms.core.celerycontroller.controller import CeleryController

        controller = CeleryController()

        if mode == 'sync':
            controller.delay(process_session_sync, session.pk, use_raw_text=False)
        else:
            controller.delay(process_session_async, session.pk, use_raw_text=False)

        return Response({
            'session_id': session.pk,
            'mode': mode,
            'message': f'PDF processing started for {pending_count} document(s).',
        }, status=status.HTTP_202_ACCEPTED)


class ProcessDocumentPdfView(APIView):
    """Trigger processing of a single document using direct PDF mode (presigned URL)."""

    @extend_schema(
        operation_id="RateConProcessDocumentPdfMode",
        request=None,
        responses={202: inline_serializer(
            name="RateConProcessDocumentPdfResponse",
            fields={
                'document_id': serializers.IntegerField(),
                'message': serializers.CharField(),
            }
        )},
    )
    def post(self, request, document_id):
        doc = get_object_or_404(
            RateConDocument.objects.filter(organization=request.organization),
            pk=document_id,
        )

        if doc.status != DocumentStatus.PENDING:
            return Response(
                {'detail': f'Document is not in PENDING state (current: {doc.status}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import process_document
        from machtms.core.celerycontroller.controller import CeleryController

        controller = CeleryController()
        controller.delay(process_document, doc.pk, use_raw_text=False)

        return Response({
            'document_id': doc.pk,
            'message': 'PDF processing started.',
        }, status=status.HTTP_202_ACCEPTED)


class SessionListView(APIView):
    """List active (non-hidden) parsing sessions, newest first, capped at 8."""

    @extend_schema(
        operation_id="RateConSessionList",
        responses={200: ParsingSessionSerializer(many=True)},
    )
    def get(self, request):
        sessions = (
            ParsingSession.objects
            .filter(organization=request.organization, is_hidden=False)
            .prefetch_related('documents')
            .order_by('-created_at')[:8]
        )
        serializer = ParsingSessionSerializer(sessions, many=True)
        return Response(serializer.data)


class HideSessionView(APIView):
    """Hide a parsing session so it no longer appears in the session list."""

    @extend_schema(
        operation_id="RateConHideSession",
        request=None,
        responses={200: inline_serializer(
            name="RateConHideSessionResponse",
            fields={
                'session_id': serializers.IntegerField(),
                'is_hidden': serializers.BooleanField(),
            }
        )},
    )
    def post(self, request, session_id):
        session = get_object_or_404(
            ParsingSession.objects.filter(organization=request.organization),
            pk=session_id,
        )
        session.is_hidden = True
        session.save(update_fields=['is_hidden', 'updated_at'])
        return Response({'session_id': session.pk, 'is_hidden': session.is_hidden})


class SessionDetailView(APIView):
    """Get session details with nested documents."""

    @extend_schema(
        operation_id="RateConSessionDetail",
        responses={200: ParsingSessionSerializer},
    )
    def get(self, request, session_id):
        session = get_object_or_404(
            ParsingSession.objects.prefetch_related(
                'documents',
            ).filter(organization=request.organization),
            pk=session_id,
        )
        serializer = ParsingSessionSerializer(session)
        return Response(serializer.data)


class DocumentDetailView(APIView):
    """Get document details."""

    @extend_schema(
        operation_id="RateConDocumentDetail",
        responses={200: RateConDocumentSerializer},
    )
    def get(self, request, document_id):
        doc = get_object_or_404(
            RateConDocument.objects.filter(
                organization=request.organization,
            ),
            pk=document_id,
        )
        serializer = RateConDocumentSerializer(doc)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deduplicate_filename(filename: str, seen: set) -> str:
    """Return a unique filename by appending -2, -3, … when there is a clash.

    Args:
        filename: The desired filename.
        seen: A set of already-used filenames (mutated in-place).

    Returns:
        A filename not present in *seen*, after adding it to *seen*.
    """
    if filename not in seen:
        seen.add(filename)
        return filename
    name, ext = os.path.splitext(filename)
    counter = 2
    while f"{name}-{counter}{ext}" in seen:
        counter += 1
    unique = f"{name}-{counter}{ext}"
    seen.add(unique)
    return unique


PRESIGNED_EXPIRY_SECONDS = 900  # 15 minutes


def _process_orphaned_entrypoints(organization=None):
    """Shared logic for recovering orphaned presigned-URL entry points.

    Called by both OrphanedDocumentCheckView (single org) and the
    process_orphaned_entrypoints Celery task (all orgs).

    Args:
        organization: An Organization instance to scope to, or None to process all orgs.

    Returns:
        dict with keys: sessions_created (list of ParsingSession),
                        expired_deleted (int), recovered_count (int).
    """
    from machtms.core.celerycontroller.controller import CeleryController
    from .tasks import process_session_async

    qs = PresignedURLEntryPoint.objects.all()
    if organization is not None:
        qs = qs.filter(organization=organization)

    now = timezone.now()
    sessions_created = []
    expired_deleted  = 0

    # Separate into groups
    orphaned_expired   = qs.filter(status=PresignedURLEntryPointStatus.ORPHANED, expiration__lt=now)
    orphaned_unexpired = qs.filter(status=PresignedURLEntryPointStatus.ORPHANED, expiration__gte=now)
    # Capture IDs now (before Case B updates them to PROCESSED) so the final
    # cleanup does not accidentally delete entries we just processed.
    processed_ids = list(qs.filter(status=PresignedURLEntryPointStatus.PROCESSED).values_list('pk', flat=True))

    # Case A — expired + orphaned: delete S3 object (best-effort) then DB record
    s3_client = s3.s3_client
    bucket = settings.AWS_RATECON_PARSE_BUCKET
    for entry in orphaned_expired:
        try:
            s3_client.delete_object(Bucket=bucket, Key=entry.s3_key)
        except Exception:
            logger.exception(
                f"Could not delete S3 object for expired orphaned entrypoint {entry.pk} (key={entry.s3_key})"
            )
        entry.delete()
        expired_deleted += 1

    # Case B — unexpired + orphaned: create one session per org, auto-dispatch
    if orphaned_unexpired.exists():
        # Group by organization
        from itertools import groupby
        entries_by_org = {}
        for entry in orphaned_unexpired.select_related('organization').order_by('organization_id'):
            org_id = entry.organization_id
            entries_by_org.setdefault(org_id, (entry.organization, []))
            entries_by_org[org_id][1].append(entry)

        controller = CeleryController()
        for org_id, (org, entries) in entries_by_org.items():
            session = ParsingSession.objects.create(
                organization=org,
                status=SessionStatus.UPLOADING,
            )
            seen_filenames: set = set()
            docs_to_create = []
            for entry in entries:
                deduped = _deduplicate_filename(entry.filename, seen_filenames)
                docs_to_create.append(
                    RateConDocument(
                        organization=org,
                        session=session,
                        s3_key=entry.s3_key,
                        original_filename=deduped,
                        status=DocumentStatus.PENDING,
                        mime_type='application/pdf',
                    )
                )
            RateConDocument.objects.bulk_create(docs_to_create)

            # Mark entrypoints processed
            entry_ids = [e.pk for e in entries]
            PresignedURLEntryPoint.objects.filter(pk__in=entry_ids).update(
                status=PresignedURLEntryPointStatus.PROCESSED,
            )

            controller.delay(process_session_async, session.pk)
            sessions_created.append(session)

    # Cases C & D — processed (expired or not): cleanup, session already exists
    PresignedURLEntryPoint.objects.filter(pk__in=processed_ids).delete()

    return {
        'sessions_created': sessions_created,
        'expired_deleted':  expired_deleted,
        'recovered_count':  len(sessions_created),
    }


# ---------------------------------------------------------------------------
# New Views
# ---------------------------------------------------------------------------

class PresignedURLEntryPointView(APIView):
    """Generate presigned S3 PUT URLs and create orphaned entrypoint records."""

    @extend_schema(
        operation_id="RateConPresignedURLs",
        request=PresignedURLRequestSerializer,
        responses={201: PresignedURLEntryPointSerializer(many=True)},
    )
    def post(self, request):
        serializer = PresignedURLRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        files = serializer.validated_data['files']
        seen_filenames: set = set()
        entrypoints = []

        for file_item in files:
            filename  = file_item['filename']
            mime_type = file_item.get('mime_type', 'application/pdf')

            deduped_filename = _deduplicate_filename(filename, seen_filenames)

            _, ext = os.path.splitext(filename)
            s3_key = f"{uuid.uuid4()}{ext if ext else '.pdf'}"

            presigned_url = s3.generate_presigned_url(
                'put_object',
                bucket_name=settings.AWS_RATECON_PARSE_BUCKET,
                object_key=s3_key,
                expires=PRESIGNED_EXPIRY_SECONDS,
                content_type=mime_type,
            )
            expiration = timezone.now() + timedelta(seconds=PRESIGNED_EXPIRY_SECONDS)

            entry = PresignedURLEntryPoint.objects.create(
                organization_id=request.organization,
                presigned_url=presigned_url,
                s3_key=s3_key,
                filename=deduped_filename,
                expiration=expiration,
                status=PresignedURLEntryPointStatus.ORPHANED,
            )
            entrypoints.append(entry)

        out = PresignedURLEntryPointSerializer(entrypoints, many=True)
        return Response(out.data, status=status.HTTP_201_CREATED)


class CreateSessionFromPresignedView(APIView):
    """Create a ParsingSession from already-uploaded presigned entry points."""

    @extend_schema(
        operation_id="RateConSessionFromPresigned",
        request=CreateSessionFromPresignedRequestSerializer,
        responses={201: inline_serializer(
            name="RateConSessionFromPresignedResponse",
            fields={
                'session_id': serializers.IntegerField(),
                'documents': RateConDocumentSerializer(many=True),
            }
        )},
    )
    def post(self, request):
        serializer = CreateSessionFromPresignedRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entrypoint_ids = serializer.validated_data['entrypoint_ids']

        entrypoints = list(
            PresignedURLEntryPoint.objects.filter(
                id__in=entrypoint_ids,
                organization=request.organization,
                status=PresignedURLEntryPointStatus.ORPHANED,
            )
        )

        if not entrypoints:
            return Response(
                {'detail': 'No valid orphaned entrypoints found for the provided IDs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = ParsingSession.objects.create(
            organization_id=request.organization,
            status=SessionStatus.UPLOADING,
        )

        seen_filenames: set = set()
        docs = []
        for entry in entrypoints:
            deduped = _deduplicate_filename(entry.filename, seen_filenames)
            docs.append(
                RateConDocument(
                    organization_id=request.organization,
                    session=session,
                    s3_key=entry.s3_key,
                    original_filename=deduped,
                    status=DocumentStatus.PENDING,
                    mime_type='application/pdf',
                )
            )

        created_docs = RateConDocument.objects.bulk_create(docs)

        # Mark entrypoints as processed
        PresignedURLEntryPoint.objects.filter(pk__in=[e.pk for e in entrypoints]).update(
            status=PresignedURLEntryPointStatus.PROCESSED,
        )

        doc_serializer = RateConDocumentSerializer(created_docs, many=True)
        return Response(
            {'session_id': session.pk, 'documents': doc_serializer.data},
            status=status.HTTP_201_CREATED,
        )


class OrphanedDocumentCheckView(APIView):
    """Trigger a background check for orphaned presigned-URL entry points.

    The view dispatches a Celery task scoped to the requesting organization and
    returns 202 immediately. The task creates a new ParsingSession for any
    unexpired orphaned entrypoints and auto-dispatches document processing.
    The frontend should poll GET /ratecon/sessions/list/ to discover the
    newly created session (if any).
    """

    @extend_schema(
        operation_id="RateConOrphanedPreCheck",
        request=None,
        responses={202: inline_serializer(
            name="RateConOrphanedPreCheckResponse",
            fields={'detail': serializers.CharField()},
        )},
    )
    def post(self, request):
        from .tasks import run_orphan_check_for_org
        from machtms.core.celerycontroller.controller import CeleryController

        org_id = getattr(request.organization, 'pk', request.organization)
        CeleryController().delay(run_orphan_check_for_org, org_id)

        return Response(
            {'detail': 'Orphan check dispatched.'},
            status=status.HTTP_202_ACCEPTED,
        )
