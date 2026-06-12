"""
Test suite for the flat per-leg schedule endpoint: /loads/leg-schedule/.

The endpoint accepts a list of dates (YYYY-MM-DD) plus an IANA timezone and
treats each date as a full local day, converted to an inclusive UTC window.

A leg becomes its own ROW only when one of that leg's OWN stops starts inside a
requested window. The emitted rows form ONE flat chronological stream sorted by
each leg's own earliest stop start_range (tie-broken by leg pk); rows are NOT
grouped by load, so a multi-leg load's rows can be split apart by other loads'
legs whose pickups fall between them.

sequence_index is the leg's 0-based position in the load's FULL trip order, so
it can be sparse across the response (a row may have sequence_index == 1 with no
sequence_index == 0 row present). previous_legs / next_legs are still sliced
from the load's full ordered leg list, so an off-window sibling -- or a
stop-less sibling -- that never earns a row of its own still appears as a
sibling summary inside an in-window leg's previous_legs / next_legs.

Each row carries the load identity, the leg's owner (carrier + driver or null),
the leg's stops, and those condensed sibling summaries.

Run:
    uv run python manage.py test machtms.backend.loads.tests.test_leg_schedule
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from machtms.backend.auth.models import Organization, OrganizationUser, UserProfile
from machtms.backend.loads.models import Load, LoadStatus
from machtms.backend.legs.models import Leg, ShipmentAssignment
from machtms.core.factories.loads import LoadFactory
from machtms.core.factories.leg import LegFactory
from machtms.core.factories.routes import StopFactory
from machtms.core.factories.addresses import AddressFactory
from machtms.core.factories.customer import CustomerFactory
from machtms.core.factories.carrier import CarrierFactory, DriverFactory


UTC = ZoneInfo('UTC')
LA = ZoneInfo('America/Los_Angeles')


def local_dt(year, month, day, hour=12, minute=0, tz=LA):
    """A timezone-aware datetime in the given local zone."""
    return datetime(year, month, day, hour, minute, tzinfo=tz)


@override_settings(DEBUG=True)
class LegScheduleEndpointTests(APITestCase):
    """Tests for the /loads/leg-schedule/ flat per-leg endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(
            company_name="Leg Schedule Org",
            phone="555-000-1111",
            email="legschedule@testorg.com",
        )
        cls.user = OrganizationUser.objects.create_user(
            email="legschedule@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        UserProfile.objects.create(user=cls.user, organization=cls.organization)

        cls.customer = CustomerFactory.create(customer_name="Acme Logistics")
        cls.carrier = CarrierFactory.create(carrier_name="Speedy Freight")
        cls.driver = DriverFactory.create(
            carrier=cls.carrier, first_name="John", last_name="Doe"
        )
        cls.url = reverse('load-leg-schedule')

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    # ---- factory helpers ---------------------------------------------------

    def _make_load(self, **kwargs):
        kwargs.setdefault('customer', self.customer)
        kwargs.setdefault('status', LoadStatus.PENDING)
        return LoadFactory.create(**kwargs)

    def _make_leg(self, load, assigned=False, carrier=None, driver=None):
        leg = LegFactory.create(load=load)
        if assigned:
            ShipmentAssignment.objects.create(
                leg=leg,
                carrier=carrier or self.carrier,
                driver=driver or self.driver,
            )
        return leg

    def _make_stop(self, leg, stop_number, start, action='LL', address=None, end=None):
        return StopFactory.create(
            leg=leg,
            stop_number=stop_number,
            action=action,
            address=address or AddressFactory.create(),
            start_range=start,
            end_range=end if end is not None else start + timedelta(hours=2),
        )

    def _get(self, dates, tz='America/Los_Angeles'):
        params = [('dates', d) for d in dates]
        params.append(('timezone', tz))
        return self.client.get(self.url, params)

    # ---- 1. response shape -------------------------------------------------

    def test_returns_200_and_count_results_shape(self):
        load = self._make_load()
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 9))

        response = self._get(['2025-06-01'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertIsInstance(response.data['results'], list)
        self.assertEqual(response.data['count'], len(response.data['results']))

    # ---- 2. one row per leg ------------------------------------------------

    def test_multi_leg_load_splits_into_one_row_per_leg(self):
        load = self._make_load(reference_number="REF-123")
        leg1 = self._make_leg(load, assigned=True)
        self._make_stop(leg1, 1, local_dt(2025, 6, 1, 8))
        leg2 = self._make_leg(load, assigned=False)
        self._make_stop(leg2, 1, local_dt(2025, 6, 1, 16))

        response = self._get(['2025-06-01'])
        rows = response.data['results']
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['reference_number'] for r in rows}, {"REF-123"})
        self.assertEqual(sorted(r['sequence_index'] for r in rows), [0, 1])
        self.assertEqual({r['leg_id'] for r in rows}, {leg1.id, leg2.id})

    # ---- 3. leg ordering by earliest stop start ---------------------------

    def test_leg_ordering_by_earliest_stop_start(self):
        # leg_a created first (lower pk) but has a LATER stop than leg_b.
        load = self._make_load()
        leg_a = self._make_leg(load, assigned=True)
        self._make_stop(leg_a, 1, local_dt(2025, 6, 1, 18))
        leg_b = self._make_leg(load, assigned=False)
        self._make_stop(leg_b, 1, local_dt(2025, 6, 1, 6))
        self.assertLess(leg_a.pk, leg_b.pk)

        response = self._get(['2025-06-01'])
        rows = {r['leg_id']: r for r in response.data['results']}
        # leg_b (earlier stop) must be sequence 0, leg_a sequence 1
        self.assertEqual(rows[leg_b.id]['sequence_index'], 0)
        self.assertEqual(rows[leg_a.id]['sequence_index'], 1)
        # leg_b appears in leg_a's previous_legs
        prev_ids = [s['leg_id'] for s in rows[leg_a.id]['previous_legs']]
        self.assertIn(leg_b.id, prev_ids)

    # ---- 4. timezone conversion boundary -----------------------------------

    def test_tz_conversion_boundary(self):
        # 00:30 on Jun 1 in LA == 07:30 UTC Jun 1. It belongs to the LA Jun 1
        # window, but NOT to the UTC-interpreted "May 31" LA window.
        load = self._make_load()
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 0, 30))

        in_window = self._get(['2025-06-01'])
        self.assertEqual(in_window.data['count'], 1)

        # Querying the previous local day must NOT include it.
        out_window = self._get(['2025-05-31'])
        self.assertEqual(out_window.data['count'], 0)

    def test_late_night_local_stop_maps_to_correct_utc_day(self):
        # 23:30 Jun 1 LA == 06:30 UTC Jun 2. Must match the LA Jun 1 query
        # (proves we use the local window, not a naive UTC date match).
        load = self._make_load()
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 23, 30))

        response = self._get(['2025-06-01'])
        self.assertEqual(response.data['count'], 1)

    # ---- 5. DST spring-forward ---------------------------------------------

    def test_dst_spring_forward_day_covered(self):
        # 2025-03-09 is the US spring-forward day (02:00 -> 03:00 local).
        # A stop late that local day must still be matched.
        load = self._make_load()
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 3, 9, 23, 0))

        response = self._get(['2025-03-09'])
        self.assertEqual(response.data['count'], 1)

    # ---- 6. non-consecutive dates ------------------------------------------

    def test_non_consecutive_dates(self):
        day1 = self._make_load(reference_number="DAY1")
        leg1 = self._make_leg(day1, assigned=True)
        self._make_stop(leg1, 1, local_dt(2025, 6, 1, 9))

        day2 = self._make_load(reference_number="DAY2")
        leg2 = self._make_leg(day2, assigned=True)
        self._make_stop(leg2, 1, local_dt(2025, 6, 2, 9))

        day3 = self._make_load(reference_number="DAY3")
        leg3 = self._make_leg(day3, assigned=True)
        self._make_stop(leg3, 1, local_dt(2025, 6, 3, 9))

        response = self._get(['2025-06-01', '2025-06-03'])
        refs = {r['reference_number'] for r in response.data['results']}
        self.assertEqual(refs, {"DAY1", "DAY3"})

    # ---- 7-9. validation errors --------------------------------------------

    def test_invalid_timezone_returns_400(self):
        response = self._get(['2025-06-01'], tz='Not/AZone')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timezone', response.data)

    def test_bad_date_format_returns_400(self):
        response = self._get(['2025-13-40'])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('dates', response.data)

    def test_empty_dates_returns_400(self):
        response = self.client.get(self.url, {'timezone': 'America/Los_Angeles'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('dates', response.data)

    def test_missing_timezone_returns_400(self):
        response = self.client.get(self.url, [('dates', '2025-06-01')])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timezone', response.data)

    # ---- 10-11. owner shape ------------------------------------------------

    def test_unassigned_leg_owner_null(self):
        load = self._make_load()
        leg = self._make_leg(load, assigned=False)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 9))

        response = self._get(['2025-06-01'])
        row = response.data['results'][0]
        self.assertIsNone(row['owner'])
        self.assertFalse(row['is_assigned'])

    def test_assigned_leg_owner_shape(self):
        load = self._make_load()
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 9))

        response = self._get(['2025-06-01'])
        row = response.data['results'][0]
        self.assertTrue(row['is_assigned'])
        owner = row['owner']
        self.assertEqual(owner['carrier']['id'], self.carrier.id)
        self.assertEqual(owner['carrier']['carrier_name'], "Speedy Freight")
        self.assertEqual(owner['driver']['id'], self.driver.id)
        self.assertEqual(owner['driver']['full_name'], "John Doe")

    # ---- 12. sibling summary -----------------------------------------------

    def test_sibling_summary_correctness(self):
        load = self._make_load()
        address1 = AddressFactory.create(place_name="Walmart DC", city="Dallas", state="TX")
        leg1 = self._make_leg(load, assigned=True)
        self._make_stop(leg1, 1, local_dt(2025, 6, 1, 8), address=address1)

        address2 = AddressFactory.create(place_name="Target DC", city="Phoenix", state="AZ")
        leg2 = self._make_leg(load, assigned=False)
        self._make_stop(leg2, 1, local_dt(2025, 6, 1, 16), action='LU', address=address2)

        response = self._get(['2025-06-01'])
        rows = {r['leg_id']: r for r in response.data['results']}

        # leg1 (sequence 0) should summarize leg2 under next_legs.
        next_legs = rows[leg1.id]['next_legs']
        self.assertEqual(len(next_legs), 1)
        summary = next_legs[0]
        self.assertEqual(summary['leg_id'], leg2.id)
        self.assertEqual(summary['owner'], "unassigned")
        self.assertEqual(summary['stops'][0]['label'], "Target DC - Phoenix, AZ")
        self.assertIsNotNone(summary['stops'][0]['start_range'])

        # leg2's previous_legs should summarize leg1 with its assigned owner.
        prev_legs = rows[leg2.id]['previous_legs']
        self.assertEqual(prev_legs[0]['leg_id'], leg1.id)
        self.assertEqual(prev_legs[0]['owner'], "Speedy Freight / John Doe")
        self.assertEqual(prev_legs[0]['stops'][0]['label'], "Walmart DC - Dallas, TX")

    # ---- 13. off-window sibling leg is NOT a row, only a sibling ------------

    def test_off_window_leg_is_not_a_row_but_appears_as_sibling(self):
        load = self._make_load()
        in_window_leg = self._make_leg(load, assigned=True)
        self._make_stop(in_window_leg, 1, local_dt(2025, 6, 1, 9))
        # Sibling whose only stop is far outside the queried window. Its later
        # stop (July) sorts it AFTER the in-window leg, so it is a "next" sibling.
        off_window_leg = self._make_leg(load, assigned=False)
        self._make_stop(off_window_leg, 1, local_dt(2025, 7, 15, 9))

        response = self._get(['2025-06-01'])
        results = response.data['results']
        leg_ids = {r['leg_id'] for r in results}

        # Only the in-window leg earns a row.
        self.assertEqual(len(results), 1)
        self.assertIn(in_window_leg.id, leg_ids)
        self.assertNotIn(off_window_leg.id, leg_ids)

        # The off-window sibling still appears in the in-window leg's next_legs.
        row = {r['leg_id']: r for r in results}[in_window_leg.id]
        next_ids = [s['leg_id'] for s in row['next_legs']]
        self.assertIn(off_window_leg.id, next_ids)

    # ---- 14. null customer -------------------------------------------------

    def test_customer_null(self):
        load = self._make_load(customer=None)
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 9))

        response = self._get(['2025-06-01'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['results'][0]['customer'])

    def test_customer_shape(self):
        load = self._make_load()
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 6, 1, 9))

        response = self._get(['2025-06-01'])
        customer = response.data['results'][0]['customer']
        self.assertEqual(customer['id'], self.customer.id)
        self.assertEqual(customer['customer_name'], "Acme Logistics")

    # ---- 15. organization scoping ------------------------------------------

    @override_settings(DEBUG=False)
    def test_org_scoping_filters_by_organization(self):
        """
        The view scopes via TMSViewMixin.get_queryset() -> Load.objects.fbo().
        fbo() short-circuits to .all() under DEBUG (see core/base/managers.py),
        so org isolation is asserted directly against the queryset with DEBUG
        off -- the real mechanism the endpoint relies on -- rather than through
        the HTTP layer (which would also need OrganizationTestMiddleware wiring).
        """
        my_load = self._make_load(organization=self.organization)
        my_leg = self._make_leg(my_load, assigned=True)
        self._make_stop(my_leg, 1, local_dt(2025, 6, 1, 9))

        other_org = Organization.objects.create(
            company_name="Other Org", phone="555-9", email="other@org.com"
        )
        other_load = LoadFactory.create(
            customer=CustomerFactory.create(), status=LoadStatus.PENDING,
            organization=other_org,
        )
        other_leg = LegFactory.create(load=other_load, organization=other_org)
        self._make_stop(other_leg, 1, local_dt(2025, 6, 1, 9))

        scoped = Load.objects.fbo(organization=self.organization)
        scoped_ids = set(scoped.values_list('id', flat=True))
        self.assertIn(my_load.id, scoped_ids)
        self.assertNotIn(other_load.id, scoped_ids)

    # ---- leg with no stops is not a row, only a sibling (edge) --------------

    def test_leg_without_stops_is_not_a_row_but_is_a_sibling(self):
        load = self._make_load()
        leg_with = self._make_leg(load, assigned=True)
        self._make_stop(leg_with, 1, local_dt(2025, 6, 1, 9))
        leg_without = self._make_leg(load, assigned=False)  # no stops

        response = self._get(['2025-06-01'])
        results = response.data['results']
        rows = {r['leg_id']: r for r in results}

        # A stop-less leg can never match a window, so it earns no row.
        self.assertEqual(len(results), 1)
        self.assertIn(leg_with.id, rows)
        self.assertNotIn(leg_without.id, rows)
        self.assertEqual(rows[leg_with.id]['sequence_index'], 0)

        # order_legs places stop-less legs last, so it is a "next" sibling with
        # no stops and an "unassigned" owner summary.
        next_legs = rows[leg_with.id]['next_legs']
        sibling = {s['leg_id']: s for s in next_legs}[leg_without.id]
        self.assertEqual(sibling['stops'], [])
        self.assertEqual(sibling['owner'], "unassigned")

    # ---- A. flat chronological stream sorts across loads -------------------

    def test_results_sorted_chronologically_across_loads(self):
        # Two SEPARATE loads. Load A is created first (lower load pk) but its
        # single leg's stop is LATER in the day; Load B is created second
        # (higher load pk) but its stop is EARLIER. The flat stream must sort by
        # each leg's OWN earliest stop -- not by load creation order / pk.
        load_a = self._make_load(reference_number="LOAD-A")
        leg_a = self._make_leg(load_a, assigned=True)
        self._make_stop(leg_a, 1, local_dt(2025, 6, 1, 18))

        load_b = self._make_load(reference_number="LOAD-B")
        leg_b = self._make_leg(load_b, assigned=False)
        self._make_stop(leg_b, 1, local_dt(2025, 6, 1, 6))

        self.assertLess(load_a.pk, load_b.pk)

        response = self._get(['2025-06-01'])
        results = response.data['results']
        self.assertEqual(len(results), 2)
        # leg_b (06:00) comes before leg_a (18:00), despite leg_b's load pk being
        # higher -- proving global chronological ordering across loads.
        self.assertEqual(results[0]['leg_id'], leg_b.id)
        self.assertEqual(results[1]['leg_id'], leg_a.id)

    # ---- B. sequence_index is sparse for a partially in-window load --------

    def test_sparse_sequence_index_for_partially_in_window_load(self):
        # One load, two legs. leg1's only stop is EARLIER and OFF-window;
        # leg2's only stop is LATER and IN-window. order_legs sorts by earliest
        # stop, so leg1 (June 1 09:00) is index 0 and leg2 (June 15 09:00) is
        # index 1. We query only leg2's day, so leg1 never earns a row -- proving
        # the surviving row carries a SPARSE sequence_index (1, with no 0 row).
        load = self._make_load()
        leg1 = self._make_leg(load, assigned=True)
        self._make_stop(leg1, 1, local_dt(2025, 6, 1, 9))  # off-window, earlier
        leg2 = self._make_leg(load, assigned=False)
        self._make_stop(leg2, 1, local_dt(2025, 6, 15, 9))  # in-window, later

        response = self._get(['2025-06-15'])
        results = response.data['results']

        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row['leg_id'], leg2.id)
        # Sparse: this is sequence_index 1 even though no index-0 row is present.
        self.assertEqual(row['sequence_index'], 1)
        # Full-trip context preserved: the off-window earlier sibling (index 0)
        # appears in previous_legs.
        prev = {s['leg_id']: s for s in row['previous_legs']}
        self.assertIn(leg1.id, prev)
        self.assertEqual(prev[leg1.id]['sequence_index'], 0)

    # ---- C. a load with no in-window legs is absent entirely ----------------

    def test_load_with_no_in_window_legs_absent(self):
        # Every stop of this load is far from the queried date, so the DB
        # pre-filter never even fetches it and it contributes zero rows.
        load = self._make_load(reference_number="OFF-WINDOW")
        leg = self._make_leg(load, assigned=True)
        self._make_stop(leg, 1, local_dt(2025, 7, 15, 9))

        response = self._get(['2025-06-01'])
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'], [])
