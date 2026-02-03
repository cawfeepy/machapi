from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.driver_list import DriverList


T = TypeVar("T", bound="Carrier")


@_attrs_define
class Carrier:
    """Serializer for Carrier model.

    Attributes:
        id (int):
        carrier_name (str):
        drivers (list[DriverList]):
        phone (str | Unset):
        email (str | Unset):
        contractor (bool | Unset):
    """

    id: int
    carrier_name: str
    drivers: list[DriverList]
    phone: str | Unset = UNSET
    email: str | Unset = UNSET
    contractor: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        carrier_name = self.carrier_name

        drivers = []
        for drivers_item_data in self.drivers:
            drivers_item = drivers_item_data.to_dict()
            drivers.append(drivers_item)

        phone = self.phone

        email = self.email

        contractor = self.contractor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "carrier_name": carrier_name,
                "drivers": drivers,
            }
        )
        if phone is not UNSET:
            field_dict["phone"] = phone
        if email is not UNSET:
            field_dict["email"] = email
        if contractor is not UNSET:
            field_dict["contractor"] = contractor

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("id", (None, str(self.id).encode(), "text/plain")))

        files.append(
            ("carrier_name", (None, str(self.carrier_name).encode(), "text/plain"))
        )

        for drivers_item_element in self.drivers:
            files.append(
                (
                    "drivers",
                    (
                        None,
                        json.dumps(drivers_item_element.to_dict()).encode(),
                        "application/json",
                    ),
                )
            )

        if not isinstance(self.phone, Unset):
            files.append(("phone", (None, str(self.phone).encode(), "text/plain")))

        if not isinstance(self.email, Unset):
            files.append(("email", (None, str(self.email).encode(), "text/plain")))

        if not isinstance(self.contractor, Unset):
            files.append(
                ("contractor", (None, str(self.contractor).encode(), "text/plain"))
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.driver_list import DriverList

        d = dict(src_dict)
        id = d.pop("id")

        carrier_name = d.pop("carrier_name")

        drivers = []
        _drivers = d.pop("drivers")
        for drivers_item_data in _drivers:
            drivers_item = DriverList.from_dict(drivers_item_data)

            drivers.append(drivers_item)

        phone = d.pop("phone", UNSET)

        email = d.pop("email", UNSET)

        contractor = d.pop("contractor", UNSET)

        carrier = cls(
            id=id,
            carrier_name=carrier_name,
            drivers=drivers,
            phone=phone,
            email=email,
            contractor=contractor,
        )

        carrier.additional_properties = d
        return carrier

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
