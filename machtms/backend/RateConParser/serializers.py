from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from machtms.core.base.serializers import TMSBaseSerializer
from .models import ParsingSession, RateConDocument, PresignedURLEntryPoint


# --- Request Serializers ---

class ProcessSessionRequestSerializer(serializers.Serializer):
    """Request body for triggering session processing."""
    mode = serializers.ChoiceField(choices=['sync', 'async'], default='async')


# --- Model Serializers ---

class RateConDocumentSerializer(TMSBaseSerializer):
    """Serializer for rate confirmation documents."""

    class Meta(TMSBaseSerializer.Meta):
        model = RateConDocument
        fields = [
            'id',
            'session', 'status',
            'original_filename',
            's3_key', 'file_size',
            'mime_type', 'error_message',
            'celery_task_id', 'processed_at',
            'created_at', 'updated_at',
            'load', 'classification_passed', 'classification_reason',
        ]


class ParsingSessionSerializer(TMSBaseSerializer):
    """Serializer for parsing sessions with nested documents and computed progress fields."""
    total_documents = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    documents = RateConDocumentSerializer(many=True, read_only=True)

    @extend_schema_field(serializers.IntegerField())
    def get_total_documents(self, obj):
        return obj.total_documents

    @extend_schema_field(serializers.FloatField())
    def get_progress(self, obj):
        return obj.progress

    class Meta(TMSBaseSerializer.Meta):
        model = ParsingSession
        fields = [
            'id', 'status', 'is_hidden', 'created_at', 'updated_at',
            'total_documents', 'progress', 'documents',
        ]


# --- Presigned URL Entry Point Serializers ---

class PresignedURLFileItemSerializer(serializers.Serializer):
    """A single file item in a presigned URL batch request."""
    filename  = serializers.CharField()
    mime_type = serializers.CharField(default='application/pdf')


class PresignedURLRequestSerializer(serializers.Serializer):
    """Request body for obtaining presigned upload URLs for a batch of files."""
    files = PresignedURLFileItemSerializer(many=True)


class PresignedURLEntryPointSerializer(serializers.ModelSerializer):
    """Response serializer for a single presigned URL entry point."""

    class Meta:
        model  = PresignedURLEntryPoint
        fields = ['id', 'presigned_url', 's3_key', 'filename', 'expiration', 'status']


class CreateSessionFromPresignedRequestSerializer(serializers.Serializer):
    """Request body for creating a session from already-uploaded presigned entrypoints."""
    entrypoint_ids = serializers.ListField(child=serializers.IntegerField())
