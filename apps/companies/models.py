from django.db import models


class Supplier(models.Model):
    bin = models.CharField(max_length=12, unique=True, db_index=True)
    name = models.CharField(max_length=500)
    registration_date = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    description = models.TextField(blank=True)
    risk_score = models.PositiveSmallIntegerField(default=0)
    region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.bin})"
