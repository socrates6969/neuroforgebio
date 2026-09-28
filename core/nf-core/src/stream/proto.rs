//! Hand-written protobuf (proto3) encoding for `proto/ingest/v1/ingest.proto`. The messages are
//! small and fixed, so this avoids a protobuf code generator and its build dependencies. The
//! decoder skips unknown fields and accepts packed and unpacked `repeated double`.

#[derive(Debug, Clone, PartialEq, Default)]
pub struct ClockOffset {
    pub collection_time: f64,
    pub offset: f64,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct LocalClockSample {
    pub lsl_time: f64,
    pub monotonic_time: f64,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Chunk {
    pub stream_id: String,
    pub seq: u64,
    pub n_samples: u32,
    pub n_channels: u32,
    pub dtype: String,
    pub samples: Vec<u8>,
    pub lsl_timestamps: Vec<f64>,
    pub clock_offsets: Vec<ClockOffset>,
    pub local_clock: Vec<LocalClockSample>,
    pub chunk_id: String,
    pub signature: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct StreamAck {
    pub stream_id: String,
    pub next_seq: u64,
    pub accepted: u32,
    pub duplicates: u32,
    pub suspect: u32,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct StreamState {
    pub stream_id: String,
    pub next_seq: u64,
    pub n_samples: u64,
    pub state: String,
    pub suspect: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DecodeError(pub &'static str);

impl std::fmt::Display for DecodeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "protobuf decode: {}", self.0)
    }
}
impl std::error::Error for DecodeError {}

// ---------------------------------------------------------------- encoding
fn varint(out: &mut Vec<u8>, mut v: u64) {
    while v >= 0x80 {
        out.push((v as u8) | 0x80);
        v >>= 7;
    }
    out.push(v as u8);
}
fn key(out: &mut Vec<u8>, field: u32, wire: u8) {
    varint(out, (u64::from(field) << 3) | u64::from(wire));
}
fn put_uint(out: &mut Vec<u8>, field: u32, v: u64) {
    if v != 0 {
        key(out, field, 0);
        varint(out, v);
    }
}
fn put_bytes(out: &mut Vec<u8>, field: u32, v: &[u8]) {
    if !v.is_empty() {
        key(out, field, 2);
        varint(out, v.len() as u64);
        out.extend_from_slice(v);
    }
}
fn put_double(out: &mut Vec<u8>, field: u32, v: f64) {
    if v.to_bits() != 0 {
        key(out, field, 1);
        out.extend_from_slice(&v.to_le_bytes());
    }
}
fn put_packed_doubles(out: &mut Vec<u8>, field: u32, v: &[f64]) {
    if !v.is_empty() {
        key(out, field, 2);
        varint(out, (v.len() * 8) as u64);
        for x in v {
            out.extend_from_slice(&x.to_le_bytes());
        }
    }
}
fn put_message(out: &mut Vec<u8>, field: u32, body: &[u8]) {
    key(out, field, 2);
    varint(out, body.len() as u64);
    out.extend_from_slice(body);
}

impl Chunk {
    pub fn encode(&self) -> Vec<u8> {
        let mut o = Vec::with_capacity(self.samples.len() + self.lsl_timestamps.len() * 8 + 256);
        put_bytes(&mut o, 1, self.stream_id.as_bytes());
        put_uint(&mut o, 2, self.seq);
        put_uint(&mut o, 3, u64::from(self.n_samples));
        put_uint(&mut o, 4, u64::from(self.n_channels));
        put_bytes(&mut o, 5, self.dtype.as_bytes());
        put_bytes(&mut o, 6, &self.samples);
        put_packed_doubles(&mut o, 7, &self.lsl_timestamps);
        for c in &self.clock_offsets {
            let mut m = Vec::with_capacity(18);
            put_double(&mut m, 1, c.collection_time);
            put_double(&mut m, 2, c.offset);
            put_message(&mut o, 8, &m);
        }
        for c in &self.local_clock {
            let mut m = Vec::with_capacity(18);
            put_double(&mut m, 1, c.lsl_time);
            put_double(&mut m, 2, c.monotonic_time);
            put_message(&mut o, 9, &m);
        }
        put_bytes(&mut o, 10, self.chunk_id.as_bytes());
        put_bytes(&mut o, 11, &self.signature);
        o
    }

    pub fn decode(buf: &[u8]) -> Result<Self, DecodeError> {
        let mut c = Chunk::default();
        let mut r = Reader { b: buf, i: 0 };
        while let Some((field, wire)) = r.key()? {
            match (field, wire) {
                (1, 2) => c.stream_id = r.string()?,
                (2, 0) => c.seq = r.varint()?,
                (3, 0) => c.n_samples = r.varint()? as u32,
                (4, 0) => c.n_channels = r.varint()? as u32,
                (5, 2) => c.dtype = r.string()?,
                (6, 2) => c.samples = r.bytes()?.to_vec(),
                (7, 2) => c.lsl_timestamps.extend(r.packed_doubles()?),
                (7, 1) => c.lsl_timestamps.push(r.double()?),
                (8, 2) => {
                    let (a, b) = pair(r.bytes()?)?;
                    c.clock_offsets.push(ClockOffset {
                        collection_time: a,
                        offset: b,
                    });
                }
                (9, 2) => {
                    let (a, b) = pair(r.bytes()?)?;
                    c.local_clock.push(LocalClockSample {
                        lsl_time: a,
                        monotonic_time: b,
                    });
                }
                (10, 2) => c.chunk_id = r.string()?,
                (11, 2) => c.signature = r.bytes()?.to_vec(),
                (_, w) => r.skip(w)?,
            }
        }
        Ok(c)
    }
}

fn pair(body: &[u8]) -> Result<(f64, f64), DecodeError> {
    let mut r = Reader { b: body, i: 0 };
    let (mut a, mut b) = (0.0, 0.0);
    while let Some((field, wire)) = r.key()? {
        match (field, wire) {
            (1, 1) => a = r.double()?,
            (2, 1) => b = r.double()?,
            (_, w) => r.skip(w)?,
        }
    }
    Ok((a, b))
}

/// `StreamStateRequest` / `FinishStreamRequest` (both: `string stream_id = 1`).
pub fn encode_stream_id_request(stream_id: &str) -> Vec<u8> {
    let mut o = Vec::new();
    put_bytes(&mut o, 1, stream_id.as_bytes());
    o
}

impl StreamAck {
    pub fn decode(buf: &[u8]) -> Result<Self, DecodeError> {
        let mut a = StreamAck::default();
        let mut r = Reader { b: buf, i: 0 };
        while let Some((field, wire)) = r.key()? {
            match (field, wire) {
                (1, 2) => a.stream_id = r.string()?,
                (2, 0) => a.next_seq = r.varint()?,
                (3, 0) => a.accepted = r.varint()? as u32,
                (4, 0) => a.duplicates = r.varint()? as u32,
                (5, 0) => a.suspect = r.varint()? as u32,
                (_, w) => r.skip(w)?,
            }
        }
        Ok(a)
    }
    pub fn encode(&self) -> Vec<u8> {
        let mut o = Vec::new();
        put_bytes(&mut o, 1, self.stream_id.as_bytes());
        put_uint(&mut o, 2, self.next_seq);
        put_uint(&mut o, 3, u64::from(self.accepted));
        put_uint(&mut o, 4, u64::from(self.duplicates));
        put_uint(&mut o, 5, u64::from(self.suspect));
        o
    }
}

impl StreamState {
    pub fn decode(buf: &[u8]) -> Result<Self, DecodeError> {
        let mut s = StreamState::default();
        let mut r = Reader { b: buf, i: 0 };
        while let Some((field, wire)) = r.key()? {
            match (field, wire) {
                (1, 2) => s.stream_id = r.string()?,
                (2, 0) => s.next_seq = r.varint()?,
                (3, 0) => s.n_samples = r.varint()?,
                (4, 2) => s.state = r.string()?,
                (5, 0) => s.suspect = r.varint()? != 0,
                (_, w) => r.skip(w)?,
            }
        }
        Ok(s)
    }
    pub fn encode(&self) -> Vec<u8> {
        let mut o = Vec::new();
        put_bytes(&mut o, 1, self.stream_id.as_bytes());
        put_uint(&mut o, 2, self.next_seq);
        put_uint(&mut o, 3, self.n_samples);
        put_bytes(&mut o, 4, self.state.as_bytes());
        put_uint(&mut o, 5, u64::from(self.suspect));
        o
    }
}

// ---------------------------------------------------------------- decoding
struct Reader<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> Reader<'a> {
    fn varint(&mut self) -> Result<u64, DecodeError> {
        let mut v = 0u64;
        for shift in (0..64).step_by(7) {
            let byte = *self.b.get(self.i).ok_or(DecodeError("truncated varint"))?;
            self.i += 1;
            v |= u64::from(byte & 0x7f) << shift;
            if byte < 0x80 {
                return Ok(v);
            }
        }
        Err(DecodeError("varint too long"))
    }
    fn key(&mut self) -> Result<Option<(u32, u8)>, DecodeError> {
        if self.i >= self.b.len() {
            return Ok(None);
        }
        let k = self.varint()?;
        let field = u32::try_from(k >> 3).map_err(|_| DecodeError("field number"))?;
        if field == 0 {
            return Err(DecodeError("field number 0"));
        }
        Ok(Some((field, (k & 7) as u8)))
    }
    fn bytes(&mut self) -> Result<&'a [u8], DecodeError> {
        let n = usize::try_from(self.varint()?).map_err(|_| DecodeError("length"))?;
        let end = self.i.checked_add(n).ok_or(DecodeError("length"))?;
        let s = self
            .b
            .get(self.i..end)
            .ok_or(DecodeError("truncated field"))?;
        self.i = end;
        Ok(s)
    }
    fn string(&mut self) -> Result<String, DecodeError> {
        String::from_utf8(self.bytes()?.to_vec()).map_err(|_| DecodeError("string is not UTF-8"))
    }
    fn double(&mut self) -> Result<f64, DecodeError> {
        let s = self
            .b
            .get(self.i..self.i + 8)
            .ok_or(DecodeError("truncated double"))?;
        self.i += 8;
        Ok(f64::from_le_bytes(s.try_into().expect("8 bytes")))
    }
    fn packed_doubles(&mut self) -> Result<Vec<f64>, DecodeError> {
        let s = self.bytes()?;
        if s.len() % 8 != 0 {
            return Err(DecodeError("packed doubles length"));
        }
        Ok(s.as_chunks::<8>()
            .0
            .iter()
            .map(|c| f64::from_le_bytes(*c))
            .collect())
    }
    fn skip(&mut self, wire: u8) -> Result<(), DecodeError> {
        match wire {
            0 => {
                self.varint()?;
            }
            1 => {
                self.i = self
                    .i
                    .checked_add(8)
                    .filter(|e| *e <= self.b.len())
                    .ok_or(DecodeError("truncated"))?
            }
            2 => {
                self.bytes()?;
            }
            5 => {
                self.i = self
                    .i
                    .checked_add(4)
                    .filter(|e| *e <= self.b.len())
                    .ok_or(DecodeError("truncated"))?
            }
            _ => return Err(DecodeError("unsupported wire type")),
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chunk_roundtrip_and_unknown_fields() {
        let c = Chunk {
            stream_id: "s".into(),
            seq: 300,
            n_samples: 2,
            n_channels: 1,
            dtype: "int16".into(),
            samples: vec![1, 0, 2, 0],
            lsl_timestamps: vec![1.5, 2.5],
            clock_offsets: vec![ClockOffset {
                collection_time: 1.0,
                offset: 0.0015,
            }],
            local_clock: vec![LocalClockSample {
                lsl_time: 2.5,
                monotonic_time: 9.0,
            }],
            chunk_id: "chunk:sha256:00".into(),
            signature: vec![7; 64],
        };
        let mut b = c.encode();
        b.extend_from_slice(&[0xa0, 0x06, 0x01]); // field 100 varint 1 (unknown)
        assert_eq!(Chunk::decode(&b).unwrap(), c);
        assert!(Chunk::decode(&b[..b.len() - 5]).is_err());
    }

    #[test]
    fn ack_and_state() {
        let a = StreamAck {
            stream_id: "s".into(),
            next_seq: 5,
            accepted: 5,
            duplicates: 0,
            suspect: 1,
        };
        assert_eq!(StreamAck::decode(&a.encode()).unwrap(), a);
        let s = StreamState {
            stream_id: "s".into(),
            next_seq: 3,
            n_samples: 300,
            state: "open".into(),
            suspect: false,
        };
        assert_eq!(StreamState::decode(&s.encode()).unwrap(), s);
        assert_eq!(encode_stream_id_request("ab"), vec![0x0a, 2, b'a', b'b']);
    }
}
