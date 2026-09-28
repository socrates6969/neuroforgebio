"""nf_channel_estimator: distinct-channel count estimator for projected-field (PF) maps.

Research use only. Not a medical device. Computational analysis of projected-field maps; not a
stimulation protocol. Clinical use requires an IRB/FDA-approved study.

Typed API::

    from nf_channel_estimator import EstimateParams, estimate, load_map

    result = estimate(load_map("map.json"), EstimateParams(m=2, survival=0.62))
    result.k_digit("R1"), result.p_k_at_least(4)
    doc = result.to_dict()  # JSON document, schema nf.channel-estimate/v1

See docs/features/channel-estimator.md.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .estimate import (  # noqa: E402
    NOTICE,
    OUTPUT_SCHEMA_ID,
    EstimateParams,
    EstimateResult,
    ParameterError,
    estimate,
)
from .pfmap import (  # noqa: E402
    SCHEMA_ID,
    Electrode,
    PFMap,
    PFMapError,
    PFMapReadError,
    from_csv_text,
    from_document,
    from_json_text,
    load_map,
)

__all__ = [
    "NOTICE",
    "OUTPUT_SCHEMA_ID",
    "SCHEMA_ID",
    "Electrode",
    "EstimateParams",
    "EstimateResult",
    "PFMap",
    "PFMapError",
    "PFMapReadError",
    "ParameterError",
    "__version__",
    "estimate",
    "from_csv_text",
    "from_document",
    "from_json_text",
    "load_map",
]
