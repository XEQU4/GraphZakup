"""Atomic authentication quotas and an explicit single trusted-proxy policy."""
import ipaddress
import math
import threading
import time
import unicodedata
import uuid
from collections.abc import Mapping
from functools import lru_cache

import redis
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.crypto import salted_hmac
from django.utils.deprecation import MiddlewareMixin
from redis.backoff import NoBackoff
from redis.retry import Retry
from rest_framework.throttling import BaseThrottle

from .common import ApiError


class ThrottleUnavailable(Exception):
    """The shared quota store cannot safely admit an authentication attempt."""


def _address(value):
    try:
        if not isinstance(value, str) or '%' in value:
            return None
        address = ipaddress.ip_address(value)
        return address.ipv4_mapped if getattr(address, 'ipv4_mapped', None) else address
    except (ValueError, TypeError):
        return None


def trusted_proxy(request):
    peer = _address(request.META.get('REMOTE_ADDR'))
    return peer is not None and any(peer in ipaddress.ip_network(network)
        for network in settings.AUTH_TRUSTED_PROXY_CIDRS)


def client_address(request):
    # Caddy overwrites this one header. Arbitrary X-Forwarded-For chains are never
    # parsed; direct clients cannot choose their own authentication quota.
    if trusted_proxy(request):
        forwarded = _address(request.META.get('HTTP_X_IZ2_CLIENT_IP'))
        if forwarded is not None:
            return str(forwarded)
    return str(_address(request.META.get('REMOTE_ADDR')) or 'unknown')


class TrustedProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not trusted_proxy(request):
            # SecurityMiddleware otherwise trusts this header from every peer
            # whenever SECURE_PROXY_SSL_HEADER is enabled.
            request.META.pop('HTTP_X_FORWARDED_PROTO', None)
            request.META.pop('HTTP_X_IZ2_CLIENT_IP', None)
        return self.get_response(request)


# One Lua operation checks and consumes all dimensions. Redis server time avoids
# worker-clock drift; a rolling window avoids double bursts at minute boundaries.
# Rejected requests do not extend an account lockout. Only HMAC keys are stored.
_CONSUME = """
local stamp = redis.call('TIME')
local now = stamp[1] * 1000 + math.floor(stamp[2] / 1000)
local duration = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local wait = 0
for _, key in ipairs(KEYS) do
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - duration)
    if redis.call('ZCARD', key) >= limit then
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        wait = math.max(wait, tonumber(oldest[2]) + duration - now)
    end
end
if wait > 0 then return wait end
for _, key in ipairs(KEYS) do
    redis.call('ZADD', key, now, ARGV[3])
    redis.call('PEXPIRE', key, duration)
end
return 0
"""
_local_lock = threading.Lock()


@lru_cache(maxsize=4)
def _redis_client(url):
    return redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1,
        retry=Retry(NoBackoff(), 0), max_connections=16)


def _consume(keys, limit, duration):
    if settings.AUTH_THROTTLE_REDIS_URL:
        try:
            wait_ms = _redis_client(settings.AUTH_THROTTLE_REDIS_URL).eval(
                _CONSUME, len(keys), *keys, duration * 1000, limit, uuid.uuid4().hex)
        except (redis.RedisError, ValueError, OSError) as error:
            # No local fallback: that would reset the shared limit on an outage.
            raise ThrottleUnavailable from error
        return wait_ms / 1000
    with _local_lock:
        now = time.time()
        histories = {key: [stamp for stamp in cache.get(key, []) if stamp > now - duration]
            for key in keys}
        wait = max((stamps[0] + duration - now for stamps in histories.values()
            if len(stamps) >= limit), default=0)
        if not wait:
            for key, stamps in histories.items():
                cache.set(key, [*stamps, now], timeout=duration)
        return wait


def consume_auth_quota(request, scope, username=None):
    rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'][scope]
    count, period = rate.split('/')
    duration = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[period[0]]
    identities = [('ip', client_address(request))]
    if scope == 'api_login' and isinstance(username, str) and username.strip():
        identities.append(('username', unicodedata.normalize('NFKC', username.strip()).casefold()))
    elif scope in {'api_account', 'api_password'} and request.user.is_authenticated:
        identities.append(('user', str(request.user.pk)))
    keys = [f'{settings.AUTH_THROTTLE_KEY_PREFIX}:{scope}:{kind}:' +
        salted_hmac('iz2-auth-throttle', identity, algorithm='sha256').hexdigest()
        for kind, identity in identities]
    return _consume(keys, int(count), duration)


class AuthenticationThrottle(BaseThrottle):
    def allow_request(self, request, view):
        data = request.data if view.throttle_scope == 'api_login' else {}
        username = data.get('username') if isinstance(data, Mapping) else None
        try:
            self.wait_seconds = consume_auth_quota(request, view.throttle_scope, username)
        except ThrottleUnavailable:
            error = ApiError('authentication_unavailable',
                'Account access is temporarily unavailable. Please try again shortly.', 503)
            error.wait = 5
            raise error from None
        return not self.wait_seconds

    def wait(self):
        return self.wait_seconds


class AdminLoginThrottleMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if (request.method != 'POST' or match is None
                or match.app_name != 'admin' or match.url_name != 'login'):
            return None
        try:
            wait = consume_auth_quota(request, 'api_login', request.POST.get('username'))
        except ThrottleUnavailable:
            return HttpResponse('Account access is temporarily unavailable. Please try again shortly.',
                status=503, headers={'Cache-Control': 'no-store', 'Retry-After': '5'})
        if wait:
            return HttpResponse('Too many sign-in attempts. Please try again later.', status=429,
                headers={'Cache-Control': 'no-store', 'Retry-After': str(math.ceil(wait))})
        return None
