# serializers.py
from rest_framework import serializers
from machtms.core.base.serializers import EmptyOnNoneListSerializer, TMSBaseSerializer
from machtms.backend.GmailAPI.models import AccountsPayableContact, GmailInvoiceLog, GmailBillingConfig, GoogleCredentials


class GmailInvoiceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GmailInvoiceLog
        fields = '__all__'


class APContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountsPayableContact
        fields = '__all__'
        list_serializer_class = EmptyOnNoneListSerializer


class GmailBillingConfigSerializer(TMSBaseSerializer):
    class Meta:
        model = GmailBillingConfig
        fields = '__all__'


class GoogleCredentialsSerialier(TMSBaseSerializer):
    class Meta:
        model = GoogleCredentials
        fields = '__all__'
