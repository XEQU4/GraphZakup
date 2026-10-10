"""Container HTTP process settings; application secrets stay in Django settings."""

import os


def positive_integer(name, default, *, minimum=1):
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


bind = f"0.0.0.0:{positive_integer('PORT', 8000)}"
workers = positive_integer("WEB_CONCURRENCY", 2)
timeout = positive_integer("GUNICORN_TIMEOUT", 120)
graceful_timeout = positive_integer("GUNICORN_GRACEFUL_TIMEOUT", 30)
max_requests = positive_integer("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = positive_integer("GUNICORN_MAX_REQUESTS_JITTER", 100, minimum=0)
# A writable tmpfs works with a read-only application filesystem.
worker_tmp_dir = "/tmp"
accesslog = "-"
errorlog = "-"
capture_output = True
# Django applies the single trusted-proxy contract. Gunicorn must not separately
# trust forwarded TLS headers, even from a loopback caller.
forwarded_allow_ips = ""
# Avoid query strings, which can contain identifiers. Never log request headers.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(L)s'
