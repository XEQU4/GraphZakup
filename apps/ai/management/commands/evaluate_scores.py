import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from apps.ai.evaluation import compare_scores


class Command(BaseCommand):
    help = 'Compare model/rule estimates with independent review-priority labels; never change application scores.'

    def add_arguments(self, parser):
        parser.add_argument('input', help='Local JSON case file; keep personal evaluation data under ignored artifacts/.')

    def handle(self, *args, **options):
        try:
            path = Path(options['input'])
            if path.stat().st_size > 2_000_000:
                raise ValueError('Evaluation file is too large.')
            result = compare_scores(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError) as error:
            raise CommandError('Invalid evaluation file or cases.') from None
        self.stdout.write(json.dumps(result))
