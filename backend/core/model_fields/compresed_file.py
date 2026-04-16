from PIL import UnidentifiedImageError
from django.db.models import FileField

from .compresed_image import CompressedImageFieldFile


class CompressedImageFileFieldFile(CompressedImageFieldFile):
    def _compress_save(self, name, content):
        try:
            return super()._compress_save(name, content)

        except UnidentifiedImageError:
            return content


class CompressedImageFileField(FileField):
    attr_class = CompressedImageFileFieldFile

    def __init__(self, *args, **kwargs):
        self.max_width = kwargs.pop("max_width", 1440)
        self.max_height = kwargs.pop("max_height", 1440)
        super().__init__(*args, **kwargs)
