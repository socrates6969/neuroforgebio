// Static checkers for the "review by eye" rows of docs/web/a11y-checklist.md (rows 2-5, 7 -- row 1
// is already covered by theme-tokens.test.mjs/style-lint.test.mjs, row 6 is a content-system
// review that needs human judgement). Every checker here is a heuristic over built HTML, built CSS
// and the page's TypeScript source -- none of them run a browser, compute real layout, or execute
// JS, so each one has a documented blind spot (see its own comment). They catch the *shape* of bug
// the audit already found once (docs/hive/A11Y-AUDIT.md); apps/web/e2e/a11y.spec.ts (axe) and
// apps/web/e2e/visual.spec.ts (real overflow) stay the ground truth.
//
// Every checker returns problems as { row, route, selector, message } so the test file can match
// them against its in-file exception allowlist (route + selector), never against markup.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { visibleText } from './_dist.mjs';

/* ------------------------------------------------------------------------ tiny HTML tree parser */

export const VOID_TAGS = new Set([
  'area',
  'base',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'input',
  'link',
  'meta',
  'param',
  'source',
  'track',
  'wbr',
]);
// Content of these is text, not markup (noscript is parsed as markup on purpose: its content is
// what JS-off visitors get, and rows 5/7 care about that; row 2 skips it, see SKIP_SUBTREE_TAGS).
const RAW_TEXT_TAGS = new Set(['script', 'style', 'textarea', 'title']);

const NBSP = String.fromCharCode(0xa0); // no-break space: NOT a line-break opportunity
const SHY = String.fromCharCode(0xad); // soft hyphen: a line-break opportunity
const ZWSP = String.fromCharCode(0x200b); // zero-width space: a line-break opportunity
const NAMED_ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: NBSP, shy: SHY };

export function decodeEntities(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, name) => {
    if (name[0] !== '#') return NAMED_ENTITIES[name.toLowerCase()] ?? whole;
    const cp = /^#x/i.test(name) ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10);
    return Number.isFinite(cp) && cp >= 0 && cp <= 0x10ffff ? String.fromCodePoint(cp) : whole;
  });
}

const ATTR_RE = /([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;

function parseAttrs(text) {
  const attrs = new Map();
  for (const m of text.matchAll(ATTR_RE)) {
    const name = m[1].toLowerCase();
    if (!attrs.has(name)) attrs.set(name, decodeEntities(m[2] ?? m[3] ?? m[4] ?? ''));
  }
  return attrs;
}

const TAG_RE =
  /<!--[\s\S]*?-->|<![^>]*>|<\/([a-zA-Z][\w:-]*)\s*>|<([a-zA-Z][\w:-]*)((?:"[^"]*"|'[^']*'|[^'">])*?)(\/?)>/g;

/**
 * Parses HTML into { type, tag, attrs: Map, classes, children, parent } element nodes and
 * { type: 'text', text } text nodes (entities decoded). Not a spec parser: no implied end tags, no
 * foster parenting. A closing tag pops back to the nearest open element of the same name (so an
 * unclosed inner element can't swallow the rest of the page) and a stray closing tag is ignored.
 * Astro's output is well-formed, which is all this needs.
 */
export function parseHtml(html) {
  const root = {
    type: 'root',
    tag: '#root',
    attrs: new Map(),
    classes: [],
    children: [],
    parent: null,
  };
  let cur = root;
  const re = new RegExp(TAG_RE.source, 'g');
  let last = 0;
  const pushText = (s) => {
    if (s) cur.children.push({ type: 'text', text: decodeEntities(s), parent: cur });
  };
  let m;
  while ((m = re.exec(html))) {
    pushText(html.slice(last, m.index));
    last = re.lastIndex;
    if (m[1]) {
      const tag = m[1].toLowerCase();
      for (let n = cur; n !== root; n = n.parent)
        if (n.tag === tag) {
          cur = n.parent;
          break;
        }
      continue;
    }
    if (!m[2]) continue; // comment or doctype
    const tag = m[2].toLowerCase();
    const attrs = parseAttrs(m[3] || '');
    const el = {
      type: 'element',
      tag,
      attrs,
      classes: (attrs.get('class') ?? '').split(/\s+/).filter(Boolean),
      children: [],
      parent: cur,
    };
    cur.children.push(el);
    if (m[4] === '/' || VOID_TAGS.has(tag)) continue;
    if (RAW_TEXT_TAGS.has(tag)) {
      const close = new RegExp(`</${tag}\\s*>`, 'gi');
      close.lastIndex = re.lastIndex;
      const cm = close.exec(html);
      const text = html.slice(re.lastIndex, cm ? cm.index : html.length);
      el.children.push({ type: 'text', text, parent: el });
      re.lastIndex = last = cm ? close.lastIndex : html.length;
      continue;
    }
    cur = el;
  }
  pushText(html.slice(last));
  return root;
}

const isEl = (n) => n?.type === 'element';
const elementChildren = (n) => n.children.filter(isEl);
const isHookAttr = (name) => name.startsWith('data-') && !name.startsWith('data-astro-');

/** Every element under `node` in document order; `skip(el)` true = don't yield it or descend. */
export function* elements(node, skip = () => false) {
  for (const c of node.children) {
    if (!isEl(c) || skip(c)) continue;
    yield c;
    yield* elements(c, skip);
  }
}

function findBody(root) {
  for (const el of elements(root)) if (el.tag === 'body') return el;
  return root;
}

/** Concatenated text of a subtree, script/style content excluded. */
function textOf(node) {
  if (node.type === 'text') return node.text;
  if (node.tag === 'script' || node.tag === 'style') return '';
  return node.children.map(textOf).join(' ');
}

const norm = (s) => s.replace(/\s+/g, ' ').trim().toLowerCase();

/** Short human/allowlist handle for an element: tag#id, tag[data-hook], tag.class.list or tag. */
export function describeEl(el) {
  if (el.attrs.get('id')) return `${el.tag}#${el.attrs.get('id')}`;
  const hook = [...el.attrs.keys()].find(isHookAttr);
  if (hook) return `${el.tag}[${hook}]`;
  if (el.classes.length) return `${el.tag}.${el.classes.join('.')}`;
  return el.tag;
}

function byId(root, id) {
  for (const el of elements(root)) if (el.attrs.get('id') === id) return el;
  return null;
}

/* --------------------------------------------------------------- exceptions (test-file allowlist) */

/**
 * Drops every problem that an exception entry { row, route, selector, reason } matches exactly
 * (same row number, route and selector string as the problem reports). `used` (a Set) collects the
 * indexes of entries that matched something, so the caller can fail on stale entries.
 */
export function applyExceptions(problems, exceptions, used) {
  return problems.filter((p) => {
    const i = exceptions.findIndex(
      (e) => e.row === p.row && e.route === p.route && e.selector === p.selector,
    );
    if (i < 0) return true;
    used?.add(i);
    return false;
  });
}

