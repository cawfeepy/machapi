from django.conf import settings
from meilisearch import Client


meili_client: Client = Client(settings.MEILI_URL, settings.MEILI_API_KEY)
