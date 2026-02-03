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


T = TypeVar("T", bound="AddressUsageByCustomerAccumulate")


@_attrs_define
class AddressUsageByCustomerAccumulate:
    """Serializer for the AddressUsageByCustomerAccumulate model.

    Attributes:
        id (int):
        address (int):
        address_detail (Address): Serializer for the Address model.
        customer (int):
        last_used (datetime.datetime | Unset):
    """

    id: int
    address: int
    address_detail: Address
    customer: int
    last_used: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        address = self.address

        address_detail = self.address_detail.to_dict()

        customer = self.customer

        last_used: str | Unset = UNSET
        if not isinstance(self.last_used, Unset):
            last_used = self.last_used.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "address": address,
                "address_detail": address_detail,
                "customer": customer,
            }
        )
        if last_used is not UNSET:
            field_dict["last_used"] = last_used

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

        if not isinstance(self.last_used, Unset):
            files.append(
                ("last_used", (None, self.last_used.isoformat().encode(), "text/plain"))
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

        _last_used = d.pop("last_used", UNSET)
        last_used: datetime.datetime | Unset
        if isinstance(_last_used, Unset):
            last_used = UNSET
        else:
            last_used = isoparse(_last_used)

        address_usage_by_customer_accumulate = cls(
            id=id,
            address=address,
            address_detail=address_detail,
            customer=customer,
            last_used=last_used,
        )

        address_usage_by_customer_accumulate.additional_properties = d
        return address_usage_by_customer_accumulate

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
