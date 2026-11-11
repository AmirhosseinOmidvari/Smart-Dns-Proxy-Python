import random
import socket
import struct
from ipaddress import IPv4Address

from dns_proxy.models import ResponseStatus, UpstreamReply


class TextUpstreamClient:
    def __init__(self, host: str, port: int, timeout: float):
        self.address = (host, port)
        self.timeout = timeout

    def query(self, domain: str) -> UpstreamReply:
        message = f"QUERY {domain}".encode("ascii")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(message, self.address)
            payload, _ = sock.recvfrom(4096)
        return self._parse(payload.decode("ascii"))

    @staticmethod
    def _parse(payload: str) -> UpstreamReply:
        fields = payload.strip().split()
        if fields == ["NOT_FOUND"]:
            return UpstreamReply(ResponseStatus.NOT_FOUND)
        if len(fields) == 3 and fields[0] == "OK":
            try:
                ttl = int(fields[2])
            except ValueError:
                return UpstreamReply(ResponseStatus.SERVER_ERROR)
            return UpstreamReply(ResponseStatus.OK, fields[1], ttl)
        return UpstreamReply(ResponseStatus.SERVER_ERROR)


class RealDnsClient:
    def __init__(self, host: str, port: int, timeout: float):
        self.address = (host, port)
        self.timeout = timeout

    def query(self, domain: str) -> UpstreamReply:
        transaction_id = random.randrange(0, 65536)
        packet = _build_query(domain, transaction_id)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(packet, self.address)
            response, _ = sock.recvfrom(4096)
        return _parse_dns_response(response, transaction_id)


def _build_query(domain: str, transaction_id: int) -> bytes:
    labels = domain.split(".")
    qname = b"".join(bytes((len(label),)) + label.encode("ascii") for label in labels) + b"\x00"
    header = struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
    return header + qname + struct.pack("!HH", 1, 1)


def _parse_dns_response(packet: bytes, transaction_id: int) -> UpstreamReply:
    if len(packet) < 12:
        return UpstreamReply(ResponseStatus.SERVER_ERROR)
    response_id, flags, questions, answers, _, _ = struct.unpack("!HHHHHH", packet[:12])
    if response_id != transaction_id or questions == 0:
        return UpstreamReply(ResponseStatus.SERVER_ERROR)
    rcode = flags & 0x000F
    if rcode == 3:
        return UpstreamReply(ResponseStatus.NOT_FOUND)
    if rcode != 0:
        return UpstreamReply(ResponseStatus.SERVER_ERROR)
    offset = 12
    try:
        for _ in range(questions):
            offset = _skip_name(packet, offset)
            offset += 4
        for _ in range(answers):
            offset = _skip_name(packet, offset)
            if offset + 10 > len(packet):
                return UpstreamReply(ResponseStatus.SERVER_ERROR)
            record_type, record_class, ttl, length = struct.unpack("!HHIH", packet[offset:offset + 10])
            offset += 10
            if offset + length > len(packet):
                return UpstreamReply(ResponseStatus.SERVER_ERROR)
            data = packet[offset:offset + length]
            offset += length
            if record_type == 1 and record_class == 1 and length == 4:
                ip = str(IPv4Address(data))
                return UpstreamReply(ResponseStatus.OK, ip, ttl)
    except (IndexError, struct.error, ValueError):
        return UpstreamReply(ResponseStatus.SERVER_ERROR)
    return UpstreamReply(ResponseStatus.NOT_FOUND)


def _skip_name(packet: bytes, offset: int) -> int:
    visited = set()
    while True:
        if offset >= len(packet):
            raise ValueError("truncated DNS name")
        length = packet[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(packet):
                raise ValueError("truncated DNS pointer")
            pointer = ((length & 0x3F) << 8) | packet[offset + 1]
            if pointer in visited:
                raise ValueError("cyclic DNS pointer")
            visited.add(pointer)
            return offset + 2
        if length > 63 or offset + 1 + length > len(packet):
            raise ValueError("invalid DNS label")
        offset += length + 1
