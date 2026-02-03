from django.db import models
from django.utils import timezone
from dirtyfields import DirtyFieldsMixin

from machtms.core.base.models import TMSModel


class Stop(DirtyFieldsMixin, TMSModel):
    """
    Represents a stop in a transportation route.

    A stop is a location where a driver must perform an action such as
    loading, unloading, or picking up/dropping off cargo.
    """

    ACTION_CHOICES = [
            ('LL', 'LIVE LOAD'),
            ('LU', 'LIVE UNLOAD'),
            ('HL', 'HOOK LOADED'),
            ('LD', 'DROP LOADED'),
            ('EMPP', 'EMPTY PICKUP'),
            ('EMPD', 'EMPTY DROP'),
            ('HUBP', 'HUB PICKUP'),
            ('HUBD', 'HUB DROPOFF'),
    ]

    leg = models.ForeignKey(
            'machtms.Leg',
            on_delete=models.CASCADE,
            related_name='stops')
    stop_number = models.PositiveIntegerField(
            help_text='Order of this stop within the leg'
    )
    address = models.ForeignKey(
            'machtms.Address',
            on_delete=models.CASCADE,
            related_name='stops',
            help_text='The address where this stop takes place'
    )

    start_range = models.DateTimeField(
            help_text='The earliest time the stop can occur'
    )

    end_range = models.DateTimeField(
            null=True,
            help_text='The latest time the stop can occur (optional)'
    )

    timestamp = models.DateTimeField(
            default=timezone.now,
            help_text='When this stop was created'
    )

    action = models.CharField(
            max_length=4,
            choices=ACTION_CHOICES,
            help_text='The type of action to be performed at this stop'
    )

    po_numbers = models.TextField(
            blank=True,
            default='',
            help_text='Purchase order numbers associated with this stop'
    )

    driver_notes = models.TextField(
            blank=True,
            default='',
            help_text='Notes for the driver regarding this stop'
    )

    class Meta:
        verbose_name = 'Stop'
        verbose_name_plural = 'Stops'
        ordering = ['stop_number']
        unique_together = ['stop_number', 'leg']

    def __str__(self):
        return f"Stop {self.stop_number} - {self.get_action_display()} at {self.address}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        # Must use check_relationship=True to track ForeignKey changes
        address_changed = 'address' in self.get_dirty_fields(check_relationship=True)

        super().save(*args, **kwargs)

        # Dispatch task if new stop or address changed
        if is_new or address_changed:
            self._dispatch_address_usage_task()

    def _dispatch_address_usage_task(self):
        """Queue Celery task to track address usage."""
        from machtms.core.celerycontroller import controller
        from machtms.core.tasks.addresses import update_address_usage

        controller.delay(
            update_address_usage,
            stop_id=self.pk,
            address_id=self.address_id,
        )


