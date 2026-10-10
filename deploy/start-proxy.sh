#!/bin/sh
# Profiles select services; validate the matching application security settings.
set -eu

fail() {
    printf '%s\n' "HTTPS configuration rejected: $1. Use prepare_deploy.py --domain and --acme-email." >&2
    exit 1
}

[ -n "${SITE_DOMAIN:-}" ] || fail "SITE_DOMAIN is missing"
[ -n "${ACME_EMAIL:-}" ] || fail "ACME_EMAIL is missing"
[ "${TRUST_PROXY_SSL_HEADER:-false}" = "true" ] || fail "TRUST_PROXY_SSL_HEADER must be true"
[ "${SECURE_SSL_REDIRECT:-false}" = "true" ] || fail "SECURE_SSL_REDIRECT must be true"
[ "${SESSION_COOKIE_SECURE:-false}" = "true" ] || fail "SESSION_COOKIE_SECURE must be true"
[ "${CSRF_COOKIE_SECURE:-false}" = "true" ] || fail "CSRF_COOKIE_SECURE must be true"
[ "${AUTH_TRUSTED_PROXY_CIDRS:-}" = "${PROXY_ADDRESS}/32" ] || fail "only the configured proxy peer may be trusted"
case ",${ALLOWED_HOSTS:-}," in
    *",${SITE_DOMAIN},"*) ;;
    *) fail "ALLOWED_HOSTS does not contain SITE_DOMAIN" ;;
esac
case ",${CSRF_TRUSTED_ORIGINS:-}," in
    *",https://${SITE_DOMAIN},"*) ;;
    *) fail "CSRF_TRUSTED_ORIGINS does not contain the HTTPS origin" ;;
esac

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
