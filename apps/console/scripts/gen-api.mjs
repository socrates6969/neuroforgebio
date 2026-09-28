#!/usr/bin/env node
// Typed API client generator (BUILD-GUIDE 3.8, 4.1).
// 1. Runs scripts/gen_openapi.py with the repo's .venv Python: the committed contract openapi/v1.yaml
//    (drift-tested against the platform app) plus the authz matrix (nf_platform.auth.authorize).
// 2. Writes src/api/authz.json and src/api/generated.ts (types + operation table). Operations marked
//    `x-nf-status: disabled` (OWNER-GATED, not served) and CORS preflights are left out.
//    `--print-openapi` writes the contract as JSON to stdout for inspection.
// Usage: node scripts/gen-api.mjs            regenerate
//        node scripts/gen-api.mjs --check    exit 1 if the committed files differ (drift test)
// Python: $NF_PYTHON, else <repo>/.venv/Scripts/python.exe (Windows) or <repo>/.venv/bin/python.
// Output is formatted with the repo's Prettier (root devDependency) so `prettier --check` stays clean.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const CONSOLE = resolve(HERE, '..');
export const ROOT = resolve(CONSOLE, '..', '..');
const OUT = join(CONSOLE, 'src', 'api');

export function findPython() {
  if (process.env.NF_PYTHON) return process.env.NF_PYTHON;
  const win = join(ROOT, '.venv', 'Scripts', 'python.exe');
  const nix = join(ROOT, '.venv', 'bin', 'python');
  if (existsSync(win)) return win;
  if (existsSync(nix)) return nix;
  return null;
}

