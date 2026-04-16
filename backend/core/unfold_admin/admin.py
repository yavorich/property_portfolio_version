from django.contrib.admin import helpers
from django.db import models
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.overrides import FORMFIELD_OVERRIDES, FORMFIELD_OVERRIDES_INLINE

from . import widgets
from .fields import PrettyUnfoldAdminReadonlyField


FORMFIELD_OVERRIDES.update(
    {
        models.ImageField: {"widget": widgets.UnfoldAdminImageFieldWidget},
        models.FileField: {"widget": widgets.UnfoldAdminFileFieldWidget},
    }
)


FORMFIELD_OVERRIDES_INLINE.update(
    {
        models.ImageField: {"widget": widgets.UnfoldAdminImageFieldWidget},
        models.FileField: {"widget": widgets.UnfoldAdminFileFieldWidget},
    }
)


helpers.AdminReadonlyField = PrettyUnfoldAdminReadonlyField


class UnfoldTabularInline(TabularInline):
    pass


class UnfoldStackedInline(StackedInline):
    pass


class UnfoldModelAdmin(ModelAdmin):
    compressed_fields = True
    list_filter_submit = True
    show_facets = False
