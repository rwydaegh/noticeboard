from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="watch",
            name="seen_checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="watch",
            name="seen_payload",
            field=models.JSONField(default=dict),
        ),
    ]
