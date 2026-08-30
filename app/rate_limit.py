import time


class TokenBucket:
    """In-process per-key token bucket.

    Sized for a single trusted caller (the AI Learning Assistant); it protects
    the downstream search provider's quota rather than doing multi-tenant
    fairness. Not shared across processes — each server replica gets its own
    budget.
    """

    def __init__(self, rate_per_minute: int, *, burst: int | None = None) -> None:
        self._rate_per_sec = rate_per_minute / 60.0
        self._capacity = float(burst if burst is not None else rate_per_minute)
        self._tokens: dict[str, float] = {}
        self._updated: dict[str, float] = {}

    def allow(self, key: str = "default") -> bool:
        now = time.monotonic()
        elapsed = max(0.0, now - self._updated.get(key, now))
        self._updated[key] = now

        tokens = min(
            self._capacity,
            self._tokens.get(key, self._capacity) + elapsed * self._rate_per_sec,
        )

        if tokens < 1.0:
            self._tokens[key] = tokens
            return False

        self._tokens[key] = tokens - 1.0
        return True
