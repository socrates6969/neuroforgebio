// CABI-M1 case 10, part 1: the gRPC ingest transport (WinHttpIngestTransport) driven THROUGH the
// library (neuroforge::Sender::state -> nf_sender_state -> nf_ingest_transport callbacks, the
// NFDevice token minted by the library), for every case that is decided in the TLS handshake or
// before any network use. These need no HTTP/2 server. The HTTP/2 cases (happy path, deadline,
// size caps, trailers) need a local gRPC server: see README "case 10" (pending the lead's choice).
#include "nf_winhttp_testing.hpp"

#include <filesystem>

#include "conformance_common.hpp"

namespace {

namespace fs = std::filesystem;
using nf::transport::testing::PinnedCa;
using nf::transport::testing::PinnedIngestTransport;

struct Outcome {
    bool ok = false;
    nf_status err = NF_OK;
    std::string text;
};

// No part of an NFDevice token may appear in any error text (case 11).
bool token_free(const std::string &s) {
    return s.find("nfd1.") == std::string::npos && s.find("NFDevice") == std::string::npos;
}

Outcome state(neuroforge::Sender &sender, neuroforge::IngestTransport &t) {
    Outcome o;
    try {
        sender.state(t);
        o.ok = true;
    } catch (const neuroforge::Error &e) {
        o.err = e.status();
        o.text = std::string(e.what()) + "|" + e.message() + "|" + e.detail() + "|" + nf_last_error() + "|" + nf_last_error_detail();
    }
    return o;
}

}  // namespace

int main() {
    conf::Config c = conf::load();
    fs::path wal_dir = fs::temp_directory_path() / ("nf-ingest-test-" + std::to_string(GetCurrentProcessId()));
    fs::create_directories(wal_dir);
    int rc = 0;
    {
        nf::transport::WinHttpTransport t;
        PinnedCa pin(c.ca_cert);
        PinnedCa strict(c.ca_cert, nf::transport::testing::Revocation::Enforce);
        neuroforge::DeviceKey key = neuroforge::DeviceKey::generate();
        neuroforge::Wal wal = neuroforge::Wal::open_ephemeral_for_testing(wal_dir.string(), "stream-1");
        neuroforge::Sender sender("tenant-a", "device-1", "stream-1", key, wal);

        // 1/2/8/13: TLS-level refusals through the library; nothing may reach the server.
        for (const char *name : {"tls12only", "selfsigned", "wronghost", "expired"}) {
            PinnedIngestTransport ing(t, pin, c.origin(name));
            Outcome o = state(sender, ing);
            std::string what = std::string("10 ingest ") + name + ": the call fails (NF_ERR_TRANSPORT)";
            CHECK(!o.ok && o.err == NF_ERR_TRANSPORT, what.c_str());
            what = std::string("10 ingest ") + name + ": nothing (and no device token) reached the server";
            CHECK(conf::events_for(c, name) == 0, what.c_str());
            what = std::string("10/11 ingest ") + name + ": no device-token text in any error";
            CHECK(token_free(o.text), what.c_str());
        }

        // Revocation (shipped path): unknown status fails closed for gRPC too (2nd test CA, no CRL).
        {
            PinnedIngestTransport ing(t, strict, c.origin("crloffline"));
            Outcome o = state(sender, ing);
            DWORD flags = nf::transport::detail::TestAccess::last_secure_failure();
            std::printf("  ingest, revocation unknown: secure-failure flags 0x%08lx\n", static_cast<unsigned long>(flags));
            CHECK(!o.ok && o.err == NF_ERR_TRANSPORT && (flags & WINHTTP_CALLBACK_STATUS_FLAG_CERT_REV_FAILED),
                  "10 ingest rev: revocation enabled, and unknown status fails closed");
            CHECK(conf::events_for(c, "crloffline") == 0, "10 ingest rev: nothing reached the server");
        }

        // HTTP/2 is required: the stdlib test server speaks only HTTP/1.1 (no ALPN h2).
        {
            PinnedIngestTransport ing(t, pin, c.origin("good"));
            Outcome o = state(sender, ing);
            CHECK(!o.ok && o.err == NF_ERR_TRANSPORT, "10 ingest: a server without HTTP/2 is refused");
            CHECK(token_free(o.text), "10/11 ingest: no device-token text in the HTTP/2 refusal");
            // Informational (asked of nfb-security): WinHTTP learns the protocol from ALPN in the
            // handshake, but the transport checks it only after the response, so this request DID reach
            // the verified TLS 1.3 server over HTTP/1.1.
            std::printf("  ingest over HTTP/1.1: %d request(s) reached the (verified) server before the h2 check\n",
                        conf::events_for(c, "good", "/neuroforge.ingest.v1.IngestService/GetStreamState"));
        }

        // Before any network use: https-only origin, CR/LF in the authorization metadata.
        bool refused_http = false;
        try {
            nf::transport::WinHttpIngestTransport bad(t, "http://127.0.0.1:1");
        } catch (const nf::transport::TransportError &) {
            refused_http = true;
        }
        CHECK(refused_http, "10 ingest: a plain-http ingest origin is refused at construction");
        nf::transport::WinHttpTransport::GrpcResult inj =
            nf::transport::detail::TestAccess::grpc(t, c.origin("good"), "/x", {"m"}, "NFDevice a\r\nInjected: 1", 5.0, pin);
        CHECK(inj.code == 14 && token_free(inj.bytes), "10 ingest: CR/LF in the authorization metadata is refused");
        CHECK(conf::events_for(c, "good", "/x") == 0, "10 ingest: the injected request never left");

        CHECK(conf::read_all(c.events).find("nfd1.") == std::string::npos, "11 the server log holds no device-token text");
        rc = conf::finish("test_ingest (case 10, TLS-level and pre-network cases)");
    }
    std::error_code ec;
    fs::remove_all(wal_dir, ec);
    return rc;
}
