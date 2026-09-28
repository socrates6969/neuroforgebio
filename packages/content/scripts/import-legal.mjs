#!/usr/bin/env node
// Converts the nfb-legal drafts (docs/inputs/legal-website/<name>.<en|no>.md) into
// packages/content/content/legal/<page>.<locale>.json. The drafts are rendered verbatim, except:
//   - the company name becomes {brand}, and the drafts' placeholder domain (the name, lowercased, with
//     a dot for the space) becomes {domain} (brand-token rule: the literal name lives only in brand.json);
//   - the first blockquote line (the DRAFT notice) is lifted into `draftNotice` for the banner. This is
//     pinned verbatim by packages/content/test/content.test.mjs ("legal pages are marked DRAFT") and
//     must not be repurposed as the SEO description (four identical banners means four identical
//     meta.description values, a real duplicate-content defect).
//   - an optional `<!-- meta-description: ... -->` directive, right after the draft-notice blockquote
//     and before the title, gives the page its own meta.description independent of draftNotice. It is
//     consumed here (tokenized, like the rest), never added to `blocks`, so it never renders on the
//     page. Falls back to draftNotice when a draft doesn't have one.
// Usage: node packages/content/scripts/import-legal.mjs          (writes the JSON files)
//        node packages/content/scripts/import-legal.mjs --check  (exit 1 if a file is stale)
// After writing, run Prettier on content/legal (the lint checks formatting; --check compares parsed JSON).
// Inline markup (**bold**, *em*, `code`, [text](href)) stays as text; apps/web renders it safely.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const PKG = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = join(PKG, '..', '..');
export const SOURCE_DIR = join(ROOT, 'docs/inputs/legal-website');
export const OUT_DIR = join(PKG, 'content/legal');
export const LEGAL_PAGES = {
  privacy: 'privacy-policy',
  terms: 'terms-of-use',
  cookies: 'cookie-statement',
  company: 'company-information',
};
export const LOCALES = ['en', 'no'];

const brandJson = JSON.parse(readFileSync(join(PKG, 'brand.json'), 'utf8'));
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Replace the company name and the drafts' placeholder domain with content tokens. */
export function tokenize(s) {
  const out = s
    .replace(new RegExp(esc(brandJson.name), 'g'), '{brand}')
    .replace(new RegExp(esc(brandJson.name.toLowerCase().replace(/ /g, '.')), 'gi'), '{domain}');
  const short = brandJson.name.split(' ')[0];
  if (new RegExp(esc(short), 'i').test(out))
    throw new Error(`import-legal: company name left after tokenizing: ${out.slice(0, 120)}`);
  return out;
}

const slug = (s) =>
  's-' +
  s
    .toLowerCase()
    .replace(/æ/g, 'ae')
    .replace(/ø/g, 'o')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 60);

const cells = (line) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((c) => c.trim());

/** Markdown (the subset the drafts use) -> { title, shortTitle, draftNotice, meta, blocks }. */
export function convert(md) {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  let title = null;
  let draftNotice = null;
  let metaDescription = null;
  const blocks = [];
  let para = null;
  let list = null;
  let quote = null;
  let table = null;
  const flush = () => {
    if (para) blocks.push({ type: 'p', text: para.join('\n') });
    if (list) blocks.push({ type: 'ul', items: list });
    if (quote) blocks.push({ type: 'quote', text: quote.join('\n') });
    // A key/value table has an empty header row (| | |): omit it, so no empty <th> is rendered.
    if (table)
      blocks.push(
        table.head.some((h) => h.trim())
          ? { type: 'table', head: table.head, rows: table.rows }
          : { type: 'table', rows: table.rows },
      );
    para = list = quote = table = null;
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      flush();
      continue;
    }
    let m;
    if ((m = /^>\s?(.*)$/.exec(line))) {
      if (draftNotice === null && blocks.length === 0 && title === null && !quote) {
        draftNotice = tokenize(m[1].trim());
        continue;
      }
      if (!quote) flush();
      quote = quote ?? [];
      quote.push(tokenize(m[1]));
      continue;
    }
    if ((m = /^<!--\s*meta-description:\s*(.*)-->\s*$/.exec(line))) {
      if (metaDescription !== null)
        throw new Error('import-legal: more than one meta-description directive');
      if (draftNotice === null)
        throw new Error(
          'import-legal: meta-description directive must come after the draft notice',
        );
      if (blocks.length > 0 || title !== null || quote)
        throw new Error('import-legal: meta-description directive must come before the title');
      metaDescription = tokenize(m[1].trim());
      continue;
    }
    if ((m = /^(#{1,3})\s+(.*)$/.exec(line))) {
      flush();
      const text = tokenize(m[2].trim());
      if (m[1] === '#') {
        if (title !== null) throw new Error('import-legal: more than one # heading');
        title = text;
      } else blocks.push({ type: m[1] === '##' ? 'h2' : 'h3', id: slug(text), text });
      continue;
    }
    if (/^\s*\|/.test(line)) {
      if (!table) {
        flush();
        table = { head: cells(tokenize(line)), rows: [] };
      } else if (/^\s*\|[\s:|-]+\|?\s*$/.test(line)) continue;
      else table.rows.push(cells(tokenize(line)));
      continue;
    }
    if ((m = /^\s*[-*]\s+(.*)$/.exec(line))) {
      if (!list) flush();
      list = list ?? [];
      list.push(tokenize(m[1]));
      continue;
    }
    if (list || table || quote) flush();
    para = para ?? [];
    para.push(tokenize(line.trim()));
  }
  flush();
  if (!title) throw new Error('import-legal: missing # title');
  if (!draftNotice) throw new Error('import-legal: missing DRAFT notice blockquote');
  // "Privacy policy – [{domain}] website" -> "Privacy policy"; "Erklæring … (cookies) – [{domain}]" -> "Erklæring … (cookies)"
  const shortTitle = title.split(/\s+[–-]\s+/)[0].trim();
  return {
    meta: { title: `${shortTitle} · {brand}`, description: metaDescription ?? draftNotice },
    draft: true,
    draftNotice,
    title,
    shortTitle,
    blocks,
  };
}

export function outputs() {
  const out = [];
  for (const [page, file] of Object.entries(LEGAL_PAGES))
    for (const locale of LOCALES) {
      const md = readFileSync(join(SOURCE_DIR, `${file}.${locale}.md`), 'utf8');
      out.push({
        path: join(OUT_DIR, `${page}.${locale}.json`),
        json: JSON.stringify(convert(md), null, 2) + '\n',
      });
    }
  return out;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  const check = process.argv.includes('--check');
  let stale = 0;
  mkdirSync(OUT_DIR, { recursive: true });
  for (const { path, json } of outputs()) {
    let cur = null;
    try {
      cur = readFileSync(path, 'utf8');
    } catch {
      /* missing */
    }
    // compare parsed JSON: the committed files are Prettier-formatted
    if (cur !== null && JSON.stringify(JSON.parse(cur)) === JSON.stringify(JSON.parse(json)))
      continue;
    if (check) {
      console.error(`stale: ${path}`);
      stale++;
    } else writeFileSync(path, json);
  }
  if (stale) process.exit(1);
  console.error(check ? 'import-legal: up to date' : 'import-legal: written');
}
