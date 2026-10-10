"""Read-only health probes for owned containers; no collection or model work."""

import sys
import time
from pathlib import Path

BEAT_HEARTBEAT = Path("/tmp/iz2-beat-heartbeat")
BEAT_MAX_AGE_SECONDS = 90


def beat_is_healthy(path=BEAT_HEARTBEAT, *, now=None):
    try:
        age = (time.time() if now is None else now) - path.stat().st_mtime
    except OSError:
        return False
    return 0 <= age <= BEAT_MAX_AGE_SECONDS


def main():
    if sys.argv[1:] != ["beat"]:
        print("Usage: python -m config.container_health beat", file=sys.stderr)
        return 2
    return 0 if beat_is_healthy() else 1


if __name__ == "__main__":
    raise SystemExit(main())
