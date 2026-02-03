from rest_framework import serializers
from machtms.core.base.serializers import TMSBaseSerializer
from machtms.backend.customers.models import Customer, CustomerAP, CustomerRepresentative


class CustomerAPSerializer(TMSBaseSerializer):
    """Serializer for CustomerAP model."""

    class Meta(TMSBaseSerializer.Meta):
        model = CustomerAP
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'email',
            'phone_number',
            'payment_type',
        ]


class CustomerRepresentativeSerializer(TMSBaseSerializer):
    """Serializer for CustomerRepresentative model."""

    class Meta(TMSBaseSerializer.Meta):
        model = CustomerRepresentative
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'name',
            'email',
            'phone_number',
        ]


class CustomerSerializer(TMSBaseSerializer):
    """Serializer for Customer model."""
    representatives = CustomerRepresentativeSerializer(many=True, read_only=True)
    ap_emails = CustomerAPSerializer(many=True, read_only=True)
    representative_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomerRepresentative.objects.all(),
        many=True,
        write_only=True,
        source='representatives',
        required=False
    )
    ap_email_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomerAP.objects.all(),
        many=True,
        write_only=True,
        source='ap_emails',
        required=False
    )

    class Meta(TMSBaseSerializer.Meta):
        model = Customer
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'customer_name',
            'address',
            'phone_number',
            'representatives',
            'ap_emails',
            'representative_ids',
            'ap_email_ids',
        ]


class CustomerListSerializer(TMSBaseSerializer):
    """Lightweight serializer for Customer list views."""

    class Meta(TMSBaseSerializer.Meta):
        model = Customer
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'customer_name',
            'phone_number',
        ]
