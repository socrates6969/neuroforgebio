// NfAbi.h: engine-free ABI compatibility rule (neuroforge.h), shared by FNeuroForgeModule and the
// MSVC tests.
#ifndef NF_ENGINE_ABI_H
#define NF_ENGINE_ABI_H

#include <cstdint>

#include "neuroforge.h"

namespace nf {
namespace engine {

// A packed `major << 16 | minor << 8 | patch` library version is usable with the bundled header
// when the majors are equal and the library minor is at least the header's.
constexpr bool abi_compatible(uint32_t packed, uint32_t header_major = NF_ABI_VERSION_MAJOR,
                              uint32_t header_minor = NF_ABI_VERSION_MINOR) {
    return (packed >> 16) == header_major && ((packed >> 8) & 0xffu) >= header_minor;
}

}  // namespace engine
}  // namespace nf

#endif  // NF_ENGINE_ABI_H
