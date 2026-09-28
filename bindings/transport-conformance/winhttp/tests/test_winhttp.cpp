// CABI-M1 conformance suite for the WinHTTP transport, driven THROUGH the library
// (neuroforge::ApiClient -> nf_api_client_request -> transport callback), against the local TLS
// server started by run_conformance.py. Trust in the test CA comes only from the unshipped test
// header nf_winhttp_testing.hpp. Case numbers follow docs/hive/CABI-M1-PLAN.md (1-5 original, 6-13
// nfb-security).
#include "nf_winhttp_testing.hpp"

#include <chrono>
#include <random>

#include "conformance_common.hpp"

namespace {

std::string g_secret;  // the bearer token; must never show up in any error text

struct Outcome {
    bool ok = false;
    int status = 0;          // HTTP status when ok
    nf_status err = NF_OK;   // library status when not ok
    std::string text;        // every error text we can see: what(), message, detail, nf_last_error
    double seconds = 0;
};

const nf::transport::testing::PinnedCa *g_pin = nullptr;

Outcome call(nf::transport::WinHttpTransport &t, const std::string &base, const std::string &path, double timeout_s = 5.0) {
    Outcome o;
    auto t0 = std::chrono::steady_clock::now();
    try {
        neuroforge::ApiClient client(base, nf::transport::testing::pinned_http_send(t, *g_pin), [](bool) { return g_secret; },
                                     timeout_s, /*max_attempts=*/1,
                                     "nf-conformance");
        neuroforge::HttpResponse r = client.request("GET", path);
        o.ok = true;
        o.status = r.status;
    } catch (const neuroforge::Error &e) {
        o.err = e.status();
        o.text = std::string(e.what()) + "|" + e.message() + "|" + e.detail() + "|" + nf_last_error() + "|" + nf_last_error_detail();
    } catch (const std::exception &e) {
        o.err = -1;
        o.text = e.what();
    }
    o.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    return o;
}

bool no_secret(const Outcome &o) { return o.text.find(g_secret) == std::string::npos; }

}  // namespace

