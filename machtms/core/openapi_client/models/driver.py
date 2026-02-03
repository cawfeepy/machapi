from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

T = TypeVar("T", bound="Driver")


@_attrs_define
class Driver:
    """Serializer for Driver model.

    Attributes:
        id (int):
        first_name (str):
        last_name (str):
        full_name (str):
        phone_number (str):
        email (str | Unset):
        address (int | None | Unset):
        carrier (int | None | Unset):
    """

    id: int
    first_name: str
    last_name: str
    full_name: str
    phone_number: str
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
        field_dict.update(
            {
                "id": id,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "phone_number": phone_number,
            }
        )
        if email is not UNSET:
            field_dict["email"] = email
        if address is not UNSET:
            field_dict["address"] = address
        if carrier is not UNSET:
            field_dict["carrier"] = carrier

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("id", (None, str(self.id).encode(), "text/plain")))

        files.append(
            ("first_name", (None, str(self.first_name).encode(), "text/plain"))
        )

        files.append(("last_name", (None, str(self.last_name).encode(), "text/plain")))

        files.append(("full_name", (None, str(self.full_name).encode(), "text/plain")))

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
        id = d.pop("id")

        first_name = d.pop("first_name")

        last_name = d.pop("last_name")

        full_name = d.pop("full_name")

        phone_number = d.pop("phone_number")

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

        driver = cls(
            id=id,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            phone_number=phone_number,
            email=email,
            address=address,
            carrier=carrier,
        )

        driver.additional_properties = d
        return driver

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
