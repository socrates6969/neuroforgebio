//! Stream write-ahead buffer, chunk building/signing and the resuming sender (feature `stream`).
//! The in-memory server below follows the platform's idempotency rules (commit only `seq ==
//! next_seq`, duplicates acknowledged, a different chunk under a committed seq rejected) and can
//! drop calls, so network cuts are simulated without sockets. The end-to-end run against the real
//! Python server lives in `bindings/python/tests`.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use nf_core::b64;
use nf_core::cjson;
use nf_core::ids::{self, Dtype};
use nf_core::stream::keystore::{EphemeralKey, StaticKey};
use nf_core::stream::proto::{self, Chunk, StreamAck, StreamState};
use nf_core::stream::sender::{IngestTransport, RpcError, Sender, SenderConfig, code};
use nf_core::stream::sign::{self, DeviceKey};
use nf_core::stream::wal::{Wal, WalError};
use nf_core::stream::writer::{StreamConfig, StreamWriter};
use proptest::prelude::*;

fn tmp(name: &str) -> PathBuf {
    static N: AtomicU32 = AtomicU32::new(0);
    let p = std::env::temp_dir().join(format!(
        "nfcore-stream-{name}-{}-{}",
        std::process::id(),
        N.fetch_add(1, Ordering::SeqCst)
    ));
    let _ = std::fs::remove_dir_all(&p);
    p
}

#[test]
fn wal_is_ciphertext_acked_records_deleted_tamper_detected() {
    let d = tmp("wal");
    let key = [7u8; 32];
    let wal = Wal::open(&d, "stream-1", &StaticKey::new(&key).unwrap(), false).unwrap();
    let rec: Vec<u8> = (0..400u32).map(|i| (i % 251) as u8).collect();
    for s in 0..3 {
        wal.append(s, &rec).unwrap();
    }
    for f in std::fs::read_dir(&d).unwrap() {
        let blob = std::fs::read(f.unwrap().path()).unwrap();
        assert!(blob.starts_with(b"NFWAL1"));
        assert!(
            !blob
                .windows(32)
                .any(|w| w == &rec[..32] || w == &rec[100..132])
        );
    }
    assert_eq!(wal.read(1).unwrap(), rec);
    assert_eq!(wal.ack(2).unwrap(), 2);
    assert_eq!(wal.pending(0), vec![2]);
    let mut names: Vec<String> = std::fs::read_dir(&d)
        .unwrap()
        .map(|e| e.unwrap().file_name().into_string().unwrap())
        .collect();
    names.sort();
    assert_eq!(
        names,
        vec![
            "0000000000000002.nfwal".to_owned(),
            "next_seq.hwm".to_owned()
        ]
    );
    // a restarted client finds its records; a different key or tampering is detected
    let again = Wal::open(&d, "stream-1", &StaticKey::new(&key).unwrap(), false).unwrap();
    assert_eq!(again.read(2).unwrap(), rec);
    let other = Wal::open(&d, "stream-1", &EphemeralKey::new(), false).unwrap();
    assert!(matches!(other.read(2), Err(WalError::Corrupt(2))));
    let wrong_stream = Wal::open(&d, "stream-2", &StaticKey::new(&key).unwrap(), false).unwrap();
    assert!(matches!(wrong_stream.read(2), Err(WalError::Corrupt(2))));
    let f = d.join("0000000000000002.nfwal");
    let mut b = std::fs::read(&f).unwrap();
    *b.last_mut().unwrap() ^= 1;
    std::fs::write(&f, b).unwrap();
    assert!(matches!(again.read(2), Err(WalError::Corrupt(2))));
    let _ = std::fs::remove_dir_all(&d);
}

