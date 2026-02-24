import logging

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
    ProcessSessionRequestSerializer,
    ParsingSessionSerializer,
    ParsingSessionDetailSerializer,
    RateConDocumentDetailSerializer,
)

logger = logging.getLogger(__name__)


class CreateSessionView(APIView):
    """Create a parsing session and return presigned URLs for file uploads."""

    @extend_schema(
        operation_id="RateConCreateSession",
        request=CreateSessionRequestSerializer,
        responses={201: inline_serializer(
            name="RateConCreateSessionResponse",
            fields={
                'session_id': serializers.IntegerField(),
                'uploads': serializers.ListSerializer(child=inline_serializer(
                    name="RateConUploadInfo",
                    fields={
                        'document_id': serializers.IntegerField(),
                        'filename': serializers.CharField(),
                        'presigned_url': serializers.CharField(),
                        's3_key': serializers.CharField(),
                    }
                )),
            }
        )},
    )
    def post(self, request):
        serializer = CreateSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ParsingSession.objects.create(
            organization=request.organization,
            status=SessionStatus.UPLOADING,
        )

        uploads = []
        for file_info in serializer.validated_data['files']:
            filename = file_info['filename']
            mime_type = file_info.get('mime_type', 'application/pdf')
            s3_key = s3.create_object_key(f"ratecon/{session.pk}/{filename}")

            doc = RateConDocument.objects.create(
                organization=request.organization,
                session=session,
                original_filename=filename,
                s3_key=s3_key,
                mime_type=mime_type,
                status=DocumentStatus.UPLOADING,
            )

            presigned_url = s3.generate_presigned_url(
                'put_object',
                bucket_name=settings.AWS_UPLOAD_BUCKET,
                object_key=s3_key,
            )

            uploads.append({
                'document_id': doc.pk,
                'filename': filename,
                'presigned_url': presigned_url,
                's3_key': s3_key,
            })

        return Response({
            'session_id': session.pk,
            'uploads': uploads,
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
