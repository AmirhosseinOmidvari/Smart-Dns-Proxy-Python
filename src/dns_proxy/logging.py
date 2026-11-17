from datetime import datetime
from pathlib import Path

from dns_proxy.models import ResolutionResult


class StructuredLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def write(self, result: ResolutionResult) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        domain = result.domain or "(empty)"
        ip = result.ip or "-"
        ttl = str(result.ttl) if result.ttl is not None else "-"
        line = f"{timestamp} | {domain} | {result.source.value} | {result.status.value} | {ip} | {ttl}\n"
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(line)
