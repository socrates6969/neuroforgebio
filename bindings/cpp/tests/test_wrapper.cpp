// C++17 test of neuroforge.hpp (built with MSVC by bindings/c/tests/run-msvc.cmd).
// Usage: test_wrapper <fixture-dir>   (fixture written by bindings/c/examples/make_fixture.rs)
#define _CRT_SECURE_NO_WARNINGS /* sscanf in the hex helper */
#include <cstdio>
#include <cstring>
#include <ctime>
#include <string>
#include <thread>
#include <vector>

#include "neuroforge.hpp"
#include "vectors.h"

namespace nf = neuroforge;

static int g_failed = 0, g_checks = 0;

#define CHECK(cond)                                                                           \
    do {                                                                                      \
        g_checks++;                                                                           \
        if (!(cond)) {                                                                        \
            g_failed++;                                                                       \
            std::fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond);     \
        }                                                                                     \
    } while (0)

// Expect `stmt` to throw nf::Error with status `code`.
#define CHECK_THROWS(stmt, code)                                                            \
    do {                                                                                      \
        bool thrown_ = false;                                                                 \
        try {                                                                                 \
            stmt;                                                                             \
        } catch (const nf::Error &e_) {                                                       \
            thrown_ = e_.status() == (code);                                                \
            if (!thrown_) std::fprintf(stderr, "  wrong error: %s\n", e_.what());             \
        }                                                                                     \
        CHECK(thrown_);                                                                       \
    } while (0)

static std::vector<uint8_t> unhex(const char *hex) {
    std::vector<uint8_t> out(std::strlen(hex) / 2);
    for (size_t i = 0; i < out.size(); i++) {
        unsigned v = 0;
        std::sscanf(hex + 2 * i, "%2x", &v);
        out[i] = static_cast<uint8_t>(v);
    }
    return out;
}

