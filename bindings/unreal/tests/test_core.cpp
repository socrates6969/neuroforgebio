// Tests of the Unreal plugin's engine-free core (NeuroForgeCore/*) against the REAL neuroforge
// library and the shared C/C++ fixture (bindings/c/tests/fixture/mod.rs):
//   rec-001: 3 channels Fz/Cz/Pz, 250 Hz, 1000 int16 samples,
//   sample(i, c) = (i*3 + c) % 2000 - 1000, timestamp(i) = 100 + i/250.
// Built and run by run-msvc.cmd (MSVC /W4 /WX). Usage: test_core <fixture dir>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <thread>
#include <vector>

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <psapi.h>

#include <memory>

#include "NeuroForgeCore/NfAbi.h"
#include "NeuroForgeCore/NfReplay.h"
#include "NeuroForgeCore/NfStreamState.h"
#include "vectors.h"  // bindings/c/tests/c/vectors.h (generated from spec/test-vectors)

namespace {

int g_failures = 0;
int g_checks = 0;

#define CHECK(cond)                                                                 \
    do {                                                                            \
        g_checks++;                                                                 \
        if (!(cond)) {                                                              \
            g_failures++;                                                           \
            std::fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond); \
        }                                                                           \
    } while (0)

template <class F>
bool throws_status(F &&f, nf_status want) {
    try {
        f();
    } catch (const neuroforge::Error &e) {
        return e.status() == want;
    }
    return false;
}

using namespace nf::engine;
using Clock = std::chrono::steady_clock;

std::string g_root;
const char *kRec = "rec-001";
const uint64_t kN = 1000;
const double kSfreq = 250.0;

int16_t sample(uint64_t i, uint64_t c) { return static_cast<int16_t>(static_cast<int64_t>((i * 3 + c) % 2000) - 1000); }

neuroforge::Recording open_rec() { return neuroforge::Recording(g_root, kRec); }

std::vector<uint8_t> unhex(const char *h) {
    std::vector<uint8_t> out;
    auto nib = [](char c) { return static_cast<uint8_t>(c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10); };
    for (size_t i = 0; h[i] && h[i + 1]; i += 2) out.push_back(static_cast<uint8_t>(nib(h[i]) << 4 | nib(h[i + 1])));
    return out;
}

size_t private_bytes() {
    PROCESS_MEMORY_COUNTERS_EX pmc{};
    GetProcessMemoryInfo(GetCurrentProcess(), reinterpret_cast<PROCESS_MEMORY_COUNTERS *>(&pmc), sizeof(pmc));
    return pmc.PrivateUsage;
}

// ------------------------------------------------------------------ tests
void test_abi_and_vectors() {
    CHECK(neuroforge::abi_compatible());
    CHECK(!neuroforge::core_version().empty());
    // The two vector families the Blueprint library exposes (blob IDs, canonical JSON).
    for (size_t i = 0; i < NF_VEC_BLOB_N; i++) {
        std::vector<uint8_t> d = unhex(NF_VEC_BLOB[i].in);
        std::string id = neuroforge::blob_id(d.data(), d.size());
        CHECK(id == NF_VEC_BLOB[i].out);
        CHECK(neuroforge::is_valid_id(id));
    }
    for (size_t i = 0; i < NF_VEC_CANONICAL_N; i++) CHECK(neuroforge::canonicalize(NF_VEC_CANONICAL[i].in) == NF_VEC_CANONICAL[i].out);
    for (size_t i = 0; i < NF_VEC_CANONICAL_ERRORS_N; i++)
        CHECK(throws_status([&] { neuroforge::canonicalize(NF_VEC_CANONICAL_ERRORS[i].in); }, NF_ERR_CANONICAL));
}

