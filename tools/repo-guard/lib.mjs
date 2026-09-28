// repo-guard: zero-dependency repository policy checks (BUILD-GUIDE 0.2/0.3, BLUEPRINT §8.1).
//   1. no neural-data files tracked (extensions + any `data/` directory) and no tracked file > 5 MB outside
//      tools/synth/fixtures (SEC-087)
//   2. no secrets in tracked files (provider key formats, private keys, tracked .env files)
//   3. every GitHub workflow is `on: workflow_dispatch` only (Actions minutes are owner spend)
//   4. dependency lifecycle scripts run only for an allowlist (APP-L6): root package.json
//      `pnpm.onlyBuiltDependencies` must exist; every lockfile package with `requiresBuild: true` and every
//      installed package with an install script must be on it or on REVIEWED_UNBUILT
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

export const DATA_EXTENSIONS = [
  '.edf',
  '.bdf',
  '.nwb',
  '.xdf',
  '.xdfz',
  '.set',
  '.fdt',
  '.fif',
  '.fif.gz',
  '.vhdr',
  '.vmrk',
  '.eeg',
  '.mat',
  '.npy',
  '.zarr',
  '.gdf',
  '.cnt',
];
const DATA_DIR_SEGMENTS = [/(^|\/)data\//i, /\.zarr\//i, /\.mff\//i];

// The line marker that allowlists a documented example (reviewed in PRs).
export const ALLOW_MARKER = 'repo-guard:allow-secret';

// Patterns are assembled from pieces so this file never matches itself.
const P = (...parts) => new RegExp(parts.join(''));
export const SECRET_PATTERNS = [
  { name: 'aws-access-key-id', re: P('\\b(?:A', 'KIA|A', 'SIA)[0-9A-Z]{16}\\b') },
  {
    name: 'aws-secret-access-key',
    re: P('aws_?secret_?access_?key', '["\']?\\s*[:=]\\s*["\']?[A-Za-z0-9/+=]{40}\\b', ''),
    flags: 'i',
  },
  {
    name: 'private-key',
    re: P('-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIV', 'ATE KEY-----'),
  },
  { name: 'github-token', re: P('\\bgh[pousr]_', '[A-Za-z0-9]{36,}\\b') },
  { name: 'github-fine-grained-token', re: P('\\bgithub_', 'pat_[A-Za-z0-9_]{50,}\\b') },
  { name: 'slack-token', re: P('\\bxox[abprs]', '-[A-Za-z0-9-]{10,}') },
  { name: 'google-api-key', re: P('\\bAI', 'za[0-9A-Za-z_-]{35}\\b') },
  { name: 'stripe-live-key', re: P('\\b[sr]k_', 'live_[0-9a-zA-Z]{20,}\\b') },
  { name: 'anthropic-api-key', re: P('\\bsk-', 'ant-[A-Za-z0-9_-]{20,}') },
  { name: 'openai-api-key', re: P('\\bsk-', '(?:proj-)?[A-Za-z0-9]{32,}\\b') },
].map((p) => ({ ...p, re: new RegExp(p.re.source, p.flags || '') }));

const SECRET_FILES = [
  /(^|\/)\.env(\.[^/]*)?$/,
  /\.(pem|p12|pfx|key)$/i,
  /(^|\/)id_(rsa|ed25519|ecdsa)$/,
];
const SECRET_FILE_ALLOW = [/\.env\.example$/];
const MAX_SCAN_BYTES = 2 * 1024 * 1024;
// SEC-087: any tracked file above this size is rejected, except synthetic fixtures.
export const MAX_FILE_BYTES = 5 * 1024 * 1024;
const LARGE_FILE_ALLOW = [/^tools\/synth\/fixtures\//];

export function checkLargeFile(path, size) {
  const p = path.replace(/\\/g, '/');
  if (size <= MAX_FILE_BYTES || LARGE_FILE_ALLOW.some((re) => re.test(p))) return null;
  return `file is ${(size / 1048576).toFixed(1)} MB (> 5 MB outside tools/synth/fixtures)`;
}

export function trackedFiles(root) {
  const out = execFileSync('git', ['-C', root, 'ls-files', '-z'], {
    encoding: 'utf8',
    maxBuffer: 64 << 20,
  });
  return out.split('\0').filter(Boolean);
}

export function checkDataFile(path) {
  const p = path.replace(/\\/g, '/');
  const lower = p.toLowerCase();
  if (DATA_EXTENSIONS.some((e) => lower.endsWith(e))) return 'neural-data file';
  if (DATA_DIR_SEGMENTS.some((re) => re.test(p))) return 'file under a data directory';
  return null;
}

export function checkSecretFile(path) {
  const p = path.replace(/\\/g, '/');
  if (SECRET_FILE_ALLOW.some((re) => re.test(p))) return null;
  return SECRET_FILES.some((re) => re.test(p)) ? 'secret-bearing file type' : null;
}

/** Scan text for secret patterns. Returns [{line, name}]. */
export function scanSecrets(text) {
  const hits = [];
  const lines = text.split('\n');
  lines.forEach((line, i) => {
    if (line.includes(ALLOW_MARKER)) return;
    for (const p of SECRET_PATTERNS) if (p.re.test(line)) hits.push({ line: i + 1, name: p.name });
  });
  return hits;
}

/** Return the set of triggers declared under the top-level `on:` key of a workflow file. */
export function workflowTriggers(yaml) {
  const lines = yaml.replace(/\r\n/g, '\n').split('\n');
  const idx = lines.findIndex((l) => /^(on|"on"|'on'|true)\s*:/.test(l));
  if (idx < 0) return null;
  const triggers = new Set();
  const inline = lines[idx]
    .replace(/^[^:]*:/, '')
    .replace(/#.*$/, '')
    .trim();
  if (inline) {
    for (const t of inline.replace(/[[\]{}]/g, ' ').split(/[,\s]+/)) {
      const name = t.replace(/:.*$/, '').replace(/["']/g, '');
      if (name) triggers.add(name);
    }
    return triggers;
  }
  let indent = null;
  for (let i = idx + 1; i < lines.length; i++) {
    const l = lines[i];
    if (/^\s*(#.*)?$/.test(l)) continue;
    if (!/^\s/.test(l)) break; // next top-level key
    const ind = l.match(/^\s*/)[0].length;
    if (indent === null) indent = ind;
    if (ind !== indent) continue;
    const m = /^\s*(?:-\s*)?["']?([A-Za-z_]+)["']?\s*:?/.exec(l);
    if (m) triggers.add(m[1]);
  }
  return triggers;
}

export function checkWorkflow(yaml) {
  const t = workflowTriggers(yaml);
  if (!t) return 'no top-level `on:` key';
  const extra = [...t].filter((x) => x !== 'workflow_dispatch');
  if (extra.length) return `non-dispatch trigger(s): ${extra.join(', ')}`;
  if (!t.has('workflow_dispatch')) return 'missing workflow_dispatch';
  return null;
}

// EXC-150-1 condition 4 (ADR 0014): the committed /arena WebAssembly must be exactly the CI build.
// .github/workflows/arena-wasm.yml proves pkg/ == the CI build from pinned source and that the CI hashes
// equal ARENA_MANIFEST; this check runs on every lint, so a hand-edited .wasm/.js (without a CI-verified
// manifest update) fails ordinary CI too.
// Canonical path (lead ruling, final): the glue and module are Vite build assets imported from
// src/assets/arena/pkg/; Vite emits content-hashed copies under /_assets/ with the bytes unchanged
// (nothing arena-related under public/). The manifest lives under security/, so changing it needs the
// security role (CODEOWNERS /security/). No pkg/ = the stub state (/arena without wasm).
export const ARENA_PKG = 'apps/web/src/assets/arena/pkg';
export const ARENA_MANIFEST = 'security/arena-pkg.sha256';
// Nothing arena-related may be served unhashed from public/ (lead + nfb-security checklist item 1).
export const ARENA_PUBLIC = 'apps/web/public/arena';
export const ARENA_FILES = [
  'arena_core.d.ts',
  'arena_core.js',
  'arena_core_bg.wasm',
  'arena_core_bg.wasm.d.ts',
];

/** Parse `sha256sum` output ("<64 hex>  <name>" per line). Returns {entries: Map, bad: [lines]}. */
export function parseSha256Sums(text) {
  const entries = new Map();
  const bad = [];
  for (const line of text.replace(/\r\n/g, '\n').split('\n')) {
    if (!line.trim()) continue;
    const m = /^([0-9a-f]{64}) [ *]([^/\\]+)$/.exec(line);
    if (m && !entries.has(m[2])) entries.set(m[2], m[1]);
    else bad.push(line);
  }
  return { entries, bad };
}

/** Check the committed arena pkg/ against its manifest. Returns [{file, rule, detail}]. */
export function checkArenaPkg(root) {
  const problems = [];
  const dir = join(root, ARENA_PKG);
  const problem = (file, detail) => problems.push({ file, rule: 'arena-pkg', detail });
  const manPath = join(root, ARENA_MANIFEST);
  const pub = join(root, ARENA_PUBLIC);
  if (existsSync(pub) && readdirSync(pub).length)
    problem(
      ARENA_PUBLIC,
      'must not exist: arena assets are Vite build assets from src/assets/arena/pkg/',
    );
  if (!existsSync(dir)) {
    // No pkg/: /arena ships without wasm. A stray manifest would claim a build that is not there.
    if (existsSync(manPath)) problem(ARENA_MANIFEST, `present but ${ARENA_PKG}/ is not committed`);
    return problems;
  }
  if (!existsSync(manPath)) {
    problem(ARENA_MANIFEST, 'missing: pkg/ must ship with the SHA-256 manifest of the CI build');
    return problems;
  }
  const { entries, bad } = parseSha256Sums(readFileSync(manPath, 'utf8'));
  for (const b of bad) problem(ARENA_MANIFEST, `malformed line: ${b}`);
  const names = readdirSync(dir).sort();
  const want = [...ARENA_FILES].sort();
  if (names.join('\n') !== want.join('\n'))
    problem(
      ARENA_PKG,
      `file set must be exactly ${want.join(', ')} (found ${names.join(', ') || 'nothing'})`,
    );
  if ([...entries.keys()].sort().join('\n') !== want.join('\n'))
    problem(ARENA_MANIFEST, `must list exactly ${want.join(', ')}`);
  for (const n of names) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) {
      problem(`${ARENA_PKG}/${n}`, 'unexpected directory');
      continue;
    }
    const got = createHash('sha256').update(readFileSync(p)).digest('hex');
    const exp = entries.get(n);
    if (exp && got !== exp)
      problem(
        `${ARENA_PKG}/${n}`,
        `SHA-256 ${got} does not match the manifest (${exp}): hand-edited?`,
      );
  }
  return problems;
}

// APP-L6: packages whose install scripts were reviewed and are NOT needed (their scripts stay blocked).
// Verified 2026-09-27 with an offline frozen install and `onlyBuiltDependencies: []`: both web builds pass.
//   esbuild: postinstall only validates/copies the binary; the prebuilt optional @esbuild/<platform> is used.
//   sharp:   install only checks for the prebuilt @img/sharp-<platform>; the site uses no astro:assets.
// Adding a package here or to `pnpm.onlyBuiltDependencies` needs a security review (CODEOWNERS).
export const REVIEWED_UNBUILT = ['esbuild', 'sharp'];
const INSTALL_SCRIPTS = ['preinstall', 'install', 'postinstall'];

/** Package name from a pnpm lockfile / virtual-store key (`/@a/b@1.0.0(peer@2)`, `a@1.0.0`, `@a+b@1.0.0_x`). */
export function pnpmKeyName(key) {
  let k = key
    .trim()
    .replace(/^['"]|['"]$/g, '')
    .replace(/^\//, '');
  k = k.replace(/\(.*$/, '');
  if (k.startsWith('@') && !k.slice(0, k.indexOf('@', 1)).includes('/')) k = k.replace('+', '/');
  const at = k.indexOf('@', 1);
  return at > 0 ? k.slice(0, at) : k;
}

/** Names of packages marked `requiresBuild: true` in a pnpm-lock.yaml text. */
export function lockfileBuildPackages(lockText) {
  const names = new Set();
  let key = null;
  for (const line of lockText.replace(/\r\n/g, '\n').split('\n')) {
    const k = /^ {2}(\S.*):\s*$/.exec(line);
    if (k) key = k[1];
    else if (/^\S/.test(line)) key = null;
    else if (key && /^ {4}requiresBuild:\s*true\s*$/.test(line)) names.add(pnpmKeyName(key));
  }
  return [...names].sort();
}

/** Installed packages (node_modules/.pnpm) that declare an install script or ship a binding.gyp; null if none installed. */
export function installedBuildPackages(root) {
  const store = join(root, 'node_modules', '.pnpm');
  if (!existsSync(store)) return null;
  const names = new Set();
  for (const d of readdirSync(store)) {
    if (d === 'node_modules' || d.indexOf('@', 1) < 0) continue;
    const name = pnpmKeyName(d);
    const dir = join(store, d, 'node_modules', ...name.split('/'));
    let pkg;
    try {
      pkg = JSON.parse(readFileSync(join(dir, 'package.json'), 'utf8'));
    } catch {
      continue;
    }
    const scripts = pkg.scripts || {};
    if (INSTALL_SCRIPTS.some((s) => scripts[s]) || existsSync(join(dir, 'binding.gyp')))
      names.add(name);
  }
  return [...names].sort();
}

/** APP-L6 check of package.json, pnpm-workspace.yaml, pnpm-lock.yaml and (if installed) node_modules. */
export function checkBuildScripts(root) {
  const problems = [];
  const read = (f) => (existsSync(join(root, f)) ? readFileSync(join(root, f), 'utf8') : null);
  const pkgText = read('package.json');
  const lock = read('pnpm-lock.yaml');
  if (!pkgText || !lock) return problems; // not a pnpm workspace
  const problem = (file, detail) => problems.push({ file, rule: 'build-scripts', detail });
  const allow = JSON.parse(pkgText).pnpm?.onlyBuiltDependencies;
  if (!Array.isArray(allow)) {
    problem(
      'package.json',
      '`pnpm.onlyBuiltDependencies` missing: pnpm 9 runs every dependency lifecycle script',
    );
    return problems;
  }
  if (/^onlyBuiltDependencies\s*:/m.test(read('pnpm-workspace.yaml') || ''))
    problem(
      'pnpm-workspace.yaml',
      'onlyBuiltDependencies here is ignored by pnpm 9; set it in package.json `pnpm`',
    );
  for (const name of lockfileBuildPackages(lock))
    if (!allow.includes(name))
      problem(
        'pnpm-lock.yaml',
        `${name} has requiresBuild: true but is not in pnpm.onlyBuiltDependencies`,
      );
  for (const name of installedBuildPackages(root) || [])
    if (!allow.includes(name) && !REVIEWED_UNBUILT.includes(name))
      problem(
        'pnpm-lock.yaml',
        `${name} has an unreviewed install script: add it to pnpm.onlyBuiltDependencies (only if the build needs it) or to REVIEWED_UNBUILT`,
      );
  return problems;
}

/**
 * Lockfile source policy (SEC-080, APP-L5): every entry of the `packages:` section of a pnpm-lock.yaml
 * text resolves from the registry with an integrity hash; git and tarball sources are refused.
 * Returns [{line, detail}].
 */
export function lockfileSourceProblems(lockText) {
  const problems = [];
  const lines = lockText.replace(/\r\n/g, '\n').split('\n');
  let inPackages = false;
  let key = null;
  let keyLine = 0;
  let resolution = null;
  const close = () => {
    if (key === null) return;
    if (resolution === null) problems.push({ line: keyLine, detail: `${key}: no resolution` });
    else if (/\btarball\s*:|\btype\s*:\s*git\b|\brepo\s*:|\bcommit\s*:/.test(resolution))
      problems.push({ line: keyLine, detail: `${key}: git or tarball source is not allowed` });
    else if (!/\bintegrity\s*:\s*sha(256|384|512)-/.test(resolution))
      problems.push({ line: keyLine, detail: `${key}: resolution has no integrity hash` });
    key = null;
    resolution = null;
  };
  lines.forEach((line, i) => {
    if (/^\S/.test(line)) {
      close();
      inPackages = /^packages\s*:\s*$/.test(line);
      return;
    }
    if (!inPackages) return;
    const k = /^ {2}(\S.*):\s*$/.exec(line);
    if (k) {
      close();
      key = k[1].replace(/^['"]|['"]$/g, '');
      keyLine = i + 1;
      return;
    }
    const r = /^ {4}resolution\s*:\s*(.*)$/.exec(line);
    if (r && key !== null) resolution = r[1];
  });
  close();
  return problems;
}

export const SBOM_SCANNER_DIR = 'tools/sbom-cdxgen';

/**
 * APP-L5 (nfb-security, 2026-09-27): the SBOM scanner is an isolated CI-only package with its own
 * lockfile. It must stay out of the pnpm workspace and the root lockfile, and its lockfile must exist
 * and pass the source policy. Both lockfiles get the source policy.
 */
export function checkSbomScanner(root) {
  const problems = [];
  const read = (f) => (existsSync(join(root, f)) ? readFileSync(join(root, f), 'utf8') : null);
  const problem = (file, detail, line) =>
    problems.push({ file, ...(line ? { line } : {}), rule: 'lockfile', detail });
  const rootLock = read('pnpm-lock.yaml');
  if (rootLock) {
    for (const p of lockfileSourceProblems(rootLock)) problem('pnpm-lock.yaml', p.detail, p.line);
    if (/^\s+'?@cyclonedx\/cdxgen@/m.test(rootLock))
      problem(
        'pnpm-lock.yaml',
        `@cyclonedx/cdxgen must not be in the root lockfile: it lives in ${SBOM_SCANNER_DIR} (regenerate the root lockfile offline)`,
      );
  }
  if (!existsSync(join(root, SBOM_SCANNER_DIR, 'package.json'))) return problems;
  const ws = read('pnpm-workspace.yaml') || '';
  if (!new RegExp(`^\\s*-\\s*['"]?!${SBOM_SCANNER_DIR}['"]?\\s*$`, 'm').test(ws))
    problem(
      'pnpm-workspace.yaml',
      `'!${SBOM_SCANNER_DIR}' must exclude the scanner from the workspace`,
    );
  const lockFile = `${SBOM_SCANNER_DIR}/pnpm-lock.yaml`;
  const lock = read(lockFile);
  if (!lock)
    problem(lockFile, 'missing: generate it offline (pnpm install --lockfile-only --offline)');
  else for (const p of lockfileSourceProblems(lock)) problem(lockFile, p.detail, p.line);
  return problems;
}

/** Run every check on a repo checkout. Returns [{file, line?, rule, detail}]. */
export function guardRepo(root) {
  const problems = [];
  for (const f of trackedFiles(root)) {
    const d = checkDataFile(f);
    if (d) problems.push({ file: f, rule: 'data-file', detail: d });
    const s = checkSecretFile(f);
    if (s) problems.push({ file: f, rule: 'secret-file', detail: s });
    let buf;
    try {
      const abs = join(root, f);
      const size = statSync(abs).size;
      const big = checkLargeFile(f, size);
      if (big) problems.push({ file: f, rule: 'large-file', detail: big });
      if (size > MAX_SCAN_BYTES) continue;
      buf = readFileSync(abs);
    } catch {
      continue; // deleted in the working tree
    }
    if (buf.includes(0)) continue; // binary
    for (const h of scanSecrets(buf.toString('utf8')))
      problems.push({ file: f, line: h.line, rule: 'secret', detail: h.name });
    if (/^\.github\/workflows\/[^/]+\.ya?ml$/.test(f)) {
      const w = checkWorkflow(buf.toString('utf8'));
      if (w) problems.push({ file: f, rule: 'workflow-trigger', detail: w });
    }
  }
  problems.push(...checkArenaPkg(root));
  problems.push(...checkBuildScripts(root));
  problems.push(...checkSbomScanner(root));
  return problems;
}
