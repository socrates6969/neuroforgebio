//! `neuroforge._native`: thin PyO3 layer over nf-core. The idiomatic API lives in Python
//! (`bindings/python/python/neuroforge`); this module only converts types, releases the GIL
//! around IO and crypto, and calls back into Python for the injected transports.

use std::path::PathBuf;
use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use nf_core::cache::ChunkCache as CoreCache;
use nf_core::cjson;
use nf_core::http::{self, ApiClient as CoreClient, HttpTransport, TokenSource};
use nf_core::ids::{self, Dtype};
use nf_core::model::ProvRecord;
use nf_core::prov::ProvRecorder as CoreProv;
use nf_core::stream::keystore::{DpapiKey, EphemeralKey, KeyProvider, StaticKey};
use nf_core::stream::sender::{
    self, IngestTransport, RpcError, Sender as CoreSender, SenderConfig,
};
use nf_core::stream::sign::{self, DeviceKey as CoreKey};
use nf_core::stream::wal::{Wal as CoreWal, WalError};
use nf_core::stream::writer::{StreamConfig, StreamWriter as CoreWriter, WriterError};
use nf_core::zarr::{self, FsStore};
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};

create_exception!(
    _native,
    CanonicalError,
    PyValueError,
    "Input cannot be canonicalised (hashing spec v1)."
);
create_exception!(
    _native,
    WalCorrupt,
    PyException,
    "A write-ahead record does not authenticate."
);
create_exception!(
    _native,
    CoreError,
    PyException,
    "An nf-core operation failed."
);
create_exception!(
    _native,
    ApiError,
    PyException,
    "args = (kind, status, message, problem_json)"
);

fn canon_err(e: cjson::CanonError) -> PyErr {
    CanonicalError::new_err(e.to_string())
}
fn core_err(e: impl std::fmt::Display) -> PyErr {
    CoreError::new_err(e.to_string())
}
fn dtype(s: &str) -> PyResult<Dtype> {
    Dtype::parse(s).map_err(canon_err)
}
/// (dtype, shape, little-endian bytes)
type ArrayOut<'py> = (String, Vec<u64>, Bound<'py, PyBytes>);
/// (status, headers, body)
type HttpOut<'py> = (u16, Vec<(String, String)>, Bound<'py, PyBytes>);

fn bytes<'py>(py: Python<'py>, b: &[u8]) -> Bound<'py, PyBytes> {
    PyBytes::new(py, b)
}

// ---------------------------------------------------------------- canonical JSON + IDs
#[pyfunction]
fn canonicalize<'py>(py: Python<'py>, text: &str) -> PyResult<Bound<'py, PyBytes>> {
    Ok(bytes(
        py,
        &cjson::canonicalize_text(text).map_err(canon_err)?,
    ))
}

#[pyfunction]
fn format_number(x: f64) -> PyResult<String> {
    cjson::format_number(x).map_err(canon_err)
}

#[pyfunction]
fn blob_id(data: &[u8]) -> String {
    ids::blob_id(data)
}

/// Streaming blob ID of a file: (id, size_bytes).
#[pyfunction]
fn blob_id_file(py: Python<'_>, path: PathBuf) -> PyResult<(String, u64)> {
    py.detach(|| {
        let f = std::fs::File::open(&path)?;
        ids::blob_id_reader(std::io::BufReader::new(f))
    })
    .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))
}

#[pyfunction]
fn pipeline_version_payload<'py>(
    py: Python<'py>,
    spec_json: &str,
) -> PyResult<Bound<'py, PyBytes>> {
    let v = cjson::parse(spec_json).map_err(canon_err)?;
    Ok(bytes(
        py,
        &ids::pipeline_version_payload(&v).map_err(canon_err)?,
    ))
}

#[pyfunction]
fn pipeline_version_id(spec_json: &str) -> PyResult<String> {
    let v = cjson::parse(spec_json).map_err(canon_err)?;
    ids::pipeline_version_id(&v).map_err(canon_err)
}

