import factory
from django.utils import timezone
from machtms.backend.RateConParser.models import (
    ParsingSession,
    RateConDocument,
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
    load = None
    classification_passed = None
    created_at = factory.LazyFunction(timezone.now)

    class Meta:
        model = RateConDocument
