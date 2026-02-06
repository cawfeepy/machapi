from datetime import timedelta

from agno.tools import Toolkit
from agno.run.base import RunContext
from django.db.models import Count
from django.utils import timezone

from machtms.backend.customers.models import Customer
from machtms.backend.loads.models import Load


class CustomerToolkit(Toolkit):
    """Toolkit for customer search and filtering operations."""

    def __init__(self):
        super().__init__(name="customer_toolkit")
        self.register(self.search_customers)
        self.register(self.list_customers)
        self.register(self.get_recently_active_customers)

    def search_customers(self, run_context: RunContext, name: str) -> str:
        """Search customers by name (partial, case-insensitive).

        Args:
            name: Customer name to search for.

        Returns:
            Formatted list of matching customers with IDs.
        """
        if not name:
            return "Error: Customer name is required."

        organization = run_context.dependencies["organization"]
        customers = (
            Customer.objects
            .filter(
                organization=organization,
                customer_name__icontains=name,
            )[:20]
        )

        if not customers:
            return f"No customers found matching '{name}'."

        lines = [f"Found {len(customers)} customer(s):"]
        for c in customers:
            phone = c.phone_number or "N/A"
            lines.append(f"  ID {c.pk}: {c.customer_name} | Phone: {phone}")
        return "\n".join(lines)

    def list_customers(
        self,
        run_context: RunContext,
        limit: int = 20,
    ) -> str:
        """List all customers for the organization, ordered by name.

        Args:
            limit: Maximum number of customers to return (default 20).

        Returns:
            Formatted list of customers with IDs and phone numbers.
        """
        organization = run_context.dependencies["organization"]
        customers = (
            Customer.objects
            .filter(organization=organization)
            .order_by('customer_name')[:limit]
        )

        if not customers:
            return "No customers found for this organization."

        lines = [f"Listing {len(customers)} customer(s):"]
        for c in customers:
            phone = c.phone_number or "N/A"
            lines.append(f"  ID {c.pk}: {c.customer_name} | Phone: {phone}")
        return "\n".join(lines)

    def get_recently_active_customers(
        self,
        run_context: RunContext,
        days_back: int = 30,
        limit: int = 20,
    ) -> str:
        """Get customers that have loads created within the last N days.

        Args:
            days_back: Number of days to look back (default 30).
            limit: Maximum number of customers to return (default 20).

        Returns:
            Formatted list of recently active customers with load counts.
        """
        organization = run_context.dependencies["organization"]
        cutoff = timezone.now() - timedelta(days=days_back)

        customers = (
            Customer.objects
            .filter(
                organization=organization,
                loads__created_at__gte=cutoff,
            )
            .annotate(recent_load_count=Count('loads'))
            .order_by('-recent_load_count')[:limit]
        )

        if not customers:
            return f"No customers with loads in the last {days_back} days."

        lines = [f"Customers active in the last {days_back} days:"]
        for c in customers:
            phone = c.phone_number or "N/A"
            lines.append(
                f"  ID {c.pk}: {c.customer_name} | Phone: {phone} "
                f"| Recent loads: {c.recent_load_count}"
            )
        return "\n".join(lines)
