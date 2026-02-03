from rest_framework import serializers
from machtms.core.base.serializers import TMSBaseSerializer
from machtms.backend.carriers.models import Carrier, Driver


class DriverSerializer(TMSBaseSerializer):
    """Serializer for Driver model."""
    full_name = serializers.ReadOnlyField()

    class Meta(TMSBaseSerializer.Meta):
        model = Driver
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'email',
            'address',
            'carrier',
        ]


class DriverListSerializer(TMSBaseSerializer):
    """Lightweight serializer for Driver list views."""
    full_name = serializers.ReadOnlyField()

    class Meta(TMSBaseSerializer.Meta):
        model = Driver
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'full_name',
            'phone_number',
            'carrier',
        ]


class CarrierSerializer(TMSBaseSerializer):
    """Serializer for Carrier model."""
    drivers = DriverListSerializer(many=True, read_only=True)

    class Meta(TMSBaseSerializer.Meta):
        model = Carrier
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'carrier_name',
            'phone',
            'email',
            'contractor',
            'drivers',
        ]


class CarrierListSerializer(TMSBaseSerializer):
    """Lightweight serializer for Carrier list views."""
    driver_count = serializers.SerializerMethodField()

    class Meta(TMSBaseSerializer.Meta):
        model = Carrier
        fields = TMSBaseSerializer.Meta.fields + [
            'id',
            'carrier_name',
            'phone',
            'contractor',
            'driver_count',
        ]

    def get_driver_count(self, obj):
        return obj.drivers.count()
