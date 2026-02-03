from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from .. import types
from ..models.action_enum import ActionEnum
from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchedStop")


@_attrs_define
class PatchedStop:
    """
    Attributes:
        id (int | Unset):
        leg (int | Unset):
        stop_number (int | Unset): Order of this stop within the leg
        start_range (datetime.datetime | Unset): The earliest time the stop can occur
        end_range (datetime.datetime | None | Unset): The latest time the stop can occur (optional)
        timestamp (datetime.datetime | Unset): When this stop was created
        action (ActionEnum | Unset): * `LL` - LIVE LOAD
            * `LU` - LIVE UNLOAD
            * `HL` - HOOK LOADED
            * `LD` - DROP LOADED
            * `EMPP` - EMPTY PICKUP
            * `EMPD` - EMPTY DROP
            * `HUBP` - HUB PICKUP
            * `HUBD` - HUB DROPOFF
        po_numbers (str | Unset): Purchase order numbers associated with this stop
        driver_notes (str | Unset): Notes for the driver regarding this stop
        address (int | Unset): The address where this stop takes place
    """

    id: int | Unset = UNSET
    leg: int | Unset = UNSET
    stop_number: int | Unset = UNSET
    start_range: datetime.datetime | Unset = UNSET
    end_range: datetime.datetime | None | Unset = UNSET
    timestamp: datetime.datetime | Unset = UNSET
    action: ActionEnum | Unset = UNSET
    po_numbers: str | Unset = UNSET
    driver_notes: str | Unset = UNSET
    address: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        leg = self.leg

        stop_number = self.stop_number

        start_range: str | Unset = UNSET
        if not isinstance(self.start_range, Unset):
            start_range = self.start_range.isoformat()

        end_range: None | str | Unset
        if isinstance(self.end_range, Unset):
            end_range = UNSET
        elif isinstance(self.end_range, datetime.datetime):
            end_range = self.end_range.isoformat()
        else:
            end_range = self.end_range

        timestamp: str | Unset = UNSET
        if not isinstance(self.timestamp, Unset):
            timestamp = self.timestamp.isoformat()

        action: str | Unset = UNSET
        if not isinstance(self.action, Unset):
            action = self.action.value

        po_numbers = self.po_numbers

        driver_notes = self.driver_notes

        address = self.address

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if leg is not UNSET:
            field_dict["leg"] = leg
        if stop_number is not UNSET:
            field_dict["stop_number"] = stop_number
        if start_range is not UNSET:
            field_dict["start_range"] = start_range
        if end_range is not UNSET:
            field_dict["end_range"] = end_range
        if timestamp is not UNSET:
            field_dict["timestamp"] = timestamp
        if action is not UNSET:
            field_dict["action"] = action
        if po_numbers is not UNSET:
            field_dict["po_numbers"] = po_numbers
        if driver_notes is not UNSET:
            field_dict["driver_notes"] = driver_notes
        if address is not UNSET:
            field_dict["address"] = address

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.leg, Unset):
            files.append(("leg", (None, str(self.leg).encode(), "text/plain")))

        if not isinstance(self.stop_number, Unset):
            files.append(
                ("stop_number", (None, str(self.stop_number).encode(), "text/plain"))
            )

        if not isinstance(self.start_range, Unset):
            files.append(
                (
                    "start_range",
                    (None, self.start_range.isoformat().encode(), "text/plain"),
                )
            )

        if not isinstance(self.end_range, Unset):
            if isinstance(self.end_range, datetime.datetime):
                files.append(
                    (
                        "end_range",
                        (None, self.end_range.isoformat().encode(), "text/plain"),
                    )
                )
            else:
                files.append(
                    ("end_range", (None, str(self.end_range).encode(), "text/plain"))
                )

        if not isinstance(self.timestamp, Unset):
            files.append(
                ("timestamp", (None, self.timestamp.isoformat().encode(), "text/plain"))
            )

        if not isinstance(self.action, Unset):
            files.append(
                ("action", (None, str(self.action.value).encode(), "text/plain"))
            )

        if not isinstance(self.po_numbers, Unset):
            files.append(
                ("po_numbers", (None, str(self.po_numbers).encode(), "text/plain"))
            )

        if not isinstance(self.driver_notes, Unset):
            files.append(
                ("driver_notes", (None, str(self.driver_notes).encode(), "text/plain"))
            )

        if not isinstance(self.address, Unset):
            files.append(("address", (None, str(self.address).encode(), "text/plain")))

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        leg = d.pop("leg", UNSET)

        stop_number = d.pop("stop_number", UNSET)

        _start_range = d.pop("start_range", UNSET)
        start_range: datetime.datetime | Unset
        if isinstance(_start_range, Unset):
            start_range = UNSET
        else:
            start_range = isoparse(_start_range)

        def _parse_end_range(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                end_range_type_0 = isoparse(data)

                return end_range_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        end_range = _parse_end_range(d.pop("end_range", UNSET))

        _timestamp = d.pop("timestamp", UNSET)
        timestamp: datetime.datetime | Unset
        if isinstance(_timestamp, Unset):
            timestamp = UNSET
        else:
            timestamp = isoparse(_timestamp)

        _action = d.pop("action", UNSET)
        action: ActionEnum | Unset
        if isinstance(_action, Unset):
            action = UNSET
        else:
            action = ActionEnum(_action)

        po_numbers = d.pop("po_numbers", UNSET)

        driver_notes = d.pop("driver_notes", UNSET)

        address = d.pop("address", UNSET)

        patched_stop = cls(
            id=id,
            leg=leg,
            stop_number=stop_number,
            start_range=start_range,
            end_range=end_range,
            timestamp=timestamp,
            action=action,
            po_numbers=po_numbers,
            driver_notes=driver_notes,
            address=address,
        )

        patched_stop.additional_properties = d
        return patched_stop

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