#[pyfunction]
fn chunk_id(dtype_name: &str, shape: Vec<u64>, data: &[u8]) -> PyResult<String> {
    ids::chunk_id(dtype(dtype_name)?, &shape, data).map_err(canon_err)
}

#[pyfunction]
fn prov_batch_id(batch_json: &str) -> PyResult<String> {
    let v = cjson::parse(batch_json).map_err(canon_err)?;
    ids::prov_batch_id(&v).map_err(canon_err)
}

#[pyfunction]
fn verify_chain(batches_json: Vec<String>) -> PyResult<Vec<String>> {
    let vals = batches_json
        .iter()
        .map(|t| cjson::parse(t))
        .collect::<Result<Vec<_>, _>>()
        .map_err(canon_err)?;
    ids::verify_chain(&vals).map_err(canon_err)
}

#[pyfunction]
fn is_valid_id(id: &str) -> bool {
    ids::is_valid_id(id)
}

// ---------------------------------------------------------------- Zarr + cache
#[pyfunction]
#[pyo3(signature = (root, recording_id, data, dtype_name, n_samples, sfreq, ch_names, units, chunk_s=4.0, chunk_channels=64, timestamps=None))]
#[allow(clippy::too_many_arguments)]
fn write_signal(
    py: Python<'_>,
    root: PathBuf,
    recording_id: &str,
    data: &[u8],
    dtype_name: &str,
    n_samples: u64,
    sfreq: f64,
    ch_names: Vec<String>,
    units: Vec<String>,
    chunk_s: f64,
    chunk_channels: u64,
    timestamps: Option<Vec<f64>>,
) -> PyResult<()> {
    let dt = dtype(dtype_name)?;
    py.detach(|| {
        let mut store = FsStore::new(root);
        zarr::write_signal(
            &mut store,
            recording_id,
            data,
            dt,
            n_samples,
            sfreq,
            &ch_names,
            &units,
            chunk_s,
            chunk_channels,
            timestamps.as_deref(),
        )
    })
    .map_err(core_err)
}

/// Read `[start, stop)` samples of level 0: (dtype, [n_samples, n_channels], bytes).
#[pyfunction]
fn read_signal<'py>(
    py: Python<'py>,
    root: PathBuf,
    recording_id: &str,
    start: u64,
    stop: u64,
) -> PyResult<ArrayOut<'py>> {
    let (meta, data) = py
        .detach(|| zarr::read_signal(&FsStore::new(root), recording_id, start, stop))
        .map_err(core_err)?;
    let n = (data.len() / meta.dtype.itemsize()) as u64 / meta.shape[1];
    Ok((
        meta.dtype.name().to_owned(),
        vec![n, meta.shape[1]],
        bytes(py, &data),
    ))
}

/// Read a box of any Zarr v3 array (regular grid, bytes codec): (dtype, shape, bytes).
#[pyfunction]
fn read_region<'py>(
    py: Python<'py>,
    root: PathBuf,
    path: &str,
    start: Vec<u64>,
    stop: Vec<u64>,
) -> PyResult<ArrayOut<'py>> {
    let store = FsStore::new(root);
    let (meta, data) = py
        .detach(|| {
            let meta = zarr::read_meta(&store, path)?;
            let data = zarr::read_region(&store, path, &meta, &start, &stop)?;
            Ok::<_, zarr::ZarrError>((meta, data))
        })
        .map_err(core_err)?;
    let shape: Vec<u64> = start
        .iter()
        .zip(&stop)
        .zip(&meta.shape)
        .map(|((a, b), n)| (*b).min(*n).saturating_sub(*a))
        .collect();
    Ok((meta.dtype.name().to_owned(), shape, bytes(py, &data)))
}

#[pyclass(module = "neuroforge._native")]
struct ChunkCache(CoreCache);

