import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0002_watch_seen_checksum_watch_seen_payload"),
    ]

    operations = [
        migrations.AddField(
            model_name="opportunity",
            name="redirect",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="procurement.opportunity",
            ),
        ),
    ]
