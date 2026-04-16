from unfold import widgets


class FileNameMixin:
    def get_context(self, name, value, attrs):
        widget = super().get_context(name, value, attrs)
        value = widget["widget"]["value"]
        if value:
            value.filename = value.name.split("/")[-1].replace("_", " ")

        return widget


class UnfoldAdminImageFieldWidget(FileNameMixin, widgets.UnfoldAdminImageFieldWidget):
    template_name = "widgets/clearable_file_input.html"


class UnfoldAdminFileFieldWidget(FileNameMixin, widgets.UnfoldAdminFileFieldWidget):
    template_name = "widgets/clearable_file_input_small.html"
