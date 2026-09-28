// neuroforge.hpp: header-only C++17 RAII wrapper over the neuroforge C ABI (ADR 0013).
//
// - Every handle is a move-only object that frees itself.
// - Every failing call throws neuroforge::Error (status code, message, detail).
// - Callbacks into C++ (transports, token sources) never let an exception reach the C ABI: a
//   throwing callback is reported to the library as a failure.
// - No logic lives here; everything is forwarded to the C ABI.
//
// Data flows device -> SDK -> platform only; nothing here sends anything to acquisition hardware.
#ifndef NEUROFORGE_HPP
#define NEUROFORGE_HPP

#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <chrono>
#include <exception>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

#include "neuroforge.h"

namespace neuroforge {

// ---------------------------------------------------------------- errors
class Error : public std::runtime_error {
public:
    Error(nf_status status, std::string message, std::string detail = {})
        : std::runtime_error(std::string(nf_status_name(status)) + ": " + message),
          status_(status), message_(std::move(message)), detail_(std::move(detail)) {}
    nf_status status() const noexcept { return status_; }
    const std::string &message() const noexcept { return message_; }
    // problem+json for NF_ERR_HTTP, else empty
    const std::string &detail() const noexcept { return detail_; }

private:
    nf_status status_;
    std::string message_;
    std::string detail_;
};

namespace detail {

inline void check(nf_status s) {
    if (s != NF_OK) throw Error(s, nf_last_error(), nf_last_error_detail());
}

// Owns an nf_buf for the duration of one call.
class Buf {
public:
    Buf() = default;
    Buf(const Buf &) = delete;
    Buf &operator=(const Buf &) = delete;
    ~Buf() { nf_buf_free(&b_); }
    nf_buf *out() noexcept { return &b_; }
    std::string str() const { return b_.data ? std::string(reinterpret_cast<const char *>(b_.data), b_.len) : std::string(); }
    std::vector<uint8_t> bytes() const { return b_.data ? std::vector<uint8_t>(b_.data, b_.data + b_.len) : std::vector<uint8_t>(); }

private:
    nf_buf b_{nullptr, 0};
};

template <class F>
std::string text(F &&f) {
    Buf b;
    check(f(b.out()));
    return b.str();
}

inline const uint8_t *u8(std::string_view s) noexcept { return reinterpret_cast<const uint8_t *>(s.data()); }

inline std::vector<std::string> lines(const std::string &s) {
    std::vector<std::string> out;
    if (s.empty()) return out;
    size_t start = 0;
    for (;;) {
        size_t nl = s.find('\n', start);
        out.push_back(s.substr(start, nl == std::string::npos ? std::string::npos : nl - start));
        if (nl == std::string::npos) return out;
        start = nl + 1;
    }
}

template <class T, void (*Free)(T *)>
struct Deleter {
    void operator()(T *p) const noexcept { Free(p); }
};

template <class T, void (*Free)(T *)>
using Handle = std::unique_ptr<T, Deleter<T, Free>>;

}  // namespace detail

// ---------------------------------------------------------------- version
struct AbiVersion {
    uint32_t major, minor, patch;
};

inline AbiVersion abi_version() noexcept {
    uint32_t v = nf_abi_version();
    return {v >> 16, (v >> 8) & 0xff, v & 0xff};
}

// Whether the loaded library can serve this header (same major, minor at least ours).
inline bool abi_compatible() noexcept {
    AbiVersion v = abi_version();
    return v.major == NF_ABI_VERSION_MAJOR && v.minor >= NF_ABI_VERSION_MINOR;
}

inline std::string core_version() { return nf_core_version(); }

// ---------------------------------------------------------------- dtypes
enum class Dtype : nf_dtype {
    Int8 = NF_DTYPE_INT8,
    Uint8 = NF_DTYPE_UINT8,
    Int16 = NF_DTYPE_INT16,
    Uint16 = NF_DTYPE_UINT16,
    Int32 = NF_DTYPE_INT32,
    Uint32 = NF_DTYPE_UINT32,
    Int64 = NF_DTYPE_INT64,
    Float32 = NF_DTYPE_FLOAT32,
    Float64 = NF_DTYPE_FLOAT64,
};

inline std::string dtype_name(Dtype d) {
    const char *n = nf_dtype_name(static_cast<nf_dtype>(d));
    return n ? n : "";
}
inline size_t itemsize(Dtype d) noexcept { return nf_dtype_itemsize(static_cast<nf_dtype>(d)); }
inline Dtype parse_dtype(const std::string &name) {
    nf_dtype d = 0;
    detail::check(nf_dtype_parse(name.c_str(), &d));
    return static_cast<Dtype>(d);
}

// ---------------------------------------------------------------- hashing spec v1
inline std::string canonicalize(std::string_view json) {
    return detail::text([&](nf_buf *o) { return nf_canonicalize(detail::u8(json), json.size(), o); });
}
inline std::string format_number(double x) {
    return detail::text([&](nf_buf *o) { return nf_format_number(x, o); });
}
inline std::string blob_id(const void *data, size_t len) {
    return detail::text([&](nf_buf *o) { return nf_blob_id(static_cast<const uint8_t *>(data), len, o); });
}
inline std::string blob_id(std::string_view data) { return blob_id(data.data(), data.size()); }
// (id, size in bytes)
inline std::pair<std::string, uint64_t> blob_id_file(const std::string &path) {
    uint64_t size = 0;
    std::string id = detail::text([&](nf_buf *o) { return nf_blob_id_file(path.c_str(), o, &size); });
    return {id, size};
}
inline std::string pipeline_version_id(std::string_view spec_json) {
    return detail::text([&](nf_buf *o) { return nf_pipeline_version_id(detail::u8(spec_json), spec_json.size(), o); });
}
inline std::string chunk_id(Dtype dtype, const std::vector<uint64_t> &shape, const void *data, size_t len) {
    return detail::text([&](nf_buf *o) {
        return nf_chunk_id(static_cast<nf_dtype>(dtype), shape.data(), shape.size(), static_cast<const uint8_t *>(data), len, o);
    });
}
inline std::string prov_batch_id(std::string_view batch_json) {
    return detail::text([&](nf_buf *o) { return nf_prov_batch_id(detail::u8(batch_json), batch_json.size(), o); });
}
// Throws Error(NF_ERR_VERIFY) when the chain is broken.
inline std::vector<std::string> verify_prov_chain(std::string_view batches_json_array) {
    return detail::lines(detail::text([&](nf_buf *o) {
        return nf_verify_prov_chain(detail::u8(batches_json_array), batches_json_array.size(), o);
    }));
}
inline bool is_valid_id(const std::string &id) noexcept { return nf_is_valid_id(id.c_str()); }

// ---------------------------------------------------------------- hashing spec v2
inline bool is_valid_id_v2(const std::string &id) noexcept { return nf_is_valid_id_v2(id.c_str()); }
inline std::string audit_batch_id(std::string_view batch_json) {
    return detail::text([&](nf_buf *o) { return nf_audit_batch_id(detail::u8(batch_json), batch_json.size(), o); });
}
inline std::vector<std::string> verify_audit_chain(std::string_view batches_json_array) {
    return detail::lines(detail::text([&](nf_buf *o) {
        return nf_verify_audit_chain(detail::u8(batches_json_array), batches_json_array.size(), o);
    }));
}
inline std::string prov_node_hash(std::string_view record_json) {
    return detail::text([&](nf_buf *o) { return nf_prov_node_hash(detail::u8(record_json), record_json.size(), o); });
}
inline std::string consent_record_hash(std::string_view record_json) {
    return detail::text([&](nf_buf *o) { return nf_consent_record_hash(detail::u8(record_json), record_json.size(), o); });
}
inline std::vector<std::string> verify_consent_chain(std::string_view records_json_array) {
    return detail::lines(detail::text([&](nf_buf *o) {
        return nf_verify_consent_chain(detail::u8(records_json_array), records_json_array.size(), o);
    }));
}
inline std::string ruleset_content_sha256(std::string_view rules_json) {
    return detail::text([&](nf_buf *o) { return nf_ruleset_content_sha256(detail::u8(rules_json), rules_json.size(), o); });
}
inline std::string sweep_variant_label(const std::string &base_pv_id, std::string_view params_json) {
    return detail::text([&](nf_buf *o) {
        return nf_sweep_variant_label(base_pv_id.c_str(), detail::u8(params_json), params_json.size(), o);
    });
}
inline std::string training_subject_hash(const std::string &tenant_id, const std::string &subject_id) {
    return detail::text([&](nf_buf *o) { return nf_training_subject_hash(tenant_id.c_str(), subject_id.c_str(), o); });
}
inline std::string training_manifest_build(std::string_view args_json) {
    return detail::text([&](nf_buf *o) { return nf_training_manifest_build(detail::u8(args_json), args_json.size(), o); });
}
inline std::string training_manifest_digest(std::string_view manifest_json) {
    return detail::text([&](nf_buf *o) {
        return nf_training_manifest_digest(detail::u8(manifest_json), manifest_json.size(), o);
    });
}

using PublicKey = std::array<uint8_t, 32>;

inline bool verify_stream_chunk(const nf_stream_chunk_fields &fields, const std::vector<uint8_t> &signature,
                                const PublicKey &public_key) {
    bool ok = false;
    detail::check(nf_verify_stream_chunk(&fields, signature.data(), signature.size(), public_key.data(), &ok));
    return ok;
}
// Returns the canonical claims JSON; throws Error(NF_ERR_VERIFY) for an invalid token.
inline std::string verify_device_token(const std::string &token, const PublicKey &public_key, int64_t now_unix_s) {
    return detail::text([&](nf_buf *o) { return nf_verify_device_token(token.c_str(), public_key.data(), now_unix_s, o); });
}
inline bool verify_provb_signature(const std::string &batch_id, const std::vector<uint8_t> &signature,
                                   const PublicKey &public_key) {
    bool ok = false;
    detail::check(nf_verify_provb_signature(batch_id.c_str(), signature.data(), signature.size(), public_key.data(), &ok));
    return ok;
}
inline bool verify_anchor(std::string_view anchor_json, const PublicKey &public_key) {
    bool ok = false;
    detail::check(nf_verify_anchor(detail::u8(anchor_json), anchor_json.size(), public_key.data(), &ok));
    return ok;
}
inline bool verify_certificate(std::string_view certificate_json, const PublicKey &public_key) {
    bool ok = false;
    detail::check(nf_verify_certificate(detail::u8(certificate_json), certificate_json.size(), public_key.data(), &ok));
    return ok;
}

// ---------------------------------------------------------------- local recordings (read-only)
class Recording {
public:
    Recording(const std::string &root, const std::string &recording_id) {
        nf_recording *r = nullptr;
        detail::check(nf_recording_open(root.c_str(), recording_id.c_str(), &r));
        h_.reset(r);
        detail::check(nf_recording_get_info(r, &info_));
    }
    uint64_t n_samples() const noexcept { return info_.n_samples; }
    uint64_t n_channels() const noexcept { return info_.n_channels; }
    double sfreq() const noexcept { return info_.sfreq; }
    Dtype dtype() const noexcept { return static_cast<Dtype>(info_.dtype); }
    bool has_timestamps() const noexcept { return info_.has_timestamps; }
    std::string channel_name(uint64_t i) const {
        return detail::text([&](nf_buf *o) { return nf_recording_channel_name(h_.get(), i, o); });
    }
    std::string channel_unit(uint64_t i) const {
        return detail::text([&](nf_buf *o) { return nf_recording_channel_unit(h_.get(), i, o); });
    }
    // Raw little-endian samples [start, stop) x all channels.
    std::vector<uint8_t> read_bytes(uint64_t start, uint64_t stop) const {
        size_t need = 0;
        nf_status s = nf_recording_read(h_.get(), start, stop, nullptr, 0, &need);
        if (s != NF_OK && s != NF_ERR_BUFFER_TOO_SMALL) detail::check(s);
        std::vector<uint8_t> out(need);
        detail::check(nf_recording_read(h_.get(), start, stop, out.data(), out.size(), &need));
        return out;
    }
    // Typed samples; T must match dtype() in size (for example int16_t for Dtype::Int16).
    template <class T>
    std::vector<T> read(uint64_t start, uint64_t stop) const {
        if (sizeof(T) != itemsize(dtype())) throw Error(NF_ERR_INVALID_ARG, "element type does not match the recording dtype");
        std::vector<uint8_t> raw = read_bytes(start, stop);
        std::vector<T> out(raw.size() / sizeof(T));
        std::memcpy(out.data(), raw.data(), raw.size());
        return out;
    }
    // Physical values (stored * scale + offset per channel) as doubles, row-major (ABI 1.1).
    std::vector<double> read_physical(uint64_t start, uint64_t stop) const {
        size_t need = 0;
        nf_status s = nf_recording_read_f64(h_.get(), start, stop, nullptr, 0, &need);
        if (s != NF_OK && s != NF_ERR_BUFFER_TOO_SMALL) detail::check(s);
        std::vector<double> out(need);
        detail::check(nf_recording_read_f64(h_.get(), start, stop, out.data(), out.size(), &need));
        return out;
    }
    std::vector<double> timestamps(uint64_t start, uint64_t stop) const {
        size_t need = 0;
        nf_status s = nf_recording_read_timestamps(h_.get(), start, stop, nullptr, 0, &need);
        if (s != NF_OK && s != NF_ERR_BUFFER_TOO_SMALL) detail::check(s);
        std::vector<double> out(need);
        detail::check(nf_recording_read_timestamps(h_.get(), start, stop, out.data(), out.size(), &need));
        return out;
    }
    const nf_recording *get() const noexcept { return h_.get(); }

private:
    detail::Handle<nf_recording, nf_recording_free> h_;
    nf_recording_info info_{};
};

class Chunk {
public:
    explicit Chunk(nf_chunk *c) : h_(c) {}
    Dtype dtype() const noexcept { return static_cast<Dtype>(nf_chunk_dtype(h_.get())); }
    std::vector<uint64_t> shape() const {
        const uint64_t *s = nf_chunk_shape(h_.get());
        return std::vector<uint64_t>(s, s + nf_chunk_rank(h_.get()));
    }
    // Bytes owned by this chunk.
    const uint8_t *data(size_t *len) const noexcept { return nf_chunk_data(h_.get(), len); }
    std::vector<uint8_t> bytes() const {
        size_t len = 0;
        const uint8_t *p = data(&len);
        return std::vector<uint8_t>(p, p + len);
    }

private:
    detail::Handle<nf_chunk, nf_chunk_free> h_;
};

class ChunkCache {
public:
    ChunkCache(const std::string &root, uint64_t max_bytes) {
        nf_chunk_cache *c = nullptr;
        detail::check(nf_chunk_cache_open(root.c_str(), max_bytes, &c));
        h_.reset(c);
    }
    // Throws Error(NF_ERR_NOT_FOUND) on a miss.
    Chunk get(const std::string &chunk_id) const {
        nf_chunk *c = nullptr;
        detail::check(nf_chunk_cache_get(h_.get(), chunk_id.c_str(), &c));
        return Chunk(c);
    }
    uint64_t size() const {
        uint64_t n = 0;
        detail::check(nf_chunk_cache_size(h_.get(), &n));
        return n;
    }

private:
    detail::Handle<nf_chunk_cache, nf_chunk_cache_free> h_;
};

// ---------------------------------------------------------------- provenance recorder
class ProvRecorder {
public:
    struct Batch {
        uint64_t seq;
        std::string id;
        std::string canonical;  // upload bytes (pending() only)
    };
    ProvRecorder(const std::string &dir, const std::string &chain) {
        nf_prov_recorder *r = nullptr;
        detail::check(nf_prov_recorder_open(dir.c_str(), chain.c_str(), &r));
        h_.reset(r);
    }
    Batch record(std::string_view records_json) {
        uint64_t seq = 0;
        std::string id = detail::text([&](nf_buf *o) {
            return nf_prov_recorder_record(h_.get(), detail::u8(records_json), records_json.size(), &seq, o);
        });
        return {seq, id, {}};
    }
    size_t size() const {
        size_t n = 0;
        detail::check(nf_prov_recorder_len(h_.get(), &n));
        return n;
    }
    std::vector<Batch> pending() const {
        size_t n = 0;
        detail::check(nf_prov_recorder_pending_count(h_.get(), &n));
        std::vector<Batch> out;
        for (size_t i = 0; i < n; i++) {
            detail::Buf id, canon;
            uint64_t seq = 0;
            detail::check(nf_prov_recorder_pending(h_.get(), i, &seq, id.out(), canon.out()));
            out.push_back({seq, id.str(), canon.str()});
        }
        return out;
    }
    void mark_synced(uint64_t seq) { detail::check(nf_prov_recorder_mark_synced(h_.get(), seq)); }

private:
    detail::Handle<nf_prov_recorder, nf_prov_recorder_free> h_;
};

// ---------------------------------------------------------------- streaming
class DeviceKey {
public:
    static DeviceKey generate() {
        nf_device_key *k = nullptr;
        detail::check(nf_device_key_generate(&k));
        return DeviceKey(k);
    }
    static DeviceKey from_seed(const std::vector<uint8_t> &seed) {
        nf_device_key *k = nullptr;
        detail::check(nf_device_key_from_seed(seed.data(), seed.size(), &k));
        return DeviceKey(k);
    }
    // Windows only (DPAPI); NF_ERR_UNSUPPORTED elsewhere.
    static DeviceKey open_sealed(const std::string &path) {
        nf_device_key *k = nullptr;
        detail::check(nf_device_key_open_sealed(path.c_str(), &k));
        return DeviceKey(k);
    }
    PublicKey public_key() const {
        PublicKey pk{};
        detail::check(nf_device_key_public_key(h_.get(), pk.data()));
        return pk;
    }
    std::string token(const std::string &tenant_id, const std::string &device_id, const std::string &stream_id,
                      uint64_t lifetime_s = 300) const {
        return detail::text([&](nf_buf *o) {
            return nf_device_key_token(h_.get(), tenant_id.c_str(), device_id.c_str(), stream_id.c_str(), lifetime_s, o);
        });
    }
    const nf_device_key *get() const noexcept { return h_.get(); }

private:
    explicit DeviceKey(nf_device_key *k) : h_(k) {}
    detail::Handle<nf_device_key, nf_device_key_free> h_;
};

class Wal {
public:
    // Persistent key required (ABI 1.2): key32 (32 bytes from an OS keystore) or dpapi_key_path
    // (Windows). Passing neither throws Error(NF_ERR_INVALID_ARG); use Wal::open_ephemeral_for_testing in tests only.
    Wal(const std::string &dir, const std::string &stream_id, const std::vector<uint8_t> &key32 = {},
        const std::string &dpapi_key_path = {}, bool fsync = true) {
        if (!key32.empty() && key32.size() != 32) throw Error(NF_ERR_INVALID_ARG, "WAL key must be 32 bytes");
        nf_wal *w = nullptr;
        detail::check(nf_wal_open(dir.c_str(), stream_id.c_str(), key32.empty() ? nullptr : key32.data(),
                                  dpapi_key_path.empty() ? nullptr : dpapi_key_path.c_str(), fsync, &w));
        h_.reset(w);
    }
    // FOR TESTS AND THROWAWAY SESSIONS ONLY: records are unreadable after the process ends.
    static Wal open_ephemeral_for_testing(const std::string &dir, const std::string &stream_id, bool fsync = false) {
        nf_wal *w = nullptr;
        detail::check(nf_wal_open_ephemeral(dir.c_str(), stream_id.c_str(), fsync, &w));
        return Wal(w);
    }
    size_t size() const {
        size_t n = 0;
        detail::check(nf_wal_len(h_.get(), &n));
        return n;
    }
    const nf_wal *get() const noexcept { return h_.get(); }

private:
    explicit Wal(nf_wal *w) : h_(w) {}
    detail::Handle<nf_wal, nf_wal_free> h_;
};

class StreamWriter {
public:
    StreamWriter(const std::string &stream_id, Dtype dtype, uint32_t n_channels, uint32_t chunk_samples,
                 const DeviceKey &key, const Wal &wal) {
        nf_stream_writer *w = nullptr;
        detail::check(nf_stream_writer_new(stream_id.c_str(), static_cast<nf_dtype>(dtype), n_channels, chunk_samples,
                                           key.get(), wal.get(), &w));
        h_.reset(w);
    }
    // samples: n x n_channels values (row-major) of the writer dtype; one timestamp per sample.
    template <class T>
    size_t push(const std::vector<T> &samples, const std::vector<double> &timestamps) {
        size_t chunks = 0;
        detail::check(nf_stream_writer_push(h_.get(), reinterpret_cast<const uint8_t *>(samples.data()),
                                            samples.size() * sizeof(T), timestamps.data(), timestamps.size(), &chunks));
        return chunks;
    }
    void add_clock_offset(double collection_time, double offset) {
        detail::check(nf_stream_writer_add_clock_offset(h_.get(), collection_time, offset));
    }
    void add_local_clock(double lsl_time, double monotonic_time) {
        detail::check(nf_stream_writer_add_local_clock(h_.get(), lsl_time, monotonic_time));
    }
    bool flush() {
        bool wrote = false;
        detail::check(nf_stream_writer_flush(h_.get(), &wrote));
        return wrote;
    }
    uint64_t next_seq() const {
        uint64_t s = 0;
        detail::check(nf_stream_writer_next_seq(h_.get(), &s));
        return s;
    }
    nf_writer_stats stats() const {
        nf_writer_stats s{};
        detail::check(nf_stream_writer_get_stats(h_.get(), &s));
        return s;
    }

private:
    detail::Handle<nf_stream_writer, nf_stream_writer_free> h_;
};

// Result of one transport call: code 0 with the response bytes, or a gRPC status with a message.
struct RpcResult {
    int32_t code = 0;
    std::string bytes;
};

// Implement this with your gRPC stack (nf.ingest.v1.IngestService). Exceptions become UNKNOWN (2).
// Thread contract (as nf_ingest_transport): methods run on the thread calling Sender::run, state or
// finish; state/finish from another thread while run() is active call them concurrently.
class IngestTransport {
public:
    virtual ~IngestTransport() = default;
    virtual RpcResult get_stream_state(const std::string &request, const std::string &authorization, double timeout_s) = 0;
    virtual RpcResult stream_chunks(const std::vector<std::string> &chunks, const std::string &authorization,
                                    double timeout_s) = 0;
    virtual RpcResult finish_stream(const std::string &request, const std::string &authorization, double timeout_s) = 0;

