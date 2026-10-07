"""Probe free local inference on synthetic data; optionally serve the saved demo."""
import argparse
from datetime import date
import importlib
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:11434', help='Native local Ollama base URL.')
    parser.add_argument('--serve', action='store_true', help='Serve synthetic saved results on localhost after the probe.')
    parser.add_argument('--serve-saved', action='store_true', help='Open the last synthetic demo without new model requests.')
    parser.add_argument('--port', type=int, default=8766)
    options = parser.parse_args()
    if not 1024 <= options.port <= 65535:
        parser.error('Port must be between 1024 and 65535.')
    sys.path.insert(0, str(ROOT))
    folder = ROOT / 'artifacts/local-ai'
    folder.mkdir(parents=True, exist_ok=True)
    if options.serve_saved:
        saved = json.loads((folder / 'latest-probe.json').read_text(encoding='utf-8'))
        saved_name = Path(saved['database']).name
        try:
            uuid.UUID(saved_name.removeprefix('demo_').removesuffix('.sqlite3'))
        except ValueError:
            parser.error('Invalid saved synthetic database name.')
        database = folder / saved_name
        if not saved.get('synthetic_only') or not saved_name.startswith('demo_') or not saved_name.endswith('.sqlite3'):
            parser.error('Only the saved synthetic demo can be opened.')
        if not database.resolve().is_relative_to(folder.resolve()) or not database.is_file():
            parser.error('The saved synthetic demo database is missing.')
    else:
        database = folder / ('demo_' + uuid.uuid4().hex + '.sqlite3')
        assert database.resolve().is_relative_to(folder.resolve()) and not database.exists()
    config = importlib.import_module('config.test_settings')
    config.DATABASES['default']['NAME'] = str(database)
    config.AI_PROVIDER = 'ollama'
    config.AI_MODEL = 'qwen3:4b'
    config.AI_BASE_URL = options.url
    config.AI_EXPERIMENTAL_SCORING = False
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.test import Client
    from django.utils import timezone
    from apps.ai.jobs import request_analysis, analyse_cluster_task
    from apps.ai.models import AnalysisState
    from apps.ai.providers import configuration, ProviderError
    from apps.companies.models import Supplier
    from apps.graph.models import RiskCluster
    from apps.graph.services import rebuild_clusters
    from apps.ingestion.models import IngestionRun, SourceObservation
    from apps.owners.models import Director, PersonIdentity, Directorship
    try:
        configuration()  # Reject paid/remote/cloud providers before making requests.
    except ProviderError as error:
        parser.error(str(error))
    if options.serve_saved:
        print(f'Saved synthetic demo: http://127.0.0.1:{options.port}/clusters/ . Press Ctrl+C to stop.', flush=True)
        call_command('runserver', f'127.0.0.1:{options.port}', use_reloader=False, insecure=True)
        return 0
    call_command('migrate', interactive=False, verbosity=0)
    results = []
    client = Client()
    for case, count in (('weak_contacts', 2), ('confirmed_director', 2), ('dense_contacts', 20), ('experimental_score', 2)):
        settings.AI_EXPERIMENTAL_SCORING = case == 'experimental_score'
        offset = Supplier.objects.count() + 100
        companies = [Supplier.objects.create(bin=f'{offset+i:012}', name=f'Synthetic {case} company {i+1}',
                     address=f'Synthetic {case} office') for i in range(count)]
        if case == 'confirmed_director':
            director = Director.objects.create(full_name='Synthetic identifier-confirmed director')
            person = PersonIdentity.objects.create(scope_key='synthetic-demo-director', full_name=director.full_name,
                director=director, iin='000000000099', is_verified=True)
            run = IngestionRun.objects.create(mode='enrich', status='succeeded')
            for company in companies:
                observation = SourceObservation.objects.create(run=run, source='synthetic_demo',
                    subject_key=f'company:{company.bin}', supplier=company, status='success',
                    fingerprint=f'{company.pk:064}', observed_at=timezone.now(),
                    normalized_values={'director_name': director.full_name, 'director_iin': person.iin,
                                       'director_iin_verified': True})
                Directorship.objects.create(supplier=company, director=director, person_identity=person,
                    source='synthetic_demo', source_observation=observation, identity_status='verified',
                    start_date=date(2020, 1, 1), end_date=date(2030, 1, 1))
        rebuild_clusters()
        cluster = RiskCluster.objects.get(is_active=True, suppliers=companies[0])
        with patch('apps.ai.jobs.enqueue'):
            job, _ = request_analysis(None, cluster.pk)
        started = time.monotonic()
        analyse_cluster_task.run(job.pk)
        duration = time.monotonic() - started
        job.refresh_from_db()
        with patch('apps.ai.jobs.enqueue'), patch('requests.Session.post', side_effect=AssertionError('Unexpected repeat inference')):
            repeated, created = request_analysis(None, cluster.pk)
        assert not created and repeated.pk == job.pk
        data = client.get(f'/analysis/{cluster.uuid}/').json()
        assert data['explanation']['id'] == job.explanation_id
        assert data['metrics']['review_priority'] == job.analysis.metrics['review_priority']
        assert AnalysisState.objects.get(cluster=cluster).explanation_id == job.explanation_id
        assert client.get(f'/clusters/{cluster.uuid}/').status_code == 200
        item = {'case': case, 'companies': count, 'status': job.status, 'error_code': job.error_code,
                'seconds': round(duration, 3), 'review_priority': job.analysis.metrics['review_priority'],
                'experimental_model_score': job.explanation.experimental_score,
                'usage': job.explanation.usage, 'url': f'http://127.0.0.1:{options.port}/clusters/{cluster.uuid}/',
                'repeat_reused': True}
        results.append(item)
        print(json.dumps(item), flush=True)
    passed = all(item['status'] == 'succeeded' for item in results)
    report = {'status': 'passed' if passed else 'fallback_observed', 'synthetic_only': True,
              'database': str(database.relative_to(ROOT)), 'results': results,
              'independent_prediction_quality': 'unverified'}
    (folder / 'latest-probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Local AI probe passed.' if passed else 'Model failure observed; saved template fallback is available.', flush=True)
    if options.serve:
        print(f'Synthetic demo: http://127.0.0.1:{options.port}/clusters/ . Press Ctrl+C to stop.', flush=True)
        call_command('runserver', f'127.0.0.1:{options.port}', use_reloader=False, insecure=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
