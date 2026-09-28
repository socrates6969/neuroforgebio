// vuln-gate: zero-dependency known-vulnerability gate (SEC-085; FDA KEV expectation, SSDF RV.1).
// Inputs are files produced in CI (network lookups happen only there):
//   pnpm audit --json, pip-audit -f json, cargo audit --json, and the CISA KEV catalogue JSON.
// Rule: FAIL on any finding that is (critical or high or unknown severity) AND has a fix available,
//       and on ANY finding whose id/alias is in CISA KEV (fix or not),
//       unless an OpenVEX statement under security/vex/ says `not_affected` (with a justification or
//       impact statement) or `fixed` for that vulnerability and that package.
// pip-audit reports no severity, so Python findings count as `unknown` (treated like high).

const SEV_ORDER = ['none', 'low', 'moderate', 'high', 'critical'];
const normSev = (s) => {
  const x = String(s || '').toLowerCase();
  if (x === 'medium') return 'moderate';
  return SEV_ORDER.includes(x) ? x : 'unknown';
};

// ---- CVSS v3.x base score (for cargo-audit advisories, which carry only a vector) ----
const W = {
  AV: { N: 0.85, A: 0.62, L: 0.55, P: 0.2 },
  AC: { L: 0.77, H: 0.44 },
  UI: { N: 0.85, R: 0.62 },
  CIA: { H: 0.56, L: 0.22, N: 0 },
};
function roundUp(x) {
  const i = Math.round(x * 100000);
  return i % 10000 === 0 ? i / 100000 : (Math.floor(i / 10000) + 1) / 10;
}
export function cvss3Score(vector) {
  const m = /^CVSS:3\.[01]\/(.*)$/.exec(String(vector || ''));
  if (!m) return null;
  const v = Object.fromEntries(m[1].split('/').map((kv) => kv.split(':')));
  const changed = v.S === 'C';
  const pr = { N: 0.85, L: changed ? 0.68 : 0.62, H: changed ? 0.5 : 0.27 }[v.PR];
  const [av, ac, ui, c, i, a] = [
    W.AV[v.AV],
    W.AC[v.AC],
    W.UI[v.UI],
    W.CIA[v.C],
    W.CIA[v.I],
    W.CIA[v.A],
  ];
  if ([av, ac, pr, ui, c, i, a].some((x) => x === undefined)) return null;
  const iss = 1 - (1 - c) * (1 - i) * (1 - a);
  const impact = changed ? 7.52 * (iss - 0.029) - 3.25 * Math.pow(iss - 0.02, 15) : 6.42 * iss;
  const expl = 8.22 * av * ac * pr * ui;
  if (impact <= 0) return 0;
  return roundUp(Math.min((changed ? 1.08 : 1) * (impact + expl), 10));
}
export function severityFromScore(s) {
  if (s === null || s === undefined) return 'unknown';
  if (s === 0) return 'none';
  if (s < 4) return 'low';
  if (s < 7) return 'moderate';
  if (s < 9) return 'high';
  return 'critical';
}

// ---- normalisers: each returns [{id, aliases, ecosystem, package, version, severity, fixAvailable}] ----
export function fromPnpmAudit(json) {
  const out = [];
  for (const a of Object.values(json.advisories || {})) {
    const versions = [...new Set((a.findings || []).map((f) => f.version).filter(Boolean))];
    const aliases = [
      ...(a.cves || []),
      a.github_advisory_id,
      a.url && a.url.split('/').pop(),
    ].filter(Boolean);
    const fix = !!a.patched_versions && a.patched_versions.trim() !== '<0.0.0';
    for (const version of versions.length ? versions : [null])
      out.push({
        id: a.github_advisory_id || String(a.id),
        aliases: [...new Set(aliases)],
        ecosystem: 'npm',
        package: a.module_name,
        version,
        severity: normSev(a.severity),
        fixAvailable: fix,
      });
  }
  return out;
}

export function fromPipAudit(json) {
  const out = [];
  const deps = Array.isArray(json) ? json : json.dependencies || [];
  for (const d of deps)
    for (const v of d.vulns || [])
      out.push({
        id: v.id,
        aliases: v.aliases || [],
        ecosystem: 'pypi',
        package: d.name,
        version: d.version || null,
        severity: 'unknown',
        fixAvailable: (v.fix_versions || []).length > 0,
      });
  return out;
}

