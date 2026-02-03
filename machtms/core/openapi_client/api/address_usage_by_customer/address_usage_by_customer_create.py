from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.address_usage_by_customer import AddressUsageByCustomer
from ...types import UNSET, Response


def _get_kwargs(
    *,
    body: AddressUsageByCustomer
    | AddressUsageByCustomer
    | AddressUsageByCustomer
    | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/address-usage-by-customer/",
    }

    if isinstance(body, AddressUsageByCustomer):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, AddressUsageByCustomer):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, AddressUsageByCustomer):
        _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AddressUsageByCustomer | None:
    if response.status_code == 201:
        response_201 = AddressUsageByCustomer.from_dict(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AddressUsageByCustomer]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: AddressUsageByCustomer
    | AddressUsageByCustomer
    | AddressUsageByCustomer
    | Unset = UNSET,
) -> Response[AddressUsageByCustomer]:
    """ViewSet for managing AddressUsageByCustomer objects.
    Tracks the relationship between addresses and customers,
    including usage statistics.

    Args:
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddressUsageByCustomer]
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
    body: AddressUsageByCustomer
    | AddressUsageByCustomer
    | AddressUsageByCustomer
    | Unset = UNSET,
) -> AddressUsageByCustomer | None:
    """ViewSet for managing AddressUsageByCustomer objects.
    Tracks the relationship between addresses and customers,
    including usage statistics.

    Args:
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddressUsageByCustomer
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: AddressUsageByCustomer
    | AddressUsageByCustomer
    | AddressUsageByCustomer
    | Unset = UNSET,
) -> Response[AddressUsageByCustomer]:
    """ViewSet for managing AddressUsageByCustomer objects.
    Tracks the relationship between addresses and customers,
    including usage statistics.

    Args:
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AddressUsageByCustomer]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: AddressUsageByCustomer
    | AddressUsageByCustomer
    | AddressUsageByCustomer
    | Unset = UNSET,
) -> AddressUsageByCustomer | None:
    """ViewSet for managing AddressUsageByCustomer objects.
    Tracks the relationship between addresses and customers,
    including usage statistics.

    Args:
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.
        body (AddressUsageByCustomer): Serializer for the AddressUsageByCustomer model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AddressUsageByCustomer
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
