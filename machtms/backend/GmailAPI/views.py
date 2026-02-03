import logging

from djangorestframework_camel_case.parser import CamelCaseJSONParser
from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from machtms.core.base.mixins import TMSViewMixin
logger = logging.getLogger(__name__)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import api_view, parser_classes, renderer_classes
from rest_framework.response import Response
from machtms.backend.GmailAPI.models import AccountsPayableContact, GmailBillingConfig, GmailInvoiceLog
from machtms.backend.GmailAPI.serializers import APContactSerializer, GmailInvoiceLogSerializer
from machtms.backend.GmailAPI.utils.service import GmailService
from machtms.backend.loads.models import Load
from .tasks import invoice_load

@extend_schema(
    operation_id="GmailBillLoad",
    summary=("""Bills the load after necessary docs are uploaded.
        Requires a loadId:int
    """
    ),
    request=inline_serializer(
        name="SendInvoiceRequest",
        fields={
            "loadId": serializers.IntegerField()
        }
    ),
    responses=GmailInvoiceLogSerializer)
@api_view(['POST'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def bill_load(request):
    load_id = request.data.get("load_id")
    load = Load.objects.for_request(request).get(pk=load_id)
    # check if load.customer contains an AccountsPayableContact
    invoice_log = GmailInvoiceLog.objects.create(
        organization=request.organization,
        load=load)
    invoice_load.delay(invoice_log.pk) # type: ignore
    serializer = GmailInvoiceLogSerializer(invoice_log)
    return Response(serializer.data)



@extend_schema(
    operation_id='getGmailLogList',
    summary=(
        "Shows the user the billing history of a load."
        "GET method so it'll require a parameter of loadId"
    ),
    parameters=[
        OpenApiParameter(name="loadId", type=int, location=OpenApiParameter.QUERY)
    ],
    responses=GmailInvoiceLogSerializer(many=True)
)
@api_view(['GET'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def get_gmail_log_list(request, load_id):
    load = Load.objects.for_request(request).get(pk=load_id)
    logs = GmailInvoiceLog.objects.filter(load=load).order_by('-created_on')
    serializer = GmailInvoiceLogSerializer(logs, many=True)
    return Response(serializer.data)



@extend_schema(
    operation_id="pollInvoicingStatus",
    summary=("In the middle of invoicing, poll for"
            " email updates if the load has successfully been bill"),
    parameters=[
        OpenApiParameter(name="invoice_log_id", type=int, location=OpenApiParameter.QUERY)
    ],
    responses=GmailInvoiceLogSerializer
)
@api_view(['GET'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def poll_invoicing_status(request, invoice_log_id=None):
    """
    will poll every 2 seconds to check if the
    invoice was sent

    returns {
        load: <int>
        created_on: <date>
        status: <date>
    }
    """
    invoice_log = GmailInvoiceLog.objects.for_request(request).get(pk=invoice_log_id)
    serializer = GmailInvoiceLogSerializer(invoice_log)
    return Response(serializer.data)


@extend_schema(
    operation_id="checkGmailAuthentication",
    summary="Check auth of the user's Gmail credentials",
    responses={
        status.HTTP_200_OK: OpenApiResponse(description="User is authenticated with Gmail API."),
        status.HTTP_401_UNAUTHORIZED: OpenApiResponse(description="User is not authenticated or configuration missing."),
    }
)
@api_view(['GET'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def check_authentication(request):
    """
        Checks whether the user is authenticated into the gmail api.
        Should return either true or false.

        if false, the browser will require client to sign in
        if true, client is good to make actions using gmail
    """
    organization = request.organization
    try:
        config = GmailBillingConfig.objects.get(organization=organization)
        service = GmailService.authenticate(config.gmail_credentials.email, organization)
        return Response(status=status.HTTP_200_OK)
    except GmailBillingConfig.DoesNotExist:
        logger.error("Gmail config does not exist")
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.error(e)
        return Response(status=status.HTTP_401_UNAUTHORIZED)


@extend_schema(
    request=inline_serializer(
        name="ProcessTokenFlowRequest",
        fields={
            "authCode": serializers.CharField(),
            "requestUri": serializers.CharField()
        }
    ),
    responses={200: OpenApiTypes.NONE, 400: OpenApiTypes.NONE})
@api_view(['POST'])
@parser_classes([CamelCaseJSONParser])
@renderer_classes([CamelCaseJSONRenderer])
def process_flow(request):
    organization = request.organization
    code = request.data.get('auth_code')
    request_uri = request.data.get('request_uri')
    try:
        service = GmailService.exchange_code(code, request_uri, organization)
    except Exception as e:
        logger.error(f"There was during exchange of Gmail auth_code:{e}")
        return Response(status=status.HTTP_400_BAD_REQUEST)
    return Response(status=status.HTTP_200_OK)


class AccountsPayableViewSet(TMSViewMixin, viewsets.ModelViewSet):
    queryset = AccountsPayableContact.objects.all()
    serializer_class = APContactSerializer

