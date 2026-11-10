from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class CacheValue:
    ip: str
    ttl: int
    stored_at: float


class TtlCache:
    def __init__(self, enabled: bool = True, max_entries: int | None = None, clock=monotonic):
        self.enabled = enabled
        self.max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, CacheValue] = OrderedDict()

    def clear(self) -> None:
        self._entries.clear()

    def put(self, domain: str, ip: str, ttl: int) -> None:
        if not self.enabled or ttl <= 0:
            return
        self._entries.pop(domain, None)
        self._entries[domain] = CacheValue(ip, ttl, self._clock())
        self._evict_if_needed()

    def get(self, domain: str) -> tuple[str, int] | None:
        if not self.enabled:
            return None
        entry = self._entries.get(domain)
        if entry is None:
            return None
        remaining = int(entry.ttl - (self._clock() - entry.stored_at))
        if remaining < 1:
            self._entries.pop(domain, None)
            return None
        return entry.ip, remaining

    def snapshot(self) -> list[tuple[str, str, int]]:
        values: list[tuple[str, str, int]] = []
        for domain in list(self._entries):
            cached = self.get(domain)
            if cached is None:
                continue
            ip, ttl = cached
            values.append((domain, ip, ttl))
        return values

    def _evict_if_needed(self) -> None:
        if self.max_entries is None:
            return
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
