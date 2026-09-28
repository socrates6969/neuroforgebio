//! Data model types shared by every SDK (BLUEPRINT §4 schemas; field names follow the v1 API).
//!
//! Unknown fields are ignored on input, so a newer server does not break an older SDK. Types that
//! are hashed go through [`crate::cjson`], never through `serde_json`'s own output.

use serde::{Deserialize, Serialize};

use crate::ids::Dtype;

/// One channel of a recording (BLUEPRINT §3.2 governance attributes included).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Channel {
    pub name: String,
    pub modality: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub nervous_system: Option<String>,
    pub sampling_rate: f64,
    pub units: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub derived_from_non_neural: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_ref: Option<String>,
}

/// A recording as returned by `GET /v1/recordings/{id}` (subset used by the SDK).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Recording {
    pub id: String,
    #[serde(default)]
    pub session_id: Option<String>,
    #[serde(default)]
    pub label: Option<String>,
    #[serde(default)]
    pub channels: Vec<Channel>,
    #[serde(default)]
    pub classification: Option<String>,
    #[serde(default)]
    pub created_at: Option<String>,
}

/// A block of samples with its timing provenance (SEC-094): the original timestamps, the clock
/// offset series and local clock pairs, never rewritten.
#[derive(Debug, Clone, PartialEq)]
pub struct Segment {
    pub dtype: Dtype,
    pub n_samples: u32,
    pub n_channels: u32,
    /// `n_samples x n_channels`, C order (sample-major), little-endian.
    pub samples: Vec<u8>,
    /// One original timestamp per sample, seconds, sender clock.
    pub timestamps: Vec<f64>,
    /// `(collection_time, offset)`; offset = remote clock - local clock (LSL semantics).
    pub clock_offsets: Vec<(f64, f64)>,
    /// `(lsl_time, monotonic_time)` read at the same instant on the edge device.
    pub local_clock: Vec<(f64, f64)>,
}

impl Segment {
    /// Content ID of the sample array (hashing spec §5.2, shape `[n_samples, n_channels]`).
    pub fn chunk_id(&self) -> Result<String, crate::cjson::CanonError> {
        crate::ids::chunk_id(
            self.dtype,
            &[u64::from(self.n_samples), u64::from(self.n_channels)],
            &self.samples,
        )
    }
}

/// A PROV record inside a provenance batch (hashing spec §5.3; shapes from step 3.1).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum ProvRecord {
    Entity {
        id: String,
        label: String,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        content: Option<String>,
    },
    Activity {
        id: String,
        label: String,
    },
    Agent {
        id: String,
        label: String,
    },
    Edge {
        rel: String,
        from: String,
        to: String,
    },
}

/// PROV relation names accepted in local records.
pub const PROV_RELATIONS: [&str; 5] = [
    "used",
    "wasGeneratedBy",
    "wasDerivedFrom",
    "wasAssociatedWith",
    "wasInformedBy",
];

/// A run artifact (only listed once its provenance is committed).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Artifact {
    pub id: String,
    pub step: String,
    pub name: String,
    pub sha256: String,
    pub size_bytes: u64,
}

/// `RunOut` of `POST /v1/runs` and `GET /v1/runs/{id}` (subset).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Run {
    pub id: String,
    pub pipeline_ref: String,
    pub pipeline_version_id: String,
    pub recording_id: String,
    pub state: String,
    #[serde(default)]
    pub seed: Option<i64>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub prov_activity_id: Option<String>,
    #[serde(default)]
    pub prov_batch_id: Option<String>,
    #[serde(default)]
    pub artifacts: Vec<Artifact>,
}

impl Run {
    /// Terminal states never change again.
    pub fn is_terminal(&self) -> bool {
        matches!(self.state.as_str(), "succeeded" | "failed" | "cancelled")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn run_from_api_json_ignores_unknown_fields() {
        let j = r#"{"id":"r1","pipeline_ref":"eeg-basic@1.2.0","pipeline_version_id":"pv:sha256:00",
            "recording_id":"x","state":"succeeded","seed":1,"record":{"a":1},
            "prov_activity_id":"p","prov_batch_id":null,"artifacts":[],"new_field":true}"#;
        let r: Run = serde_json::from_str(j).unwrap();
        assert!(r.is_terminal() && r.prov_activity_id.as_deref() == Some("p"));
    }

    #[test]
    fn prov_record_shape() {
        let r = ProvRecord::Edge {
            rel: "used".into(),
            from: "a".into(),
            to: "b".into(),
        };
        let v = serde_json::to_value(&r).unwrap();
        assert_eq!(
            v,
            serde_json::json!({"type":"edge","rel":"used","from":"a","to":"b"})
        );
    }
}
