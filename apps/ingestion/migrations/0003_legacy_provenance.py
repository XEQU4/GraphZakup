"""Preserve legacy facts as unverified observations; no guessed identity or dates."""
import hashlib
import json
import re

from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    db = schema_editor.connection.alias
    Run = apps.get_model('ingestion', 'IngestionRun')
    Observation = apps.get_model('ingestion', 'SourceObservation')
    Selected = apps.get_model('ingestion', 'SelectedFact')
    Person = apps.get_model('owners', 'PersonIdentity')
    Identity = apps.get_model('ingestion', 'PersonSourceIdentity')
    Supplier = apps.get_model('companies', 'Supplier')
    Contract = apps.get_model('contracts', 'Contract')
    now = timezone.now()
    run = Run.objects.using(db).create(mode='legacy', status='succeeded', stage='complete', finished_at=now)

    def observe(key, values, supplier_id=None, contract_id=None):
        digest = hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return Observation.objects.using(db).create(
            run=run, source='legacy', subject_key=key, status='not_checked', raw_values=values,
            normalized_values=values, parser_version='legacy-backfill-1', observed_at=now,
            fingerprint=digest, supplier_id=supplier_id, contract_id=contract_id,
        )

    fields = ('bin', 'name', 'director_name', 'address', 'phone', 'email', 'registration_date',
              'region', 'city', 'oked', 'company_status', 'website', 'resident_status',
              'company_size', 'kopf', 'economic_sector')
    for supplier in Supplier.objects.using(db).order_by('pk').iterator():
        values = {field: str(getattr(supplier, field)) if getattr(supplier, field) is not None else None for field in fields}
        obs = observe(f'company:{supplier.bin}', values, supplier.pk)
        Selected.objects.using(db).bulk_create([
            Selected(supplier_id=supplier.pk, field=field, observation=obs)
            for field, value in values.items() if value not in (None, '') and field != 'bin'
        ])
    for contract in Contract.objects.using(db).order_by('pk').iterator():
        values = {field: str(getattr(contract, field)) for field in (
            'contract_number', 'contract_gos_id', 'tender_id', 'title', 'amount',
            'customer_name', 'customer_bin', 'contract_date', 'supplier_id')}
        observe(f'contract:{contract.pk}', values, contract.supplier_id, contract.pk)
        if re.fullmatch(r'[0-9]{12}', contract.customer_bin or ''):
            customer, created = Supplier.objects.using(db).get_or_create(
                bin=contract.customer_bin,
                defaults={'name': contract.customer_name or contract.customer_bin, 'is_supplier': False, 'is_customer': True},
            )
            if not customer.is_customer:
                Supplier.objects.using(db).filter(pk=customer.pk).update(is_customer=True)
            Contract.objects.using(db).filter(pk=contract.pk).update(customer_id=customer.pk)
            if created:
                obs = observe(f'company:{customer.bin}', {'bin': customer.bin, 'name': customer.name}, customer.pk, contract.pk)
                Selected.objects.using(db).create(supplier_id=customer.pk, field='name', observation=obs)

    for model_name, person_field in (('Directorship', 'director'), ('Ownership', 'owner')):
        Role = apps.get_model('owners', model_name)
        for role in Role.objects.using(db).select_related(person_field, 'supplier').order_by('pk').iterator():
            representation = getattr(role, person_field)
            scope = f'legacy-{person_field}:{representation.pk}'
            person, _ = Person.objects.using(db).get_or_create(
                scope_key=scope, defaults={'full_name': representation.full_name, 'iin': representation.iin,
                                          person_field + '_id': representation.pk, 'is_verified': False},
            )
            values = {'full_name': representation.full_name, 'iin': representation.iin,
                      'start_date': str(role.start_date) if role.start_date else None,
                      'end_date': str(role.end_date) if role.end_date else None}
            if person_field == 'owner':
                values['share_percent'] = str(role.share_percent) if role.share_percent is not None else None
            obs = observe(f'{person_field}_role:{role.pk}', values, role.supplier_id)
            Identity.objects.using(db).create(
                person=person, supplier_id=role.supplier_id, source='legacy', source_key=f'{person_field}_role:{role.pk}',
                role=person_field, observed_name=representation.full_name,
                normalized_name=' '.join(representation.full_name.casefold().split()), observation=obs,
            )
            Role.objects.using(db).filter(pk=role.pk).update(
                person_identity=person, source='legacy', source_observation=obs, identity_status='unverified',
            )

    Checkpoint = apps.get_model('ingestion', 'SourceCheckpoint')
    Setting = apps.get_model('core', 'SystemSetting')
    for stream, key in (('initial', 'last_import_page'), ('full', 'full_import_page')):
        value = Setting.objects.using(db).filter(key=key).values_list('value', flat=True).first()
        if value and value.isdigit() and int(value) > 0:
            Checkpoint.objects.using(db).get_or_create(
                source='goszakup_contracts', stream=stream, defaults={'next_page': int(value), 'run': run},
            )


class Migration(migrations.Migration):
    dependencies = [
        ('ingestion', '0002_initial'),
        ('owners', '0003_alter_directorship_unique_together_and_more'),
        ('contracts', '0006_contract_customer'),
        ('core', '0001_initial'),
    ]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
