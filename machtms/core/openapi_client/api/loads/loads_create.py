from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.load import Load
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: Load | Load | Load | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/loads/",
    }

    if isinstance(body, Load):
        if not isinstance(body, Unset):
            _kwargs["json"] = body.to_dict()

        headers["Content-Type"] = "application/json"
    if isinstance(body, Load):
        if not isinstance(body, Unset):
            _kwargs["data"] = body.to_dict()

        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if isinstance(body, Load):
        if not isinstance(body, Unset):
            _kwargs["files"] = body.to_multipart()

        headers["Content-Type"] = "multipart/form-data"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Load | None:
    if response.status_code == 201:
        response_201 = Load.from_dict(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Load]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: Load | Load | Load | Unset = UNSET,
) -> Response[Load]:
    """ViewSet for managing Load objects.

    Provides CRUD operations for loads with organization-based filtering.

    Args:
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Load]
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
    body: Load | Load | Load | Unset = UNSET,
) -> Load | None:
    """ViewSet for managing Load objects.

    Provides CRUD operations for loads with organization-based filtering.

    Args:
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Load
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: Load | Load | Load | Unset = UNSET,
) -> Response[Load]:
    """ViewSet for managing Load objects.

    Provides CRUD operations for loads with organization-based filtering.

    Args:
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Load]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: Load | Load | Load | Unset = UNSET,
) -> Load | None:
    """ViewSet for managing Load objects.

    Provides CRUD operations for loads with organization-based filtering.

    Args:
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
        body (Load | Unset): Declarative mixin that handles nested writes automatically using
            'nested_relations'.

            Features:
            - Atomic Transactions: Entire operation is all-or-nothing.
            - Order Preservation: Processes nested relations in the order defined.
            - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Load
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
