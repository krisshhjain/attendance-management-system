from django.core.exceptions import ValidationError
from django.db import models


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "name"]

    def clean(self):
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": "Holiday name cannot be empty."})
        duplicate = type(self).objects.filter(date=self.date).exclude(pk=self.pk)
        if self.date and duplicate.exists():
            raise ValidationError({"date": "A holiday already exists for this date."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.date})"
