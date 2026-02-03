from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CarrierList")


@_attrs_define
class CarrierList:
    """Lightweight serializer for Carrier list views.

    Attributes:
        id (int):
        carrier_name (str):
        driver_count (str):
        phone (str | Unset):
        contractor (bool | Unset):
    """

    id: int
    carrier_name: str
    driver_count: str
    phone: str | Unset = UNSET
    contractor: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        carrier_name = self.carrier_name

        driver_count = self.driver_count

        phone = self.phone

        contractor = self.contractor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "carrier_name": carrier_name,
                "driver_count": driver_count,
            }
        )
        if phone is not UNSET:
            field_dict["phone"] = phone
        if contractor is not UNSET:
            field_dict["contractor"] = contractor

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        carrier_name = d.pop("carrier_name")

        driver_count = d.pop("driver_count")

        phone = d.pop("phone", UNSET)

        contractor = d.pop("contractor", UNSET)

        carrier_list = cls(
            id=id,
            carrier_name=carrier_name,
            driver_count=driver_count,
            phone=phone,
            contractor=contractor,
        )

        carrier_list.additional_properties = d
        return carrier_list

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
