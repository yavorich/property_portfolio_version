from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="generations_reset_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Если задано, лимит презентаций считается только от листингов, "
                    "созданных после этой даты."
                ),
                null=True,
                verbose_name="Сброс счётчика генераций",
            ),
        ),
    ]
