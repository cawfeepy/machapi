import factory
import uuid
from django.utils import timezone
from machtms.backend.DocumentManager.models import DirectUpload, PostShipmentDocument, SessionUploadLog, UploadLog
from .loads import LoadFactory

def random_hash():
    return uuid.uuid4().hex

class DirectUploadFactory(factory.django.DjangoModelFactory):
    created_on = factory.LazyFunction(timezone.now)
    queue_hash_id = factory.LazyFunction(random_hash)
    load = factory.SubFactory(LoadFactory)

    class Meta:
        model = DirectUpload


class SessionUploadLogFactory(factory.django.DjangoModelFactory):
    created_on = factory.LazyFunction(timezone.now)
    load = factory.SubFactory(LoadFactory)

    class Meta:
        model = SessionUploadLog


class UploadLogFactory(factory.django.DjangoModelFactory):
    created_on = factory.LazyFunction(timezone.now)
    direct_upload = factory.SubFactory(DirectUploadFactory)
    session = factory.SubFactory(SessionUploadLogFactory)

    class Meta:
            model = UploadLog


class PostShipmentDocumentFactory(factory.django.DjangoModelFactory):
    created_on = factory.LazyFunction(timezone.now)
    load = factory.SubFactory(LoadFactory)

    class Meta:
        model = PostShipmentDocument



