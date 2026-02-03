from machtms.backend.carriers.models import Carrier
from machtms.backend.customers.models import Customer
from machtms.backend.loads.models import Load
from machtms.backend.addresses.models import Address


def transform_load(load: Load|None):
    """
    Flatten the Load object into a dictionary that's easily indexed by MeiliSearch.
    """
    if load is None:
        raise Exception("This Load is None")
    return {
        "id": load.id,
        "invoice_id": load.invoice_id,
        "organization_id": load.organization_id,
        "reference": load.reference,
        "customer": getattr(load.customer, "company_name", None),
        "carrier": getattr(load.carrier, "company_name", None),
        # Flatten all stops
        "stops": [
            {
                "stop_num": stop.stop_num,
                "action": stop.action,
                "place_name": stop.address.place_name,
                "address": (
                    f"{stop.address.street}, {stop.address.city}, "
                    f"{stop.address.state} {getattr(stop.address, 'zip_code', "")}".strip(" ")
                )
            } for stop in load.stops.all() if stop.address
        ],
    }


def transform_carrier(carrier: Carrier|None):
    """
    Serialize the Carrier object.
    """
    if carrier is None:
        raise Exception("This Carrier is None")
    return {
        "company_name": carrier.company_name
    }


def transform_customer(customer: Customer):
    """
    Serialize the Customer object.
    """
    return {
        "company_name": customer.company_name
    }


def transform_address(address: Address|None):
    """
    Serialize the Address object.
    """

    if address is None:
        raise Exception("This Address is None")
    return {
        "place_name": address.place_name,
        "street": address.street,
        "city": address.city,
        "state": address.state,
        "zip_code": address.zip_code
    }
