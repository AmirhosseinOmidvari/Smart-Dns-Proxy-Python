from dataclasses import dataclass
from ipaddress import IPv4Address, ip_address
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    upstream_ip: str
    upstream_port: int
    upstream_timeout_sec: float
    sinkhole_ip: str
    proxy_ip: str
    local_ttl: int
    ad_list_file: Path
    sanction_list_file: Path
    cache_enabled: bool = True
    cache_max_entries: int | None = None
    real_dns_enabled: bool = False

    @classmethod
    def load(cls, path: str | Path = "config.txt") -> "AppConfig":
        config_path = Path(path).resolve()
        if not config_path.is_file():
            raise ConfigError(f"missing configuration file: {config_path.name}")
        values: dict[str, str] = {}
        for raw_line in config_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise ConfigError(f"invalid configuration line: {raw_line}")
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key or not value:
                raise ConfigError(f"invalid configuration line: {raw_line}")
            values[key] = value
        required = (
            "upstream_ip",
            "upstream_port",
            "sinkhole_ip",
            "proxy_ip",
            "ad_list_file",
            "sanction_list_file",
        )
        missing = [key for key in required if key not in values]
        if missing:
            raise ConfigError(f"missing key: {missing[0]}")
        upstream_ip = _ipv4(values["upstream_ip"], "upstream_ip")
        sinkhole_ip = _ipv4(values["sinkhole_ip"], "sinkhole_ip")
        proxy_ip = _ipv4(values["proxy_ip"], "proxy_ip")
        upstream_port = _integer(values["upstream_port"], "upstream_port", 1)
        timeout = _real(values.get("upstream_timeout_sec", "2"), "upstream_timeout_sec", 0.001)
        local_ttl = _integer(values.get("local_ttl", "60"), "local_ttl", 0)
        cache_max = None
        if "cache_max_entries" in values:
            cache_max = _integer(values["cache_max_entries"], "cache_max_entries", 1)
        cache_enabled = _boolean(values.get("cache_enabled", "true"), "cache_enabled")
        real_dns_enabled = _boolean(values.get("real_dns_enabled", "false"), "real_dns_enabled")
        ad_file = _resolve_file(config_path.parent, values["ad_list_file"])
        sanction_file = _resolve_file(config_path.parent, values["sanction_list_file"])
        for file_path, key in ((ad_file, "ad_list_file"), (sanction_file, "sanction_list_file")):
            if not file_path.is_file():
                raise ConfigError(f"missing file for {key}: {file_path}")
        return cls(
            upstream_ip=upstream_ip,
            upstream_port=upstream_port,
            upstream_timeout_sec=timeout,
            sinkhole_ip=sinkhole_ip,
            proxy_ip=proxy_ip,
            local_ttl=local_ttl,
            ad_list_file=ad_file,
            sanction_list_file=sanction_file,
            cache_enabled=cache_enabled,
            cache_max_entries=cache_max,
            real_dns_enabled=real_dns_enabled,
        )


def _resolve_file(base: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else base / candidate


def _ipv4(value: str, key: str) -> str:
    try:
        address = ip_address(value)
    except ValueError as exc:
        raise ConfigError(f"invalid IPv4 for {key}: {value}") from exc
    if not isinstance(address, IPv4Address):
        raise ConfigError(f"invalid IPv4 for {key}: {value}")
    return str(address)


def _integer(value: str, key: str, minimum: int) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ConfigError(f"invalid integer for {key}: {value}") from exc
    if number < minimum:
        raise ConfigError(f"invalid value for {key}: {value}")
    return number


def _real(value: str, key: str, minimum: float) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ConfigError(f"invalid number for {key}: {value}") from exc
    if number < minimum:
        raise ConfigError(f"invalid value for {key}: {value}")
    return number


def _boolean(value: str, key: str) -> bool:
    lowered = value.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ConfigError(f"invalid boolean for {key}: {value}")
