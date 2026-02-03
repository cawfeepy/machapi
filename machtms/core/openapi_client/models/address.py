from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

T = TypeVar("T", bound="Address")


@_attrs_define
class Address:
    """Serializer for the Address model.

    Attributes:
        id (int):
        street (str):
        city (str):
        state (str):
        zip_code (str):
        country (str | Unset):
        latitude (None | str | Unset):
        longitude (None | str | Unset):
    """

    id: int
    street: str
    city: str
    state: str
    zip_code: str
    country: str | Unset = UNSET
    latitude: None | str | Unset = UNSET
    longitude: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        street = self.street

        city = self.city

        state = self.state

        zip_code = self.zip_code

        country = self.country

        latitude: None | str | Unset
        if isinstance(self.latitude, Unset):
            latitude = UNSET
        else:
            latitude = self.latitude

        longitude: None | str | Unset
        if isinstance(self.longitude, Unset):
            longitude = UNSET
        else:
            longitude = self.longitude

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "street": street,
                "city": city,
                "state": state,
                "zip_code": zip_code,
            }
        )
        if country is not UNSET:
            field_dict["country"] = country
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("id", (None, str(self.id).encode(), "text/plain")))

        files.append(("street", (None, str(self.street).encode(), "text/plain")))

        files.append(("city", (None, str(self.city).encode(), "text/plain")))

        files.append(("state", (None, str(self.state).encode(), "text/plain")))

        files.append(("zip_code", (None, str(self.zip_code).encode(), "text/plain")))

        if not isinstance(self.country, Unset):
            files.append(("country", (None, str(self.country).encode(), "text/plain")))

        if not isinstance(self.latitude, Unset):
            if isinstance(self.latitude, str):
                files.append(
                    ("latitude", (None, str(self.latitude).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("latitude", (None, str(self.latitude).encode(), "text/plain"))
                )

        if not isinstance(self.longitude, Unset):
            if isinstance(self.longitude, str):
                files.append(
                    ("longitude", (None, str(self.longitude).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("longitude", (None, str(self.longitude).encode(), "text/plain"))
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        street = d.pop("street")

        city = d.pop("city")

        state = d.pop("state")

        zip_code = d.pop("zip_code")

        country = d.pop("country", UNSET)

        def _parse_latitude(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        latitude = _parse_latitude(d.pop("latitude", UNSET))

        def _parse_longitude(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        longitude = _parse_longitude(d.pop("longitude", UNSET))

        address = cls(
            id=id,
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            latitude=latitude,
            longitude=longitude,
        )

        address.additional_properties = d
        return address

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
