"""Start the dedicated worker only after the configured local model is available."""

import json
import os
import sys

import requests

MODEL_METADATA_LIMIT = 1024 * 1024
WORKER_ARGUMENTS = (
    "celery", "-A", "config", "worker", "--loglevel=info", "--concurrency=1",
    "--queues=iz2-ai", "--hostname=ai@%h",
)


def require_local_model(configuration):
    """One bounded metadata request; never pull weights or perform inference."""
    if configuration.provider != "ollama":
        return
    with requests.Session() as session:
        session.trust_env = False
        with session.post(
            configuration.base_url + "/api/show", json={"model": configuration.model},
            timeout=(3, 5), allow_redirects=False, stream=True,
        ) as response:
            if response.status_code != 200:
                raise ValueError("model_metadata_unavailable")
            body = bytearray()
            for chunk in response.iter_content(chunk_size=16384):
                body.extend(chunk)
                if len(body) > MODEL_METADATA_LIMIT:
                    raise ValueError("model_metadata_too_large")
    metadata = json.loads(body)
    if not isinstance(metadata, dict) or not isinstance(metadata.get("details"), dict):
        raise ValueError("model_metadata_invalid")


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from apps.ai.providers import configuration, ProviderError
    try:
        require_local_model(configuration())
    except (ProviderError, requests.RequestException, ValueError):
        # Do not expose endpoint credentials, model payloads or transport errors.
        print("AI worker not started: verify the configured provider and local model initialization.", file=sys.stderr)
        return 1
    os.execvp(WORKER_ARGUMENTS[0], WORKER_ARGUMENTS)


if __name__ == "__main__":
    raise SystemExit(main())
