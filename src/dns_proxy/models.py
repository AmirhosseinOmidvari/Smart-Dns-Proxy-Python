from dataclasses import dataclass
from enum import Enum


class DecisionSource(str, Enum):
    AD_BLOCK = "AD_BLOCK"
    SANCTION = "SANCTION"
    CACHE = "CACHE"
    UPSTREAM = "UPSTREAM"
    NONE = "NONE"


class ResponseStatus(str, Enum):
    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    SERVER_ERROR = "SERVER_ERROR"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class UpstreamReply:
    status: ResponseStatus
    ip: str | None = None
    ttl: int | None = None


@dataclass(frozen=True)
class ResolutionResult:
    domain: str
    source: DecisionSource
    status: ResponseStatus
    ip: str | None = None
    ttl: int | None = None


@dataclass
class Statistics:
    total: int = 0
    ad_block: int = 0
    sanction: int = 0
    cache: int = 0
    upstream: int = 0
    errors: int = 0

    def record(self, result: ResolutionResult) -> None:
        self.total += 1
        counters = {
            DecisionSource.AD_BLOCK: "ad_block",
            DecisionSource.SANCTION: "sanction",
            DecisionSource.CACHE: "cache",
            DecisionSource.UPSTREAM: "upstream",
        }
        field = counters.get(result.source)
        if field is not None:
            setattr(self, field, getattr(self, field) + 1)
        if result.status is not ResponseStatus.OK:
            self.errors += 1

    def render(self) -> str:
        return (
            f"Total: {self.total} | AD_BLOCK: {self.ad_block} | "
            f"SANCTION: {self.sanction} | CACHE: {self.cache} | "
            f"UPSTREAM: {self.upstream} | ERRORS: {self.errors}"
        )