export function dumpPlatform(python = findPython()) {
  if (!python)
    throw new Error('no Python: create the repo .venv (docs/dev/toolchain.md) or set NF_PYTHON');
  const r = spawnSync(python, [join(HERE, 'gen_openapi.py')], {
    cwd: ROOT,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  if (r.status !== 0) throw new Error(`gen_openapi.py failed (${r.status}): ${r.stderr}`);
  return JSON.parse(r.stdout);
}

// ------------------------------------------------------------------ JSON Schema -> TypeScript
const IDENT = /^[A-Za-z_$][A-Za-z0-9_$]*$/;
const key = (k) => (IDENT.test(k) ? k : JSON.stringify(k));
const refName = (ref) =>
  ref
    .split('/')
    .pop()
    .replace(/[^A-Za-z0-9_]/g, '_');

export function tsType(s, indent = '') {
  if (!s || Object.keys(s).length === 0) return 'unknown';
  if (s.$ref) return refName(s.$ref);
  if (s.const !== undefined) return JSON.stringify(s.const);
  if (s.enum) return s.enum.map((v) => JSON.stringify(v)).join(' | ');
  const union = s.anyOf || s.oneOf;
  if (union) {
    const parts = [...new Set(union.map((u) => tsType(u, indent)))];
    return parts.length === 1 ? parts[0] : parts.join(' | ');
  }
  if (s.allOf) return s.allOf.map((u) => tsType(u, indent)).join(' & ');
  const t = Array.isArray(s.type) ? s.type : [s.type];
  if (t.length > 1) return t.map((x) => tsType({ ...s, type: x }, indent)).join(' | ');
  switch (t[0]) {
    case 'string':
      return 'string';
    case 'integer':
    case 'number':
      return 'number';
    case 'boolean':
      return 'boolean';
    case 'null':
      return 'null';
    case 'array': {
      const inner = tsType(s.items, indent);
      return /[|&]/.test(inner) ? `Array<${inner}>` : `${inner}[]`;
    }
    case 'object':
    case undefined: {
      const props = s.properties || {};
      const req = new Set(s.required || []);
      const names = Object.keys(props).sort();
      if (names.length === 0) {
        if (s.additionalProperties && typeof s.additionalProperties === 'object')
          return `Record<string, ${tsType(s.additionalProperties, indent)}>`;
        return 'Record<string, unknown>';
      }
      const inner = indent + '  ';
      const lines = names.map((n) => {
        const d = props[n].description ? `${inner}/** ${props[n].description} */\n` : '';
        return `${d}${inner}${key(n)}${req.has(n) ? '' : '?'}: ${tsType(props[n], inner)};`;
      });
      return `{\n${lines.join('\n')}\n${indent}}`;
    }
    default:
      return 'unknown';
  }
}

const camel = (s) =>
  s
    .replace(/[^A-Za-z0-9]+(.)?/g, (_, c) => (c ? c.toUpperCase() : ''))
    .replace(/^./, (c) => c.toLowerCase());

function jsonSchemaOf(content) {
  if (!content) return null;
  const json = content['application/json'];
  if (json) return json.schema ?? {};
  // text/event-stream: the data of each event (x-nf-event-data points at its schema)
  const sse = content['text/event-stream'];
  return sse?.['x-nf-event-data'] ? { $ref: sse['x-nf-event-data'] } : null;
}

/** Operation list: [{name, method, path, action, pathParams, queryParams, body, response, ...}]. */
export function operations(doc) {
  const ops = [];
  const seen = new Set();
  for (const path of Object.keys(doc.paths).sort()) {
    for (const [method, op] of Object.entries(doc.paths[path])) {
      if (op['x-nf-status'] === 'disabled' || method === 'options') continue;
      let name = camel(op.summary || op.operationId);
      if (seen.has(name)) name = camel(op.operationId);
      seen.add(name);
      const params = op.parameters || [];
      const ok = Object.keys(op.responses || {})
        .filter((c) => /^2\d\d$/.test(c))
        .sort()[0];
      const resp = ok ? op.responses[ok].content : null;
      const rb = op.requestBody?.content || null;
      ops.push({
        name,
        method: method.toUpperCase(),
        path,
        action: op['x-nf-action'] ?? null,
        status: ok ? Number(ok) : 200,
        pathParams: params.filter((p) => p.in === 'path'),
        queryParams: params.filter((p) => p.in === 'query'),
        body: rb ? (rb['application/json'] ? 'json' : 'binary') : null,
        bodySchema: jsonSchemaOf(rb),
        bodyRequired: !!op.requestBody?.required,
        response: resp ? jsonSchemaOf(resp) : null,
        responseTypes: resp ? Object.keys(resp).sort() : [],
      });
    }
  }
  return ops;
}

function paramsType(list) {
  if (!list.length) return 'never';
  const lines = list
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((p) => `      ${key(p.name)}${p.required ? '' : '?'}: ${tsType(p.schema, '      ')};`);
  return `{\n${lines.join('\n')}\n    }`;
}

export function renderTs(doc) {
  const schemas = doc.components?.schemas || {};
  const out = [
    '// GENERATED by apps/console/scripts/gen-api.mjs from the platform FastAPI app. Do not edit.',
    '// Regenerate: node apps/console/scripts/gen-api.mjs (a test fails on drift).',
    '/* eslint-disable */',
    '',
    `export const API_TITLE = ${JSON.stringify(doc.info?.title ?? '')};`,
    `export const API_VERSION = ${JSON.stringify(doc.info?.version ?? '')};`,
    '',
  ];
  for (const n of Object.keys(schemas).sort()) {
    const s = schemas[n];
    if (s.description) out.push(`/** ${s.description.split('\n')[0]} */`);
    out.push(`export type ${refName(n)} = ${tsType(s)};`, '');
  }
  const ops = operations(doc);
  out.push('export interface Operations {');
  for (const o of ops) {
    const body =
      o.body === 'json' ? tsType(o.bodySchema, '    ') : o.body === 'binary' ? 'Blob' : 'never';
    const resp = o.response ? tsType(o.response, '    ') : 'unknown';
    out.push(
      `  /** ${o.method} ${o.path}${o.action ? ` (action ${o.action})` : ''} */`,
      `  ${o.name}: {`,
      `    path: ${paramsType(o.pathParams)};`,
      `    query: ${paramsType(o.queryParams)};`,
      `    body: ${body};`,
      `    response: ${resp};`,
      '  };',
    );
  }
  out.push('}', '', 'export type OperationName = keyof Operations;', '');
  out.push(
    'export interface OperationMeta {',
    "  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';",
    '  path: string;',
    '  /** authz action from x-nf-action (null only for unmapped routes, which the server denies) */',
    '  action: string | null;',
    '  status: number;',
    "  body: 'json' | 'binary' | null;",
    '  responseTypes: readonly string[];',
    '}',
    '',
    'export const OPERATIONS: { readonly [K in OperationName]: OperationMeta } = {',
  );
  for (const o of ops)
    out.push(
      `  ${o.name}: { method: '${o.method}', path: '${o.path}', action: ${JSON.stringify(o.action)}, status: ${o.status}, body: ${JSON.stringify(o.body)}, responseTypes: ${JSON.stringify(o.responseTypes)} },`,
    );
  out.push('};', '');
  return out.join('\n');
}

const pretty = (v) => JSON.stringify(v, null, 2) + '\n';

async function format(files) {
  const prettier = await import('prettier');
  const out = {};
  for (const [name, text] of Object.entries(files)) {
    const filepath = join(OUT, name);
    const options = (await prettier.resolveConfig(filepath)) ?? {};
    out[name] = await prettier.format(text, { ...options, filepath });
  }
  return out;
}

export async function generate(dump) {
  return format({
    'authz.json': pretty(dump.authz),
    'generated.ts': renderTs(dump.openapi),
  });
}

/** Files that differ from the committed ones (normalising CRLF, for Windows checkouts). */
export function drift(files) {
  const bad = [];
  for (const [name, text] of Object.entries(files)) {
    const p = join(OUT, name);
    const cur = existsSync(p) ? readFileSync(p, 'utf8').replace(/\r\n/g, '\n') : null;
    if (cur !== text) bad.push(name);
  }
  return bad;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const dump = dumpPlatform();
  if (process.argv.includes('--print-openapi')) {
    process.stdout.write(pretty(dump.openapi));
    process.exit(0);
  }
  const files = await generate(dump);
  if (process.argv.includes('--check')) {
    const bad = drift(files);
    if (bad.length) {
      console.error(
        `gen-api: ${bad.join(', ')} out of date with the platform API; run node apps/console/scripts/gen-api.mjs`,
      );
      process.exit(1);
    }
    console.error('gen-api: client matches the platform API');
  } else {
    for (const [name, text] of Object.entries(files)) writeFileSync(join(OUT, name), text);
    console.error(`gen-api: wrote ${Object.keys(files).join(', ')} to src/api`);
  }
}
