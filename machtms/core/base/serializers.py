from django.db import models
from machtms.core.auth.contextdefault import CurrentOrganizationDefault
from rest_framework import serializers


class FlexiblePrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """
    A PrimaryKeyRelatedField that accepts both PKs and model instances.

    This is useful when data may have already been converted to model instances
    by a parent serializer's to_internal_value(), but needs to be re-validated
    by a child serializer that expects PKs.
    """
    def to_internal_value(self, data):
        # If already a model instance, return it directly
        if hasattr(data, 'pk'):
            queryset = self.get_queryset()
            # Verify it belongs to the queryset
            if queryset.filter(pk=data.pk).exists():
                return data
            self.fail('does_not_exist', pk_value=data.pk)
        return super().to_internal_value(data)


class RelatedFieldAlternative(FlexiblePrimaryKeyRelatedField):
    """
    A PrimaryKeyRelatedField that accepts PKs on input but can return
    full serialized data on output when a serializer is provided.
    """
    def __init__(self, **kwargs):
        self.serializer = kwargs.pop('serializer', None)
        if self.serializer is not None and not issubclass(self.serializer, serializers.Serializer):
            raise TypeError('"serializer" is not a valid serializer class')
        super().__init__(**kwargs)

    def use_pk_only_optimization(self):
        return False if self.serializer else True

    def to_representation(self, instance):
        if self.serializer:
            return self.serializer(instance, context=self.context).data
        return super().to_representation(instance)


class TMSBaseSerializer(serializers.ModelSerializer):
    organization = serializers.HiddenField(default=CurrentOrganizationDefault())

    class Meta:
        fields = ['organization',]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('organization'):
            del data['organization']
        return data


class HashSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        iterable = data.all() if isinstance(data, models.Manager) else data
        result = {}
        for obj in iterable:
            result[obj.pk] = self.child.to_representation(obj)
        return result


class EmptyOnNoneListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        if data is None:
            return []          # convert None � []
        return super().to_representation(data)
