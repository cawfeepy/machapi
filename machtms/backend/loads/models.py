from django.db import models
from django.utils import timezone
from machtms.core.base.models import TMSModel


class LoadStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ASSIGNED = 'assigned', 'Assigned'
    DISPATCHED = 'dispatched', 'Dispatched'
    IN_TRANSIT = 'in_transit', 'In Transit'
    TIMES_MISSING = 'times_missing', 'Times Missing'
    RESCHEDULED = 'rescheduled', 'Rescheduled'
    CLAIM = 'claim', 'Claim'
    AT_HUB = 'at_hub', 'At Hub'
    COMPLETE = 'complete', 'Complete'
    TONU = 'tonu', 'TONU'


class BillingStatus(models.TextChoices):
    PAPERWORK_PENDING = 'paperwork_pending', 'Paperwork Pending'
    PENDING_DELIVERY = 'pending_delivery', 'Pending Delivery'
    BILLED = 'billed', 'Billed'
    REJECTED = 'rejected', 'Rejected'
    PAID = 'paid', 'Paid'


class TrailerType(models.TextChoices):
    SMALL_20 = 'SMALL_20', "20'"
    SMALL_28 = 'SMALL_28', "28'"
    MEDIUM_40 = 'MEDIUM_40', "40'"
    MEDIUM_45 = 'MEDIUM_45', "45'"
    LARGE_48 = 'LARGE_48', "48'"
    LARGE_53 = 'LARGE_53', "53'"


class Load(TMSModel):
    """
    Load model representing a transportation shipment.
    """
    reference_number = models.TextField(blank=True, default='')
    bol_number = models.TextField(blank=True, default='')

    customer = models.ForeignKey(
        'machtms.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loads'
    )

    status = models.CharField(
        max_length=20,
        choices=LoadStatus.choices,
        default=LoadStatus.PENDING
    )

    billing_status = models.CharField(
        max_length=20,
        choices=BillingStatus.choices,
        default=BillingStatus.PENDING_DELIVERY
    )

    trailer_type = models.CharField(
        max_length=20,
        choices=TrailerType.choices,
        blank=True,
        default=''
    )

    created_at = models.DateTimeField(editable=False)
    updated_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Load'
        verbose_name_plural = 'Loads'


    def save(self, *args, **kwargs):
        if not self.id:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        return super(Load, self).save(*args, **kwargs)


    def __str__(self):
        return f"Load {self.reference_number or self.pk}"
