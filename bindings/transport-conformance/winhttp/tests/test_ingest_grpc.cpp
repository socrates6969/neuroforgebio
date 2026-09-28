// CABI-M1 case 10, part 2: the HTTP/2 gRPC cases of the ingest transport, against grpc_server.py
// (grpcio, the same stack as the platform's ingest edge). NOT RUN YET: grpcio needs the owner's install
// OK (requirements-grpc-test.txt). Run by run-msvc.cmd only when NF_GRPC_PYTHON is set, under
// run_conformance.py --grpc. Everything goes THROUGH the library (neuroforge::Sender -> nf_sender_*).
#include "nf_winhttp_testing.hpp"

#include <chrono>
#include <filesystem>
#include <sstream>
#include <thread>

#include "conformance_common.hpp"

namespace {

namespace fs = std::filesystem;
using nf::transport::testing::PinnedCa;
using nf::transport::testing::PinnedIngestTransport;
using Clock = std::chrono::steady_clock;

bool token_free(const std::string &s) {
    return s.find("nfd1.") == std::string::npos && s.find("NFDevice") == std::string::npos;
}

// Events logged by grpc_server.py for one listener/method (presence flags only, never values).
struct GrpcEvents {
    int calls = 0, with_nfdevice = 0;
};
GrpcEvents grpc_events(const conf::Config &c, const std::string &listener, const std::string &method) {
    GrpcEvents e;
    std::istringstream in(conf::read_all(conf::raw_value(c.json, "grpc_events")));
    for (std::string line; std::getline(in, line);) {
        if (line.find("\"listener\": \"" + listener + "\"") == std::string::npos) continue;
        if (line.find("\"method\": \"" + method + "\"") == std::string::npos) continue;
        e.calls++;
        if (line.find("\"nfdevice_present\": true") != std::string::npos) e.with_nfdevice++;
    }
    return e;
}

std::string error_text(const neuroforge::Error &e) {
    return std::string(e.what()) + "|" + e.message() + "|" + e.detail() + "|" + nf_last_error() + "|" + nf_last_error_detail();
}

}  // namespace

