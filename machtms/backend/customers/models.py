from django.db import models
from machtms.core.base.models import TMSModel


class Customer(TMSModel):
    """
    Customer model representing a business customer/broker.
    """
    customer_name = models.CharField(max_length=255)
    address = models.ForeignKey(
        'machtms.Address',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers'
    )
    phone_number = models.CharField(max_length=20, blank=True)
    # representatives = models.ManyToManyField(
    #     CustomerRepresentative,
    #     blank=True,
    #     related_name='customers'
    # )
    # ap_emails = models.ManyToManyField(
    #     CustomerAP,
    #     blank=True,
    #     related_name='customers'
    # )

    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.customer_name


class CustomerRepresentative(TMSModel):
    """
    Representative associated with a customer.
    """
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    company = models.ForeignKey(Customer, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Customer Representative'
        verbose_name_plural = 'Customer Representatives'

    def __str__(self):
        return self.name


class CustomerAP(TMSModel):
    """
    Customer Accounts Payable contact information.
    Represents an AP contact associated with customers.
    """

    class PaymentType(models.TextChoices):
        QUICKPAY = 'quickpay', 'Quick Pay'
        STANDARD = 'standard', 'Standard Pay'

    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.STANDARD
    )
    company = models.ForeignKey(Customer, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Customer AP'
        verbose_name_plural = 'Customer APs'

    def __str__(self):
        return f"{self.email} ({self.get_payment_type_display()})"
