"""Run one transport client against the local TLS test server (CABI-M1 conformance suite).

    python run_conformance.py -- <client program and its arguments ...>

1. makes a temp dir; tls_server.py writes test certificates there and starts the listeners
   (127.0.0.1:47000-47099 only);
2. writes <temp>/conformance.json (ports, CA path, event-log path) and runs the client with
   NF_CONFORMANCE=<that file>. The client performs the cases and asserts the outcomes itself;
3. always, even on failure or timeout: stops the server (closes its stdin, kills it after 10 s),
   deletes the temp dir, and checks that no port in 47000-47099 is still bound by this run.

Exit code: the client's exit code, or 3 when the harness itself fails (server did not start, a
port stayed bound, or the temp dir could not be removed). Lane terms: bci-queen light lane,
the run is capped at --client-timeout seconds (default 150).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT_MIN, PORT_MAX = 47000, 47099


def bound_ports(ports: list[int]) -> list[int]:
    """Ports of `ports` where something still LISTENS on 127.0.0.1 (a connect succeeds). A connect
    test, not a bind test: closed connections in TIME_WAIT would make a bind test report false
    leftovers on Windows."""
    busy = []
    for p in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((HOST, p)) == 0:
                busy.append(p)
    return busy


def unbindable_ports(ports: list[int], retries: int = 10) -> list[int]:
    """bci-queen's post-run check: bind every port on 127.0.0.1 and release it at once. A port that
    cannot be bound is retried for ~5 s (sockets of just-closed connections may linger)."""
    import time

    def fails(p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, p))
                return False
            except OSError:
                return True

    bad = [p for p in ports if fails(p)]
    for _ in range(retries):
        if not bad:
            break
        time.sleep(0.5)
        bad = [p for p in bad if fails(p)]
    return bad


def clean_cryptnet_cache(urls: list[str]) -> bool:
    """bci-queen term: Windows CryptNet caches the CRLs WinHTTP fetched. Delete ONLY this run's own
    entries, by exact URL (never a wildcard), then list the cache (read-only) and confirm that no
    127.0.0.1:470xx entry is left. Returns True when clean."""
    if os.name != "nt":
        return True
    certutil = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "certutil.exe")
    for url in urls:
        # exit code is non-zero when the URL was never cached (e.g. the unreachable CRL point): fine
        subprocess.run([certutil, "-urlcache", url, "delete"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    listing = subprocess.run([certutil, "-urlcache"], capture_output=True, text=True, errors="replace").stdout
    left = [l.strip() for l in listing.splitlines() if "127.0.0.1:470" in l]
    if left:
        print(f"run_conformance: CryptNet cache still holds {len(left)} 127.0.0.1:470xx entr(y/ies): {left}", file=sys.stderr)
        return False
    print("run_conformance: CryptNet cache: this run's CRL URLs deleted by exact URL; no 127.0.0.1:470xx entry left", flush=True)
    return True


CI_ROOT_NAME = "NeuroForge conformance test CA"


def on_ephemeral_ci_runner() -> bool:
    """True only on a GitHub-HOSTED Actions runner (a fresh VM destroyed after the job)."""
    return os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"


def ci_trust_root(ca_cert: str) -> None:
    """--ci-trust-root: add the run's test CA to the machine Root store, so the SHIPPED transport (no
    test hook) can be tested end to end: revoked vs good, CRL offline. Refuses to run anywhere but an
    ephemeral GitHub-hosted runner: never on a developer PC (lead ruling 2026-09-27)."""
    if not on_ephemeral_ci_runner():
        raise SystemExit("run_conformance: --ci-trust-root is refused outside a GitHub-hosted runner")
    certutil = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "certutil.exe")
    end = "-----END CERTIFICATE-----"
    parts = [p + end + "\n" for p in Path(ca_cert).read_text(encoding="ascii").split(end) if "BEGIN CERTIFICATE" in p]
    for i, pem in enumerate(parts):  # the bundle holds both test CAs; add each one explicitly
        one = Path(ca_cert).with_name(f"ci-root-{i}.pem")
        one.write_text(pem.lstrip(), encoding="ascii")
        subprocess.run([certutil, "-addstore", "Root", str(one)], check=True, stdout=subprocess.DEVNULL)
    print(f"run_conformance: CI only: {len(parts)} test CA(s) added to LocalMachine\\Root on the ephemeral runner", flush=True)


def ci_untrust_root() -> None:
    if not on_ephemeral_ci_runner():
        return
    certutil = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "certutil.exe")
    for name in (CI_ROOT_NAME, CI_ROOT_NAME + " 2"):
        subprocess.run([certutil, "-delstore", "Root", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openssl", default=r"C:\Program Files\Git\usr\bin\openssl.exe")
    ap.add_argument("--slow-s", type=float, default=5.0)
    ap.add_argument("--client-timeout", type=float, default=150.0)
    ap.add_argument("--grpc", action="store_true",
                    help="also start grpc_server.py (case 10 HTTP/2 cases); needs NF_GRPC_PYTHON = a venv with grpcio")
    ap.add_argument("--ci-trust-root", action="store_true",
                    help="CI ONLY (GitHub-hosted runner): trust the test CA machine-wide for this run")
    ap.add_argument("client", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    client = a.client[1:] if a.client[:1] == ["--"] else a.client
    if not client:
        ap.error("give the client program after --")
    if a.ci_trust_root and not on_ephemeral_ci_runner():
        print("run_conformance: --ci-trust-root is refused outside a GitHub-hosted runner", file=sys.stderr)
        return 3
    grpc_python = os.environ.get("NF_GRPC_PYTHON", "")
    if a.grpc and not (grpc_python and os.path.exists(grpc_python)):
        print("run_conformance: --grpc needs NF_GRPC_PYTHON = the python of the grpcio test venv "
              "(requirements-grpc-test.txt; install only after the owner's OK)", file=sys.stderr)
        return 3

    # A bind probe is instant; a connect probe to a closed port costs ~0.2 s on Windows, so the
    # connect ("still listening?") check below runs only on the ports this run used.
    busy_before = set(unbindable_ports(list(range(PORT_MIN, PORT_MAX + 1)), retries=0))
    if busy_before:
        print(f"run_conformance: note: ports busy before the run (not ours): {sorted(busy_before)}", flush=True)
    tmp = Path(tempfile.mkdtemp(prefix="nf-conformance-"))
    server = None
    gserver = None
    conf_urls: list[str] = []
    rc = 3
    ports: list[int] = []
    try:
        server = subprocess.Popen(
            [sys.executable, str(HERE / "tls_server.py"), "--dir", str(tmp), "--openssl", a.openssl,
             "--slow-s", str(a.slow_s), "--max-lifetime", str(a.client_timeout + 30)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        line: list[str] = []
        reader = threading.Thread(target=lambda: line.append(server.stdout.readline()), daemon=True)
        reader.start()
        reader.join(60)
        if not line or not line[0].strip():
            print("run_conformance: the TLS server did not start", file=sys.stderr)
            return 3
        conf = json.loads(line[0])
        conf_urls = [u for u in (conf.get("crl_url"), conf.get("crl_dead_url")) if u]
        ports = sorted(conf["ports"].values())
        # bci-queen condition: the server may only ever have bound 127.0.0.1 (as it reports from getsockname()).
        wrong = {n: a for n, a in conf["bound"].items() if a[0] != HOST or not (PORT_MIN <= a[1] <= PORT_MAX)}
        if wrong:
            print(f"run_conformance: server bound outside 127.0.0.1:{PORT_MIN}-{PORT_MAX}: {wrong}", file=sys.stderr)
            return 3
        if a.ci_trust_root:
            ci_trust_root(conf["ca_cert"])
        if a.grpc:
            # PYTHONDONTWRITEBYTECODE: the grpcio venv may belong to another worktree (bci-queen: read-only
            # use); nothing, not even __pycache__, is written into it.
            genv = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            gserver = subprocess.Popen(
                [grpc_python, "-B", str(HERE / "grpc_server.py"), "--cert", conf["good_cert"], "--key", conf["good_key"],
                 "--events", str(tmp / "grpc-events.jsonl"), "--slow-s", str(a.slow_s),
                 "--exclude", ",".join(str(p) for p in conf.get("reserved_ports", ports)),
                 "--max-lifetime", str(a.client_timeout + 30)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=genv)
            gline: list[str] = []
            greader = threading.Thread(target=lambda: gline.append(gserver.stdout.readline()), daemon=True)
            greader.start()
            greader.join(60)
            if not gline or not gline[0].strip():
                print("run_conformance: the gRPC server did not start", file=sys.stderr)
                return 3
            gconf = json.loads(gline[0])
            wrong = {n: b for n, b in gconf["grpc_bound"].items() if b[0] != HOST or not (PORT_MIN <= b[1] <= PORT_MAX)}
            if wrong:
                print(f"run_conformance: gRPC server bound outside 127.0.0.1:{PORT_MIN}-{PORT_MAX}: {wrong}", file=sys.stderr)
                return 3
            conf.update(gconf["grpc_ports"])  # flat keys (grpc_good, ...) for the C++ tests
            conf["grpc_events"] = gconf["grpc_events"]
            ports += sorted(gconf["grpc_ports"].values())
        conf_path = tmp / "conformance.json"
        conf_path.write_text(json.dumps(conf, indent=2), encoding="utf-8")
        print(f"run_conformance: server up on {ports}; running {' '.join(client)}", flush=True)
        env = dict(os.environ, NF_CONFORMANCE=str(conf_path))
        try:
            rc = subprocess.run(client, env=env, timeout=a.client_timeout).returncode
        except subprocess.TimeoutExpired:
            print(f"run_conformance: client exceeded {a.client_timeout} s", file=sys.stderr)
            rc = 3
    finally:
        if a.ci_trust_root:
            ci_untrust_root()
        if conf_urls:
            if not clean_cryptnet_cache(conf_urls):
                rc = rc or 3
        if gserver is not None:
            try:
                gserver.stdin.close()
                gserver.wait(10)
            except (subprocess.TimeoutExpired, OSError):
                gserver.kill()
                gserver.wait(10)
        if server is not None:
            try:
                server.stdin.close()
                server.wait(10)
            except (subprocess.TimeoutExpired, OSError):
                server.kill()
                server.wait(10)
        try:
            shutil.rmtree(tmp)
        except OSError as e:
            print(f"run_conformance: could not remove {tmp}: {e}", file=sys.stderr)
            rc = rc or 3
        all_ports = list(range(PORT_MIN, PORT_MAX + 1))
        left = [p for p in bound_ports(ports) if p not in busy_before]
        unbindable = [p for p in unbindable_ports(all_ports) if p not in busy_before]
        if left or unbindable:
            print(f"run_conformance: after the run, listening: {left}; not bindable: {unbindable}", file=sys.stderr)
            rc = rc or 3
        else:
            print("run_conformance: server stopped, temp dir removed; all of 127.0.0.1:47000-47099 bindable, none listening", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
