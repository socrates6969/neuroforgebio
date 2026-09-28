// sbom-props: zero-dependency CycloneDX post-processor (SEC-083; FDA Feb 2026 guidance, CRA Annex I Part II).
// Every component (nested ones included) must carry the properties
//   nfb:supportLevel  = maintained | unmaintained | abandoned | unknown
//   nfb:endOfSupport  = YYYY-MM-DD | unknown
// `add` fills missing values from an overrides file (security/support-levels.json) or `unknown`;
// `check` asserts the SBOM is CycloneDX JSON >= 1.6 and that both properties are present and valid.

export const SUPPORT_LEVEL = 'nfb:supportLevel';
export const END_OF_SUPPORT = 'nfb:endOfSupport';
export const LEVELS = ['maintained', 'unmaintained', 'abandoned', 'unknown'];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
export const MIN_SPEC = [1, 6];

function specOk(v) {
  const m = /^(\d+)\.(\d+)$/.exec(String(v || ''));
  if (!m) return false;
  const [maj, min] = [Number(m[1]), Number(m[2])];
  return maj > MIN_SPEC[0] || (maj === MIN_SPEC[0] && min >= MIN_SPEC[1]);
}

/** Yield every component, depth first, with a readable path. */
export function* components(bom) {
  function* rec(list, prefix) {
    for (const [i, c] of (list || []).entries()) {
      const id = c['bom-ref'] || c.purl || `${c.name || '?'}@${c.version || '?'}`;
      const path = `${prefix}[${i}] ${id}`;
      yield { c, path };
      yield* rec(c.components, `${path} >`);
    }
  }
  if (bom.metadata && bom.metadata.component) {
    yield { c: bom.metadata.component, path: 'metadata.component' };
    yield* rec(bom.metadata.component.components, 'metadata.component >');
  }
  yield* rec(bom.components, 'components');
}

const getProp = (c, name) => (c.properties || []).find((p) => p.name === name);

/** Match an overrides entry by purl without version, then by name. */
function lookup(overrides, c) {
  if (!overrides) return null;
  const purl = (c.purl || '').replace(/[?#].*$/, '');
  const bare = purl.replace(/@[^@/]*$/, '');
  return overrides[purl] || overrides[bare] || overrides[c.name] || null;
}

/** Add missing properties in place. Existing values are kept. Returns the number of components touched. */
export function addProps(bom, overrides = null) {
  let touched = 0;
  for (const { c } of components(bom)) {
    const o = lookup(overrides, c) || {};
    c.properties = c.properties || [];
    let t = false;
    if (!getProp(c, SUPPORT_LEVEL)) {
      c.properties.push({ name: SUPPORT_LEVEL, value: o.supportLevel || 'unknown' });
      t = true;
    }
    if (!getProp(c, END_OF_SUPPORT)) {
      c.properties.push({ name: END_OF_SUPPORT, value: o.endOfSupport || 'unknown' });
      t = true;
    }
    if (t) touched++;
  }
  return touched;
}

/**
 * Append components the generator cannot discover (e.g. CI container images pinned by digest in
 * services/platform/docker-compose.ci.yml, SEC-083 / M2-REVIEW MinIO decision). A component whose
 * purl or bom-ref is already present is skipped. Returns the number added.
 */
export function includeComponents(bom, extra) {
  bom.components = bom.components || [];
  const seen = new Set();
  for (const { c } of components(bom)) for (const k of [c.purl, c['bom-ref']]) if (k) seen.add(k);
  let n = 0;
  for (const c of extra || []) {
    const keys = [c.purl, c['bom-ref']].filter(Boolean);
    if (!keys.length) throw new Error(`included component ${c.name || '?'} has no purl or bom-ref`);
    if (keys.some((k) => seen.has(k))) continue;
    bom.components.push(structuredClone(c));
    keys.forEach((k) => seen.add(k));
    n++;
  }
  return n;
}

/** Return a list of problems (empty = valid). */
export function checkBom(bom) {
  const problems = [];
  if (!bom || bom.bomFormat !== 'CycloneDX') problems.push('bomFormat is not "CycloneDX"');
  if (!specOk(bom && bom.specVersion))
    problems.push(`specVersion ${bom && bom.specVersion} < ${MIN_SPEC.join('.')}`);
  let n = 0;
  for (const { c, path } of components(bom || {})) {
    n++;
    const lvl = getProp(c, SUPPORT_LEVEL);
    const eos = getProp(c, END_OF_SUPPORT);
    if (!lvl) problems.push(`${path}: missing ${SUPPORT_LEVEL}`);
    else if (!LEVELS.includes(lvl.value))
      problems.push(`${path}: ${SUPPORT_LEVEL}="${lvl.value}" not in ${LEVELS.join('|')}`);
    if (!eos) problems.push(`${path}: missing ${END_OF_SUPPORT}`);
    else if (eos.value !== 'unknown' && !DATE_RE.test(eos.value))
      problems.push(`${path}: ${END_OF_SUPPORT}="${eos.value}" is not YYYY-MM-DD or unknown`);
  }
  if (n === 0) problems.push('SBOM has no components');
  return problems;
}
