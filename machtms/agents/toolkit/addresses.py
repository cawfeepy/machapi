from datetime import timedelta

from agno.tools import Toolkit
from agno.run.base import RunContext
from django.db.models import Q
from django.utils import timezone

from machtms.backend.addresses.models import Address, AddressUsageAccumulate, AddressUsageByCustomerAccumulate


class AddressToolkit(Toolkit):
    """Toolkit for address search, creation, and filtering"""

    def __init__(self):
        super().__init__(name="address_toolkit")
        self.register(self.search_addresses)
        self.register(self.ensure_address)
        self.register(self.get_recent_addresses_for_customer)
        self.register(self.list_addresses)
        self.register(self.get_recently_used_addresses)

    def search_addresses(
        self,
        run_context: RunContext,
        street: str = "",
        city: str = "",
        state: str = "",
        zip_code: str = "",
    ) -> str:
        """Search for addresses by partial, case-insensitive criteria.

        At least one criterion is required.

        Args:
            street: Partial street address.
            city: Partial city name.
            state: State abbreviation or partial name.
            zip_code: ZIP/postal code.

        Returns:
            Formatted list of matching addresses with their IDs.
        """
        if not any([street, city, state, zip_code]):
            return "Error: At least one search criterion is required."

        organization = run_context.dependencies["organization"]
        qs = Address.objects.filter(organization=organization)

        if street:
            qs = qs.filter(street__icontains=street)
        if city:
            qs = qs.filter(city__icontains=city)
        if state:
            qs = qs.filter(state__icontains=state)
        if zip_code:
            qs = qs.filter(zip_code__icontains=zip_code)

        addresses = qs[:20]

        if not addresses:
            return "No addresses found matching your criteria."

        lines = [f"Found {len(addresses)} address(es):"]
        for addr in addresses:
            lines.append(f"  ID {addr.pk}: {addr.street}, {addr.city}, {addr.state} {addr.zip_code}")
        return "\n".join(lines)

    def ensure_address(
        self,
        run_context: RunContext,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        country: str = "US",
    ) -> str:
        """Find an exact address match or create a new one. Returns the address ID.

        Args:
            street: Full street address.
            city: City name.
            state: State abbreviation.
            zip_code: ZIP/postal code.
            country: Country code (default US).

        Returns:
            Address ID and whether it was created or found.
        """
        organization = run_context.dependencies["organization"]
        addr, created = Address.objects.get_or_create(
            organization=organization,
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            defaults={"country": country},
        )
        status = "Created new" if created else "Found existing"
        return f"{status} address (ID {addr.pk}): {addr.street}, {addr.city}, {addr.state} {addr.zip_code}"

    def get_recent_addresses_for_customer(
        self,
        run_context: RunContext,
        customer_id: int,
        limit: int = 10,
    ) -> str:
        """Get recently used addresses for a customer.

        Args:
            customer_id: The customer's ID.
            limit: Maximum number of addresses to return.

        Returns:
            Formatted list of recent addresses for the customer.
        """
        organization = run_context.dependencies["organization"]
        usages = (
            AddressUsageByCustomerAccumulate.objects
            .filter(
                organization=organization,
                customer_id=customer_id,
            )
            .select_related('address')
            .order_by('-last_used')[:limit]
        )

        if not usages:
            return f"No recent addresses found for customer ID {customer_id}."

        lines = [f"Recent addresses for customer ID {customer_id}:"]
        for usage in usages:
            addr = usage.address
            lines.append(
                f"  ID {addr.pk}: {addr.street}, {addr.city}, {addr.state} {addr.zip_code} "
                f"(last used: {usage.last_used.strftime('%m/%d/%Y')})"
            )
        return "\n".join(lines)

    def list_addresses(
        self,
        run_context: RunContext,
        limit: int = 20,
    ) -> str:
        """List all addresses for the organization, ordered by most recently created.

        Args:
            limit: Maximum number of addresses to return (default 20).

        Returns:
            Formatted list of addresses with their IDs.
        """
        organization = run_context.dependencies["organization"]
        addresses = (
            Address.objects
            .filter(organization=organization)
            .order_by('-pk')[:limit]
        )

        if not addresses:
            return "No addresses found for this organization."

        lines = [f"Listing {len(addresses)} address(es):"]
        for addr in addresses:
            lines.append(f"  ID {addr.pk}: {addr.street}, {addr.city}, {addr.state} {addr.zip_code}")
        return "\n".join(lines)

    def get_recently_used_addresses(
        self,
        run_context: RunContext,
        days_back: int = 30,
        limit: int = 20,
    ) -> str:
        """Get addresses that have been used recently, regardless of customer.

        Args:
            days_back: Number of days to look back (default 30).
            limit: Maximum number of addresses to return (default 20).

        Returns:
            Formatted list of recently used addresses with last-used dates.
        """
        organization = run_context.dependencies["organization"]
        cutoff = timezone.now() - timedelta(days=days_back)

        usages = (
            AddressUsageAccumulate.objects
            .filter(
                organization=organization,
                last_used__gte=cutoff,
            )
            .select_related('address')
            .order_by('-last_used')[:limit]
        )

        if not usages:
            return f"No addresses used in the last {days_back} days."

        lines = [f"Addresses used in the last {days_back} days:"]
        for usage in usages:
            addr = usage.address
            lines.append(
                f"  ID {addr.pk}: {addr.street}, {addr.city}, {addr.state} {addr.zip_code} "
                f"(last used: {usage.last_used.strftime('%m/%d/%Y')})"
            )
        return "\n".join(lines)
