from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0002_listing_extras"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotSettings",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "support_url",
                    models.URLField(
                        blank=True,
                        help_text=(
                            "Например, https://t.me/your_support — будет показана "
                            "кнопкой в /start и /help."
                        ),
                        max_length=512,
                        verbose_name="Ссылка на поддержку",
                    ),
                ),
                (
                    "support_button_label",
                    models.CharField(
                        blank=True,
                        default="💬 Support",
                        max_length=64,
                        verbose_name="Подпись кнопки",
                    ),
                ),
            ],
            options={
                "verbose_name": "настройки бота",
                "verbose_name_plural": "Настройки бота",
            },
        ),
    ]
