from typing import TextIO

from dns_proxy.models import ResolutionResult


class Console:
    def __init__(self, resolver, input_stream: TextIO, output_stream: TextIO):
        self.resolver = resolver
        self.input_stream = input_stream
        self.output_stream = output_stream

    def run(self) -> None:
        self._write_line("DNS Proxy ready.")
        while True:
            self.output_stream.write("Enter domain (or exit): ")
            self.output_stream.flush()
            raw = self.input_stream.readline()
            if raw == "":
                break
            value = raw.strip()
            if value.casefold() == "exit":
                self._write_line("Bye.")
                break
            if value.casefold() == "stats":
                self._write_line(self.resolver.statistics.render())
                continue
            if value.casefold() == "reload":
                try:
                    warnings = self.resolver.reload_lists()
                except OSError as exc:
                    self._write_line(f"Reload error: {exc}")
                    continue
                for warning in warnings:
                    self._write_line(warning)
                self._write_line("Lists reloaded.")
                continue
            if value.casefold() == "cache":
                entries = self.resolver.cache_snapshot()
                if not entries:
                    self._write_line("Cache is empty.")
                else:
                    for domain, ip, ttl in entries:
                        self._write_line(f"{domain} | {ip} | {ttl}")
                continue
            self._print_result(self.resolver.resolve(value))

    def _print_result(self, result: ResolutionResult) -> None:
        domain = result.domain or "(empty)"
        ip = result.ip or "-"
        ttl = str(result.ttl) if result.ttl is not None else "-"
        self._write_line(f"Domain : {domain}")
        self._write_line(f"Source : {result.source.value}")
        self._write_line(f"Status : {result.status.value}")
        self._write_line(f"IP : {ip}")
        self._write_line(f"TTL : {ttl}")
        self._write_line("")

    def _write_line(self, value: str) -> None:
        self.output_stream.write(value + "\n")
        self.output_stream.flush()
