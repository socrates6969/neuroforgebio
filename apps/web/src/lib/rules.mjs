// Law-tracker rows from the jurisdiction RuleSets (BUILD-GUIDE 5.6). Read at BUILD time from
// rules/*.yaml (the same files the platform's classification engine loads), so a changed rule file
// changes /law-tracker at the next build. Plain JS (no TS) so node:test can import it directly.
//
// Validation mirrors services/platform/nf_platform/governance/rules.py where the page depends on
// it (schema names, required fields, review_status values); the content hash itself is checked by
// the platform's loader and its tests. Any problem throws, which fails the build.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import yaml from 'js-yaml';

export const SCHEMA_MANIFEST = 'nf.ruleset/v1';
export const SCHEMA_FILE = 'nf.jurisdiction-rules/v1';
export const REVIEW_STATUSES = ['draft', 'unverified', 'counsel-reviewed'];

const squash = (v) => (v == null ? null : String(v).split(/\s+/).filter(Boolean).join(' '));

function readYaml(dir, name) {
  try {
    return yaml.load(readFileSync(join(dir, name), 'utf8'), { schema: yaml.JSON_SCHEMA });
  } catch (e) {
    throw new Error(`rules/${name}: cannot read (${e.message})`);
  }
}

function need(cond, msg) {
  if (!cond) throw new Error(msg);
}

/**
 * Load the RuleSet in `dir` and return `{ version, contentSha256, rows }`. One row per rule, in
 * manifest order: jurisdiction, citation, effective date, what it covers, review status.
 */
export function loadRuleSet(dir) {
  const man = readYaml(dir, 'ruleset.yaml');
  need(man && man.schema === SCHEMA_MANIFEST, `ruleset.yaml: schema must be ${SCHEMA_MANIFEST}`);
  need(Number.isInteger(man.version) && man.version >= 1, 'ruleset.yaml: version must be >= 1');
  need(Array.isArray(man.files) && man.files.length, 'ruleset.yaml: files missing');
  const rows = [];
  const seen = new Set();
  for (const fname of man.files) {
    const doc = readYaml(dir, String(fname));
    need(doc && doc.schema === SCHEMA_FILE, `${fname}: schema must be ${SCHEMA_FILE}`);
    need(typeof doc.jurisdiction === 'string' && doc.jurisdiction, `${fname}: jurisdiction`);
    for (const [i, r] of (doc.rules || []).entries()) {
      const where = `${fname}: rules[${i}]`;
      for (const k of ['id', 'title', 'instrument', 'status_text', 'citation', 'obligations'])
        need(r && r[k] != null, `${where}: ${k} missing`);
      need(REVIEW_STATUSES.includes(r.review_status), `${where}: bad review_status`);
      need(
        r.effective_date == null || /^\d{4}-\d{2}-\d{2}$/.test(r.effective_date),
        `${where}: effective_date must be YYYY-MM-DD or null`,
      );
      need(r.citation.source, `${where}: citation.source missing`);
      need(!seen.has(r.id), `${where}: duplicate rule id ${r.id}`);
      seen.add(r.id);
      rows.push({
        id: String(r.id),
        jurisdiction: String(doc.jurisdiction),
        jurisdictionName: String(doc.name || doc.jurisdiction),
        title: squash(r.title),
        instrument: squash(r.instrument),
        statusText: squash(r.status_text),
        effectiveDate: r.effective_date ?? null,
        citation: {
          source: squash(r.citation.source),
          grade: squash(r.citation.grade),
          definition: squash(r.citation.definition),
          researchRef: squash(r.citation.research_ref),
        },
        obligations: r.obligations.map((o) => squash(o.text)),
        notes: squash(r.notes),
        reviewStatus: r.review_status,
        // "verified" = the source itself was checked. Counsel review is a separate badge.
        verified: r.review_status !== 'unverified',
      });
    }
  }
  need(rows.length > 0, 'the RuleSet has no rules');
  return { version: man.version, contentSha256: String(man.content_sha256 || ''), rows };
}

/** A DOI in a citation, as an https://doi.org link (the only links derived from rule text). */
export function doiUrl(source) {
  const m = /doi:(10\.[^\s,;]+)/i.exec(source || '');
  return m ? `https://doi.org/${m[1]}` : null;
}
