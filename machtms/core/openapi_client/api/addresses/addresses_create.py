from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.address import Address
from ...types import UNSET, Response


def _get_kwargs(
    *,
    body: Address | Address | Address | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/addresses/",
    }

    if isinstance(body, Address):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, Address):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, Address):
        _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Address | None:
    if response.status_code == 201:
        response_201 = Address.from_dict(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Address]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: Address | Address | Address | Unset = UNSET,
) -> Response[Address]:
    """ViewSet for managing Address objects.
    Provides CRUD operations for addresses in the system.

    Args:
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Address]
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
    body: Address | Address | Address | Unset = UNSET,
) -> Address | None:
    """ViewSet for managing Address objects.
    Provides CRUD operations for addresses in the system.

    Args:
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Address
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: Address | Address | Address | Unset = UNSET,
) -> Response[Address]:
    """ViewSet for managing Address objects.
    Provides CRUD operations for addresses in the system.

    Args:
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Address]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: Address | Address | Address | Unset = UNSET,
) -> Address | None:
    """ViewSet for managing Address objects.
    Provides CRUD operations for addresses in the system.

    Args:
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.
        body (Address): Serializer for the Address model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Address
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
