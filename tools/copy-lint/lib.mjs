// copy-lint core. Zero dependencies. See README.md for the rules and their rationale.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { extname, join, basename, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export const EXTENSIONS = new Set(['.json', '.md', '.mdx', '.html', '.htm', '.astro']);
const SKIP_DIRS = new Set(['node_modules', 'dist', '.git', '.astro', '.venv', 'target']);

// Letter/number boundaries (Unicode aware). Hyphen-like and space-like classes.
const L = '(?<![\\p{L}\\p{N}_])';
const R = '(?![\\p{L}\\p{N}_])';
const H = '[-\\u2010\\u2011\\u2012\\u2013\\u2014]';
const S = '[\\s\\u00a0]+'; // one or more spaces
const S0 = '[\\s\\u00a0]*'; // optional spaces
const HS = '(?:[-\\u2010\\u2011\\u2012\\u2013\\u2014\\s\\u00a0])+'; // any run of hyphens/spaces

/** Banned terms. `term` is what gets reported; `re` is the matcher (flags added below). */
export const RULES = [
  { term: 'built-in', re: `${L}built${S0}${H}${S0}in${R}|${L}builtin${R}` },
  // "live" only as a status. Plain "live" (e.g. "live streams", "where people live") is fine;
  // see README "The live rule". Standalone "Live" labels are handled by the segment check.
  {
    term: 'live',
    re:
      `${L}(?:(?:is|are|was|were|be|been|being|go|goes|going|went|gone|now|currently|already)${S}live` +
      `|live${S}(?:now|today|product|service|platform|beta|release|version|in${S}production)` +
      `|(?:status|state)${S0}[:=]${S0}live)${R}`,
  },
  { term: 'available now', re: `${L}available${S}now${R}|${L}now${S}available${R}` },
  { term: 'certified', re: `${L}certified${R}` },
  { term: 'HIPAA-compliant', re: `${L}hipaa${HS}?compliant${R}` },
  { term: 'SOC 2 compliant', re: `${L}soc${HS}?2(?:${S}type${S}(?:ii|i|2|1))?${HS}compliant${R}` },
  { term: 'treat', re: `${L}treat(?:s|ed|ing)?${R}` },
  { term: 'diagnose', re: `${L}diagnos(?:e|es|ed|ing)${R}` },
  { term: 'cure', re: `${L}cur(?:e|es|ed|ing)${R}` },
  { term: 'restore', re: `${L}restor(?:e|es|ed|ing)${R}` },
  { term: 'automated neuro-cleaning', re: `${L}automated${S}neuro${HS}?cleaning${R}` },
].map((r) => ({ ...r, rx: new RegExp(r.re, 'giu') }));

/** Negations that allowlist a hit when they occur up to NEG_WINDOW words earlier in the same clause. */
export const NEGATIONS = new Set([
  'not',
  'never',
  'no',
  'non',
  'nor',
  'neither',
  'without',
  'cannot',
  "isn't",
  "aren't",
  "wasn't",
  "weren't",
  "don't",
  "doesn't",
  "didn't",
  "won't",
  "can't",
  'isn’t',
  'aren’t',
  'don’t',
  'doesn’t',
  'won’t',
  'can’t',
  // Norwegian (bokmål): "skal ikke brukes til diagnose", "aldri", "ingen", "uten", "verken/hverken ... eller"
  'ikke',
  'aldri',
  'ingen',
  'uten',
  'verken',
  'hverken',
]);
export const NEG_WINDOW = 4;

/** Mock UI labels: numbers inside mock UI must sit next to one of these. */
export const MOCK_LABEL = /demo\s+data|\btarget\b|\bestimated?\b/i;

// JSON keys whose string values are not copy (URLs, ids, paths, CSS classes).
const JSON_SKIP_KEYS = new Set([
  'href',
  'url',
  'src',
  'source',
  'sources',
  'slug',
  'id',
  'path',
  'icon',
  'class',
  'classname',
  '$schema',
  'image',
  'file',
  'doi',
  'pmid',
  'arxiv',
  'rel',
  'type',
  'key',
]);

const VOID = new Set([
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
  'source',
  'track',
  'wbr',
]);
const ENTITIES = {
  nbsp: ' ',
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  ndash: '–',
  mdash: '—',
  shy: '',
  hyphen: '‐',
};

function lineStarts(src) {
  const starts = [0];
  for (let i = 0; i < src.length; i++) if (src[i] === '\n') starts.push(i + 1);
  return starts;
}
function lineOf(starts, off) {
  let lo = 0,
    hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= off) lo = mid;
    else hi = mid - 1;
  }
  return lo + 1;
}