#[pymethods]
impl ChunkCache {
    #[new]
    fn new(root: PathBuf, max_bytes: u64) -> PyResult<Self> {
        Ok(Self(CoreCache::open(root, max_bytes).map_err(core_err)?))
    }
    fn put(
        &self,
        py: Python<'_>,
        dtype_name: &str,
        shape: Vec<u64>,
        data: &[u8],
    ) -> PyResult<String> {
        let dt = dtype(dtype_name)?;
        py.detach(|| self.0.put(dt, &shape, data)).map_err(core_err)
    }
    fn get<'py>(&self, py: Python<'py>, id: &str) -> PyResult<Option<ArrayOut<'py>>> {
        let got = py.detach(|| self.0.get(id)).map_err(core_err)?;
        Ok(got.map(|c| (c.dtype.name().to_owned(), c.shape, bytes(py, &c.data))))
    }
    fn size(&self) -> PyResult<u64> {
        self.0.size().map_err(core_err)
    }
}

// ---------------------------------------------------------------- provenance recorder
#[pyclass(module = "neuroforge._native")]
struct ProvRecorder(Mutex<CoreProv>);

#[pymethods]
impl ProvRecorder {
    #[new]
    fn new(dir: PathBuf, chain: &str) -> PyResult<Self> {
        Ok(Self(Mutex::new(
            CoreProv::open(dir, chain).map_err(core_err)?,
        )))
    }
    /// Append one batch; `records_json` is a JSON list of PROV records. Returns (seq, id).
    fn record(&self, py: Python<'_>, records_json: &str) -> PyResult<(u64, String)> {
        let recs: Vec<ProvRecord> =
            serde_json::from_str(records_json).map_err(|e| PyValueError::new_err(e.to_string()))?;
        let b = py
            .detach(|| self.0.lock().expect("prov lock").record(&recs))
            .map_err(core_err)?;
        Ok((b.seq, b.id))
    }
    /// Unsynced batches: [(seq, id, canonical_bytes)].
    fn pending<'py>(&self, py: Python<'py>) -> PyResult<Vec<(u64, String, Bound<'py, PyBytes>)>> {
        let r = self.0.lock().expect("prov lock");
        r.pending()
            .iter()
            .map(|b| {
                Ok((
                    b.seq,
                    b.id.clone(),
                    bytes(py, &cjson::to_canonical(&b.value).map_err(canon_err)?),
                ))
            })
            .collect()
    }
    fn mark_synced(&self, seq: u64) -> PyResult<()> {
        self.0
            .lock()
            .expect("prov lock")
            .mark_synced(seq)
            .map_err(core_err)
    }
    fn head(&self) -> Option<(u64, String)> {
        self.0
            .lock()
            .expect("prov lock")
            .head()
            .map(|b| (b.seq, b.id.clone()))
    }
    fn batch_ids(&self) -> Vec<String> {
        self.0
            .lock()
            .expect("prov lock")
            .batches()
            .iter()
            .map(|b| b.id.clone())
            .collect()
    }
    fn __len__(&self) -> usize {
        self.0.lock().expect("prov lock").len()
    }
}

// ---------------------------------------------------------------- keys, WAL, writer
#[pyclass(module = "neuroforge._native")]
struct DeviceKey(Arc<CoreKey>);

