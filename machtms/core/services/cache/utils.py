import logging
import hashlib
import json
from typing import Optional, Tuple, Any
from django.core.cache import cache as C
import logging

logger = logging.getLogger(__name__)

class CacheKeyIterator:
    def __init__(self, cache_client, partial_key, model_id=None):
        """
        :param cache_client: The cache instance (django_redis client).
        :param partial_key: The key pattern to search in the cache.
        :param model_id: Optional model_id to filter by.
        """
        self.cache_client = cache_client
        self.cache_keys = list(cache_client.iter_keys(partial_key))  # Get cache keys
        self.model_id = model_id
        self.index = 0  # Track iteration progress

    def __iter__(self):
        """Returns an iterator object (itself)."""
        return self

    def __next__(self):
        """Fetches the next valid cache entry."""
        while self.index < len(self.cache_keys):
            key = self.cache_keys[self.index]
            self.index += 1  # Move to the next key

            try:
                cached = self.cache_client.get(key)
                if not cached:
                    continue  # Skip if cache is empty or None

                hashed = cached.get("hash")
                id_list = cached.get("id_list")

                if hashed is None or id_list is None:
                    continue  # Skip if missing required fields

                if self.model_id is not None and self.model_id not in set(id_list):
                    continue  # Skip if model_id filtering is applied and doesn't match

                return key, hashed  # Return the relevant key-hash pair

            except Exception as e:
                logging.debug(f"Error processing key {key}: {e}")
                continue  # Skip and move to the next iteration

        raise StopIteration()  # No more items to iterate over


def get_organization_id(org_id=None):
    if org_id is None:
        return "_"
    return org_id


def set_hash(data):
    H = hashlib.sha256
    encoded = json.dumps(data).encode('utf-8')
    return H(encoded).hexdigest()



def is_hash_changed(cached_hash, incoming):
    return cached_hash != set_hash(incoming)


def set_cache_key(
        organization_id: Optional[str] = None,
        reverse_key: Optional[str] = None,
        query_params: Optional[str] = None
        ):
    assert (organization_id and reverse_key) is not None
    return f"{organization_id}:{reverse_key}:{query_params}"


def get_cache(
        organization_id: Optional[str] = None,
        reverse_key: Optional[str] = None,
        query_params: Optional[str] = None,
        ) -> Tuple[str, Any]:

    org_id = get_organization_id(organization_id)

    key = set_cache_key(
            organization_id=org_id,
            reverse_key=reverse_key,
            query_params=query_params
            )
    logger.info(key)

    try:
        data = C.get(key)
    except Exception as e:
        print(f"within get_cache function:{e}")
        data = None

    return key, data


def set_search_query_cache(key:str, data=None, id_list=None, timeout=43200):
    assert (data, id_list) is not None
    to_cache = {
            "data": data,
            "id_list": id_list,
            "hash": set_hash(data)
            }
    C.set(key, to_cache, timeout=timeout)
