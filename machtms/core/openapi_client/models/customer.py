from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.customer_ap import CustomerAP
    from ..models.customer_representative import CustomerRepresentative


T = TypeVar("T", bound="Customer")


@_attrs_define
class Customer:
    """Serializer for Customer model.

    Attributes:
        id (int):
        customer_name (str):
        representatives (list[CustomerRepresentative]):
        ap_emails (list[CustomerAP]):
        address (int | None | Unset):
        phone_number (str | Unset):
        representative_ids (list[int] | Unset):
        ap_email_ids (list[int] | Unset):
    """

    id: int
    customer_name: str
    representatives: list[CustomerRepresentative]
    ap_emails: list[CustomerAP]
    address: int | None | Unset = UNSET
    phone_number: str | Unset = UNSET
    representative_ids: list[int] | Unset = UNSET
    ap_email_ids: list[int] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        customer_name = self.customer_name

        representatives = []
        for representatives_item_data in self.representatives:
            representatives_item = representatives_item_data.to_dict()
            representatives.append(representatives_item)

        ap_emails = []
        for ap_emails_item_data in self.ap_emails:
            ap_emails_item = ap_emails_item_data.to_dict()
            ap_emails.append(ap_emails_item)

        address: int | None | Unset
        if isinstance(self.address, Unset):
            address = UNSET
        else:
            address = self.address

        phone_number = self.phone_number

        representative_ids: list[int] | Unset = UNSET
        if not isinstance(self.representative_ids, Unset):
            representative_ids = self.representative_ids

        ap_email_ids: list[int] | Unset = UNSET
        if not isinstance(self.ap_email_ids, Unset):
            ap_email_ids = self.ap_email_ids

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "customer_name": customer_name,
                "representatives": representatives,
                "ap_emails": ap_emails,
            }
        )
        if address is not UNSET:
            field_dict["address"] = address
        if phone_number is not UNSET:
            field_dict["phone_number"] = phone_number
        if representative_ids is not UNSET:
            field_dict["representative_ids"] = representative_ids
        if ap_email_ids is not UNSET:
            field_dict["ap_email_ids"] = ap_email_ids

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("id", (None, str(self.id).encode(), "text/plain")))

        files.append(
            ("customer_name", (None, str(self.customer_name).encode(), "text/plain"))
        )

        for representatives_item_element in self.representatives:
            files.append(
                (
                    "representatives",
                    (
                        None,
                        json.dumps(representatives_item_element.to_dict()).encode(),
                        "application/json",
                    ),
                )
            )

        for ap_emails_item_element in self.ap_emails:
            files.append(
                (
                    "ap_emails",
                    (
                        None,
                        json.dumps(ap_emails_item_element.to_dict()).encode(),
                        "application/json",
                    ),
                )
            )

        if not isinstance(self.address, Unset):
            if isinstance(self.address, int):
                files.append(
                    ("address", (None, str(self.address).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("address", (None, str(self.address).encode(), "text/plain"))
                )

        if not isinstance(self.phone_number, Unset):
            files.append(
                ("phone_number", (None, str(self.phone_number).encode(), "text/plain"))
            )

        if not isinstance(self.representative_ids, Unset):
            for representative_ids_item_element in self.representative_ids:
                files.append(
                    (
                        "representative_ids",
                        (
                            None,
                            str(representative_ids_item_element).encode(),
                            "text/plain",
                        ),
                    )
                )

        if not isinstance(self.ap_email_ids, Unset):
            for ap_email_ids_item_element in self.ap_email_ids:
                files.append(
                    (
                        "ap_email_ids",
                        (None, str(ap_email_ids_item_element).encode(), "text/plain"),
                    )
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.customer_ap import CustomerAP
        from ..models.customer_representative import CustomerRepresentative

        d = dict(src_dict)
        id = d.pop("id")

        customer_name = d.pop("customer_name")

        representatives = []
        _representatives = d.pop("representatives")
        for representatives_item_data in _representatives:
            representatives_item = CustomerRepresentative.from_dict(
                representatives_item_data
            )

            representatives.append(representatives_item)

        ap_emails = []
        _ap_emails = d.pop("ap_emails")
        for ap_emails_item_data in _ap_emails:
            ap_emails_item = CustomerAP.from_dict(ap_emails_item_data)

            ap_emails.append(ap_emails_item)

        def _parse_address(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        address = _parse_address(d.pop("address", UNSET))

        phone_number = d.pop("phone_number", UNSET)

        representative_ids = cast(list[int], d.pop("representative_ids", UNSET))

        ap_email_ids = cast(list[int], d.pop("ap_email_ids", UNSET))

        customer = cls(
            id=id,
            customer_name=customer_name,
            representatives=representatives,
            ap_emails=ap_emails,
            address=address,
            phone_number=phone_number,
            representative_ids=representative_ids,
            ap_email_ids=ap_email_ids,
        )

        customer.additional_properties = d
        return customer

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
