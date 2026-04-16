from os import path


def get_upload_path(catalog, name_field, field=None):
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("makemigrations", "migrate"):
        return

    def upload_path(instance, filename):
        return path.join(
            catalog,
            str(getattr(instance, name_field)),
            f"{field}_{filename}" if field is not None else filename,
        )

    return upload_path


def get_upload_name_path(catalog, catalog_name_field, file_prefix_field):
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("makemigrations", "migrate"):
        return

    def upload_path(instance, filename):
        return path.join(
            catalog,
            str(getattr(instance, catalog_name_field)),
            f"{getattr(instance, file_prefix_field)} {filename}".lstrip(),
        )

    return upload_path
