import json
import re
import unicodedata
from typing import Any

from django.db import models
from django.utils import formats, timezone
from django.utils.functional import keep_lazy_text
from django.utils.hashable import make_hashable
from django.utils.html import format_html
from unfold.utils import _boolean_icon, display_for_value


RUS_TO_EN_TRANSLATION = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": '"',
        "ы": "y",
        "ь": "'",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
)


@keep_lazy_text
def _slugify(value, allow_unicode=False):
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = value.lower().translate(RUS_TO_EN_TRANSLATION)
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def display_for_field(value: Any, field: Any, empty_value_display: str) -> str:
    if getattr(field, "flatchoices", None):
        try:
            return dict(field.flatchoices).get(value, empty_value_display)
        except TypeError:
            # Allow list-like choices.
            flatchoices = make_hashable(field.flatchoices)
            value = make_hashable(value)
            return dict(flatchoices).get(value, empty_value_display)
    elif isinstance(field, models.BooleanField):
        return _boolean_icon(value)
    elif value is None or value == "":
        return empty_value_display
    elif isinstance(field, models.DateTimeField):
        return formats.localize(timezone.template_localtime(value))
    elif isinstance(field, (models.DateField, models.TimeField)):
        return formats.localize(value)
    elif isinstance(field, models.DecimalField):
        return formats.number_format(value, field.decimal_places)
    elif isinstance(field, (models.IntegerField, models.FloatField)):
        return formats.number_format(value)
    elif isinstance(field, models.ImageField) and value:
        return format_html(
            '<a href="{url}"><img src="{url}" alt="Image preview" class="block rounded"></a>',
            url=value.url,
        )
    elif isinstance(field, models.FileField) and value:
        return format_html(
            '<a href="{}" class="text-primary-600 dark:text-primary-500">{}</a>',
            value.url,
            value,
        )
    elif isinstance(field, models.JSONField) and value:
        try:
            return json.dumps(value, ensure_ascii=False, cls=field.encoder)
        except TypeError:
            return display_for_value(value, empty_value_display)
    else:
        return display_for_value(value, empty_value_display)