#[pymethods]
impl DeviceKey {
    #[staticmethod]
    fn generate() -> Self {
        Self(Arc::new(CoreKey::generate()))
    }
    /// Import an existing 32-byte Ed25519 seed. There is no way to export it again.
    #[staticmethod]
    fn from_seed(seed: &[u8]) -> PyResult<Self> {
        CoreKey::from_seed(seed)
            .map(|k| Self(Arc::new(k)))
            .ok_or_else(|| PyValueError::new_err("seed must be 32 bytes"))
    }
    /// Windows: the seed is stored only DPAPI-sealed at `path` (created on first use).
    #[staticmethod]
    fn sealed(path: PathBuf) -> PyResult<Self> {
        CoreKey::load_or_create_sealed(&path)
            .map(|k| Self(Arc::new(k)))
            .map_err(core_err)
    }
    #[getter]
    fn public_key<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        bytes(py, &self.0.public_key())
    }
    #[pyo3(signature = (tenant_id, device_id, stream_id, lifetime_s=300))]
    fn token(
        &self,
        tenant_id: &str,
        device_id: &str,
        stream_id: &str,
        lifetime_s: u64,
    ) -> PyResult<String> {
        sign::make_device_token(
            &self.0,
            tenant_id,
            device_id,
            stream_id,
            lifetime_s,
            sign::unix_now(),
        )
        .map_err(canon_err)
    }
    fn __repr__(&self) -> String {
        format!("{:?}", self.0)
    }
}

#[pyclass(module = "neuroforge._native")]
struct Wal(Arc<CoreWal>);

fn wal_err(e: WalError) -> PyErr {
    match e {
        WalError::Corrupt(_) => WalCorrupt::new_err(e.to_string()),
        other => core_err(other),
    }
}

#[pymethods]
impl Wal {
    /// Key source, in order: `key` (32 bytes from an OS keystore), `dpapi_key_path` (Windows,
    /// sealed file compatible with the 2.7 prototype), else an in-memory ephemeral key.
    #[new]
    #[pyo3(signature = (directory, stream_id, key=None, dpapi_key_path=None, fsync=true))]
    fn new(
        directory: PathBuf,
        stream_id: &str,
        key: Option<&[u8]>,
        dpapi_key_path: Option<PathBuf>,
        fsync: bool,
    ) -> PyResult<Self> {
        let provider: Box<dyn KeyProvider> = match (key, dpapi_key_path) {
            (Some(k), _) => Box::new(StaticKey::new(k).map_err(core_err)?),
            (None, Some(p)) => Box::new(DpapiKey::new(p).map_err(core_err)?),
            (None, None) => Box::new(EphemeralKey::new()),
        };
        Ok(Self(Arc::new(
            CoreWal::open(directory, stream_id, provider.as_ref(), fsync).map_err(wal_err)?,
        )))
    }
    fn append(&self, py: Python<'_>, seq: u64, record: &[u8]) -> PyResult<()> {
        py.detach(|| self.0.append(seq, record)).map_err(wal_err)
    }
    fn read<'py>(&self, py: Python<'py>, seq: u64) -> PyResult<Bound<'py, PyBytes>> {
        let r = py.detach(|| self.0.read(seq)).map_err(wal_err)?;
        Ok(bytes(py, &r))
    }
    #[pyo3(signature = (from_seq=0))]
    fn pending(&self, from_seq: u64) -> Vec<u64> {
        self.0.pending(from_seq)
    }
    fn ack(&self, py: Python<'_>, next_seq: u64) -> PyResult<usize> {
        py.detach(|| self.0.ack(next_seq)).map_err(wal_err)
    }
    fn max_seq(&self) -> Option<u64> {
        self.0.max_seq()
    }
    fn __len__(&self) -> usize {
        self.0.len()
    }
}

#[pyclass(module = "neuroforge._native")]
struct StreamWriter(Mutex<CoreWriter>);

/// Config errors (bad rate, chunk under 20 ms, value cap) are the caller's arguments:
/// `ValueError`. Anything else stays `CoreError`.
fn writer_err(e: WriterError) -> PyErr {
    match e {
        WriterError::Config(_) => PyValueError::new_err(e.to_string()),
        other => core_err(other),
    }
}