#[test]
fn device_token_matches_protocol_shape() {
    let key = DeviceKey::from_seed(&[1u8; 32]).unwrap();
    let tok = sign::make_device_token(&key, "tn", "dev", "st", 300, 1_790_000_000).unwrap();
    let parts: Vec<&str> = tok.split('.').collect();
    assert_eq!(parts[0], "nfd1");
    let payload = b64::decode_url(parts[1]).unwrap();
    assert_eq!(
        std::str::from_utf8(&payload).unwrap(),
        r#"{"aud":"nf-ingest/v1","device_id":"dev","exp":1790000300,"iat":1790000000,"stream_id":"st","tenant_id":"tn"}"#
    );
    let sig = b64::decode_url(parts[2]).unwrap();
    let pre = ids::tagged_preimage(sign::TAG_DEVICE_TOKEN, &payload);
    assert!(sign::verify(&key.public_key(), &pre, &sig));
    assert!(sign::make_device_token(&key, "tn", "dev", "st", 601, 0).is_err());
    assert!(!format!("{key:?}").contains("0101010101"));
}

// ---------------------------------------------------------------- fake server
#[derive(Default)]
struct FakeServer {
    committed: Mutex<BTreeMap<u64, Chunk>>,
    drop_next: AtomicU32,
    calls: AtomicU32,
    public_key: [u8; 32],
}

impl FakeServer {
    fn next_seq(&self) -> u64 {
        self.committed
            .lock()
            .unwrap()
            .keys()
            .next_back()
            .map_or(0, |s| s + 1)
    }
    fn maybe_drop(&self) -> Result<(), RpcError> {
        self.calls.fetch_add(1, Ordering::SeqCst);
        if self.drop_next.load(Ordering::SeqCst) > 0 {
            self.drop_next.fetch_sub(1, Ordering::SeqCst);
            return Err(RpcError {
                code: code::UNAVAILABLE,
                message: "cut".into(),
            });
        }
        Ok(())
    }
}

impl IngestTransport for FakeServer {
    fn get_stream_state(&self, _r: Vec<u8>, auth: &str, _t: Duration) -> Result<Vec<u8>, RpcError> {
        assert!(auth.starts_with("NFDevice nfd1."));
        self.maybe_drop()?;
        Ok(StreamState {
            stream_id: "s".into(),
            next_seq: self.next_seq(),
            n_samples: 0,
            state: "open".into(),
            suspect: false,
        }
        .encode())
    }
    fn stream_chunks(
        &self,
        chunks: Vec<Vec<u8>>,
        _auth: &str,
        _t: Duration,
    ) -> Result<Vec<u8>, RpcError> {
        self.maybe_drop()?;
        let mut ack = StreamAck {
            stream_id: "s".into(),
            ..Default::default()
        };
        let mut committed = self.committed.lock().unwrap();
        for raw in chunks {
            let c = Chunk::decode(&raw).map_err(|e| RpcError {
                code: code::INVALID_ARGUMENT,
                message: e.to_string(),
            })?;
            // signature AND recomputed chunk_id over the samples (M9)
            assert!(
                sign::verify_chunk_full(&c, &self.public_key),
                "bad signature or payload"
            );
            let next = committed.keys().next_back().map_or(0, |s| s + 1);
            match committed.get(&c.seq) {
                Some(old) if old.chunk_id == c.chunk_id => ack.duplicates += 1,
                Some(_) => {
                    return Err(RpcError {
                        code: code::ALREADY_EXISTS,
                        message: "conflict".into(),
                    });
                }
                None if c.seq == next => {
                    committed.insert(c.seq, c);
                    ack.accepted += 1;
                }
                None => {
                    return Err(RpcError {
                        code: code::INVALID_ARGUMENT,
                        message: "gap".into(),
                    });
                }
            }
        }
        ack.next_seq = committed.keys().next_back().map_or(0, |s| s + 1);
        Ok(ack.encode())
    }
    fn finish_stream(&self, _r: Vec<u8>, _a: &str, _t: Duration) -> Result<Vec<u8>, RpcError> {
        Ok(StreamState {
            state: "closed".into(),
            next_seq: self.next_seq(),
            ..Default::default()
        }
        .encode())
    }
}

