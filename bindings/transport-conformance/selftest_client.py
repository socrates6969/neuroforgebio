"""Self-test of the conformance HARNESS (not of any SDK transport): a strict Python stdlib client
(TLS 1.3 minimum, test CA only, hostname checks, no redirects) must see exactly the conditions each
listener is meant to create. Run under run_conformance.py:

    python run_conformance.py -- python selftest_client.py
"""

from __future__ import annotations

import http.client
import json
import os
import ssl
import sys
import time

failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)
    failures += 0 if ok else 1


def strict_ctx(ca: str) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=ca)  # trusts ONLY the test CA; verifies chain + hostname
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    return ctx


def request(host: str, port: int, ctx: ssl.SSLContext, path: str = "/ok", timeout: float = 5.0):
    conn = http.client.HTTPSConnection(host, port, context=ctx, timeout=timeout)
    try:
        conn.request("GET", path, headers={"Authorization": "Bearer selftest-marker"})
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        conn.close()


def fails(fn) -> tuple[bool, str]:
    try:
        fn()
        return False, "succeeded"
    except (ssl.SSLError, ssl.SSLCertVerificationError, OSError) as e:
        return True, type(e).__name__


def main() -> int:
    conf = json.load(open(os.environ["NF_CONFORMANCE"], encoding="utf-8"))
    host, ports, ca = conf["host"], conf["ports"], conf["ca_cert"]
    ctx = strict_ctx(ca)

    status, _, body = request(host, ports["good"], ctx)
    check("good: TLS 1.3 + test CA + hostname -> 200", status == 200 and b'"ok": true' in body, str(status))

    ok, why = fails(lambda: request(host, ports["tls12only"], ctx))
    check("tls12only: a TLS 1.3-minimum client is refused", ok, why)
    ctx12 = strict_ctx(ca)
    ctx12.minimum_version = ssl.TLSVersion.TLSv1_2
    status, _, _ = request(host, ports["tls12only"], ctx12)
    check("tls12only: really serves TLS 1.2 (a 1.2 client connects)", status == 200, str(status))

    for name in ("wronghost", "expired", "selfsigned"):
        ok, why = fails(lambda n=name: request(host, ports[n], ctx))
        check(f"{name}: certificate verification fails", ok, why)

    status, headers, _ = request(host, ports["redirect"], ctx, "/start")
    loc = headers.get("Location", "")
    check("redirect: 302 to another origin", status == 302 and loc.startswith(f"https://localhost:{ports['target']}/"), f"{status} {loc}")

    status, headers, _ = request(host, ports["redirect_same"], ctx, "/start")
    check("redirect_same: 302 to the same origin", status == 302 and
          headers.get("Location") == f"https://localhost:{ports['redirect_same']}/landed", f"{status}")
    status, _, _ = request(host, ports["redirect_same"], ctx, "/landed")
    check("redirect_same: /landed itself answers 200 (so a follower would be seen)", status == 200)

    status, headers, body = request(host, ports["big"], ctx, "/x", timeout=30)
    check("big: serves a 17 MiB body", status == 200 and len(body) == 17 * 1024 * 1024, str(len(body)))
    status, headers, _ = request(host, ports["bigheaders"], ctx, "/x")
    hsize = sum(len(k) + len(v) + 4 for k, v in headers.items())
    check("bigheaders: sends > 64 KiB of headers", status == 200 and hsize > 64 * 1024, str(hsize))

    t0 = time.monotonic()
    ok, why = fails(lambda: request(host, ports["slow"], ctx, timeout=1.0))
    dt = time.monotonic() - t0
    check("slow: a 1 s client timeout fires before the server answers", ok and dt < 3.0, f"{why} after {dt:.2f} s")

    # Revocation fixtures: the CRL distribution point serves a CRL that lists `revoked` (and only
    # it); a CRL-checking client must refuse `revoked` and still accept `good`.
    import base64
    import urllib.parse
    u = urllib.parse.urlsplit(conf["crl_url"])
    hc = http.client.HTTPConnection(u.hostname, u.port, timeout=5)
    hc.request("GET", u.path)
    der = hc.getresponse().read()
    hc.close()
    check("crl: the distribution point serves a DER CRL", len(der) > 50 and der[0] == 0x30, f"{len(der)} bytes")
    crl_pem = "-----BEGIN X509 CRL-----\n" + base64.encodebytes(der).decode() + "-----END X509 CRL-----\n"
    cctx = strict_ctx(ca)
    # cadata accepts certificates only; a CRL must come from a PEM file (next to the events log,
    # inside the run's temp dir, which the runner deletes).
    crl_file = os.path.join(os.path.dirname(conf["events"]), "selftest-crl.pem")
    with open(crl_file, "w", encoding="ascii") as f:
        f.write(crl_pem)
    cctx.load_verify_locations(cafile=crl_file)
    cctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
    ok, why = fails(lambda: request(host, ports["revoked"], cctx))
    check("revoked: a CRL-checking client refuses it", ok, why)
    status, _, _ = request(host, ports["good"], cctx)
    check("revoked fixture: the same CRL-checking client still accepts good", status == 200)
    status, _, _ = request(host, ports["revoked"], ctx)
    check("revoked: without CRL checks it is a valid chain (so only revocation can refuse it)", status == 200)
    status, _, _ = request(host, ports["crloffline"], ctx)
    check("crloffline: a valid chain whose CRL point is unreachable", status == 200)

    events = [json.loads(l) for l in open(conf["events"], encoding="utf-8") if l.strip()]
    check("events: the redirect target was never contacted (this client does not follow)",
          not any(e["listener"] == "target" for e in events))
    check("events: /landed was requested exactly once (by this test directly, not by following)",
          sum(1 for e in events if e["listener"] == "redirect_same" and e["path"] == "/landed") == 1)
    check("events: requests that completed TLS are logged with authorization_present only",
          all(set(e) == {"listener", "method", "path", "authorization_present", "nfdevice_present"} for e in events)
          and any(e["listener"] == "good" and e["authorization_present"] for e in events))
    check("events: no failed-TLS listener saw a request",
          not any(e["listener"] in ("wronghost", "expired", "selfsigned") for e in events))
    raw = open(conf["events"], encoding="utf-8").read()
    check("events: token text never written", "selftest-marker" not in raw)

    print(f"selftest: {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
