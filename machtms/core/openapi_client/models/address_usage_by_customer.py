from __future__ import annotations

import datetime
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from .. import types
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.address import Address


T = TypeVar("T", bound="AddressUsageByCustomer")


@_attrs_define
class AddressUsageByCustomer:
    """Serializer for the AddressUsageByCustomer model.

    Attributes:
        id (int):
        address (int):
        address_detail (Address): Serializer for the Address model.
        customer (int):
        last_used (datetime.datetime):
        times_used (int | Unset):
    """

    id: int
    address: int
    address_detail: Address
    customer: int
    last_used: datetime.datetime
    times_used: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        address = self.address

        address_detail = self.address_detail.to_dict()

        customer = self.customer

        last_used = self.last_used.isoformat()

        times_used = self.times_used

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "address": address,
                "address_detail": address_detail,
                "customer": customer,
                "last_used": last_used,
            }
        )
        if times_used is not UNSET:
            field_dict["times_used"] = times_used

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("id", (None, str(self.id).encode(), "text/plain")))

        files.append(("address", (None, str(self.address).encode(), "text/plain")))

        files.append(
            (
                "address_detail",
                (
                    None,
                    json.dumps(self.address_detail.to_dict()).encode(),
                    "application/json",
                ),
            )
        )

        files.append(("customer", (None, str(self.customer).encode(), "text/plain")))

        files.append(
            ("last_used", (None, self.last_used.isoformat().encode(), "text/plain"))
        )

        if not isinstance(self.times_used, Unset):
            files.append(
                ("times_used", (None, str(self.times_used).encode(), "text/plain"))
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.address import Address

        d = dict(src_dict)
        id = d.pop("id")

        address = d.pop("address")

        address_detail = Address.from_dict(d.pop("address_detail"))

        customer = d.pop("customer")

        last_used = isoparse(d.pop("last_used"))

        times_used = d.pop("times_used", UNSET)

        address_usage_by_customer = cls(
            id=id,
            address=address,
            address_detail=address_detail,
            customer=customer,
            last_used=last_used,
            times_used=times_used,
        )

        address_usage_by_customer.additional_properties = d
        return address_usage_by_customer

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
