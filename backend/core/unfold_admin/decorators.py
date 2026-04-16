from django.core.exceptions import PermissionDenied


def submit_line_action(
    function=None,
    *,
    permissions=None,
    description=None,
    url_path=None,
    attrs=None,
):
    def decorator(func):
        def inner(
            model_admin,
            request,
            *args,
            **kwargs,
        ):
            if permissions:
                permission_checks = (
                    getattr(model_admin, f"has_{permission}_permission")
                    for permission in permissions
                )

                if not all(
                    has_permission(request, args[0].pk)
                    for has_permission in permission_checks
                ):
                    raise PermissionDenied
            return func(model_admin, request, *args, **kwargs)

        if permissions is not None:
            inner.allowed_permissions = permissions
        if description is not None:
            inner.short_description = description
        if url_path is not None:
            inner.url_path = url_path
        inner.attrs = attrs or {}
        return inner

    if function is None:
        return decorator
    else:
        return decorator(function)
