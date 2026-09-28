"""neuroforge: the Python SDK on the nf-core Rust core (BLUEPRINT §5, BUILD-GUIDE 4.3).

Illustrative API, subject to change::

    import neuroforge as nf
    rec = nf.open("sub-01_task-motor_eeg.edf")
    run = nf.pipelines.get("eeg-basic@1.0.0").run(rec)
    print(run.provenance.id)          # every parameter, version and input hash

Connection settings come from ``nf.configure(...)`` or the environment (``NF_API_URL``,
``NF_API_TOKEN``, ``NF_SESSION``). Hashing, canonical JSON, retries, the stream write-ahead buffer
and the offline provenance recorder run in nf-core; this package is the idiomatic layer on top.

Data flows device -> SDK -> platform only: nothing in this package sends anything to acquisition
hardware (SEC-090/091).
"""

from __future__ import annotations

from . import canonical, local, pipelines, streaming
from ._native import __version__ as core_version
from .client import Client, NfApiError, configure, get_client
from .recordings import LocalFile, RemoteRecording, open
from .runs import Provenance, Run

__version__ = "0.1.0"

__all__ = [
    "Client",
    "LocalFile",
    "NfApiError",
    "Provenance",
    "RemoteRecording",
    "Run",
    "canonical",
    "configure",
    "core_version",
    "get_client",
    "local",
    "open",
    "pipelines",
    "streaming",
]
