from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.address_usage_by_customer_accumulate import (
    AddressUsageByCustomerAccumulate,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    ordering: str | Unset = UNSET,
    search: str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["ordering"] = ordering

    params["search"] = search

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/address-usage-by-customer-accumulate/",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[AddressUsageByCustomerAccumulate] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = AddressUsageByCustomerAccumulate.from_dict(
                response_200_item_data
            )

            response_200.append(response_200_item)

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[list[AddressUsageByCustomerAccumulate]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    ordering: str | Unset = UNSET,
    search: str | Unset = UNSET,
) -> Response[list[AddressUsageByCustomerAccumulate]]:
    """ViewSet for managing AddressUsageByCustomerAccumulate objects.
    Tracks address usage by customer accumulation for analysis.

    Args:
        ordering (str | Unset):
        search (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[AddressUsageByCustomerAccumulate]]
    """

    kwargs = _get_kwargs(
        ordering=ordering,
        search=search,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    ordering: str | Unset = UNSET,
    search: str | Unset = UNSET,
) -> list[AddressUsageByCustomerAccumulate] | None:
    """ViewSet for managing AddressUsageByCustomerAccumulate objects.
    Tracks address usage by customer accumulation for analysis.

    Args:
        ordering (str | Unset):
        search (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[AddressUsageByCustomerAccumulate]
    """

    return sync_detailed(
        client=client,
        ordering=ordering,
        search=search,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    ordering: str | Unset = UNSET,
    search: str | Unset = UNSET,
) -> Response[list[AddressUsageByCustomerAccumulate]]:
    """ViewSet for managing AddressUsageByCustomerAccumulate objects.
    Tracks address usage by customer accumulation for analysis.

    Args:
        ordering (str | Unset):
        search (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[AddressUsageByCustomerAccumulate]]
    """

    kwargs = _get_kwargs(
        ordering=ordering,
        search=search,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    ordering: str | Unset = UNSET,
    search: str | Unset = UNSET,
) -> list[AddressUsageByCustomerAccumulate] | None:
    """ViewSet for managing AddressUsageByCustomerAccumulate objects.
    Tracks address usage by customer accumulation for analysis.

    Args:
        ordering (str | Unset):
        search (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[AddressUsageByCustomerAccumulate]
    """

    return (
        await asyncio_detailed(
            client=client,
            ordering=ordering,
            search=search,
        )
    ).parsed
