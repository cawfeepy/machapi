from machtms.core.factories.addresses import AddressFactory
from machtms.core.factories.carrier import CarrierFactory, DriverFactory
from machtms.core.factories.creator_factories import (
    FakeAddressCreator,
    FakeCarrierCreator,
    FakeStopCreator,
    LoadCreationFactory,
    create_batch_loads,
    quick_create,
)
from machtms.core.factories.customer import (
    CustomerAPFactory,
    CustomerFactory,
    CustomerRepresentativeFactory,
)
from machtms.core.factories.leg import LegFactory, ShipmentAssignmentFactory
from machtms.core.factories.loads import LoadFactory
from machtms.core.factories.routes import StopFactory

__all__ = [
    # Address factories
    'AddressFactory',
    # Carrier factories
    'CarrierFactory',
    'DriverFactory',
    # Customer factories
    'CustomerAPFactory',
    'CustomerRepresentativeFactory',
    'CustomerFactory',
    # Simulation creators
    'FakeAddressCreator',
    'FakeCarrierCreator',
    'FakeStopCreator',
    # Load factories
    'LoadFactory',
    'LoadCreationFactory',
    # Leg factories
    'LegFactory',
    'ShipmentAssignmentFactory',
    # Route factories
    'StopFactory',
    # Prebuilt convenience functions
    'create_batch_loads',
    'quick_create',
]
