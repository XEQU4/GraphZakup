"""Safe source errors: messages never include response bodies or credentials."""


class SourceError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def is_challenge(response):
    text = response.text.lower()
    return response.status_code == 429 or any(marker in text for marker in (
        "too many requests", "g-recaptcha", "recaptchasubmit", "cf-chl-",
        "verify you are human", "captcha challenge",
    ))


def require_html_response(response):
    if is_challenge(response):
        raise SourceError("source_challenge_or_rate_limit")
    if response.status_code != 200:
        raise SourceError(f"source_http_{response.status_code}")
    if not response.text.strip():
        raise SourceError("source_empty_response")