export function fromCargoAudit(json) {
  const list = (json.vulnerabilities && json.vulnerabilities.list) || [];
  return list.map((v) => ({
    id: v.advisory.id,
    aliases: v.advisory.aliases || [],
    ecosystem: 'cargo',
    package: (v.package && v.package.name) || v.advisory.package,
    version: (v.package && v.package.version) || null,
    severity: severityFromScore(cvss3Score(v.advisory.cvss)),
    fixAvailable: ((v.versions && v.versions.patched) || []).length > 0,
  }));
}

export function kevSet(json) {
  return new Set(((json && json.vulnerabilities) || []).map((v) => v.cveID).filter(Boolean));
}

// ---- OpenVEX ----
const PURL_TYPE = { npm: 'npm', pypi: 'pypi', cargo: 'cargo' };
function parsePurl(p) {
  const m = /^pkg:([^/]+)\/(.+?)(?:@([^?#]+))?(?:[?#].*)?$/.exec(String(p || ''));
  if (!m) return null;
  return {
    type: m[1].toLowerCase(),
    name: decodeURIComponent(m[2]).toLowerCase(),
    version: m[3] ? decodeURIComponent(m[3]) : null,
  };
}
function productMatches(product, f) {
  const ids = [product['@id'], ...Object.values(product.identifiers || {})];
  return ids.some((id) => {
    const p = parsePurl(id);
    if (!p || p.type !== PURL_TYPE[f.ecosystem]) return false;
    const name =
      f.ecosystem === 'pypi'
        ? f.package.toLowerCase().replace(/[-_.]+/g, '-')
        : f.package.toLowerCase();
    const pname = f.ecosystem === 'pypi' ? p.name.replace(/[-_.]+/g, '-') : p.name;
    return pname === name && (!p.version || !f.version || p.version === f.version);
  });
}

/** Validate an OpenVEX document; returns a list of problems. */
export function validateVex(doc) {
  const errs = [];
  if (!/^https:\/\/openvex\.dev\/ns/.test(doc['@context'] || ''))
    errs.push('@context is not an OpenVEX namespace');
  for (const k of ['@id', 'author', 'timestamp']) if (!doc[k]) errs.push(`missing ${k}`);
  if (!Array.isArray(doc.statements) || !doc.statements.length) errs.push('no statements');
  for (const [i, s] of (doc.statements || []).entries()) {
    const vname = s.vulnerability && (s.vulnerability.name || s.vulnerability['@id']);
    if (!vname) errs.push(`statement ${i}: missing vulnerability.name`);
    if (!Array.isArray(s.products) || !s.products.length) errs.push(`statement ${i}: no products`);
    if (!['not_affected', 'affected', 'fixed', 'under_investigation'].includes(s.status))
      errs.push(`statement ${i}: bad status ${s.status}`);
    if (s.status === 'not_affected' && !s.justification && !s.impact_statement)
      errs.push(`statement ${i}: not_affected needs a justification or impact_statement`);
  }
  return errs;
}

/** Return the suppressing statement for a finding, or null. */
export function vexFor(finding, vexDocs) {
  const ids = new Set([finding.id, ...finding.aliases].map((x) => String(x).toUpperCase()));
  for (const doc of vexDocs)
    for (const s of doc.statements || []) {
      if (!['not_affected', 'fixed'].includes(s.status)) continue;
      const v = s.vulnerability || {};
      const names = [v.name, v['@id'], ...(v.aliases || [])]
        .filter(Boolean)
        .map((x) => String(x).toUpperCase());
      if (!names.some((n) => ids.has(n))) continue;
      if ((s.products || []).some((p) => productMatches(p, finding))) return s;
    }
  return null;
}

/** Apply the gate. Returns {failures: [{finding, reason}], suppressed: [...], ignored: n}. */
export function gate(findings, kev, vexDocs) {
  const failures = [];
  const suppressed = [];
  let ignored = 0;
  for (const f of findings) {
    const inKev = [f.id, ...f.aliases].some((x) => kev.has(x));
    const blocking = ['critical', 'high', 'unknown'].includes(f.severity) && f.fixAvailable;
    if (!inKev && !blocking) {
      ignored++;
      continue;
    }
    const reason = inKev ? 'listed in CISA KEV' : `${f.severity} severity with a fix available`;
    const s = vexFor(f, vexDocs);
    if (s) suppressed.push({ finding: f, reason, status: s.status });
    else failures.push({ finding: f, reason });
  }
  return { failures, suppressed, ignored };
}
