// licence-check: zero-dependency licence gate for browser-shipped packages (SEC-084).
// Roots: the production `dependencies` (+ `optionalDependencies`) of apps/web, apps/console and packages/*.
// Walks the installed tree in node_modules (pnpm layout, symlinks resolved), reads each package.json
// `license` (or legacy `licenses`) field and evaluates it as an SPDX expression against the allowlist
// in security/licences.json (human-readable copy: docs/security/licences.md).
// Build-only packages listed in `buildOnly` are checked themselves but their subtree is not walked,
// because their dependencies run at build time and are not shipped to browsers.
import { existsSync, readdirSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';

/** Tokenise and evaluate an SPDX expression. Returns true/false; unknown ids are false. */
export function spdxAllowed(expr, allowed) {
  const tokens = String(expr)
    .replace(/\(/g, ' ( ')
    .replace(/\)/g, ' ) ')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  let i = 0;
  const peek = () => tokens[i];
  function factor() {
    const t = tokens[i++];
    if (t === '(') {
      const v = orExpr();
      if (tokens[i++] !== ')') throw new Error(`unbalanced SPDX expression: ${expr}`);
      return v;
    }
    if (!t || /^(AND|OR|WITH|\))$/i.test(t)) throw new Error(`bad SPDX expression: ${expr}`);
    let id = t.replace(/\+$/, '');
    if (peek() && /^WITH$/i.test(peek())) {
      i++;
      id = `${id} WITH ${tokens[i++]}`;
    }
    return allowed.has(id);
  }
  function andExpr() {
    let v = factor();
    while (peek() && /^AND$/i.test(peek())) {
      i++;
      v = factor() && v;
    }
    return v;
  }
  function orExpr() {
    let v = andExpr();
    while (peek() && /^OR$/i.test(peek())) {
      i++;
      v = andExpr() || v;
    }
    return v;
  }
  try {
    const v = orExpr();
    return i === tokens.length ? v : false;
  } catch {
    return false;
  }
}

/** Normalise the licence field(s) of a package.json into one SPDX expression string (or null). */
export function licenceOf(pkg) {
  const l = pkg.license;
  if (typeof l === 'string' && l.trim()) return l.trim();
  if (l && typeof l === 'object' && l.type) return String(l.type);
  if (Array.isArray(pkg.licenses) && pkg.licenses.length)
    return pkg.licenses.map((x) => (typeof x === 'string' ? x : x.type)).join(' OR ');
  return null;
}

function readJson(p) {
  return JSON.parse(readFileSync(p, 'utf8'));
}

/** Node-style resolution of `name` from directory `from` (walks up through node_modules). */
function resolvePkg(name, from) {
  let dir = from;
  for (;;) {
    const cand = join(dir, 'node_modules', name, 'package.json');
    if (existsSync(cand)) return realpathSync(dirname(cand));
    const up = dirname(dir);
    if (up === dir) return null;
    dir = up;
  }
}

/** Workspace roots whose production deps ship to browsers. */
export function browserRoots(root) {
  const roots = [];
  for (const app of ['web', 'console'])
    if (existsSync(join(root, 'apps', app, 'package.json'))) roots.push(join(root, 'apps', app));
  const pk = join(root, 'packages');
  if (existsSync(pk))
    for (const d of readdirSync(pk))
      if (existsSync(join(pk, d, 'package.json'))) roots.push(join(pk, d));
  return roots.map((r) => realpathSync(r));
}

/**
 * Check the installed tree. policy = {allowed: [...], buildOnly: [...], exceptions: {"name@version": reason}}.
 * Returns {problems: [{pkg, licence, path, detail}], checked: n}.
 */
export function checkTree(root, policy) {
  const allowed = new Set(policy.allowed);
  const buildOnly = new Set(policy.buildOnly || []);
  const exceptions = policy.exceptions || {};
  const nodeModulesRoot = realpathSync(root);
  const seen = new Set();
  const problems = [];
  let checked = 0;
  const queue = browserRoots(root).map((dir) => ({
    dir,
    chain: [relative(nodeModulesRoot, dir).replace(/\\/g, '/')],
  }));
  while (queue.length) {
    const { dir, chain } = queue.shift();
    if (seen.has(dir)) continue;
    seen.add(dir);
    const pkg = readJson(join(dir, 'package.json'));
    const firstParty =
      !/[\\/]node_modules[\\/]/.test(relative(nodeModulesRoot, dir) + '/') && pkg.private;
    if (!firstParty) {
      checked++;
      const id = `${pkg.name}@${pkg.version}`;
      const lic = licenceOf(pkg);
      if (!exceptions[id] && !exceptions[pkg.name]) {
        if (!lic)
          problems.push({
            pkg: id,
            licence: null,
            path: chain.join(' > '),
            detail: 'no licence field',
          });
        else if (!spdxAllowed(lic, allowed))
          problems.push({
            pkg: id,
            licence: lic,
            path: chain.join(' > '),
            detail: 'licence not allowed',
          });
      }
      if (buildOnly.has(pkg.name)) continue;
    }
    const deps = { ...(pkg.dependencies || {}) };
    const optional = pkg.optionalDependencies || {};
    for (const name of Object.keys({ ...deps, ...optional })) {
      const d = resolvePkg(name, dir);
      if (!d) {
        if (!(name in optional))
          problems.push({
            pkg: name,
            licence: null,
            path: chain.join(' > '),
            detail: 'not installed (run pnpm install)',
          });
        continue;
      }
      queue.push({ dir: d, chain: [...chain, name] });
    }
  }
  return { problems, checked };
}
