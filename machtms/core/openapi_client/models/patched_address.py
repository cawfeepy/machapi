from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedAddress")


@_attrs_define
class PatchedAddress:
    """Serializer for the Address model.

    Attributes:
        id (int | Unset):
        street (str | Unset):
        city (str | Unset):
        state (str | Unset):
        zip_code (str | Unset):
        country (str | Unset):
        latitude (None | str | Unset):
        longitude (None | str | Unset):
    """

    id: int | Unset = UNSET
    street: str | Unset = UNSET
    city: str | Unset = UNSET
    state: str | Unset = UNSET
    zip_code: str | Unset = UNSET
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
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if street is not UNSET:
            field_dict["street"] = street
        if city is not UNSET:
            field_dict["city"] = city
        if state is not UNSET:
            field_dict["state"] = state
        if zip_code is not UNSET:
            field_dict["zip_code"] = zip_code
        if country is not UNSET:
            field_dict["country"] = country
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.street, Unset):
            files.append(("street", (None, str(self.street).encode(), "text/plain")))

        if not isinstance(self.city, Unset):
            files.append(("city", (None, str(self.city).encode(), "text/plain")))

        if not isinstance(self.state, Unset):
            files.append(("state", (None, str(self.state).encode(), "text/plain")))

        if not isinstance(self.zip_code, Unset):
            files.append(
                ("zip_code", (None, str(self.zip_code).encode(), "text/plain"))
            )

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
        id = d.pop("id", UNSET)

        street = d.pop("street", UNSET)

        city = d.pop("city", UNSET)

        state = d.pop("state", UNSET)

        zip_code = d.pop("zip_code", UNSET)

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

        patched_address = cls(
            id=id,
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            latitude=latitude,
            longitude=longitude,
        )

        patched_address.additional_properties = d
        return patched_address

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
