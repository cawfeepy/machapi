from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.leg import Leg
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: int,
    *,
    body: Leg | Leg | Leg | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/legs/{id}/".format(
            id=quote(str(id), safe=""),
        ),
    }

    if isinstance(body, Leg):
        if not isinstance(body, Unset):
            _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, Leg):
        if not isinstance(body, Unset):
            _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, Leg):
        if not isinstance(body, Unset):
            _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Leg | None:
    if response.status_code == 200:
        response_200 = Leg.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Leg]:
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
    body: Leg | Leg | Leg | Unset = UNSET,
) -> Response[Leg]:
    """ViewSet for viewing and editing Leg instances.

    Provides standard CRUD operations for legs.

    Args:
        id (int):
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Leg]
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
    body: Leg | Leg | Leg | Unset = UNSET,
) -> Leg | None:
    """ViewSet for viewing and editing Leg instances.

    Provides standard CRUD operations for legs.

    Args:
        id (int):
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Leg
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
    body: Leg | Leg | Leg | Unset = UNSET,
) -> Response[Leg]:
    """ViewSet for viewing and editing Leg instances.

    Provides standard CRUD operations for legs.

    Args:
        id (int):
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Leg]
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
    body: Leg | Leg | Leg | Unset = UNSET,
) -> Leg | None:
    """ViewSet for viewing and editing Leg instances.

    Provides standard CRUD operations for legs.

    Args:
        id (int):
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Leg | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Leg
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            body=body,
        )
    ).parsed
