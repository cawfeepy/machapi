import factory
from factory.django import DjangoModelFactory

from machtms.backend.legs.models import Leg, ShipmentAssignment


class LegFactory(DjangoModelFactory):
    """
    Factory for creating Leg instances.
    A Leg represents a segment of a load's journey.
    """
    class Meta:
        model = Leg

    load = factory.SubFactory('machtms.core.factories.loads.LoadFactory')


class ShipmentAssignmentFactory(DjangoModelFactory):
    """
    Factory for creating ShipmentAssignment instances.
    Associates a carrier and driver to a specific leg of a shipment.
    """
    class Meta:
        model = ShipmentAssignment

    carrier = factory.SubFactory('machtms.core.factories.carrier.CarrierFactory')
    driver = factory.SubFactory('machtms.core.factories.carrier.DriverFactory')
    leg = factory.SubFactory(LegFactory)
