from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from machtms.core.base.serializers import TMSBaseSerializer
from .models import ParsingSession, RateConDocument, ParsedRateCon, SessionStatus, DocumentStatus


# --- Request Serializers ---

class CreateSessionRequestSerializer(serializers.Serializer):
    """Request body for creating a new parsing session (empty body accepted)."""
    pass


class DocumentUploadRequestSerializer(serializers.Serializer):
    """Request body for uploading a single document to a session."""
    session_id = serializers.IntegerField()
    filename = serializers.CharField()
    mime_type = serializers.CharField(default='application/pdf')


class ProcessSessionRequestSerializer(serializers.Serializer):
    """Request body for triggering session processing."""
    mode = serializers.ChoiceField(choices=['sync', 'async'], default='sync')


# --- Model Serializers ---

class ParsedRateConSerializer(TMSBaseSerializer):
    """Serializer for parsed rate confirmation content."""

    class Meta(TMSBaseSerializer.Meta):
        model = ParsedRateCon
        fields = '__all__'
        read_only_fields = [
            'document', 'raw_text', 'structured_data', 'load',
            'classification_passed', 'classification_reason', 'created_at',
        ]


class RateConDocumentSerializer(TMSBaseSerializer):
    """Serializer for rate confirmation documents."""

    class Meta(TMSBaseSerializer.Meta):
        model = RateConDocument
        fields = [
            'id', 'organization', 'session', 'status', 'original_filename',
            's3_key', 'file_size', 'mime_type', 'error_message',
            'celery_task_id', 'processed_at', 'created_at', 'updated_at',
        ]


class RateConDocumentDetailSerializer(RateConDocumentSerializer):
    """Document serializer with nested parsed content."""
    parsed_content = ParsedRateConSerializer(read_only=True)

    class Meta(RateConDocumentSerializer.Meta):
        fields = RateConDocumentSerializer.Meta.fields + ['parsed_content']


class RateConDocumentStatusSerializer(serializers.ModelSerializer):
    """Lightweight serializer for document status polling."""

    class Meta:
        model = RateConDocument
        fields = ['id', 'status', 'original_filename', 'error_message', 'processed_at']


class ParsingSessionSerializer(TMSBaseSerializer):
    """Serializer for parsing sessions with computed progress fields."""
    total_documents = serializers.SerializerMethodField()
    completed_documents = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField())
    def get_total_documents(self, obj):
        return obj.total_documents

    @extend_schema_field(serializers.IntegerField())
    def get_completed_documents(self, obj):
        return obj.completed_documents

    @extend_schema_field(serializers.FloatField())
    def get_progress(self, obj):
        return obj.progress

    class Meta(TMSBaseSerializer.Meta):
        model = ParsingSession
        fields = [
            'id', 'organization', 'status', 'created_at', 'updated_at',
            'total_documents', 'completed_documents', 'progress',
        ]


class ParsingSessionDetailSerializer(ParsingSessionSerializer):
    """Session serializer with nested documents."""
    documents = RateConDocumentSerializer(many=True, read_only=True)

    class Meta(ParsingSessionSerializer.Meta):
        fields = ParsingSessionSerializer.Meta.fields + ['documents']
