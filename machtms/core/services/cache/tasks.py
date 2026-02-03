from typing import Optional
from celery import shared_task
from machtms.core.services.cache import actions as A

### UPDATE THE CACHE

def update_cache(
        organization_id: Optional[str] = None,
        reverse_key: Optional[str] = None,
        model_id: Optional[int] = None,
        ):

    try:
        found_cache_keys = A.review_cache(
                model_id=model_id,
                organization_id=organization_id,
                reverse_key=reverse_key,
                )
        reverse_check_key = reverse_key.replace("-list", "-check_cache")
        A.update_cache(found_cache_keys, reverse_check_key)
    except Exception as e:
        print(f"within update_cache task {e}")


@shared_task(bind=True)
def task_update_cache(
        self,
        organization_id: Optional[str] = None,
        reverse_key: Optional[str] = None,
        model_id: Optional[int] = None,
        ):
    update_cache(
            organization_id=organization_id,
            reverse_key=reverse_key,
            model_id=model_id,
            )


### SAVE TO CACHE ###

def save_search_cache(
        data,
        id_list=[],
        organization_id=None,
        reverse_list_key=None,
        query_params="",
        ):
    try:
        A.save_search_cache(
                data,
                id_list=id_list,
                organization_id=organization_id,
                reverse_key=reverse_list_key,
                query_params=query_params
                )
    except Exception as e:
        print(f"{e}: within save_search_cache")


@shared_task(bind=True)
def task_save_search_cache(
        self,
        data,
        id_list=[],
        organization_id=None,
        reverse_list_key=None,
        query_params="",
        ):
    save_search_cache(
            data,
            id_list=id_list,
            organization_id=organization_id,
            reverse_list_key=reverse_list_key,
            query_params=query_params
            )


### DOWNLOAD INVOICE ###

# TODO: task to handle downloading invoice
# using WeasyPrint
@shared_task(bind=True)
def task_download_invoice(): pass
