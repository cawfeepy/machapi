from __future__ import annotations

import datetime
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from .. import types
from ..models.billing_status_enum import BillingStatusEnum
from ..models.blank_enum import BlankEnum
from ..models.status_enum import StatusEnum
from ..models.trailer_type_enum import TrailerTypeEnum
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.leg import Leg


T = TypeVar("T", bound="PatchedLoad")


@_attrs_define
class PatchedLoad:
    """Declarative mixin that handles nested writes automatically using 'nested_relations'.

    Features:
    - Atomic Transactions: Entire operation is all-or-nothing.
    - Order Preservation: Processes nested relations in the order defined.
    - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

        Attributes:
            id (int | Unset):
            reference_number (str | Unset):
            bol_number (str | Unset):
            customer (int | None | Unset):
            status (StatusEnum | Unset): * `pending` - Pending
                * `assigned` - Assigned
                * `dispatched` - Dispatched
                * `in_transit` - In Transit
                * `times_missing` - Times Missing
                * `rescheduled` - Rescheduled
                * `claim` - Claim
                * `at_hub` - At Hub
                * `complete` - Complete
                * `tonu` - TONU
            billing_status (BillingStatusEnum | Unset): * `paperwork_pending` - Paperwork Pending
                * `pending_delivery` - Pending Delivery
                * `billed` - Billed
                * `rejected` - Rejected
                * `paid` - Paid
            trailer_type (BlankEnum | TrailerTypeEnum | Unset):
            legs (list[Leg] | Unset):
            created_at (datetime.datetime | Unset):
            updated_at (datetime.datetime | Unset):
    """

    id: int | Unset = UNSET
    reference_number: str | Unset = UNSET
    bol_number: str | Unset = UNSET
    customer: int | None | Unset = UNSET
    status: StatusEnum | Unset = UNSET
    billing_status: BillingStatusEnum | Unset = UNSET
    trailer_type: BlankEnum | TrailerTypeEnum | Unset = UNSET
    legs: list[Leg] | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        reference_number = self.reference_number

        bol_number = self.bol_number

        customer: int | None | Unset
        if isinstance(self.customer, Unset):
            customer = UNSET
        else:
            customer = self.customer

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        billing_status: str | Unset = UNSET
        if not isinstance(self.billing_status, Unset):
            billing_status = self.billing_status.value

        trailer_type: str | Unset
        if isinstance(self.trailer_type, Unset):
            trailer_type = UNSET
        elif isinstance(self.trailer_type, TrailerTypeEnum):
            trailer_type = self.trailer_type.value
        else:
            trailer_type = self.trailer_type.value

        legs: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.legs, Unset):
            legs = []
            for legs_item_data in self.legs:
                legs_item = legs_item_data.to_dict()
                legs.append(legs_item)

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if reference_number is not UNSET:
            field_dict["reference_number"] = reference_number
        if bol_number is not UNSET:
            field_dict["bol_number"] = bol_number
        if customer is not UNSET:
            field_dict["customer"] = customer
        if status is not UNSET:
            field_dict["status"] = status
        if billing_status is not UNSET:
            field_dict["billing_status"] = billing_status
        if trailer_type is not UNSET:
            field_dict["trailer_type"] = trailer_type
        if legs is not UNSET:
            field_dict["legs"] = legs
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []

        if not isinstance(self.id, Unset):
            files.append(("id", (None, str(self.id).encode(), "text/plain")))

        if not isinstance(self.reference_number, Unset):
            files.append(
                (
                    "reference_number",
                    (None, str(self.reference_number).encode(), "text/plain"),
                )
            )

        if not isinstance(self.bol_number, Unset):
            files.append(
                ("bol_number", (None, str(self.bol_number).encode(), "text/plain"))
            )

        if not isinstance(self.customer, Unset):
            if isinstance(self.customer, int):
                files.append(
                    ("customer", (None, str(self.customer).encode(), "text/plain"))
                )
            else:
                files.append(
                    ("customer", (None, str(self.customer).encode(), "text/plain"))
                )

        if not isinstance(self.status, Unset):
            files.append(
                ("status", (None, str(self.status.value).encode(), "text/plain"))
            )

        if not isinstance(self.billing_status, Unset):
            files.append(
                (
                    "billing_status",
                    (None, str(self.billing_status.value).encode(), "text/plain"),
                )
            )

        if not isinstance(self.trailer_type, Unset):
            if isinstance(self.trailer_type, TrailerTypeEnum):
                files.append(
                    (
                        "trailer_type",
                        (None, str(self.trailer_type.value).encode(), "text/plain"),
                    )
                )
            else:
                files.append(
                    (
                        "trailer_type",
                        (None, str(self.trailer_type.value).encode(), "text/plain"),
                    )
                )

        if not isinstance(self.legs, Unset):
            for legs_item_element in self.legs:
                files.append(
                    (
                        "legs",
                        (
                            None,
                            json.dumps(legs_item_element.to_dict()).encode(),
                            "application/json",
                        ),
                    )
                )

        if not isinstance(self.created_at, Unset):
            files.append(
                (
                    "created_at",
                    (None, self.created_at.isoformat().encode(), "text/plain"),
                )
            )

        if not isinstance(self.updated_at, Unset):
            files.append(
                (
                    "updated_at",
                    (None, self.updated_at.isoformat().encode(), "text/plain"),
                )
            )

        for prop_name, prop in self.additional_properties.items():
            files.append((prop_name, (None, str(prop).encode(), "text/plain")))

        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.leg import Leg

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        reference_number = d.pop("reference_number", UNSET)

        bol_number = d.pop("bol_number", UNSET)

        def _parse_customer(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        customer = _parse_customer(d.pop("customer", UNSET))

        _status = d.pop("status", UNSET)
        status: StatusEnum | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = StatusEnum(_status)

        _billing_status = d.pop("billing_status", UNSET)
        billing_status: BillingStatusEnum | Unset
        if isinstance(_billing_status, Unset):
            billing_status = UNSET
        else:
            billing_status = BillingStatusEnum(_billing_status)

        def _parse_trailer_type(data: object) -> BlankEnum | TrailerTypeEnum | Unset:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                trailer_type_type_0 = TrailerTypeEnum(data)

                return trailer_type_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, str):
                raise TypeError()
            trailer_type_type_1 = BlankEnum(data)

            return trailer_type_type_1

        trailer_type = _parse_trailer_type(d.pop("trailer_type", UNSET))

        _legs = d.pop("legs", UNSET)
        legs: list[Leg] | Unset = UNSET
        if _legs is not UNSET:
            legs = []
            for legs_item_data in _legs:
                legs_item = Leg.from_dict(legs_item_data)

                legs.append(legs_item)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = isoparse(_created_at)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = isoparse(_updated_at)

        patched_load = cls(
            id=id,
            reference_number=reference_number,
            bol_number=bol_number,
            customer=customer,
            status=status,
            billing_status=billing_status,
            trailer_type=trailer_type,
            legs=legs,
            created_at=created_at,
            updated_at=updated_at,
        )

        patched_load.additional_properties = d
        return patched_load

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