/** Shape problems in an exception list: missing fields, empty reason, unknown row, duplicates. */
export function exceptionShapeProblems(exceptions) {
  const out = [];
  const seen = new Set();
  exceptions.forEach((e, i) => {
    if (![2, 3, 4, 5, 7].includes(e.row)) out.push(`entry ${i}: row must be 2, 3, 4, 5 or 7`);
    if (typeof e.route !== 'string' || !e.route.startsWith('/')) out.push(`entry ${i}: bad route`);
    if (typeof e.selector !== 'string' || !e.selector.trim())
      out.push(`entry ${i}: empty selector`);
    if (typeof e.reason !== 'string' || !e.reason.trim()) out.push(`entry ${i}: empty reason`);
    const key = `${e.row} ${e.route} ${e.selector}`;
    if (seen.has(key)) out.push(`entry ${i}: duplicate of an earlier entry (${key})`);
    seen.add(key);
  });
  return out;
}

/* ---------------------------------------------------------------------------- CSS rule parsing */

/**
 * Astro 5.18.2 (this repo's version) scopes a component's <style> with the attribute strategy:
 * every compound selector gets `[data-astro-cid-<8 chars>]` appended, e.g. the built gallery CSS
 * contains `.blocks[data-astro-cid-sahthylw]>section[data-astro-cid-sahthylw]{scroll-margin-top:
 * 80px;min-width:0}` (checked against a real build, web-integration dist/clinical/_assets,
 * 2026-09-27). The checkers match selectors against the parsed DOM, where those same attributes
 * exist, so scoping is honoured exactly rather than stripped. normalizeSelector() only prints a
 * source-like selector (the allowlist key); it also strips the `:where([data-astro-cid-…])` form
 * of the other scopedStyleStrategy in case the config ever changes.
 */
const CID_RE = /:where\(\[data-astro-cid-[a-z0-9]+\]\)|\[data-astro-cid-[a-z0-9]+\]/gi;

export function normalizeSelector(sel) {
  return sel
    .replace(/:global\(([^()]*)\)/gi, '$1')
    .replace(CID_RE, '')
    .replace(/:where\(([^()]*)\)/gi, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Splits on `sep` (a character, or ' ' for any whitespace) at top level: not in (), [] or quotes. */
function splitTopLevel(text, sep) {
  const out = [];
  let depth = 0;
  let start = 0;
  let quote = null;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === quote) quote = null;
    } else if (c === '"' || c === "'") quote = c;
    else if (c === '(' || c === '[') depth++;
    else if (c === ')' || c === ']') depth--;
    else if (depth === 0 && (sep === ' ' ? /\s/.test(c) : c === sep)) {
      out.push(text.slice(start, i));
      start = i + 1;
    }
  }
  out.push(text.slice(start));
  return out.map((s) => s.trim()).filter(Boolean);
}

/** Declaration block text -> Map(property -> value), lowercased, !important dropped. */
export function parseDecls(declText) {
  const props = new Map();
  for (const d of splitTopLevel(declText, ';')) {
    const colon = d.indexOf(':');
    if (colon <= 0) continue;
    const prop = d.slice(0, colon).trim().toLowerCase();
    const value = d
      .slice(colon + 1)
      .replace(/!\s*important\s*$/i, '')
      .trim()
      .toLowerCase();
    props.set(prop, value);
  }
  return props;
}

/**
 * Flat list of { selector, decl } style rules from CSS text, by repeatedly peeling off the
 * innermost `prelude { body-without-braces }` block, which flattens @media/@supports/@layer nesting
 * (a nested rule is always innermost before its wrapping @-rule is). Consequence, deliberately
 * worst-case: a rule inside any media query counts as if it always applied. Statement at-rules
 * (@import, @charset, `@layer a, b;`) are removed first so they can't glue onto the next selector.
 * Known gaps: @keyframes steps come out as "rules" (their selectors don't parse, so they match
 * nothing), and a literal { or } inside a quoted CSS string would confuse it (nothing in this
 * codebase's CSS does that).
 */
export function parseCssRules(cssText) {
  const rules = [];
  let text = cssText
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/@(?:import|charset|namespace|layer)\b[^;{}]*;/gi, ' ');
  const innerBlock = /([^{}]*)\{([^{}]*)\}/g;
  let changed = true;
  let guard = 0;
  while (changed && guard++ < 20000) {
    changed = false;
    text = text.replace(innerBlock, (whole, prelude, body) => {
      changed = true;
      const sel = prelude.trim();
      if (sel && !sel.startsWith('@')) rules.push({ selector: sel, decl: body });
      return ' ';
    });
  }
  return rules;
}

/* -------------------------------------------------------------------------- selector matching */

function splitCompounds(sel) {
  const out = [];
  let buf = '';
  let comb = null;
  let depth = 0;
  let quote = null;
  const flush = () => {
    if (!buf) return;
    out.push({ comb, text: buf });
    buf = '';
    comb = null;
  };
  for (const c of sel.trim()) {
    if (quote) {
      buf += c;
      if (c === quote) quote = null;
      continue;
    }
    if (c === '"' || c === "'") quote = c;
    else if (c === '(' || c === '[') depth++;
    else if (c === ')' || c === ']') depth--;
    if (depth === 0 && (c === '>' || c === '+' || c === '~')) {
      flush();
      comb = c;
      continue;
    }
    if (depth === 0 && /\s/.test(c)) {
      if (buf) {
        flush();
        comb = ' ';
      }
      continue;
    }
    buf += c;
  }
  flush();
  return out;
}

const ATTR_SEL_RE =
  /^\s*([\w:-]+)\s*(?:([~|^$*]?=)\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+)))?\s*([is])?\s*$/i;
const LEGACY_PSEUDO_ELEMENTS = new Set(['before', 'after', 'first-line', 'first-letter']);

function parseCompound(text) {
  const c = { tag: null, ids: [], classes: [], attrs: [], pseudos: [], pseudoElement: false };
  let i = 0;
  const readIdent = () => {
    let s = '';
    while (i < text.length) {
      const ch = text[i];
      if (ch === '\\' && i + 1 < text.length) {
        s += text[i + 1];
        i += 2;
      } else if (/[\w-]/.test(ch) || ch.charCodeAt(0) > 127) {
        s += ch;
        i++;
      } else break;
    }
    return s;
  };
  const readParen = () => {
    const start = i + 1;
    let depth = 0;
    for (; i < text.length; i++) {
      if (text[i] === '(') depth++;
      else if (text[i] === ')' && --depth === 0) {
        i++;
        return text.slice(start, i - 1);
      }
    }
    return text.slice(start);
  };
  while (i < text.length) {
    const ch = text[i];
    if (ch === '*') {
      c.tag = '*';
      i++;
    } else if (ch === '.') {
      i++;
      c.classes.push(readIdent());
    } else if (ch === '#') {
      i++;
      c.ids.push(readIdent());
    } else if (ch === '[') {
      const end = text.indexOf(']', i);
      const am = ATTR_SEL_RE.exec(text.slice(i + 1, end < 0 ? text.length : end));
      i = end < 0 ? text.length : end + 1;
      if (!am) return null;
      c.attrs.push({
        name: am[1].toLowerCase(),
        op: am[2] ?? null,
        value: am[3] ?? am[4] ?? am[5] ?? '',
        ci: (am[6] ?? '').toLowerCase() === 'i',
      });
    } else if (ch === ':') {
      if (text[i + 1] === ':') return { ...c, pseudoElement: true };
      i++;
      const name = readIdent().toLowerCase();
      const arg = text[i] === '(' ? readParen() : null;
      if (LEGACY_PSEUDO_ELEMENTS.has(name)) return { ...c, pseudoElement: true };
      c.pseudos.push({ name, arg });
    } else if (/[\w-]/.test(ch)) {
      c.tag = readIdent().toLowerCase();
    } else return null; // namespaces, keyframe percentages and other syntax this doesn't model
  }
  return c;
}

