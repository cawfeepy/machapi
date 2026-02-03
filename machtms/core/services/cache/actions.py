"""
actions.py

callable functions for background tasks
they are not celery tasks,
but the actual functions that can run them
"""

import logging
from django.urls import reverse
import requests
from typing import List, Optional, Tuple, TypeAlias
from django.core.cache import cache as C
from machtms.core.utils.url import construct_url_from_cache_key
from . import utils as U

logger = logging.getLogger(__name__)

Key: TypeAlias = str
Hash: TypeAlias = str
KeyHitType: TypeAlias = List[Tuple[Key, Hash]]


def get_cache(organization_id=None, reverse_key=None, query_params=None):
    assert not None in (reverse_key, query_params)
    org_id = U.get_organization_id(organization_id)
    return C.get(f"{org_id}:{reverse_key}:{query_params}")


def update_cache(key_hit: KeyHitType, reverse_check_key):

    for key, hashed in key_hit:
        o_id,_,qparams = key.split(":", 2)

        resolved = reverse(reverse_check_key)
        request_url = construct_url_from_cache_key(
                "http://127.0.0.1:8000",
                resolved,
                qparams,
                organization_id=o_id
                )

        resp = requests.get(request_url)
        if resp.status_code == 200:
            data = resp.json()
            resp_hash = U.set_hash(data)
            if U.is_hash_changed(hashed, resp_hash):
                id_list = data.pop('id_list')
                U.set_search_query_cache(
                        key,
                        data=data,
                        id_list=id_list)


def review_cache(
        organization_id: Optional[str] = None,
        reverse_key: Optional[str] = None,
        model_id: Optional[int] = None,
        ) -> KeyHitType:
    # NOTE: reverse_key must be "{basename}-list"
    # NOTE: all this function does is check if
    # changed model_id is in the cache
    """
        When you create a new model,
        go through the whole cache, based on reverse_key
        make 'check' requests to Django and return <results>
        {
            "data": <data to save>,
            "hash": <computed sha256 hash based on data>,
            "id_list": <primary keys of the data>
        }
    """

    if None in [organization_id, reverse_key]:
        msg = "model_id/organization_id/reverse_key needs to be set"
        raise Exception(msg)

    org_id = U.get_organization_id(organization_id)

    # NOTE: <org_id:{basename}-list:query_params>
    partial_key = f"{org_id}:{reverse_key}*"

    key_hit: KeyHitType = []
    for key, hashed in U.CacheKeyIterator(C, partial_key, model_id=model_id):
        key_hit.append((key, hashed))

    return key_hit

# if data is empty, task will not be called
def save_search_cache(
        data: list[dict],
        id_list: list[int] = [],
        organization_id: Optional[str] = None,
        reverse_key: Optional[str] = None,
        query_params: str = "",
        ):
    """
    - data: paginated response data
    - id_list: model ids contained within the data
    - organization_id: data to which organization it belongs
    - request_full_path: output of request.get_full_path()
    - key_group: which cache group it belongs to
        for example, if it's addresses, then save it
        as '*:addresses:*'
    - Saves to cache in this structure:
    The data is saved to cache in the following structure:
    {
        "data": <data to save>,
        "hash": <computed sha256 hash based on data>,
        "id_list": <primary keys of the queryset>
    }
    """

    if not query_params or not data:
        return
    cache_key, cache_data = U.get_cache(
            organization_id=organization_id,
            reverse_key=reverse_key,
            query_params=query_params
            )

    logger.debug(f"cache_data is None {cache_data is None}")

    if cache_data is None or U.is_hash_changed(cache_data.get("hash"), data):
        U.set_search_query_cache(
                cache_key,
                data=data,
                id_list=id_list)
