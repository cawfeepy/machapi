"""
Test suite for the Load Dashboard / Calendar endpoints.

This module tests:
1. calendar_day action - Returns loads for a specific day (primary endpoint)
2. calendar_week action - Returns loads grouped by day for a week (secondary endpoint)

Both endpoints filter by pickup stops and sort with unassigned legs first.

Module Structure:
  │
  ├── CalendarTestHelpers (class)
  │   ├── get_week_sunday()           - Calculate week's Sunday
  │   ├── create_test_organization()  - Create test org
  │   ├── create_test_user()          - Create user + profile
  │   ├── create_load_with_pickup()   - Create load with pickup/delivery stops
  │   ├── create_multi_day_load()     - Create load with multiple pickup stops
  │   └── make_datetime_for_date()    - Create timezone-aware datetime
  │
  ├── CalendarDayEndpointTests (APITestCase) - 16 tests
  │   ├── Response structure tests (5)
  │   ├── Load filtering tests (2)
  │   ├── Sorting tests (2)
  │   ├── Summary stats tests (2)
  │   ├── Serializer data tests (2)
  │   └── Edge cases (3)
  │
  └── CalendarWeekEndpointTests (APITestCase) - 20 tests
      ├── Response structure tests (4)
      ├── Load grouping by day tests (3)
      ├── Sorting tests (2)
      ├── Week parameter tests (3)
      ├── Serializer data tests (3)
      ├── Summary stats tests (2)
      └── Edge cases (3)
"""
from datetime import datetime, timedelta
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.loads.models import Load, LoadStatus
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.backend.routes.models import Stop
from machtms.core.factories.loads import LoadFactory
from machtms.core.factories.leg import LegFactory
from machtms.core.factories.routes import StopFactory
from machtms.core.factories.addresses import AddressFactory
from machtms.core.factories.customer import CustomerFactory
from machtms.core.factories.carrier import CarrierFactory, DriverFactory


# ============================================================================
# TEST HELPERS
# ============================================================================