#[pymethods]
impl StreamWriter {
    /// With `sfreq` (Hz): a timed stream, chunks of `chunk_ms` (default 100) or, if given,
    /// `chunk_samples`, which must last at least 20 ms. Without `sfreq`: a stream without a
    /// nominal rate, chunked by `chunk_samples` (no duration check).
    #[new]
    #[pyo3(signature = (stream_id, dtype_name, n_channels, chunk_samples, key, wal, *, sfreq=None, chunk_ms=None))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        stream_id: &str,
        dtype_name: &str,
        n_channels: u32,
        chunk_samples: Option<u32>,
        key: &DeviceKey,
        wal: &Wal,
        sfreq: Option<f64>,
        chunk_ms: Option<f64>,
    ) -> PyResult<Self> {
        let dt = dtype(dtype_name)?;
        let cfg = match (sfreq, chunk_samples, chunk_ms) {
            (Some(_), Some(_), Some(_)) => {
                return Err(PyValueError::new_err(
                    "pass chunk_ms or chunk_samples, not both",
                ));
            }
            // Checked against the 20 ms floor by the core writer.
            (Some(f), Some(cs), None) => StreamConfig {
                stream_id: stream_id.into(),
                dtype: dt,
                n_channels,
                chunk_samples: cs,
                sfreq: Some(f),
            },
            (Some(f), None, ms) => {
                let ms = ms.unwrap_or(100.0);
                StreamConfig::timed(stream_id, dt, n_channels, f, ms).map_err(writer_err)?
            }
            (None, _, Some(_)) => return Err(PyValueError::new_err("chunk_ms needs sfreq")),
            (None, None, None) => {
                return Err(PyValueError::new_err(
                    "a stream without sfreq needs chunk_samples",
                ));
            }
            (None, Some(cs), None) => StreamConfig::irregular(stream_id, dt, n_channels, cs),
        };
        Ok(Self(Mutex::new(
            CoreWriter::new(cfg, key.0.clone(), wal.0.clone()).map_err(writer_err)?,
        )))
    }
    #[getter]
    fn sfreq(&self) -> Option<f64> {
        self.0.lock().expect("writer lock").config().sfreq
    }
    #[getter]
    fn chunk_samples(&self) -> u32 {
        self.0.lock().expect("writer lock").config().chunk_samples
    }
    /// True once a timed writer's flush wrote the short final chunk (push is then refused).
    #[getter]
    fn closed(&self) -> bool {
        self.0.lock().expect("writer lock").is_closed()
    }
    /// `samples`: n x n_channels little-endian values (C order); `timestamps`: n float64 LE.
    fn push(&self, py: Python<'_>, samples: &[u8], timestamps: &[u8]) -> PyResult<usize> {
        if !timestamps.len().is_multiple_of(8) {
            return Err(PyValueError::new_err("timestamps must be float64 bytes"));
        }
        let ts: Vec<f64> = timestamps
            .as_chunks::<8>()
            .0
            .iter()
            .map(|b| f64::from_le_bytes(*b))
            .collect();
        py.detach(|| self.0.lock().expect("writer lock").push(samples, &ts))
            .map_err(core_err)
    }
    fn add_clock_offset(&self, collection_time: f64, offset: f64) {
        self.0
            .lock()
            .expect("writer lock")
            .add_clock_offset(collection_time, offset);
    }
    fn add_local_clock(&self, lsl_time: f64, monotonic_time: f64) {
        self.0
            .lock()
            .expect("writer lock")
            .add_local_clock(lsl_time, monotonic_time);
    }
    fn flush(&self, py: Python<'_>) -> PyResult<bool> {
        py.detach(|| self.0.lock().expect("writer lock").flush())
            .map_err(core_err)
    }
    #[getter]
    fn next_seq(&self) -> u64 {
        self.0.lock().expect("writer lock").next_seq()
    }
    #[getter]
    fn buffered_samples(&self) -> usize {
        self.0.lock().expect("writer lock").buffered_samples()
    }
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let s = self.0.lock().expect("writer lock").stats.clone();
        let d = PyDict::new(py);
        d.set_item("chunks", s.chunks)?;
        d.set_item("samples", s.samples)?;
        d.set_item("wal_peak", s.wal_peak)?;
        Ok(d)
    }
}

