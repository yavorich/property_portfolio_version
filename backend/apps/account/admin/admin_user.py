from django.contrib import admin
from django.contrib.auth.models import Group

from apps.account.models import AdminUser
from core.unfold_admin.admin import UnfoldModelAdmin
from core.unfold_admin.filters import AllValuesFieldListDropdownFilter
from core.unfold_user_admin.mixins import ChangePasswordMixin


@admin.register(AdminUser)
class AdminUserAdmin(ChangePasswordMixin, UnfoldModelAdmin):
    fields = ("username", "password", "is_active")
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2"),
            },
        ),
    )

    search_fields = ("username",)
    list_filter = (("is_active", AllValuesFieldListDropdownFilter),)
    list_display = ("id", "username", "is_active")
    list_display_links = ("id", "username")
    show_full_result_count = False


admin.site.unregister(Group)