static void test_hashing() {
    CHECK(nf::abi_compatible());
    CHECK(!nf::core_version().empty());
    for (size_t i = 0; i < NF_VEC_CANONICAL_N; i++) CHECK(nf::canonicalize(NF_VEC_CANONICAL[i].in) == NF_VEC_CANONICAL[i].out);
    for (size_t i = 0; i < NF_VEC_PV_N; i++) CHECK(nf::pipeline_version_id(NF_VEC_PV[i].in) == NF_VEC_PV[i].out);
    for (size_t i = 0; i < NF_VEC_AUDITB_N; i++) CHECK(nf::audit_batch_id(NF_VEC_AUDITB[i].in) == NF_VEC_AUDITB[i].out);
    for (size_t i = 0; i < NF_VEC_CONSENT_N; i++) CHECK(nf::consent_record_hash(NF_VEC_CONSENT[i].in) == NF_VEC_CONSENT[i].out);
    for (size_t i = 0; i < NF_VEC_SUBJECT_N; i++)
        CHECK(nf::training_subject_hash(NF_VEC_SUBJECT[i].in, NF_VEC_SUBJECT[i].out) == NF_VEC_SUBJECT[i].extra);
    auto ids = nf::verify_prov_chain(NF_VEC_PROVB_CHAIN);
    CHECK(ids.size() == NF_VEC_PROVB_N);
    for (size_t i = 0; i < ids.size() && i < NF_VEC_PROVB_N; i++) CHECK(ids[i] == NF_VEC_PROVB[i].out);
    CHECK_THROWS(nf::verify_audit_chain(NF_VEC_PROVB_CHAIN), NF_ERR_VERIFY);

    nf::PublicKey pk{};
    auto pkv = unhex(NF_VEC_PUBLIC_KEY_HEX);
    std::memcpy(pk.data(), pkv.data(), 32);
    CHECK(nf::verify_device_token(NF_VEC_TOKEN, pk, NF_VEC_TOKEN_IAT) == NF_VEC_TOKEN_CLAIMS);
    CHECK_THROWS(nf::verify_device_token(NF_VEC_TOKEN, pk, NF_VEC_TOKEN_EXP + 31), NF_ERR_VERIFY);
    CHECK(nf::verify_provb_signature(NF_VEC_PROVB_SIG_BATCH_ID, unhex(NF_VEC_PROVB_SIG_HEX), pk));
    CHECK(nf::verify_anchor(NF_VEC_PROV_ANCHOR, pk));
    CHECK(nf::verify_certificate(NF_VEC_DELETION_CERTIFICATE, pk));

    // errors become exceptions with the status and message
    try {
        nf::canonicalize("{\"a\":1,\"a\":2}");
        CHECK(false);
    } catch (const nf::Error &e) {
        CHECK(e.status() == NF_ERR_CANONICAL);
        CHECK(!e.message().empty());
        CHECK(std::strstr(e.what(), "NF_ERR_CANONICAL") != nullptr);
    }
    CHECK_THROWS(nf::parse_dtype("complex64"), NF_ERR_INVALID_ARG);
    CHECK(nf::parse_dtype("int16") == nf::Dtype::Int16);
    CHECK(nf::itemsize(nf::Dtype::Float64) == 8);
    CHECK(nf::blob_id("") == "blob:sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
}

static void test_local(const std::string &dir) {
    nf::Recording rec(dir, "rec-001");
    CHECK(rec.n_samples() == 1000 && rec.n_channels() == 3 && rec.dtype() == nf::Dtype::Int16);
    CHECK(rec.channel_name(1) == "Cz" && rec.channel_unit(2) == "uV");
    auto x = rec.read<int16_t>(10, 12);
    CHECK(x.size() == 6);
    for (size_t k = 0; k < x.size(); k++) CHECK(x[k] == static_cast<int16_t>(((10 + k / 3) * 3 + k % 3) % 2000) - 1000);
    CHECK_THROWS(rec.read<float>(0, 1), NF_ERR_INVALID_ARG);
    auto phys = rec.read_physical(10, 12);
    CHECK(phys.size() == 6);
    for (size_t k = 0; k < phys.size() && k < x.size(); k++) CHECK(phys[k] == static_cast<double>(x[k]));
    CHECK(rec.read_physical(1000, 1000).empty());
    CHECK(nf::abi_version().minor >= 1);
    CHECK(rec.read_bytes(1000, 1000).empty());
    auto ts = rec.timestamps(0, 2);
    CHECK(ts.size() == 2 && ts[1] == 100.0 + 1.0 / 250.0);
    CHECK_THROWS(nf::Recording(dir, "nope"), NF_ERR_NOT_FOUND);
    CHECK_THROWS(rec.channel_name(3), NF_ERR_INVALID_ARG);

    // moved-from handles are empty and must not double free
    nf::ChunkCache cache(dir + "/cache", 1u << 20);
    std::vector<float> vals{0.5f, 1.5f, 2.5f, 3.5f, 4.5f, 5.5f};
    std::string id = nf::chunk_id(nf::Dtype::Float32, {2, 3}, vals.data(), vals.size() * sizeof(float));
    nf::Chunk c = cache.get(id);
    nf::Chunk moved = std::move(c);
    CHECK(moved.dtype() == nf::Dtype::Float32);
    CHECK((moved.shape() == std::vector<uint64_t>{2, 3}));
    auto bytes = moved.bytes();
    CHECK(bytes.size() == 24 && std::memcmp(bytes.data(), vals.data(), 24) == 0);
    CHECK_THROWS(cache.get("chunk:sha256:0000000000000000000000000000000000000000000000000000000000000000"),
                 NF_ERR_NOT_FOUND);
    CHECK(cache.size() > 0);

    nf::ProvRecorder prov(dir + "/prov", "cpp-chain");
    size_t before = prov.size();
    auto b = prov.record(R"([{"type":"agent","id":"urn:nf:user:1","label":"analyst"}])");
    CHECK(b.seq == before && nf::is_valid_id(b.id));
    auto pending = prov.pending();
    CHECK(!pending.empty() && pending.back().id == b.id);
    CHECK(nf::prov_batch_id(pending.back().canonical) == b.id);
    prov.mark_synced(b.seq);
    CHECK(prov.pending().empty());
    CHECK_THROWS(prov.record(R"([])"), NF_ERR_INVALID_ARG);
}

// A transport that is down, and one that throws: neither may crash the library.
struct DownTransport : nf::IngestTransport {
    int calls = 0;
    nf::RpcResult get_stream_state(const std::string &, const std::string &auth, double) override {
        calls += auth.rfind("NFDevice nfd1.", 0) == 0;
        return {14, "down for maintenance"};
    }
    nf::RpcResult stream_chunks(const std::vector<std::string> &, const std::string &, double) override { return {14, ""}; }
    nf::RpcResult finish_stream(const std::string &, const std::string &, double) override {
        throw std::runtime_error("transport bug");
    }
};

// A transport that acknowledges everything, with minimal hand-encoded proto3 replies
// (StreamAck / StreamState field 2 = next_seq varint, StreamState field 4 = state string).
static std::string varint(uint64_t v) {
    std::string out;
    while (v >= 0x80) {
        out.push_back(static_cast<char>((v & 0x7f) | 0x80));
        v >>= 7;
    }
    out.push_back(static_cast<char>(v));
    return out;
}
struct AckTransport : nf::IngestTransport {
    uint64_t acked = 0;
    int finishes = 0;
    std::string state_msg(const std::string &state) const {
        std::string m = "\x10" + varint(acked);
        if (!state.empty()) m += "\x22" + varint(state.size()) + state;
        return m;
    }
    nf::RpcResult get_stream_state(const std::string &, const std::string &, double) override { return {0, state_msg("open")}; }
    nf::RpcResult stream_chunks(const std::vector<std::string> &chunks, const std::string &, double) override {
        acked += chunks.size();  // chunks arrive in order from the committed seq
        return {0, "\x10" + varint(acked)};
    }
    nf::RpcResult finish_stream(const std::string &, const std::string &, double) override {
        finishes++;
        return {0, state_msg("closed")};
    }
};

static void test_streaming(const std::string &dir) {
    auto key = nf::DeviceKey::from_seed(std::vector<uint8_t>(32, 9));
    auto pk = key.public_key();
    std::string token = key.token("tenant", "dev-cpp", "s-cpp", 120);
    CHECK(nf::verify_device_token(token, pk, static_cast<int64_t>(std::time(nullptr))).find("dev-cpp") != std::string::npos);
    CHECK_THROWS(nf::DeviceKey::from_seed({1, 2, 3}), NF_ERR_INVALID_ARG);

    CHECK_THROWS(nf::Wal(dir + "/wal-cpp-nokey", "s-cpp"), NF_ERR_INVALID_ARG);
    auto eph = nf::Wal::open_ephemeral_for_testing(dir + "/wal-cpp-eph", "s-cpp");
    CHECK(eph.size() == 0);
    nf::Wal wal(dir + "/wal-cpp", "s-cpp", std::vector<uint8_t>(32, 3), {}, false);
    nf::StreamWriter w("s-cpp", nf::Dtype::Float32, 2, 10, key, wal);
    std::vector<float> samples(25 * 2, 0.25f);
    std::vector<double> ts(25);
    for (size_t i = 0; i < ts.size(); i++) ts[i] = 1.0 + static_cast<double>(i) / 100.0;
    CHECK(w.push(samples, ts) == 2);
    CHECK(w.flush());
    CHECK(w.stats().chunks == 3 && w.next_seq() == 3);
    CHECK(wal.size() == 3);
    CHECK_THROWS(w.push(std::vector<float>(3), std::vector<double>(1)), NF_ERR_INVALID_ARG);

    auto cfg = nf::Sender::default_config();
    cfg.backoff_min_s = 0.001;
    nf::Sender sender("tenant", "dev-cpp", "s-cpp", key, wal, &cfg);
    DownTransport t;
    try {
        sender.state(t);
        CHECK(false);
    } catch (const nf::Error &e) {
        CHECK(e.status() == NF_ERR_TRANSPORT);
        CHECK(e.message().find("down for maintenance") != std::string::npos);
    }
    CHECK(t.calls == 1);
    // CABI-T2: finish refuses while chunks are pending, before calling the transport
    CHECK_THROWS(sender.finish(t), NF_ERR_INVALID_ARG);
    // run/stop from two threads: the sender keeps retrying until stopped
    std::thread runner([&] { sender.run(t); });
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    sender.stop();
    runner.join();
    CHECK(sender.stats().rpc_errors >= 1);
    CHECK(wal.size() == 3);  // nothing acknowledged, nothing lost
    // drain_and_finish against a down transport times out and leaves the stream open
    CHECK_THROWS(sender.drain_and_finish(t, w, wal, 0.2), NF_ERR_TRANSPORT);
    CHECK(wal.size() == 3);

    // drain_and_finish against a healthy transport uploads everything, then closes
    AckTransport ok;
    nf::StreamState st = sender.drain_and_finish(ok, w, wal, 20.0);
    CHECK(wal.size() == 0);
    CHECK(ok.acked == 3 && ok.finishes == 1);
    CHECK(st.state == "closed" && st.next_seq == 3);
}

static void test_api() {
    CHECK_THROWS(nf::check_base_url("http://api.example.org"), NF_ERR_INVALID_ARG);
    int sends = 0;
    nf::ApiClient client(
        "https://api.example.org",
        [&](const nf::HttpRequest &r) {
            sends++;
            nf::HttpResponse resp;
            std::string auth;
            for (auto &h : r.headers)
                if (h.first == "authorization") auth = h.second;
            if (auth != "Bearer fresh") {
                resp.status = 401;
            } else if (r.url.find("/boom") != std::string::npos) {
                throw std::runtime_error("socket closed");
            } else if (r.url.find("/huge") != std::string::npos) {
                resp.status = 200;
                resp.body.assign(static_cast<size_t>(NF_MAX_RESPONSE_BYTES) + 1, 'x');
            } else if (r.url.find("/missing") != std::string::npos) {
                resp.status = 404;
                resp.body = R"({"title":"Not Found","status":404,"detail":"gone"})";
                resp.headers.push_back({"content-type", "application/problem+json"});
            } else {
                resp.status = 200;
                resp.body = r.method + " " + r.url;
            }
            return resp;
        },
        [](bool refresh) { return std::string(refresh ? "fresh" : "stale"); }, 5.0, 2);
    auto ok = client.request("GET", "/v1/ping", {{"q", "a b"}});
    CHECK(ok.status == 200 && ok.body == "GET https://api.example.org/v1/ping?q=a%20b");
    CHECK(sends == 2);
    try {
        client.request("GET", "/v1/missing");
        CHECK(false);
    } catch (const nf::Error &e) {
        CHECK(e.status() == NF_ERR_HTTP);
        CHECK(e.detail().find("gone") != std::string::npos);
    }
    CHECK_THROWS(client.request("POST", "/v1/boom", {}, {}, "{}"), NF_ERR_TRANSPORT);
    nf::ApiClient moved = std::move(client);
    CHECK(moved.request("GET", "/v1/ping").status == 200);
    // ABI 1.2.1: a response over NF_MAX_RESPONSE_BYTES fails the request
    CHECK_THROWS(moved.request("GET", "/v1/huge"), NF_ERR_TRANSPORT);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <fixture-dir>\n", argv[0]);
        return 2;
    }
    try {
        test_hashing();
        test_local(argv[1]);
        test_streaming(argv[1]);
        test_api();
    } catch (const std::exception &e) {
        std::fprintf(stderr, "unexpected exception: %s\n", e.what());
        g_failed++;
    }
    std::printf("test_wrapper: %d checks, %d failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}
