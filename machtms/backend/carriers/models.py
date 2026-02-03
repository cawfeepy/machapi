from django.db import models
from machtms.core.base.models import TMSModel


class Carrier(TMSModel):
    """
    Carrier model representing a trucking company or freight carrier.
    """
    carrier_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    contractor = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Carrier'
        verbose_name_plural = 'Carriers'

    def __str__(self):
        return self.carrier_name


class Driver(TMSModel):
    """
    Driver model representing a truck driver.
    Can be associated with a carrier.
    """
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.ForeignKey(
        'machtms.Address',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drivers'
    )
    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drivers'
    )

    class Meta:
        verbose_name = 'Driver'
        verbose_name_plural = 'Drivers'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
