from django.conf import settings
from django.db import models


class Opportunity(models.Model):
    source_key = models.CharField(max_length=180, unique=True)
    current = models.ForeignKey(
        "Notice", null=True, blank=True, on_delete=models.SET_NULL, related_name="current_for"
    )
    updated_at = models.DateTimeField(auto_now=True)


class Notice(models.Model):
    publication_id = models.CharField(max_length=40, unique=True)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="notices")
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    published = models.DateField(db_index=True)
    title = models.TextField()
    description = models.TextField(blank=True)
    buyer = models.TextField(blank=True)
    country = models.CharField(max_length=3, blank=True, db_index=True)
    kind = models.CharField(max_length=40, blank=True, db_index=True)
    language = models.CharField(max_length=10, blank=True)
    deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    checksum = models.CharField(max_length=64)
    quality = models.CharField(max_length=20, default="search")
    retrieved_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published", "-id"]


class Artifact(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="artifacts")
    checksum = models.CharField(max_length=64)
    content = models.TextField()
    format = models.CharField(max_length=8)
    retrieved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notice", "checksum"], name="unique_notice_artifact")
        ]


class Lot(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name="lots")
    identifier = models.CharField(max_length=80)
    title = models.TextField(blank=True)
    description = models.TextField(blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    value = models.DecimalField(max_digits=24, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, blank=True)
    payload = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notice", "identifier"], name="unique_notice_lot")
        ]


class ImportRun(models.Model):
    query = models.TextField()
    status = models.CharField(max_length=20, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    seen = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    unchanged = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list)
    cursor = models.TextField(blank=True)
    source_total = models.PositiveIntegerField(null=True)
    truncated = models.BooleanField(default=False)


class Watch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE)
    stage = models.CharField(max_length=20, default="saved")
    note = models.TextField(blank=True)
    seen_notice = models.ForeignKey(Notice, null=True, on_delete=models.SET_NULL)
    seen_checksum = models.CharField(max_length=64, blank=True)
    seen_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "opportunity"], name="unique_user_watch")
        ]


class SavedSearch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    query = models.CharField(max_length=500, blank=True)
    country = models.CharField(max_length=3, blank=True)
    status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    countries = models.JSONField(default=list)
    exclusions = models.JSONField(default=list)


class EvidenceNote(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE)
    model = models.CharField(max_length=200)
    input_hash = models.CharField(max_length=64)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
