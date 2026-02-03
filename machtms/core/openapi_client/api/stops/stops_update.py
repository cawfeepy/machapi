from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.stop import Stop
from ...types import UNSET, Response


def _get_kwargs(
    id: int,
    *,
    body: Stop | Stop | Stop | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/stops/{id}/".format(
            id=quote(str(id), safe=""),
        ),
    }

    if isinstance(body, Stop):
        _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, Stop):
        _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, Stop):
        _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Stop | None:
    if response.status_code == 200:
        response_200 = Stop.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Stop]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    id: int,
    *,
    client: AuthenticatedClient,
    body: Stop | Stop | Stop | Unset = UNSET,
) -> Response[Stop]:
    """ViewSet for managing stops in transportation routes.

    Provides full CRUD operations for Stop objects.
    Supports searching by address, PO numbers, and stop number.
    Results are ordered by start_range by default.

    Args:
        id (int):
        body (Stop):
        body (Stop):
        body (Stop):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Stop]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: int,
    *,
    client: AuthenticatedClient,
    body: Stop | Stop | Stop | Unset = UNSET,
) -> Stop | None:
    """ViewSet for managing stops in transportation routes.

    Provides full CRUD operations for Stop objects.
    Supports searching by address, PO numbers, and stop number.
    Results are ordered by start_range by default.

    Args:
        id (int):
        body (Stop):
        body (Stop):
        body (Stop):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Stop
    """

    return sync_detailed(
        id=id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    id: int,
    *,
    client: AuthenticatedClient,
    body: Stop | Stop | Stop | Unset = UNSET,
) -> Response[Stop]:
    """ViewSet for managing stops in transportation routes.

    Provides full CRUD operations for Stop objects.
    Supports searching by address, PO numbers, and stop number.
    Results are ordered by start_range by default.

    Args:
        id (int):
        body (Stop):
        body (Stop):
        body (Stop):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Stop]
    """

    kwargs = _get_kwargs(
        id=id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: int,
    *,
    client: AuthenticatedClient,
    body: Stop | Stop | Stop | Unset = UNSET,
) -> Stop | None:
    """ViewSet for managing stops in transportation routes.

    Provides full CRUD operations for Stop objects.
    Supports searching by address, PO numbers, and stop number.
    Results are ordered by start_range by default.

    Args:
        id (int):
        body (Stop):
        body (Stop):
        body (Stop):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Stop
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
