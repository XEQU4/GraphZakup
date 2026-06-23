import uuid

from django.db import models
from django.db.models import Sum

from apps.companies.models import Supplier


class Connection(models.Model):
    OWNER = "owner"
    DIRECTOR = "director"
    ADDRESS = "address"
    PHONE = "phone"
    EMAIL = "email"
    CUSTOMER = "customer"

    CONNECTION_TYPES = [
        (OWNER, "Common Owner"),
        (DIRECTOR, "Common Director"),
        (ADDRESS, "Common Address"),
        (PHONE, "Common Phone"),
        (EMAIL, "Common Email"),
        (CUSTOMER, "Общий заказчик"),
    ]

    source_supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="outgoing_connections")
    target_supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="incoming_connections")
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)
    weight = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "connection_type"
                ]
            )
        ]

    def __str__(self):
        return (
            f"{self.source_supplier} -> "
            f"{self.target_supplier}"
        )


class RiskCluster(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    risk_score = models.PositiveSmallIntegerField(default=0)
    total_contract_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    explanation = models.TextField(blank=True)
    suppliers = models.ManyToManyField(Supplier, related_name="risk_clusters")
    ai_explanation = models.TextField(blank=True)
    last_analyzed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-risk_score"]

    def __str__(self):
        return f"{self.name} ({self.risk_score})"

    def update_total_amount(self):
        total = (
                self.suppliers
                .aggregate(
                    total=Sum("contracts__amount")
                )["total"]
                or 0
        )

        self.total_contract_amount = total
        self.save(
            update_fields=["total_contract_amount"]
        )
