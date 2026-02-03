from django.urls import path
from rest_framework import routers

from machtms.backend.GmailAPI.views import AccountsPayableViewSet, check_authentication, get_gmail_log_list, poll_invoicing_status, bill_load, process_flow


urlpatterns = [
    path("bill_load", bill_load, name="api.bill_load"),
    path("billing_logs/<int:load_id>", get_gmail_log_list, name="api.billing_logs"),
    path("poll_billing/<int:invoice_log_id>", poll_invoicing_status, name="api.poll_billing"),
    path("check_gmail_auth", check_authentication, name="api.check_gmail_auth"),
    path("process_gmail_flow", process_flow, name='api.process_gmail_flow')
]

router = routers.SimpleRouter()
router.register(r'ap_contacts', AccountsPayableViewSet, basename='ap_contact')
urlpatterns += router.urls
