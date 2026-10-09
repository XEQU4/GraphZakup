"""Owned native development worker/beat entry point; production uses Linux Compose."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUNTIME = ROOT / 'artifacts' / 'background'
NODE = 'iz2-background@local'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['worker', 'ai-worker', 'beat', 'kick', 'status', 'ping', 'shutdown'])
    args = parser.parse_args()
    # Explicitly running this helper opts in for these processes, not the web app.
    os.environ.update(ENABLE_SCHEDULED_IMPORT='true', ENABLE_SCHEDULED_KGD='true', ENABLE_KGD_CHECKS='true',
                      GPG_LOG_TO_FILES='false', GPG_DISABLE_LOGGING_INIT='true', AI_ALLOW_PAID='false',
                      ENABLE_BACKGROUND_AI='true', AI_PROVIDER='ollama', AI_MODEL='qwen3:4b',
                      AI_BASE_URL='http://127.0.0.1:11434', AI_TIMEOUT_SECONDS='180', AI_MAX_OUTPUT_TOKENS='2048')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from config.celery import app
    from django.conf import settings
    from redis import Redis
    if args.role == 'status':
        from apps.ingestion.background import collection_status
        state = collection_status()
        print('Saved companies: {companies}; contracts: {contracts}'.format(**state['totals']))
        print('Last cycle: ' + state['latest_cycle'].get('finished_at', 'not completed yet'))
        for source, detail in state['sources'].items():
            print(source + ': ' + detail.get('status', 'not started') + '; next due (UTC): ' + detail.get('next_due', '-'))
            if detail.get('errors'):
                print('  Saved errors: ' + json.dumps(detail['errors']))
            if detail.get('cursor'):
                print('  Crawl progress: ' + json.dumps(detail['cursor']))
        print('Contract repair backlog: ' + str(state['contract_repair']['unresolved']))
        print('Companies awaiting first profile attempts: ' + str(state['enrichment_backlog']))
        print('KGD coverage: ' + json.dumps(state['kgd_coverage']))
        return
    with Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=5, socket_timeout=5) as broker:
        broker.ping()
    if args.role == 'ping':
        print('Redis ready')
        return
    if args.role == 'shutdown':
        app.control.broadcast('shutdown', destination=[NODE, 'iz2-ai@local'])
        print('Owned workers requested to finish active tasks and stop')
        return
    if args.role == 'kick':
        # A solo worker cannot answer control pings while collecting. Queueing
        # through the checked broker also works while the worker is busy.
        app.send_task('apps.core.tasks.collect_background', queue='ingestion', expires=840)
        print('First bounded cycle queued')
        return
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / (args.role + '-pid.json')).write_text(json.dumps({'pid': os.getpid(), 'role': args.role}), encoding='utf-8')
    if args.role in ('worker', 'ai-worker'):
        # Do not consume historical tasks from the user's existing default queue.
        ai = args.role == 'ai-worker'
        app.worker_main(['worker', '--pool=solo', '--concurrency=1', '--queues=' + ('iz2-ai' if ai else 'ingestion'),
                         '--hostname=' + ('iz2-ai@local' if ai else NODE), '--loglevel=INFO', '--without-gossip', '--without-mingle'])
    else:
        app.Beat(loglevel='INFO', scheduler='celery.beat:PersistentScheduler', max_interval=30,
                 schedule=str(RUNTIME / 'beat-schedule'), pidfile=str(RUNTIME / 'beat.pid')).run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        # Connection strings and source bodies must not enter startup diagnostics.
        print('Background process failed: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