/** { parts: [{ comb, compound }] } | { pseudoElement: true } | null (unsupported syntax). */
function parseComplex(sel) {
  const out = [];
  for (const p of splitCompounds(sel)) {
    const compound = parseCompound(p.text);
    if (!compound) return null;
    if (compound.pseudoElement) return { pseudoElement: true };
    out.push({ comb: p.comb, compound });
  }
  return out.length ? { parts: out } : null;
}

// Tri-state results: true (matches), false (doesn't), null (can't tell statically -- a state
// pseudo-class like :hover, :has(), :nth-child()). Each caller decides what "can't tell" means for
// it, always in the direction that avoids a false pass. A selector that doesn't parse at all is
// "no match" (see PageStyles.decls).
function and3(a, b) {
  if (a === false || b === false) return false;
  return a === null || b === null ? null : true;
}

function matchAttr(el, a) {
  if (!el.attrs.has(a.name)) return false;
  if (!a.op) return true;
  let v = el.attrs.get(a.name);
  let want = a.value;
  if (a.ci) {
    v = v.toLowerCase();
    want = want.toLowerCase();
  }
  if (a.op === '=') return v === want;
  if (a.op === '~=') return v.split(/\s+/).includes(want);
  if (a.op === '|=') return v === want || v.startsWith(`${want}-`);
  if (a.op === '^=') return want !== '' && v.startsWith(want);
  if (a.op === '$=') return want !== '' && v.endsWith(want);
  if (a.op === '*=') return want !== '' && v.includes(want);
  return null;
}

const siblingsOf = (el) => (el.parent ? elementChildren(el.parent) : [el]);

function matchPseudo(el, p) {
  if (p.name === 'first-child') return siblingsOf(el)[0] === el;
  if (p.name === 'last-child') return siblingsOf(el).at(-1) === el;
  if (p.name === 'only-child') return siblingsOf(el).length === 1;
  if (p.name === 'root') return el.tag === 'html';
  if (!['is', 'where', 'matches', 'not'].includes(p.name)) return null;
  let r = false;
  for (const s of splitTopLevel(p.arg ?? '', ',')) {
    const cx = parseComplex(s);
    const x = cx && !cx.pseudoElement ? matchComplex(cx.parts, cx.parts.length - 1, el) : null;
    if (x === true) {
      r = true;
      break;
    }
    if (x === null) r = null;
  }
  if (p.name !== 'not') return r;
  return r === null ? null : !r;
}

function matchCompound(c, el) {
  if (c.tag && c.tag !== '*' && c.tag !== el.tag) return false;
  for (const id of c.ids) if (el.attrs.get('id') !== id) return false;
  for (const cls of c.classes) if (!el.classes.includes(cls)) return false;
  let r = true;
  for (const a of c.attrs) r = and3(r, matchAttr(el, a));
  if (r === false) return false;
  for (const p of c.pseudos) r = and3(r, matchPseudo(el, p));
  return r;
}

function matchAny(candidates, parts, idx) {
  let r = false;
  for (const cand of candidates) {
    const x = matchComplex(parts, idx, cand);
    if (x === true) return true;
    if (x === null) r = null;
  }
  return r;
}

function matchComplex(parts, idx, el) {
  const self = matchCompound(parts[idx].compound, el);
  if (self === false || idx === 0) return self;
  const comb = parts[idx].comb;
  let rest = null;
  if (comb === '>') rest = isEl(el.parent) ? matchComplex(parts, idx - 1, el.parent) : false;
  else if (comb === ' ') {
    const ancestors = [];
    for (let a = el.parent; isEl(a); a = a.parent) ancestors.push(a);
    rest = matchAny(ancestors, parts, idx - 1);
  } else if (comb === '+' || comb === '~') {
    const sibs = siblingsOf(el);
    const i = sibs.indexOf(el);
    const before = comb === '+' ? sibs.slice(Math.max(0, i - 1), i) : sibs.slice(0, i);
    rest = matchAny(before, parts, idx - 1);
  }
  return and3(self, rest);
}

/* ---------------------------------------------------------------------- per-page style index */

// Only rules that set one of these can matter to row 2; everything else is dropped at parse time.
const LAYOUT_PROPS = [
  'display',
  'min-width',
  'grid-template-columns',
  'grid-template',
  'grid',
  'grid-auto-columns',
  'flex-direction',
  'flex-flow',
  'overflow',
  'overflow-x',
  'white-space',
  'text-wrap',
  'text-wrap-mode',
  'overflow-wrap',
  'word-wrap',
  'word-break',
];
const sheetCache = new Map();

function layoutRulesOf(cssText) {
  let rules = sheetCache.get(cssText);
  if (rules) return rules;
  rules = [];
  for (const r of parseCssRules(cssText)) {
    const props = parseDecls(r.decl);
    if (!LAYOUT_PROPS.some((p) => props.has(p))) continue;
    const sels = splitTopLevel(r.selector, ',').map((raw) => ({
      raw,
      cx: parseComplex(raw),
      scoped: /data-astro-cid-/.test(raw),
    }));
    rules.push({ props, sels });
  }
  sheetCache.set(cssText, rules);
  return rules;
}

/** Style lookup for one page: `sheets` is a CSS string or an array of strings / { text, siteWide }. */
class PageStyles {
  constructor(sheets) {
    const list = (Array.isArray(sheets) ? sheets : [sheets]).map((s) =>
      typeof s === 'string' ? { text: s, siteWide: false } : s,
    );
    this.rules = list.flatMap((s) =>
      layoutRulesOf(s.text).map((rule) => ({ ...rule, siteWide: s.siteWide })),
    );
    this.cache = new Map();
  }

  /** [{ props, certain, containerEligible, selector }] for every rule that matches or may match. */
  decls(el) {
    let out = this.cache.get(el);
    if (out) return out;
    out = [];
    for (const rule of this.rules) {
      let best = false;
      let bestSel = null;
      for (const sel of rule.sels) {
        // A selector this matcher can't parse at all matches nothing: treating it as "maybe
        // everything" would turn one odd rule into a page-wide false alarm.
        if (!sel.cx || sel.cx.pseudoElement) continue;
        const m = matchComplex(sel.cx.parts, sel.cx.parts.length - 1, el);
        if (m === true || (m === null && best === false)) {
          best = m;
          bestSel = sel;
        }
        if (m === true) break;
      }
      if (best === false) continue;
      out.push({
        props: rule.props,
        certain: best === true,
        // Page-local = scoped to a component (Astro cid) or from a sheet not every page links.
        containerEligible: bestSel.scoped || !rule.siteWide,
        selector: bestSel.raw,
      });
    }
    const inline = el.attrs.get('style');
    if (inline) {
      const props = parseDecls(inline);
      out.push({ props, certain: true, containerEligible: true, selector: '[style]' });
    }
    this.cache.set(el, out);
    return out;
  }
}

