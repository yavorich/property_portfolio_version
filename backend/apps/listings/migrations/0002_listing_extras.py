from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="reference_code",
            field=models.CharField(blank=True, max_length=32, verbose_name="Reference"),
        ),
        migrations.AddField(
            model_name="listing",
            name="property_type",
            field=models.CharField(blank=True, max_length=64, verbose_name="Тип объекта"),
        ),
        migrations.AddField(
            model_name="listing",
            name="features",
            field=models.JSONField(blank=True, default=list, verbose_name="Особенности"),
        ),
        migrations.AddField(
            model_name="listing",
            name="presentation",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="listings/%Y/%m/presentation/",
                verbose_name="Презентация (PDF)",
            ),
        ),
    ]
