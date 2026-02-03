from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedDriver")


@_attrs_define
class PatchedDriver:
    """Serializer for Driver model.

    Attributes:
        id (int | Unset):
        first_name (str | Unset):
        last_name (str | Unset):
        full_name (str | Unset):
        phone_number (str | Unset):
        email (str | Unset):
        address (int | None | Unset):
        carrier (int | None | Unset):
    """

    id: int | Unset = UNSET
    first_name: str | Unset = UNSET
    last_name: str | Unset = UNSET
    full_name: str | Unset = UNSET
    phone_number: str | Unset = UNSET
    email: str | Unset = UNSET
    address: int | None | Unset = UNSET
    carrier: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        first_name = self.first_name

        last_name = self.last_name

        full_name = self.full_name

        phone_number = self.phone_number

        email = self.email

        address: int | None | Unset
        if isinstance(self.address, Unset):
            address = UNSET
        else:
            address = self.address

        carrier: int | None | Unset
        if isinstance(self.carrier, Unset):
            carrier = UNSET
        else:
            carrier = self.carrier

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if first_name is not UNSET:
            field_dict["first_name"] = first_name
        if last_name is not UNSET:
            field_dict["last_name"] = last_name
        if full_name is not UNSET:
            field_dict["full_name"] = full_name
        if phone_number is not UNSET:
            field_dict["phone_number"] = phone_number
        if email is not UNSET:
            field_dict["email"] = email
        if address is not UNSET:
            field_dict["address"] = address
        if carrier is not UNSET:
            field_dict["carrier"] = carrier

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.first_name, Unset):
            files.append(
                ("first_name", (None, str(self.first_name).encode(), "text/plain"))
            )

        if not isinstance(self.last_name, Unset):
            files.append(
                ("last_name", (None, str(self.last_name).encode(), "text/plain"))
            )

        if not isinstance(self.full_name, Unset):
            files.append(
                ("full_name", (None, str(self.full_name).encode(), "text/plain"))
            )

        if not isinstance(self.phone_number, Unset):
            files.append(
                ("phone_number", (None, str(self.phone_number).encode(), "text/plain"))
            )

        if not isinstance(self.email, Unset):
            files.append(("email", (None, str(self.email).encode(), "text/plain")))

        if not isinstance(self.address, Unset):
            if isinstance(self.address, int):
                files.append(
                    ("address", (None, str(self.address).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("address", (None, str(self.address).encode(), "text/plain"))
                )

        if not isinstance(self.carrier, Unset):
            if isinstance(self.carrier, int):
                files.append(
                    ("carrier", (None, str(self.carrier).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("carrier", (None, str(self.carrier).encode(), "text/plain"))
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        first_name = d.pop("first_name", UNSET)

        last_name = d.pop("last_name", UNSET)

        full_name = d.pop("full_name", UNSET)

        phone_number = d.pop("phone_number", UNSET)

        email = d.pop("email", UNSET)

        def _parse_address(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        address = _parse_address(d.pop("address", UNSET))

        def _parse_carrier(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        carrier = _parse_carrier(d.pop("carrier", UNSET))

        patched_driver = cls(
            id=id,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            phone_number=phone_number,
            email=email,
            address=address,
            carrier=carrier,
        )

        patched_driver.additional_properties = d
        return patched_driver

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
