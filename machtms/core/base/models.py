from typing import Self
from django.conf import settings
from django.db import models
from django.db.models.manager import Manager
from machtms.core.base.managers import TMSManager, TMSQuerySet


class TMSModel(models.Model):
    organization = models.ForeignKey(
            'Organization',
            on_delete=models.CASCADE,
            null=True, 
            blank=True)


    class Meta:
        abstract = True


    objects: TMSManager[Self] = TMSManager()
    # objects = TMSQuerySet.as_manager()

    # @classmethod
    # def __init_subclass__(cls, **kwargs):
    #     """Dynamically set related_name based on subclass attribute `related_names`."""
    #     super().__init_subclass__(**kwargs)
    #
    #     # Get related_names list from the subclass (default to empty list if not defined)
    #     related_names = getattr(cls, "related_names", [])
    #
    #     for field_name, related_name in related_names:
    #         # Skip if the subclass explicitly defines this field
    #         if field_name in cls.__dict__:
    #             continue
    #
    #         # Apply the new related_name dynamically
    #         cls.add_to_class(
    #             field_name,
    #             models.ForeignKey(
    #                 'Organization',
    #                 on_delete=models.CASCADE,
    #                 null=DEBUG,
    #                 blank=DEBUG,
    #                 related_name=related_name
    #             )
    #         )