    nf_ingest_transport c_table() noexcept { return {this, &unary<&IngestTransport::get_stream_state>, &chunks_cb, &unary<&IngestTransport::finish_stream>}; }

private:
    static int32_t reply(nf_reply *r, const RpcResult &res) noexcept {
        nf_reply_set(r, detail::u8(res.bytes), res.bytes.size());
        return res.code;
    }
    template <RpcResult (IngestTransport::*M)(const std::string &, const std::string &, double)>
    static int32_t unary(void *user, const uint8_t *req, size_t len, const char *auth, double timeout_s, nf_reply *r) noexcept {
        try {
            auto *self = static_cast<IngestTransport *>(user);
            return reply(r, (self->*M)(std::string(reinterpret_cast<const char *>(req), len), auth, timeout_s));
        } catch (const std::exception &e) {
            return reply(r, {2, e.what()});
        } catch (...) {
            return reply(r, {2, "unknown C++ exception"});
        }
    }
    static int32_t chunks_cb(void *user, const nf_bytes *chunks, size_t n, const char *auth, double timeout_s, nf_reply *r) noexcept {
        try {
            std::vector<std::string> v;
            v.reserve(n);
            for (size_t i = 0; i < n; i++) v.emplace_back(reinterpret_cast<const char *>(chunks[i].data), chunks[i].len);
            return reply(r, static_cast<IngestTransport *>(user)->stream_chunks(v, auth, timeout_s));
        } catch (const std::exception &e) {
            return reply(r, {2, e.what()});
        } catch (...) {
            return reply(r, {2, "unknown C++ exception"});
        }
    }
};

struct StreamState {
    std::string stream_id;
    uint64_t next_seq = 0;
    uint64_t n_samples = 0;
    std::string state;
    bool suspect = false;
};

class Sender {
public:
    Sender(const std::string &tenant_id, const std::string &device_id, const std::string &stream_id, const DeviceKey &key,
           const Wal &wal, const nf_sender_config *config = nullptr) {
        nf_sender *s = nullptr;
        detail::check(nf_sender_new(tenant_id.c_str(), device_id.c_str(), stream_id.c_str(), key.get(), wal.get(), config, &s));
        h_.reset(s);
    }
    static nf_sender_config default_config() {
        nf_sender_config c{};
        detail::check(nf_sender_config_default(&c));
        return c;
    }
    // Blocks until stop(); run it on its own thread.
    void run(IngestTransport &t) {
        nf_ingest_transport c = t.c_table();
        detail::check(nf_sender_run(h_.get(), &c));
    }
    void stop() { detail::check(nf_sender_stop(h_.get())); }
    void reset() { detail::check(nf_sender_reset(h_.get())); }
    StreamState state(IngestTransport &t) { return call(t, nf_sender_state); }
    // Close the stream (FinishStream). Does NOT upload: throws Error(NF_ERR_INVALID_ARG) without
    // closing while the WAL still holds chunks or run() is active, and after closing if a writer
    // added chunks meanwhile. Use drain_and_finish() unless you drained yourself.
    StreamState finish(IngestTransport &t) { return call(t, nf_sender_finish); }

