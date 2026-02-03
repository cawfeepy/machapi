from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedShipmentAssignment")


@_attrs_define
class PatchedShipmentAssignment:
    """Serializer for the ShipmentAssignment model.

    Accepts primary keys for carrier, driver, and leg on input.
    Returns full nested JSON for carrier and driver on output.

        Attributes:
            id (int | Unset):
            carrier (int | Unset):
            driver (int | Unset):
            leg (int | Unset):
    """

    id: int | Unset = UNSET
    carrier: int | Unset = UNSET
    driver: int | Unset = UNSET
    leg: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        carrier = self.carrier

        driver = self.driver

        leg = self.leg

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if carrier is not UNSET:
            field_dict["carrier"] = carrier
        if driver is not UNSET:
            field_dict["driver"] = driver
        if leg is not UNSET:
            field_dict["leg"] = leg

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.carrier, Unset):
            files.append(("carrier", (None, str(self.carrier).encode(), "text/plain")))

        if not isinstance(self.driver, Unset):
            files.append(("driver", (None, str(self.driver).encode(), "text/plain")))

        if not isinstance(self.leg, Unset):
            files.append(("leg", (None, str(self.leg).encode(), "text/plain")))

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        carrier = d.pop("carrier", UNSET)

        driver = d.pop("driver", UNSET)

        leg = d.pop("leg", UNSET)

        patched_shipment_assignment = cls(
            id=id,
            carrier=carrier,
            driver=driver,
            leg=leg,
        )

        patched_shipment_assignment.additional_properties = d
        return patched_shipment_assignment

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
