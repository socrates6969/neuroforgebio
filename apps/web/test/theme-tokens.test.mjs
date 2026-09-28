// Every var(--x) used under apps/web/src must resolve to a real token defined in BOTH themes'
// tokens.css (packages/ui and packages/figures already get this from style-lint.test.mjs; this is
// the same check for apps/web/src, which that lint doesn't cover). A var() whose custom property
// isn't defined by a theme silently falls through to its own CSS fallback forever in that theme -
// e.g. apps/web/src/components/BuildStatePill.astro referenced --color-success(-light), which
// neither theme defines, so it always used the literal fallback colours (an under-AA contrast pair
// in both themes, docs/hive/A11Y-AUDIT.md T6/BuildStatePill). Source-only: no build required.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { REPO } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const SRC = join(REPO, 'apps/web/src');
const EXTS = new Set(['.astro', '.css', '.ts', '.mjs', '.tsx']);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

function definedTokens(theme) {
  const css = readFileSync(join(REPO, `packages/themes/${theme}/tokens.css`), 'utf8');
  return new Set([...css.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)].map((m) => m[1]));
}

/** Every top-level var(...) call in `text`: { start, inner } (inner = the argument list, not
 * split on comma yet). Paren-aware so `var(--a, color-mix(in srgb, var(--b) 10%, transparent))`
 * doesn't truncate at the first inner ")". */
function varCalls(text) {
  const out = [];
  const re = /var\(/g;
  let m;
  while ((m = re.exec(text))) {
    let i = m.index + 4; // just after "var("
    let depth = 1;
    while (i < text.length && depth > 0) {
      if (text[i] === '(') depth++;
      else if (text[i] === ')') depth--;
      i++;
    }
    out.push({ start: m.index, end: i, inner: text.slice(m.index + 4, i - 1) });
  }
  return out;
}

/** Split `inner` on its first top-level comma (not inside a nested "(...)"). */
function splitArgs(inner) {
  let depth = 0;
  for (let i = 0; i < inner.length; i++) {
    if (inner[i] === '(') depth++;
    else if (inner[i] === ')') depth--;
    else if (inner[i] === ',' && depth === 0) return [inner.slice(0, i), inner.slice(i + 1)];
  }
  return [inner, null];
}

/** A fallback "resolves through" the theme if it itself references a token that both themes
 * define, however deeply nested (e.g. inside color-mix()). */
function fallbackResolves(fallback, defined) {
  if (fallback === null) return false;
  return varCalls(fallback).some((c) => defined.has(splitArgs(c.inner)[0].trim()));
}

test('every var(--x) under apps/web/src is defined by both themes (or falls back to one that is)', () => {
  const defined = new Set(
    [...definedTokens(THEMES[0])].filter((t) => definedTokens(THEMES[1]).has(t)),
  );
  const problems = [];
  for (const f of walk(SRC)) {
    const ext = f.slice(f.lastIndexOf('.'));
    if (!EXTS.has(ext)) continue;
    const text = readFileSync(f, 'utf8');
    for (const call of varCalls(text)) {
      const [namePart, fallback] = splitArgs(call.inner);
      const name = namePart.trim();
      if (!/^--[a-zA-Z0-9-]+$/.test(name)) continue; // not a plain custom-property reference
      if (defined.has(name)) continue;
      if (fallbackResolves(fallback, defined)) continue;
      const line = text.slice(0, call.start).split('\n').length;
      problems.push(
        `${relative(REPO, f)}:${line}  ${text.slice(call.start, call.end)} — ${name} is not defined by both themes' tokens.css, and its fallback doesn't resolve to a token that is`,
      );
    }
  }
  assert.deepEqual(problems, []);
});
