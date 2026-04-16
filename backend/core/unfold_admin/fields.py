from django.contrib.admin.utils import lookup_field
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import (
    ForeignObjectRel,
    ManyToManyRel,
    OneToOneField,
)
from django.template.defaultfilters import linebreaksbr
from django.utils.html import conditional_escape, format_html
from unfold.fields import UnfoldAdminReadonlyField
from unfold.utils import prettify_json

from .utils import display_for_field


class PrettyUnfoldAdminReadonlyField(UnfoldAdminReadonlyField):
    def _get_contents(self) -> str:
        from django.contrib.admin.templatetags.admin_list import _boolean_icon

        field, obj, model_admin = (
            self.field["field"],
            self.form.instance,
            self.model_admin,
        )
        try:
            f, attr, value = lookup_field(field, obj, model_admin)
        except (AttributeError, ValueError, ObjectDoesNotExist):
            result_repr = self.empty_value_display
        else:
            if field in self.form.fields:
                widget = self.form[field].field.widget
                # This isn't elegant but suffices for contrib.auth's
                # ReadOnlyPasswordHashWidget.
                if getattr(widget, "read_only", False):
                    return widget.render(field, value)

            if f is None:
                if getattr(attr, "boolean", False):
                    result_repr = _boolean_icon(value)
                else:
                    if hasattr(value, "__html__"):
                        result_repr = value
                    else:
                        result_repr = linebreaksbr(value)
            else:
                if isinstance(f.remote_field, ManyToManyRel) and value is not None:
                    result_repr = ", ".join(map(str, value.all()))
                elif (
                    isinstance(f.remote_field, (ForeignObjectRel, OneToOneField))
                    and value is not None
                ):
                    result_repr = self.get_admin_url(f.remote_field, value)
                elif isinstance(f, models.JSONField):
                    formatted_output = prettify_json(value)

                    if formatted_output:
                        return formatted_output

                    result_repr = display_for_field(value, f, self.empty_value_display)
                    return conditional_escape(result_repr)
                elif isinstance(f, models.URLField):
                    return format_html(
                        '<a href="{}" class="text-primary-600 dark:text-primary-500">{}</a>',
                        value,
                        value,
                    )
                else:
                    result_repr = display_for_field(value, f, self.empty_value_display)
                    return conditional_escape(result_repr)
                result_repr = linebreaksbr(result_repr)
        return conditional_escape(result_repr)
