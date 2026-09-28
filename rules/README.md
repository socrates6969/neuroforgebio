# rules

Jurisdiction RuleSets as versioned YAML (BUILD-GUIDE 5.2, BLUEPRINT §8.2). **Not legal advice.**

- `ruleset.yaml`: the manifest (`version`, the jurisdiction files, `content_sha256`). The loader
  (`services/platform/nf_platform/governance/rules.py`) refuses the RuleSet when a rule changed but
  the hash did not: every change needs a new version and a new hash
  (`.venv/Scripts/python -m nf_platform.governance.rules_hash`).
- `co.yaml`, `ca.yaml`, `ct.yaml`, `mt.yaml`, `eu.yaml`: one file per jurisdiction. Every rule has a
  citation, an effective date (null when `market/regulation.md` states none), a predicate over the
  channel attributes (`nervous_system`, `derived_from_non_neural`, `modality`), obligations and a
  `review_status`.
- Facts come only from `market/regulation.md` (a test checks that every quoted definition appears
  there verbatim).
- `review_status`: `draft` (encoded, not reviewed), `unverified` (the source itself is not verified:
  Montana, no predicate, reported as "not evaluated"), `counsel-reviewed` (only with a reviewer record
  `review: {reviewer, reviewed_on, record}`). Counsel review is an owner action; nothing here is
  counsel-reviewed.
- The engine never outputs "not regulated", only "not matched by RuleSet vN".