class CalendarTestHelpers:
    """
    Shared helper methods for calendar endpoint tests.

    This class provides reusable methods for creating test data and
    calculating date boundaries used across calendar test classes.
    """

    @staticmethod
    def get_week_sunday(date: datetime) -> datetime:
        """Get the Sunday of the week containing the given date."""
        days_since_sunday = (date.weekday() + 1) % 7
        sunday = date - timedelta(days=days_since_sunday)
        return timezone.make_aware(datetime.combine(sunday.date(), datetime.min.time()))

    @staticmethod
    def create_test_organization(name: str = "Test Org") -> Organization:
        """Create a test organization."""
        return Organization.objects.create(
            company_name=name,
            phone="555-123-4567",
            email=f"{name.lower().replace(' ', '')}@testorg.com"
        )

    @staticmethod
    def create_test_user(email: str, organization: Organization) -> tuple:
        """
        Create a test user with profile.

        Returns:
            Tuple of (OrganizationUser, UserProfile)
        """
        user = OrganizationUser.objects.create_user(
            email=email,
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        profile = UserProfile.objects.create(
            user=user,
            organization=organization
        )
        return user, profile

    @staticmethod
    def create_load_with_pickup(
        pickup_datetime: datetime,
        customer,
        address,
        carrier=None,
        driver=None,
        assigned: bool = True
    ) -> Load:
        """
        Create a load with a pickup stop at the specified datetime.

        Args:
            pickup_datetime: The datetime for the pickup stop
            customer: Customer instance to associate with the load
            address: Address instance for stops
            carrier: Carrier instance (required if assigned=True)
            driver: Driver instance (required if assigned=True)
            assigned: Whether to create a ShipmentAssignment for the leg

        Returns:
            The created Load instance
        """
        load = LoadFactory.create(customer=customer, status=LoadStatus.PENDING)
        leg = LegFactory.create(load=load)

        # Create pickup stop (LL = Live Load)
        StopFactory.create(
            leg=leg,
            stop_number=1,
            action='LL',
            address=address,
            start_range=pickup_datetime,
            end_range=pickup_datetime + timedelta(hours=2),
        )

        # Create delivery stop (LU = Live Unload)
        StopFactory.create(
            leg=leg,
            stop_number=2,
            action='LU',
            address=address,
            start_range=pickup_datetime + timedelta(hours=6),
            end_range=pickup_datetime + timedelta(hours=8),
        )

        if assigned and carrier and driver:
            ShipmentAssignment.objects.create(
                leg=leg,
                carrier=carrier,
                driver=driver,
            )

        return load

    @staticmethod
    def create_multi_day_load(
        pickup_datetimes: list,
        customer,
        address,
        carrier=None,
        driver=None,
        assigned: bool = True
    ) -> Load:
        """
        Create a load with multiple pickup stops on different days.

        Args:
            pickup_datetimes: List of datetimes for pickup stops
            customer: Customer instance
            address: Address instance for stops
            carrier: Carrier instance (required if assigned=True)
            driver: Driver instance (required if assigned=True)
            assigned: Whether to create a ShipmentAssignment

        Returns:
            The created Load instance
        """
        load = LoadFactory.create(customer=customer, status=LoadStatus.PENDING)
        leg = LegFactory.create(load=load)

        for idx, pickup_dt in enumerate(pickup_datetimes):
            action = 'LL' if idx % 2 == 0 else 'HL'
            StopFactory.create(
                leg=leg,
                stop_number=idx + 1,
                action=action,
                address=address,
                start_range=pickup_dt,
                end_range=pickup_dt + timedelta(hours=2),
            )

        # Add final delivery stop
        last_pickup = pickup_datetimes[-1]
        StopFactory.create(
            leg=leg,
            stop_number=len(pickup_datetimes) + 1,
            action='LU',
            address=address,
            start_range=last_pickup + timedelta(hours=6),
            end_range=last_pickup + timedelta(hours=8),
        )

        if assigned and carrier and driver:
            ShipmentAssignment.objects.create(
                leg=leg,
                carrier=carrier,
                driver=driver,
            )

        return load

    @staticmethod
    def make_datetime_for_date(date, hours: int = 9) -> datetime:
        """
        Create a timezone-aware datetime for the given date at specified hour.

        Args:
            date: A date object
            hours: Hour of day (default 9am)

        Returns:
            Timezone-aware datetime
        """
        return timezone.make_aware(
            datetime.combine(date, datetime.min.time())
        ) + timedelta(hours=hours)


# ============================================================================
# CALENDAR DAY ENDPOINT TESTS
# ============================================================================

@override_settings(DEBUG=True)
class CalendarDayEndpointTests(APITestCase):
    """
    Tests for the /loads/calendar-day/ endpoint.

    This is the primary endpoint for displaying loads when a user clicks
    on a specific day in the calendar.
    """

    helpers = CalendarTestHelpers

    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all test methods."""
        cls.organization = cls.helpers.create_test_organization("Day Test Org")
        cls.user, cls.user_profile = cls.helpers.create_test_user(
            "day_testuser@example.com",
            cls.organization
        )
        cls.customer = CustomerFactory.create()
        cls.address = AddressFactory.create()
        cls.carrier = CarrierFactory.create()
        cls.driver = DriverFactory.create(carrier=cls.carrier)

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.client.force_authenticate(user=self.user)
        self.test_date = timezone.now().date() + timedelta(days=1)

    def _create_load(self, pickup_datetime: datetime, assigned: bool = True) -> Load:
        """Shortcut to create a load with pickup."""
        return self.helpers.create_load_with_pickup(
            pickup_datetime=pickup_datetime,
            customer=self.customer,
            address=self.address,
            carrier=self.carrier if assigned else None,
            driver=self.driver if assigned else None,
            assigned=assigned
        )

    # ==================== RESPONSE STRUCTURE TESTS ====================

    def test_returns_200(self):
        """Test that GET /loads/calendar-day/ returns HTTP 200."""
        url = reverse('load-calendar-day')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required top-level fields."""
        url = reverse('load-calendar-day')
        response = self.client.get(url)

        required_fields = ['date', 'day_name', 'total_loads', 'unassigned_count', 'loads']
        for field in required_fields:
            self.assertIn(field, response.data)

    def test_loads_is_array(self):
        """Test that response.loads is an array."""
        url = reverse('load-calendar-day')
        response = self.client.get(url)
        self.assertIsInstance(response.data['loads'], list)

    def test_day_name_matches_date(self):
        """Test that day_name matches the date provided."""
        date_str = self.test_date.isoformat()
        expected_day_name = self.test_date.strftime('%A').lower()

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': date_str})

        self.assertEqual(response.data['day_name'], expected_day_name)

    def test_empty_day_returns_empty_loads_array(self):
        """Test that a day with no loads returns an empty loads array."""
        future_date = (timezone.now() + timedelta(days=365)).date()

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': future_date.isoformat()})

        self.assertEqual(response.data['total_loads'], 0)
        self.assertEqual(response.data['unassigned_count'], 0)
        self.assertEqual(response.data['loads'], [])

    # ==================== LOAD FILTERING TESTS ====================

    def test_only_loads_for_specified_date_returned(self):
        """Test that only loads with pickups on the specified date are returned."""
        test_datetime = self.helpers.make_datetime_for_date(self.test_date)
        load_today = self._create_load(test_datetime, assigned=True)

        other_datetime = test_datetime + timedelta(days=2)
        load_other = self._create_load(other_datetime, assigned=True)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        load_ids = [l['id'] for l in response.data['loads']]
        self.assertIn(load_today.pk, load_ids)
        self.assertNotIn(load_other.pk, load_ids)

    def test_date_parameter_filters_correctly(self):
        """Test that the date parameter correctly filters loads."""
        date1 = self.test_date
        date2 = self.test_date + timedelta(days=1)

        load1 = self._create_load(self.helpers.make_datetime_for_date(date1), assigned=True)
        load2 = self._create_load(self.helpers.make_datetime_for_date(date2), assigned=True)

        url = reverse('load-calendar-day')

        # Query for date1
        response = self.client.get(url, {'date': date1.isoformat()})
        load_ids = [l['id'] for l in response.data['loads']]
        self.assertIn(load1.pk, load_ids)
        self.assertNotIn(load2.pk, load_ids)

        # Query for date2
        response = self.client.get(url, {'date': date2.isoformat()})
        load_ids = [l['id'] for l in response.data['loads']]
        self.assertIn(load2.pk, load_ids)
        self.assertNotIn(load1.pk, load_ids)

    # ==================== SORTING TESTS ====================

    def test_unassigned_loads_appear_first(self):
        """Test that loads with unassigned legs appear before assigned loads."""
        base_datetime = self.helpers.make_datetime_for_date(self.test_date, hours=0)

        assigned_load = self._create_load(base_datetime + timedelta(hours=6), assigned=True)
        unassigned_load = self._create_load(base_datetime + timedelta(hours=14), assigned=False)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        load_ids = [l['id'] for l in response.data['loads']]
        self.assertLess(
            load_ids.index(unassigned_load.pk),
            load_ids.index(assigned_load.pk),
            "Unassigned load should appear before assigned load"
        )

    def test_assigned_loads_sorted_by_pickup_time(self):
        """Test that assigned loads are sorted by pickup time (earliest first)."""
        base_datetime = self.helpers.make_datetime_for_date(self.test_date, hours=0)

        load_late = self._create_load(base_datetime + timedelta(hours=16), assigned=True)
        load_early = self._create_load(base_datetime + timedelta(hours=6), assigned=True)
        load_mid = self._create_load(base_datetime + timedelta(hours=10), assigned=True)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        load_ids = [l['id'] for l in response.data['loads']]
        self.assertLess(load_ids.index(load_early.pk), load_ids.index(load_mid.pk))
        self.assertLess(load_ids.index(load_mid.pk), load_ids.index(load_late.pk))

    # ==================== SUMMARY STATS TESTS ====================

    def test_total_loads_count_is_correct(self):
        """Test that total_loads matches number of loads returned."""
        base_datetime = self.helpers.make_datetime_for_date(self.test_date)

        self._create_load(base_datetime, assigned=True)
        self._create_load(base_datetime + timedelta(hours=2), assigned=True)
        self._create_load(base_datetime + timedelta(hours=4), assigned=False)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        self.assertEqual(response.data['total_loads'], 3)
        self.assertEqual(len(response.data['loads']), 3)

    def test_unassigned_count_is_correct(self):
        """Test that unassigned_count matches loads with unassigned legs."""
        base_datetime = self.helpers.make_datetime_for_date(self.test_date)

        self._create_load(base_datetime, assigned=True)
        self._create_load(base_datetime + timedelta(hours=2), assigned=False)
        self._create_load(base_datetime + timedelta(hours=4), assigned=False)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        self.assertEqual(response.data['unassigned_count'], 2)

    # ==================== SERIALIZER DATA TESTS ====================

    def test_load_data_includes_required_fields(self):
        """Test that each load includes required fields."""
        self._create_load(self.helpers.make_datetime_for_date(self.test_date), assigned=True)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        load_data = response.data['loads'][0]
        required_fields = ['id', 'reference_number', 'status', 'has_unassigned_leg',
                           'first_pickup_time', 'legs', 'customer']
        for field in required_fields:
            self.assertIn(field, load_data)

    def test_leg_includes_assignment_info(self):
        """Test that leg data includes assignment information."""
        self._create_load(self.helpers.make_datetime_for_date(self.test_date), assigned=True)

        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': self.test_date.isoformat()})

        leg_data = response.data['loads'][0]['legs'][0]
        self.assertIn('is_assigned', leg_data)
        self.assertIn('shipment_assignments', leg_data)
        self.assertIn('stops', leg_data)
        self.assertTrue(leg_data['is_assigned'])

    # ==================== EDGE CASES ====================

    def test_invalid_date_falls_back_to_today(self):
        """Test that an invalid date format falls back to today."""
        url = reverse('load-calendar-day')
        response = self.client.get(url, {'date': 'not-a-valid-date'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('date', response.data)

    def test_no_date_parameter_defaults_to_today(self):
        """Test that omitting date parameter defaults to today."""
        url = reverse('load-calendar-day')
        response = self.client.get(url)

        today = timezone.now().date().isoformat()
        self.assertEqual(response.data['date'], today)

    def test_unauthenticated_request_rejected(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)

        url = reverse('load-calendar-day')
        response = self.client.get(url)

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


# ============================================================================
# CALENDAR WEEK ENDPOINT TESTS
# ============================================================================

@override_settings(DEBUG=True)
class CalendarWeekEndpointTests(APITestCase):
    """
    Tests for the /loads/calendar-week/ endpoint.

    This endpoint returns loads grouped by day for a Sunday-Saturday week.
    """

    helpers = CalendarTestHelpers

    @classmethod
    def setUpTestData(cls):
        """Set up test data shared across all test methods."""
        cls.organization = cls.helpers.create_test_organization("Week Test Org")
        cls.user, cls.user_profile = cls.helpers.create_test_user(
            "week_testuser@example.com",
            cls.organization
        )
        cls.customer = CustomerFactory.create()
        cls.address = AddressFactory.create()
        cls.carrier = CarrierFactory.create()
        cls.driver = DriverFactory.create(carrier=cls.carrier)

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.client.force_authenticate(user=self.user)
        self.week_start = self.helpers.get_week_sunday(timezone.now())

    def _create_load(self, pickup_datetime: datetime, assigned: bool = True) -> Load:
        """Shortcut to create a load with pickup."""
        return self.helpers.create_load_with_pickup(
            pickup_datetime=pickup_datetime,
            customer=self.customer,
            address=self.address,
            carrier=self.carrier if assigned else None,
            driver=self.driver if assigned else None,
            assigned=assigned
        )

    def _create_multi_day_load(self, pickup_datetimes: list, assigned: bool = True) -> Load:
        """Shortcut to create a multi-day load."""
        return self.helpers.create_multi_day_load(
            pickup_datetimes=pickup_datetimes,
            customer=self.customer,
            address=self.address,
            carrier=self.carrier if assigned else None,
            driver=self.driver if assigned else None,
            assigned=assigned
        )

    # ==================== RESPONSE STRUCTURE TESTS ====================

    def test_returns_200(self):
        """Test that GET /loads/calendar-week/ returns HTTP 200."""
        url = reverse('load-calendar-week')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required top-level fields."""
        url = reverse('load-calendar-week')
        response = self.client.get(url)

        required_fields = ['week_start', 'week_end', 'days', 'total_loads', 'unassigned_count']
        for field in required_fields:
            self.assertIn(field, response.data)

    def test_response_days_contains_all_weekdays(self):
        """Test that response.days contains all 7 day keys."""
        url = reverse('load-calendar-week')
        response = self.client.get(url)

        expected_days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        for day in expected_days:
            self.assertIn(day, response.data['days'])

    def test_empty_week_returns_empty_day_arrays(self):
        """Test that a week with no loads returns empty arrays for each day."""
        future_sunday = self.week_start + timedelta(days=365)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': future_sunday.date().isoformat()})

        self.assertEqual(response.data['total_loads'], 0)
        for day_name in ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']:
            self.assertEqual(response.data['days'][day_name], [])

    # ==================== LOAD GROUPING BY DAY TESTS ====================

    def test_load_appears_in_correct_day(self):
        """Test that a load with a Monday pickup appears in monday array."""
        monday_pickup = self.week_start + timedelta(days=1, hours=9)
        load = self._create_load(monday_pickup, assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        monday_ids = [l['id'] for l in response.data['days']['monday']]
        self.assertIn(load.pk, monday_ids)

        # Verify not in other days
        for day in ['sunday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']:
            day_ids = [l['id'] for l in response.data['days'][day]]
            self.assertNotIn(load.pk, day_ids)

    def test_multiple_loads_grouped_by_their_pickup_days(self):
        """Test that loads with different pickup days appear in correct arrays."""
        load_tuesday = self._create_load(self.week_start + timedelta(days=2, hours=8), assigned=True)
        load_friday = self._create_load(self.week_start + timedelta(days=5, hours=14), assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        tuesday_ids = [l['id'] for l in response.data['days']['tuesday']]
        friday_ids = [l['id'] for l in response.data['days']['friday']]

        self.assertIn(load_tuesday.pk, tuesday_ids)
        self.assertIn(load_friday.pk, friday_ids)

    def test_multi_day_load_appears_in_multiple_days(self):
        """Test that a load with pickups on multiple days appears in each day."""
        wednesday_pickup = self.week_start + timedelta(days=3, hours=8)
        thursday_pickup = self.week_start + timedelta(days=4, hours=10)

        load = self._create_multi_day_load([wednesday_pickup, thursday_pickup], assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        wednesday_ids = [l['id'] for l in response.data['days']['wednesday']]
        thursday_ids = [l['id'] for l in response.data['days']['thursday']]

        self.assertIn(load.pk, wednesday_ids)
        self.assertIn(load.pk, thursday_ids)

    # ==================== SORTING TESTS ====================

    def test_unassigned_loads_appear_first(self):
        """Test that loads with unassigned legs appear before assigned loads."""
        monday_early = self.week_start + timedelta(days=1, hours=6)
        monday_late = self.week_start + timedelta(days=1, hours=14)

        assigned_load = self._create_load(monday_early, assigned=True)
        unassigned_load = self._create_load(monday_late, assigned=False)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        monday_ids = [l['id'] for l in response.data['days']['monday']]
        self.assertLess(
            monday_ids.index(unassigned_load.pk),
            monday_ids.index(assigned_load.pk),
            "Unassigned load should appear before assigned load"
        )

    def test_assigned_loads_sorted_by_pickup_time(self):
        """Test that assigned loads are sorted by pickup time (earliest first)."""
        monday_early = self.week_start + timedelta(days=1, hours=6)
        monday_mid = self.week_start + timedelta(days=1, hours=10)
        monday_late = self.week_start + timedelta(days=1, hours=16)

        load_late = self._create_load(monday_late, assigned=True)
        load_early = self._create_load(monday_early, assigned=True)
        load_mid = self._create_load(monday_mid, assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        monday_ids = [l['id'] for l in response.data['days']['monday']]
        self.assertLess(monday_ids.index(load_early.pk), monday_ids.index(load_mid.pk))
        self.assertLess(monday_ids.index(load_mid.pk), monday_ids.index(load_late.pk))

    # ==================== WEEK PARAMETER TESTS ====================

    def test_week_start_parameter_filters_to_specific_week(self):
        """Test that week_start parameter returns loads for that specific week."""
        next_week_start = self.week_start + timedelta(days=7)
        next_monday = next_week_start + timedelta(days=1, hours=9)
        load = self._create_load(next_monday, assigned=True)

        url = reverse('load-calendar-week')

        # Query current week (load should NOT appear)
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})
        all_ids = []
        for day in response.data['days'].values():
            all_ids.extend([l['id'] for l in day])
        self.assertNotIn(load.pk, all_ids)

        # Query next week (load SHOULD appear)
        response = self.client.get(url, {'week_start': next_week_start.date().isoformat()})
        monday_ids = [l['id'] for l in response.data['days']['monday']]
        self.assertIn(load.pk, monday_ids)

    def test_invalid_week_start_falls_back_to_current_week(self):
        """Test that an invalid date format falls back to current week."""
        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': 'not-a-date'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('week_start', response.data)

    def test_week_end_is_saturday(self):
        """Test that week_end is the Saturday of the specified week."""
        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        expected_end = (self.week_start + timedelta(days=6)).date().isoformat()
        self.assertEqual(response.data['week_end'], expected_end)

    # ==================== SERIALIZER DATA TESTS ====================

    def test_load_data_includes_required_fields(self):
        """Test that each load in response includes required fields."""
        monday_pickup = self.week_start + timedelta(days=1, hours=9)
        self._create_load(monday_pickup, assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        load_data = response.data['days']['monday'][0]
        required_fields = ['id', 'reference_number', 'status', 'has_unassigned_leg',
                           'first_pickup_time', 'legs', 'customer']
        for field in required_fields:
            self.assertIn(field, load_data)

    def test_leg_data_includes_is_assigned_and_stops(self):
        """Test that leg data includes is_assigned flag and stops array."""
        monday_pickup = self.week_start + timedelta(days=1, hours=9)
        self._create_load(monday_pickup, assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        leg_data = response.data['days']['monday'][0]['legs'][0]
        self.assertIn('is_assigned', leg_data)
        self.assertIn('stops', leg_data)
        self.assertIn('shipment_assignments', leg_data)

    def test_assigned_leg_has_shipment_assignment_data(self):
        """Test that assigned leg includes carrier and driver info."""
        monday_pickup = self.week_start + timedelta(days=1, hours=9)
        self._create_load(monday_pickup, assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        leg_data = response.data['days']['monday'][0]['legs'][0]
        self.assertTrue(leg_data['is_assigned'])
        self.assertGreater(len(leg_data['shipment_assignments']), 0)

        assignment = leg_data['shipment_assignments'][0]
        self.assertIn('carrier', assignment)
        self.assertIn('driver', assignment)

    # ==================== SUMMARY STATS TESTS ====================

    def test_total_loads_count_is_correct(self):
        """Test that total_loads matches number of unique loads."""
        self._create_load(self.week_start + timedelta(days=1, hours=9), assigned=True)
        self._create_load(self.week_start + timedelta(days=2, hours=9), assigned=True)
        self._create_load(self.week_start + timedelta(days=3, hours=9), assigned=False)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        self.assertEqual(response.data['total_loads'], 3)

    def test_unassigned_count_is_correct(self):
        """Test that unassigned_count matches loads with unassigned legs."""
        self._create_load(self.week_start + timedelta(days=1, hours=9), assigned=True)
        self._create_load(self.week_start + timedelta(days=2, hours=9), assigned=False)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        self.assertEqual(response.data['unassigned_count'], 1)

    # ==================== EDGE CASES ====================

    def test_unauthenticated_request_rejected(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)

        url = reverse('load-calendar-week')
        response = self.client.get(url)

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_load_outside_week_range_not_included(self):
        """Test that loads with pickups outside the week are not included."""
        before_week = self.week_start - timedelta(days=3)
        load = self._create_load(before_week, assigned=True)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        all_ids = []
        for day in response.data['days'].values():
            all_ids.extend([l['id'] for l in day])

        self.assertNotIn(load.pk, all_ids)

    def test_delivery_stop_does_not_place_load_in_day(self):
        """Test that only pickup actions place load in day, not delivery."""
        # Create load with pickup on Sunday, delivery on Wednesday
        sunday_pickup = self.week_start + timedelta(hours=9)
        load = LoadFactory.create(customer=self.customer, status=LoadStatus.PENDING)
        leg = LegFactory.create(load=load)

        # Pickup on Sunday
        StopFactory.create(
            leg=leg, stop_number=1, action='LL', address=self.address,
            start_range=sunday_pickup, end_range=sunday_pickup + timedelta(hours=2)
        )

        # Delivery on Wednesday (LU = not a pickup action)
        wednesday_delivery = self.week_start + timedelta(days=3, hours=14)
        StopFactory.create(
            leg=leg, stop_number=2, action='LU', address=self.address,
            start_range=wednesday_delivery, end_range=wednesday_delivery + timedelta(hours=2)
        )

        ShipmentAssignment.objects.create(leg=leg, carrier=self.carrier, driver=self.driver)

        url = reverse('load-calendar-week')
        response = self.client.get(url, {'week_start': self.week_start.date().isoformat()})

        sunday_ids = [l['id'] for l in response.data['days']['sunday']]
        wednesday_ids = [l['id'] for l in response.data['days']['wednesday']]

        self.assertIn(load.pk, sunday_ids)
        self.assertNotIn(load.pk, wednesday_ids)