void test_to_float() {
    using D = neuroforge::Dtype;
    {
        int16_t v[3] = {-32768, 0, 32767};
        float f[3];
        to_float(D::Int16, reinterpret_cast<const uint8_t *>(v), 3, f);
        CHECK(f[0] == -32768.0f && f[1] == 0.0f && f[2] == 32767.0f);
    }
    {
        int32_t v[2] = {-100000, 7};
        float f[2];
        to_float(D::Int32, reinterpret_cast<const uint8_t *>(v), 2, f);
        CHECK(f[0] == -100000.0f && f[1] == 7.0f);
    }
    {
        int64_t v[1] = {-5};
        float f[1];
        to_float(D::Int64, reinterpret_cast<const uint8_t *>(v), 1, f);
        CHECK(f[0] == -5.0f);
    }
    {
        double v[2] = {0.25, -1.5};
        float f[2];
        to_float(D::Float64, reinterpret_cast<const uint8_t *>(v), 2, f);
        CHECK(f[0] == 0.25f && f[1] == -1.5f);
    }
    {
        float v[1] = {3.5f}, f[1];
        to_float(D::Float32, reinterpret_cast<const uint8_t *>(v), 1, f);
        CHECK(f[0] == 3.5f);
    }
    {
        uint8_t v[1] = {0};
        float f[1];
        CHECK(throws_status([&] { to_float(static_cast<D>(99), v, 1, f); }, NF_ERR_INVALID_ARG));
    }
}

void test_read_floats() {
    neuroforge::Recording r = open_rec();
    CHECK(r.n_samples() == kN && r.n_channels() == 3 && r.sfreq() == kSfreq);
    CHECK(r.dtype() == neuroforge::Dtype::Int16);
    std::vector<float> all = read_floats(r, 0, kN);
    CHECK(all.size() == kN * 3);
    bool ok = true;
    for (uint64_t i = 0; i < kN; i++)
        for (uint64_t c = 0; c < 3; c++) ok = ok && all[i * 3 + c] == static_cast<float>(sample(i, c));
    CHECK(ok);
    CHECK(read_floats(r, 990, 5000).size() == 10 * 3);  // clamped to the end
    CHECK(read_floats(r, 1000, 1010).empty());          // empty range: no native call
    CHECK(read_floats(r, 20, 10).empty());
    // Split reads (ABI 1.2 caps one native read at 1 GiB): force 7-row pieces (7 * 3 ch * 2 B)
    // and odd boundaries; the result must equal one unsplit read.
    CHECK(read_floats(r, 0, kN, 42) == all);
    CHECK(read_floats(r, 5, 998, 42) == read_floats(r, 5, 998));
    CHECK(read_stored_floats(r, 0, kN, 1) == read_stored_floats(r, 0, kN));  // below one row: 1 row per call
    CHECK(rows_per_call(r) == kMaxStoredBytesPerCall / 6);
}

// Replace the value of member `key` (first occurrence) in a JSON text. Enough for the fixture's
// zarr.json; the value is a number, null or a flat array.
bool replace_member(std::string &text, const std::string &key, const std::string &value) {
    size_t k = text.find("\"" + key + "\"");
    if (k == std::string::npos) {
        // Absent (defaults): insert it as the first member of the nf_signal object.
        size_t g = text.find("\"nf_signal\"");
        size_t brace = g == std::string::npos ? g : text.find('{', g);
        if (brace == std::string::npos) return false;
        text.insert(brace + 1, "\"" + key + "\":" + value + ",");
        return true;
    }
    size_t colon = text.find(':', k);
    if (colon == std::string::npos) return false;
    size_t b = colon + 1;
    while (b < text.size() && (text[b] == ' ' || text[b] == '\n' || text[b] == '\r' || text[b] == '\t')) b++;
    size_t e = b;
    if (text[b] == '[') {
        e = text.find(']', b);
        if (e == std::string::npos) return false;
        e++;
    } else {
        while (e < text.size() && text[e] != ',' && text[e] != '}' && text[e] != '\n') e++;
    }
    text.replace(b, e - b, value);
    return true;
}

