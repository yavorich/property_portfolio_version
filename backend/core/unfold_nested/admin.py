from nested_admin.nested import (
    NestedModelAdminMixin,
    NestedInlineModelAdminMixin,
    NestedTabularInlineMixin,
)

from core.unfold_admin.admin import (
    UnfoldModelAdmin,
    UnfoldTabularInline,
    UnfoldStackedInline,
)


class UnfoldNestedAdmin(NestedModelAdminMixin, UnfoldModelAdmin):
    pass


class UnfoldNestedTabularInline(NestedTabularInlineMixin, UnfoldTabularInline):
    template = "unfold/nested/tabular.html"


class UnfoldNestedStackedInline(NestedInlineModelAdminMixin, UnfoldStackedInline):
    template = "unfold/nested/stacked.html"
