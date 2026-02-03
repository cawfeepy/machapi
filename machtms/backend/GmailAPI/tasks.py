# tasks.py
import logging
logger = logging.getLogger(__name__)
from django.utils import timezone
from django.db.models import Q
from machtms.backend.auth.models import Organization
from celery import shared_task
from machtms.backend.GmailAPI.models import GmailInvoiceLog, GmailBillingConfig
from machtms.backend.GmailAPI.utils.gather import DocumentAggregator
from machtms.backend.GmailAPI.utils.send import MessageBuilder
from machtms.backend.GmailAPI.utils.service import GmailService


@shared_task(bind=True)
def invoice_load(self, invoice_log_id):
    invoice_log = GmailInvoiceLog.objects.get(pk=invoice_log_id)
    load = invoice_log.load
    try:
        config = GmailBillingConfig.objects.get(organization=invoice_log.organization)
        creds = config.gmail_credentials

        service = GmailService.authenticate(creds.email, config.organization)
        documents = DocumentAggregator.aggregate_documents(
            invoice_log.load, organization=config.organization
        )
        message = MessageBuilder(
            load,
            creds.email,
            load.customer.ap_email.email,
            documents
        ).construct_email()
        service.send_email(message)
        invoice_log.status = 'success'
    except GmailBillingConfig.DoesNotExist:
        logger.error("GmailBillingConfig did not exist")
        invoice_log.status = 'error'
        invoice_log.error_message = "Error authenticating Gmail account"
    finally:
        invoice_log.finished = timezone.now()
        invoice_log.save()


@shared_task
def scheduled_invoice_load(self):
    """
        Iterate through each organization.

        Filter through loads that:
        - load.status != billed
        - contains a category POD document
            OR | load is marked as TONU

        later: send all organizations to different
        machines listening to process the task
    """
    organizations = Organization.objects.all()
    for org in organizations:

        loads = org.load_set.all().exclude(
           Q(active=False)|Q(status='billed'),
        ).filter(
                Q(documents__category='POD')
                | Q(is_TONU=True)
        ).distinct()

        for load in loads:
            invoice_log = GmailInvoiceLog.objects.create(
                organization=org,
                load=load)
            try:
                config = GmailBillingConfig.objects.get(organization=org)
                creds = config.gmail_credentials

                service = GmailService.authenticate(creds.email, config.organization)

                documents = DocumentAggregator.aggregate_documents(
                    load,
                    organization=config.organization)

                message = MessageBuilder(
                    load,
                    creds.email,
                    load.customer.ap_email.email,
                    documents
                ).construct_email()

                service.send_email(message)
                invoice_log.status = 'success'
            except Exception as e:
                logger.error(e)
                invoice_log.status = 'error'
                invoice_log.error_message = 'Something went wrong during scheduling billing.'
            finally:
                invoice_log.finished = timezone.now()
                invoice_log.save()
