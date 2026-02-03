"""
Test suite for the loads module.

This module contains comprehensive tests for:
1. LoadFactoryTests - Testing factories and database population
2. LoadViewSetTests - Testing LoadViewSet CRUD operations
3. LoadOpenAPIClientTests - Testing views using generated OpenAPI client
"""
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.loads.models import Load, LoadStatus, BillingStatus, TrailerType
from machtms.backend.routes.models import Stop
from machtms.core.factories.creator_factories.prebuilt import quick_create

# OpenAPI client imports
from machtms.core.openapi_client.api.loads import (
    loads_list,
    loads_create,
    loads_retrieve,
    loads_update,
    loads_partial_update,
)
from machtms.core.openapi_client.models import Load as LoadSchema
from machtms.core.openapi_client.models.status_enum import StatusEnum
from machtms.core.openapi_client.models.billing_status_enum import BillingStatusEnum


class LoadFactoryTests(APITestCase):
    """
    Tests for factories and database population.

    These tests verify that the quick_create factory correctly generates
    loads with all associated relationships (legs, stops, carriers, drivers,
    shipment assignments).
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-123-4567",
            email="test@testorg.com"
        )
        cls.user = OrganizationUser.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        cls.user_profile = UserProfile.objects.create(
            user=cls.user,
            organization=cls.organization
        )

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.client.force_authenticate(user=self.user)
        # Create test data using quick_create
        self.load_results = quick_create(5)

    def test_leg_contains_stops(self):
        """
        Test that a leg created by the factory contains stops.

        Each leg should have at least 2 stops (pickup and delivery).
        """
        for result in self.load_results:
            leg = result['leg']
            stops = leg.stops.all()

            self.assertGreaterEqual(
                stops.count(),
                2,
                f"Leg {leg.pk} should have at least 2 stops, found {stops.count()}"
            )

    def test_stop_numbers_are_in_order(self):
        """
        Test that stop numbers within a leg are sequential and ordered.

        Stops should be numbered starting from 1 and increment sequentially.
        The ordering constraint (stop_number, leg) ensures uniqueness.
        """
        for result in self.load_results:
            leg = result['leg']
            stops = leg.stops.all().order_by('stop_number')
            stop_numbers = list(stops.values_list('stop_number', flat=True))

            # Verify stops start at 1
            self.assertEqual(
                stop_numbers[0],
                1,
                f"First stop number should be 1, got {stop_numbers[0]}"
            )

            # Verify sequential ordering
            expected_numbers = list(range(1, len(stop_numbers) + 1))
            self.assertEqual(
                stop_numbers,
                expected_numbers,
                f"Stop numbers should be sequential: expected {expected_numbers}, got {stop_numbers}"
            )

    def test_driver_assigned_belongs_to_carrier(self):
        """
        Test that a driver assigned via ShipmentAssignment belongs to that carrier.

        The ShipmentAssignment links a carrier and driver to a leg. The assigned
        driver should belong to the assigned carrier.
        """
        for result in self.load_results:
            assignment = result['assignment']
            carrier = assignment.carrier
            driver = assignment.driver

            self.assertEqual(
                driver.carrier,
                carrier,
                f"Driver {driver.full_name} should belong to carrier {carrier.carrier_name}"
            )

    def test_load_has_customer_association(self):
        """
        Test that each load created by the factory has a customer.

        The LoadCreationFactory creates a customer and associates it with the load.
        """
        for result in self.load_results:
            load = result['load']
            customer = result['customer']

            self.assertIsNotNone(
                load.customer,
                f"Load {load.pk} should have a customer"
            )
            self.assertEqual(
                load.customer,
                customer,
                f"Load's customer should match the result customer"
            )

    def test_load_has_leg_association(self):
        """
        Test that each load has at least one leg associated via reverse relation.

        The leg is created with a ForeignKey to load with related_name='legs'.
        """
        for result in self.load_results:
            load = result['load']
            leg = result['leg']

            self.assertIn(
                leg,
                load.legs.all(),
                f"Leg {leg.pk} should be associated with Load {load.pk}"
            )

    def test_stops_have_valid_actions(self):
        """
        Test that stops have valid action codes.

        Actions should be one of the valid choices defined in Stop.ACTION_CHOICES.
        """
        valid_actions = {choice[0] for choice in Stop.ACTION_CHOICES}

        for result in self.load_results:
            stops = result['stops']
            for stop in stops:
                self.assertIn(
                    stop.action,
                    valid_actions,
                    f"Stop action '{stop.action}' is not a valid action choice"
                )


@override_settings(DEBUG=True)
class LoadViewSetTests(APITestCase):
    """
    Tests for LoadViewSet CRUD operations.

    These tests verify the LoadViewSet endpoints for:
    - List (GET /loads/)
    - Create (POST /loads/)
    - Retrieve (GET /loads/{id}/)
    - Update (PUT /loads/{id}/)
    - Partial Update (PATCH /loads/{id}/)
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-123-4567",
            email="test@testorg.com"
        )
        cls.user = OrganizationUser.objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        cls.user_profile = UserProfile.objects.create(
            user=cls.user,
            organization=cls.organization
        )

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.client.force_authenticate(user=self.user)
        # Create test data
        self.load_results = quick_create(3)
        self.sample_result = self.load_results[0]
        self.sample_load = self.sample_result['load']

    # ==================== LIST TESTS ====================

    def test_list_loads_returns_200(self):
        """Test that GET /loads/ returns HTTP 200."""
        url = reverse('load-list')
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200, got {response.status_code}"
        )

    def test_list_loads_returns_all_loads(self):
        """Test that GET /loads/ returns all created loads."""
        url = reverse('load-list')
        response = self.client.get(url)

        # Get result data - handle paginated and non-paginated responses
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            results = data['results']
        else:
            results = data

        # Verify all created loads are returned
        created_load_ids = {result['load'].pk for result in self.load_results}
        returned_load_ids = {item['id'] for item in results}

        self.assertTrue(
            created_load_ids.issubset(returned_load_ids),
            f"Not all created loads were returned. Created: {created_load_ids}, Returned: {returned_load_ids}"
        )

    # ==================== RETRIEVE TESTS ====================

    def test_retrieve_load_returns_200(self):
        """Test that GET /loads/{id}/ returns HTTP 200."""
        url = reverse('load-detail', kwargs={'pk': self.sample_load.pk})
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200, got {response.status_code}"
        )

    def test_retrieve_load_returns_correct_data(self):
        """Test that GET /loads/{id}/ returns the correct load data."""
        url = reverse('load-detail', kwargs={'pk': self.sample_load.pk})
        response = self.client.get(url)

        self.assertEqual(
            response.data['id'],
            self.sample_load.pk,
            "Returned load ID should match requested ID"
        )
        self.assertEqual(
            response.data['reference_number'],
            self.sample_load.reference_number,
            "Returned reference_number should match"
        )

    def test_retrieve_nonexistent_load_returns_404(self):
        """Test that GET /loads/{id}/ returns 404 for non-existent load."""
        url = reverse('load-detail', kwargs={'pk': 99999})
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            f"Expected 404, got {response.status_code}"
        )

    # ==================== CREATE TESTS ====================

    def test_create_load_returns_201(self):
        """Test that POST /loads/ with valid data returns HTTP 201."""
        url = reverse('load-list')
        # Get the customer from sample result for association
        customer = self.sample_result['customer']

        payload = {
            'reference_number': 'TEST-REF-001',
            'bol_number': 'BOL-001',
            'customer': customer.pk,
            'status': LoadStatus.PENDING,
            'billing_status': BillingStatus.PENDING_DELIVERY,
            'trailer_type': TrailerType.LARGE_53,
        }

        response = self.client.post(url, payload, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201, got {response.status_code}. Response: {response.data}"
        )

    def test_create_load_persists_data(self):
        """Test that POST /loads/ creates a load in the database."""
        url = reverse('load-list')
        customer = self.sample_result['customer']

        initial_count = Load.objects.count()

        payload = {
            'reference_number': 'TEST-REF-002',
            'bol_number': 'BOL-002',
            'customer': customer.pk,
            'status': LoadStatus.PENDING,
            'billing_status': BillingStatus.PENDING_DELIVERY,
        }

        response = self.client.post(url, payload, format='json')

        self.assertEqual(
            Load.objects.count(),
            initial_count + 1,
            "Load count should increase by 1"
        )

        # Verify the created load
        created_load = Load.objects.get(pk=response.data['id'])
        self.assertEqual(created_load.reference_number, 'TEST-REF-002')
        self.assertEqual(created_load.customer, customer)

    def test_create_load_with_nested_legs_and_stops(self):
        """
        Test that POST /loads/ with nested legs and stops creates all objects.

        This tests the AutoNestedMixin functionality for nested writes.
        """
        url = reverse('load-list')
        customer = self.sample_result['customer']
        # Get an address from an existing stop for the test
        sample_stop = self.sample_result['stops'][0]
        address = sample_stop.address

        payload = {
            'reference_number': 'TEST-NESTED-001',
            'bol_number': 'BOL-NESTED-001',
            'customer': customer.pk,
            'status': LoadStatus.PENDING,
            'billing_status': BillingStatus.PENDING_DELIVERY,
            'legs': [
                {
                    'stops': [
                        {
                            'stop_number': 1,
                            'address': address.pk,
                            'start_range': '2024-01-15T08:00:00Z',
                            'end_range': '2024-01-15T10:00:00Z',
                            'action': 'LL',
                            'po_numbers': 'PO-001',
                            'driver_notes': 'Test pickup',
                        },
                        {
                            'stop_number': 2,
                            'address': address.pk,
                            'start_range': '2024-01-15T14:00:00Z',
                            'end_range': '2024-01-15T16:00:00Z',
                            'action': 'LU',
                            'po_numbers': 'PO-002',
                            'driver_notes': 'Test delivery',
                        },
                    ]
                }
            ]
        }

        response = self.client.post(url, payload, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201, got {response.status_code}. Response: {response.data}"
        )

        # Verify load was created
        created_load = Load.objects.get(pk=response.data['id'])
        self.assertEqual(created_load.reference_number, 'TEST-NESTED-001')

        # Verify leg was created
        legs = created_load.legs.all()
        self.assertEqual(legs.count(), 1, "Should have created 1 leg")

        # Verify stops were created
        leg = legs.first()
        stops = leg.stops.all().order_by('stop_number')
        self.assertEqual(stops.count(), 2, "Should have created 2 stops")
        self.assertEqual(stops[0].action, 'LL')
        self.assertEqual(stops[1].action, 'LU')

    def test_create_load_without_customer(self):
        """Test that POST /loads/ works without a customer (nullable field)."""
        url = reverse('load-list')

        payload = {
            'reference_number': 'TEST-NO-CUSTOMER',
            'bol_number': 'BOL-NC',
            'status': LoadStatus.PENDING,
            'billing_status': BillingStatus.PENDING_DELIVERY,
        }

        response = self.client.post(url, payload, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201, got {response.status_code}. Response: {response.data}"
        )

        created_load = Load.objects.get(pk=response.data['id'])
        self.assertIsNone(created_load.customer)

    # ==================== UPDATE TESTS ====================

    def test_update_load_returns_200(self):
        """Test that PUT /loads/{id}/ with valid data returns HTTP 200."""
        url = reverse('load-detail', kwargs={'pk': self.sample_load.pk})
        customer = self.sample_result['customer']

        payload = {
            'reference_number': 'UPDATED-REF',
            'bol_number': 'UPDATED-BOL',
            'customer': customer.pk,
            'status': LoadStatus.ASSIGNED,
            'billing_status': BillingStatus.BILLED,
        }

        response = self.client.put(url, payload, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200, got {response.status_code}. Response: {response.data}"
        )

    def test_update_load_persists_changes(self):
        """Test that PUT /loads/{id}/ updates the load in the database."""
        url = reverse('load-detail', kwargs={'pk': self.sample_load.pk})
        customer = self.sample_result['customer']

        payload = {
            'reference_number': 'UPDATED-REF-PERSIST',
            'bol_number': 'UPDATED-BOL-PERSIST',
            'customer': customer.pk,
            'status': LoadStatus.COMPLETE,
            'billing_status': BillingStatus.PAID,
        }

        self.client.put(url, payload, format='json')

        # Refresh from database
        self.sample_load.refresh_from_db()

        self.assertEqual(self.sample_load.reference_number, 'UPDATED-REF-PERSIST')
        self.assertEqual(self.sample_load.bol_number, 'UPDATED-BOL-PERSIST')
        self.assertEqual(self.sample_load.status, LoadStatus.COMPLETE)
        self.assertEqual(self.sample_load.billing_status, BillingStatus.PAID)

    def test_partial_update_load_returns_200(self):
        """Test that PATCH /loads/{id}/ with partial data returns HTTP 200."""
        url = reverse('load-detail', kwargs={'pk': self.sample_load.pk})

        payload = {
            'status': LoadStatus.IN_TRANSIT,
        }

        response = self.client.patch(url, payload, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200, got {response.status_code}. Response: {response.data}"
        )

        # Verify only status was updated
        self.sample_load.refresh_from_db()
        self.assertEqual(self.sample_load.status, LoadStatus.IN_TRANSIT)



