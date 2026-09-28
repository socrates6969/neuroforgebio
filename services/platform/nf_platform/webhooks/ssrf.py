"""SSRF policy for webhook URLs (SEC-076; OWASP API7).

``check_url`` is called when an endpoint is registered; ``resolve_pinned`` on EVERY delivery:

1. Only ``https`` URLs with a DNS host name, no user-info, no fragment, port 443 or 1024-65535.
   IP-literal hosts are refused outright (no ``https://10.0.0.1/``, ``https://[::1]/``, decimal or
   hex encodings, which ``ipaddress`` would not even parse as a host name).
2. The host is resolved ONCE per delivery. If ANY address is in a blocked range the delivery is
   refused (an attacker controls which A record a client picks).
3. The connection goes to the address that was checked (``PinnedTarget.address``), with the host
   name only in SNI/Host. A second DNS answer (DNS rebinding) is never consulted.

Blocked: RFC 1918, loopback, link-local (incl. 169.254.169.254 and the other cloud metadata
addresses), CGNAT 100.64/10, "this network" 0/8, multicast, reserved/benchmark/documentation
ranges, and the IPv6 equivalents (::1, ::, fc00::/7, fe80::/10, ff00::/8, 2001:db8::/32,
64:ff9b::/96 NAT64 and ::ffff:0:0/96 IPv4-mapped, 2002::/16 6to4 whose embedded IPv4 is checked).

In a deployment, webhook egress additionally goes through the egress proxy with the same deny list
(infra; see docs/platform/webhooks.md). This module is the application-side layer.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Iterable[str]]

_BLOCKED_V4 = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",  # this network
        "10.0.0.0/8",  # RFC 1918
        "100.64.0.0/10",  # CGNAT (RFC 6598)
        "127.0.0.0/8",  # loopback
        "169.254.0.0/16",  # link-local, incl. 169.254.169.254 metadata
        "172.16.0.0/12",  # RFC 1918
        "192.0.0.0/24",  # IETF protocol assignments
        "192.0.2.0/24",  # TEST-NET-1
        "192.88.99.0/24",  # 6to4 relay anycast
        "192.168.0.0/16",  # RFC 1918
        "198.18.0.0/15",  # benchmarking
        "198.51.100.0/24",  # TEST-NET-2
        "203.0.113.0/24",  # TEST-NET-3
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved, incl. 255.255.255.255
    )
]
_BLOCKED_V6 = [
    ipaddress.ip_network(n)
    for n in (
        "::/128",  # unspecified
        "::1/128",  # loopback
        # deprecated IPv4-compatible ::a.b.c.d (RFC 4291 §2.5.5.1): no legitimate webhook target,
        # and ``is_global`` is True for e.g. ::169.254.169.254, so block the whole range
        "::/96",
        "::ffff:0:0/96",  # IPv4-mapped (checked via the embedded IPv4 too)
        "64:ff9b::/96",  # NAT64 (embedded IPv4 checked too)
        "64:ff9b:1::/48",  # local-use NAT64
        "100::/64",  # discard-only
        "2001::/23",  # IETF protocol assignments (incl. Teredo 2001::/32)
        "2001:db8::/32",  # documentation
        "2002::/16",  # 6to4 (embedded IPv4 checked too)
        "fc00::/7",  # unique local
        "fe80::/10",  # link-local
        "fec0::/10",  # deprecated site-local
        "ff00::/8",  # multicast
    )
]
# Named cloud metadata endpoints (also inside the ranges above; listed for clarity and tests).
METADATA_ADDRESSES = frozenset(
    {"169.254.169.254", "169.254.170.2", "fd00:ec2::254", "100.100.100.200"}
)


class BlockedUrl(ValueError):
    """The URL or its resolved address is not an allowed webhook target."""


@dataclass(frozen=True)
class PinnedTarget:
    url: str
    host: str
    port: int
    address: str  # the checked IP the connection must use


def _embedded_v4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if int(ip) >> 32 == 0 and int(ip) > 1:  # IPv4-compatible ::a.b.c.d (not :: or ::1)
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip in ipaddress.ip_network("64:ff9b::/96"):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.teredo is not None:
        return ip.teredo[1]
    return None


def is_blocked(address: str) -> bool:
    try:
        ip: IPAddress = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return True  # not an address we understand: refuse
    if str(ip) in METADATA_ADDRESSES:
        return True
    if isinstance(ip, ipaddress.IPv6Address):
        v4 = _embedded_v4(ip)
        if v4 is not None and is_blocked(str(v4)):
            return True
        return any(ip in n for n in _BLOCKED_V6) or not ip.is_global
    return any(ip in n for n in _BLOCKED_V4) or not ip.is_global


def _looks_like_ip(host: str) -> bool:
    h = host.strip("[]")
    try:
        ipaddress.ip_address(h.split("%", 1)[0])
        return True
    except ValueError:
        pass
    # Numeric forms some resolvers accept: 2130706433, 0x7f000001, 0177.0.0.1, 127.1
    labels = h.split(".")
    return all(lbl.isdigit() or lbl.lower().startswith("0x") for lbl in labels if lbl)


def check_url(url: str) -> tuple[str, int]:
    """Static checks (no DNS). Returns (host, port) or raises :class:`BlockedUrl`."""
    if len(url) > 2048:
        raise BlockedUrl("URL too long")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as e:
        raise BlockedUrl("malformed URL") from e
    if parts.scheme != "https":
        raise BlockedUrl("only https URLs are allowed")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise BlockedUrl("user-info is not allowed in webhook URLs")
    if parts.fragment:
        raise BlockedUrl("fragments are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise BlockedUrl("a host name is required")
    if _looks_like_ip(host):
        raise BlockedUrl("IP-literal hosts are not allowed; use a DNS name")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".invalid")):
        raise BlockedUrl("internal host names are not allowed")
    if "." not in host:
        raise BlockedUrl("a fully qualified host name is required")
    port = 443 if port is None else port
    if port != 443 and not 1024 <= port <= 65535:
        raise BlockedUrl("port must be 443 or 1024-65535")
    return host, port


def system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    return [str(i[4][0]) for i in infos]


def resolve_pinned(url: str, resolver: Resolver = system_resolver) -> PinnedTarget:
    """Resolve once, refuse if ANY address is blocked, pin the first allowed address."""
    host, port = check_url(url)
    try:
        addresses = [a for a in resolver(host, port)]
    except OSError as e:
        raise BlockedUrl("host does not resolve") from e
    if not addresses:
        raise BlockedUrl("host does not resolve")
    bad = [a for a in addresses if is_blocked(a)]
    if bad:
        raise BlockedUrl("host resolves to a blocked address")
    return PinnedTarget(url=url, host=host, port=port, address=addresses[0])
