from collections.abc import Callable

from machtms.backend.loads.models import Load
from .indices import MEILI_INDICES, TMSIndex
from typing import Literal, TypeVar
from .client import meili_client


def get_meili_index(index_name: TMSIndex):
    """
    :param index_name: TMSIndex is an enum class.

    Depending on the DEBUG env variable,
    _index could either return TMS_LOADS or DEBUG_TMS_LOADS

    That's why I wrapped the index_name to _index

    If you try to call meili_client.get_index with TMSIndex directly, you'll get the following:
    ---
    1. Argument of type "TMSIndex" cannot be assigned to parameter "uid" of type "str" in function "get_index"
     'TMSIndex' is not assignable to 'str'
    ---

    """
    return MEILI_INDICES[index_name]


def create_or_update_index_schema(index_name: TMSIndex):
    _index = get_meili_index(index_name)
    try:
        meili_client.get_index(index_name)
    except Exception:
        # If index doesn't exist, create it
        meili_client.create_index(_index, {'primaryKey': 'id'})
    return _index


M = TypeVar('M')
def index_document(
        operation: Literal['add', 'update'],
        model: M,
        index_name: TMSIndex,
        transform: Callable[[M], dict]):
    """
    General function to handle indexing operations in MeiliSearch.

    Usage:
        index_document('add' or 'update', load, TMSIndex.TMS_LOADS, transform_load)
    :param operation: The operation to perform, either 'add' or 'update' :required
    :param model: The model instance to be transformed and indexed. :required
    :param index_name: The name of the index in MeiliSearch. :required
    :param transform: A function that transforms the model instance into a dictionary. :required
    """
    _index = create_or_update_index_schema(index_name)

    index = meili_client.index(_index)
    doc = transform(model)
    if operation == 'add':
        index.add_documents([doc])
    elif operation == 'update':
        index.update_documents([doc])


def delete_document_from_index(index_name: TMSIndex, pk):
    """
    Deletes a single document from MeiliSearch by ID.
    """
    _index = get_meili_index(index_name)
    index = meili_client.index(_index)
    index.delete_document(str(pk))


def delete_entire_index(index_name: TMSIndex):
    """
    Completely deletes the MeiliSearch index. Use with caution!
    """
    _index = get_meili_index(index_name)
    meili_client.delete_index(_index)
