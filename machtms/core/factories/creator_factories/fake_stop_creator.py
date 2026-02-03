"""
FakeStopCreator module for generating stops for existing legs.

This module provides the FakeStopCreator class that generates Stop instances
for existing Leg objects, useful for testing stop-specific functionality
or adding stops to legs without going through the full load creation workflow.
"""
import random
from datetime import timedelta
from typing import List, Optional, TypeAlias

from django.utils import timezone

from machtms.backend.legs.models import Leg
from machtms.backend.routes.models import Stop
from machtms.core.factories.routes import StopFactory

# Type aliases for clarity
StopList: TypeAlias = List[Stop]


class FakeStopCreator:
    """
    Creates and manages fake stops for legs in test scenarios.

    This class generates Stop instances using StopFactory for existing Leg objects.
    It handles proper stop numbering, action assignment based on position,
    and realistic time ranges.

    Attributes:
        stops: List of all Stop instances created by this creator.

    Example:
        creator = FakeStopCreator()
        stops = creator.create_stops_for_leg(leg, num_stops=3)
        # Creates 3 stops: pickup, hub, delivery

        # Or create stops for multiple legs
        for leg in legs:
            creator.create_stops_for_leg(leg)
    """

    FIRST_STOP_ACTIONS: List[str] = ["LL", "HL"]
    MIDDLE_STOP_ACTIONS: List[str] = ["HUBP", "HUBD"]
    LAST_STOP_ACTIONS: List[str] = ["LU", "LD"]

    def __init__(self) -> None:
        """
        Initialize FakeStopCreator.

        Creates an empty list to track all stops created by this instance.
        """
        self.stops: StopList = []

    def _determine_action(self, stop_index: int, total_stops: int) -> str:
        """
        Determine the appropriate action for a stop based on its position.

        Args:
            stop_index: Zero-based index of the stop within the leg
            total_stops: Total number of stops being created

        Returns:
            Action code string (e.g., 'LL', 'LU', 'HUBP')
        """
        is_first = stop_index == 0
        is_last = stop_index == total_stops - 1

        if is_first:
            return random.choice(self.FIRST_STOP_ACTIONS)
        elif is_last:
            return random.choice(self.LAST_STOP_ACTIONS)
        else:
            return random.choice(self.MIDDLE_STOP_ACTIONS)

    def create_stops_for_leg(
        self,
        leg: Leg,
        num_stops: int = 2,
        base_date: Optional["timezone.datetime"] = None,
    ) -> StopList:
        """
        Create stops for a given leg.

        Generates the specified number of stops with:
        - Sequential stop_number starting from 1
        - Appropriate actions based on position (first=pickup, last=delivery)
        - Auto-generated addresses via StopFactory's AddressFactory SubFactory
        - Time ranges spaced 4 hours apart with 2-hour windows

        Args:
            leg: Leg instance to associate stops with
            num_stops: Number of stops to create (default: 2, must be 2 or 3)
            base_date: Starting datetime for stop time ranges. If None, uses
                      now + 1-7 random days.

        Returns:
            List of created Stop instances ordered by stop_number

        Raises:
            ValueError: If num_stops is not 2 or 3

        Example:
            creator = FakeStopCreator()
            stops = creator.create_stops_for_leg(leg, num_stops=2)
            # Returns [pickup_stop, delivery_stop]
        """
        if num_stops not in (2, 3):
            raise ValueError(f"num_stops must be 2 or 3, got {num_stops}")

        if base_date is None:
            random_days_offset = random.randint(1, 7)
            base_date = timezone.now() + timedelta(days=random_days_offset)

        created_stops: StopList = []

        for stop_index in range(num_stops):
            stop_number = stop_index + 1
            action = self._determine_action(stop_index, num_stops)

            # Calculate time ranges: 4 hours apart with 2-hour windows
            hours_offset = 4 * stop_index
            start_range = base_date + timedelta(hours=hours_offset)
            end_range = start_range + timedelta(hours=2)

            stop = StopFactory.create(
                leg=leg,
                stop_number=stop_number,
                action=action,
                start_range=start_range,
                end_range=end_range,
            )

            created_stops.append(stop)
            self.stops.append(stop)

        return created_stops

    def create_batch_stops(
        self,
        legs: List[Leg],
        stops_per_leg: int = 2,
    ) -> List[StopList]:
        """
        Create stops for multiple legs at once.

        This is a convenience method for generating stops across multiple legs,
        useful for bulk test data generation.

        Args:
            legs: List of Leg instances to create stops for
            stops_per_leg: Number of stops per leg (2 or 3, default: 2)

        Returns:
            List of stop lists, one for each leg

        Example:
            creator = FakeStopCreator()
            all_stops = creator.create_batch_stops(legs, stops_per_leg=3)
            for leg_stops in all_stops:
                print(f"Created {len(leg_stops)} stops")
        """
        results: List[StopList] = []

        for leg in legs:
            leg_stops = self.create_stops_for_leg(leg, num_stops=stops_per_leg)
            results.append(leg_stops)

        return results

    def get_all_stops(self) -> StopList:
        """
        Return all stops created by this FakeStopCreator instance.

        Returns:
            List of all Stop instances created by this creator

        Example:
            creator = FakeStopCreator()
            creator.create_stops_for_leg(leg1)
            creator.create_stops_for_leg(leg2)
            all_stops = creator.get_all_stops()  # Contains stops from both legs
        """
        return self.stops

    def get_stop_count(self) -> int:
        """
        Return the total number of stops created by this instance.

        Returns:
            Integer count of all stops created
        """
        return len(self.stops)
