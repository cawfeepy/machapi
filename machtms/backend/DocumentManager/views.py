import logging

logger = logging.getLogger(__name__)
from drf_spectacular.utils import extend_schema, inline_serializer

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from .utils import generate_truncated_hash, s3

from djangorestframework_camel_case.parser import CamelCaseJSONParser
from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer

from rest_framework import serializers, status
from rest_framework.decorators import api_view, parser_classes, renderer_classes
from rest_framework.request import Request
from rest_framework.response import Response

from machtms.backend.DocumentManager.tasks import task_upload_to_shipment
from machtms.backend.loads.models import Load

from .models import SessionUploadLog
from .serializers import (
    DirectUploadSerializer, PostShipmentDocumentSerializer,
    PresignedUrlSerializer, S3UploadRequestSerializer,
    SessionUploadLogSerializer, SessionUploadReadOnlySerializer,
    UploadLogSerializer)


@api_view(["POST"])
def generate_queue_hash(request: Request):
    """
    Either two things will happen:
        client will want two or more documents merged.
        - in that case: these documents will share a hash id

        otherwise, client will have multiple queues of each
        document
    """
    queue_hash_id = generate_truncated_hash()
    return Response(queue_hash_id, status=status.HTTP_200_OK)


@api_view(['POST'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def start_session(request: Request, invoice_id: int|None=None):
    """
    POST - create a session log for client, send load.pk not invoice_id
    GET - given an invoice_id, get non-expired session_logs and return the latest
    """
    if request.method == 'GET':
        """ Return the latest"""
        pass
    elif request.method == 'POST':
        serializer = SessionUploadLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(organization=request.organization)
        return Response({"session_id": log.pk})
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@extend_schema(
    operation_id="DocumentGetPresignedURL",
    request=PresignedUrlSerializer,
    responses=inline_serializer(
        name="DocumentGetPresignedURL",
        fields={
            'presigned': serializers.CharField(),
            'object_key': serializers.CharField(),
            **PresignedUrlSerializer().get_fields()
        }
    ))
@api_view(["POST"])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def get_presigned_url(request: Request):
    """
    get the data from the request, create an object_key
    from the request data (filename and queue_hash_id)
    accepts
    request.data:
        filename = serializers.CharField()
        content_type = serializers.CharField()
        category = serializers.CharField()
        queue_hash_id = serializers.CharField(required=False, allow_null=True)

    View really just modifies the incoming data for the client
    and adds an s3url (presigned url)

    Response Data:
    payload: {
        presigned: str,
        queue_hash_id[if empty in request.data]
        object_key
    }
    """
    serializer = PresignedUrlSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
                serializer.errors,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    data = serializer.data
    s3url = s3.generate_presigned_url('put_object',
                                    bucket_name=settings.AWS_UPLOAD_BUCKET,
                                    object_key=data.get('object_key'))
    data.setdefault('presigned', s3url)
    return Response(data, status=status.HTTP_200_OK)



@extend_schema(
    operation_id='DocumentRegisterUpload',
    request=inline_serializer(
        name="DocumentRegisterUpload",
        fields={
            'sessionId': serializers.IntegerField(),
            **DirectUploadSerializer().get_fields()
        }
    ),
    responses=inline_serializer(
            name="DocumentRegisterUploadSerializer",
            fields={"uploadId": serializers.IntegerField()}
    ))
@api_view(['POST'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def register_upload(R:Request):
    """
    Args:
        request:
        - session_id
        - queue_hash_id
        - filename
        - object_key
        - content_type
        - category
        - loadId
    Response:
        {
            "uploadId": int
        }
    """
    try:
        with transaction.atomic():
            session = SessionUploadLog.objects.for_request(R).get(
                pk=R.data.pop('session_id')
            )

            # create DirectUpload model
            serializer = DirectUploadSerializer(data=R.data)
            serializer.is_valid(raise_exception=True)
            upload = serializer.save(organization=R.organization)

            # create log of this DirectUpload
            ul_serializer = UploadLogSerializer(data={
                'session': session.pk,
                'direct_upload': upload.pk
            })
            ul_serializer.is_valid(raise_exception=True)
            ul_serializer.save(organization=R.organization)

            return Response({'upload_id': upload.pk}, status=status.HTTP_200_OK)

    except ValidationError as ve:
        return Response({'detail': "Something went wrong!"}, status=status.HTTP_400_BAD_REQUEST)
    except SessionUploadLog.DoesNotExist:
        return Response(
            {'detail': 'Session not found.'},
            status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.debug(e)
        return Response(
            {'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    operation_id="DocumentNotifyUploadComplete",
    request=inline_serializer(
        name="DocumentNotifyUploadComplete",
        fields={"sessionId": serializers.IntegerField()}
    ),
    responses={
        status.HTTP_200_OK: OpenApiResponse("200")
    })
@api_view(["POST"])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def notify_upload_complete(request):
    """
        Use Celery to upload these documents to
        S3, then save this to PostShipmentDocument
    """
    session_id = request.data.get('session_id')

    if not session_id is None:
        return Response({"error": "session_id is empty"}, status=status.HTTP_400_BAD_REQUEST)

    task_upload_to_shipment.delay(session_id)

    return Response(status=status.HTTP_200_OK)


@extend_schema(
    operation_id="DocumentPollPostshipmentComplete",
    parameters=[
        OpenApiParameter(
            name="sessionId",
            type=int,
            location=OpenApiParameter.QUERY
        )
    ],
    responses=SessionUploadReadOnlySerializer)
@api_view(["GET"])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def poll_postshipment_complete(request, session_id: int):
    """
    request:
        session_id

    returns Response with data. Client is looking for
    UploadLog.status == 'success'
    wip:
        return this shape:
        {
            session_id: int,
            upload_logs: hash<[upload_id]: {poll_status, upload_id}>
        }
    """
    session = SessionUploadLog.objects.for_request(request).get(pk=session_id)
    serializer = SessionUploadReadOnlySerializer(session)
    return Response(serializer.data)



@extend_schema(
    operation_id="DocumentListShipmentDocuments",
    parameters=[
        OpenApiParameter(
            name="loadId",
            type=str,
            location=OpenApiParameter.QUERY
        )
    ],
    responses=PostShipmentDocumentSerializer(many=True))
@api_view(['GET'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def list_shipment_documents(request: Request, load_id: int):
    load = Load.objects.for_request(request).get(pk=load_id)
    documents = load.documents.all()
    serializer = PostShipmentDocumentSerializer(documents, many=True)
    return Response(serializer.data)



# ===================================================
# ===================================================
# ===================================================
# ===================================================
# ============ TODO LATER ===========================
# ===================================================
# ===================================================
# ===================================================
# ===================================================

### TODO: work on this later
@api_view(["POST"])
def post_upload_document(request: Request):
    """
    - create document context
    - create document queues attached to this context
    - add S3UploadImage with their object_keys
    - send this document_context to celery
    - return the data

    request.data:
        filename = serializers.CharField()
        content_type = serializers.CharField()
        category = serializers.CharField()
        queue_hash_id = serializers.CharField(required=False, allow_null=True)
    """
    files = request.data # a list

    serializer = S3UploadRequestSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(organization=request.organization)
    return Response(status=status.HTTP_200_OK)


@api_view(["GET"])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def download_document(request: Request):
    object_key = request.query_params.get("object_key")
    bucket = "PDF"
    # generate presigned url and return to client to download PDF file
    return Response()
