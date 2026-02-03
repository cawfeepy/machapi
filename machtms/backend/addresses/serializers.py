from rest_framework import serializers
from machtms.core.base.serializers import TMSBaseSerializer
from machtms.backend.addresses.models import (
    Address,
    AddressUsageAccumulate,
    AddressUsageByCustomerAccumulate,
)


class AddressSerializer(TMSBaseSerializer):
    """Serializer for the Address model."""

    class Meta(TMSBaseSerializer.Meta):
        model = Address
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'street',
            'city',
            'state',
            'zip_code',
            'country',
            'latitude',
            'longitude',
        ]
        read_only_fields = ['id']


class AddressUsageAccumulateSerializer(TMSBaseSerializer):
    """Serializer for the AddressUsageAccumulate model."""
    address_detail = AddressSerializer(source='address', read_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = AddressUsageAccumulate
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'address',
            'address_detail',
            'last_used',
        ]
        read_only_fields = ['id']


class AddressUsageByCustomerAccumulateSerializer(TMSBaseSerializer):
    """Serializer for the AddressUsageByCustomerAccumulate model."""
    address_detail = AddressSerializer(source='address', read_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = AddressUsageByCustomerAccumulate
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'address',
            'address_detail',
            'customer',
            'last_used',
        ]
        read_only_fields = ['id']
