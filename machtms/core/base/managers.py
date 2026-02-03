import logging
from django.db import models
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from typing import TypeVar, Optional, Sequence, TYPE_CHECKING

_MT = TypeVar("_MT", bound="TMSModel", covariant=True) # type: ignore
logger = logging.getLogger(__name__)


class TMSQuerySet(models.QuerySet[_MT]):

    def for_organization(self, organization):
        """Filter to the given organisation."""
        return self.all() if settings.DEBUG else self.filter(organization=organization)

    def for_request(self, request):
        """
        Entry point for views: works out which organisation applies,
        then delegates to the underlying queryset method.
        """
        org = getattr(request, "organization", None)
        if org is None and not settings.DEBUG:
            raise PermissionDenied("Not authenticated")
        return self.for_organization(org)

    # TODO: remove this function
    def fbo(
        self,
        organization: Optional[models.Model] = None,
        request: Optional[Request] = None,
    ) -> 'TMSQuerySet[_MT]':

        if settings.DEBUG:
            return self.all()
        if request\
            and hasattr(request, 'organization')\
            and request.organization is not None:
            return self.filter(organization=request.organization)
        elif organization is not None:
            return self.filter(organization=organization)

        logger.error(f"settings.DEBUG set to {settings.DEBUG}: Not Authenticated")
        raise Exception("Not Authenticated")


if TYPE_CHECKING:
    # • In type-checking mode we inherit from both Manager and QuerySet,
    #   so Pylance & mypy see every method.
    class TMSManager(models.Manager[_MT], TMSQuerySet[_MT]): ...
else:
    # • At runtime we want the real thing that Django builds for us.
    TMSManager = models.Manager.from_queryset(TMSQuerySet)
