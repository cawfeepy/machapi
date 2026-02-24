import factory
from django.utils import timezone
from machtms.backend.RateConParser.models import (
    ParsingSession,
    RateConDocument,
    ParsedRateCon,
    SessionStatus,
    DocumentStatus,
)


class ParsingSessionFactory(factory.django.DjangoModelFactory):
    status = SessionStatus.UPLOADING
    created_at = factory.LazyFunction(timezone.now)

    class Meta:
        model = ParsingSession


class RateConDocumentFactory(factory.django.DjangoModelFactory):
    session = factory.SubFactory(ParsingSessionFactory)
    status = DocumentStatus.PENDING
    original_filename = factory.Sequence(lambda n: f"ratecon_{n}.pdf")
    s3_key = factory.Sequence(lambda n: f"ratecon/test/ratecon_{n}.pdf")
    file_size = 1024
    mime_type = 'application/pdf'
    created_at = factory.LazyFunction(timezone.now)

    class Meta:
        model = RateConDocument


class ParsedRateConFactory(factory.django.DjangoModelFactory):
    document = factory.SubFactory(RateConDocumentFactory)
    raw_text = "Sample parsed text"
    structured_data = factory.LazyFunction(lambda: {"reference_number": "TEST-001"})
    classification_passed = True
    created_at = factory.LazyFunction(timezone.now)

    class Meta:
        model = ParsedRateCon
