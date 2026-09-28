"""Edge SDK prototype for stream ingest (BUILD-GUIDE 2.7). nf-core replaces it in step 4.2.

Pieces:

- ``source``: where samples come from. ``SyntheticSource`` (deterministic, paced in real time) and
  ``LslSource`` (an LSL *inlet* via pylsl; SEC-091: this package never creates outlets).
- ``wal``: the local write-ahead log. Every chunk is sealed with AES-256-GCM before it touches the
  disk (SEC-037) and deleted once the server has acknowledged it.
- ``client``: ``EdgeClient``. The acquisition thread only reads the source and appends to the WAL;
  it never waits for the network (SEC-093). The sender thread replays the WAL to
  ``IngestService.StreamChunks`` and resumes from the server's committed ``next_seq`` after any
  disconnect. Nothing is ever sent towards the device (SEC-090).
"""
