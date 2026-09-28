//! Sender side: replays the write-ahead buffer to `IngestService.StreamChunks` and resumes from
//! the server's committed `next_seq` after any failure (same rules as the 2.7 prototype's
//! `EdgeClient._send_loop`).
//!
//! 1. `GetStreamState` -> `next_seq`; drop acknowledged WAL records. A server `next_seq` beyond
//!    the WAL's high-water mark means the server holds seqs this WAL never produced (stream_id
//!    reused, or the WAL directory was lost): fatal, and nothing is deleted (H4).
//! 2. Send a batch of up to `batch_max` records in seq order (waiting up to `linger` for each
//!    next record); the ack's `next_seq` deletes what the server stored durably. An ack beyond
//!    `last sent seq + 1` is a protocol violation: fatal, and nothing is deleted (H4).
//! 3. On any error: fatal codes stop the sender and are reported; everything else backs off
//!    exponentially, re-syncs from the server state and resends. The server is idempotent on
//!    `(stream_id, seq)`, so overlapping resends are harmless.
//!
//! The transport is a trait: the Python binding implements it with grpcio (raw bytes in, raw
//! bytes out), so the rules above run in nf-core while the HTTP/2 stack stays in the host.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use super::proto::{self, StreamAck, StreamState};
use super::sign::{DeviceKey, auth_header, make_device_token, unix_now};
use super::wal::Wal;

/// gRPC status codes (only the numbers matter on the wire).
pub mod code {
    pub const CANCELLED: i32 = 1;
    pub const UNKNOWN: i32 = 2;
    pub const INVALID_ARGUMENT: i32 = 3;
    pub const DEADLINE_EXCEEDED: i32 = 4;
    pub const NOT_FOUND: i32 = 5;
    pub const ALREADY_EXISTS: i32 = 6;
    pub const PERMISSION_DENIED: i32 = 7;
    pub const RESOURCE_EXHAUSTED: i32 = 8;
    pub const UNAVAILABLE: i32 = 14;
    pub const DATA_LOSS: i32 = 15;
    pub const UNAUTHENTICATED: i32 = 16;
}

