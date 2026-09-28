# Transport conformance suite (CABI-M1)

This is the test harness for the transport contract in `docs/hive/CABI-M1-PLAN.md` (branch `docs/abi-sdk-gaps`).
Every HTTP or gRPC stack that carries NeuroForge tokens must pass it before anyone calls it a "default transport",
and nfb-security reviews the results.

## Pieces

| File | What |
|---|---|
| `tls_server.py` | Local TLS test server, Python stdlib only (`ssl`, `http.server`). Test certificates come from Git's `openssl.exe`: a test CA, plus good, wrong-host, expired and self-signed leaves. It has 15 listeners on `127.0.0.1:47000-47099`: good (TLS 1.3), tls12only, wronghost, expired, selfsigned, redirect (to another origin), target, redirect_same, slow, big (17 MiB body), bigheaders (80 KiB), trickle (the body arrives 1 byte every 50 ms), revoked (listed on the CA's CRL), crloffline (its CRL point is a reserved port nothing listens on), and crl (the plain-http CRL distribution point, at a random path per run). The event log records only the listener, the path and whether an `Authorization` header was *present*, never its value. |
| `run_conformance.py` | Runs one client program against the server. Whatever happens, it then stops the server, deletes the temp certificates, and checks that nothing still listens on 47000-47099 (a connect test, no netstat). |
| `selftest_client.py` | Checks that the harness itself creates each condition, using a strict Python client. |
| `winhttp/` | The header-only C++ WinHTTP transport for C++ hosts on Windows (`include/nf_winhttp_transport.hpp`, the only file that ships) and its conformance tests (`tests/`, `run-msvc.cmd`). The test-CA trust hook is in `tests/nf_winhttp_testing.hpp`, which is **never shipped**. |

## WinHTTP transport: platform and behaviour notes

