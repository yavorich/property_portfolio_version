from uuid import uuid4

from django.db import models

from apps.account.models import User


class Listing(models.Model):
    class Source(models.TextChoices):
        BAYUT = "bayut", "Bayut"
        PROPERTY_FINDER = "property_finder", "Property Finder"

    class Status(models.TextChoices):
        PENDING = "pending", "В очереди"
        PARSING = "parsing", "Парсинг"
        DOWNLOADING = "downloading", "Скачивание фото"
        PARSED = "parsed", "Данные собраны"
        PROCESSING = "processing", "Обработка фото"
        DONE = "done", "Готово"
        FAILED = "failed", "Ошибка"

    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    source = models.CharField("Источник", max_length=32, choices=Source.choices)
    source_url = models.URLField("Ссылка на листинг", max_length=1024)
    status = models.CharField(
        "Статус", max_length=32, choices=Status.choices, default=Status.PENDING
    )
    error = models.TextField("Ошибка", blank=True)

    title = models.CharField("Название", max_length=512, blank=True)
    address = models.CharField("Адрес", max_length=512, blank=True)
    description = models.TextField("Описание", blank=True)

    price = models.BigIntegerField("Цена", null=True, blank=True)
    currency = models.CharField("Валюта", max_length=8, blank=True, default="AED")

    area_sqft = models.FloatField("Площадь (sqft)", null=True, blank=True)
    area_sqm = models.FloatField("Площадь (m²)", null=True, blank=True)
    rooms = models.IntegerField("Комнат", null=True, blank=True)
    bathrooms = models.IntegerField("Санузлов", null=True, blank=True)
    floor = models.CharField("Этаж", max_length=64, blank=True)

    broker_name = models.CharField("Брокер — имя", max_length=256, blank=True)
    broker_phone = models.CharField("Брокер — телефон", max_length=64, blank=True)
    broker_email = models.EmailField("Брокер — email", blank=True)
    broker_agency = models.CharField("Агентство", max_length=256, blank=True)

    raw_data = models.JSONField("Сырые данные", null=True, blank=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "листинг"
        verbose_name_plural = "Листинги"

    def __str__(self):
        return self.title or self.source_url


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    index = models.PositiveIntegerField("Порядок")
    source_url = models.URLField("Оригинальная ссылка", max_length=2048)
    original = models.ImageField("Оригинал", upload_to="listings/%Y/%m/original/", null=True, blank=True)
    processed = models.ImageField("После обработки", upload_to="listings/%Y/%m/processed/", null=True, blank=True)
    downloaded_at = models.DateTimeField("Скачано", null=True, blank=True)

    class Meta:
        ordering = ["index"]
        unique_together = [("listing", "index")]
        verbose_name = "фото"
        verbose_name_plural = "Фото"

    def __str__(self):
        return f"{self.listing_id} #{self.index}"
