from django.db import models

from apps.companies.models import Supplier


class Contract(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="contracts")
    customer = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name='purchases')
    # Tender numbers are not unique: a tender may have several
    # contracts/amendments, and the registry often leaves this field empty.
    tender_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True
    )
    # Numeric goszakup ID for /egzcontract/cpublic/show/<id> links
    contract_gos_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    # Unique contract identifier used as the import key
    contract_number = models.CharField(
        max_length=255,
        unique=True,
        db_index=True
    )

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

    @property
    def goszakup_url(self):
        if self.contract_gos_id:
            return f"https://goszakup.gov.kz/ru/egzcontract/cpublic/show/{self.contract_gos_id}"
        return None
