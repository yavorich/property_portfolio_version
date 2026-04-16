from django.db import models
from django.core.validators import RegexValidator
from django import forms
from django.urls import path
from django.http import JsonResponse
from django.utils.html import format_html
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    message="Введите цвет в формате #RRGGBB или #RGB",
)


class ColorPickerAdminMixin:
    """
    Универсальный миксин для админки, добавляющий:
    - цветовое поле (color input)
    - AJAX сохранение без перезагрузки
    """

    color_field_name = "color"  # цвет фона
    text_color_field_name = "text_color"  # цвет текста
    model = None

    # --- форма с color-полями ---
    class ColorPickerForm(forms.ModelForm):
        def __init__(
            self, *args, color_field_name=None, text_color_field_name=None, **kwargs
        ):
            super().__init__(*args, **kwargs)
            color_field = color_field_name or "color"
            text_color_field = text_color_field_name or "text_color"
            for f in [color_field, text_color_field]:
                if f in self.fields:
                    self.fields[f].widget = forms.TextInput(attrs={"type": "color"})

        class Meta:
            fields = "__all__"

    # При инициализации админки передаём поля в форму
    def get_form(self, request, obj=None, **kwargs):
        kwargs.setdefault(
            "form",
            self.ColorPickerForm,
        )
        form = super().get_form(request, obj, **kwargs)

        # Оборачиваем __init__ формы, чтобы передавать названия полей
        class FormWithColorFields(form):
            def __init__(self2, *args, **fkwargs):
                super().__init__(
                    *args,
                    color_field_name=self.color_field_name,
                    text_color_field_name=self.text_color_field_name,
                    **fkwargs,
                )

        return FormWithColorFields

    # --- отображение цвета в списке ---
    def color_picker(self, obj):
        value = getattr(obj, self.color_field_name)
        return self._color_input_html(obj.pk, value, self.color_field_name)

    color_picker.short_description = "Цвет"

    def text_color_picker(self, obj):
        value = getattr(obj, self.text_color_field_name)
        return self._color_input_html(obj.pk, value, self.text_color_field_name)

    text_color_picker.short_description = "Цвет текста"

    def _color_input_html(self, pk, value, field_name):
        return format_html(
            '<div style="display:flex;align-items:center;gap:0.3rem;">'
            '<input type="color" value="{}" data-id="{}" data-field="{}" class="color-input" '
            'style="border:none;background:none;width:2rem;height:2rem;cursor:pointer;">'
            '<span class="save-check" style="display:none;color:green;">&#10003;</span>'
            "</div>",
            value,
            pk,
            field_name,
        )

    # --- добавляем URL для обновления цвета ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "update-color/",
                self.admin_site.admin_view(self.update_color),
                name=f"{self.model._meta.model_name}_update_color",
            ),
        ]
        return custom_urls + urls

    # --- обработчик AJAX запроса ---
    @method_decorator(csrf_protect)
    def update_color(self, request):
        if request.method == "POST":
            pk = request.POST.get("id")
            color = request.POST.get("color")
            field = request.POST.get("field")
            try:
                model = self.model or self.opts.model
                obj = model.objects.get(pk=pk)
                setattr(obj, field, color)
                obj.save()
                return JsonResponse({"success": True})
            except model.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Not found"}, status=404
                )
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)}, status=400)
        return JsonResponse({"success": False, "error": "Invalid request"}, status=400)

    class Media:
        js = ("admin/js/color_update.js",)


class ColorField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 7)
        kwargs.setdefault("validators", [HEX_COLOR_VALIDATOR])
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        defaults = {"widget": forms.TextInput(attrs={"type": "color"})}
        defaults.update(kwargs)
        return super().formfield(**defaults)
