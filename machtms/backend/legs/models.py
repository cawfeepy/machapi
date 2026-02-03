from django.core.exceptions import ValidationError
from django.db import models
from machtms.core.base.models import TMSModel


class Leg(TMSModel):
    """
    A Leg represents a segment of a load's journey containing multiple stops.
    Each leg contains stops that terminate with a delivery or hub stop.
    """
    load = models.ForeignKey(
        'machtms.Load',
        on_delete=models.CASCADE,
        related_name='legs',
        help_text='The load this leg belongs to'
    )

    class Meta:
        verbose_name = 'Leg'
        verbose_name_plural = 'Legs'
        ordering = ['pk']

    def __str__(self):
        return f"Leg {self.pk} - Load {self.load_id}"


class ShipmentAssignment(TMSModel):
    """
    Associates a carrier and driver to a specific leg of a shipment.
    """
    carrier = models.ForeignKey(
        'machtms.Carrier',
        on_delete=models.CASCADE,
        related_name='shipment_assignments',
        help_text='The carrier assigned to this leg'
    )
    driver = models.ForeignKey(
        'machtms.Driver',
        on_delete=models.CASCADE,
        related_name='shipment_assignments',
        help_text='The driver assigned to this leg'
    )
    leg = models.ForeignKey(
        Leg,
        on_delete=models.CASCADE,
        related_name='shipment_assignments',
        help_text='The leg this assignment is for'
    )

    class Meta:
        verbose_name = 'Shipment Assignment'
        verbose_name_plural = 'Shipment Assignments'
        ordering = ['pk']

    def __str__(self):
        return f"Assignment {self.pk} - Leg {self.leg_id}"
