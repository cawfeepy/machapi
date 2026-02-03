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


T = TypeVar("T", bound="PatchedCarrier")


@_attrs_define
class PatchedCarrier:
    """Serializer for Carrier model.

    Attributes:
        id (int | Unset):
        carrier_name (str | Unset):
        phone (str | Unset):
        email (str | Unset):
        contractor (bool | Unset):
        drivers (list[DriverList] | Unset):
    """

    id: int | Unset = UNSET
    carrier_name: str | Unset = UNSET
    phone: str | Unset = UNSET
    email: str | Unset = UNSET
    contractor: bool | Unset = UNSET
    drivers: list[DriverList] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        carrier_name = self.carrier_name

        phone = self.phone

        email = self.email

        contractor = self.contractor

        drivers: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.drivers, Unset):
            drivers = []
            for drivers_item_data in self.drivers:
                drivers_item = drivers_item_data.to_dict()
                drivers.append(drivers_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if carrier_name is not UNSET:
            field_dict["carrier_name"] = carrier_name
        if phone is not UNSET:
            field_dict["phone"] = phone
        if email is not UNSET:
            field_dict["email"] = email
        if contractor is not UNSET:
            field_dict["contractor"] = contractor
        if drivers is not UNSET:
            field_dict["drivers"] = drivers

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.carrier_name, Unset):
            files.append(
                ("carrier_name", (None, str(self.carrier_name).encode(), "text/plain"))
            )

        if not isinstance(self.phone, Unset):
            files.append(("phone", (None, str(self.phone).encode(), "text/plain")))

        if not isinstance(self.email, Unset):
            files.append(("email", (None, str(self.email).encode(), "text/plain")))

        if not isinstance(self.contractor, Unset):
            files.append(
                ("contractor", (None, str(self.contractor).encode(), "text/plain"))
            )

        if not isinstance(self.drivers, Unset):
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

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.driver_list import DriverList

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        carrier_name = d.pop("carrier_name", UNSET)

        phone = d.pop("phone", UNSET)

        email = d.pop("email", UNSET)

        contractor = d.pop("contractor", UNSET)

        _drivers = d.pop("drivers", UNSET)
        drivers: list[DriverList] | Unset = UNSET
        if _drivers is not UNSET:
            drivers = []
            for drivers_item_data in _drivers:
                drivers_item = DriverList.from_dict(drivers_item_data)

                drivers.append(drivers_item)

        patched_carrier = cls(
            id=id,
            carrier_name=carrier_name,
            phone=phone,
            email=email,
            contractor=contractor,
            drivers=drivers,
        )

        patched_carrier.additional_properties = d
        return patched_carrier

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