// ---------------------------------------------------------------- sender (gRPC via Python)
/// Calls `transport.get_stream_state(req: bytes, auth: str, timeout: float) -> bytes`,
/// `transport.stream_chunks(chunks: list[bytes], auth, timeout) -> bytes`,
/// `transport.finish_stream(req, auth, timeout) -> bytes`. A raised exception with an integer
/// `code` attribute maps to that gRPC status; anything else is UNKNOWN (retried).
struct PyIngest(Py<PyAny>);

impl PyIngest {
    fn call(
        &self,
        name: &str,
        arg: impl FnOnce(Python<'_>) -> PyResult<Py<PyAny>>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError> {
        Python::attach(|py| {
            let res = arg(py).and_then(|a| {
                self.0
                    .bind(py)
                    .call_method1(name, (a, auth, timeout.as_secs_f64()))
            });
            match res {
                Ok(v) => v.extract::<Vec<u8>>().map_err(|e| RpcError {
                    code: sender::code::UNKNOWN,
                    message: e.to_string(),
                }),
                Err(e) => {
                    let code = e
                        .value(py)
                        .getattr("code")
                        .ok()
                        .and_then(|c| c.extract::<i32>().ok())
                        .unwrap_or(sender::code::UNKNOWN);
                    Err(RpcError {
                        code,
                        message: e.to_string(),
                    })
                }
            }
        })
    }
}

impl IngestTransport for PyIngest {
    fn get_stream_state(
        &self,
        request: Vec<u8>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError> {
        self.call(
            "get_stream_state",
            |py| Ok(PyBytes::new(py, &request).into_any().unbind()),
            auth,
            timeout,
        )
    }
    fn stream_chunks(
        &self,
        chunks: Vec<Vec<u8>>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError> {
        self.call(
            "stream_chunks",
            |py| {
                Ok(PyList::new(py, chunks.iter().map(|c| PyBytes::new(py, c)))?
                    .into_any()
                    .unbind())
            },
            auth,
            timeout,
        )
    }
    fn finish_stream(
        &self,
        request: Vec<u8>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError> {
        self.call(
            "finish_stream",
            |py| Ok(PyBytes::new(py, &request).into_any().unbind()),
            auth,
            timeout,
        )
    }
}

#[pyclass(module = "neuroforge._native")]
struct Sender(Arc<CoreSender>);

fn state_dict<'py>(
    py: Python<'py>,
    s: nf_core::stream::proto::StreamState,
) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("stream_id", s.stream_id)?;
    d.set_item("next_seq", s.next_seq)?;
    d.set_item("n_samples", s.n_samples)?;
    d.set_item("state", s.state)?;
    d.set_item("suspect", s.suspect)?;
    Ok(d)
}

fn rpc_err(e: RpcError) -> PyErr {
    CoreError::new_err(format!("rpc code {}: {}", e.code, e.message))
}

#[pymethods]
impl Sender {
    #[new]
    #[pyo3(signature = (tenant_id, device_id, stream_id, key, wal, batch_max=50, linger_s=0.2, call_timeout_s=10.0, backoff_min_s=0.05, backoff_max_s=1.0))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        tenant_id: &str,
        device_id: &str,
        stream_id: &str,
        key: &DeviceKey,
        wal: &Wal,
        batch_max: usize,
        linger_s: f64,
        call_timeout_s: f64,
        backoff_min_s: f64,
        backoff_max_s: f64,
    ) -> PyResult<Self> {
        let secs = |x: f64| {
            Duration::try_from_secs_f64(x)
                .map_err(|_| PyValueError::new_err("durations must be >= 0"))
        };
        let mut cfg = SenderConfig::new(tenant_id, device_id, stream_id);
        cfg.batch_max = batch_max.max(1);
        cfg.linger = secs(linger_s)?;
        cfg.call_timeout = secs(call_timeout_s)?;
        cfg.backoff_min = secs(backoff_min_s)?;
        cfg.backoff_max = secs(backoff_max_s)?;
        Ok(Self(Arc::new(CoreSender::new(
            cfg,
            key.0.clone(),
            wal.0.clone(),
        ))))
    }
    /// Blocks (GIL released) until `stop()` or a fatal error.
    fn run(&self, py: Python<'_>, transport: Py<PyAny>) {
        let s = self.0.clone();
        py.detach(move || s.run(&PyIngest(transport)));
    }
    fn stop(&self) {
        self.0.stop.store(true, Ordering::SeqCst);
    }
    fn reset(&self) {
        self.0.stop.store(false, Ordering::SeqCst);
    }
    fn state<'py>(&self, py: Python<'py>, transport: Py<PyAny>) -> PyResult<Bound<'py, PyDict>> {
        let s = self.0.clone();
        let st = py
            .detach(move || s.state(&PyIngest(transport)))
            .map_err(rpc_err)?;
        state_dict(py, st)
    }
    fn finish<'py>(&self, py: Python<'py>, transport: Py<PyAny>) -> PyResult<Bound<'py, PyDict>> {
        let s = self.0.clone();
        let st = py
            .detach(move || s.finish(&PyIngest(transport)))
            .map_err(rpc_err)?;
        state_dict(py, st)
    }
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let s = self.0.stats();
        let d = PyDict::new(py);
        d.set_item("calls", s.calls)?;
        d.set_item("chunks_acked", s.chunks_acked)?;
        d.set_item("rpc_errors", s.rpc_errors)?;
        d.set_item("next_seq_acked", s.next_seq_acked)?;
        d.set_item("fatal", s.fatal)?;
        d.set_item("errors", s.errors)?;
        Ok(d)
    }
}

