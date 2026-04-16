import os

from django.db.models import FileField
from rest_framework.utils import model_meta


def delete_file(instance):
    """
    Удаляет файлы из файловой системы при удалении модели с FileField
    """
    info = model_meta.get_field_info(instance.__class__)
    file_field_names = (
        field
        for field, FieldClass in info.fields.items()
        if isinstance(FieldClass, FileField)
    )

    for file_field_name in file_field_names:
        file_field = getattr(instance, file_field_name)
        if file_field:
            file_path = file_field.path
            try:
                file_field.delete(save=False)
                file_directory = os.path.dirname(file_path)
                if not os.listdir(file_directory):
                    os.rmdir(file_directory)
            except ValueError:
                pass
            except FileNotFoundError:
                pass


def delete_file_on_update(instance):
    """
    Удаляет файлы из файловой системы при изменении полей FileField модели
    """
    if instance._state.adding or not instance.pk:
        return

    try:
        old_instance = instance.__class__.objects.get(pk=instance.pk)
    except instance.DoesNotExist:
        return

    info = model_meta.get_field_info(instance.__class__)
    file_field_names = (
        field
        for field, FieldClass in info.fields.items()
        if isinstance(FieldClass, FileField)
    )
    for file_field_name in file_field_names:
        old_file_field = getattr(old_instance, file_field_name)
        file_field = getattr(instance, file_field_name)

        if old_file_field.name != file_field.name:
            old_file_field.delete(save=False)