/* --------------------------------------------------------------------------------------- row 2 */
// Row 2 flags real reflow RISK, not every grid/flex container. A page-local grid/flex container is
// a finding only when BOTH:
//  (a) it has no min-width:0 escape for the item concerned, where an escape is any of
//      1. a grid whose every column track has a fixed minimum (minmax(0, …), minmax(220px, …),
//         220px, …): per CSS Grid §6.6 an item only gets a content-based automatic minimum when it
//         spans a track whose min sizing function is `auto` (bare `1fr` = minmax(auto, 1fr) and
//         `auto` do); no grid-template-columns at all means implicit `auto` tracks, i.e. no escape;
//      2./3. a rule that certainly matches the item and sets min-width:0 -- a child-combinator
//         rule (`.blocks > section`, the gallery.astro fix) and a class on the item itself
//         (`.main`, DocsShell/PageBody/SecurityPage) are both just "a rule matching the item",
//         checked against the parsed DOM with Astro's scoping attributes intact;
//      4. the item is itself a scroll container (overflow/overflow-x auto|scroll|hidden): its
//         automatic minimum is 0 (CSS Grid §6.6, Flexbox §4.5) -- PipelineSteps' `.code` grid,
//         whose <pre> item scrolls, is the real example;
//  (b) some item (or a descendant of it) is unbreakable-width:
//      - a <pre> (lines never wrap),
//      - a box with overflow-x auto|scroll (its min-content width is its content's, so a nested
//        scroller does NOT protect the grid above it -- that was exactly the gallery bug),
//      - a run of >= 40 characters with no break opportunity: a hash/URL token in normal text, or
//        any text under white-space:nowrap|pre (where spaces don't break either). This is how "a
//        <code> not inside a wrapping element" and "an element whose CSS sets white-space:nowrap"
//        are checked: by the length of what they make unbreakable, not by their mere presence, so
//        a 9-character nowrap status pill is not a finding. Break opportunities counted:
//        whitespace (normal wrapping only), <br>/<wbr>, U+200B, soft hyphen, a hyphen before a
//        letter, block boundaries, and every character under overflow-wrap:anywhere /
//        word-break:break-all|break-word. "/" is NOT counted (URLs treated as unbreakable).
// Flex containers whose direction is column are skipped (min-width:auto acts on the main axis).
//
// "Page-local" means: a grid/flex rule scoped to a component (Astro's data-astro-cid attribute)
// or from a stylesheet that not every inner page links. Unscoped rules from the site-wide bundle
// (packages/themes, `nf-*` utilities) are not containers here; see the test file header. Escape
// and risk properties (min-width, overflow, white-space, overflow-wrap) come from ALL linked CSS.
//
// Honest limits (no layout engine): a rule in any @media counts as always applying (worst case
// for risk; a min-width:0 inside a media query still counts as an escape); cascade order and
// specificity are ignored (a later `white-space: normal` doesn't cancel an earlier nowrap);
// selectors with :hover/:has()/:nth-child() are "maybe" matches, counted as risk and container
// matches but never as escapes; which track an item lands in isn't modelled (any content-sized
// track makes every item count); replaced elements (img, video, canvas, svg), form controls and
// text directly inside a flex/grid container (an anonymous item) aren't measured; fixed-width
// wrappers that would contain a long line aren't recognised. Per the spec, min-width:0 stops the
// grid growing but a bare long token still overflows its now-narrower item unless it also gets
// overflow-wrap:anywhere -- the message says so. apps/web/e2e/visual.spec.ts is the real check.

export const LONG_TOKEN = 40;
const INLINE_TAGS = new Set([
  'a',
  'abbr',
  'b',
  'bdi',
  'bdo',
  'cite',
  'code',
  'data',
  'del',
  'dfn',
  'em',
  'i',
  'ins',
  'kbd',
  'label',
  'mark',
  'output',
  'q',
  's',
  'samp',
  'small',
  'span',
  'strong',
  'sub',
  'sup',
  'time',
  'u',
  'var',
]);
// Subtrees row 2 never measures: not rendered, out of flow, or replaced/control content.
const SKIP_SUBTREE_TAGS = new Set([
  'script',
  'style',
  'template',
  'noscript',
  'svg',
  'math',
  'canvas',
  'iframe',
  'video',
  'audio',
  'img',
  'picture',
  'object',
  'embed',
  'select',
  'textarea',
  'input',
  'head',
]);

function skipForLayout(el) {
  if (SKIP_SUBTREE_TAGS.has(el.tag) || el.attrs.has('hidden')) return true;
  if (el.classes.includes('nf-visually-hidden')) return true;
  return /display\s*:\s*none/i.test(el.attrs.get('style') ?? '');
}

const GRID_FLEX_RE = /^(?:inline-)?(?:grid|flex)$/;
const MIN_WIDTH_ZERO_RE = /^0(?:\.0+)?(?:px|r?em|%)?$/;
const LENGTH_RE =
  /^-?\d*\.?\d+(?:px|r?em|ch|ex|lh|rlh|vw|vh|vmin|vmax|[sdl]vw|cq[iw]|%|cm|mm|in|pt|pc|q)$/i;
const overflowX = (props) => props.get('overflow-x') ?? props.get('overflow')?.split(/\s+/)[0];
const isContainerDecl = (d) =>
  d.containerEligible && GRID_FLEX_RE.test(d.props.get('display') ?? '');

function isFixedLength(t) {
  const s = t.trim();
  if (/^0(?:\.0+)?$/.test(s)) return true;
  if (/^(?:calc|min|max|clamp)\(/.test(s)) return !/fr\b|auto|content/.test(s);
  return LENGTH_RE.test(s);
}

function trackHasFixedMin(track) {
  const fn = /^([a-z-]+)\(([\s\S]*)\)$/.exec(track.trim());
  if (!fn) return isFixedLength(track);
  if (fn[1] === 'minmax') return isFixedLength(splitTopLevel(fn[2], ',')[0] ?? '');
  if (fn[1] === 'repeat') return trackListSafe(splitTopLevel(fn[2], ',').slice(1).join(','));
  if (['calc', 'min', 'max', 'clamp'].includes(fn[1])) return isFixedLength(track);
  return false; // fit-content() and anything unrecognised: content-sized minimum
}

function trackListSafe(value) {
  const cleaned = value.replace(/\[[^\]]*\]/g, ' ').replace(/\b(?:auto-flow|dense)\b/g, ' ');
  const tracks = splitTopLevel(cleaned, ' ');
  return tracks.length > 0 && tracks.every(trackHasFixedMin);
}

/** True when every column-track definition any matching rule gives this grid has fixed minimums. */
function gridTracksSafe(decls) {
  const cols = [];
  const autoCols = [];
  for (const d of decls) {
    const p = d.props;
    if (p.has('grid-template-columns')) cols.push(p.get('grid-template-columns'));
    for (const sh of ['grid-template', 'grid']) {
      if (!p.has(sh)) continue;
      const parts = splitTopLevel(p.get(sh), '/');
      cols.push(parts.length > 1 ? parts[1] : 'none');
    }
    if (p.has('grid-auto-columns')) autoCols.push(p.get('grid-auto-columns'));
  }
  if (cols.length === 0) cols.push('none');
  const safe = (v) => {
    if (v !== 'none') return trackListSafe(v);
    return autoCols.length > 0 && autoCols.every(trackListSafe);
  };
  return cols.every(safe);
}