// ---------------------------------------------------------------- HTTP API client
/// `transport(method, url, headers, body, timeout) -> (status, headers, body)`.
struct PyHttp(Py<PyAny>, f64);

impl HttpTransport for PyHttp {
    fn send(&self, req: &http::Request) -> Result<http::Response, http::TransportError> {
        Python::attach(|py| {
            let headers: Vec<(String, String)> = req.headers.clone();
            let out = self
                .0
                .bind(py)
                .call1((
                    req.method.as_str(),
                    req.url.as_str(),
                    headers,
                    PyBytes::new(py, &req.body),
                    self.1,
                ))
                .and_then(|r| r.extract::<(u16, Vec<(String, String)>, Vec<u8>)>());
            match out {
                Ok((status, headers, body)) => Ok(http::Response {
                    status,
                    headers,
                    body,
                }),
                Err(e) => Err(http::TransportError::other(e.to_string())),
            }
        })
    }
}

/// `provider(refresh: bool) -> str`.
struct PyTokens(Py<PyAny>);

impl TokenSource for PyTokens {
    fn token(&self) -> Result<String, String> {
        Python::attach(|py| {
            self.0
                .bind(py)
                .call1((false,))
                .and_then(|t| t.extract::<String>())
                .map_err(|e| e.to_string())
        })
    }
    fn refresh(&self) -> Result<String, String> {
        Python::attach(|py| {
            self.0
                .bind(py)
                .call1((true,))
                .and_then(|t| t.extract::<String>())
                .map_err(|e| e.to_string())
        })
    }
}

#[pyclass(module = "neuroforge._native")]
struct ApiClient(CoreClient<PyHttp>);

