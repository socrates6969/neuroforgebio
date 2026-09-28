"""Signed webhooks (BUILD-GUIDE 4.6; BLUEPRINT §4.1; SEC-045, SEC-076).

- ``payloads``: the outbound event schemas (the only webhook surface; hw-guard scans them, SEC-090).
- ``signing``: HMAC-SHA-256 over ``<timestamp>.<body>``, 5-minute tolerance, several signatures
  during a key rotation.
- ``ssrf``: URL policy; resolve once, refuse private/loopback/link-local/metadata targets, pin the
  address for the connection (DNS-rebinding defence).
- ``service``: endpoints, key rotation with overlap, the delivery queue with exponential backoff.
"""
