import operator
from datetime import datetime

from django.contrib.admin import AllValuesFieldListFilter
from django.contrib.admin.utils import (
    get_last_value_from_parameters,
    reverse_field_path,
)
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.validators import EMPTY_VALUES
from django.utils import formats
from django.utils.translation import gettext_lazy as _
from unfold.contrib.filters.admin import (
    RangeDateFilter as UnfoldRangeDateFilter,
    RelatedDropdownFilter,
)
from unfold.contrib.filters.admin.mixins import DropdownMixin, ValueMixin


class AllValuesFieldListDropdownFilter(
    ValueMixin, DropdownMixin, AllValuesFieldListFilter
):
    field_choices = None

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.lookup_kwarg = field_path
        self.lookup_kwarg_isnull = "%s__isnull" % field_path
        self.lookup_val = params.get(self.lookup_kwarg)
        self.lookup_val_isnull = get_last_value_from_parameters(
            params, self.lookup_kwarg_isnull
        )
        self.empty_value_display = model_admin.get_empty_value_display()
        try:
            parent_model, reverse_path = reverse_field_path(model, field_path)
        except FieldDoesNotExist:
            parent_model = model
        # Obey parent ModelAdmin queryset when deciding which options to show
        if model == parent_model:
            queryset = model_admin.get_queryset(request)
        else:
            queryset = parent_model._default_manager.all()

        self.lookup_choices = (
            queryset.distinct().order_by(field.name).values_list(field.name, flat=True)
        )

        if field.choices:
            self.field_choices = {_id: _value for _id, _value in field.choices}

        super(AllValuesFieldListFilter, self).__init__(
            field, request, params, model, model_admin, field_path
        )

    def choices(self, changelist: ChangeList):
        if self.field_choices is not None:
            lookup_choices = set(self.lookup_choices)
            choices = [
                self.all_option,
                *[
                    (val, self.get_display_value(val))
                    for val in self.field_choices.keys()
                    if val in lookup_choices
                ],
            ]
        else:
            choices = [
                self.all_option,
                *[(val, self.get_display_value(val)) for val in self.lookup_choices],
            ]

        yield {
            "form": self.form_class(
                label=self.title,
                name=self.lookup_kwarg,
                choices=choices,
                data={self.lookup_kwarg: self.value()},
                multiple=self.multiple if hasattr(self, "multiple") else False,
            ),
        }

    def get_display_value(self, val):
        if val is None:
            return "---"
        elif self.field_choices is not None:
            return self.field_choices.get(val, val)
        elif isinstance(val, bool):
            return _("Yes") if val else _("No")
        return val


class RangeDateFilter(UnfoldRangeDateFilter):
    formats = formats.ISO_INPUT_FORMATS["DATE_INPUT_FORMATS"] + ["%d.%m.%Y"]

    def __init__(
        self,
        field,
        request,
        params,
        model,
        model_admin,
        field_path,
    ) -> None:
        super(UnfoldRangeDateFilter, self).__init__(
            field, request, params, model, model_admin, field_path
        )

        self.request = request
        if self.parameter_name is None:
            self.parameter_name = self.field_path

        if self.parameter_name + "_from" in params:
            value = params.pop(self.field_path + "_from")
            value = value[0] if isinstance(value, list) else value

            if value not in EMPTY_VALUES:
                self.used_parameters[self.field_path + "_from"] = value

        if self.parameter_name + "_to" in params:
            value = params.pop(self.field_path + "_to")
            value = value[0] if isinstance(value, list) else value

            if value not in EMPTY_VALUES:
                self.used_parameters[self.field_path + "_to"] = value

    def queryset(self, request, queryset):
        filters = {}

        value_from = self.used_parameters.get(self.parameter_name + "_from", None)
        if value_from not in EMPTY_VALUES:
            filters.update(
                {
                    self.parameter_name
                    + "__gte": self._parse_value(
                        self.used_parameters.get(self.parameter_name + "_from", None)
                    ),
                }
            )

        value_to = self.used_parameters.get(self.parameter_name + "_to", None)
        if value_to not in EMPTY_VALUES:
            filters.update(
                {
                    self.parameter_name
                    + "__lte": self._parse_value(
                        self.used_parameters.get(self.parameter_name + "_to", None)
                    ),
                }
            )

        try:
            return queryset.filter(**filters)
        except (ValueError, ValidationError):
            return None

    def _parse_value(self, value):
        if value is None:
            return

        for _format in self.formats:
            try:
                return datetime.strptime(value, _format).date()
            except (ValueError, TypeError) as e:
                pass


class AllValuesRelatedDropdownFilter(RelatedDropdownFilter):
    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        rel_ids = (
            model_admin.get_queryset(request)
            .values_list(field.attname, flat=True)
            .distinct()
        )
        if field.choices is not None:
            return field.choices

        rel_model = field.remote_field.model
        limit_choices_to = field.get_limit_choices_to()
        pk_field = (
            field.remote_field.get_related_field().attname
            if hasattr(field.remote_field, "get_related_field")
            else "pk"
        )
        choice_func = operator.attrgetter(pk_field)

        qs = rel_model._default_manager.filter(
            **{f"{pk_field}__in": rel_ids}
        ).complex_filter(limit_choices_to)

        if ordering:
            qs = qs.order_by(*ordering)

        return [(choice_func(x), str(x)) for x in qs]