// Physical values (ABI 1.1): a copy of the fixture with per-channel scale/offset, the same
// transformation bindings/c/tests/abi.rs applies. Replay must deliver stored * scale + offset.
void test_physical_values() {
    namespace fs = std::filesystem;
    fs::path src = fs::path(g_root) / kRec, root = fs::path(g_root).parent_path() / "fixture-scaled";
    fs::remove_all(root);
    fs::create_directories(root);
    fs::copy(src, root / kRec, fs::copy_options::recursive);
    fs::path meta = root / kRec / "zarr.json";
    std::string text;
    {
        std::ifstream in(meta, std::ios::binary);
        text.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
    }
    CHECK(replace_member(text, "scale", "[0.5,1.0,2.0]"));
    CHECK(replace_member(text, "offset", "[0.0,10.0,-1.0]"));
    {
        std::ofstream out(meta, std::ios::binary | std::ios::trunc);
        out << text;
    }
    const float scale[3] = {0.5f, 1.0f, 2.0f}, offset[3] = {0.0f, 10.0f, -1.0f};
    neuroforge::Recording r(root.string(), kRec);
    std::vector<float> phys = read_floats(r, 0, kN), stored = read_stored_floats(r, 0, kN);
    bool ok = phys.size() == kN * 3 && stored.size() == kN * 3;
    for (uint64_t i = 0; ok && i < kN; i++)
        for (uint64_t c = 0; c < 3; c++) {
            float s = static_cast<float>(sample(i, c));
            ok = ok && stored[i * 3 + c] == s && phys[i * 3 + c] == s * scale[c] + offset[c];
        }
    CHECK(ok);

    ReplayOptions o;
    o.speed = std::numeric_limits<double>::infinity();
    o.block_samples = 250;
    o.backpressure = Backpressure::Block;
    ReplayWorker w(neuroforge::Recording(root.string(), kRec), o);
    w.start();
    SampleBlock b;
    auto deadline = Clock::now() + std::chrono::seconds(10);
    while (!w.try_pop(b) && Clock::now() < deadline) std::this_thread::sleep_for(std::chrono::milliseconds(1));
    CHECK(b.rows == 250 && b.at(3, 2) == static_cast<float>(sample(3, 2)) * 2.0f - 1.0f);
    w.stop();
}

void test_replay_exact() {
    ReplayOptions o;
    o.speed = std::numeric_limits<double>::infinity();
    o.block_samples = 37;
    o.max_queued = 4;
    o.backpressure = Backpressure::Block;
    ReplayWorker w(open_rec(), o);
    CHECK(w.channel_names() == (std::vector<std::string>{"Fz", "Cz", "Pz"}));
    w.start();
    uint64_t next = 0;
    bool ok = true;
    auto deadline = Clock::now() + std::chrono::seconds(30);
    SampleBlock b;
    while (next < kN && Clock::now() < deadline) {
        if (!w.try_pop(b)) {
            if (w.error()) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
            continue;
        }
        ok = ok && b.first_sample == next && b.channels == 3 && b.time_s == static_cast<double>(next) / kSfreq;
        for (uint32_t row = 0; row < b.rows; row++)
            for (uint32_t c = 0; c < 3; c++) ok = ok && b.at(row, c) == static_cast<float>(sample(b.first_sample + row, c));
        next += b.rows;
    }
    CHECK(ok);
    CHECK(next == kN);
    w.stop();
    CHECK(w.completed());
    CHECK(!w.error());
    CHECK(w.dropped_blocks() == 0);
    CHECK(!w.try_pop(b));
}

