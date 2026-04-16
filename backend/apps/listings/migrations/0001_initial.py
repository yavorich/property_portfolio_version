import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Listing",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[("bayut", "Bayut"), ("property_finder", "Property Finder")],
                        max_length=32,
                        verbose_name="Источник",
                    ),
                ),
                (
                    "source_url",
                    models.URLField(max_length=1024, verbose_name="Ссылка на листинг"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "В очереди"),
                            ("parsing", "Парсинг"),
                            ("downloading", "Скачивание фото"),
                            ("parsed", "Данные собраны"),
                            ("processing", "Обработка фото"),
                            ("done", "Готово"),
                            ("failed", "Ошибка"),
                        ],
                        default="pending",
                        max_length=32,
                        verbose_name="Статус",
                    ),
                ),
                ("error", models.TextField(blank=True, verbose_name="Ошибка")),
                ("title", models.CharField(blank=True, max_length=512, verbose_name="Название")),
                ("address", models.CharField(blank=True, max_length=512, verbose_name="Адрес")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("price", models.BigIntegerField(blank=True, null=True, verbose_name="Цена")),
                (
                    "currency",
                    models.CharField(blank=True, default="AED", max_length=8, verbose_name="Валюта"),
                ),
                (
                    "area_sqft",
                    models.FloatField(blank=True, null=True, verbose_name="Площадь (sqft)"),
                ),
                (
                    "area_sqm",
                    models.FloatField(blank=True, null=True, verbose_name="Площадь (m²)"),
                ),
                ("rooms", models.IntegerField(blank=True, null=True, verbose_name="Комнат")),
                ("bathrooms", models.IntegerField(blank=True, null=True, verbose_name="Санузлов")),
                ("floor", models.CharField(blank=True, max_length=64, verbose_name="Этаж")),
                (
                    "broker_name",
                    models.CharField(blank=True, max_length=256, verbose_name="Брокер — имя"),
                ),
                (
                    "broker_phone",
                    models.CharField(blank=True, max_length=64, verbose_name="Брокер — телефон"),
                ),
                (
                    "broker_email",
                    models.EmailField(blank=True, max_length=254, verbose_name="Брокер — email"),
                ),
                (
                    "broker_agency",
                    models.CharField(blank=True, max_length=256, verbose_name="Агентство"),
                ),
                ("raw_data", models.JSONField(blank=True, null=True, verbose_name="Сырые данные")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="listings",
                        to="account.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "листинг",
                "verbose_name_plural": "Листинги",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ListingPhoto",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("index", models.PositiveIntegerField(verbose_name="Порядок")),
                (
                    "source_url",
                    models.URLField(max_length=2048, verbose_name="Оригинальная ссылка"),
                ),
                (
                    "original",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="listings/%Y/%m/original/",
                        verbose_name="Оригинал",
                    ),
                ),
                (
                    "processed",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="listings/%Y/%m/processed/",
                        verbose_name="После обработки",
                    ),
                ),
                (
                    "downloaded_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="Скачано"),
                ),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="listings.listing",
                    ),
                ),
            ],
            options={
                "verbose_name": "фото",
                "verbose_name_plural": "Фото",
                "ordering": ["index"],
                "unique_together": {("listing", "index")},
            },
        ),
    ]