function blankRange(out, a, b) {
  for (let i = a; i < b && i < out.length; i++)
    if (out[i] !== '\n' && out[i] !== '\r') out[i] = ' ';
}

/** Blank URLs so hosts/paths such as "live.example.com" never match. */
function blankUrls(out) {
  const s = out.join('');
  for (const m of s.matchAll(/\b(?:https?:\/\/|mailto:|www\.)[^\s"'<>)\]]+/gi))
    blankRange(out, m.index, m.index + m[0].length);
}

/** Decode HTML entities in place, padding with spaces so offsets (and lines) are kept. */
function decodeEntities(out) {
  const s = out.join('');
  for (const m of s.matchAll(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi)) {
    let ch;
    const k = m[1];
    if (k[0] === '#')
      ch = String.fromCodePoint(
        k[1] === 'x' || k[1] === 'X' ? parseInt(k.slice(2), 16) : parseInt(k.slice(1), 10),
      );
    else ch = ENTITIES[k.toLowerCase()];
    if (ch === undefined) continue;
    const arr = [...ch.padEnd(m[0].length, ' ')];
    for (let i = 0; i < m[0].length; i++) out[m.index + i] = arr[i] ?? ' ';
  }
}

/**
 * HTML/Astro/MDX-ish scanner. Returns the visible text with the same length and line
 * structure as the source (non-visible characters become spaces), the text segments
 * (runs between tags), and mock regions (elements carrying a data-mock attribute).
 */
export function extractMarkup(src, { astro = false, markdown = false, mdx = false } = {}) {
  const out = src.split(''); // UTF-16 code units, so indices match the source
  const n = src.length;
  const segments = [];
  const mocks = [];
  const stack = [];
  let i = 0;
  let segStart = 0;
  const closeSeg = (end) => {
    if (end > segStart) segments.push([segStart, end]);
  };

  if (astro) {
    // Astro frontmatter is code. (Markdown frontmatter stays: titles/descriptions are copy.)
    const fm = /^﻿?---\r?\n[\s\S]*?\r?\n---[^\n]*/.exec(src);
    if (fm) {
      blankRange(out, 0, fm[0].length);
      i = fm[0].length;
      segStart = i;
    }
  }
  const exprs = astro || mdx;

  while (i < n) {
    const c = src[i];
    if (src.startsWith('<!--', i)) {
      const e = src.indexOf('-->', i + 4);
      const end = e < 0 ? n : e + 3;
      closeSeg(i);
      blankRange(out, i, end);
      i = end;
      segStart = i;
      continue;
    }
    if (c === '<' && /[A-Za-z/!?]/.test(src[i + 1] || '')) {
      const start = i;
      let j = i + 1,
        q = null,
        depth = 0;
      while (j < n) {
        const d = src[j];
        if (q) {
          if (d === q) q = null;
        } else if (d === '"' || d === "'" || (depth > 0 && d === '`')) q = d;
        else if (d === '{') depth++;
        else if (d === '}') depth = Math.max(0, depth - 1);
        else if (d === '>' && depth === 0) break;
        j++;
      }
      const end = Math.min(n, j + 1);
      const tag = src.slice(start, end);
      closeSeg(start);
      blankRange(out, start, end);
      // Visible attributes are copy too: alt, title, aria-label, placeholder, meta content.
      for (const m of tag.matchAll(
        /\s(alt|title|aria-label|placeholder|content)\s*=\s*("([^"]*)"|'([^']*)')/gi,
      )) {
        if (m[1].toLowerCase() === 'content' && !/^<meta\b/i.test(tag)) continue;
        const val = m[3] ?? m[4];
        const vs = start + m.index + m[0].length - val.length - 1;
        for (let k = 0; k < val.length; k++) out[vs + k] = src[vs + k];
        segments.push([vs, vs + val.length]);
      }
      const tm = /^<(\/?)\s*([A-Za-z][\w:.-]*)/.exec(tag);
      if (tm) {
        const closing = tm[1] === '/';
        const name = tm[2].toLowerCase();
        const isMock = /\sdata-mock(?=[\s=/>])/i.test(tag);
        const selfClosing = /\/\s*>$/.test(tag) || VOID.has(name);
        if (!closing && (name === 'script' || name === 'style')) {
          const re = new RegExp(`</${name}\\s*>`, 'ig');
          re.lastIndex = end;
          const mm = re.exec(src);
          const e2 = mm ? mm.index + mm[0].length : n;
          blankRange(out, end, e2);
          i = e2;
          segStart = i;
          continue;
        }
        if (closing) {
          for (let s = stack.length - 1; s >= 0; s--) {
            if (stack[s].name === name) {
              for (const p of stack.splice(s))
                if (p.mock)
                  mocks.push({ tagStart: p.tagStart, start: p.start, end: start, tag: p.tag });
              break;
            }
          }
        } else if (selfClosing) {
          if (isMock) mocks.push({ tagStart: start, start: end, end, tag });
        } else {
          stack.push({ name, tagStart: start, start: end, mock: isMock, tag });
        }
      }
      i = end;
      segStart = i;
      continue;
    }
    if (exprs && c === '{') {
      // Astro/MDX expression: code, not copy. Keep only string literals inside it.
      closeSeg(i);
      let j = i + 1,
        depth = 1;
      out[i] = ' ';
      while (j < n && depth > 0) {
        const d = src[j];
        if (d === '"' || d === "'" || d === '`') {
          const q = d;
          out[j] = ' ';
          j++;
          const ls = j;
          while (j < n && src[j] !== q) {
            if (src[j] === '\\') j++;
            j++;
          }
          segments.push([ls, Math.min(j, n)]);
          if (j < n) out[j] = ' ';
          j++;
          continue;
        }
        if (d === '{') depth++;
        else if (d === '}') depth--;
        if (out[j] !== '\n' && out[j] !== '\r') out[j] = ' ';
        j++;
      }
      i = j;
      segStart = i;
      continue;
    }
    i++;
  }
  closeSeg(n);
  for (const p of stack)
    if (p.mock) mocks.push({ tagStart: p.tagStart, start: p.start, end: n, tag: p.tag });

  if (markdown) {
    const s = out.join('');
    // Link targets and reference definitions are URLs/paths, not copy.
    for (const m of s.matchAll(/\]\([^)\n]*\)/g))
      blankRange(out, m.index + 1, m.index + m[0].length);
    for (const m of s.matchAll(/^[ \t]*\[[^\]\n]+\]:[^\n]*/gm))
      blankRange(out, m.index, m.index + m[0].length);
  }
  decodeEntities(out);
  blankUrls(out);
  return { text: out.join(''), segments, mocks };
}

