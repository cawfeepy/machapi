from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.shipment_assignment import ShipmentAssignment
from ...types import UNSET, Response


def _get_kwargs(
    *,
    body: ShipmentAssignment | ShipmentAssignment | ShipmentAssignment | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/shipment-assignments/",
    }

    if isinstance(body, ShipmentAssignment):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, ShipmentAssignment):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, ShipmentAssignment):
        _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ShipmentAssignment | None:
    if response.status_code == 201:
        response_201 = ShipmentAssignment.from_dict(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ShipmentAssignment]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: ShipmentAssignment | ShipmentAssignment | ShipmentAssignment | Unset = UNSET,
) -> Response[ShipmentAssignment]:
    """ViewSet for viewing and editing ShipmentAssignment instances.

    Provides standard CRUD operations for shipment assignments.

    Args:
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ShipmentAssignment]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: ShipmentAssignment | ShipmentAssignment | ShipmentAssignment | Unset = UNSET,
) -> ShipmentAssignment | None:
    """ViewSet for viewing and editing ShipmentAssignment instances.

    Provides standard CRUD operations for shipment assignments.

    Args:
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ShipmentAssignment
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: ShipmentAssignment | ShipmentAssignment | ShipmentAssignment | Unset = UNSET,
) -> Response[ShipmentAssignment]:
    """ViewSet for viewing and editing ShipmentAssignment instances.

    Provides standard CRUD operations for shipment assignments.

    Args:
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ShipmentAssignment]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: ShipmentAssignment | ShipmentAssignment | ShipmentAssignment | Unset = UNSET,
) -> ShipmentAssignment | None:
    """ViewSet for viewing and editing ShipmentAssignment instances.

    Provides standard CRUD operations for shipment assignments.

    Args:
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.
        body (ShipmentAssignment): Serializer for the ShipmentAssignment model.

            Accepts primary keys for carrier, driver, and leg on input.
            Returns full nested JSON for carrier and driver on output.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ShipmentAssignment
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
