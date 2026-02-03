from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.driver import Driver
from ...models.patched_driver import PatchedDriver
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: int,
    *,
    body: PatchedDriver | PatchedDriver | PatchedDriver | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/drivers/{id}/".format(
            id=quote(str(id), safe=""),
        ),
    }

    if isinstance(body, PatchedDriver):
        if not isinstance(body, Unset):
            _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, PatchedDriver):
        if not isinstance(body, Unset):
            _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, PatchedDriver):
        if not isinstance(body, Unset):
            _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Driver | None:
    if response.status_code == 200:
        response_200 = Driver.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Driver]:
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
    body: PatchedDriver | PatchedDriver | PatchedDriver | Unset = UNSET,
) -> Response[Driver]:
    """ViewSet for Driver model.
    Provides CRUD operations for drivers.

    Args:
        id (int):
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Driver]
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
    body: PatchedDriver | PatchedDriver | PatchedDriver | Unset = UNSET,
) -> Driver | None:
    """ViewSet for Driver model.
    Provides CRUD operations for drivers.

    Args:
        id (int):
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Driver
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
    body: PatchedDriver | PatchedDriver | PatchedDriver | Unset = UNSET,
) -> Response[Driver]:
    """ViewSet for Driver model.
    Provides CRUD operations for drivers.

    Args:
        id (int):
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Driver]
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
    body: PatchedDriver | PatchedDriver | PatchedDriver | Unset = UNSET,
) -> Driver | None:
    """ViewSet for Driver model.
    Provides CRUD operations for drivers.

    Args:
        id (int):
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.
        body (PatchedDriver | Unset): Serializer for Driver model.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Driver
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
