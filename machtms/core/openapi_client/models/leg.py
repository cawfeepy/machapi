from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.stop import Stop


T = TypeVar("T", bound="Leg")


@_attrs_define
class Leg:
    """Declarative mixin that handles nested writes automatically using 'nested_relations'.

    Features:
    - Atomic Transactions: Entire operation is all-or-nothing.
    - Order Preservation: Processes nested relations in the order defined.
    - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

        Attributes:
            load (int):
            id (int | Unset):
            stops (list[Stop] | Unset):
    """

    load: int
    id: int | Unset = UNSET
    stops: list[Stop] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        load = self.load

        id = self.id

        stops: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.stops, Unset):
            stops = []
            for stops_item_data in self.stops:
                stops_item = stops_item_data.to_dict()
                stops.append(stops_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "load": load,
            }
        )
        if id is not UNSET:
            field_dict["id"] = id
        if stops is not UNSET:
            field_dict["stops"] = stops

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("load", (None, str(self.load).encode(), "text/plain")))

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.stops, Unset):
            for stops_item_element in self.stops:
                files.append(
                    (
                        "stops",
                        (
                            None,
                            json.dumps(stops_item_element.to_dict()).encode(),
                            "application/json",
                        ),
                    )
                )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.stop import Stop

        d = dict(src_dict)
        load = d.pop("load")

        id = d.pop("id", UNSET)

        _stops = d.pop("stops", UNSET)
        stops: list[Stop] | Unset = UNSET
        if _stops is not UNSET:
            stops = []
            for stops_item_data in _stops:
                stops_item = Stop.from_dict(stops_item_data)

                stops.append(stops_item)

        leg = cls(
            load=load,
            id=id,
            stops=stops,
        )

        leg.additional_properties = d
        return leg

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
