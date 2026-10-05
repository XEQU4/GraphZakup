"""Archive original roles; create company-scoped identities without a name merge."""
import hashlib
from decimal import Decimal
from django.db import migrations


def isolate(apps, schema_editor):
    db = schema_editor.connection.alias
    Person = apps.get_model('owners', 'PersonIdentity')
    Identity = apps.get_model('ingestion', 'PersonSourceIdentity')
    Candidate = apps.get_model('ingestion', 'IdentityCandidate')
    for model_name, field in (('Directorship', 'director'), ('Ownership', 'owner')):
        Role = apps.get_model('owners', model_name)
        Representation = apps.get_model('owners', 'Director' if field == 'director' else 'Owner')
        for old in Role.objects.using(db).filter(source='legacy', is_current=True).select_related(field, 'source_observation').iterator():
            representation = getattr(old, field)
            key = f'legacy-company:{old.supplier_id}:{field}:{representation.pk}'
            scoped_representation = Representation.objects.using(db).create(full_name=representation.full_name, iin='')
            person = Person.objects.using(db).create(scope_key=key, full_name=representation.full_name,
                                                    **{field + '_id': scoped_representation.pk})
            Role.objects.using(db).filter(pk=old.pk).update(is_current=False)
            values = {'supplier_id': old.supplier_id, field + '_id': scoped_representation.pk,
                      'person_identity': person, 'source': 'legacy', 'source_observation_id': old.source_observation_id,
                      'identity_status': 'unverified', 'observed_from': old.source_observation.observed_at,
                      'start_date': old.start_date, 'end_date': old.end_date}
            if field == 'owner':
                values['share_percent'] = None  # Old default 100 does not prove a share.
            Role.objects.using(db).create(**values)
            normalized = ' '.join(representation.full_name.casefold().split())
            identity = Identity.objects.using(db).create(person=person, supplier_id=old.supplier_id,
                source='legacy', source_key='scoped:' + hashlib.sha256(key.encode()).hexdigest(), role=field,
                observed_name=representation.full_name, normalized_name=normalized,
                observation_id=old.source_observation_id)
            for other in Identity.objects.using(db).filter(source='legacy', source_key__startswith='scoped:',
                    normalized_name=normalized).exclude(pk=identity.pk).iterator():
                left, right = sorted((identity.pk, other.pk))
                Candidate.objects.using(db).get_or_create(left_id=left, right_id=right, defaults={
                    'confidence': Decimal('0.250'), 'evidence': {'rule': 'legacy_same_name_v1',
                    'requires_identifier_verification': True}})


class Migration(migrations.Migration):
    dependencies = [('ingestion', '0003_legacy_provenance')]
    operations = [migrations.RunPython(isolate, migrations.RunPython.noop)]
