# neuroforge (Python SDK)

Status: **in development**, not published. Illustrative API, subject to change.

The Python SDK on the shared Rust core `nf-core` (PyO3, abi3 for Python 3.12+). Hashing, canonical
JSON, retries, the encrypted stream buffer and the offline provenance recorder run in nf-core; this
package is the idiomatic layer on top.

```python
import neuroforge as nf
rec = nf.open("sub-01_task-motor_eeg.edf")
run = nf.pipelines.get("eeg-basic@1.0.0").run(rec)
print(run.provenance.id)          # every parameter, version and input hash
```

| Module | What |
|---|---|
| `nf.open`, `nf.recordings` | local files (hashed client-side) and platform recordings (`read`, `to_mne`) |
| `nf.pipelines` | `get(ref)`, `publish(spec)`, `Pipeline.run(rec)`; the pipeline ID is recomputed locally |
| `nf.runs` | `Run.wait()`, `Run.record`, `Run.provenance` (`lineage()`, `export("prov-json")`) |
| `nf.streaming` | device keys, `open_stream`, `Stream.push`, `run_acquisition` (gRPC extra) |
| `nf.lsl` | LSL **inlet** bridge with clock-offset capture (LSL extra) |
| `nf.local` | offline provenance recorder, Zarr v3 `nf-signal/1` store, chunk cache |
| `nf.canonical` | NF-CJSON and content IDs |

Stream chunks are cut and signed by time: a `Stream` takes the nominal rate `sfreq` and
`chunk_ms` (default 100 ms, minimum 20 ms, enforced in nf-core, P7.7 R1). The partial chunk
written by `drain` ends the stream. Streams without a nominal rate (markers) pass
`irregular=True` with `chunk_samples`.

Extras: `neuroforge[stream]` (grpcio), `neuroforge[lsl]` (pylsl), `neuroforge[mne]` (MNE-Python).

Nothing in this package sends anything to acquisition hardware (SEC-090/091).

## Development (dev PC: debug builds only)

```sh
VIRTUAL_ENV=.venv CARGO_BUILD_JOBS=1 .venv/Scripts/maturin develop --uv -m bindings/python/Cargo.toml
.venv/Scripts/python -m pytest bindings/python/tests
```

Release wheels (abi3; Windows, macOS, Linux) are built in CI only: `.github/workflows/sdk-wheels.yml`
(manual dispatch, no publish step). Release notes follow `bindings/python/RELEASE-NOTES-TEMPLATE.md`,
which states the end-of-support date (SEC-134).