// ---------- JSON with positions ----------
function parseJsonPos(src) {
  let i = 0;
  const err = (msg) => {
    throw new Error(`${msg} at offset ${i}`);
  };
  const ws = () => {
    while (i < src.length && /[\s﻿]/.test(src[i])) i++;
  };
  function value(key) {
    ws();
    const c = src[i];
    const start = i;
    if (c === '{') {
      i++;
      const node = { kind: 'object', start, key, entries: [] };
      ws();
      if (src[i] === '}') {
        i++;
        return node;
      }
      for (;;) {
        ws();
        if (src[i] !== '"') err('expected key');
        const kStart = i;
        const k = str();
        ws();
        if (src[i] !== ':') err('expected :');
        i++;
        const v = value(k);
        node.entries.push({ key: k, keyStart: kStart, value: v });
        ws();
        if (src[i] === ',') {
          i++;
          continue;
        }
        if (src[i] === '}') {
          i++;
          return node;
        }
        err('expected , or }');
      }
    }
    if (c === '[') {
      i++;
      const node = { kind: 'array', start, key, items: [] };
      ws();
      if (src[i] === ']') {
        i++;
        return node;
      }
      for (;;) {
        node.items.push(value(key));
        ws();
        if (src[i] === ',') {
          i++;
          continue;
        }
        if (src[i] === ']') {
          i++;
          return node;
        }
        err('expected , or ]');
      }
    }
    if (c === '"') return { kind: 'string', start, key, value: str() };
    const m = /^(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null)/.exec(src.slice(i, i + 64));
    if (!m) err('unexpected token');
    i += m[0].length;
    const lit = m[0];
    return {
      kind: lit === 'true' || lit === 'false' ? 'bool' : lit === 'null' ? 'null' : 'number',
      start,
      key,
      value: JSON.parse(lit),
    };
  }
  function str() {
    const s = i;
    i++;
    while (i < src.length && src[i] !== '"') {
      if (src[i] === '\\') i++;
      i++;
    }
    i++;
    return JSON.parse(src.slice(s, i));
  }
  const root = value(undefined);
  ws();
  if (i < src.length) err('trailing data');
  return root;
}