    // Stop writing first. Flushes `writer`, runs the sender on a helper thread until `wal` is empty
    // (or `timeout_s` passes, or the sender hits a fatal error), stops it, then finishes. If chunks
    // are still unsent it throws Error(NF_ERR_TRANSPORT) and leaves the stream OPEN, so nothing is
    // lost; call it again later.
    StreamState drain_and_finish(IngestTransport &t, StreamWriter &writer, const Wal &wal, double timeout_s = 60.0) {
        writer.flush();
        reset();
        std::exception_ptr failed;  // written by the runner, read only after join()
        std::atomic<bool> ended{false};
        std::thread runner([&] {
            try {
                run(t);
            } catch (...) {
                failed = std::current_exception();
            }
            ended = true;
        });
        auto deadline = std::chrono::steady_clock::now() + std::chrono::duration<double>(timeout_s);
        while (wal.size() > 0 && std::chrono::steady_clock::now() < deadline && !stats().fatal && !ended)
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        stop();
        runner.join();
        if (failed) std::rethrow_exception(failed);
        size_t left = wal.size();
        if (left > 0)
            throw Error(NF_ERR_TRANSPORT, std::to_string(left) + " chunks still unsent; the stream was NOT closed");
        return finish(t);
    }
    nf_sender_stats stats() const {
        nf_sender_stats s{};
        detail::check(nf_sender_get_stats(h_.get(), &s));
        return s;
    }

private:
    using StateFn = nf_status (*)(const nf_sender *, const nf_ingest_transport *, nf_stream_state *);
    StreamState call(IngestTransport &t, StateFn f) {
        nf_ingest_transport c = t.c_table();
        nf_stream_state s{};
        nf_status st = f(h_.get(), &c, &s);
        StreamState out;
        if (st == NF_OK) {
            out = {std::string(reinterpret_cast<const char *>(s.stream_id.data), s.stream_id.len), s.next_seq, s.n_samples,
                   std::string(reinterpret_cast<const char *>(s.state.data), s.state.len), s.suspect};
        }
        nf_stream_state_free(&s);
        detail::check(st);
        return out;
    }
    detail::Handle<nf_sender, nf_sender_free> h_;
};

// ---------------------------------------------------------------- API client
struct HttpRequest {
    std::string method, url;
    std::vector<std::pair<std::string, std::string>> headers;
    std::string body;
    double timeout_s = 0;
};

struct HttpResponse {
    uint16_t status = 0;
    std::vector<std::pair<std::string, std::string>> headers;
    std::string body;
};

// Your HTTP stack: return the response for any status; throw for a transport failure.
using HttpSend = std::function<HttpResponse(const HttpRequest &)>;
// Your token store: return a bearer token (refresh = true after a 401); throw on failure.
using TokenFn = std::function<std::string(bool refresh)>;

inline void check_base_url(const std::string &url) { detail::check(nf_check_base_url(url.c_str())); }

class ApiClient {
public:
    ApiClient(const std::string &base_url, HttpSend send, TokenFn tokens, double timeout_s = 30.0,
              uint32_t max_attempts = 5, const std::string &user_agent = {})
        : cb_(new Callbacks{std::move(send), std::move(tokens)}) {
        nf_http_transport t{cb_.get(), &send_cb};
        nf_token_source k{cb_.get(), &token_cb};
        nf_api_client *c = nullptr;
        detail::check(nf_api_client_new(base_url.c_str(), &t, &k, timeout_s, max_attempts,
                                        user_agent.empty() ? nullptr : user_agent.c_str(), &c));
        h_.reset(c);
    }
    // 2xx responses; any other status throws Error(NF_ERR_HTTP) with the problem+json in detail().
    HttpResponse request(const std::string &method, const std::string &path,
                         const std::vector<std::pair<std::string, std::string>> &query = {},
                         const std::vector<std::pair<std::string, std::string>> &headers = {},
                         std::string_view body = {}) const {
        auto pairs = [](const std::vector<std::pair<std::string, std::string>> &v) {
            std::vector<nf_header> out;
            for (const auto &p : v) out.push_back({p.first.c_str(), p.second.c_str()});
            return out;
        };
        std::vector<nf_header> q = pairs(query), h = pairs(headers);
        nf_http_response *r = nullptr;
        detail::check(nf_api_client_request(h_.get(), method.c_str(), path.c_str(), q.data(), q.size(), h.data(), h.size(),
                                            detail::u8(body), body.size(), &r));
        detail::Handle<nf_http_response, nf_http_response_free> resp(r);
        HttpResponse out;
        out.status = nf_http_response_status(r);
        for (size_t i = 0, n = nf_http_response_header_count(r); i < n; i++) {
            const char *name = nullptr, *value = nullptr;
            detail::check(nf_http_response_header(r, i, &name, &value));
            out.headers.emplace_back(name, value);
        }
        size_t len = 0;
        const uint8_t *b = nf_http_response_body(r, &len);
        out.body.assign(reinterpret_cast<const char *>(b), len);
        return out;
    }

private:
    // Thread contract (as nf_http_transport / nf_token_source): send and tokens run on the thread
    // calling request(), concurrently when the client is shared between threads, so both must be
    // thread-safe then.
    struct Callbacks {
        HttpSend send;
        TokenFn tokens;
    };
    static int32_t send_cb(void *user, const nf_http_request *req, nf_http_reply *reply) noexcept {
        try {
            HttpRequest r;
            r.method = req->method;
            r.url = req->url;
            for (size_t i = 0; i < req->n_headers; i++) r.headers.emplace_back(req->headers[i].name, req->headers[i].value);
            r.body.assign(reinterpret_cast<const char *>(req->body), req->body_len);
            r.timeout_s = req->timeout_s;
            HttpResponse resp = static_cast<Callbacks *>(user)->send(r);
            nf_http_reply_set_status(reply, resp.status);
            for (const auto &h : resp.headers) nf_http_reply_add_header(reply, h.first.c_str(), h.second.c_str());
            nf_http_reply_set_body(reply, detail::u8(resp.body), resp.body.size());
            return 0;
        } catch (const std::exception &e) {
            nf_http_reply_set_body(reply, detail::u8(e.what()), std::strlen(e.what()));
            return 1;
        } catch (...) {
            return 1;
        }
    }
    static int32_t token_cb(void *user, bool refresh, nf_reply *reply) noexcept {
        try {
            std::string t = static_cast<Callbacks *>(user)->tokens(refresh);
            nf_reply_set(reply, detail::u8(t), t.size());
            return 0;
        } catch (const std::exception &e) {
            nf_reply_set(reply, detail::u8(e.what()), std::strlen(e.what()));
            return 1;
        } catch (...) {
            return 1;
        }
    }
    std::unique_ptr<Callbacks> cb_;  // declared before h_: outlives the client handle
    detail::Handle<nf_api_client, nf_api_client_free> h_;
};

}  // namespace neuroforge

#endif  // NEUROFORGE_HPP
