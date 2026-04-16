from django.shortcuts import get_object_or_404
from asgiref.sync import sync_to_async, async_to_sync
from rest_framework.generics import GenericAPIView

from .views import AsyncAPIView
from .mixins import (
    AsyncListModelMixin,
    AsyncRetrieveModelMixin,
    AsyncUpdateModelMixin,
    AsyncCreateModelMixin,
)


class AsyncGenericAPIView(GenericAPIView, AsyncAPIView):
    """
    DRF GenericAPIView with asynchronous methods
    """

    @sync_to_async
    def get_queryset(self):
        return super().get_queryset()

    async def get_async_queryset(self, queryset):
        """
        Queryset async wrapper
        """
        return [instance async for instance in queryset]

    @sync_to_async
    def get_serializer_data(self, serializer):
        return serializer.data

    @sync_to_async
    def get_object(self):
        queryset = async_to_sync(self.filter_queryset)(
            async_to_sync(self.get_queryset)()
        )

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
            % (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        if serializer_class is None:
            return

        kwargs.setdefault("context", self.get_serializer_context())
        return serializer_class(*args, **kwargs)

    def get_serializer_class(self):
        return self.serializer_class

    async def filter_queryset(self, queryset):
        for backend in list(self.filter_backends):
            queryset = await sync_to_async(backend().filter_queryset)(
                self.request, queryset, self
            )
        return queryset

    async def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        return await sync_to_async(self.paginator.paginate_queryset)(
            queryset, self.request, view=self
        )

    async def get_paginated_response(self, data):
        assert self.paginator is not None
        return await sync_to_async(self.paginator.get_paginated_response)(data)


class AsyncListAPIView(AsyncListModelMixin, AsyncGenericAPIView):
    """
    DRF ListAPIView with asynchronous methods
    """

    async def get(self, request, *args, **kwargs):
        return await self.list(request, *args, **kwargs)


class AsyncRetrieveAPIView(AsyncRetrieveModelMixin, AsyncGenericAPIView):
    """
    DRF RetrieveAPIView with asynchronous methods
    """

    async def get(self, request, *args, **kwargs):
        return await self.retrieve(request, *args, **kwargs)


class AsyncCreateAPIView(AsyncCreateModelMixin, AsyncGenericAPIView):
    """
    DRF CreateAPIView with asynchronous methods
    """

    async def post(self, request, *args, **kwargs):
        return await self.create(request, *args, **kwargs)


class AsyncListCreateAPIView(
    AsyncListModelMixin, AsyncCreateModelMixin, AsyncGenericAPIView
):
    """
    DRF ListCreateAPIView with asynchronous methods
    """

    async def get(self, request, *args, **kwargs):
        return await self.list(request, *args, **kwargs)

    async def post(self, request, *args, **kwargs):
        return await self.create(request, *args, **kwargs)


class AsyncRetrieveUpdateAPIView(
    AsyncRetrieveModelMixin, AsyncUpdateModelMixin, AsyncGenericAPIView
):
    """
    DRF RetrieveUpdateAPIView with asynchronous methods
    """

    async def get(self, request, *args, **kwargs):
        return await self.retrieve(request, *args, **kwargs)

    async def put(self, request, *args, **kwargs):
        return await self.update(request, *args, **kwargs)

    async def patch(self, request, *args, **kwargs):
        return await self.partial_update(request, *args, **kwargs)
