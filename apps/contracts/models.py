from django.db import models

from apps.companies.models import Supplier


class Contract(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="contracts")
    tender_id = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=1000)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    winner = models.BooleanField(default=False)
    customer_name = models.CharField(max_length=500, blank=True)
    customer_bin = models.CharField(max_length=12, blank=True)
    contract_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-contract_date"]

    def __str__(self):
        return self.title
