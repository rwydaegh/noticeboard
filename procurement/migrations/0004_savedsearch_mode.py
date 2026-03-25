from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0003_opportunity_redirect"),
    ]

    operations = [
        migrations.AddField(
            model_name="savedsearch",
            name="mode",
            field=models.CharField(default="keyword", max_length=10),
        ),
    ]
