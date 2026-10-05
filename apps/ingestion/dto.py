from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ResultStatus(StrEnum):
    SUCCESS = 'success'
    NOT_FOUND = 'not_found'
    UNAVAILABLE = 'unavailable'
    INVALID = 'invalid'
    NOT_CHECKED = 'not_checked'


@dataclass(frozen=True)
class SourceResult:
    source: str
    subject_key: str
    status: ResultStatus
    data: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    parser_version: str = '2.0'
    source_url: str = ''
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_code: str = ''
    from_cache: bool = False
