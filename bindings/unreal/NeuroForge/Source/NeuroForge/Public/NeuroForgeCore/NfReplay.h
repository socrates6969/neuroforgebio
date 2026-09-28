// NfReplay.h: engine-free replay of a NeuroForge recording on a background thread (C++17).
//
// No Unreal headers: this file is compiled and unit-tested with plain MSVC /W4 /WX
// (bindings/unreal/tests). The UE component (NeuroForgeStreamComponent) is a thin shell around it.
//
// Threading: the worker thread is the only thread that touches the Recording while it runs;
// try_pop may be called from any single consumer thread (in Unreal: the game thread).
// Data flows recording -> game only; nothing here sends anything to a device.
#ifndef NF_ENGINE_REPLAY_H
#define NF_ENGINE_REPLAY_H

#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <deque>
#include <exception>
#include <limits>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "neuroforge.hpp"

namespace nf {
namespace engine {

// A block of consecutive samples, row-major [rows][channels], as physical values in the channel units.
struct SampleBlock {
    uint64_t first_sample = 0;
    uint32_t rows = 0;
    uint32_t channels = 0;
    std::vector<float> data;
    double time_s = 0;  // first_sample / sample rate
    uint32_t loop = 0;  // 0 on the first pass, +1 per wrap of a looping replay
    float at(uint32_t row, uint32_t channel) const { return data[static_cast<size_t>(row) * channels + channel]; }
};

enum class Backpressure {
    DropOldest,  // real time: drop the oldest queued block, memory stays bounded
    Block,       // lossless: wait for the consumer
};

struct ReplayOptions {
    double speed = 1.0;  // 1 = real time; +infinity = unpaced
    bool loop = false;
    uint32_t block_samples = 32;
    size_t max_queued = 256;
    Backpressure backpressure = Backpressure::DropOldest;
};

// Convert `rows` x `channels` little-endian values of `dtype` to float.
inline void to_float(neuroforge::Dtype dtype, const uint8_t *src, size_t n, float *dst) {
    using D = neuroforge::Dtype;
    auto conv = [&](auto tag) {
        using T = decltype(tag);
        for (size_t i = 0; i < n; i++) {
            T v;
            std::memcpy(&v, src + i * sizeof(T), sizeof(T));
            dst[i] = static_cast<float>(v);
        }
    };
    switch (dtype) {
        case D::Int8: conv(int8_t{}); break;
        case D::Uint8: conv(uint8_t{}); break;
        case D::Int16: conv(int16_t{}); break;
        case D::Uint16: conv(uint16_t{}); break;
        case D::Int32: conv(int32_t{}); break;
        case D::Uint32: conv(uint32_t{}); break;
        case D::Int64: conv(int64_t{}); break;
        case D::Float32: conv(float{}); break;
        case D::Float64: conv(double{}); break;
        default: throw neuroforge::Error(NF_ERR_INVALID_ARG, "unknown dtype code " + std::to_string(static_cast<int>(dtype)));
    }
}

// Most stored bytes one native read may cover. The core refuses single reads over 1 GiB (ABI 1.2
// hardening), so long reads are split well below that.
constexpr uint64_t kMaxStoredBytesPerCall = 64ull << 20;

inline uint64_t rows_per_call(const neuroforge::Recording &rec, uint64_t max_bytes = kMaxStoredBytesPerCall) {
    uint64_t row_bytes = rec.n_channels() * neuroforge::itemsize(rec.dtype());
    return row_bytes == 0 ? 1 : (std::max<uint64_t>)(1, max_bytes / row_bytes);
}

// Read rows [start, stop) of a recording as PHYSICAL values (stored * scale + offset per channel,
// in the channel units; ABI 1.1 nf_recording_read_f64), narrowed to float, row-major.
inline std::vector<float> read_floats(const neuroforge::Recording &rec, uint64_t start, uint64_t stop,
                                      uint64_t max_bytes_per_call = kMaxStoredBytesPerCall) {
    if (stop > rec.n_samples()) stop = rec.n_samples();
    if (start >= stop) return {};
    const uint64_t ch = rec.n_channels(), step = rows_per_call(rec, max_bytes_per_call);
    std::vector<float> out;
    out.reserve(static_cast<size_t>((stop - start) * ch));
    for (uint64_t a = start; a < stop; a += step) {
        uint64_t b = (std::min)(stop, a + step);
        std::vector<double> phys = rec.read_physical(a, b);
        if (phys.size() != (b - a) * ch) throw neuroforge::Error(NF_ERR_CORRUPT, "read returned an unexpected value count");
        for (double v : phys) out.push_back(static_cast<float>(v));
    }
    return out;
}

// Read rows [start, stop) as STORED values (no scale/offset) converted to float.
inline std::vector<float> read_stored_floats(const neuroforge::Recording &rec, uint64_t start, uint64_t stop,
                                             uint64_t max_bytes_per_call = kMaxStoredBytesPerCall) {
    if (stop > rec.n_samples()) stop = rec.n_samples();
    if (start >= stop) return {};
    const uint64_t ch = rec.n_channels(), step = rows_per_call(rec, max_bytes_per_call);
    std::vector<float> out(static_cast<size_t>((stop - start) * ch));
    for (uint64_t a = start; a < stop; a += step) {
        uint64_t b = (std::min)(stop, a + step);
        std::vector<uint8_t> raw = rec.read_bytes(a, b);
        size_t n = static_cast<size_t>((b - a) * ch);
        if (raw.size() != n * neuroforge::itemsize(rec.dtype()))
            throw neuroforge::Error(NF_ERR_CORRUPT, "read returned an unexpected byte count");
        to_float(rec.dtype(), raw.data(), n, out.data() + static_cast<size_t>((a - start) * ch));
    }
    return out;
}

class ReplayWorker {
public:
    ReplayWorker(neuroforge::Recording rec, ReplayOptions opt) : rec_(std::move(rec)), opt_(opt) {
        if (!(opt_.speed > 0)) throw neuroforge::Error(NF_ERR_INVALID_ARG, "speed must be > 0");
        if (opt_.block_samples == 0) throw neuroforge::Error(NF_ERR_INVALID_ARG, "block_samples must be > 0");
        if (opt_.max_queued == 0) throw neuroforge::Error(NF_ERR_INVALID_ARG, "max_queued must be > 0");
        if (!unpaced() && !(rec_.sfreq() > 0))
            throw neuroforge::Error(NF_ERR_INVALID_ARG, "recording has no positive sample rate; use an infinite speed");
        for (uint64_t i = 0; i < rec_.n_channels(); i++) names_.push_back(rec_.channel_name(i));
    }
    ReplayWorker(const ReplayWorker &) = delete;
    ReplayWorker &operator=(const ReplayWorker &) = delete;
    ~ReplayWorker() { stop(); }

