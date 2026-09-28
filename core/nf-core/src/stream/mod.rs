//! Stream ingest, device -> platform only (`proto/ingest/v1/ingest.proto`, BUILD-GUIDE 2.7/4.2).
//!
//! - [`writer::StreamWriter`] (acquisition thread): samples + original timestamps + clock-offset
//!   series + local-clock pairs -> hashed, signed [`proto::Chunk`] -> encrypted [`wal::Wal`].
//! - [`sender::Sender`] (sender thread): WAL -> `IngestService.StreamChunks` over an injected
//!   [`sender::IngestTransport`], resuming from the server's committed `next_seq`.
//!
//! Timing (SEC-093): the acquisition side never waits for the network. Timestamps (SEC-094) are
//! stored exactly as given; nothing here rewrites them.

pub mod keystore;
pub mod proto;
pub mod sender;
pub mod sign;
pub mod wal;
pub mod writer;
