import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("query", models.TextField()),
                ("status", models.CharField(default="running", max_length=20)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("seen", models.PositiveIntegerField(default=0)),
                ("created", models.PositiveIntegerField(default=0)),
                ("unchanged", models.PositiveIntegerField(default=0)),
                ("errors", models.JSONField(default=list)),
                ("cursor", models.TextField(blank=True)),
                ("source_total", models.PositiveIntegerField(null=True)),
                ("truncated", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="Notice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("publication_id", models.CharField(max_length=40, unique=True)),
                ("reference", models.CharField(blank=True, db_index=True, max_length=100)),
                ("published", models.DateField(db_index=True)),
                ("title", models.TextField()),
                ("description", models.TextField(blank=True)),
                ("buyer", models.TextField(blank=True)),
                ("country", models.CharField(blank=True, db_index=True, max_length=3)),
                ("kind", models.CharField(blank=True, db_index=True, max_length=40)),
                ("language", models.CharField(blank=True, max_length=10)),
                ("deadline", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("payload", models.JSONField(default=dict)),
                ("checksum", models.CharField(max_length=64)),
                ("quality", models.CharField(default="search", max_length=20)),
                ("retrieved_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-published", "-id"],
            },
        ),
        migrations.CreateModel(
            name="EvidenceNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("model", models.CharField(max_length=200)),
                ("input_hash", models.CharField(max_length=64)),
                ("result", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "notice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="procurement.notice"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Opportunity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("source_key", models.CharField(max_length=180, unique=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "current",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="current_for",
                        to="procurement.notice",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="notice",
            name="opportunity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notices",
                to="procurement.opportunity",
            ),
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("countries", models.JSONField(default=list)),
                ("exclusions", models.JSONField(default=list)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SavedSearch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("query", models.CharField(blank=True, max_length=500)),
                ("country", models.CharField(blank=True, max_length=3)),
                ("status", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Lot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("identifier", models.CharField(max_length=80)),
                ("title", models.TextField(blank=True)),
                ("description", models.TextField(blank=True)),
                ("deadline", models.DateTimeField(blank=True, null=True)),
                ("value", models.DecimalField(decimal_places=2, max_digits=24, null=True)),
                ("currency", models.CharField(blank=True, max_length=3)),
                ("payload", models.JSONField(default=dict)),
                (
                    "notice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lots",
                        to="procurement.notice",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("notice", "identifier"), name="unique_notice_lot"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Artifact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("checksum", models.CharField(max_length=64)),
                ("content", models.TextField()),
                ("format", models.CharField(max_length=8)),
                ("retrieved_at", models.DateTimeField(auto_now_add=True)),
                (
                    "notice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="procurement.notice",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("notice", "checksum"), name="unique_notice_artifact"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Watch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("stage", models.CharField(default="saved", max_length=20)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "opportunity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="procurement.opportunity"
                    ),
                ),
                (
                    "seen_notice",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="procurement.notice",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "opportunity"), name="unique_user_watch"
                    )
                ],
            },
        ),
    ]
