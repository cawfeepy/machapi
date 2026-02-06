from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.core.factories import (
    AddressFactory,
    CarrierFactory,
    CustomerFactory,
    DriverFactory,
)


class AIEnvironmentDataCreator:
    """Creates fake data for the AI agent test environment."""

    def create_all(self) -> dict:
        """Create all fake data and return a summary dict."""
        organization = Organization.objects.create(
            company_name="AI Test Trucking Co",
            phone="555-000-1234",
            email="dispatch@aitesttrucking.com",
        )

        user = OrganizationUser.objects.create_user(
            email="agent@aitesttrucking.com",
            password="testpass123",
            first_name="Agent",
            last_name="Tester",
        )
        profile = UserProfile.objects.create(
            user=user,
            organization=organization,
        )

        addresses = AddressFactory.create_batch(5, organization=organization)

        carriers = []
        drivers = []
        for _ in range(3):
            carrier = CarrierFactory.create(organization=organization)
            carriers.append(carrier)
            for _ in range(2):
                driver = DriverFactory.create(
                    carrier=carrier,
                    organization=organization,
                )
                drivers.append(driver)

        customers = CustomerFactory.create_batch(3, organization=organization)

        return {
            'organization': organization,
            'user': user,
            'profile': profile,
            'addresses': addresses,
            'carriers': carriers,
            'drivers': drivers,
            'customers': customers,
        }

    def print_summary(self, data: dict):
        """Print a summary of the created data to the terminal."""
        org = data['organization']
        print("\n" + "=" * 50)
        print("  Fake Data Summary")
        print("=" * 50)
        print(f"  Organization : {org.company_name}")
        print(f"  User         : {data['user'].email}")
        print(f"  Addresses    : {len(data['addresses'])}")
        print(f"  Carriers     : {len(data['carriers'])}")
        print(f"  Drivers      : {len(data['drivers'])}")
        print(f"  Customers    : {len(data['customers'])}")
        print("=" * 50)
        print()
