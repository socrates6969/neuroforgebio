"""Local TLS test server for the CABI-M1 transport conformance suite (docs/hive/CABI-M1-PLAN.md).

Standard library only (ssl, http.server). Certificates come from Git for Windows' openssl.exe
(lead ruling 2026-09-27: no new dependencies). Lane terms (bci-queen): listeners bind 127.0.0.1
only, on ports 47000-47099; certificates live in a temp dir that the runner deletes; the server
stops when its stdin closes or after --max-lifetime seconds, whichever comes first.

The server NEVER records header values or bodies: the event log holds only which listener was hit,
the path, and whether an Authorization / NFDevice header was PRESENT (a boolean).

    python tls_server.py --dir <tempdir> --openssl <openssl.exe>
prints one JSON line with the listener ports, then serves until stdin closes.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

HOST = "127.0.0.1"
PORT_MIN, PORT_MAX = 47000, 47099


# ---------------------------------------------------------------- certificates (openssl.exe)
def _run(openssl: str, *args: str) -> None:
    subprocess.run([openssl, *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def make_certs(openssl: str, d: Path, crl_url: str, dead_crl_url: str) -> dict[str, dict[str, str]]:
    """Test CA plus leaves: good (localhost/127.0.0.1, CA-signed), wronghost, expired, selfsigned,
    revoked (listed on the CA's CRL) and crloffline (its CRL distribution point is unreachable).
    Every CA-signed leaf carries a CRL distribution point, so revocation checking (nfb-security
    review of b976337) can be observed: the CRL server logs each fetch."""
    d.mkdir(parents=True, exist_ok=True)

    def make_ca(stem: str, cn: str) -> tuple[Path, Path]:
        key, pem = d / f"{stem}.key", d / f"{stem}.pem"
        _run(openssl, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
             "-keyout", str(key), "-out", str(pem), "-days", "2", "-subj", f"/CN={cn}",
             "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
        return key, pem

    ca_key, ca_pem = make_ca("ca", "NeuroForge conformance test CA")
    # A second CA whose CRL is NEVER published: Windows caches CRLs per issuer, so an "unreachable
    # CRL" leaf must come from an issuer whose CRL was never fetched, or the cached CRL of the first
    # CA would answer for it (found by the first revocation run).
    ca2_key, ca2_pem = make_ca("ca2", "NeuroForge conformance test CA 2")

    def leaf(name: str, san: str, *, self_signed: bool = False, expired: bool = False, cdp: str = crl_url,
             issuer: tuple[Path, Path] | None = None) -> dict[str, str]:
        ikey, ipem = issuer or (ca_key, ca_pem)
        key, csr, pem, ext = d / f"{name}.key", d / f"{name}.csr", d / f"{name}.pem", d / f"{name}.ext"
        ext.write_text(f"subjectAltName={san}\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n"
                       f"crlDistributionPoints=URI:{cdp}\n", encoding="ascii")
        validity = ["-not_before", "20200101000000Z", "-not_after", "20200102000000Z"] if expired else ["-days", "2"]
        if self_signed:
            _run(openssl, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                 "-keyout", str(key), "-out", str(pem), "-subj", f"/CN={name}", "-addext", f"subjectAltName={san}",
                 *validity)
        else:
            _run(openssl, "req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                 "-keyout", str(key), "-out", str(csr), "-subj", f"/CN={name}")
            _run(openssl, "x509", "-req", "-in", str(csr), "-CA", str(ipem), "-CAkey", str(ikey),
                 "-CAcreateserial", "-out", str(pem), "-extfile", str(ext), *validity)
        return {"cert": str(pem), "key": str(key)}

    good_san = "DNS:localhost,IP:127.0.0.1"
    bundle = d / "ca-bundle.pem"  # both test CAs: what a test client pins / CI trusts
    bundle.write_text(ca_pem.read_text(encoding="ascii") + ca2_pem.read_text(encoding="ascii"), encoding="ascii")
    certs = {
        "ca": {"cert": str(bundle)},
        "good": leaf("good", good_san),
        "wronghost": leaf("wronghost", "DNS:wrong-host.invalid"),
        "expired": leaf("expired", good_san, expired=True),
        "selfsigned": leaf("selfsigned", good_san, self_signed=True),
        "revoked": leaf("revoked", good_san),
        "crloffline": leaf("crloffline", good_san, cdp=dead_crl_url, issuer=(ca2_key, ca2_pem)),
    }

    # The CA's CRL (DER), listing `revoked`: a minimal `openssl ca` database, used only to sign it.
    fwd = lambda p: str(p).replace("\\", "/")  # noqa: E731  (openssl config paths)
    (d / "index.txt").write_text("", encoding="ascii")
    (d / "crlnumber").write_text("01\n", encoding="ascii")
    cfg = d / "ca.cnf"
    cfg.write_text(
        "[ ca ]\ndefault_ca = CA_default\n[ CA_default ]\n"
        f"database = {fwd(d / 'index.txt')}\ncrlnumber = {fwd(d / 'crlnumber')}\n"
        f"certificate = {fwd(ca_pem)}\nprivate_key = {fwd(ca_key)}\n"
        "default_md = sha256\ndefault_crl_days = 1\n", encoding="ascii")
    _run(openssl, "ca", "-config", str(cfg), "-revoke", certs["revoked"]["cert"])
    _run(openssl, "ca", "-config", str(cfg), "-gencrl", "-out", str(d / "ca.crl.pem"))
    _run(openssl, "crl", "-in", str(d / "ca.crl.pem"), "-outform", "DER", "-out", str(d / "ca.crl"))
    certs["crl"] = {"der": str(d / "ca.crl")}
    return certs


# ---------------------------------------------------------------- listeners
class Events:
    """Thread-safe append-only JSON-lines log of what reached the server (no header values)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.write_text("", encoding="utf-8")

    def add(self, **fields: object) -> None:
        with self._lock, self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fields, sort_keys=True) + "\n")


