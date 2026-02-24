from django.db import models
from machtms.core.base.models import TMSModel


class IncomeLineItem(TMSModel):
    class Categories(models.TextChoices):
        FLAT_RATE   = 'FR', ("Flat rate")
        LUMPER      = 'LF', ("Lumper")
        DEADHEAD    = 'DH', ("Deadhead")
        DETENTION   = 'DT', ("Detention")
        LAYOVER     = 'LO', ("Layover")
        STORAGE     = 'TS', ("Storage")
        STOPOFF     = 'SO', ("Stop off")
        TONU        = 'TONU', ("TONU (Truck ordered not used)")

    class Meta:
        ordering = ('id',)

    category = models.CharField(
        max_length=20, 
        choices=Categories.choices, 
        default=Categories.FLAT_RATE)
    rate = models.DecimalField(
        default=0.00, 
        max_digits=8, 
        decimal_places=2)
    quantity = models.FloatField(default=1.0)
    load = models.ForeignKey(
        'Load',
        related_name='income_line_items',
        on_delete=models.CASCADE)


    @property
    def total(self):
        _total = float(self.quantity)  * float(self.rate)
        return _total
