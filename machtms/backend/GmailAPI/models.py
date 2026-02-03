from django.db.models.fields import related
from django.utils import timezone
from django.db import models
from machtms.core.base.models import TMSModel
from machtms.backend.auth.models import Organization
from machtms.backend.customers.models import Customer


class GoogleCredentials(TMSModel):
    class Meta(TMSModel.Meta): # type: ignore
        unique_together = ('email', 'organization')

    email = models.EmailField(max_length=254)
    token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expiry = models.DateTimeField()


class GmailBillingConfig(TMSModel):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="gmail_config")
    gmail_credentials = models.OneToOneField(GoogleCredentials, on_delete=models.CASCADE)



InvoiceLogChoices = [
    ('processing', 'PROCESSING'),
    ('success', 'SUCCESS'),
    ('error', 'ERROR')
]
class GmailInvoiceLog(TMSModel):
    load = models.ForeignKey('machtms.Load', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='processing', choices=InvoiceLogChoices)
    created_on = models.DateTimeField(default=timezone.now)
    finished = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)


class AccountRep(TMSModel):
    email = models.TextField()
    first_name = models.TextField()
    last_name = models.TextField(blank=True)
    phone = models.TextField(blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)


class AccountsPayableContact(TMSModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='ap_emails')
    name = models.TextField()
    email = models.TextField()
    is_default = models.BooleanField(default=False)


class FactoringContact(TMSModel):
    email = models.TextField()
    company_name = models.TextField()
    phone = models.TextField(blank=True)


class FactoringDefaultSettings(TMSModel):
    default = models.OneToOneField(
        FactoringContact,
        on_delete=models.CASCADE,
    )
