"""Run the local dashboard with Python 3.10 or later."""

import json
import os
import sys
from collections import deque
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
from pathlib import Path
from socketserver import BaseRequestHandler, UDPServer
from tempfile import NamedTemporaryFile
from threading import Lock, Thread
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
CONFIG_FILE = ROOT / "config.txt"
LOG_FILE = ROOT / "log.txt"
sys.path.insert(0, str(ROOT / "src"))

from dns_proxy.app import build_resolver
from dns_proxy.config import AppConfig, ConfigError
from dns_proxy.upstream_server import SimulatedUpstream

HOST = "127.0.0.1"
PORT = 8080
SETTINGS = (
    "upstream_ip", "upstream_port", "upstream_timeout_sec", "sinkhole_ip",
    "proxy_ip", "local_ttl", "cache_enabled", "cache_max_entries", "real_dns_enabled",
)
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/relay.svg": ("relay.svg", "image/svg+xml"),
    "/signal.webp": ("signal.webp", "image/webp"),
}


class SimulatorRequest(BaseRequestHandler):
    def handle(self):
        payload, udp = self.request
        reply = self.server.simulator._handle(payload)
        udp.sendto(reply.encode("ascii"), self.client_address)


class LocalSimulator(UDPServer):
    def __init__(self, address):
        super().__init__(address, SimulatorRequest)
        self.simulator = SimulatedUpstream(*address)
        self.worker = Thread(target=self.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        self.worker.start()

    def close(self):
        self.shutdown()
        self.server_close()
        self.worker.join()


def temporary_text(path, content):
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as file:
        name = Path(file.name)
        file.write(content)
    return name


class Dashboard:
    def __init__(self):
        self.lock = Lock()
        self.simulator = None
        self.warnings = []
        self.config = AppConfig.load(CONFIG_FILE)
        self.resolver = build_resolver(CONFIG_FILE, warning_handler=self.warnings.append)
        if self.simulator_available:
            try:
                self.set_simulator(True)
            except OSError:
                self.warnings.append("The UDP port is already in use. An external simulator may be running.")

    @property
    def simulator_available(self):
        return not self.config.real_dns_enabled and IPv4Address(self.config.upstream_ip).is_loopback

    def set_simulator(self, enabled):
        if enabled:
            if not self.simulator_available:
                raise ValueError("The simulator requires simulated UDP mode and a loopback address.")
            if self.simulator is None:
                self.simulator = LocalSimulator((self.config.upstream_ip, self.config.upstream_port))
        elif self.simulator is not None:
            self.simulator.close()
            self.simulator = None

    def state(self):
        return {
            "settings": {key: getattr(self.config, key) for key in SETTINGS},
            "stats": asdict(self.resolver.statistics),
            "cache": [
                {"domain": domain, "ip": ip, "ttl": ttl}
                for domain, ip, ttl in self.resolver.cache_snapshot()
            ],
            "simulator": {
                "available": self.simulator_available,
                "running": self.simulator is not None,
                "requests": self.simulator.simulator.request_count if self.simulator else None,
            },
            "warnings": self.warnings,
        }

    def activity(self):
        if not LOG_FILE.exists():
            return []
        entries = []
        with LOG_FILE.open(encoding="utf-8") as log:
            for line in reversed(deque(log, maxlen=60)):
                parts = line.rstrip("\n").split(" | ", maxsplit=1)
                if len(parts) == 2:
                    fields = parts[1].rsplit(" | ", maxsplit=4)
                    if len(fields) == 5:
                        entries.append(dict(zip(
                            ("time", "domain", "source", "status", "ip", "ttl"),
                            [parts[0], *fields],
                        )))
        return entries

    def policy_lists(self):
        return {
            "ads": self.config.ad_list_file.read_text(encoding="utf-8"),
            "sanctions": self.config.sanction_list_file.read_text(encoding="utf-8"),
        }

    def reload_policies(self):
        self.warnings = self.resolver.reload_lists()
        return self.warnings

    def save_policies(self, values):
        for key in ("ads", "sanctions"):
            if not isinstance(values.get(key), str):
                raise ValueError("Both policy lists must be text.")
        prepared = {}
        try:
            for key, path in (
                ("ads", self.config.ad_list_file),
                ("sanctions", self.config.sanction_list_file),
            ):
                if path in prepared:
                    if values[key] != values["ads"]:
                        raise ValueError("Both lists point to one file and must contain the same text.")
                    continue
                prepared[path] = temporary_text(path, values[key])
            for path, candidate in prepared.items():
                candidate.replace(path)
        finally:
            for candidate in prepared.values():
                candidate.unlink(missing_ok=True)
        return self.reload_policies()

    def save_settings(self, values):
        keys = set(SETTINGS)
        if values.keys() != keys:
            raise ValueError("Send all editable settings.")
        lines = CONFIG_FILE.read_text(encoding="utf-8").splitlines()
        edits = {}
        for key in SETTINGS:
            value = values[key]
            if key in ("real_dns_enabled", "cache_enabled"):
                if type(value) is not bool:
                    raise ValueError(f"{key} requires a boolean.")
                value = str(value).lower()
            if value is None and key == "cache_max_entries":
                edits[key] = None
                continue
            if type(value) not in (int, float, str) or not str(value).strip() or "\r" in str(value) or "\n" in str(value):
                raise ValueError(f"{key} requires a value.")
            edits[key] = f"{key}={str(value).strip()}"
        preserved = [
            line for line in lines
            if line.split("=", 1)[0].strip() not in keys
        ]
        updated = preserved + [line for line in edits.values() if line is not None]
        pending = temporary_text(CONFIG_FILE, "\n".join(updated) + "\n")
        warnings = []
        try:
            config = AppConfig.load(pending)
            resolver = build_resolver(pending, warning_handler=warnings.append)
            pending.replace(CONFIG_FILE)
        finally:
            pending.unlink(missing_ok=True)
        if self.simulator and (
            config.real_dns_enabled or self.simulator.server_address != (config.upstream_ip, config.upstream_port)
        ):
            self.set_simulator(False)
        resolver.statistics = self.resolver.statistics
        self.config, self.resolver, self.warnings = config, resolver, warnings

    def query(self, domain):
        if not isinstance(domain, str):
            raise ValueError("Enter a domain name.")
        start = perf_counter()
        result = asdict(self.resolver.resolve(domain))
        result["elapsed_ms"] = round((perf_counter() - start) * 1000, 2)
        return result


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not self.valid_host():
            return
        if self.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[self.path]
            self.respond(200, (STATIC / filename).read_bytes(), content_type)
            return
        actions = {
            "/api/state": self.server.dashboard.state,
            "/api/activity": self.server.dashboard.activity,
            "/api/policies": self.server.dashboard.policy_lists,
        }
        if self.path not in actions:
            self.reply(404, {"error": "Page not found."})
            return
        try:
            with self.server.dashboard.lock:
                self.reply(200, actions[self.path]())
        except (OSError, ValueError) as exc:
            self.reply(400, {"error": str(exc)})

    def do_POST(self):
        if not self.valid_host():
            return
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers['Host']}":
            self.reply(403, {"error": "Use the dashboard's own origin."})
            return
        if self.headers.get_content_type() != "application/json":
            self.reply(415, {"error": "Send JSON data."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024 * 1024:
                raise ValueError("Invalid or oversized request.")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Send a JSON object.")
            with self.server.dashboard.lock:
                payload = self.dispatch(data)
            self.reply(200, payload)
        except LookupError:
            self.reply(404, {"error": "Action not found."})
        except (OSError, ValueError) as exc:
            self.reply(400, {"error": str(exc)})

    def dispatch(self, data):
        app = self.server.dashboard
        result = None
        if self.path == "/api/resolve":
            result = app.query(data.get("domain"))
        elif self.path == "/api/settings":
            app.save_settings(data)
        elif self.path == "/api/policies":
            app.save_policies(data)
        elif self.path == "/api/policies/reload":
            app.reload_policies()
        elif self.path == "/api/cache/clear":
            app.resolver.cache.clear()
        elif self.path == "/api/simulator":
            if type(data.get("running")) is not bool:
                raise ValueError("Choose whether to run the simulator.")
            app.set_simulator(data["running"])
        else:
            raise LookupError
        return {"result": result, **app.state()}

    def valid_host(self):
        if self.headers.get("Host") in {f"{HOST}:{PORT}", f"localhost:{PORT}"}:
            return True
        self.reply(403, {"error": "Open this dashboard on localhost."})
        return False

    def reply(self, status, data):
        self.respond(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def respond(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


def main():
    os.chdir(ROOT)
    try:
        with ThreadingHTTPServer((HOST, PORT), DashboardHandler) as server:
            dashboard = Dashboard()
            server.dashboard = dashboard
            print(f"DNS Proxy Dashboard: http://{HOST}:{PORT}", flush=True)
            try:
                server.serve_forever()
            finally:
                dashboard.set_simulator(False)
    except KeyboardInterrupt:
        return 0
    except (ConfigError, OSError, ValueError) as exc:
        print(f"Dashboard could not start: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