fn api_err(e: http::ApiError) -> PyErr {
    match &e {
        http::ApiError::Http {
            status, problem, ..
        } => {
            let pj = problem.as_ref().and_then(|p| serde_json::to_string(p).ok());
            ApiError::new_err(("http", *status, e.to_string(), pj))
        }
        http::ApiError::Url(_) => ApiError::new_err(("url", 0u16, e.to_string(), None::<String>)),
        http::ApiError::Auth(_) => ApiError::new_err(("auth", 0u16, e.to_string(), None::<String>)),
        http::ApiError::Transport(_) => {
            ApiError::new_err(("transport", 0u16, e.to_string(), None::<String>))
        }
        http::ApiError::Decode(_) => {
            ApiError::new_err(("decode", 0u16, e.to_string(), None::<String>))
        }
    }
}

#[pymethods]
impl ApiClient {
    #[new]
    #[pyo3(signature = (base_url, transport, tokens, timeout_s=30.0, max_attempts=5, user_agent=None))]
    fn new(
        base_url: &str,
        transport: Py<PyAny>,
        tokens: Py<PyAny>,
        timeout_s: f64,
        max_attempts: u32,
        user_agent: Option<String>,
    ) -> PyResult<Self> {
        let mut c = CoreClient::new(
            base_url,
            PyHttp(transport, timeout_s),
            Box::new(PyTokens(tokens)),
        )
        .map_err(api_err)?;
        c.policy.max_attempts = max_attempts.max(1);
        if let Some(ua) = user_agent {
            c.user_agent = ua;
        }
        Ok(Self(c))
    }
    #[getter]
    fn base_url(&self) -> String {
        self.0.base().to_owned()
    }
    /// Send with auth + retries; returns (status, headers, body) for 2xx, raises ApiError else.
    #[pyo3(signature = (method, path, query=vec![], headers=vec![], body=vec![]))]
    fn request<'py>(
        &self,
        py: Python<'py>,
        method: &str,
        path: &str,
        query: Vec<(String, String)>,
        headers: Vec<(String, String)>,
        body: Vec<u8>,
    ) -> PyResult<HttpOut<'py>> {
        let q: Vec<(&str, String)> = query.iter().map(|(k, v)| (k.as_str(), v.clone())).collect();
        let r = py
            .detach(|| self.0.send(method, path, &q, headers, body))
            .map_err(api_err)?;
        Ok((r.status, r.headers, bytes(py, &r.body)))
    }
}

/// SEC-030 URL policy as used by the client (https, or http to a loopback host).
#[pyfunction]
fn check_base_url(url: &str) -> PyResult<()> {
    http::check_base_url(url).map_err(api_err)
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", nf_core::VERSION)?;
    m.add("CanonicalError", m.py().get_type::<CanonicalError>())?;
    m.add("WalCorrupt", m.py().get_type::<WalCorrupt>())?;
    m.add("CoreError", m.py().get_type::<CoreError>())?;
    m.add("ApiError", m.py().get_type::<ApiError>())?;
    for f in [
        wrap_pyfunction!(canonicalize, m)?,
        wrap_pyfunction!(format_number, m)?,
        wrap_pyfunction!(blob_id, m)?,
        wrap_pyfunction!(blob_id_file, m)?,
        wrap_pyfunction!(pipeline_version_payload, m)?,
        wrap_pyfunction!(pipeline_version_id, m)?,
        wrap_pyfunction!(chunk_id, m)?,
        wrap_pyfunction!(prov_batch_id, m)?,
        wrap_pyfunction!(verify_chain, m)?,
        wrap_pyfunction!(is_valid_id, m)?,
        wrap_pyfunction!(write_signal, m)?,
        wrap_pyfunction!(read_signal, m)?,
        wrap_pyfunction!(read_region, m)?,
        wrap_pyfunction!(check_base_url, m)?,
    ] {
        m.add_function(f)?;
    }
    m.add_class::<ChunkCache>()?;
    m.add_class::<ProvRecorder>()?;
    m.add_class::<DeviceKey>()?;
    m.add_class::<Wal>()?;
    m.add_class::<StreamWriter>()?;
    m.add_class::<Sender>()?;
    m.add_class::<ApiClient>()?;
    Ok(())
}
