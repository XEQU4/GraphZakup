"""Deployment-only checks for shared authentication and trusted TLS forwarding."""
from django.conf import settings
from django.core.checks import register, Tags, Warning


@register(Tags.security, deploy=True)
def authentication_deployment_checks(app_configs, **kwargs):
    messages = []
    if not settings.AUTH_THROTTLE_REDIS_URL:
        messages.append(Warning(
            'Authentication limits are process-local without AUTH_THROTTLE_REDIS_URL.',
            hint='Configure the shared Redis limiter before serving public requests.', id='iz2.W001'))
    if settings.SECURE_PROXY_SSL_HEADER and not settings.AUTH_TRUSTED_PROXY_CIDRS:
        messages.append(Warning(
            'Forwarded TLS headers are ignored without AUTH_TRUSTED_PROXY_CIDRS.',
            hint='Allow only the address of the reverse proxy that overwrites the forwarding headers.',
            id='iz2.W002'))
    return messages
