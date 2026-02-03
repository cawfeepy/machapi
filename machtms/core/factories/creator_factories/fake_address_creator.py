"""
FakeAddressCreator module for generating and organizing fake addresses for load simulation.

This module provides the FakeAddressCreator class that generates Address instances
and organizes them into tuples suitable for route simulation.
"""
import random
from typing import List, Tuple, TypeAlias

from machtms.backend.addresses.models import Address
from machtms.core.factories.addresses import AddressFactory

# Type aliases for clarity
AddressTuple: TypeAlias = Tuple[Address, ...]
TwoStopRoute: TypeAlias = Tuple[Address, Address]
ThreeStopRoute: TypeAlias = Tuple[Address, Address, Address]
AddressList: TypeAlias = List[Address]


class FakeAddressCreator:
    """
    Creates and organizes fake addresses for load simulation purposes.

    This class generates N addresses using AddressFactory and organizes them into
    2-tuples (Shipper, Receiver) and 3-tuples (Shipper, Stop, Receiver) for use
    in load creation.

    Attributes:
        fakeAddresses: List of address tuples, each containing 2 or 3 Address instances.

    Important Constraint:
        The address with PK=1 (the first address created, at index 0) can appear as
        a shipper (first position in tuple) but CANNOT appear as a receiver (last
        position in any tuple). This enforces the business rule that certain
        locations are pickup-only.
    """

    def __init__(self, N: int) -> None:
        """
        Initialize FakeAddressCreator and generate N addresses organized into tuples.

        Args:
            N: Total number of addresses to create. Must be >= 3 for meaningful
               tuple generation.

        Raises:
            ValueError: If N is less than 3.
        """
        if N < 3:
            raise ValueError("N must be at least 3 for meaningful tuple generation")

        self.fakeAddresses: List[AddressTuple] = []

        # Create N addresses using AddressFactory
        addresses: AddressList = []
        for _ in range(N):
            addresses.append(AddressFactory.create())

        # The first address (PK=1, index 0) is our special shipper-only address
        shipper_only_address = addresses[0]

        # Create a pool of addresses that can be used as receivers (excluding first address)
        receiver_pool = addresses[1:]

        # Generate tuples with a mix of 2-tuples and 3-tuples (approximately 50/50 split)
        self._generate_address_tuples(addresses, shipper_only_address, receiver_pool)

    def _generate_address_tuples(
        self,
        all_addresses: AddressList,
        shipper_only_address: Address,
        receiver_pool: AddressList
    ) -> None:
        """
        Generate address tuples ensuring constraints are met.

        Creates both 2-tuples (Shipper, Receiver) and 3-tuples (Shipper, Stop, Receiver).
        Ensures that shipper_only_address never appears at the last index of any tuple.
        Ensures uniqueness within each tuple (no address appears twice in same tuple).

        Args:
            all_addresses: All created addresses.
            shipper_only_address: The address that cannot be a receiver (PK=1).
            receiver_pool: Addresses that can serve as receivers (excludes shipper_only).
        """
        num_addresses = len(all_addresses)

        # Determine number of tuples to create (roughly N/2 tuples, minimum 2)
        num_tuples = max(2, num_addresses // 2)

        for i in range(num_tuples):
            # Alternate between 2-tuples and 3-tuples for variety
            is_three_tuple = (i % 2 == 1)

            if is_three_tuple and len(all_addresses) >= 3:
                tuple_result = self._create_three_tuple(
                    all_addresses, shipper_only_address, receiver_pool
                )
            else:
                tuple_result = self._create_two_tuple(
                    all_addresses, shipper_only_address, receiver_pool
                )

            if tuple_result:
                self.fakeAddresses.append(tuple_result)

    def _create_two_tuple(
        self,
        all_addresses: AddressList,
        shipper_only_address: Address,
        receiver_pool: AddressList
    ) -> TwoStopRoute:
        """
        Create a 2-tuple (Shipper, Receiver) ensuring constraints are met.

        Args:
            all_addresses: All created addresses.
            shipper_only_address: The address that cannot be a receiver.
            receiver_pool: Addresses that can serve as receivers.

        Returns:
            A tuple of (shipper_address, receiver_address) with unique addresses.
        """
        # Pick a random shipper from all addresses
        shipper = random.choice(all_addresses)

        # Pick a receiver from receiver_pool, ensuring it's different from shipper
        available_receivers = [addr for addr in receiver_pool if addr != shipper]
        if not available_receivers:
            # Fallback: use any address from receiver_pool
            available_receivers = receiver_pool

        receiver = random.choice(available_receivers)

        return (shipper, receiver)

    def _create_three_tuple(
        self,
        all_addresses: AddressList,
        shipper_only_address: Address,
        receiver_pool: AddressList
    ) -> ThreeStopRoute:
        """
        Create a 3-tuple (Shipper, Stop, Receiver) ensuring constraints are met.

        Args:
            all_addresses: All created addresses.
            shipper_only_address: The address that cannot be a receiver.
            receiver_pool: Addresses that can serve as receivers.

        Returns:
            A tuple of (shipper_address, stop_address, receiver_address) with unique addresses.
        """
        # Pick a random shipper from all addresses
        shipper = random.choice(all_addresses)

        # Pick a stop that's different from shipper
        available_stops = [addr for addr in all_addresses if addr != shipper]
        stop = random.choice(available_stops)

        # Pick a receiver from receiver_pool, ensuring it's different from shipper and stop
        available_receivers = [
            addr for addr in receiver_pool
            if addr != shipper and addr != stop
        ]
        if not available_receivers:
            # Fallback: use any address from receiver_pool different from stop
            available_receivers = [addr for addr in receiver_pool if addr != stop]
            if not available_receivers:
                available_receivers = receiver_pool

        receiver = random.choice(available_receivers)

        return (shipper, stop, receiver)

    def filterFakeAddresses(self, stop_length: int) -> List[AddressTuple]:
        """
        Filter and return address tuples matching the specified stop_length.

        Args:
            stop_length: The desired tuple length (typically 2 or 3).
                - 2: Returns tuples with (Shipper, Receiver)
                - 3: Returns tuples with (Shipper, Stop, Receiver)

        Returns:
            List of address tuples where len(tuple) == stop_length.
            Returns an empty list if stop_length is not 2 or 3.
        """
        if stop_length not in (2, 3):
            return []

        return [addr_tuple for addr_tuple in self.fakeAddresses if len(addr_tuple) == stop_length]

    def get_address_tuple(self) -> AddressTuple:
        """
        Return a random address tuple from the fakeAddresses list.

        This method is used by LoadCreationFactory to obtain a random route
        for load creation.

        Returns:
            A random tuple containing 2 or 3 Address instances.

        Raises:
            IndexError: If fakeAddresses is empty (should not happen with N >= 3).
        """
        return random.choice(self.fakeAddresses)
