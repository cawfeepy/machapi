from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types

T = TypeVar("T", bound="ShipmentAssignment")


@_attrs_define
class ShipmentAssignment:
    """Serializer for the ShipmentAssignment model.

    Accepts primary keys for carrier, driver, and leg on input.
    Returns full nested JSON for carrier and driver on output.

        Attributes:
            id (int):
            carrier (int):
            driver (int):
            leg (int):
    """

    id: int
    carrier: int
    driver: int
    leg: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        carrier = self.carrier

        driver = self.driver

        leg = self.leg

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "carrier": carrier,
                "driver": driver,
                "leg": leg,
            }
        )

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("id", (None, str(self.id).encode(), "text/plain")))

        files.append(("carrier", (None, str(self.carrier).encode(), "text/plain")))

        files.append(("driver", (None, str(self.driver).encode(), "text/plain")))

        files.append(("leg", (None, str(self.leg).encode(), "text/plain")))

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        carrier = d.pop("carrier")

        driver = d.pop("driver")

        leg = d.pop("leg")

        shipment_assignment = cls(
            id=id,
            carrier=carrier,
            driver=driver,
            leg=leg,
        )

        shipment_assignment.additional_properties = d
        return shipment_assignment

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
