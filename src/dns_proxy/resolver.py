from collections.abc import Callable
from ipaddress import ip_address

from dns_proxy.cache import TtlCache
from dns_proxy.domain import is_valid_domain, normalize_domain
from dns_proxy.lists import DomainList
from dns_proxy.models import DecisionSource, ResolutionResult, ResponseStatus, Statistics, UpstreamReply


class Resolver:
    def __init__(
        self,
        sinkhole_ip: str,
        proxy_ip: str,
        local_ttl: int,
        ad_list: DomainList,
        sanction_list: DomainList,
        cache: TtlCache,
        upstream,
        logger: Callable[[ResolutionResult], None] | None = None,
    ):
        self.sinkhole_ip = sinkhole_ip
        self.proxy_ip = proxy_ip
        self.local_ttl = local_ttl
        self.ad_list = ad_list
        self.sanction_list = sanction_list
        self.cache = cache
        self.upstream = upstream
        self.logger = logger
        self.statistics = Statistics()

    def resolve(self, raw_domain: str) -> ResolutionResult:
        normalized = normalize_domain(raw_domain)
        if not is_valid_domain(raw_domain):
            result = ResolutionResult(normalized, DecisionSource.NONE, ResponseStatus.INVALID_INPUT)
            return self._record(result)
        if self.ad_list.matches(normalized):
            result = ResolutionResult(normalized, DecisionSource.AD_BLOCK, ResponseStatus.OK, self.sinkhole_ip, self.local_ttl)
            return self._record(result)
        if self.sanction_list.matches(normalized):
            result = ResolutionResult(normalized, DecisionSource.SANCTION, ResponseStatus.OK, self.proxy_ip, self.local_ttl)
            return self._record(result)
        cached = self.cache.get(normalized)
        if cached is not None:
            ip, ttl = cached
            result = ResolutionResult(normalized, DecisionSource.CACHE, ResponseStatus.OK, ip, ttl)
            return self._record(result)
        try:
            reply = self.upstream.query(normalized)
        except (OSError, TimeoutError, ValueError):
            reply = UpstreamReply(ResponseStatus.SERVER_ERROR)
        result = self._from_upstream(normalized, reply)
        if result.status is ResponseStatus.OK and result.ip is not None and result.ttl is not None:
            self.cache.put(normalized, result.ip, result.ttl)
        return self._record(result)

    def reload_lists(self) -> list[str]:
        return self.ad_list.reload() + self.sanction_list.reload()

    def cache_snapshot(self) -> list[tuple[str, str, int]]:
        return self.cache.snapshot()

    def _from_upstream(self, domain: str, reply: UpstreamReply) -> ResolutionResult:
        if reply.status is ResponseStatus.NOT_FOUND:
            return ResolutionResult(domain, DecisionSource.UPSTREAM, ResponseStatus.NOT_FOUND)
        if reply.status is not ResponseStatus.OK or reply.ip is None or reply.ttl is None:
            return ResolutionResult(domain, DecisionSource.UPSTREAM, ResponseStatus.SERVER_ERROR)
        try:
            ip_address(reply.ip)
        except ValueError:
            return ResolutionResult(domain, DecisionSource.UPSTREAM, ResponseStatus.SERVER_ERROR)
        if reply.ttl <= 0:
            return ResolutionResult(domain, DecisionSource.UPSTREAM, ResponseStatus.SERVER_ERROR)
        return ResolutionResult(domain, DecisionSource.UPSTREAM, ResponseStatus.OK, reply.ip, reply.ttl)

    def _record(self, result: ResolutionResult) -> ResolutionResult:
        self.statistics.record(result)
        if self.logger is not None:
            self.logger(result)
        return result
