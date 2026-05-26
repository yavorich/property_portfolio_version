from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0003_botsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="botsettings",
            name="contact_url",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Куда ведёт слово «here» в сообщении про лимит презентаций "
                    "(например, https://t.me/your_account)."
                ),
                max_length=512,
                verbose_name="Контактная ссылка",
            ),
        ),
    ]