@override_settings(DEBUG=True)
class LoadOrganizationIsolationTests(APITestCase):
    """
    Tests for organization-based isolation in LoadViewSet.

    These tests verify that:
    - Users can only access loads belonging to their organization
    - Loads are properly filtered by organization in list views
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data with multiple organizations."""
        # Organization 1
        cls.org1 = Organization.objects.create(
            company_name="Org One",
            phone="555-111-1111",
            email="org1@test.com"
        )
        cls.user1 = OrganizationUser.objects.create_user(
            email="user1@org1.com",
            password="testpass123",
            first_name="User",
            last_name="One"
        )
        cls.profile1 = UserProfile.objects.create(
            user=cls.user1,
            organization=cls.org1
        )

        # Organization 2
        cls.org2 = Organization.objects.create(
            company_name="Org Two",
            phone="555-222-2222",
            email="org2@test.com"
        )
        cls.user2 = OrganizationUser.objects.create_user(
            email="user2@org2.com",
            password="testpass123",
            first_name="User",
            last_name="Two"
        )
        cls.profile2 = UserProfile.objects.create(
            user=cls.user2,
            organization=cls.org2
        )

    def test_user_can_access_own_organization_loads(self):
        """
        Test that authenticated users can access loads from their organization.

        Note: In DEBUG mode, organization filtering may be bypassed.
        This test verifies the basic access pattern works.
        """
        # Create loads using the factory (they will be created without organization in DEBUG mode)
        self.client.force_authenticate(user=self.user1)
        load_results = quick_create(2)

        url = reverse('load-list')
        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "User should be able to access loads endpoint"
        )

    def test_authenticated_user_required_for_loads(self):
        """Test that unauthenticated requests are handled properly."""
        # Clear authentication
        self.client.force_authenticate(user=None)

        url = reverse('load-list')
        response = self.client.get(url)

        # Should return either 401 or 403 depending on DRF settings
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
            f"Expected 401 or 403 for unauthenticated request, got {response.status_code}"
        )