    void start() {
        if (thread_.joinable() || started_) throw neuroforge::Error(NF_ERR_INVALID_ARG, "already started");
        started_ = true;
        thread_ = std::thread([this] { run(); });
    }

    // Ask the worker to stop and join it. Safe to call more than once and from the destructor.
    void stop() {
        {
            std::lock_guard<std::mutex> g(m_);
            stop_ = true;
        }
        cv_.notify_all();
        if (thread_.joinable()) thread_.join();
    }

    bool try_pop(SampleBlock &out) {
        std::lock_guard<std::mutex> g(m_);
        if (q_.empty()) return false;
        out = std::move(q_.front());
        q_.pop_front();
        cv_.notify_all();
        return true;
    }

    bool running() const { return started_ && !finished_.load(); }
    bool completed() const { return completed_.load(); }
    uint64_t dropped_blocks() const { return dropped_.load(); }
    size_t queued() const {
        std::lock_guard<std::mutex> g(m_);
        return q_.size();
    }
    std::optional<std::string> error() const {
        std::lock_guard<std::mutex> g(m_);
        return error_;
    }

    const std::vector<std::string> &channel_names() const { return names_; }
    double sample_rate() const { return rec_.sfreq(); }
    uint64_t n_samples() const { return rec_.n_samples(); }
    uint32_t n_channels() const { return static_cast<uint32_t>(rec_.n_channels()); }
    const ReplayOptions &options() const { return opt_; }

private:
    bool unpaced() const { return opt_.speed == (std::numeric_limits<double>::infinity)(); }

    void run() {
        try {
            run_inner();
        } catch (const std::exception &e) {
            std::lock_guard<std::mutex> g(m_);
            error_ = e.what();
        } catch (...) {
            std::lock_guard<std::mutex> g(m_);
            error_ = "unknown exception in replay worker";
        }
        finished_ = true;
    }

    void run_inner() {
        using clock = std::chrono::steady_clock;
        const uint64_t n = rec_.n_samples();
        const uint32_t ch = n_channels();
        const bool paced = !unpaced();
        const double rate = paced ? rec_.sfreq() * opt_.speed : 0.0;  // samples per wall-clock second
        uint64_t pos = 0;
        uint32_t loop = 0;
        auto pass_start = clock::now();

        for (;;) {
            if (stopping()) return;
            if (pos >= n) {
                if (!opt_.loop || n == 0) {
                    completed_ = true;
                    return;
                }
                pos = 0;
                loop++;
                // The next pass starts where this one ended on the timeline (no drift per loop).
                if (paced) pass_start += std::chrono::duration_cast<clock::duration>(std::chrono::duration<double>(n / rate));
            }
            uint32_t rows = static_cast<uint32_t>((std::min<uint64_t>)(opt_.block_samples, n - pos));  // parens: windows.h min macro
            if (paced) {
                // The block is due when its last row has "played".
                auto due = pass_start + std::chrono::duration_cast<clock::duration>(std::chrono::duration<double>((pos + rows) / rate));
                std::unique_lock<std::mutex> lk(m_);
                if (cv_.wait_until(lk, due, [this] { return stop_; })) return;
            }
            SampleBlock b;
            b.first_sample = pos;
            b.rows = rows;
            b.channels = ch;
            b.data = read_floats(rec_, pos, pos + rows);
            b.time_s = rec_.sfreq() > 0 ? static_cast<double>(pos) / rec_.sfreq() : 0.0;
            b.loop = loop;
            if (!push(std::move(b))) return;
            pos += rows;
        }
    }

    bool stopping() {
        std::lock_guard<std::mutex> g(m_);
        return stop_;
    }

    // Returns false when stopping.
    bool push(SampleBlock &&b) {
        std::unique_lock<std::mutex> lk(m_);
        if (opt_.backpressure == Backpressure::Block) {
            cv_.wait(lk, [this] { return stop_ || q_.size() < opt_.max_queued; });
            if (stop_) return false;
        } else if (q_.size() >= opt_.max_queued) {
            q_.pop_front();
            dropped_++;
        }
        q_.push_back(std::move(b));
        return true;
    }

    neuroforge::Recording rec_;
    ReplayOptions opt_;
    std::vector<std::string> names_;
    mutable std::mutex m_;
    std::condition_variable cv_;
    std::deque<SampleBlock> q_;
    std::optional<std::string> error_;
    bool stop_ = false;
    bool started_ = false;
    std::atomic<bool> finished_{false};
    std::atomic<bool> completed_{false};
    std::atomic<uint64_t> dropped_{0};
    std::thread thread_;
};

}  // namespace engine
}  // namespace nf

#endif  // NF_ENGINE_REPLAY_H
