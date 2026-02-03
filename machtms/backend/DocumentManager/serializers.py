from collections import OrderedDict
import logging
from django.db import transaction, models
from drf_spectacular.utils import extend_schema_field

from machtms.core.base.serializers import HashSerializer, TMSBaseSerializer, RelatedFieldAlternative
from machtms.backend.loads.serializers import LoadSerializer
from machtms.backend.loads.models import Load
from .utils import generate_truncated_hash, s3
from rest_framework import serializers
from rest_framework.serializers import CharField, PrimaryKeyRelatedField, Serializer
from . import models
from drf_spectacular.extensions import OpenApiSerializerExtension


logger = logging.getLogger(__name__)

class S3UploadSerializer(serializers.ModelSerializer):
    """
    queue
    object_key
    filename
    category
    content_type
    created_on
    """
    class Meta:
        model = models.S3UploadImage
        fields = ("__all__")


class S3UploadRequestSerializer(serializers.Serializer):
    files = serializers.ListSerializer(
            child=S3UploadSerializer()
            )

    def create(self, validated_data):
        uploaded = []
        files_data = validated_data.pop('files')
        for file in files_data:
            put = dict(
                    **file,
                    **validated_data,
                    )
            models.S3UploadImage.objects.create(**put)
        return uploaded


class PresignedUrlSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    category = serializers.CharField()
    queue_hash_id = serializers.CharField(required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Use provided queue_hash_id if present, otherwise generate a new one
        queue_hash_id = data.pop("queue_hash_id") or generate_truncated_hash()
        object_key = s3.create_object_key(f"{data.get('filename')}-{queue_hash_id}")

        return {
            'queue_hash_id': queue_hash_id,
            'object_key': object_key,
        }


class DirectUploadSerializer(TMSBaseSerializer):
    load_id = PrimaryKeyRelatedField(
        queryset=Load.objects.all(),
        write_only=True,
        source='load'
    )
    class Meta(TMSBaseSerializer.Meta):
        model = models.DirectUpload
        fields = '__all__'
        extra_kwargs = {"load": {"read_only": True}}


class PostShipmentDocumentSerializer(TMSBaseSerializer):
    class Meta(TMSBaseSerializer.Meta):
        model = models.PostShipmentDocument
        fields = ('__all__')


class UploadLogDictListSerializer(serializers.ListSerializer):
    """
    When the child serializer is used with many=True, return

        {
            "<pk>": {upload_id, poll_status, message},
            ...
        }
    """
    def to_representation(self, data):
        # data might be a list/tuple or a queryset
        iterable = data.all() if hasattr(data, "all") else data

        new_data= OrderedDict(
            (str(item.direct_upload_id), self.child.to_representation(item))   # keys **must** be str for JSON
            for item in iterable
        )
        print(new_data)
        return new_data


    @property
    def data(self):
        if not hasattr(self, "_data"):
            # identical to BaseSerializer.data, but without ReturnList()
            self._data = self.to_representation(self.instance)
        return self._data


class UploadLogSerializer(serializers.ModelSerializer):
    upload_id = serializers.IntegerField(source='direct_upload_id', read_only=True)

    poll_status = serializers.CharField(source='status', read_only=True)

    """
        many=True will return the following shape:
        {
            [pk]: {upload_id, poll_status, message}
        }
    """
    class Meta:
        model = models.UploadLog
        fields = ('upload_id', 'poll_status', 'message', 'direct_upload', 'session')
        extra_kwargs = {
            "direct_upload": {"write_only": True},
            "session":       {"write_only": True},
        }
        list_serializer_class = UploadLogDictListSerializer




class SessionUploadReadOnlySerializer(serializers.ModelSerializer):
    #{
#   #    session_id: int,
#   #    post_documents: [] # load.documents.all()
#   #    upload_logs: {} # session.upload_logs.all()
    #}

    session_id = PrimaryKeyRelatedField(queryset=models.SessionUploadLog.objects.all(), source='pk')
    post_documents = PostShipmentDocumentSerializer(
        many=True, read_only=True, source='load.documents')
    upload_logs = serializers.SerializerMethodField(read_only=True)

    @extend_schema_field(serializers.DictField(child=UploadLogSerializer()))
    def get_upload_logs(self, obj):
        """
        Returns
        {
            "<upload_id>": {upload_id, poll_status, message},
            ...
        }
        """
        qs = obj.upload_logs.all()
        return OrderedDict(
            (item.direct_upload_id, UploadLogSerializer(item).data)
            for item in qs
        )

    class Meta:
        model = models.SessionUploadLog
        fields = ('post_documents', 'session_id', 'upload_logs')


class SessionUploadLogSerializer(TMSBaseSerializer):
    load_id = PrimaryKeyRelatedField(queryset=Load.objects.all(), source='load')
    class Meta(TMSBaseSerializer.Meta):
        model = models.SessionUploadLog
        fields = ('load_id',)