const hasMinWidthZero = (decls) =>
  decls.some((d) => d.certain && MIN_WIDTH_ZERO_RE.test(d.props.get('min-width') ?? ''));
const isScrollContainer = (decls) =>
  decls.some((d) => d.certain && /^(?:auto|scroll|hidden)$/.test(overflowX(d.props) ?? ''));
const flexDirection = (p) => p.get('flex-direction') ?? p.get('flex-flow') ?? '';

function whiteSpaceMode(decls, inherited) {
  let mode = null;
  for (const d of decls) {
    const p = d.props;
    const v = p.get('white-space') ?? p.get('text-wrap-mode') ?? p.get('text-wrap');
    if (!v) continue;
    if (/\bpre\b(?!-)/.test(v)) return 'pre';
    if (/\bnowrap\b/.test(v)) return 'nowrap';
    if (d.certain) mode = 'normal';
  }
  return mode ?? inherited;
}

function breaksAnywhere(decls, inherited) {
  if (inherited) return true;
  for (const d of decls) {
    if (!d.certain) continue;
    const wrap = d.props.get('overflow-wrap') ?? d.props.get('word-wrap') ?? '';
    if (wrap === 'anywhere' || /^break-(?:all|word)$/.test(d.props.get('word-break') ?? ''))
      return true;
  }
  return false;
}

/** First unbreakable-width thing inside `item` (item included): { el, why, token } or null. */
function findUnbreakable(item, styles) {
  let run = 0;
  let runText = '';
  let runEl = null;
  let found = null;
  const reset = () => {
    run = 0;
    runText = '';
  };
  const push = (ch, el) => {
    if (run === 0) runEl = el;
    run++;
    if (runText.length < 48) runText += ch;
    if (run >= LONG_TOKEN && !found) {
      const why = `a ${LONG_TOKEN}+-character run with no break opportunity ("${runText.trim()}…")`;
      found = { el: runEl, why, token: true };
    }
  };
  const visitText = (node, ctx) => {
    const t = node.text;
    let lastSpace = false;
    for (let i = 0; i < t.length && !found; i++) {
      const ch = t[i];
      const space = /[ \t\n\r\f]/.test(ch);
      if (ctx.anywhere) reset();
      else if (ctx.ws === 'normal') {
        if (space || ch === ZWSP || ch === SHY) reset();
        else {
          push(ch, node.parent);
          if (ch === '-' && /[A-Za-z]/.test(t[i + 1] ?? '')) reset();
        }
      } else if (ctx.ws === 'pre' && ch === '\n') reset();
      else if (!(space && ctx.ws === 'nowrap' && lastSpace)) push(space ? ' ' : ch, node.parent);
      lastSpace = space;
    }
  };
  const visit = (node, ctx, isItem) => {
    if (found) return;
    if (node.type === 'text') return visitText(node, ctx);
    if (skipForLayout(node)) return;
    if (node.tag === 'br') return reset();
    if (node.tag === 'wbr') {
      if (ctx.ws === 'normal') reset();
      return;
    }
    if (node.tag === 'pre') {
      found = { el: node, why: 'a <pre> (preformatted lines never wrap)', token: false };
      return;
    }
    const decls = styles.decls(node);
    if (!isItem && decls.some((d) => /^(?:auto|scroll)$/.test(overflowX(d.props) ?? ''))) {
      const why = "an overflow-x:auto/scroll box (a scroller's min-content width is its content's)";
      found = { el: node, why, token: false };
      return;
    }
    const next = {
      ws: whiteSpaceMode(decls, ctx.ws),
      anywhere: breaksAnywhere(decls, ctx.anywhere),
    };
    const block = !INLINE_TAGS.has(node.tag);
    if (block) reset();
    for (const c of node.children) visit(c, next, false);
    if (block) reset();
  };
  visit(item, { ws: 'normal', anywhere: false }, true);
  return found;
}

/**
 * Row 2 over one page. `sheets`: this page's CSS (a string, or an array of strings or
 * { text, siteWide } -- siteWide sheets contribute only their component-scoped rules as
 * containers); `html`: the page's built HTML. Returns { problems, containers }, where containers
 * counts the grid/flex containers actually examined (the anti-vacuous-pass number).
 */
export function gridFlexMinWidthProblems(route, sheets, html) {
  const styles = new PageStyles(sheets);
  const body = findBody(parseHtml(html));
  const problems = [];
  let containers = 0;
  for (const el of elements(body, skipForLayout)) {
    const decls = styles.decls(el);
    const displays = decls.filter(isContainerDecl);
    if (displays.length === 0) continue;
    const isGrid = displays.every((d) => /grid$/.test(d.props.get('display')));
    const isFlex = displays.every((d) => /flex$/.test(d.props.get('display')));
    const columnOnly =
      isFlex &&
      decls.some((d) => d.certain && /^column/.test(flexDirection(d.props))) &&
      !decls.some((d) => /^row/.test(flexDirection(d.props)));
    if (columnOnly) continue;
    containers++;
    if (isGrid && gridTracksSafe(decls)) continue;
    for (const item of elementChildren(el)) {
      if (skipForLayout(item)) continue;
      const itemDecls = styles.decls(item);
      if (hasMinWidthZero(itemDecls) || isScrollContainer(itemDecls)) continue;
      const hit = findUnbreakable(item, styles);
      if (!hit) continue;
      const selector = normalizeSelector(displays[0].selector);
      const display = displays[0].props.get('display');
      const fix = hit.token ? ' plus overflow-wrap:anywhere on the text' : '';
      problems.push({
        row: 2,
        route,
        selector,
        message:
          `${route}: <${describeEl(el)}> ("${selector}", display:${display}) -- its item ` +
          `<${describeEl(item)}> has no min-width:0 and contains ${hit.why} in ` +
          `<${describeEl(hit.el)}>, which can force the ${isGrid ? 'grid' : 'flex row'} (and ` +
          `the page) wider than the viewport (row 2). Fix: min-width:0 on the item${fix}. ` +
          `Static heuristic; apps/web/e2e/visual.spec.ts is the real overflow check.`,
      });
      break; // one finding per container is enough to act on
    }
  }
  return { problems, containers };
}

/* ------------------------------------------------------------------------ page-script helpers */

/** Astro page source -> the .ts files its bare `<script>import '…ts'</script>` blocks load. */
export function resolvePageScripts(webRoot, urlPath) {
  const slug = urlPath.replace(/^\/|\/$/g, '');
  const candidates = slug
    ? [join(webRoot, 'src/pages', `${slug}.astro`), join(webRoot, 'src/pages', slug, 'index.astro')]
    : [join(webRoot, 'src/pages/index.astro')];
  const astroFile = candidates.find((f) => existsSync(f));
  if (!astroFile) return { astroFile: null, scripts: [] };
  const text = readFileSync(astroFile, 'utf8');
  const scripts = [];
  for (const sm of text.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/gi))
    for (const im of sm[1].matchAll(/import\s+['"]([^'"]+\.ts)['"]/g))
      scripts.push(resolve(dirname(astroFile), im[1]));
  return { astroFile, scripts };
}

