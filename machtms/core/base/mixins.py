import logging
from django.db import transaction, IntegrityError
from typing import Optional
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from dataclasses import dataclass
from typing import Type, Dict, Any, Optional
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from machtms.backend.auth.models import Organization
from machtms.core.auth.permissions import LocalhostPermission
from machtms.core.services.cache import tasks, actions

logger = logging.getLogger(__name__)


class LoggingMixin:
    """
    A mixin for DRF ViewSets that logs all action calls and exceptions.

    Logs successful responses (status < 400) as INFO and exceptions as ERROR.
    Automatically captures the view name and action being performed.

    Usage:
        class MyViewSet(LoggingMixin, viewsets.ModelViewSet):
            queryset = MyModel.objects.all()
            serializer_class = MySerializer
    """

    def finalize_response(self, request, response, *args, **kwargs):
        """
        Called after the view returns a response.
        Logs successful requests with view name, action, and status code.
        """
        view_name = self.get_view_name()
        action_name = getattr(self, 'action', 'unknown')

        if response.status_code < 400:
            logger.info(
                f"[{request.method}] {view_name}.{action_name} - "
                f"Status: {response.status_code}"
            )
        else:
            logger.warning(
                f"[{request.method}] {view_name}.{action_name} - "
                f"Status: {response.status_code}"
            )

        return super().finalize_response(request, response, *args, **kwargs)

    def handle_exception(self, exc):
        """
        Called when an exception is raised during request processing.
        Logs the exception with view name and error message.
        """
        view_name = self.get_view_name()
        action_name = getattr(self, 'action', 'unknown')

        logger.error(
            f"[EXCEPTION] {view_name}.{action_name} - {type(exc).__name__}: {str(exc)}"
        )

        return super().handle_exception(exc)


class TMSCacheMixin:

    @property
    def organization_id(self):
        request = self.request
        return request.organization


    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        model_id = self.get_object().pk
        task_kwargs = {
                "reverse_key": f"{self.basename}-list",
                "model_id": model_id,
                }
        if self.organization_id is not None:
            task_kwargs['organization_id'] = self.organization_id
        tasks.task_update_cache.delay(**task_kwargs)

        return response


    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        task_kwargs = {
                "reverse_key": f"{self.basename}-list",
                }
        if self.organization_id is not None:
            task_kwargs['organization_id'] = self.organization_id
        tasks.task_update_cache.delay(**task_kwargs)
        return response


    def list(self, request, *args, **kwargs):
        reverse_key = f"{self.basename}-{self.action}"
        query_params = request.query_params.get("search", None)
        if query_params:
            logger.debug(f"query_params exists: {query_params}")
            cached = actions.get_cache(
                    organization_id=self.organization_id,
                    reverse_key=reverse_key,
                    query_params=request.META.get("QUERY_STRING")
                    )
            if cached:
                logger.debug(f"cache exists:\n{cached}")
                return Response(cached)

            response = super().list(request, *args, **kwargs)

            task_kwargs = {
                    "reverse_list_key": reverse_key,
                    "id_list": response.data.get('id_list', []),
                    "query_params": request.META.get('QUERY_STRING'),
                    }
            if self.organization_id is not None:
                task_kwargs['organization_id'] = self.organization_id
            tasks.task_save_search_cache.delay(
                    response.data, **task_kwargs) # type: ignore
            logger.debug("sent celery task `task_save_search_cache`")

            return response

        return super().list(request, *args, **kwargs)



    @action(detail=False, methods=['get'], permission_classes=[LocalhostPermission])
    def check_cache(self):
        queryset = self.filter_queryset(self.get_queryset())
        id_list = list(queryset.values_list("pk", flat=True))

        page = self.paginate_queryset(queryset)
        if page is not None:
            logger.debug("page exists")
            serializer_data = self.get_serializer(page, many=True).data
            paginated_response = self.get_paginated_response(serializer_data)
            paginated_response.data = {**paginated_response.data, "id_list": id_list}
            logger.debug(f"\n{paginated_response.data}")
            return paginated_response
        return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TMSViewMixin(LoggingMixin):
    '''
    ClassViewSet with convenience methods to reduce repitition
    get_queryset_all: depending on environment, will return a
    queryset with either organization or no organization

    perform_create: depending on environment, will save
    serializer with organization or no organization
    '''


    def get_queryset(self):
        """
        Taking a look at user.userprofile.organization:

        Under DEBUG mode, I assume this is ok.
        since userprofile.organization has null=True
        """

        org: Optional[Organization] = self.request.organization
        return self.queryset.fbo(organization=org)


    def perform_create(self, serializer):
        org: Optional[Organization] = self.request.organization
        serializer.save(organization=self.request.organization)


# ========== SERIALIZER MIXINS ==========


@dataclass
class NestedRelationConfig:
    """
    Configuration for a single nested relationship.
 
    Args:
        parent_field_name: The FK field name on the Child model (e.g., 'load').
        related_manager_name: The related_name on the Parent model (e.g., 'legs').
        serializer_class: The serializer used to validate/save the child.
        extra_kwargs_method: (Optional) Name of a method on the parent serializer 
                             that returns a dict of extra kwargs for child.save().
    """
    parent_field_name: str
    related_manager_name: str
    serializer_class: Type[serializers.Serializer]
    extra_kwargs_method: Optional[str] = None


