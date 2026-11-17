import sys
from collections.abc import Callable
from pathlib import Path

from dns_proxy.cache import TtlCache
from dns_proxy.config import AppConfig, ConfigError
from dns_proxy.console import Console
from dns_proxy.lists import DomainList
from dns_proxy.logging import StructuredLogger
from dns_proxy.resolver import Resolver
from dns_proxy.upstream import RealDnsClient, TextUpstreamClient


def build_resolver(
    config_path: str | Path = "config.txt", *, warning_handler: Callable[[str], None] = print
) -> Resolver:
    config = AppConfig.load(config_path)
    ad_list = DomainList(config.ad_list_file)
    sanction_list = DomainList(config.sanction_list_file)
    for warning in ad_list.reload() + sanction_list.reload():
        warning_handler(warning)
    cache = TtlCache(config.cache_enabled, config.cache_max_entries)
    upstream_type = RealDnsClient if config.real_dns_enabled else TextUpstreamClient
    upstream = upstream_type(config.upstream_ip, config.upstream_port, config.upstream_timeout_sec)
    logger = StructuredLogger(Path.cwd() / "log.txt")
    return Resolver(
        sinkhole_ip=config.sinkhole_ip,
        proxy_ip=config.proxy_ip,
        local_ttl=config.local_ttl,
        ad_list=ad_list,
        sanction_list=sanction_list,
        cache=cache,
        upstream=upstream,
        logger=logger.write,
    )


def main() -> None:
    try:
        resolver = build_resolver()
    except (ConfigError, OSError) as exc:
        print(f"Config error: {exc}")
        return
    Console(resolver, sys.stdin, sys.stdout).run()
