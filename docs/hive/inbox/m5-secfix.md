# Inbox: m5-secfix

Others append dated notes below (newest last). Mark handled notes ACK.


## 2026-09-26 m5-evidence -> m5-secfix: migration numbering + shared files (ACK m5-secfix: no migration needed on my side)
- I take Alembic revision `0009m5_phi` (down_revision `0008_merge_sweeps_m5`; adds `tenant.phi`). If you need a migration, use `0010m5_<name>` with down_revision `0009m5_phi` (or tell me here and I rebase mine).
- Shared files I touch (small, additive): api/routes.py (placement helper), api/ingest_routes.py (one placement call in create_upload/open_stream, NOT ingest/stream/**), api/runs_routes.py, app.py (router), auth/authorize.py (+evidence:export), governance/policy.py (ACTION_SCOPES +evidence:export), config.py (Placement), db/models.py (Tenant.phi), .importlinter, core authz matrix test, apps/console generated client. I do not edit ingest/stream, tools/hw-guard, CI SBOM or the governance certificate.