class NestedUpdateMixin:
    """
    Contains the core logic for syncing a list of child objects.
    Optimized to prevent N+1 queries.
    """

    def upsert_nested_list(
        self,
        parent_instance,
        data_list: list,
        config: NestedRelationConfig,
        extra_save_kwargs: Optional[Dict[str, Any]] = None
    ):
        if extra_save_kwargs is None:
            extra_save_kwargs = {}

        # 1. Fetch Manager
        existing_children = getattr(parent_instance, config.related_manager_name)

        # 2. OPTIMIZATION: Fetch all valid IDs upfront to avoid N+1 queries in the loop
        # This turns O(n) queries into O(1) query.
        existing_ids = set(existing_children.values_list('id', flat=True))

        # 3. PRE-COMPUTE keep_ids from items that have IDs (updates)
        # and validate they belong to this parent
        keep_ids = []
        for item_data in data_list:
            child_id = item_data.get('id')
            if child_id:
                if child_id not in existing_ids:
                    raise ValidationError({
                        config.related_manager_name: f"Object {child_id} does not belong to this parent."
                    })
                keep_ids.append(child_id)

        # 4. DELETE FIRST - Remove children not in payload before creating new ones
        # This prevents unique constraint violations (e.g., stop_number conflicts)
        if existing_ids:
            existing_children.exclude(id__in=keep_ids).delete()

        # 5. Process updates and creates
        results = []
        for item_data in data_list:
            child_id = item_data.get('id')

            if child_id:
                # --- UPDATE ---
                child_instance = existing_children.get(id=child_id)

                serializer = config.serializer_class(
                    child_instance,
                    data=item_data,
                    partial=True,
                    context=self.context
                )
                serializer.is_valid(raise_exception=True)
                instance = serializer.save(**extra_save_kwargs)
            else:
                # --- CREATE ---
                # Data is already validated by parent serializer during initial validation.
                # Skip re-validation and create directly using the model to avoid issues
                # with model instances (e.g., Address) being passed instead of pks.
                serializer_class = config.serializer_class
                model_class = serializer_class.Meta.model

                # Extract nested relation data before creating (can't pass reverse relations to create())
                child_nested_relations = getattr(serializer_class, 'nested_relations', {})
                nested_data_map = {}
                for nested_field in child_nested_relations.keys():
                    if nested_field in item_data:
                        nested_data_map[nested_field] = item_data.pop(nested_field)

                # Build create kwargs: parent FK + extra kwargs + validated item data
                create_kwargs = {config.parent_field_name: parent_instance}
                create_kwargs.update(extra_save_kwargs)
                create_kwargs.update(item_data)

                instance = model_class.objects.create(**create_kwargs)

                # Recursively handle nested writes for the child instance
                for nested_field, nested_config in child_nested_relations.items():
                    if nested_field in nested_data_map:
                        self.upsert_nested_list(
                            parent_instance=instance,
                            data_list=nested_data_map[nested_field],
                            config=nested_config,
                            extra_save_kwargs={}
                        )

            results.append(instance)

        return results


class AutoNestedMixin(NestedUpdateMixin):
    """
    Declarative mixin that handles nested writes automatically using 'nested_relations'.

    Features:
    - Atomic Transactions: Entire operation is all-or-nothing.
    - Order Preservation: Processes nested relations in the order defined.
    - Error Handling: Catches IntegrityErrors and re-raises them as ValidationErrors.
    """
    nested_relations: Dict[str, NestedRelationConfig] = {}

    def create(self, validated_data):
        nested_data_map = self._pop_nested_data(validated_data)

        try:
            with transaction.atomic():
                # 1. Create Parent
                instance = super().create(validated_data)

                # 2. Handle Children
                self._handle_nested_writes(instance, nested_data_map)
        except IntegrityError as e:
            # Catch DB-level constraints (like Unique violations) that pass DRF validation
            raise ValidationError({"detail": str(e)})

        return instance

    def update(self, instance, validated_data):
        nested_data_map = self._pop_nested_data(validated_data)

        try:
            with transaction.atomic():
                # 1. Update Parent
                instance = super().update(instance, validated_data)

                # 2. Handle Children
                self._handle_nested_writes(instance, nested_data_map)
        except IntegrityError as e:
            raise ValidationError({"detail": str(e)})

        return instance


    def _pop_nested_data(self, validated_data):
        """Extracts nested data before the parent is saved."""
        data_map = {}
        for field_name in self.nested_relations.keys():
            if field_name in validated_data:
                data_map[field_name] = validated_data.pop(field_name)
        return data_map


    def _handle_nested_writes(self, parent_instance, nested_data_map):
        """Iterates through defined relations and executes upsert logic."""
        # Note: In Python 3.7+, dictionary insertion order is preserved.
        # This means children are processed in the order you define them in 'nested_relations'.
        for field_name, config in self.nested_relations.items():
            # Only process if data was actually provided
            if field_name in nested_data_map:
                data_list = nested_data_map[field_name]
                # Fetch dynamic kwargs if configured
                extra_kwargs = {}
                if config.extra_kwargs_method:
                    method = getattr(self, config.extra_kwargs_method)
                    extra_kwargs = method(parent_instance)

                self.upsert_nested_list(
                    parent_instance=parent_instance,
                    data_list=data_list,
                    config=config,
                    extra_save_kwargs=extra_kwargs
                )
