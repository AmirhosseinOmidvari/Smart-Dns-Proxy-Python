import socket


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5354


class SimulatedUpstream:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.address = (host, port)
        self.request_count = 0

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(self.address)
            while True:
                payload, client = sock.recvfrom(4096)
                reply = self._handle(payload)
                sock.sendto(reply.encode("ascii"), client)

    def _handle(self, payload: bytes) -> str:
        fields = payload.decode("ascii", errors="replace").strip().split(maxsplit=1)
        if len(fields) != 2 or fields[0] != "QUERY":
            reply = "NOT_FOUND"
            domain = "(invalid)"
        else:
            domain = fields[1]
            reply = "NOT_FOUND" if domain == "missing.example.net" else "OK 198.51.100.7 5"
        self.request_count += 1
        print(f"Request #{self.request_count}: {domain} -> {reply}", flush=True)
        return reply


def main() -> None:
    SimulatedUpstream().serve_forever()


if __name__ == "__main__":
    main()
