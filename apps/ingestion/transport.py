"""Bounded, per-host paced HTTP; no response bodies or credentials are logged."""
from collections import OrderedDict
from time import monotonic, sleep
from urllib.parse import urlsplit

from curl_cffi import requests

from .errors import SourceError, is_challenge, require_html_response


class HttpTransport:
    ALLOWED_HOSTS = {'goszakup.gov.kz', 'pk.adata.kz'}

    def __init__(self, session=None, min_interval=1.5, retries=2, cache_ttl=60,
                 sleeper=sleep, clock=monotonic, heartbeat=None):
        self.session = session or requests.Session()
        self.min_interval, self.retries, self.cache_ttl = min_interval, retries, cache_ttl
        self.sleeper, self.clock, self.heartbeat = sleeper, clock, heartbeat
        self._last, self._cache = {}, OrderedDict()

    def get(self, url, *, timeout=30, headers=None, allow_not_found=False):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in self.ALLOWED_HOSTS
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise SourceError('source_url_not_allowed')
        key = (url, allow_not_found)
        cached = self._cache.get(key)
        if cached and cached[0] > self.clock():
            self._cache.move_to_end(key)
            return cached[1]
        for attempt in range(self.retries + 1):
            if self.heartbeat:
                self.heartbeat()
            delay = self.min_interval - (self.clock() - self._last.get(parsed.hostname, -self.min_interval))
            if delay > 0:
                self.sleeper(delay)
            self._last[parsed.hostname] = self.clock()
            response = None
            try:
                response = self.session.get(url, headers=headers or {'User-Agent': 'Mozilla/5.0'},
                                            impersonate='chrome120', timeout=timeout, allow_redirects=False)
            except requests.RequestsError:
                code = 'source_request_failed'
            else:
                if len(response.content if hasattr(response, 'content') else response.text.encode()) > 4 * 1024 * 1024:
                    raise SourceError('source_response_too_large')
                if is_challenge(response):
                    code = 'source_challenge_or_rate_limit'
                elif response.status_code in (408, 500, 502, 503, 504):
                    code = f'source_http_{response.status_code}'
                else:
                    if not (allow_not_found and response.status_code == 404):
                        require_html_response(response)
                    if response.status_code == 200 and self.cache_ttl > 0:
                        self._cache[key] = (self.clock() + self.cache_ttl, response)
                        while len(self._cache) > 32:
                            self._cache.popitem(last=False)
                    return response
            if attempt == self.retries:
                raise SourceError(code) from None
            retry_after = getattr(response, 'headers', {}).get('Retry-After', '') if response is not None else ''
            delay = min(60, int(retry_after)) if retry_after.isdigit() else min(60, 2 ** (attempt + 1))
            self.sleeper(delay)

    def close(self):
        self._cache.clear()
        self.session.close()