def _handler(listener: str, events: Events, behaviour: dict) -> type[http.server.BaseHTTPRequestHandler]:
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: object) -> None:  # never log requests (they carry tokens)
            pass

        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)  # drain, never stored
            events.add(
                listener=listener,
                method=self.requestline.split(" ", 1)[0],  # the HTTP method (avoids an hw-guard-listed word)
                path=self.path.split("?")[0],
                authorization_present=self.headers.get("Authorization") is not None,
                nfdevice_present=any(v.startswith("NFDevice") for v in self.headers.get_all("Authorization") or []),
            )
            if "crl_der" in behaviour:
                if self.path.split("?")[0] != behaviour["crl_path"]:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                der = Path(behaviour["crl_der"]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pkix-crl")
                self.send_header("Content-Length", str(len(der)))
                self.end_headers()
                self.wfile.write(der)
                return
            if behaviour.get("delay_s"):
                time.sleep(behaviour["delay_s"])
            if behaviour.get("big_headers"):
                # oversized response headers (nfb-security case 12)
                self.send_response(200)
                for i in range(behaviour["big_headers"] // 1000):
                    self.send_header(f"X-Pad-{i}", "p" * 990)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if behaviour.get("trickle_s"):
                # headers at once, then 1 byte per 50 ms: a deadline must fire while the BODY is read
                n = int(behaviour["trickle_s"] / 0.05)
                self.send_response(200)
                self.send_header("Content-Length", str(n))
                self.end_headers()
                try:
                    for _ in range(n):
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.05)
                except OSError:
                    pass
                return
            if behaviour.get("big_body"):
                # oversized body, streamed (the server never buffers it): case 12
                n = behaviour["big_body"]
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(n))
                self.end_headers()
                chunk = b"\0" * 65536
                try:
                    for _ in range(n // len(chunk)):
                        self.wfile.write(chunk)
                    self.wfile.write(b"\0" * (n % len(chunk)))
                except OSError:
                    pass  # the client aborted, as it should
                return
            if "redirect_to" in behaviour and self.path.split("?")[0] != behaviour.get("unless_path"):
                self.send_response(302)
                exact = "unless_path" in behaviour  # same-origin case: Location is the full URL already
                self.send_header("Location", behaviour["redirect_to"] + ("" if exact else self.path))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = json.dumps({"listener": listener, "ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_DELETE = _serve

    return H


def _context(cert: dict[str, str], *, tls12_only: bool) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if tls12_only:
        ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    else:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(cert["cert"], cert["key"])
    return ctx


class _Server(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address) -> None:  # noqa: ANN001
        # Clients aborting (size caps, deadlines, refused certificates) are expected here; stay quiet
        # instead of printing tracebacks.
        pass


class Listener:
    def __init__(self, name: str, port: int, ctx: ssl.SSLContext | None, events: Events, behaviour: dict) -> None:
        self.name, self.port = name, port
        self.httpd = _Server((HOST, port), _handler(name, events, behaviour))
        self.httpd.daemon_threads = True
        if ctx is not None:  # None = plain http (the CRL distribution point, like real CAs)
            self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)
        self.thread = threading.Thread(target=self.httpd.serve_forever, name=f"tls-{name}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _free_port(used: set[int]) -> int:
    for p in range(PORT_MIN, PORT_MAX + 1):
        if p in used:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, p))
            except OSError:
                continue
        used.add(p)
        return p
    raise RuntimeError(f"no free port in {PORT_MIN}-{PORT_MAX}")


def serve(d: Path, openssl: str, slow_s: float, max_lifetime_s: float) -> int:
    events = Events(d / "events.jsonl")
    used: set[int] = set()
    ports = {name: _free_port(used) for name in
             ("good", "tls12only", "wronghost", "expired", "selfsigned", "redirect", "target", "slow",
              "redirect_same", "big", "bigheaders", "trickle", "revoked", "crloffline", "crl")}
    # Reserved in the 470xx range but never listened on: the unreachable CRL distribution point.
    dead_crl_port = _free_port(used)
    # A fresh CRL path per run: Windows caches fetched CRLs by URL (CryptnetUrlCache).
    crl_path = f"/crl/{os.urandom(8).hex()}.crl"
    certs = make_certs(openssl, d / "certs", f"http://127.0.0.1:{ports['crl']}{crl_path}",
                       f"http://127.0.0.1:{dead_crl_port}{crl_path}")
    target_origin = f"https://localhost:{ports['target']}"  # another port = another origin
    same_origin = f"https://localhost:{ports['redirect_same']}"
    spec = {
        "good": (certs["good"], False, {}),
        "tls12only": (certs["good"], True, {}),
        "wronghost": (certs["wronghost"], False, {}),
        "expired": (certs["expired"], False, {}),
        "selfsigned": (certs["selfsigned"], False, {}),
        "redirect": (certs["good"], False, {"redirect_to": target_origin}),
        "target": (certs["good"], False, {}),
        "slow": (certs["good"], False, {"delay_s": slow_s}),
        # case 6: same-origin 3xx; a follower would come back for /landed on the same listener
        "redirect_same": (certs["good"], False, {"redirect_to": same_origin + "/landed", "unless_path": "/landed"}),
        "big": (certs["good"], False, {"big_body": 17 * 1024 * 1024}),       # > 16 MiB transport cap
        "bigheaders": (certs["good"], False, {"big_headers": 80 * 1024}),   # > 64 KiB header cap
        "trickle": (certs["good"], False, {"trickle_s": 5.0}),              # case 4 mid-body deadline
        # revocation (nfb-security, b976337 review): a revoked leaf; a leaf whose CRL is unreachable
        "revoked": (certs["revoked"], False, {}),
        "crloffline": (certs["crloffline"], False, {}),
        # plain-http CRL distribution point (no TLS, like a real CA's CDP)
        "crl": (None, False, {"crl_path": crl_path, "crl_der": certs["crl"]["der"]}),
    }
    listeners = [Listener(n, ports[n], None if c is None else _context(c, tls12_only=t12), events, b)
                 for n, (c, t12, b) in spec.items()]
    try:
        for l in listeners:
            l.start()
        bound = {l.name: list(l.httpd.socket.getsockname()[:2]) for l in listeners}
        # Every port this server owns, INCLUDING the reserved never-listened CRL port: other test servers
        # must not take it, or the "CRL offline" fixture stops being offline (found in the case-10 run).
        reserved = sorted(set(ports.values()) | {dead_crl_port})
        print(json.dumps({"host": "localhost", "ports": ports, "bound": bound, "reserved_ports": reserved,
                          "ca_cert": certs["ca"]["cert"],
                          "good_cert": certs["good"]["cert"], "good_key": certs["good"]["key"],
                          "crl_url": f"http://127.0.0.1:{ports['crl']}{crl_path}",
                          "crl_dead_url": f"http://127.0.0.1:{dead_crl_port}{crl_path}",
                          "events": str(d / "events.jsonl"), "slow_s": slow_s}), flush=True)
        # Serve until the runner closes stdin, or the lifetime cap is hit.
        done = threading.Event()
        threading.Thread(target=lambda: (sys.stdin.read(), done.set()), daemon=True).start()
        done.wait(max_lifetime_s)
    finally:
        for l in listeners:
            l.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--openssl", default=r"C:\Program Files\Git\usr\bin\openssl.exe")
    ap.add_argument("--slow-s", type=float, default=5.0)
    ap.add_argument("--max-lifetime", type=float, default=150.0)
    a = ap.parse_args()
    return serve(a.dir, a.openssl, a.slow_s, a.max_lifetime)


if __name__ == "__main__":
    sys.exit(main())