fn f32s(start: usize, n: usize, ch: usize) -> Vec<u8> {
    (start..start + n)
        .flat_map(|i| (0..ch).map(move |c| (i * 7 + c * 131) as f32 * 0.5))
        .flat_map(f32::to_le_bytes)
        .collect()
}

#[test]
fn sender_resumes_after_cuts_without_gaps_or_duplicates() {
    let d = tmp("send");
    let key = Arc::new(DeviceKey::generate());
    let wal = Arc::new(Wal::open(&d, "s", &EphemeralKey::new(), false).unwrap());
    let server = Arc::new(FakeServer {
        public_key: key.public_key(),
        ..Default::default()
    });
    let cfg = StreamConfig {
        stream_id: "s".into(),
        dtype: Dtype::Float32,
        n_channels: 4,
        chunk_samples: 10,
        sfreq: None,
    };
    let mut w = StreamWriter::new(cfg, key.clone(), wal.clone()).unwrap();
    let mut scfg = SenderConfig::new("tn", "dev", "s");
    scfg.batch_max = 3;
    scfg.linger = Duration::from_millis(5);
    scfg.backoff_min = Duration::from_millis(1);
    scfg.backoff_max = Duration::from_millis(5);
    let sender = Arc::new(Sender::new(scfg, key.clone(), wal.clone()));
    let (s2, srv) = (sender.clone(), server.clone());
    let th = std::thread::spawn(move || s2.run(&*srv));
    let total = 237usize;
    let mut sent = 0;
    while sent < total {
        let n = (total - sent).min(13);
        let ts: Vec<f64> = (sent..sent + n)
            .map(|i| 100.0 + i as f64 / 1000.0)
            .collect();
        w.add_clock_offset(ts[0], 0.0015);
        w.add_local_clock(ts[0], 5.0 + ts[0]);
        w.push(&f32s(sent, n, 4), &ts).unwrap();
        sent += n;
        if sent % 52 == 0 {
            server.drop_next.store(2, Ordering::SeqCst); // cut the next two calls
        }
        std::thread::sleep(Duration::from_millis(2));
    }
    w.flush().unwrap();
    server.drop_next.store(1, Ordering::SeqCst);
    for _ in 0..500 {
        if wal.is_empty() {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    sender.stop.store(true, Ordering::SeqCst);
    th.join().unwrap();
    let st = sender.stats();
    assert!(wal.is_empty(), "WAL not drained: {st:?}");
    assert!(st.fatal.is_none() && st.rpc_errors >= 1, "{st:?}");
    let committed = server.committed.lock().unwrap();
    assert_eq!(
        committed.keys().copied().collect::<Vec<_>>(),
        (0..committed.len() as u64).collect::<Vec<_>>()
    );
    let all: Vec<u8> = committed.values().flat_map(|c| c.samples.clone()).collect();
    assert_eq!(all, f32s(0, total, 4));
    let stamps: Vec<f64> = committed
        .values()
        .flat_map(|c| c.lsl_timestamps.clone())
        .collect();
    assert_eq!(
        stamps,
        (0..total)
            .map(|i| 100.0 + i as f64 / 1000.0)
            .collect::<Vec<_>>()
    );
    let n_offsets: usize = committed.values().map(|c| c.clock_offsets.len()).sum();
    assert_eq!(n_offsets, total.div_ceil(13));
    let _ = std::fs::remove_dir_all(&d);
}

fn fast_sender_cfg() -> SenderConfig {
    let mut scfg = SenderConfig::new("tn", "dev", "s");
    scfg.batch_max = 2;
    scfg.linger = Duration::from_millis(5);
    scfg.backoff_min = Duration::from_millis(1);
    scfg.backoff_max = Duration::from_millis(5);
    scfg
}

fn f32_cfg() -> StreamConfig {
    StreamConfig {
        stream_id: "s".into(),
        dtype: Dtype::Float32,
        n_channels: 2,
        chunk_samples: 5,
        sfreq: None,
    }
}

/// Run a sender until the WAL is empty (or ~5 s pass), then stop it.
fn drain(sender: Arc<Sender>, server: Arc<FakeServer>, wal: &Wal) {
    let s2 = sender.clone();
    let th = std::thread::spawn(move || s2.run(&*server));
    for _ in 0..500 {
        if wal.is_empty() || sender.stats().fatal.is_some() {
            break;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    sender.stop.store(true, Ordering::SeqCst);
    th.join().unwrap();
}

/// H4: stream, drain the WAL completely, restart with the same stream_id and WAL directory,
/// write more. Numbering continues past what the server has, so the new records are sent, not
/// deleted by the first resync ack.
#[test]
fn restart_after_full_drain_sends_new_records() {
    let d = tmp("h4-restart");
    let key = Arc::new(DeviceKey::generate());
    let wal_key = [9u8; 32];
    let server = Arc::new(FakeServer {
        public_key: key.public_key(),
        ..Default::default()
    });
    {
        let wal = Arc::new(Wal::open(&d, "s", &StaticKey::new(&wal_key).unwrap(), true).unwrap());
        let mut w = StreamWriter::new(f32_cfg(), key.clone(), wal.clone()).unwrap();
        let ts: Vec<f64> = (0..15).map(|i| i as f64).collect();
        assert_eq!(w.push(&f32s(0, 15, 2), &ts).unwrap(), 3);
        let sender = Arc::new(Sender::new(fast_sender_cfg(), key.clone(), wal.clone()));
        drain(sender.clone(), server.clone(), &wal);
        assert!(wal.is_empty(), "{:?}", sender.stats());
        assert_eq!(wal.next_seq(), 3);
    }
    assert_eq!(server.next_seq(), 3);
    // process restart: the drained WAL still knows where numbering stopped
    let wal = Arc::new(Wal::open(&d, "s", &StaticKey::new(&wal_key).unwrap(), true).unwrap());
    assert!(wal.is_empty());
    assert_eq!(wal.next_seq(), 3);
    let mut w = StreamWriter::new(f32_cfg(), key.clone(), wal.clone()).unwrap();
    assert_eq!(w.next_seq(), 3);
    let ts: Vec<f64> = (15..25).map(|i| i as f64).collect();
    assert_eq!(w.push(&f32s(15, 10, 2), &ts).unwrap(), 2);
    assert_eq!(wal.pending(0), vec![3, 4]);
    let sender = Arc::new(Sender::new(fast_sender_cfg(), key.clone(), wal.clone()));
    drain(sender.clone(), server.clone(), &wal);
    let st = sender.stats();
    assert!(st.fatal.is_none(), "{st:?}");
    assert!(wal.is_empty(), "{st:?}");
    let committed = server.committed.lock().unwrap();
    assert_eq!(
        committed.keys().copied().collect::<Vec<_>>(),
        vec![0, 1, 2, 3, 4]
    );
    let all: Vec<u8> = committed.values().flat_map(|c| c.samples.clone()).collect();
    assert_eq!(all, f32s(0, 25, 2));
    drop(committed);
    let _ = std::fs::remove_dir_all(&d);
}

/// Scripted transport: fixed server state; `stream_chunks` acks a fixed `next_seq`.
struct Scripted {
    state_next: u64,
    ack_next: u64,
    sent: Mutex<Vec<u64>>,
}

impl IngestTransport for Scripted {
    fn get_stream_state(&self, _: Vec<u8>, _: &str, _: Duration) -> Result<Vec<u8>, RpcError> {
        Ok(StreamState {
            stream_id: "s".into(),
            next_seq: self.state_next,
            state: "open".into(),
            ..Default::default()
        }
        .encode())
    }
    fn stream_chunks(
        &self,
        chunks: Vec<Vec<u8>>,
        _: &str,
        _: Duration,
    ) -> Result<Vec<u8>, RpcError> {
        let mut sent = self.sent.lock().unwrap();
        for raw in chunks {
            sent.push(Chunk::decode(&raw).unwrap().seq);
        }
        Ok(StreamAck {
            stream_id: "s".into(),
            next_seq: self.ack_next,
            ..Default::default()
        }
        .encode())
    }
    fn finish_stream(&self, _: Vec<u8>, _: &str, _: Duration) -> Result<Vec<u8>, RpcError> {
        unreachable!()
    }
}

/// Run the sender until it stops by itself, or stop it after 3 s (so a regression that makes it
/// loop instead of failing shows up as a failed assertion, not a hung test).
fn run_bounded(sender: &Sender, t: &Scripted) {
    let stop = sender.stop.clone();
    std::thread::scope(|sc| {
        let done = Arc::new(std::sync::atomic::AtomicBool::new(false));
        let d2 = done.clone();
        sc.spawn(move || {
            for _ in 0..300 {
                if d2.load(Ordering::SeqCst) {
                    return;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
            stop.store(true, Ordering::SeqCst);
        });
        sender.run(t);
        done.store(true, Ordering::SeqCst);
    });
}

fn wal_with_records(name: &str, n: usize) -> (PathBuf, Arc<Wal>, Arc<DeviceKey>) {
    let d = tmp(name);
    let key = Arc::new(DeviceKey::generate());
    let wal = Arc::new(Wal::open(&d, "s", &EphemeralKey::new(), false).unwrap());
    let mut w = StreamWriter::new(f32_cfg(), key.clone(), wal.clone()).unwrap();
    let ts: Vec<f64> = (0..n * 5).map(|i| i as f64).collect();
    assert_eq!(w.push(&f32s(0, n * 5, 2), &ts).unwrap(), n);
    (d, wal, key)
}

/// H4: a server acking past what was actually sent is rejected (fatal) and deletes nothing.
#[test]
fn ack_beyond_last_sent_is_rejected_not_applied() {
    let (d, wal, key) = wal_with_records("h4-ack", 5);
    let t = Scripted {
        state_next: 0,
        ack_next: 100,
        sent: Mutex::new(vec![]),
    };
    let sender = Sender::new(fast_sender_cfg(), key, wal.clone());
    run_bounded(&sender, &t);
    let st = sender.stats();
    let fatal = st.fatal.expect("fatal");
    assert!(fatal.contains("15") && fatal.contains("acked"), "{fatal}");
    assert_eq!(*t.sent.lock().unwrap(), vec![0, 1]); // one batch went out
    assert_eq!(wal.pending(0), vec![0, 1, 2, 3, 4]); // nothing deleted, unsent kept
    assert_eq!(st.chunks_acked, 0);
    let _ = std::fs::remove_dir_all(&d);
}

/// H4: a server that already holds seqs this WAL never produced (stream_id reused with a fresh
/// WAL) stops the sender instead of deleting the local, never-sent records below its next_seq.
#[test]
fn server_ahead_of_wal_high_water_mark_is_fatal() {
    let (d, wal, key) = wal_with_records("h4-reuse", 3);
    assert_eq!(wal.next_seq(), 3);
    let t = Scripted {
        state_next: 10,
        ack_next: 10,
        sent: Mutex::new(vec![]),
    };
    let sender = Sender::new(fast_sender_cfg(), key, wal.clone());
    run_bounded(&sender, &t);
    let fatal = sender.stats().fatal.expect("fatal");
    assert!(fatal.contains("high-water"), "{fatal}");
    assert!(t.sent.lock().unwrap().is_empty());
    assert_eq!(wal.pending(0), vec![0, 1, 2]);
    let _ = std::fs::remove_dir_all(&d);
}

/// M9: the signature does not cover the samples; `verify_chunk_full` also recomputes chunk_id.
#[test]
fn verify_chunk_full_detects_tampered_samples() {
    let (d, wal, key) = wal_with_records("m9", 1);
    let c = Chunk::decode(&wal.read(0).unwrap()).unwrap();
    let pk = key.public_key();
    assert!(sign::verify_chunk(&c, &pk) && sign::verify_chunk_full(&c, &pk));
    let mut t = c.clone();
    t.samples[3] ^= 0x40;
    assert!(sign::verify_chunk(&t, &pk), "signature alone misses it");
    assert!(!sign::verify_chunk_full(&t, &pk));
    let mut t = c.clone();
    t.samples.pop();
    assert!(!sign::verify_chunk_full(&t, &pk));
    let mut t = c.clone();
    t.dtype = "int8".into();
    assert!(!sign::verify_chunk_full(&t, &pk));
    let mut t = c.clone();
    t.dtype = "complex64".into();
    assert!(!sign::verify_chunk_full(&t, &pk));
    assert!(!sign::verify_chunk_full(
        &c,
        &DeviceKey::generate().public_key()
    ));
    let _ = std::fs::remove_dir_all(&d);
}

#[test]
fn fatal_error_stops_the_sender() {
    struct Deny;
    impl IngestTransport for Deny {
        fn get_stream_state(&self, _: Vec<u8>, _: &str, _: Duration) -> Result<Vec<u8>, RpcError> {
            Err(RpcError {
                code: code::UNAUTHENTICATED,
                message: "no".into(),
            })
        }
        fn stream_chunks(
            &self,
            _: Vec<Vec<u8>>,
            _: &str,
            _: Duration,
        ) -> Result<Vec<u8>, RpcError> {
            unreachable!()
        }
        fn finish_stream(&self, _: Vec<u8>, _: &str, _: Duration) -> Result<Vec<u8>, RpcError> {
            unreachable!()
        }
    }
    let d = tmp("fatal");
    let wal = Arc::new(Wal::open(&d, "s", &EphemeralKey::new(), false).unwrap());
    let s = Sender::new(
        SenderConfig::new("t", "d", "s"),
        Arc::new(DeviceKey::generate()),
        wal,
    );
    s.run(&Deny);
    assert!(s.stats().fatal.unwrap().contains("16"));
    let _ = std::fs::remove_dir_all(&d);
}

#[test]
fn writer_rejects_bad_config_and_input() {
    let d = tmp("cfg");
    let wal = Arc::new(Wal::open(&d, "s", &EphemeralKey::new(), false).unwrap());
    let key = Arc::new(DeviceKey::generate());
    let mk = |dtype, ch, cs| {
        StreamWriter::new(
            StreamConfig {
                stream_id: "s".into(),
                dtype,
                n_channels: ch,
                chunk_samples: cs,
                sfreq: None,
            },
            key.clone(),
            wal.clone(),
        )
    };
    assert!(mk(Dtype::Uint8, 1, 1).is_err());
    assert!(mk(Dtype::Int16, 0, 1).is_err());
    assert!(mk(Dtype::Int16, 1000, 1001).is_err());
    let mut w = mk(Dtype::Int16, 2, 3).unwrap();
    assert!(w.push(&[0; 3], &[1.0]).is_err());
    assert!(w.push(&[0; 4], &[f64::NAN]).is_err());
    let _ = std::fs::remove_dir_all(&d);
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 32, ..ProptestConfig::default() })]

    /// Buffering: any sequence of push sizes yields contiguous seqs, full-size chunks except the
    /// last, the exact input bytes/timestamps in order, valid IDs and signatures; acking any
    /// prefix leaves exactly the remaining records.
    #[test]
    fn buffering_preserves_every_sample(pushes in prop::collection::vec(0usize..40, 1..12), chunk in 1u32..17, ack_at in 0u64..40) {
        let d = tmp("prop");
        let wal = Arc::new(Wal::open(&d, "p", &EphemeralKey::new(), false).unwrap());
        let key = Arc::new(DeviceKey::generate());
        let mut w = StreamWriter::new(StreamConfig { stream_id: "p".into(), dtype: Dtype::Int32, n_channels: 3, chunk_samples: chunk, sfreq: None }, key.clone(), wal.clone()).unwrap();
        let mut start = 0usize;
        let mut want = Vec::new();
        for n in &pushes {
            let data: Vec<u8> = (start..start + n).flat_map(|i| (0..3).map(move |c| (i * 3 + c) as i32)).flat_map(i32::to_le_bytes).collect();
            let ts: Vec<f64> = (start..start + n).map(|i| i as f64 * 0.004).collect();
            want.extend_from_slice(&data);
            w.push(&data, &ts).unwrap();
            start += n;
        }
        w.flush().unwrap();
        let seqs = wal.pending(0);
        let total = start;
        prop_assert_eq!(seqs.clone(), (0..total.div_ceil(chunk as usize) as u64).collect::<Vec<_>>());
        let mut got = Vec::new();
        let mut stamps = Vec::new();
        for (i, s) in seqs.iter().enumerate() {
            let c = proto::Chunk::decode(&wal.read(*s).unwrap()).unwrap();
            if i + 1 < seqs.len() { prop_assert_eq!(c.n_samples, chunk); }
            prop_assert!(sign::verify_chunk_full(&c, &key.public_key()));
            prop_assert_eq!(ids::chunk_id(Dtype::Int32, &[u64::from(c.n_samples), 3], &c.samples).unwrap(), c.chunk_id.clone());
            got.extend_from_slice(&c.samples);
            stamps.extend_from_slice(&c.lsl_timestamps);
        }
        prop_assert_eq!(got, want);
        prop_assert_eq!(stamps, (0..total).map(|i| i as f64 * 0.004).collect::<Vec<_>>());
        wal.ack(ack_at).unwrap();
        prop_assert_eq!(wal.pending(0), seqs.into_iter().filter(|s| *s >= ack_at).collect::<Vec<_>>());
        let _ = std::fs::remove_dir_all(&d);
    }

    #[test]
    fn chunk_protobuf_round_trips(seq in any::<u64>(), n in 1u32..5, ts in prop::collection::vec(any::<f64>(), 0..5), sig in prop::collection::vec(any::<u8>(), 0..70)) {
        let c = Chunk { stream_id: "x".into(), seq, n_samples: n, n_channels: 1, dtype: "int16".into(), samples: vec![1; 2 * n as usize], lsl_timestamps: ts, chunk_id: "c".into(), signature: sig, ..Default::default() };
        let back = Chunk::decode(&c.encode()).unwrap();
        prop_assert_eq!(back.encode(), c.encode());
    }
}

#[test]
fn signing_payload_is_canonical_json() {
    let c = Chunk {
        stream_id: "s".into(),
        seq: 3,
        n_samples: 1,
        n_channels: 1,
        dtype: "int16".into(),
        samples: vec![0, 0],
        lsl_timestamps: vec![12.0],
        chunk_id: "chunk:sha256:ab".into(),
        ..Default::default()
    };
    let p = sign::signing_payload(&c).unwrap();
    let (tag, body) = p.split_at(sign::TAG_CHUNK_SIG.len() + 1);
    assert_eq!(tag, b"nf.stream-chunk.v1\0");
    let text = std::str::from_utf8(body).unwrap();
    assert_eq!(cjson::canonicalize_text(text).unwrap(), body);
    assert!(text.contains(r#""t_first":12,"t_last":12"#));
}

proptest! {
    #![proptest_config(ProptestConfig { cases: 256, ..ProptestConfig::default() })]

    /// SEC-062 (short, local): the protobuf decoders never panic on hostile bytes.
    #[test]
    fn decoders_never_panic(bytes in prop::collection::vec(any::<u8>(), 0..256)) {
        let _ = Chunk::decode(&bytes);
        let _ = StreamAck::decode(&bytes);
        let _ = StreamState::decode(&bytes);
    }
}
