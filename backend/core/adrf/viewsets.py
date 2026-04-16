from functools import update_wrapper

from django.conf import settings
from django.utils.decorators import classonlymethod
from rest_framework.viewsets import ViewSetMixin

from .generic import AsyncGenericAPIView
from .mixins import (
    AsyncListModelMixin,
    AsyncRetrieveModelMixin,
    AsyncCreateModelMixin,
    AsyncUpdateModelMixin,
    AsyncDestroyModelMixin,
)
from .utils import non_atomic_request


class AsyncViewSetMixin(ViewSetMixin):
    @classonlymethod
    def as_view(cls, actions=None, **initkwargs):
        """
        Because of the way class based views create a closure around the
        instantiated view, we need to totally reimplement `.as_view`,
        and slightly modify the view function that is created and returned.
        """
        # The name and description initkwargs may be explicitly overridden for
        # certain route configurations. eg, names of extra actions.
        cls.name = None
        cls.description = None
        # The suffix initkwarg is reserved for displaying the viewset type.
        # This initkwarg should have no effect if the name is provided.
        # eg. 'List' or 'Instance'.
        cls.suffix = None

        # The detail initkwarg is reserved for introspecting the viewset type.
        cls.detail = None

        # Setting a basename allows a view to reverse its action urls. This
        # value is provided by the router through the initkwargs.
        cls.basename = None

        # actions must not be empty
        if not actions:
            raise TypeError(
                "The `actions` argument must be provided when "
                "calling `.as_view()` on a ViewSet. For example "
                "`.as_view({'get': 'list'})`"
            )

        # sanitize keyword arguments
        for key in initkwargs:
            if key in cls.http_method_names:
                raise TypeError(
                    "You tried to pass in the %s method name as a "
                    "keyword argument to %s(). Don't do that." % (key, cls.__name__)
                )
            if not hasattr(cls, key):
                raise TypeError(
                    "%s() received an invalid keyword %r" % (cls.__name__, key)
                )

        # name and suffix are mutually exclusive
        if "name" in initkwargs and "suffix" in initkwargs:
            raise TypeError(
                "%s() received both `name` and `suffix`, which are "
                "mutually exclusive arguments." % (cls.__name__)
            )

        @non_atomic_request
        async def view(request, *args, **kwargs):
            self = cls(**initkwargs)

            if "get" in actions and "head" not in actions:
                actions["head"] = actions["get"]

            # We also store the mapping of request methods to actions,
            # so that we can later set the action attribute.
            # eg. `self.action = 'list'` on an incoming GET request.
            self.action_map = actions

            # Bind methods to actions
            # This is the bit that's different to a standard view
            for method, action in actions.items():
                handler = getattr(self, action)
                setattr(self, method, handler)

            self.request = request
            self.args = args
            self.kwargs = kwargs

            # or continue as usual
            return await self.dispatch(request, *args, **kwargs)

        # take name and docstring from class
        update_wrapper(view, cls, updated=())

        # and possible attributes set by decorators
        # like csrf_exempt from dispatch
        update_wrapper(view, cls.dispatch, assigned=())

        # We need to set these on the view function, so that breadcrumb
        # generation can pick out these bits of information from a
        # resolved URL.
        view.cls = cls
        view.initkwargs = initkwargs
        view.actions = actions
        view.csrf_exempt = True
        return view


class AsyncGenericViewSet(AsyncViewSetMixin, AsyncGenericAPIView):
    """
    DRF GenericViewSet with asynchronous methods
    """

    view_is_async = True


class AsyncModelViewSet(
    AsyncListModelMixin,
    AsyncRetrieveModelMixin,
    AsyncCreateModelMixin,
    AsyncUpdateModelMixin,
    AsyncDestroyModelMixin,
    AsyncGenericViewSet,
):
    """
    DRF ModelViewSet with asynchronous methods
    """

    pass


class AsyncReadOnlyModelViewSet(
    AsyncListModelMixin, AsyncRetrieveModelMixin, AsyncGenericViewSet
):
    """
    DRF ReadOnlyModelViewSet with asynchronous methods
    """

    pass
