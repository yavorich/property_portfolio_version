from django.forms import (
    Form,
    ChoiceField,
    Select,
    BooleanField,
    HiddenInput,
    IntegerField,
    NumberInput,
)
from django.utils.translation import gettext_lazy as _


class MovePageActionForm(Form):
    action = ChoiceField(
        label="",
        widget=Select(
            {
                "class": " ".join(
                    [
                        "appearance-none",
                        "bg-white/20",
                        "font-medium",
                        "grow",
                        "px-3",
                        "py-2",
                        "pr-8",
                        "rounded",
                        "text-white",
                        "*:text-base-700",
                        "lg:min-w-72",
                    ]
                ),
                "aria-label": _("Select action to run"),
                "x-model": "action",
            }
        ),
    )

    select_across = BooleanField(
        label="",
        required=False,
        initial=0,
        widget=HiddenInput({"class": "select-across"}),
    )
    step = IntegerField(
        required=False,
        initial=1,
        widget=NumberInput(attrs={"id": "changelist-form-step"}),
        label=False,
    )
    page = IntegerField(
        required=False,
        widget=NumberInput(attrs={"id": "changelist-form-page"}),
        label=False,
    )
