from pathlib import Path

from dns_proxy.domain import is_valid_domain, normalize_domain


class DomainList:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._entries: set[str] = set()

    @property
    def entries(self) -> frozenset[str]:
        return frozenset(self._entries)

    def reload(self) -> list[str]:
        warnings: list[str] = []
        entries: set[str] = set()
        for raw_line in self.path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            normalized = normalize_domain(line)
            if normalized != line.casefold() or not is_valid_domain(line):
                warnings.append(f"Warning: bad line in {self.path.name}: {raw_line}")
                continue
            entries.add(normalized)
        self._entries = entries
        return warnings

    def matches(self, domain: str) -> bool:
        return any(domain == entry or domain.endswith("." + entry) for entry in self._entries)
