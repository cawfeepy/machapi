import logging
import os
import uuid

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from machtms.core.utils import s3_utils as s3
from .models import ParsingSession, RateConDocument, DocumentStatus, SessionStatus
from .serializers import (
    CreateSessionRequestSerializer,
    DocumentUploadRequestSerializer,
    ProcessSessionRequestSerializer,
    ParsingSessionSerializer,
    ParsingSessionDetailSerializer,
    RateConDocumentDetailSerializer,
)

logger = logging.getLogger(__name__)


class CreateSessionView(APIView):
    """Create a parsing session."""

    @extend_schema(
        operation_id="RateConCreateSession",
        request=CreateSessionRequestSerializer,
        responses={201: inline_serializer(
            name="RateConCreateSessionResponse",
            fields={
                'session_id': serializers.IntegerField(),
            }
        )},
    )
    def post(self, request):
        session = ParsingSession.objects.create(
            organization_id=request.organization,
            status=SessionStatus.UPLOADING,
        )

        return Response({
            'session_id': session.pk,
        }, status=status.HTTP_201_CREATED)


class DocumentUploadView(APIView):
    """Generate a presigned URL and create a RateConDocument for a single file upload."""

    @staticmethod
    def generate_s3_key(extension: str = ".pdf") -> str:
        """Generate a unique S3 key using a UUID."""
        return f"{uuid.uuid4()}{extension}"

    @staticmethod
    def resolve_duplicate_filename(filename: str, organization_id: int) -> str:
        """Resolve duplicate filenames by appending a counter suffix."""
        if not RateConDocument.objects.filter(
            organization_id=organization_id,
            original_filename=filename,
        ).exists():
            return filename
        name, ext = os.path.splitext(filename)
        counter = 1
        while RateConDocument.objects.filter(
            organization_id=organization_id,
            original_filename=f"{name}-{counter}{ext}",
        ).exists():
            counter += 1
        return f"{name}-{counter}{ext}"

    @extend_schema(
        operation_id="RateConDocumentUpload",
        request=DocumentUploadRequestSerializer,
        responses={201: inline_serializer(
            name="RateConDocumentUploadResponse",
            fields={
                'document_id': serializers.IntegerField(),
                'original_filename': serializers.CharField(),
                's3_key': serializers.CharField(),
                'presigned_url': serializers.CharField(),
            }
        )},
    )
    def post(self, request):
        serializer = DocumentUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        filename = serializer.validated_data['filename']
        mime_type = serializer.validated_data.get('mime_type', 'application/pdf')

        session = get_object_or_404(
            ParsingSession.objects.filter(organization=request.organization),
            pk=session_id,
        )

        org_id = getattr(request.organization, 'pk', request.organization)
        resolved_filename = self.resolve_duplicate_filename(filename, org_id)

        _, ext = os.path.splitext(filename)
        s3_key = self.generate_s3_key(extension=ext if ext else ".pdf")

        doc = RateConDocument.objects.create(
            organization_id=request.organization,
            session=session,
            original_filename=resolved_filename,
            s3_key=s3_key,
            mime_type=mime_type,
            status=DocumentStatus.UPLOADING,
        )

        presigned_url = s3.generate_presigned_url(
            'put_object',
            bucket_name=settings.AWS_RATECON_PARSE_BUCKET,
            object_key=s3_key,
            content_type=mime_type,
        )

        return Response({
            'document_id': doc.pk,
            'original_filename': resolved_filename,
            's3_key': s3_key,
            'presigned_url': presigned_url,
        }, status=status.HTTP_201_CREATED)


class DocumentUploadCompleteView(APIView):
    """Mark a document as uploaded (UPLOADING -> PENDING)."""

    @extend_schema(
        operation_id="RateConDocumentUploadComplete",
        request=inline_serializer(
            name="RateConDocUploadCompleteRequest",
            fields={
                'document_id': serializers.IntegerField(),
                'file_size': serializers.IntegerField(required=False),
            }
        ),
        responses={200: inline_serializer(
            name="RateConDocUploadCompleteResponse",
            fields={
                'document_id': serializers.IntegerField(),
                'status': serializers.CharField(),
            }
        )},
    )
    def post(self, request):
        document_id = request.data.get('document_id')
        doc = get_object_or_404(
            RateConDocument.objects.filter(organization=request.organization),
            pk=document_id,
        )

        if doc.status != DocumentStatus.UPLOADING:
            return Response(
                {'detail': f'Document is not in UPLOADING state (current: {doc.status})'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc.status = DocumentStatus.PENDING
        if 'file_size' in request.data:
            doc.file_size = request.data['file_size']
        doc.save(update_fields=['status', 'file_size', 'updated_at'])

        return Response({
            'document_id': doc.pk,
            'status': doc.status,
        })


class ProcessSessionView(APIView):
    """Trigger processing of a parsing session (sync or async mode)."""

    @extend_schema(
        operation_id="RateConProcessSession",
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
        operation_id="RateConProcessDocumentPdf",
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
    """List all parsing sessions for the organization."""

    @extend_schema(
        operation_id="RateConSessionList",
        responses={200: ParsingSessionSerializer(many=True)},
    )
    def get(self, request):
        sessions = ParsingSession.objects.filter(
            organization=request.organization,
        ).order_by('-created_at')
        serializer = ParsingSessionSerializer(sessions, many=True)
        return Response(serializer.data)


class SessionDetailView(APIView):
    """Get session details with nested documents."""

    @extend_schema(
        operation_id="RateConSessionDetail",
        responses={200: ParsingSessionDetailSerializer},
    )
    def get(self, request, session_id):
        session = get_object_or_404(
            ParsingSession.objects.filter(organization=request.organization),
            pk=session_id,
        )
        serializer = ParsingSessionDetailSerializer(session)
        return Response(serializer.data)


class DocumentDetailView(APIView):
    """Get document details with parsed content."""

    @extend_schema(
        operation_id="RateConDocumentDetail",
        responses={200: RateConDocumentDetailSerializer},
    )
    def get(self, request, document_id):
        doc = get_object_or_404(
            RateConDocument.objects.filter(organization=request.organization),
            pk=document_id,
        )
        serializer = RateConDocumentDetailSerializer(doc)
        return Response(serializer.data)
