// NfStreamState.h: engine-free per-frame state for a replayed stream: the newest value per channel,
// the current sample index and name lookups. Game-thread only; no locking. Unit-tested with MSVC.
#ifndef NF_ENGINE_STREAM_STATE_H
#define NF_ENGINE_STREAM_STATE_H

#include <cstdint>
#include <limits>
#include <string>
#include <unordered_map>
#include <vector>

#include "NfReplay.h"

namespace nf {
namespace engine {

class StreamState {
public:
    void reset(const std::vector<std::string> &names, double sample_rate) {
        names_ = names;
        index_.clear();
        for (size_t i = 0; i < names_.size(); i++) index_.emplace(names_[i], i);
        latest_.assign(names_.size(), 0.0f);
        sample_rate_ = sample_rate;
        current_sample_ = -1;
        blocks_ = 0;
    }

    // Fold one block into the state (newest row wins).
    void apply(const SampleBlock &b) {
        if (b.rows == 0 || b.channels != latest_.size()) return;
        const float *last = b.data.data() + static_cast<size_t>(b.rows - 1) * b.channels;
        latest_.assign(last, last + b.channels);
        current_sample_ = static_cast<int64_t>(b.first_sample + b.rows - 1);
        blocks_++;
    }

    // Index of a channel name, or -1.
    int channel_index(const std::string &name) const {
        auto it = index_.find(name);
        return it == index_.end() ? -1 : static_cast<int>(it->second);
    }

    // Newest value of a channel; NaN for an unknown channel or before the first block.
    float value(const std::string &name) const {
        int i = channel_index(name);
        if (i < 0 || current_sample_ < 0) return (std::numeric_limits<float>::quiet_NaN)();
        return latest_[static_cast<size_t>(i)];
    }

    const std::vector<float> &latest() const { return latest_; }
    const std::vector<std::string> &names() const { return names_; }
    int64_t current_sample() const { return current_sample_; }
    double sample_rate() const { return sample_rate_; }
    uint64_t blocks() const { return blocks_; }

private:
    std::vector<std::string> names_;
    std::unordered_map<std::string, size_t> index_;
    std::vector<float> latest_;
    double sample_rate_ = 0;
    int64_t current_sample_ = -1;
    uint64_t blocks_ = 0;
};

}  // namespace engine
}  // namespace nf

#endif  // NF_ENGINE_STREAM_STATE_H