const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
/** Regex source for "the element held in `prop`, then a dot": `ui.live.`, `live!.`, … */
const refTo = (prop) => `(?<![\\w$])${escRe(prop)}\\s*!?\\s*\\.`;
const WRITE_PROPS = 'textContent|innerHTML|innerText|outerHTML|value';
const WRITE_CALLS =
  'replaceChildren|append|appendChild|prepend|insertAdjacentHTML|insertAdjacentText|replaceWith';
const SETS_VALUETEXT = `(?:setAttribute\\(\\s*['"]aria-valuetext['"]|ariaValueText\\s*=(?!=))`;

const HOOK_LOOKUP_RE =
  /(\w+)\s*[:=]\s*(?:[\w$.]+\.)?(?:q|qs|querySelector)(?:<[^>]*>)?\(\s*(?:[\w$.]+\s*,\s*)?['"]\[(data-[a-z0-9-]+)\]['"]\s*\)/g;
const ID_LOOKUP_RE =
  /(\w+)\s*[:=]\s*(?:[\w$.]+\.)?getElementById(?:<[^>]*>)?\(\s*['"]([^'"]+)['"]\s*\)/g;

/**
 * prop -> hook for every element a script looks up by hook: `name: q(el, '[data-x]')`,
 * `name = el.querySelector<T>('[data-x]')` (hook 'data-x') and `name = …getElementById('x')`
 * (hook '#x'). This is the construction pattern playground.ts, arena.ts and interface.ts all use.
 */
export function scriptPropHooks(scriptText) {
  const map = new Map();
  for (const m of scriptText.matchAll(HOOK_LOOKUP_RE))
    if (!map.has(m[1])) map.set(m[1], m[2].toLowerCase());
  for (const m of scriptText.matchAll(ID_LOOKUP_RE)) if (!map.has(m[1])) map.set(m[1], `#${m[2]}`);
  return map;
}

/** Script props that refer to this element (via one of its data-* attributes or its id). */
function propsForEl(el, propHooks) {
  const hooks = new Set([...el.attrs.keys()].filter((k) => k.startsWith('data-')));
  if (el.attrs.get('id')) hooks.add(`#${el.attrs.get('id')}`);
  return [...propHooks].filter(([, hook]) => hooks.has(hook)).map(([prop]) => prop);
}

/** Brace-matched body of the callback starting at `idx` (concise arrows: the expression). */
function extractCallbackBody(text, idx) {
  let parenDepth = 0;
  for (let j = idx; j < text.length; j++) {
    const c = text[j];
    if (c === '(') parenDepth++;
    else if (c === ')') {
      if (parenDepth === 0) return text.slice(idx, j).trim();
      parenDepth--;
    } else if (c === '{' && parenDepth === 0) {
      let depth = 1;
      let k = j + 1;
      while (k < text.length && depth > 0) {
        if (text[k] === '{') depth++;
        else if (text[k] === '}') depth--;
        k++;
      }
      return text.slice(j + 1, k - 1);
    }
  }
  return null;
}

const METHOD_RE =
  /\n\s*(?:(?:export|private|public|protected|static|async|function)\s+)*([A-Za-z_$][\w$]*)\s*\(([^()]*)\)\s*(?::\s*[^{};=]+?)?\s*\{/g;
const NOT_METHODS = new Set([
  'if',
  'for',
  'while',
  'switch',
  'catch',
  'function',
  'constructor',
  'return',
]);

/** name -> body for every method / function-declaration-shaped block (constructor excluded). */
function methodBodyMap(text) {
  const map = new Map();
  const re = new RegExp(METHOD_RE.source, 'g');
  let m;
  while ((m = re.exec(text))) {
    const name = m[1];
    if (NOT_METHODS.has(name)) continue;
    const braceIdx = re.lastIndex - 1;
    let depth = 1;
    let k = braceIdx + 1;
    while (k < text.length && depth > 0) {
      if (text[k] === '{') depth++;
      else if (text[k] === '}') depth--;
      k++;
    }
    if (!map.has(name)) map.set(name, text.slice(braceIdx + 1, k - 1));
  }
  return map;
}

/** Listener callbacks as { target, event, body }; target = the expression before the call. */
function listeners(scriptText) {
  const out = [];
  const re = /([\w$.!]+)\s*\.addEventListener\(\s*['"]([\w-]+)['"]\s*,\s*/g;
  let m;
  while ((m = re.exec(scriptText))) {
    const body = extractCallbackBody(scriptText, re.lastIndex);
    if (body !== null) out.push({ target: m[1].replace(/!/g, ''), event: m[2], body });
  }
  return out;
}

const isValueEvent = (l) => l.event === 'input' || l.event === 'change';
const listensOn = (l, prop) => new RegExp(`(?:^|\\.)${escRe(prop)}$`).test(l.target);

/**
 * `body` plus the bodies of the methods/functions it names directly -- one level only:
 * `this.x(…)`, a passed reference `this.x` / `this.x.bind(this)`, or a bare `x(…)` call.
 */
function expandOneLevel(body, methods, self) {
  let out = body;
  const names = new Set();
  for (const m of body.matchAll(/\bthis\.([A-Za-z_$][\w$]*)\b(?!\s*=(?!=))/g)) names.add(m[1]);
  for (const m of body.matchAll(/(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(/g)) names.add(m[1]);
  for (const name of names) {
    const m = methods.get(name);
    if (m && name !== self) out += `\n${m}`;
  }
  return out;
}

/** Does `text` write content into the element held in `prop`? */
function writesTo(text, prop) {
  const re = new RegExp(`${refTo(prop)}(?:(?:${WRITE_PROPS})\\s*=(?!=)|(?:${WRITE_CALLS})\\s*\\()`);
  return re.test(text);
}

/**
 * The script's "update units": each event-listener callback, and each method/function body with
 * any listener callbacks cut out of it (those are their own units), each expanded one call level.
 * Two elements are "updated from the same handler/event" when some unit writes both.
 */
function updateUnits(scriptText) {
  const methods = methodBodyMap(scriptText);
  const units = listeners(scriptText).map((l) => expandOneLevel(l.body, methods));
  for (const [name, body] of methods) {
    let own = body;
    for (const l of listeners(body)) own = own.replace(l.body, ' ');
    units.push(expandOneLevel(own, methods, name));
  }
  return units;
}

/* ------------------------------------------------------------------------------------ rows 3/4 */
// A "live" element is aria-live="polite"/"assertive", or role="status"/"alert"/"log" (implicit
// live regions). aria-live="off" is a deliberate opt-out (/playground's and /interface's <output>
// readouts) and is never a live region, so never a violation.
function isLive(el) {
  const live = el.attrs.get('aria-live')?.trim().toLowerCase();
  if (live !== undefined) return live === 'polite' || live === 'assertive';
  const role = el.attrs.get('role')?.trim().toLowerCase();
  return role === 'status' || role === 'alert' || role === 'log';
}

function liveRegions(root) {
  return [...elements(root)]
    .filter(isLive)
    .map((el) => ({ el, hidden: el.classes.includes('nf-visually-hidden'), desc: describeEl(el) }));
}

/** Number of live regions on a page (the real-dist test's anti-vacuous-pass count). */
export function countLiveRegions(html) {
  return liveRegions(parseHtml(html)).length;
}

/**
 * Row 3a: a visible (not .nf-visually-hidden) live region whose rendered markup already holds
 * structural content (a list, table or heading, or 2+ paragraphs) -- the shape of a results panel
 * doubling as a live region. Limitation: judges the markup at render only; a region that is empty
 * at render and filled later is row 3b's job (script check) or a reviewer's.
 */
export function liveStructureProblems(route, html) {
  const problems = [];
  for (const r of liveRegions(parseHtml(html))) {
    if (r.hidden) continue;
    const inner = [...elements(r.el)];
    const structural =
      inner.some((e) => /^(?:ul|ol|dl|table|h[1-6])$/.test(e.tag)) ||
      inner.filter((e) => e.tag === 'p').length >= 2;
    if (!structural) continue;
    problems.push({
      row: 3,
      route,
      selector: r.desc,
      message:
        `${route}: visible live region <${r.desc}> contains a list/table/heading or 2+ ` +
        `paragraphs (row 3) -- a results panel, not a status line; announce a summary from a ` +
        `hidden status line instead`,
    });
  }
  return problems;
}

/**
 * Row 3b: the page script re-renders a live region in full (`<prop>.innerHTML =` or
 * insertAdjacentHTML) -- a screen reader re-announces the whole block every time. Only elements
 * the script looks up by data-* hook or id are followed (scriptPropHooks); a helper that receives
 * the element as a parameter slips through (documented, not guessed at).
 */
export function innerHtmlIntoLiveProblems(route, html, scriptText) {
  if (!scriptText) return [];
  const hooks = scriptPropHooks(scriptText);
  const problems = [];
  for (const r of liveRegions(parseHtml(html))) {
    for (const prop of propsForEl(r.el, hooks)) {
      const re = new RegExp(`${refTo(prop)}(?:innerHTML\\s*=(?!=)|insertAdjacentHTML\\s*\\()`);
      if (!re.test(scriptText)) continue;
      problems.push({
        row: 3,
        route,
        selector: r.desc,
        message:
          `${route}: script re-renders live region <${r.desc}> via ${prop}.innerHTML on every ` +
          `update (row 3) -- use a short textContent status line`,
      });
    }
  }
  return problems;
}

const COMPONENT_ROOT_TAGS = new Set(['section', 'article', 'form', 'fieldset']);

function isComponentRoot(el) {
  if (!isEl(el)) return false;
  return COMPONENT_ROOT_TAGS.has(el.tag) || [...el.attrs.keys()].some(isHookAttr);
}

function nearestCommonAncestor(a, b) {
  const chain = new Set();
  for (let n = a.parent; n; n = n.parent) chain.add(n);
  for (let n = b.parent; n; n = n.parent) if (chain.has(n)) return n;
  return null;
}

/**
 * Row 4: a VISIBLE live region re-announcing what a HIDDEN, dedicated live region already
 * announces a summary of (the /arena bug: `.arena-card` was aria-live next to the hidden status
 * line, and one run updated both). Two live regions with different purposes (an error summary and
 * a separate "saved" confirmation) are fine. For every (visible, hidden) pair:
 *  - if the page script looks both up (scriptPropHooks), the pair is a finding only when one
 *    update unit (a listener callback, or a method body, each followed one call level) writes to
 *    both;
 *  - if the script can't be resolved for both, fall back to structure: a finding when their
 *    nearest common ancestor is a section/article/form/fieldset or a data-* component root.
 * Limitation: one handler that writes the two regions in mutually exclusive branches (if/else) is
 * still flagged -- static text can't tell the branches apart; that case goes on the allowlist with
 * a reason. Call chains deeper than one level are not followed (a false pass, documented).
 */
export function duplicateLiveProblems(route, html, scriptTexts = []) {
  const regions = liveRegions(parseHtml(html));
  const hidden = regions.filter((r) => r.hidden);
  const visible = regions.filter((r) => !r.hidden);
  const scripts = scriptTexts.map((text) => ({ text, hooks: scriptPropHooks(text), units: null }));
  const problems = [];
  for (const v of visible) {
    for (const h of hidden) {
      const resolved = scripts
        .map((s) => ({ s, pv: propsForEl(v.el, s.hooks), ph: propsForEl(h.el, s.hooks) }))
        .filter((x) => x.pv.length && x.ph.length);
      let evidence = null;
      if (resolved.length) {
        for (const { s, pv, ph } of resolved) {
          s.units ??= updateUnits(s.text);
          const both = (u) => pv.some((a) => writesTo(u, a)) && ph.some((b) => writesTo(u, b));
          if (s.units.some(both)) evidence = 'the same handler in the page script updates both';
        }
      } else {
        const nca = nearestCommonAncestor(v.el, h.el);
        if (isComponentRoot(nca))
          evidence = `both sit in the same <${describeEl(nca)}> (page script not resolved)`;
      }
      if (!evidence) continue;
      problems.push({
        row: 4,
        route,
        selector: `${v.desc} + ${h.desc}`,
        message:
          `${route}: visible live region <${v.desc}> and hidden live region <${h.desc}> -- ` +
          `${evidence}, so one event is announced twice (row 4). ` +
          `Keep only the hidden status line live.`,
      });
    }
  }
  return problems;
}

/* --------------------------------------------------------------------------------------- row 5 */

const LABELLABLE = new Set(['input', 'select', 'textarea', 'meter', 'progress', 'output']);

/**
 * Row 5: information reachable only by hovering a title=. An element is a finding only when ALL
 * hold:
 *  - it has no aria-label / aria-labelledby (then it has a real accessible name);
 *  - for img/area/input[type=image]: its alt doesn't contain the title text; for form controls:
 *    no associated <label> (for= or wrapping) contains it;
 *  - its own visible text doesn't contain the title text (a title that merely repeats the
 *    element's text adds nothing; one that ADDS information to visible text -- <abbr title="World
 *    Health Organization">WHO</abbr>, the /docs/api `<span title="…">200</span>` bug -- is still
 *    hover-only);
 *  - the title text isn't present anywhere else on the page as text (visible or
 *    .nf-visually-hidden).
 * iframe title is its accessible name (always allowed); SVG subtrees and <head> are not checked.
 * Limitation: case-insensitive substring matching, so a short or common title ("Info", "Details")
 * that happens to appear elsewhere on the page counts as present (a false negative), and text
 * inside aria-hidden nodes still counts as "present". Catches the common case, not every case.
 */
export function titleOnlyProblems(route, html) {
  const root = parseHtml(html);
  const pageText = norm(visibleText(html.replace(/<!--[\s\S]*?-->/g, ' ')));
  const problems = [];
  const skip = (e) => e.tag === 'svg' || e.tag === 'template';
  for (const el of elements(findBody(root), skip)) {
    const title = el.attrs.get('title')?.trim();
    if (!title || el.tag === 'iframe') continue;
    if (el.attrs.get('aria-label')?.trim() || el.attrs.get('aria-labelledby')?.trim()) continue;
    const t = norm(title);
    const type = (el.attrs.get('type') ?? '').toLowerCase();
    const hasAlt = ['img', 'area'].includes(el.tag) || (el.tag === 'input' && type === 'image');
    if (hasAlt && norm(el.attrs.get('alt') ?? '').includes(t)) continue;
    if (LABELLABLE.has(el.tag)) {
      const id = el.attrs.get('id');
      const labels = id
        ? [...elements(root)].filter((l) => l.tag === 'label' && l.attrs.get('for') === id)
        : [];
      for (let a = el.parent; isEl(a); a = a.parent) if (a.tag === 'label') labels.push(a);
      if (labels.some((l) => norm(textOf(l)).includes(t))) continue;
    }
    if (norm(textOf(el)).includes(t) || pageText.includes(t)) continue;
    const shown = title.length > 60 ? `${title.slice(0, 60)}…` : title;
    problems.push({
      row: 5,
      route,
      selector: `${el.tag}[title="${title}"]`,
      message:
        `${route}: <${describeEl(el)} title="${shown}"> -- that text is reachable only by hover ` +
        `(row 5); add it as visible or .nf-visually-hidden text`,
    });
  }
  return problems;
}

/* --------------------------------------------------------------------------------------- row 7 */

/**
 * Row 7b's handler heuristic: some 'input'/'change' listener (on `rangeProp` when given, else any),
 * followed one call level, both writes a visible value (`.value =` / `.textContent =`) and sets
 * aria-valuetext (setAttribute or .ariaValueText =; on `rangeProp` itself when given).
 */
export function scriptSyncsValuetext(scriptText, rangeProp = null) {
  const methods = methodBodyMap(scriptText);
  const owner = rangeProp ? refTo(rangeProp) : '\\.';
  const setsRe = new RegExp(`${owner}${SETS_VALUETEXT}`);
  for (const l of listeners(scriptText)) {
    if (!isValueEvent(l) || (rangeProp && !listensOn(l, rangeProp))) continue;
    const body = expandOneLevel(l.body, methods);
    if (/\.(?:value|textContent)\s*=(?!=)/.test(body) && setsRe.test(body)) return true;
  }
  return false;
}

/**
 * A range's companion visible value display, or null. A companion is: an <output for="…"> naming
 * the range's id; an element named by its aria-describedby/aria-controls; an <output> in the
 * range's own <label> (or, without one, its parent element) -- the /arena and /playground
 * pattern; or an element near the range (same grandparent) that the range's own input/change
 * listener writes into.
 */
function rangeCompanion(root, range, scripts) {
  const id = range.attrs.get('id');
  for (const el of elements(root))
    if (el.tag === 'output' && id && (el.attrs.get('for') ?? '').split(/\s+/).includes(id))
      return { el, how: `<output for="${id}">` };
  for (const attr of ['aria-describedby', 'aria-controls'])
    for (const ref of (range.attrs.get(attr) ?? '').split(/\s+/).filter(Boolean)) {
      const el = byId(root, ref);
      if (el) return { el, how: `${attr}="${ref}"` };
    }
  let scope = range.parent;
  for (let a = range.parent; isEl(a); a = a.parent)
    if (a.tag === 'label') {
      scope = a;
      break;
    }
  if (isEl(scope)) {
    const out = [...elements(scope)].find((e) => e.tag === 'output');
    if (out) return { el: out, how: 'a nearby <output>' };
  }
  const near = isEl(range.parent?.parent) ? range.parent.parent : range.parent;
  for (const { hooks, text } of scripts) {
    const methods = methodBodyMap(text);
    for (const prop of propsForEl(range, hooks)) {
      for (const l of listeners(text)) {
        if (!isValueEvent(l) || !listensOn(l, prop)) continue;
        const body = expandOneLevel(l.body, methods);
        for (const [other, hook] of hooks) {
          if (other === prop || !writesTo(body, other)) continue;
          const el = [...elements(near)].find((e) =>
            hook.startsWith('#') ? e.attrs.get('id') === hook.slice(1) : e.attrs.has(hook),
          );
          if (el) return { el, how: `a nearby element its handler writes into (${other})` };
        }
      }
    }
  }
  return null;
}

/** A range inside a `hidden` subtree (or a <template>) isn't perceivable before its script runs. */
function hiddenAtRender(el) {
  for (let a = el; isEl(a); a = a.parent)
    if (a.attrs.has('hidden') || a.tag === 'template') return true;
  return false;
}

/**
 * Row 7 over one page. A range needs aria-valuetext only when it has a companion visible value
 * display (see rangeCompanion); a bare range whose native value is all a sighted user sees passes.
 * For each range with a companion:
 *  - 7a: aria-valuetext must be present (non-empty) at render (JS-off / not-yet-run users),
 *    unless the range sits in a `hidden` subtree at render (e.g. /playground's JS-only form);
 *  - 7b (only when `scriptTexts` is given): an input/change listener on that range (via its script
 *    property; any listener if the range can't be tied to one) must update aria-valuetext in the
 *    same handler as the visible value, one call level followed. `scriptTexts` = [] means "the
 *    page has a companion display but no script could be resolved", which is reported.
 * Returns { problems, ranges, withCompanion }.
 */
export function rangeProblems(route, html, scriptTexts = null) {
  const root = parseHtml(html);
  const scripts = (scriptTexts ?? []).map((text) => ({ text, hooks: scriptPropHooks(text) }));
  const problems = [];
  let ranges = 0;
  let withCompanion = 0;
  for (const el of elements(findBody(root))) {
    if (el.tag !== 'input' || (el.attrs.get('type') ?? '').toLowerCase() !== 'range') continue;
    ranges++;
    const companion = rangeCompanion(root, el, scripts);
    if (!companion) continue;
    withCompanion++;
    const desc = describeEl(el);
    const base = { row: 7, route, selector: desc };
    if (!hiddenAtRender(el) && !el.attrs.get('aria-valuetext')?.trim())
      problems.push({
        ...base,
        message:
          `${route}: <${desc} type="range"> shows its value in ${companion.how} but has no ` +
          `aria-valuetext at render (row 7a)`,
      });
    if (scriptTexts === null) continue;
    if (scripts.length === 0) {
      problems.push({
        ...base,
        message:
          `${route}: <${desc} type="range"> has a companion value display but no page script ` +
          `could be resolved to check it keeps aria-valuetext in sync (row 7b)`,
      });
      continue;
    }
    const props = scripts.flatMap((s) => propsForEl(el, s.hooks).map((p) => ({ s, p })));
    const ok = props.length
      ? props.some(({ s, p }) => scriptSyncsValuetext(s.text, p))
      : scripts.some((s) => scriptSyncsValuetext(s.text));
    if (!ok)
      problems.push({
        ...base,
        message:
          `${route}: no input/change handler for <${desc} type="range"> updates aria-valuetext ` +
          `together with the visible value (row 7b) -- compare playground.ts settingsChanged()`,
      });
  }
  return { problems, ranges, withCompanion };
}
