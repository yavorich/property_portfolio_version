from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    Model,
    PositiveBigIntegerField,
    URLField,
    UUIDField,
)


class AdminUser(AbstractUser):
    """Admin account for Django admin site. Uses standard username/password auth."""

    class Meta:
        verbose_name = "администратора"
        verbose_name_plural = "Администраторы"


class User(Model):
    """Telegram bot user. Authorized by Telegram ID — not a Django auth principal."""

    telegram_id = PositiveBigIntegerField("Телеграм ID", unique=True)
    telegram_name = CharField("Телеграм", max_length=256, null=True, blank=True)
    uuid = UUIDField(default=uuid4, unique=True)

    first_name = CharField("Имя", max_length=256, blank=True)
    last_name = CharField("Фамилия", max_length=256, blank=True)
    avatar = URLField("Аватар", null=True, blank=True)

    is_active = BooleanField("Активность", default=True)
    created_at = DateTimeField("Дата регистрации", auto_now_add=True)
    generations_reset_at = DateTimeField(
        "Сброс счётчика генераций",
        null=True,
        blank=True,
        help_text="Если задано, лимит презентаций считается только от листингов, "
                  "созданных после этой даты.",
    )

    class Meta:
        verbose_name = "пользователя"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.telegram_name or str(self.telegram_id)

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()
