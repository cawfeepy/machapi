from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..models.payment_type_enum import PaymentTypeEnum
from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedCustomerAP")


@_attrs_define
class PatchedCustomerAP:
    """Serializer for CustomerAP model.

    Attributes:
        id (int | Unset):
        email (str | Unset):
        phone_number (str | Unset):
        payment_type (PaymentTypeEnum | Unset): * `quickpay` - Quick Pay
            * `standard` - Standard Pay
    """

    id: int | Unset = UNSET
    email: str | Unset = UNSET
    phone_number: str | Unset = UNSET
    payment_type: PaymentTypeEnum | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        email = self.email

        phone_number = self.phone_number

        payment_type: str | Unset = UNSET
        if not isinstance(self.payment_type, Unset):
            payment_type = self.payment_type.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if email is not UNSET:
            field_dict["email"] = email
        if phone_number is not UNSET:
            field_dict["phone_number"] = phone_number
        if payment_type is not UNSET:
            field_dict["payment_type"] = payment_type

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.email, Unset):
            files.append(("email", (None, str(self.email).encode(), "text/plain")))

        if not isinstance(self.phone_number, Unset):
            files.append(
                ("phone_number", (None, str(self.phone_number).encode(), "text/plain"))
            )

        if not isinstance(self.payment_type, Unset):
            files.append(
                (
                    "payment_type",
                    (None, str(self.payment_type.value).encode(), "text/plain"),
                )
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        email = d.pop("email", UNSET)

        phone_number = d.pop("phone_number", UNSET)

        _payment_type = d.pop("payment_type", UNSET)
        payment_type: PaymentTypeEnum | Unset
        if isinstance(_payment_type, Unset):
            payment_type = UNSET
        else:
            payment_type = PaymentTypeEnum(_payment_type)

        patched_customer_ap = cls(
            id=id,
            email=email,
            phone_number=phone_number,
            payment_type=payment_type,
        )

        patched_customer_ap.additional_properties = d
        return patched_customer_ap

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