function* walkJson(node) {
  yield node;
  if (node.kind === 'object') for (const e of node.entries) yield* walkJson(e.value);
  if (node.kind === 'array') for (const it of node.items) yield* walkJson(it);
}

// ---------- matching ----------
function negated(text, off) {
  let before = text.slice(Math.max(0, off - 160), off);
  const cut = Math.max(before.search(/[.;:!?](?=[^.;:!?]*$)/), before.lastIndexOf('\n\n'));
  if (cut >= 0) before = before.slice(cut + 1);
  const words = before.toLowerCase().match(/[\p{L}’']+/gu) || [];
  return words.slice(-NEG_WINDOW).some((w) => NEGATIONS.has(w));
}

// ---------- reviewed exact-phrase allowlist (allow.json) ----------
// Each entry {term, phrase, reason}: a hit for `term` is ignored only when the matched words lie inside an
// occurrence of exactly that phrase (case-insensitive, any whitespace run between words). Every entry needs a
// written reason and is reviewed like code. The banned-term list itself is unchanged. An optional `paths`
// array scopes an entry: it applies only to files whose forward-slash path contains one of the strings.
const phraseRx = (phrase) =>
  new RegExp(
    phrase
      .trim()
      .split(/\s+/)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('[\\s\\u00a0]+'),
    'giu',
  );

/** Validate and compile allowlist entries. Throws on an invalid entry. */
export function compileAllow(entries) {
  const terms = new Set(RULES.map((r) => r.term));
  return entries.map((e, i) => {
    if (!e || !terms.has(e.term)) throw new Error(`allow[${i}]: unknown term ${e && e.term}`);
    if (!e.phrase || !e.reason || String(e.reason).trim().length < 20)
      throw new Error(`allow[${i}]: needs a phrase and a written reason`);
    const rule = RULES.find((r) => r.term === e.term);
    rule.rx.lastIndex = 0;
    if (!new RegExp(rule.re, 'iu').test(e.phrase))
      throw new Error(`allow[${i}]: phrase does not contain the term "${e.term}"`);
    if (
      e.paths !== undefined &&
      !(
        Array.isArray(e.paths) &&
        e.paths.length &&
        e.paths.every((p) => typeof p === 'string' && p)
      )
    )
      throw new Error(`allow[${i}]: paths must be a non-empty array of strings`);
    return { term: e.term, phrase: e.phrase, rx: phraseRx(e.phrase), paths: e.paths };
  });
}

const ALLOW_FILE = join(dirname(fileURLToPath(import.meta.url)), 'allow.json');
export const ALLOW = compileAllow(JSON.parse(readFileSync(ALLOW_FILE, 'utf8')));

function allowed(text, term, start, end, allow) {
  for (const a of allow) {
    if (a.term !== term) continue;
    a.rx.lastIndex = 0;
    for (const m of text.matchAll(a.rx))
      if (m.index <= start && end <= m.index + m[0].length) return true;
  }
  return false;
}

/** Find banned-term hits in `text`. Returns [{offset, term, match}]. */
export function findTerms(text, allow = ALLOW) {
  const hits = [];
  for (const r of RULES) {
    r.rx.lastIndex = 0;
    for (const m of text.matchAll(r.rx)) {
      if (negated(text, m.index)) continue;
      if (allowed(text, r.term, m.index, m.index + m[0].length, allow)) continue;
      hits.push({ offset: m.index, term: r.term, match: m[0].replace(/\s+/g, ' ') });
    }
  }
  return hits;
}

/** A segment (text node, JSON value, table cell, list item) that is only the word "live" is a status label. */
function standaloneLive(text, [a, b]) {
  const seg = text.slice(a, b);
  const bare = seg.replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  if (bare.toLowerCase() === 'live') return a + seg.toLowerCase().indexOf('live');
  return -1;
}

/** Allowlist entries that apply to `name` (entries without `paths` apply everywhere). */
export function allowFor(name, allow = ALLOW) {
  const file = String(name).replace(/\\/g, '/');
  return allow.filter((a) => !a.paths || a.paths.some((p) => file.includes(p)));
}

function lintMarkupFile(src, kind, allow) {
  const { text, segments, mocks } = extractMarkup(src, {
    astro: kind === 'astro',
    markdown: kind === 'md' || kind === 'mdx',
    mdx: kind === 'mdx',
  });
  const hits = findTerms(text, allow);
  let segs = segments;
  if (kind === 'md' || kind === 'mdx') {
    segs = [];
    for (const [a, b] of segments) {
      // split markdown segments into lines and table cells
      let s = a;
      for (let k = a; k <= b; k++) {
        if (k === b || text[k] === '\n' || text[k] === '|') {
          segs.push([s, k]);
          s = k + 1;
        }
      }
    }
  }
  for (const seg of segs) {
    const off = standaloneLive(text, seg);
    if (off >= 0 && !hits.some((h) => h.term === 'live' && h.offset === off))
      hits.push({ offset: off, term: 'live', match: 'live (status label)' });
  }
  for (const mk of mocks) {
    const inner = text.slice(mk.start, mk.end) + ' ' + mk.tag.replace(/data-mock/gi, '');
    if (/\d/.test(inner) && !MOCK_LABEL.test(inner))
      hits.push({
        offset: mk.tagStart,
        term: 'mock-number-unlabelled',
        match: 'data-mock element has a number but no "demo data"/"target"/"ESTIMATE" label',
      });
  }
  return hits;
}

function lintJsonFile(src, allow) {
  const root = parseJsonPos(src);
  const hits = [];
  for (const node of walkJson(root)) {
    if (
      node.kind === 'string' &&
      !(node.key && JSON_SKIP_KEYS.has(String(node.key).toLowerCase()))
    ) {
      // lint the decoded value, report at the string's position
      const arr = node.value.split('');
      blankUrls(arr);
      const text = arr.join('');
      for (const h of findTerms(text, allow))
        hits.push({ offset: node.start, term: h.term, match: h.match });
      if (standaloneLive(text, [0, text.length]) >= 0)
        hits.push({ offset: node.start, term: 'live', match: 'live (status label)' });
    }
    if (node.kind === 'object') {
      const mockEntry = node.entries.find(
        (e) => e.key === 'mock' && e.value.kind === 'bool' && e.value.value === true,
      );
      if (mockEntry) {
        let hasNum = false,
          hasLabel = false;
        for (const d of walkJson(node)) {
          if (d.kind === 'number') hasNum = true;
          if (d.kind === 'string') {
            if (/\d/.test(d.value)) hasNum = true;
            if (MOCK_LABEL.test(d.value)) hasLabel = true;
          }
        }
        if (hasNum && !hasLabel)
          hits.push({
            offset: mockEntry.keyStart,
            term: 'mock-number-unlabelled',
            match: '"mock": true object has a number but no "demo data"/"target"/"ESTIMATE" label',
          });
      }
    }
  }
  return hits;
}

/** Lint one file's source. `name` decides the parser by extension. */
export function lintSource(src, name) {
  const ext = extname(name).toLowerCase();
  const allow = allowFor(name);
  let hits;
  if (ext === '.json') hits = lintJsonFile(src, allow);
  else if (ext === '.md') hits = lintMarkupFile(src, 'md', allow);
  else if (ext === '.mdx') hits = lintMarkupFile(src, 'mdx', allow);
  else if (ext === '.astro') hits = lintMarkupFile(src, 'astro', allow);
  else hits = lintMarkupFile(src, 'html', allow);
  const starts = lineStarts(src);
  const seen = new Set();
  return hits
    .map((h) => ({ line: lineOf(starts, h.offset), term: h.term, match: h.match }))
    .filter((h) => {
      const k = `${h.line}|${h.term}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    })
    .sort((a, b) => a.line - b.line || a.term.localeCompare(b.term));
}

/** Expand CLI paths into files. Explicitly passed paths are always scanned; skip-dirs apply only when recursing. */
export function collectFiles(paths) {
  const files = [];
  const walk = (p, explicit) => {
    let st;
    try {
      st = statSync(p);
    } catch {
      throw new Error(`no such file or directory: ${p}`);
    }
    if (st.isDirectory()) {
      if (!explicit && SKIP_DIRS.has(basename(p))) return;
      for (const e of readdirSync(p).sort()) walk(join(p, e), false);
    } else if (EXTENSIONS.has(extname(p).toLowerCase()) || explicit) {
      if (EXTENSIONS.has(extname(p).toLowerCase())) files.push(p);
      else process.stderr.write(`copy-lint: skipping unsupported file type: ${p}\n`);
    }
  };
  for (const p of paths) walk(p, true);
  return files;
}

export function lintFiles(paths) {
  const results = [];
  const errors = [];
  for (const f of collectFiles(paths)) {
    try {
      const src = readFileSync(f, 'utf8');
      for (const h of lintSource(src, f)) results.push({ file: f.replace(/\\/g, '/'), ...h });
    } catch (e) {
      errors.push({ file: f.replace(/\\/g, '/'), error: e.message });
    }
  }
  return { results, errors };
}
