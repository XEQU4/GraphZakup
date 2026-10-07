"""Serve the compiled React application without changing saved domain data."""
import json
from pathlib import Path, PurePosixPath
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render


def home(request):
    return redirect('/app/')


def index(request, path=''):
    candidates = [Path(settings.STATIC_ROOT) / 'frontend/vite-manifest.json', Path(settings.BASE_DIR) / 'static/frontend/vite-manifest.json']
    manifest = next((item for item in candidates if item.is_file()), None)
    if manifest is None:
        return HttpResponse('The React interface has not been built. Run npm.cmd ci and npm.cmd run build in frontend, then python manage.py collectstatic --noinput and restart Django.', status=503, content_type='text/plain; charset=utf-8')
    try:
        entries = json.loads(manifest.read_text(encoding='utf-8'))
        entry = entries['index.html']
        def asset(name):
            value = PurePosixPath(name)
            if not isinstance(name, str) or value.is_absolute() or '..' in value.parts or not str(value).startswith('assets/'):
                raise ValueError('Invalid frontend asset path.')
            # Vite imports refer to its own hashed names. A second storage hash
            # would give the entry two URLs, re-running React and its contexts.
            return settings.STATIC_URL.rstrip('/') + '/frontend/' + str(value)
        context = {'entry_script':asset(entry['file']), 'entry_styles':[asset(name) for name in entry.get('css', [])]}
        response = render(request, 'frontend/index.html', context)
        response['Cache-Control'] = 'no-cache'
        return response
    except (KeyError, TypeError, ValueError, OSError):
        return HttpResponse('The React build or static manifest is incomplete. Rebuild frontend, collect static assets and restart Django.', status=503, content_type='text/plain; charset=utf-8')
