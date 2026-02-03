from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="DriverList")


@_attrs_define
class DriverList:
    """Lightweight serializer for Driver list views.

    Attributes:
        id (int):
        full_name (str):
        phone_number (str):
        carrier (int | None | Unset):
    """

    id: int
    full_name: str
    phone_number: str
    carrier: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        full_name = self.full_name

        phone_number = self.phone_number

        carrier: int | None | Unset
        if isinstance(self.carrier, Unset):
            carrier = UNSET
        else:
            carrier = self.carrier

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "full_name": full_name,
                "phone_number": phone_number,
            }
        )
        if carrier is not UNSET:
            field_dict["carrier"] = carrier

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        full_name = d.pop("full_name")

        phone_number = d.pop("phone_number")

        def _parse_carrier(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        carrier = _parse_carrier(d.pop("carrier", UNSET))

        driver_list = cls(
            id=id,
            full_name=full_name,
            phone_number=phone_number,
            carrier=carrier,
        )

        driver_list.additional_properties = d
        return driver_list

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
