from django.db.models import F, Value, FloatField, ExpressionWrapper
from django.db.models.functions import Now, Extract, Coalesce

from machtms.backend.addresses.models import AddressUsage

def find_address_by_customer_score(customer_id: int):

    qs = AddressUsage.objects.filter(broker_id=customer_id).annotate(
        age_days=Extract(Now() - F("last_used"), "day"),
    ).annotate(
        score=ExpressionWrapper(
            # tweak weights to taste
            (Value(100.0) / (Value(1.0) + Coalesce(F("age_days"), Value(3650.0)))) +
            (Coalesce(F("times_used"), Value(0)) * Value(0.25)),
            output_field=FloatField(),
        )
    ).order_by("-score", "-last_used")
    return qs
