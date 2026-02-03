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

T = TypeVar("T", bound="Stop")


@_attrs_define
class Stop:
    """
    Attributes:
        leg (int):
        stop_number (int): Order of this stop within the leg
        start_range (datetime.datetime): The earliest time the stop can occur
        action (ActionEnum): * `LL` - LIVE LOAD
            * `LU` - LIVE UNLOAD
            * `HL` - HOOK LOADED
            * `LD` - DROP LOADED
            * `EMPP` - EMPTY PICKUP
            * `EMPD` - EMPTY DROP
            * `HUBP` - HUB PICKUP
            * `HUBD` - HUB DROPOFF
        address (int): The address where this stop takes place
        id (int | Unset):
        end_range (datetime.datetime | None | Unset): The latest time the stop can occur (optional)
        timestamp (datetime.datetime | Unset): When this stop was created
        po_numbers (str | Unset): Purchase order numbers associated with this stop
        driver_notes (str | Unset): Notes for the driver regarding this stop
    """

    leg: int
    stop_number: int
    start_range: datetime.datetime
    action: ActionEnum
    address: int
    id: int | Unset = UNSET
    end_range: datetime.datetime | None | Unset = UNSET
    timestamp: datetime.datetime | Unset = UNSET
    po_numbers: str | Unset = UNSET
    driver_notes: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        leg = self.leg

        stop_number = self.stop_number

        start_range = self.start_range.isoformat()

        action = self.action.value

        address = self.address

        id = self.id

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

        po_numbers = self.po_numbers

        driver_notes = self.driver_notes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "leg": leg,
                "stop_number": stop_number,
                "start_range": start_range,
                "action": action,
                "address": address,
            }
        )
        if id is not UNSET:
            field_dict["id"] = id
        if end_range is not UNSET:
            field_dict["end_range"] = end_range
        if timestamp is not UNSET:
            field_dict["timestamp"] = timestamp
        if po_numbers is not UNSET:
            field_dict["po_numbers"] = po_numbers
        if driver_notes is not UNSET:
            field_dict["driver_notes"] = driver_notes

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        files.append(("leg", (None, str(self.leg).encode(), "text/plain")))

        files.append(
            ("stop_number", (None, str(self.stop_number).encode(), "text/plain"))
        )

        files.append(
            ("start_range", (None, self.start_range.isoformat().encode(), "text/plain"))
        )

        files.append(("action", (None, str(self.action.value).encode(), "text/plain")))

        files.append(("address", (None, str(self.address).encode(), "text/plain")))

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

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

        if not isinstance(self.po_numbers, Unset):
            files.append(
                ("po_numbers", (None, str(self.po_numbers).encode(), "text/plain"))
            )

        if not isinstance(self.driver_notes, Unset):
            files.append(
                ("driver_notes", (None, str(self.driver_notes).encode(), "text/plain"))
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        leg = d.pop("leg")

        stop_number = d.pop("stop_number")

        start_range = isoparse(d.pop("start_range"))

        action = ActionEnum(d.pop("action"))

        address = d.pop("address")

        id = d.pop("id", UNSET)

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

        po_numbers = d.pop("po_numbers", UNSET)

        driver_notes = d.pop("driver_notes", UNSET)

        stop = cls(
            leg=leg,
            stop_number=stop_number,
            start_range=start_range,
            action=action,
            address=address,
            id=id,
            end_range=end_range,
            timestamp=timestamp,
            po_numbers=po_numbers,
            driver_notes=driver_notes,
        )

        stop.additional_properties = d
        return stop

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
