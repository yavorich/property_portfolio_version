from django.apps import AppConfig

from core.unfold_admin.utils import _slugify


class UnfoldAdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.unfold_admin"

    def ready(self):
        import django.template.defaultfilters

        django.template.defaultfilters._slugify = _slugify