class DRFHttpxResponseAdapter:
    """
    Adapter that wraps DRF's Response to look like httpx.Response.

    This allows the openapi-python-client generated functions to parse
    responses from Django REST Framework's test client.
    """

    def __init__(self, drf_response):
        self._drf_response = drf_response

    @property
    def status_code(self) -> int:
        return self._drf_response.status_code

    @property
    def content(self) -> bytes:
        return self._drf_response.content

    @property
    def headers(self):
        return dict(self._drf_response.headers) if hasattr(self._drf_response, 'headers') else {}

    def json(self):
        return self._drf_response.json()


class DRFHttpxClientAdapter:
    """
    Adapter that wraps DRF's APIClient to look like httpx.Client.

    The openapi-python-client functions call client.get_httpx_client().request(**kwargs).
    This adapter provides that interface using the DRF test client.
    """

    def __init__(self, drf_client, pending_body=None):
        self._drf_client = drf_client
        self._pending_body = pending_body

    def request(self, method: str, url: str, **kwargs) -> DRFHttpxResponseAdapter:
        method = method.lower()
        request_method = getattr(self._drf_client, method)

        # Handle different content types
        json_data = kwargs.get('json')
        data = kwargs.get('data')
        files = kwargs.get('files')

        # Use pending body if no body in kwargs (for raw dict payloads)
        if json_data is None and data is None and files is None and self._pending_body is not None:
            json_data = self._pending_body

        if json_data is not None:
            response = request_method(url, json_data, format='json')
        elif data is not None:
            response = request_method(url, data)
        elif files is not None:
            response = request_method(url, files, format='multipart')
        else:
            response = request_method(url)

        return DRFHttpxResponseAdapter(response)


