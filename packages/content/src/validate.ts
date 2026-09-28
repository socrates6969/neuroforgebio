// Zero-dependency validator for the descriptors in ./schema.ts.
import type { Schema } from './schema.ts';

const TAG = /<\/?([a-zA-Z][a-zA-Z0-9-]*)[^>]*>/g;

function checkRich(s: string): string | null {
  let depth = 0;
  for (const m of s.matchAll(TAG)) {
    const whole = m[0];
    if (whole !== '<em>' && whole !== '</em>') return `tag ${whole} not allowed (only <em>)`;
    depth += whole === '<em>' ? 1 : -1;
    if (depth < 0 || depth > 1) return 'unbalanced or nested <em>';
  }
  return depth === 0 ? null : 'unclosed <em>';
}

export function validate(value: unknown, schema: Schema, path = '$'): string[] {
  const errs: string[] = [];
  switch (schema.k) {
    case 'str':
    case 'rich': {
      if (typeof value !== 'string' || value.trim() === '') {
        errs.push(`${path}: expected non-empty string`);
        break;
      }
      if (schema.k === 'str') {
        TAG.lastIndex = 0;
        if (TAG.test(value)) errs.push(`${path}: HTML not allowed in plain string`);
        TAG.lastIndex = 0;
      } else {
        const e = checkRich(value);
        if (e) errs.push(`${path}: ${e}`);
      }
      break;
    }
    case 'bool':
      if (typeof value !== 'boolean') errs.push(`${path}: expected boolean`);
      break;
    case 'lit':
      if (value !== schema.v) errs.push(`${path}: expected ${JSON.stringify(schema.v)}`);
      break;
    case 'enum':
      if (typeof value !== 'string' || !schema.v.includes(value))
        errs.push(`${path}: expected one of ${schema.v.join(' | ')}, got ${JSON.stringify(value)}`);
      break;
    case 'arr':
      if (!Array.isArray(value)) {
        errs.push(`${path}: expected array`);
        break;
      }
      if (value.length < schema.min) errs.push(`${path}: expected at least ${schema.min} item(s)`);
      value.forEach((v, i) => errs.push(...validate(v, schema.item, `${path}[${i}]`)));
      break;
    case 'rec':
      if (!isPlainObject(value)) {
        errs.push(`${path}: expected object`);
        break;
      }
      for (const [k, v] of Object.entries(value))
        errs.push(...validate(v, schema.value, `${path}.${k}`));
      break;
    case 'obj': {
      if (!isPlainObject(value)) {
        errs.push(`${path}: expected object`);
        break;
      }
      const o = value as Record<string, unknown>;
      for (const [k, s] of Object.entries(schema.req)) {
        if (!(k in o)) errs.push(`${path}.${k}: missing`);
        else errs.push(...validate(o[k], s, `${path}.${k}`));
      }
      for (const [k, v] of Object.entries(o)) {
        if (k in schema.req) continue;
        const s = schema.opt[k];
        if (!s) errs.push(`${path}.${k}: unknown key`);
        else errs.push(...validate(v, s, `${path}.${k}`));
      }
      break;
    }
  }
  return errs;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** Calls fn(string, path) for every string value in a JSON tree. */
export function walkStrings(
  value: unknown,
  fn: (s: string, path: string) => void,
  path = '$',
): void {
  if (typeof value === 'string') fn(value, path);
  else if (Array.isArray(value)) value.forEach((v, i) => walkStrings(v, fn, `${path}[${i}]`));
  else if (isPlainObject(value))
    for (const [k, v] of Object.entries(value)) walkStrings(v, fn, `${path}.${k}`);
}

/** Placeholder tokens such as {brand}. */
export const TOKEN = /\{([a-zA-Z]+)\}/g;

/** Returns a deep copy with every {token} replaced from vars; unknown tokens are left in place. */
export function substitute<T>(value: T, vars: Record<string, string>): T {
  if (typeof value === 'string')
    return value.replace(TOKEN, (m, k: string) => (k in vars ? vars[k] : m)) as unknown as T;
  if (Array.isArray(value)) return value.map((v) => substitute(v, vars)) as unknown as T;
  if (isPlainObject(value)) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = substitute(v, vars);
    return out as T;
  }
  return value;
}

/** Lists leftover {tokens} in a tree (after substitution these are errors). */
export function unresolvedTokens(value: unknown): string[] {
  const out: string[] = [];
  walkStrings(value, (s, p) => {
    for (const m of s.matchAll(TOKEN)) out.push(`${p}: unresolved ${m[0]}`);
  });
  return out;
}