/// Errors after which resending the same bytes can never succeed.
pub const FATAL: [i32; 6] = [
    code::UNAUTHENTICATED,
    code::PERMISSION_DENIED,
    code::INVALID_ARGUMENT,
    code::ALREADY_EXISTS,
    code::DATA_LOSS,
    code::NOT_FOUND,
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RpcError {
    pub code: i32,
    pub message: String,
}

impl RpcError {
    pub fn is_fatal(&self) -> bool {
        FATAL.contains(&self.code)
    }
}

/// Raw-bytes transport for the three IngestService calls. `auth` is the full `authorization`
/// metadata value; `timeout` is the per-call deadline.
pub trait IngestTransport {
    fn get_stream_state(
        &self,
        request: Vec<u8>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError>;
    fn stream_chunks(
        &self,
        chunks: Vec<Vec<u8>>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError>;
    fn finish_stream(
        &self,
        request: Vec<u8>,
        auth: &str,
        timeout: Duration,
    ) -> Result<Vec<u8>, RpcError>;
}

#[derive(Debug, Clone)]
pub struct SenderConfig {
    pub tenant_id: String,
    pub device_id: String,
    pub stream_id: String,
    pub batch_max: usize,
    pub linger: Duration,
    pub call_timeout: Duration,
    pub backoff_min: Duration,
    pub backoff_max: Duration,
    pub token_lifetime_s: u64,
}

impl SenderConfig {
    pub fn new(tenant_id: &str, device_id: &str, stream_id: &str) -> Self {
        Self {
            tenant_id: tenant_id.into(),
            device_id: device_id.into(),
            stream_id: stream_id.into(),
            batch_max: 50,
            linger: Duration::from_millis(200),
            call_timeout: Duration::from_secs(10),
            backoff_min: Duration::from_millis(50),
            backoff_max: Duration::from_secs(1),
            token_lifetime_s: 300,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq)]
pub struct SenderStats {
    pub calls: u64,
    pub chunks_acked: u64,
    pub rpc_errors: u64,
    pub next_seq_acked: u64,
    pub fatal: Option<String>,
    pub errors: Vec<i32>,
}

pub struct Sender {
    pub cfg: SenderConfig,
    key: Arc<DeviceKey>,
    wal: Arc<Wal>,
    pub stop: Arc<AtomicBool>,
    stats: std::sync::Mutex<SenderStats>,
}

fn decode_err(e: proto::DecodeError) -> RpcError {
    RpcError {
        code: code::UNKNOWN,
        message: e.to_string(),
    }
}

impl Sender {
    pub fn new(cfg: SenderConfig, key: Arc<DeviceKey>, wal: Arc<Wal>) -> Self {
        Self {
            cfg,
            key,
            wal,
            stop: Arc::new(AtomicBool::new(false)),
            stats: Default::default(),
        }
    }

    pub fn stats(&self) -> SenderStats {
        self.stats.lock().expect("stats").clone()
    }

    fn auth(&self) -> Result<String, RpcError> {
        let t = make_device_token(
            &self.key,
            &self.cfg.tenant_id,
            &self.cfg.device_id,
            &self.cfg.stream_id,
            self.cfg.token_lifetime_s,
            unix_now(),
        )
        .map_err(|e| RpcError {
            code: code::INVALID_ARGUMENT,
            message: e.to_string(),
        })?;
        Ok(auth_header(&t))
    }

    pub fn state(&self, t: &dyn IngestTransport) -> Result<StreamState, RpcError> {
        let raw = t.get_stream_state(
            proto::encode_stream_id_request(&self.cfg.stream_id),
            &self.auth()?,
            self.cfg.call_timeout,
        )?;
        StreamState::decode(&raw).map_err(decode_err)
    }

    pub fn finish(&self, t: &dyn IngestTransport) -> Result<StreamState, RpcError> {
        let raw = t.finish_stream(
            proto::encode_stream_id_request(&self.cfg.stream_id),
            &self.auth()?,
            self.cfg.call_timeout * 6,
        )?;
        StreamState::decode(&raw).map_err(decode_err)
    }

    fn batch(&self, first: u64) -> Result<Vec<Vec<u8>>, RpcError> {
        let mut out = Vec::new();
        let mut seq = first;
        while out.len() < self.cfg.batch_max {
            if !self.wal.wait_for(seq, self.cfg.linger) {
                break;
            }
            out.push(self.wal.read(seq).map_err(|e| RpcError {
                code: code::DATA_LOSS,
                message: e.to_string(),
            })?);
            seq += 1;
        }
        Ok(out)
    }

    fn sleep_or_stop(&self, d: Duration) {
        let step = Duration::from_millis(10);
        let mut left = d;
        while !left.is_zero() && !self.stop.load(Ordering::SeqCst) {
            let s = left.min(step);
            std::thread::sleep(s);
            left -= s;
        }
    }

    /// Run until `stop` is set or a fatal error occurs.
    pub fn run(&self, t: &dyn IngestTransport) {
        let mut next: Option<u64> = None;
        let mut backoff = self.cfg.backoff_min;
        while !self.stop.load(Ordering::SeqCst) {
            let step: Result<(), RpcError> = (|| {
                let n = match next {
                    Some(n) => n,
                    None => {
                        let st = self.state(t)?;
                        let hwm = self.wal.next_seq();
                        if st.next_seq > hwm {
                            return Err(RpcError {
                                code: code::DATA_LOSS,
                                message: format!(
                                    "server next_seq {} is beyond this WAL's high-water mark {hwm} \
                                     (stream_id reused or WAL lost); refusing to drop local records",
                                    st.next_seq
                                ),
                            });
                        }
                        self.wal.ack(st.next_seq).map_err(|e| RpcError {
                            code: code::DATA_LOSS,
                            message: e.to_string(),
                        })?;
                        next = Some(st.next_seq);
                        st.next_seq
                    }
                };
                if self.wal.pending(n).is_empty() {
                    self.wal.wait_for(n, Duration::from_millis(100));
                    return Ok(());
                }
                let batch = self.batch(n)?;
                if batch.is_empty() {
                    return Ok(());
                }
                let sent_end = n + batch.len() as u64; // last sent seq + 1
                self.stats.lock().expect("stats").calls += 1;
                let raw = t.stream_chunks(batch, &self.auth()?, self.cfg.call_timeout)?;
                let ack = StreamAck::decode(&raw).map_err(decode_err)?;
                if ack.next_seq > sent_end {
                    return Err(RpcError {
                        code: code::DATA_LOSS,
                        message: format!(
                            "server acked next_seq {} but only seqs < {sent_end} were sent; \
                             refusing to drop unsent records",
                            ack.next_seq
                        ),
                    });
                }
                {
                    let mut s = self.stats.lock().expect("stats");
                    s.chunks_acked += ack.next_seq.saturating_sub(n);
                    s.next_seq_acked = ack.next_seq;
                }
                next = Some(ack.next_seq);
                self.wal.ack(ack.next_seq).map_err(|e| RpcError {
                    code: code::DATA_LOSS,
                    message: e.to_string(),
                })?;
                Ok(())
            })();
            match step {
                Ok(()) => backoff = self.cfg.backoff_min,
                Err(e) => {
                    let mut s = self.stats.lock().expect("stats");
                    s.rpc_errors += 1;
                    if s.errors.len() < 50 {
                        s.errors.push(e.code);
                    }
                    if e.is_fatal() {
                        s.fatal = Some(format!("code {}: {}", e.code, e.message));
                        return;
                    }
                    drop(s);
                    next = None; // re-sync from the server's committed state
                    self.sleep_or_stop(backoff);
                    backoff = (backoff * 2).min(self.cfg.backoff_max);
                }
            }
        }
    }
}
