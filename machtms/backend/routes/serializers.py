from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer
from machtms.backend.routes import Stop
from machtms.backend.addresses.models import Address
from machtms.core.base.serializers import TMSBaseSerializer, FlexiblePrimaryKeyRelatedField
from machtms.backend.routes.openapi_doc import (
    STOP_READ_EXAMPLES,
    STOP_EXAMPLES,
    STOP_WRITE_EXAMPLES,
)


@extend_schema_serializer(examples=STOP_READ_EXAMPLES)
class StopReadSerializer(TMSBaseSerializer):
    class Meta:
        model = Stop
        fields = ('__all__',)


@extend_schema_serializer(examples=STOP_EXAMPLES)
class StopSerializer(TMSBaseSerializer):
    # id is optional and writable to support nested upsert operations
    id = serializers.IntegerField(required=False)
    leg = serializers.PrimaryKeyRelatedField(read_only=True)
    # Use FlexiblePrimaryKeyRelatedField to accept both PKs and model instances
    # This allows the serializer to be re-validated after parent serializer
    # has already converted PKs to instances
    address = FlexiblePrimaryKeyRelatedField(queryset=Address.objects.all())

    class Meta:
        model = Stop
        fields = '__all__'


@extend_schema_serializer(examples=STOP_WRITE_EXAMPLES)
class StopWriteSerializer(serializers.ModelSerializer):
    """
    Accepts stop objects where id is optional.
    - If id is present: use/update existing Stop
    - If id is missing: create a new Stop
    """
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Stop
        fields = ["id", "action", "address"]