void test_replay_paced() {
    ReplayOptions o;
    o.speed = 4.0;  // the 4 s fixture should take about 1 s
    o.block_samples = 25;
    ReplayWorker w(open_rec(), o);
    auto t0 = Clock::now();
    w.start();
    uint64_t rows = 0;
    SampleBlock b;
    while (!(w.completed() && w.queued() == 0) && Clock::now() - t0 < std::chrono::seconds(10)) {
        while (w.try_pop(b)) rows += b.rows;
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    while (w.try_pop(b)) rows += b.rows;
    double s = std::chrono::duration<double>(Clock::now() - t0).count();
    CHECK(rows == kN);
    std::printf("  paced replay at 4x: %.3f s (expected about 1.0)\n", s);
    CHECK(s > 0.9 && s < 2.0);
}

void test_replay_loop_and_stop() {
    ReplayOptions o;
    o.speed = std::numeric_limits<double>::infinity();
    o.loop = true;
    o.block_samples = 100;
    o.max_queued = 8;
    o.backpressure = Backpressure::Block;
    ReplayWorker w(open_rec(), o);
    w.start();
    uint32_t max_loop = 0;
    auto deadline = Clock::now() + std::chrono::seconds(10);
    SampleBlock b;
    while (max_loop < 2 && Clock::now() < deadline)
        if (w.try_pop(b)) max_loop = (std::max)(max_loop, b.loop);
    CHECK(max_loop == 2);
    auto t0 = Clock::now();
    w.stop();  // the worker is blocked on a full queue: stop must wake it
    CHECK(Clock::now() - t0 < std::chrono::seconds(1));
    CHECK(!w.running());

    // A paced worker waiting for its next block must also stop promptly.
    ReplayOptions slow;
    slow.speed = 0.001;
    ReplayWorker w2(open_rec(), slow);
    w2.start();
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    t0 = Clock::now();
    w2.stop();
    CHECK(Clock::now() - t0 < std::chrono::seconds(1));
}

void test_drop_oldest() {
    ReplayOptions o;
    o.speed = std::numeric_limits<double>::infinity();
    o.block_samples = 10;
    o.max_queued = 5;
    o.backpressure = Backpressure::DropOldest;
    ReplayWorker w(open_rec(), o);
    w.start();
    auto deadline = Clock::now() + std::chrono::seconds(10);
    while (!w.completed() && Clock::now() < deadline) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    CHECK(w.completed());
    CHECK(w.queued() == 5);
    CHECK(w.dropped_blocks() == 100 - 5);
    SampleBlock b;
    CHECK(w.try_pop(b) && b.first_sample == 950);  // the newest blocks survived
}

void test_bad_options() {
    ReplayOptions o;
    o.speed = 0;
    CHECK(throws_status([&] { ReplayWorker w(open_rec(), o); }, NF_ERR_INVALID_ARG));
    o.speed = 1;
    o.block_samples = 0;
    CHECK(throws_status([&] { ReplayWorker w(open_rec(), o); }, NF_ERR_INVALID_ARG));
    CHECK(throws_status([&] { neuroforge::Recording r(g_root, "no-such-recording"); }, NF_ERR_NOT_FOUND) ||
          throws_status([&] { neuroforge::Recording r(g_root, "no-such-recording"); }, NF_ERR_IO));
    ReplayWorker w(open_rec(), ReplayOptions{});
    w.start();
    CHECK(throws_status([&] { w.start(); }, NF_ERR_INVALID_ARG));
}

void test_abi_rule() {
    CHECK(abi_compatible(nf_abi_version()));
    CHECK(abi_compatible(1u << 16 | 1u << 8, 1, 1));
    CHECK(abi_compatible(1u << 16 | 5u << 8 | 3u, 1, 1));  // newer minor is fine
    CHECK(!abi_compatible(1u << 16 | 0u << 8 | 9u, 1, 1)); // older minor: a missing symbol
    CHECK(!abi_compatible(2u << 16 | 1u << 8, 1, 1));      // other major
    CHECK(!abi_compatible(0u, 1, 1));
}

// Destroying a worker that is blocked on a full queue (Block policy), and replacing a worker from
// inside the consumer loop (what a game handler calling Stop/Start does), must neither hang nor crash.
void test_destroy_and_replace_mid_stream() {
    ReplayOptions o;
    o.speed = std::numeric_limits<double>::infinity();
    o.block_samples = 10;
    o.max_queued = 2;
    o.backpressure = Backpressure::Block;
    {
        auto w = std::make_unique<ReplayWorker>(open_rec(), o);
        w->start();
        std::this_thread::sleep_for(std::chrono::milliseconds(50));  // the queue is full: the worker waits
        CHECK(w->queued() == 2);
        auto t0 = Clock::now();
        w.reset();  // destructor stops and joins
        CHECK(Clock::now() - t0 < std::chrono::seconds(1));
    }
    auto w = std::make_unique<ReplayWorker>(open_rec(), o);
    w->start();
    SampleBlock b;
    int replaced = 0;
    auto deadline = Clock::now() + std::chrono::seconds(10);
    uint64_t last_first = 0;
    while (Clock::now() < deadline) {
        if (!w->try_pop(b)) continue;
        last_first = b.first_sample;
        if (b.first_sample == 20 && replaced < 3) {  // "handler" restarts the stream
            w = std::make_unique<ReplayWorker>(open_rec(), o);
            w->start();
            replaced++;
            continue;
        }
        if (replaced == 3 && b.first_sample == 990) break;
    }
    CHECK(replaced == 3);
    CHECK(last_first == 990);
}

void test_stream_state() {
    StreamState s;
    s.reset({"Fz", "Cz", "Pz"}, 250.0);
    CHECK(std::isnan(s.value("Cz")));  // no data yet
    CHECK(s.channel_index("Pz") == 2 && s.channel_index("Oz") == -1);
    SampleBlock b;
    b.first_sample = 10;
    b.rows = 2;
    b.channels = 3;
    b.data = {1, 2, 3, 4, 5, 6};
    s.apply(b);
    CHECK(s.current_sample() == 11);
    CHECK(s.value("Fz") == 4 && s.value("Cz") == 5 && s.value("Pz") == 6);
    CHECK(std::isnan(s.value("Oz")));
    b.channels = 2;  // mismatched block is ignored
    s.apply(b);
    CHECK(s.blocks() == 1);
}

// Repeated create/free loops: process private bytes must not grow (a leak of even a few dozen
// bytes per iteration would exceed the bound).
void test_no_leaks() {
    auto measure = [](const char *what, int n, auto &&body) {
        for (int i = 0; i < (std::min)(n, 500); i++) body();  // warm up allocator pools
        size_t before = private_bytes();
        for (int i = 0; i < n; i++) body();
        long long growth = static_cast<long long>(private_bytes()) - static_cast<long long>(before);
        std::printf("  %-28s %6d iterations, private bytes %+lld KiB\n", what, n, growth / 1024);
        CHECK(growth < (8ll << 20));
    };
    measure("Recording open/read/free", 5000, [] {
        neuroforge::Recording r = open_rec();
        (void)read_floats(r, 0, 64);
    });
    measure("ReplayWorker create/free", 2000, [] {
        ReplayOptions o;
        o.speed = std::numeric_limits<double>::infinity();
        o.max_queued = 2;
        ReplayWorker w(open_rec(), o);
        w.start();
    });
    measure("blob_id", 100000, [] { (void)neuroforge::blob_id("hello\n"); });
    measure("error path", 100000, [] {
        try {
            neuroforge::canonicalize("{\"a\":1,\"a\":2}");
        } catch (const neuroforge::Error &) {
        }
    });
}

}  // namespace

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: test_core <fixture dir>\n");
        return 2;
    }
    g_root = argv[1];
    struct {
        const char *name;
        void (*fn)();
    } tests[] = {
        {"abi_and_vectors", test_abi_and_vectors}, {"to_float", test_to_float},
        {"read_floats", test_read_floats},         {"physical_values", test_physical_values},
        {"replay_exact", test_replay_exact},
        {"replay_paced", test_replay_paced},       {"replay_loop_and_stop", test_replay_loop_and_stop},
        {"drop_oldest", test_drop_oldest},         {"bad_options", test_bad_options},
        {"abi_rule", test_abi_rule},               {"destroy_and_replace", test_destroy_and_replace_mid_stream},
        {"stream_state", test_stream_state},       {"no_leaks", test_no_leaks},
    };
    for (auto &t : tests) {
        int before = g_failures;
        try {
            t.fn();
        } catch (const std::exception &e) {
            g_failures++;
            std::fprintf(stderr, "%s: unexpected exception: %s\n", t.name, e.what());
        }
        std::printf("%s %s\n", g_failures == before ? "PASS" : "FAIL", t.name);
    }
    std::printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
