from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.settings import api_settings
from asgiref.sync import sync_to_async
from rest_framework.status import HTTP_204_NO_CONTENT


class AsyncListModelMixin:
    """
    DRF ListModelMixin with asynchronous methods
    """

    async def list(self, request, *args, **kwargs):
        aqueryset = await self.filter_queryset(await self.get_queryset())

        page = await self.paginate_queryset(aqueryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return await self.get_paginated_response(
                await self.get_serializer_data(serializer)
            )

        serializer = self.get_serializer(aqueryset, many=True)
        return Response(await self.get_serializer_data(serializer))


class AsyncRetrieveModelMixin:
    """
    DRF RetrieveModelMixin with asynchronous methods
    """

    async def retrieve(self, request, *args, **kwargs):
        instance = await self.get_object()
        serializer = self.get_serializer(instance)
        return Response(await self.get_serializer_data(serializer))


class AsyncCreateModelMixin:
    """
    DRF CreateModelMixin with asynchronous methods
    """

    async def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        await self.perform_create(serializer)
        headers = await self.get_success_headers(serializer.data)
        return Response(
            await self.get_serializer_data(serializer),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @sync_to_async
    def perform_create(self, serializer):
        serializer.save()

    async def get_success_headers(self, data):
        try:
            return {"Location": str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}


class AsyncUpdateModelMixin:
    """
    DRF UpdateModelMixin with asynchronous methods
    """

    async def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = await self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        await self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(await self.get_serializer_data(serializer))

    @sync_to_async
    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()

    async def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return await self.update(request, *args, **kwargs)


class AsyncDestroyModelMixin:
    """
    DRF DestroyModelMixin with asynchronous methods
    """

    async def destroy(self, request, *args, **kwargs):
        instance = await self.get_object()
        await self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @sync_to_async
    def perform_destroy(self, instance):
        instance.delete()


class AsyncUpdateActionModelMixin:
    async def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        await self.perform_update(serializer)
        return Response(status=HTTP_204_NO_CONTENT)

    async def perform_update(self, serializer):
        serializer.save()