int main() {
    conf::Config c = conf::load();
    if (c.json.find("\"grpc_good\"") == std::string::npos) {
        std::fprintf(stderr, "test_ingest_grpc: no gRPC server in this run (run_conformance.py --grpc)\n");
        return 3;
    }
    fs::path dir = fs::temp_directory_path() / ("nf-ingest-grpc-" + std::to_string(GetCurrentProcessId()));
    fs::create_directories(dir);
    int rc = 0;
    {
        nf::transport::WinHttpTransport t;
        PinnedCa pin(c.ca_cert);
        neuroforge::DeviceKey key = neuroforge::DeviceKey::generate();
        neuroforge::Wal wal = neuroforge::Wal::open_ephemeral_for_testing(dir.string(), "stream-1");
        neuroforge::Sender sender("tenant-a", "device-1", "stream-1", key, wal);

        // Happy path: GetStreamState over HTTP/2, device token present at the edge.
        PinnedIngestTransport good(t, pin, c.origin("grpc_good"));
        try {
            neuroforge::StreamState s = sender.state(good);
            CHECK(s.stream_id == "stream-1" && s.state == "open" && s.next_seq == 0, "10 grpc GetStreamState: parsed reply");
        } catch (const neuroforge::Error &e) {
            std::printf("  GetStreamState failed: %s\n", e.what());
            CHECK(false, "10 grpc GetStreamState: parsed reply");
        }
        GrpcEvents ge = grpc_events(c, "grpc_good", "GetStreamState");
        CHECK(ge.calls == 1 && ge.with_nfdevice == 1, "10 grpc: exactly one call, carrying an NFDevice authorization");

        // Client-streaming upload of real signed chunks from the WAL, then FinishStream.
        neuroforge::StreamWriter w("stream-1", neuroforge::Dtype::Float32, 2, 100, key, wal);
        {
            std::vector<float> samples(250 * 2, 1.5f);
            std::vector<double> ts(250);
            for (size_t i = 0; i < ts.size(); i++) ts[i] = 10.0 + static_cast<double>(i) / 250.0;
            w.push(samples, ts);
            w.flush();  // 3 chunks: 100 + 100 + 50
        }
        CHECK(wal.size() == 3, "10 grpc: 3 chunks waiting in the WAL");
        // CABI-T2 (ABI 1.2.1): a bare finish() with unsent chunks is refused and never reaches the edge.
        try {
            sender.finish(good);
            CHECK(false, "10 grpc CABI-T2: finish() with unsent chunks is refused");
        } catch (const neuroforge::Error &e) {
            CHECK(e.status() == NF_ERR_INVALID_ARG, "10 grpc CABI-T2: finish() with unsent chunks is refused");
        }
        CHECK(grpc_events(c, "grpc_good", "FinishStream").calls == 0, "10 grpc CABI-T2: no FinishStream reached the edge");
        CHECK(wal.size() == 3, "10 grpc CABI-T2: nothing was lost");
        try {
            neuroforge::StreamState s = sender.drain_and_finish(good, w, wal, 20.0);
            nf_sender_stats st = sender.stats();
            std::printf("  finish: state=%s next_seq=%llu n_samples=%llu; wal=%zu; sender calls=%llu acked=%llu rpc_errors=%llu\n",
                        s.state.c_str(), static_cast<unsigned long long>(s.next_seq), static_cast<unsigned long long>(s.n_samples),
                        wal.size(), static_cast<unsigned long long>(st.calls), static_cast<unsigned long long>(st.chunks_acked),
                        static_cast<unsigned long long>(st.rpc_errors));
            CHECK(s.state == "closed" && s.next_seq == 3 && s.n_samples == 250, "10 grpc StreamChunks + FinishStream: all acknowledged");
        } catch (const neuroforge::Error &e) {
            std::printf("  finish failed: %s\n", e.what());
            CHECK(false, "10 grpc StreamChunks + FinishStream: all acknowledged");
        }
        CHECK(wal.size() == 0, "10 grpc: the WAL is empty after the acknowledged upload");
        CHECK(grpc_events(c, "grpc_good", "StreamChunks").with_nfdevice >= 1, "10 grpc StreamChunks: NFDevice authorization present");

        // gRPC error (trailers-only PERMISSION_DENIED): surfaced as a transport failure, token-free.
        PinnedIngestTransport denied(t, pin, c.origin("grpc_denied"));
        try {
            sender.state(denied);
            CHECK(false, "10 grpc error status: surfaced as NF_ERR_TRANSPORT");
        } catch (const neuroforge::Error &e) {
            CHECK(e.status() == NF_ERR_TRANSPORT, "10 grpc error status: surfaced as NF_ERR_TRANSPORT");
            CHECK(token_free(error_text(e)), "10/11 grpc error status: no device-token text");
            const std::string etext = error_text(e);
            std::printf("  denied error text: %s\n", std::string(e.what()).c_str());
            CHECK(etext.find('\r') == std::string::npos && etext.find('\n') == std::string::npos,
                  "10 grpc error status: server-injected CR/LF neutralised (no line injection)");
            CHECK(etext.find("denied by the conformance test server") != std::string::npos,
                  "10 grpc error status: the server's message is carried (sanitised)");
        }

        // Reply cap (12): a > 1 MiB reply is aborted by the transport (and the library caps at 1 MiB).
        PinnedIngestTransport big(t, pin, c.origin("grpc_big"));
        try {
            sender.state(big);
            CHECK(false, "10/12 grpc > 1 MiB reply: aborted");
        } catch (const neuroforge::Error &e) {
            CHECK(e.status() == NF_ERR_TRANSPORT, "10/12 grpc > 1 MiB reply: aborted");
        }

        // Deadline (4): the sender's call timeout is the whole-call deadline, enforced by the watchdog.
        {
            nf_sender_config cfg = neuroforge::Sender::default_config();
            cfg.call_timeout_s = 1.0;
            neuroforge::Sender quick("tenant-a", "device-1", "stream-1", key, wal, &cfg);
            PinnedIngestTransport slow(t, pin, c.origin("grpc_slow"));
            auto t0 = Clock::now();
            bool failed = false;
            try {
                quick.state(slow);
            } catch (const neuroforge::Error &e) {
                failed = e.status() == NF_ERR_TRANSPORT;
            }
            double s = std::chrono::duration<double>(Clock::now() - t0).count();
            std::printf("  grpc slow server failed after %.2f s (deadline 1.0 s)\n", s);
            CHECK(failed && s < 1.25, "10/4 grpc deadline: failed within deadline + 0.25 s");
        }
        rc = conf::finish("test_ingest_grpc (case 10, HTTP/2 cases)");
    }
    std::error_code ec;
    fs::remove_all(dir, ec);
    return rc;
}
