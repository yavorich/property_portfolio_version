from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import ImageField
from PIL import Image, ExifTags
from django.db.models.fields.files import ImageFieldFile


class CompressedImageFieldFile(ImageFieldFile):
    def save(self, name, content, save=True):
        content = self._compress_save(name, content)
        return super().save(name, content, save)

    def _compress_save(self, name, content):
        with Image.open(content) as img:
            if img.width < self.field.max_width and img.height < self.field.max_height:
                return content

            img.thumbnail(
                (self.field.max_width, self.field.max_height), Image.Resampling.LANCZOS
            )
            img = self._fix_orientation(img)

            extension = name.split(".")[-1].upper()
            if extension == "JPG":
                extension = "JPEG"

            if img.mode == "RGBA":
                extension = "PNG"

            elif img.mode == "P":
                extension = "GIF"

            with BytesIO() as buffer:
                img.save(buffer, extension)
                return ContentFile(buffer.getvalue())

    def _fix_orientation(self, img):
        orientation = None
        for _orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[_orientation] == "Orientation":
                orientation = _orientation
                break

        exif = img.getexif()
        if exif is not None:
            orientation_value = exif.get(orientation)

            if orientation_value == 3:
                return img.rotate(180, expand=True)
            elif orientation_value == 6:
                return img.rotate(270, expand=True)
            elif orientation_value == 8:
                return img.rotate(90, expand=True)

        return img


class CompressedImageField(ImageField):
    attr_class = CompressedImageFieldFile

    def __init__(self, *args, **kwargs):
        self.max_width = kwargs.pop("max_width", 1440)
        self.max_height = kwargs.pop("max_height", 1440)
        super().__init__(*args, **kwargs)
