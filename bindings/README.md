# bindings

Language bindings over `core/nf-core` (BLUEPRINT §5, ADR 0007). No SDK logic lives here; each binding converts types and forwards to the core.

| Directory | What | Consumers |
|---|---|---|
| `python/` | PyO3 extension `neuroforge._native` + the idiomatic `neuroforge` package | Python SDK (PyPI) |
| `c/` | Stable C ABI (`neuroforge.dll` / `libneuroforge.so`, static library) + generated header `c/include/neuroforge.h` (ADR 0013) | C, C++, Unity (P/Invoke), Unreal |
| `cpp/` | Header-only C++17 RAII wrapper `cpp/include/neuroforge.hpp` over the C ABI | C++ and Unreal |

Data flows device -> SDK -> platform only. No binding exposes anything that sends data or instructions to acquisition hardware; `tools/hw-guard` scans this directory.
