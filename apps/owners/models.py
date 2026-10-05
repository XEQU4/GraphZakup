from django.db import models

from apps.companies.models import Supplier


class PersonIdentity(models.Model):
    """Exact verified IIN or a source/company-scoped identity; never a name-only merge."""
    scope_key = models.CharField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    iin = models.CharField(max_length=12, blank=True)
    is_verified = models.BooleanField(default=False)
    director = models.OneToOneField('Director', null=True, blank=True, on_delete=models.PROTECT)
    owner = models.OneToOneField('Owner', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['iin'], condition=models.Q(is_verified=True) & ~models.Q(iin=''),
                                              name='owners_verified_iin_unique'),
                       models.CheckConstraint(condition=models.Q(is_verified=False) | ~models.Q(iin=''),
                                              name='owners_verified_iin_required')]


class Owner(models.Model):
    iin = models.CharField(max_length=12, blank=True, default="", db_index=True)
    full_name = models.CharField(max_length=255)
    risk_score = models.PositiveSmallIntegerField(default=0)
    has_tax_debt = models.BooleanField(default=False)
    has_court_cases = models.BooleanField(default=False)
    is_bankrupt = models.BooleanField(default=False)
    blacklisted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Director(models.Model):
    iin = models.CharField(max_length=12, blank=True, default="", db_index=True)
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Ownership(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="ownerships")
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="ownerships")
    share_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=None)
    person_identity = models.ForeignKey(PersonIdentity, null=True, blank=True, on_delete=models.PROTECT)
    source_observation = models.ForeignKey('ingestion.SourceObservation', null=True, blank=True, on_delete=models.PROTECT)
    source = models.CharField(max_length=40, blank=True)
    identity_status = models.CharField(max_length=20, default='unverified')
    is_current = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    observed_from = models.DateTimeField(null=True, blank=True)
    observed_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['supplier', 'owner'], condition=models.Q(is_current=True),
                                              name='owners_current_ownership_unique'),
                       models.CheckConstraint(condition=models.Q(share_percent__isnull=True) | (
                           models.Q(share_percent__gte=0) & models.Q(share_percent__lte=100)), name='owners_share_percent_bounds')]

    def __str__(self):
        return f"{self.owner} -> {self.supplier}"


class Directorship(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="directorships")
    director = models.ForeignKey(Director, on_delete=models.CASCADE, related_name="directorships")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    person_identity = models.ForeignKey(PersonIdentity, null=True, blank=True, on_delete=models.PROTECT)
    source_observation = models.ForeignKey('ingestion.SourceObservation', null=True, blank=True, on_delete=models.PROTECT)
    source = models.CharField(max_length=40, blank=True)
    identity_status = models.CharField(max_length=20, default='unverified')
    is_current = models.BooleanField(default=True)
    observed_from = models.DateTimeField(null=True, blank=True)
    observed_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['supplier', 'director'], condition=models.Q(is_current=True),
                                              name='owners_current_directorship_unique')]

    def __str__(self):
        return f"{self.director} -> {self.supplier}"


class CourtCase(models.Model):
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="court_cases")
    case_number = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    status = models.CharField(max_length=100)
    decision_date = models.DateField(null=True, blank=True)
    source_url = models.URLField(blank=True)

    def __str__(self):
        return self.case_number


class TaxDebt(models.Model):
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="tax_debts")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    source = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.owner} - {self.amount}"


class Bankruptcy(models.Model):
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="bankruptcies")
    status = models.CharField(max_length=100)
    started_at = models.DateField()
    finished_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.owner} - {self.status}"
