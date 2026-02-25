from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.core.factories import (
    AddressFactory,
    CarrierFactory,
    CustomerFactory,
    DriverFactory,
)
from machtms.core.factories.creator_factories.prebuilt import create_weekly_loads


class DevEnvironmentDataCreator:
    """Creates fake data for the devserver environment."""

    def __init__(self, loads_per_week=10, offset=0, stops_per_load=2):
        self.loads_per_week = loads_per_week
        self.offset = offset
        self.stops_per_load = stops_per_load

    def create_all(self) -> dict:
        """Create org, user, profile, base data, and weekly loads."""
        organization = Organization.objects.create(
            company_name="Dev Trucking Co",
            phone="555-000-5678",
            email="dispatch@devtrucking.com",
        )

        user = OrganizationUser.objects.create_user(
            email="dev@devtrucking.com",
            password="testpass123",
            first_name="Dev",
            last_name="User",
        )
        profile = UserProfile.objects.create(
            user=user,
            organization=organization,
        )

        addresses = AddressFactory.create_batch(5, organization=organization)

        carriers = []
        drivers = []
        for _ in range(3):
            carrier = CarrierFactory.create(
                organization=organization,
                address__organization=organization,
            )
            carriers.append(carrier)
            for _ in range(2):
                driver = DriverFactory.create(
                    carrier=carrier,
                    organization=organization,
                )
                drivers.append(driver)

        customers = CustomerFactory.create_batch(
            3,
            organization=organization,
            address__organization=organization,
        )

        load_results = create_weekly_loads(
            loads_per_week=self.loads_per_week,
            offset=self.offset,
            stops_per_load=self.stops_per_load,
        )

        return {
            'organization': organization,
            'user': user,
            'profile': profile,
            'addresses': addresses,
            'carriers': carriers,
            'drivers': drivers,
            'customers': customers,
            'load_results': load_results,
        }

    def print_summary(self, data: dict):
        """Print a summary of the created data."""
        org = data['organization']
        load_results = data['load_results']
        num_weeks = self.offset + 1
        total_stops = sum(len(r['stops']) for r in load_results)

        print("\n" + "=" * 50)
        print("  Dev Environment Data Summary")
        print("=" * 50)
        print(f"  Organization : {org.company_name}")
        print(f"  User         : {data['user'].email}")
        print(f"  Addresses    : {len(data['addresses'])}")
        print(f"  Carriers     : {len(data['carriers'])}")
        print(f"  Drivers      : {len(data['drivers'])}")
        print(f"  Customers    : {len(data['customers'])}")
        print(f"  Loads        : {len(load_results)}")
        print(f"  Stops        : {total_stops}")
        print(f"  Weeks        : {num_weeks} (offset={self.offset})")
        print(f"  Stops/Load   : {self.stops_per_load}")
        print("=" * 50)
        print()