- **TLS 1.3 (case 13):** Schannel supports TLS 1.3 from **Windows 11 and Windows Server 2022**. Every Windows 10
  version, and Windows Server 2019 and older, lists it as "Not supported" (Microsoft Learn, "Protocols in TLS/SSL
  (Schannel SSP)", updated 2025-03-20). WinHTTP's option docs add that Windows 11 enables only TLS 1.2 and 1.3 by
  default. On older Windows the constructor throws if WinHTTP rejects the TLS 1.3-only option. Otherwise every
  handshake fails, so the transport fails closed either way. The fail-closed path has not been exercised on this
  machine, which runs Windows 11.
- **Proxy:** the transport uses `WINHTTP_ACCESS_TYPE_NO_PROXY`. Behind a mandatory corporate proxy, every request
  fails closed. That is intended.
- **Deadline:** a threadpool-timer watchdog closes the request handle at `timeout_s`, which cancels the
  blocked WinHTTP call. Conformance case 4 requires the call to end within deadline + 0.25 s.
- **Revocation:** checking is ON in the shipped path (`WINHTTP_ENABLE_SSL_REVOCATION`) and fails closed. A revoked
  certificate and a revocation result of "unknown/offline" both fail the request, and no ignore flag is set.
  - **Verified locally:** with the test hook in Enforce mode, a CA-valid server fails with `CERT_REV_FAILED` (0x1),
    and no request byte reaches it. That proves revocation is requested and that "unknown" fails closed.
    Windows can't complete revocation for our untrusted test root.
  - **CI-only, not verified on this PC:** revoked vs good, and an unreachable CRL under a trusted root.
    That needs the test CA in a machine Root store, which happens only on an ephemeral GitHub-hosted runner
    (`tests/ci/`, manual-dispatch workflow on the CI branch).
  - **Removed from the local suite:** the check "rev: shipped path (CRL pre-cached) refuses a revoked leaf with
    CERT_REVOKED", together with its good-leaf companion.
    - **Why:** measured on 2026-09-27 under the untrusted test root, WinHTTP's own check raised no
      secure-failure flag (0x0) for the revoked leaf, even with the CA's CRL already in the CryptNet cache. The refusal
      came only from the test hook's own chain check, so a pass would not have shown anything about WinHTTP.
    - **Where it lives now:** the CI `trusted-root` job, check "ci revoked leaf: fails", through the shipped transport
      with no hook.
  - **Test path:** so the rest of the suite can run under the untrusted root, the unshipped hook tolerates
    WinHTTP's "revocation unknown" (`WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE`), in the test path only. Its own
    pin check then does the revocation work: chain to the pinned root with `CERT_CHAIN_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT`,
    CRL fetch allowed, and it refuses revoked, unknown and offline alike. Locally that verifies:
    - good plus a reachable CRL gives 200;
    - a revoked leaf is refused;
    - with the CRL server down, the request is refused;
    - no request byte reaches any refused server.

    That covers the test path and the fixtures, not WinHTTP's own decision.

## Cases (numbers as in the plan)

1. A bad certificate fails: self-signed, a wrong host on a valid chain, and expired (8), as separate cases. Nothing reaches those servers.
2. A TLS 1.2-only server fails, and nothing reaches it. Where TLS 1.3 isn't available, the transport fails closed (13).
3. A cross-origin 302 isn't followed, and the target never sees a request.
4. `timeout_s` is the whole-request deadline. The call must end within deadline + 0.25 s, both against a slow server (no headers for 5 s) and against a trickling body (headers at once, then 1 byte every 50 ms, so the deadline fires mid-body).
5. and 11. No token in logs, `what()`, the message or detail, `nf_last_error`, or the server log.
6. A same-origin 302 isn't followed.
7. The transport refuses plain http to a non-loopback host, CR/LF in headers, and credentials in the URL.
9. Test-CA trust only through the unshipped `tests/nf_winhttp_testing.hpp`. At compile time, `tests/test_release.cpp` proves that the shipped header has no trust API and leaves the test-access type undefined. `test_macro_rejected.cpp` must fail to compile, because `NF_TRANSPORT_TESTING` is an `#error` against the shipped header. At run time, the shipped transport refuses the test server.
10. The gRPC ingest transport (`WinHttpIngestTransport`, the device token):
    - **What it is:** gRPC over WinHTTP HTTP/2, which is required, with grpc-status read from the trailers. It runs under the same policy as the HTTP transport, plus a 1 MiB reply cap. It's tested THROUGH the library (`neuroforge::Sender` -> `nf_sender_*`).
    - **Part 1, `test_ingest.cpp`, runs locally:**
      - TLS 1.2-only, self-signed, wrong-host and expired servers are refused, nothing reaches them, and no device-token text appears in any error;
      - revocation unknown fails closed;
      - a server without HTTP/2 is refused;
      - plain-http origins and CR/LF in the metadata are refused.
    - **Part 2, `test_ingest_grpc.cpp` with `grpc_server.py`, written, NOT RUN:**
      - a GetStreamState reply is parsed;
      - StreamChunks uploads real signed WAL chunks, then FinishStream (acknowledged, WAL empties, NFDevice present);
      - a trailers-only error status is surfaced token-free;
      - a > 1 MiB reply is aborted;
      - the deadline holds within 0.25 s.
    - **Part 2 is waiting on:** `grpcio`, pinned with hashes in `requirements-grpc-test.txt`, for a dedicated test venv. It waits for the owner's install OK. Then run with `NF_GRPC_PYTHON=<that venv>\Scripts\python.exe`.
    - **Unity:** it has no gRPC stack (open item E5). Unity uploads go through a host that uses this transport.
    - **Accepted limit (nfb-security, case 10 review):** on a non-h2 negotiation, one request, token included,
      reaches the authenticated origin before the refusal. WinHTTP reports the negotiated protocol only after the response,
      and no status callback is added to shipped code. The origin is already authenticated before any byte is sent
      (TLS 1.3, certificate, hostname, revocation), and the device token is short-lived (≤ 10 min) and stream-bound.
    - **Infra requirement (nfb-security):** the ingest edge offers ONLY `h2` in ALPN, with no HTTP/1.1 fallback on the ingest host.
      A non-h2 negotiation then can only mean a misconfigured edge, and the client refuses it.
    - **Hardening:** `grpc-message` is server-controlled. After percent-decoding, C0 controls and DEL become spaces, and it's
      capped at 1024 bytes, so a server can't inject lines into consumer logs.
12. An oversized body (> 16 MiB) and oversized headers (> 64 KiB) are aborted.

## Running (bci-queen light lane, one "go" per run)

```
<venv>\Scripts\python.exe bindings\transport-conformance\run_conformance.py -- <venv>\Scripts\python.exe bindings\transport-conformance\selftest_client.py
bindings\transport-conformance\winhttp\run-msvc.cmd
```

The Unity check of the same conditions is an owner item: `bindings/unity/VERIFY-ON-EDITOR.md`, Step 5.
