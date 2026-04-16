import json
from typing import Dict, List, Callable

from unfold.widgets import UnfoldAdminSelectWidget


class AutoCompleteUnfoldSelectWidget(UnfoldAdminSelectWidget):
    auto_complete_context = None

    class Media:
        js = ("js/autocomplete.js",)

    def __init__(
        self,
        depends_field,
        generate_map_func: Callable[[], Dict[str, List[str]]],
        attrs=None,
        choices=(),
    ):
        self.depends_field = depends_field
        self.generate_map_func = generate_map_func
        super().__init__(attrs, choices)

    def get_context(self, name, value, attrs):
        options_map = {
            str(current): [str(value) for value in depends_list_values]
            for current, depends_list_values in self.generate_map_func().items()
        }
        attrs["data-options-map"] = json.dumps(options_map)
        attrs["data-depends-field"] = self.depends_field
        context = super().get_context(name, value, attrs)

        # context.update(self.auto_complete_context)
        return context
