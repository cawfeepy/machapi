from django.utils import timezone
from django.db import models
from machtms.core.base.models import TMSModel

class BaseAddress(TMSModel):
    street = models.TextField()
    city = models.TextField()
    state = models.TextField()
    zip_code = models.TextField()
    country = models.TextField()

    class Meta(TMSModel.Meta):
        abstract = True

class Address(BaseAddress):
    """
    Represents a physical address used in the transportation management system.
    Linked to customers through the AddressUsage intermediary model.
    """
    street = models.CharField(max_length=300)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=2)
    zip_code = models.CharField(max_length=12)
    country = models.TextField(default='US')
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'

    def __str__(self):
        parts = [self.street, self.city, self.state, self.zip_code, self.country]
        return ', '.join(part for part in parts if part)


class AddressUsageAccumulate(TMSModel):
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    last_used = models.DateTimeField(default=timezone.now)


class AddressUsageByCustomerAccumulate(TMSModel):
    """
    A model that accumulates rows of address usage.
    That way we can analyze this data for recency by
    any date range.

    times_used isn't needed since we'll use aggregation
    functions to calculate that.
    """
    address = models.ForeignKey(
        'Address',
        on_delete=models.CASCADE,
        related_name='customer_usages_accumulate'
    )
    customer = models.ForeignKey(
        'machtms.Customer',
        on_delete=models.CASCADE,
        related_name='address_usages_accumulate'
    )
    last_used = models.DateTimeField(default=timezone.now)


    class Meta:
        verbose_name = 'Address Usage (by Customer)'
        verbose_name_plural = 'Address Usages (by Customer)'

    def __str__(self):
        return f"{self.address} - {self.customer}"