int main() {
    conf::Config c = conf::load();
    std::random_device rd;
    g_secret = "NFTEST-SECRET-" + std::to_string(rd()) + std::to_string(rd());

    nf::transport::WinHttpTransport t;
    nf::transport::testing::PinnedCa pin(c.ca_cert);
    g_pin = &pin;

    // 1 (baseline): TLS 1.3, pinned test CA, correct hostname -> 200, and the token reached the right server.
    Outcome good = call(t, c.origin("good"), "/ok");
    if (!good.ok)  // diagnostics only: which WinHTTP step failed and the secure-failure flags
        std::printf("  good server failed: %s (secure-failure flags 0x%08lx)\n", good.text.substr(0, good.text.find('|')).c_str(),
                    static_cast<unsigned long>(nf::transport::detail::TestAccess::last_secure_failure()));
    CHECK(good.ok && good.status == 200, "1 good server: 200 over TLS 1.3");
    CHECK(conf::events_for(c, "good", "/ok") == 1, "1 good server: exactly one request arrived (no retries)");

    // Revocation (nfb-security, b976337 review; lead ruling): the shipped send path REQUESTS revocation
    // checking and fails CLOSED when the result is unknown. Proven locally by behaviour (WinHTTP's
    // ENABLE_FEATURE is set-only): with the pin in Enforce mode, the same CA-valid good server that
    // just answered 200 now fails with CERT_REV_FAILED, since Windows cannot complete revocation for an
    // untrusted root, and no request byte reaches it. Revoked-vs-good and CRL-offline behaviour under
    // a TRUSTED root is CI-only (.github/workflows on the CI branch; see README).
    // The crloffline leaf comes from a second test CA whose CRL is never published, so its revocation
    // status is genuinely unknown (the first CA's CRL, once cached, cannot answer for it).
    nf::transport::testing::PinnedCa strict(c.ca_cert, nf::transport::testing::Revocation::Enforce);
    auto enforce_get = [&](const std::string &listener, const std::string &path, DWORD &flags) {
        Outcome o;
        try {
            neuroforge::ApiClient client(c.origin(listener), nf::transport::testing::pinned_http_send(t, strict),
                                         [](bool) { return g_secret; }, 10.0, 1, "nf-conformance");
            client.request("GET", path);
            o.ok = true;
        } catch (const neuroforge::Error &e) {
            o.err = e.status();
            o.text = std::string(e.what()) + "|" + e.message() + "|" + e.detail();
        }
        flags = nf::transport::detail::TestAccess::last_secure_failure();
        return o;
    };
    DWORD rev_flags = 0;
    Outcome rev = enforce_get("crloffline", "/rev-enforce", rev_flags);
    std::printf("  shipped path, revocation unknown: %s, secure-failure flags 0x%08lx\n", rev.ok ? "succeeded" : "failed",
                static_cast<unsigned long>(rev_flags));
    CHECK(!rev.ok && rev.err == NF_ERR_TRANSPORT && (rev_flags & WINHTTP_CALLBACK_STATUS_FLAG_CERT_REV_FAILED),
          "rev: revocation enabled, and unknown status fails closed (shipped path, CERT_REV_FAILED)");
    CHECK(conf::events_for(c, "crloffline", "/rev-enforce") == 0, "rev: no request byte reached the server");

    // Test-path revocation (nfb-security condition 3): the unshipped hook's own chain check with CRL
    // fetch. It proves the fixtures and the fail-closed rule; it does NOT prove WinHTTP's own
    // revoked-vs-good decision (CI-only).
    CHECK(conf::events_for(c, "crl") >= 1, "rev (test path): the hook fetched the CA's CRL for the good server");
    Outcome hrev = call(t, c.origin("revoked"), "/ok");
    std::printf("  revoked: chain status 0x%08lx\n", static_cast<unsigned long>(nf::transport::testing::PinnedCa::last_chain_error()));
    CHECK(!hrev.ok && hrev.err == NF_ERR_TRANSPORT, "rev (test path): a revoked leaf is refused");
    CHECK(conf::events_for(c, "revoked") == 0, "rev (test path): no request byte reached the revoked server");
    Outcome hoff = call(t, c.origin("crloffline"), "/ok", 15.0);
    std::printf("  CRL offline: chain status 0x%08lx after %.2f s\n",
                static_cast<unsigned long>(nf::transport::testing::PinnedCa::last_chain_error()), hoff.seconds);
    CHECK(!hoff.ok && hoff.err == NF_ERR_TRANSPORT, "rev (test path): CRL server down is refused (fail closed)");
    CHECK(conf::events_for(c, "crloffline") == 0, "rev (test path): no request byte reached the CRL-offline server");

    // NOT testable locally (measured, run of 2026-09-27): under the untrusted test root, WinHTTP's OWN
    // decision on the revoked leaf, even with the CA's CRL already in the CryptNet cache, raised no
    // secure-failure flag (0x0); only this hook's own chain check refused it. So WinHTTP's
    // revoked-vs-good decision is CI-only (trusted root on an ephemeral runner), not claimed here.

    // 2 / 13: a TLS 1.2-only server is refused, and nothing reaches it.
    Outcome t12 = call(t, c.origin("tls12only"), "/ok");
    CHECK(!t12.ok && t12.err == NF_ERR_TRANSPORT, "2 TLS 1.2-only server: NF_ERR_TRANSPORT");
    CHECK(conf::events_for(c, "tls12only") == 0, "2 TLS 1.2-only server: no request arrived");

    // 1 / 8: self-signed, wrong host (SAN mismatch on a valid test-CA chain) and expired, as separate cases.
    for (const char *name : {"selfsigned", "wronghost", "expired"}) {
        Outcome o = call(t, c.origin(name), "/ok");
        std::string what = std::string("8 ") + name + ": NF_ERR_TRANSPORT";
        CHECK(!o.ok && o.err == NF_ERR_TRANSPORT, what.c_str());
        what = std::string("8 ") + name + ": no request (and no token) arrived";
        CHECK(conf::events_for(c, name) == 0, what.c_str());
        what = std::string("11 ") + name + ": no token in any error text";
        CHECK(no_secret(o), what.c_str());
    }

    // 3: cross-origin 302 is not followed; the target never sees a request.
    Outcome cross = call(t, c.origin("redirect"), "/start");
    CHECK(!cross.ok && (cross.err == NF_ERR_HTTP || cross.err == NF_ERR_TRANSPORT), "3 cross-origin 302: surfaced, not followed");
    CHECK(conf::events_for(c, "target") == 0, "3 cross-origin 302: the target received nothing (no Authorization)");

    // 6: same-origin 302 is not followed either.
    Outcome same = call(t, c.origin("redirect_same"), "/start");
    CHECK(!same.ok && (same.err == NF_ERR_HTTP || same.err == NF_ERR_TRANSPORT), "6 same-origin 302: surfaced, not followed");
    CHECK(conf::events_for(c, "redirect_same", "/landed") == 0, "6 same-origin 302: /landed was never requested");

    // 4: timeout_s is the whole-request deadline (server answers after 5 s; deadline 1 s).
    Outcome slow = call(t, c.origin("slow"), "/ok", 1.0);
    CHECK(!slow.ok && slow.err == NF_ERR_TRANSPORT, "4 slow server: NF_ERR_TRANSPORT");
    std::printf("  slow server failed after %.2f s (deadline 1.0 s)\n", slow.seconds);
    // nfb-security condition 3: the watchdog closes the handle AT the deadline; bound tightened from
    // < 2.5 s to < timeout + 0.25 s (stricter, not looser).
    CHECK(slow.seconds < 1.25, "4 slow server: failed within deadline + 0.25 s (watchdog)");

    // 12: oversized body and oversized headers are aborted.
    Outcome big = call(t, c.origin("big"), "/x", 30.0);
    CHECK(!big.ok && big.err == NF_ERR_TRANSPORT, "12 17 MiB body > 16 MiB cap: aborted");
    Outcome bigh = call(t, c.origin("bigheaders"), "/x");
    CHECK(!bigh.ok && bigh.err == NF_ERR_TRANSPORT, "12 80 KiB headers > 64 KiB cap: aborted");

    // 7: the transport itself refuses plain http to a non-loopback host, and CR/LF header injection.
    auto transport_refuses = [&](const std::string &url, std::pair<std::string, std::string> header) {
        neuroforge::HttpRequest r;
        r.method = "GET";
        r.url = url;
        r.headers.push_back(std::move(header));
        r.timeout_s = 2;
        try {
            t.send(r);
            return false;
        } catch (const nf::transport::TransportError &) {
            return true;
        }
    };
    CHECK(transport_refuses("http://example.invalid/x", {"Authorization", "Bearer " + g_secret}),
          "7 plain http to a non-loopback host: refused by the transport before any network use");
    CHECK(transport_refuses(c.origin("good") + "/x", {"X-Test", "a\r\nInjected: 1"}), "7 CR/LF in a header value: refused");
    CHECK(transport_refuses("https://user:pw@localhost:1/x", {"X-Test", "1"}), "7 credentials in the URL: refused");

    // 11: no token in any error text, for every failing case above.
    bool clean = no_secret(rev) && no_secret(hrev) && no_secret(hoff) && no_secret(t12) && no_secret(cross) && no_secret(same) && no_secret(slow) && no_secret(big) && no_secret(bigh);
    CHECK(clean, "11 no token text in what()/message/detail/nf_last_error for any failure");
    CHECK(conf::read_all(c.events).find(g_secret) == std::string::npos, "11 the server log holds no token text either");

    // 4 (watchdog, mid-body): headers arrive at once, then the body trickles 1 byte / 50 ms for 5 s,
    // so the 1 s deadline fires while the BODY is being read (each read returns quickly, so only the
    // whole-request deadline can stop it). Must end within deadline + 0.25 s, and not before it.
    Outcome mid = call(t, c.origin("trickle"), "/x", 1.0);
    std::printf("  trickling body with a 1.0 s deadline ended after %.3f s\n", mid.seconds);
    CHECK(!mid.ok && mid.err == NF_ERR_TRANSPORT && mid.seconds >= 0.95 && mid.seconds < 1.25,
          "4 deadline during a trickling body: ended at the deadline (watchdog)");

    return conf::finish("test_winhttp (test CA via nf_winhttp_testing.hpp)");
}