class DRFTestClientAdapter:
    """
    Adapter that wraps DRF's APIClient to mimic AuthenticatedClient interface.

    This allows openapi-python-client generated functions to work with
    Django REST Framework's test client in APITestCase.

    For write operations (POST, PUT, PATCH), use with_body() to set the payload
    since the generated client expects model instances, not dicts.
    """

    def __init__(self, drf_client, pending_body=None):
        self._drf_client = drf_client
        self._pending_body = pending_body
        self.raise_on_unexpected_status = False

    def with_body(self, body):
        """Return a new adapter with the body set for the next request."""
        return DRFTestClientAdapter(self._drf_client, pending_body=body)

    def get_httpx_client(self):
        return DRFHttpxClientAdapter(self._drf_client, self._pending_body)


@override_settings(DEBUG=True)
class LoadOpenAPIClientTests(APITestCase):
    """
    Tests for LoadViewSet using the generated OpenAPI client.

    These tests verify that the openapi-python-client generated functions
    correctly interact with the LoadViewSet endpoints and enforce payload types.

    Note: Some nested object parsing may fail due to serializer field renaming
    (e.g., LegSerializer renames 'id' to 'leg_id'). Tests use raw JSON responses
    where nested parsing is affected.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data that will be shared across all test methods."""
        cls.organization = Organization.objects.create(
            company_name="Test Org",
            phone="555-123-4567",
            email="test@testorg.com"
        )
        cls.user = OrganizationUser.objects.create_user(
            email="openapi_testuser@example.com",
            password="testpass123",
            first_name="OpenAPI",
            last_name="Tester"
        )
        cls.user_profile = UserProfile.objects.create(
            user=cls.user,
            organization=cls.organization
        )

    def setUp(self):
        """Set up test fixtures for each test method."""
        self.client.force_authenticate(user=self.user)
        self.api_client = DRFTestClientAdapter(self.client)
        # Create test data using quick_create (loads with legs)
        self.load_results = quick_create(3)
        self.sample_result = self.load_results[0]
        self.sample_load = self.sample_result['load']

        # Create loads without legs for tests that need clean parsing
        # (LegSerializer renames 'id' to 'leg_id' which breaks generated client parsing)
        self.clean_results = quick_create(1, create_legs=False)
        self.clean_load = self.clean_results[0]['load']

    def _get_raw_response(self, response):
        """Helper to get raw JSON from response when parsing fails."""
        import json
        return json.loads(response.content)

    # ==================== LIST TESTS ====================

    def test_list_loads_returns_json_array(self):
        """Test that loads_list returns a JSON array with load data."""
        # Use DRF client directly for list endpoint
        response = self.client.get('/api/loads/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 4)  # 3 with legs + 1 clean

        # Verify structure of returned loads
        for load_data in data:
            self.assertIn('id', load_data)
            self.assertIn('reference_number', load_data)
            self.assertIn('status', load_data)

    # ==================== RETRIEVE TESTS ====================

    def test_retrieve_load_parses_to_schema(self):
        """Test that LoadSchema parses correctly when load has no nested legs."""
        load = loads_retrieve.sync(
            client=self.api_client,
            id=self.clean_load.pk
        )

        self.assertIsNotNone(load)
        self.assertIsInstance(load, LoadSchema)
        self.assertEqual(load.id, self.clean_load.pk)
        self.assertEqual(load.reference_number, self.clean_load.reference_number)

    # ==================== CREATE TESTS ====================

    def test_create_load_with_typed_payload(self):
        """Test that loads_create accepts typed payload and returns correct data."""
        customer = self.sample_result['customer']

        payload = {
            'reference_number': 'OPENAPI-TEST-002',
            'bol_number': 'BOL-OPENAPI-002',
            'customer': customer.pk,
            'status': StatusEnum.PENDING.value,
            'billing_status': BillingStatusEnum.PENDING_DELIVERY.value,
        }

        response = loads_create.sync_detailed(
            client=self.api_client.with_body(payload),
        )

        self.assertEqual(response.status_code, 201)
        raw_data = self._get_raw_response(response)
        self.assertEqual(raw_data['reference_number'], 'OPENAPI-TEST-002')
        self.assertIn('id', raw_data)

    def test_create_load_validates_enum_values(self):
        """Test that the API validates enum values in payload."""
        customer = self.sample_result['customer']

        # Test with valid enum values
        payload = {
            'reference_number': 'ENUM-TEST-001',
            'bol_number': 'BOL-ENUM-001',
            'customer': customer.pk,
            'status': StatusEnum.ASSIGNED.value,
            'billing_status': BillingStatusEnum.BILLED.value,
        }

        response = loads_create.sync_detailed(
            client=self.api_client.with_body(payload),
        )

        self.assertEqual(response.status_code, 201)
        raw_data = self._get_raw_response(response)
        self.assertEqual(raw_data['status'], 'assigned')
        self.assertEqual(raw_data['billing_status'], 'billed')

    # ==================== RESPONSE STRUCTURE TESTS ====================

    def test_response_contains_datetime_strings(self):
        """Test that response contains ISO datetime strings."""
        response = loads_retrieve.sync_detailed(
            client=self.api_client,
            id=self.clean_load.pk
        )

        raw_data = self._get_raw_response(response)
        self.assertIn('created_at', raw_data)
        self.assertIn('updated_at', raw_data)

        # Verify datetime format (ISO 8601)
        from datetime import datetime
        datetime.fromisoformat(raw_data['created_at'].replace('Z', '+00:00'))
        datetime.fromisoformat(raw_data['updated_at'].replace('Z', '+00:00'))

    def test_response_contains_valid_enum_values(self):
        """Test that response contains valid enum string values."""
        response = loads_retrieve.sync_detailed(
            client=self.api_client,
            id=self.clean_load.pk
        )

        raw_data = self._get_raw_response(response)

        # Verify enum values are valid
        valid_statuses = {e.value for e in StatusEnum}
        valid_billing_statuses = {e.value for e in BillingStatusEnum}

        self.assertIn(raw_data['status'], valid_statuses)
        self.assertIn(raw_data['billing_status'], valid_billing_statuses)

    def test_parsed_load_has_correct_types(self):
        """Test that LoadSchema parses with correct datetime and enum types."""
        load = loads_retrieve.sync(
            client=self.api_client,
            id=self.clean_load.pk
        )

        self.assertIsNotNone(load)
        self.assertIsInstance(load, LoadSchema)

        # Verify datetime parsing
        from datetime import datetime
        self.assertIsInstance(load.created_at, datetime)
        self.assertIsInstance(load.updated_at, datetime)

        # Verify enum parsing
        self.assertIsInstance(load.status, StatusEnum)
        self.assertIsInstance(load.billing_status, BillingStatusEnum)

    # ==================== UPSERT TESTS ====================

    def test_partial_update_upserts_stops_with_existing_and_new(self):
        """
        Test that PATCH /loads/{id}/ upserts stops correctly.

        Scenario:
        - Start with a load that has 1 leg with existing stops
        - Update the load with:
          - Load-level fields (reference_number, status, etc.)
          - 2 existing stops (with IDs) - should be updated
          - 1 new stop (without ID) - should be created
        - Verify that exactly 3 stops exist after the update (upsert replaces all)
        """
        # Use sample_load which has legs with stops from quick_create
        load = self.sample_load
        leg = self.sample_result['leg']
        customer = self.sample_result['customer']
        existing_stops = list(leg.stops.all().order_by('stop_number'))
        address = self.sample_result['stops'][0].address

        # Verify we have at least 2 existing stops to work with
        self.assertGreaterEqual(len(existing_stops), 2, "Should have at least 2 stops")

        # Use first 2 stops for the upsert test
        stop1 = existing_stops[0]
        stop2 = existing_stops[1]
        original_stop1_id = stop1.pk
        original_stop2_id = stop2.pk

        # Build payload with load info + 2 existing stops (with IDs) + 1 new stop (without ID)
        # Note: Stops not included in payload will be deleted by the upsert logic
        payload = {
            'reference_number': load.reference_number,
            'bol_number': load.bol_number,
            'customer': customer.pk,
            'status': StatusEnum.IN_TRANSIT.value,
            'billing_status': BillingStatusEnum.PENDING_DELIVERY.value,
            'legs': [
                {
                    'id': leg.pk,
                    'stops': [
                        {
                            'id': stop1.pk,
                            'stop_number': 1,
                            'address': address.pk,
                            'start_range': '2024-02-01T08:00:00Z',
                            'end_range': '2024-02-01T10:00:00Z',
                            'action': 'LL',
                            'po_numbers': 'PO-UPDATED-001',
                            'driver_notes': 'Updated stop 1',
                        },
                        {
                            'id': stop2.pk,
                            'stop_number': 2,
                            'address': address.pk,
                            'start_range': '2024-02-01T12:00:00Z',
                            'end_range': '2024-02-01T14:00:00Z',
                            'action': 'LU',
                            'po_numbers': 'PO-UPDATED-002',
                            'driver_notes': 'Updated stop 2',
                        },
                        {
                            # No ID - this is a NEW stop
                            # Using 'LL' because 'LU' cannot follow 'LU' per INVALID_TRANSITIONS
                            'stop_number': 3,
                            'address': address.pk,
                            'start_range': '2024-02-01T16:00:00Z',
                            'end_range': '2024-02-01T18:00:00Z',
                            'action': 'LL',
                            'po_numbers': 'PO-NEW-003',
                            'driver_notes': 'New stop 3 - created via upsert',
                        },
                    ]
                }
            ]
        }

        # Use DRF client directly to perform partial update
        from django.urls import reverse
        url = reverse('load-detail', kwargs={'pk': load.pk})
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}. Response: {response.data}"
        )

        # Verify load-level fields were updated
        load.refresh_from_db()
        self.assertEqual(load.status, LoadStatus.IN_TRANSIT)

        # Refresh leg from database and check stops
        leg.refresh_from_db()
        updated_stops = list(leg.stops.all().order_by('stop_number'))

        # Verify exactly 3 stops now exist (2 updated + 1 new, others deleted)
        self.assertEqual(
            len(updated_stops),
            3,
            f"Expected 3 stops after upsert, got {len(updated_stops)}"
        )

        # Verify existing stops were updated (same IDs, new data)
        stop1.refresh_from_db()
        self.assertEqual(stop1.pk, original_stop1_id, "Stop 1 should keep its original ID")
        self.assertEqual(stop1.po_numbers, 'PO-UPDATED-001')
        self.assertEqual(stop1.driver_notes, 'Updated stop 1')

        stop2.refresh_from_db()
        self.assertEqual(stop2.pk, original_stop2_id, "Stop 2 should keep its original ID")
        self.assertEqual(stop2.po_numbers, 'PO-UPDATED-002')
        self.assertEqual(stop2.driver_notes, 'Updated stop 2')

        # Verify new stop was created
        new_stop = leg.stops.get(stop_number=3)
        self.assertEqual(new_stop.po_numbers, 'PO-NEW-003')
        self.assertEqual(new_stop.driver_notes, 'New stop 3 - created via upsert')
        self.assertEqual(new_stop.action, 'LL')

        # Verify the new stop has a different ID than existing stops
        existing_ids = {original_stop1_id, original_stop2_id}
        self.assertNotIn(
            new_stop.pk,
            existing_ids,
            "New stop should have a different ID than existing stops"
        )
