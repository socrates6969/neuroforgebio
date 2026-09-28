// Docs (BUILD-GUIDE 4.5): the pages show exactly the code tools/doc-snippets/run.py executes or
// verbatim excerpts of repository files, the API reference matches the committed OpenAPI document,
// unbuilt features carry a status label.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';
import { REPO, brand, files, read, requireDist } from './_dist.mjs';

const THEMES = ['clinical', 'cosmos'];
const DOCS = join(REPO, 'apps/web/src/docs');
const pkg = brand.codeIdentifiers.pythonImport;
const esc = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const unesc = (s) =>
  s
    .replace(/&quot;/g, '"')
    .replace(/&#34;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
const quickstarts = readdirSync(join(DOCS, 'quickstarts'))
  .filter((f) => f.endsWith('.json'))
  .map((f) => ({ slug: f.slice(0, -5), doc: JSON.parse(read(join(DOCS, 'quickstarts', f))) }));

const guides = readdirSync(join(DOCS, 'guides'))
  .filter((f) => f.endsWith('.json'))
  .map((f) => ({ slug: f.slice(0, -5), doc: JSON.parse(read(join(DOCS, 'guides', f))) }));
const blockText = (lines) => lines.join('\n').replaceAll('{pkg}', pkg);
const preBlocks = (html) =>
  [...html.matchAll(/<pre\b[^>]*>\s*<code[^>]*>([\s\S]*?)<\/code>\s*<\/pre>/g)].map((m) =>
    unesc(m[1]),
  );

/** Text of every code block a docs page may show, with where it is checked. */
function allowedBlocks() {
  const allowed = new Map();
  const qs = new Map(quickstarts.map((q) => [q.slug, q.doc]));
  for (const { slug, doc } of quickstarts)
    for (const s of doc.sections.filter((x) => x.code))
      allowed.set(blockText(s.code.lines), `doctest ${slug}#${s.id}`);
  const guideBlocks = new Map();
  for (const { slug, doc } of guides) {
    const shown = [];
    for (const s of doc.sections.filter((x) => x.code)) {
      const c = s.code;
      assert.ok(
        !c.source !== !c.doctest,
        `${slug}#${s.id}: a code block names exactly one of source, doctest`,
      );
      if (c.doctest) {
        const [q, id] = c.doctest.split('#');
        const hit = qs.get(q)?.sections.find((x) => x.id === id && x.code);
        assert.ok(hit, `${slug}#${s.id}: unknown doctest block ${c.doctest}`);
        assert.deepEqual(
          c.lines,
          [],
          `${slug}#${s.id}: a doctest block takes its lines from the quickstart`,
        );
        shown.push(blockText(hit.code.lines));
      } else {
        const text = blockText(c.lines);
        const src = read(join(REPO, c.source)).replace(/\r\n/g, '\n');
        assert.ok(
          text.trim() && src.includes(text),
          `${slug}#${s.id}: not a verbatim excerpt of ${c.source}`,
        );
        allowed.set(text, `source ${c.source}`);
        shown.push(text);
      }
    }
    guideBlocks.set(slug, shown);
  }
  return { allowed, guideBlocks };
}

test('four quickstarts: file ingest, pipeline run, streaming, lineage export', () => {
  assert.deepEqual(quickstarts.map((q) => q.slug).sort(), [
    'file-ingest',
    'lineage-export',
    'pipeline-run',
    'streaming',
  ]);
});

test('every quickstart code block is rendered verbatim (the runner executes the same text)', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    for (const { slug, doc } of quickstarts) {
      const html = read(join(dist, 'docs/quickstart', slug, 'index.html'));
      const blocks = [
        ...html.matchAll(/<pre class="code"[^>]*>\s*<code[^>]*>([\s\S]*?)<\/code>\s*<\/pre>/g),
      ].map((m) => unesc(m[1]));
      const want = doc.sections
        .filter((s) => s.code)
        .map((s) => s.code.lines.join('\n').replaceAll('{pkg}', pkg));
      assert.deepEqual(blocks, want, `${t} ${slug}`);
      for (const s of doc.sections.filter((x) => x.code)) assert.equal(s.code.language, 'python');
    }
  }
});

test('API reference is generated from the committed openapi/v1.yaml', () => {
  const spec = read(join(REPO, 'openapi/v1.yaml')).replace(/\r\n/g, '\n');
  const ref = JSON.parse(read(join(DOCS, 'api-reference.json')));
  const sha = createHash('sha256').update(spec, 'utf8').digest('hex');
  assert.equal(
    ref.sha256,
    sha,
    'openapi/v1.yaml changed: run tools/doc-snippets/gen_api_reference.py',
  );
  const html = read(join(requireDist('clinical'), 'docs/api/index.html'));
  const ops = ref.groups.flatMap((g) => g.operations);
  assert.ok(ops.length > 0);
  for (const o of ops) assert.ok(html.includes(esc(o.path)), o.path);
});

test('docs overview labels unbuilt features with a status', () => {
  const idx = JSON.parse(read(join(DOCS, 'index.json')));
  const items = idx.sections.flatMap((s) => s.items ?? []);
  assert.ok(items.length >= 3 && items.every((i) => i.status), 'every overview item has a status');
  assert.ok(
    items.some((i) => i.status === 'designed') && items.some((i) => i.status === 'planned'),
  );
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'docs/index.html'));
    assert.match(html, /Designed/);
    assert.match(html, /Planned/);
  }
});

test('SDK guides: Python SDK and C ABI; C ABI and engine SDKs read "in development, not released"', () => {
  assert.deepEqual(guides.map((g) => g.slug).sort(), ['c-abi', 'python-sdk']);
  for (const { slug, doc } of guides)
    assert.ok(doc.status && doc.source, `${slug}: status and source`);
  const cabi = guides.find((g) => g.slug === 'c-abi').doc;
  for (const text of [cabi.heading, cabi.lede, cabi.meta.description])
    assert.match(text, /in development, not released/i);
  // Pinned sources: feature/c-abi 9b69b20 (ABI 1.2.0) and feature/engine-sdks 5db14b2 (lead
  // review 2026-09-27). Update these pins when the page is re-sourced to newer heads.
  assert.match(cabi.source, /feature\/c-abi \(commit 9b69b20, ABI 1\.2\.0/);
  assert.match(cabi.source, /feature\/engine-sdks \(commit 5db14b2\)/);
  assert.doesNotMatch(JSON.stringify(cabi), /48336f5|db5cf16|ABI 1\.[01]\b/, 'stale source');
  // every section cites the branch file it summarises
  for (const s of cabi.sections)
    assert.match(s.body.at(-1), /^Source: bindings\/.+\(feature\/[a-z-]+, [0-9a-f]{7}\)/, s.id);
  // bindings/c is not on main yet, so no code block can be checked against it: none is shown.
  assert.ok(
    cabi.sections.every((s) => !s.code),
    'C ABI page shows no code until bindings/c is merged',
  );
  const engines = cabi.sections.find((s) => s.id === 'engines');
  assert.ok(
    engines.items.length === 2 &&
      engines.items.every(
        (i) => i.status === 'in-preparation' && /^In development, not released./.test(i.body),
      ),
  );
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'docs/c-abi/index.html'));
    assert.match(html, /In preparation/);
  }
});

test('every code block on every docs page is a doctest or a verbatim excerpt of a repository file', () => {
  const { allowed, guideBlocks } = allowedBlocks();
  for (const t of THEMES) {
    const dist = requireDist(t);
    let n = 0;
    for (const f of files(join(dist, 'docs'), '.html')) {
      for (const b of preBlocks(read(f))) {
        assert.ok(
          allowed.has(b),
          `${t} ${f}: code block is neither a doctest nor a source excerpt:\n${b}`,
        );
        n++;
      }
    }
    assert.ok(n > 0, `${t}: no code blocks found`);
    for (const [slug, want] of guideBlocks) {
      const html = read(join(dist, 'docs', slug, 'index.html'));
      assert.deepEqual(preBlocks(html), want, `${t} ${slug}`);
    }
  }
});

test('Python SDK guide: one call per v1 operation, each wrapper checked against the SDK source', () => {
  const g = guides.find((x) => x.slug === 'python-sdk').doc;
  const E = g.endpoints;
  const ref = JSON.parse(read(join(DOCS, 'api-reference.json')));
  const ops = ref.groups.flatMap((x) => x.operations);
  const ids = new Set(ops.map((o) => o.operationId));
  const named = [...E.wrapped, ...E.unsupported].map((x) => x.operationId);
  assert.equal(new Set(named).size, named.length, 'an operation is listed twice');
  for (const id of named) assert.ok(ids.has(id), `${id} is not in openapi/v1.yaml`);
  for (const w of E.wrapped) {
    const src = read(join(REPO, w.file.replaceAll('{pkg}', pkg))).replace(/\r\n/g, '\n');
    const op = ops.find((o) => o.operationId === w.operationId);
    assert.ok(src.includes(w.needle), `${w.operationId}: ${w.file} does not contain ${w.needle}`);
    // The call of the path in the needle matches the operation's path (IDs are f-string fields).
    const re = new RegExp('^' + op.path.replace(/\{[^}]+\}/g, String.raw`\{[^}]+\}`) + '$');
    const m = w.needle.match(/"(\/v1\/[^"]*)"/);
    if (m) assert.match(m[1], re, `${w.operationId}: ${m[1]} is not ${op.path}`);
    for (const part of w.call.split(/(?<=\)), /)) {
      const fn = part.replace(/\(.*$/, '').split('.').pop();
      assert.match(
        src,
        new RegExp(String.raw`\bdef ${fn}\(`),
        `${w.operationId}: ${fn} is not defined in ${w.file}`,
      );
    }
  }
  const client = read(join(REPO, 'bindings/python/python', pkg, 'client.py'));
  for (const fn of ['get', 'post', 'request'])
    assert.match(client, new RegExp(String.raw`\n    def ${fn}\(`));
  assert.match(read(join(REPO, 'bindings/python/python', pkg, '__init__.py')), /"get_client"/);
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'docs/python-sdk/index.html'));
    const rows = [...html.matchAll(/<tr[^>]*\bid="ep-([A-Za-z0-9_]+)"/g)].map((m) => m[1]);
    assert.deepEqual(
      rows,
      ops.map((o) => o.operationId),
      `${t}: one row per operation, in reference order`,
    );
    const side = html.match(/<nav class="side"[\s\S]*?<\/nav>/)[0];
    assert.doesNotMatch(side, /\/docs\/python-sdk\//, `${t}: linked from /docs, not the side nav`);
    assert.match(read(join(requireDist(t), 'docs/index.html')), /href="\/docs\/python-sdk\/"/);
  }
});

test('every docs page carries Organization + TechArticle JSON-LD for its own canonical URL', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const pages = files(join(dist, 'docs'), '.html');
    assert.ok(pages.length >= 8, `${t}: docs pages`);
    for (const f of pages) {
      const html = read(f);
      const nodes = [
        ...html.matchAll(
          /<script[^>]*\stype=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script\s*>/gi,
        ),
      ]
        .map((m) => JSON.parse(m[1]))
        // one script per node, or one script with an @graph of nodes (web-seo's lean form)
        .flatMap((n) => n['@graph'] ?? [n]);
      assert.ok(
        nodes.some((n) => n['@type'] === 'Organization' && n.name && n.url),
        f,
      );
      const art = nodes.find((n) => n['@type'] === 'TechArticle');
      const canon = html.match(/<link[^>]*rel="canonical"[^>]*href="([^"]+)"/)?.[1];
      assert.ok(art && canon && art.url === canon, `${f}: TechArticle url ${art?.url} != ${canon}`);
    }
  }
});

// JSON.parse keeps the last of two equal keys silently: a duplicate "description" in apiPage once
// replaced the /docs/api meta description with the column label "Description".
test('docs JSON has no duplicate keys in any object', () => {
  const docs = [
    join(DOCS, 'index.json'),
    join(DOCS, 'changelog.json'),
    ...['quickstarts', 'guides'].flatMap((d) =>
      readdirSync(join(DOCS, d)).map((f) => join(DOCS, d, f)),
    ),
  ];
  for (const f of docs) {
    const stack = [];
    const dups = [];
    const src = read(f);
    // Tokenise strings and structural characters; a string followed by ':' is a key.
    for (const m of src.matchAll(/"(?:[^"\\]|\\.)*"\s*:|[{}[\]]/g)) {
      const t = m[0];
      if (t === '{') stack.push(new Set());
      else if (t === '[') stack.push(null);
      else if (t === '}' || t === ']') stack.pop();
      else if (stack.at(-1)) {
        const k = t.replace(/\s*:$/, '');
        if (stack.at(-1).has(k)) dups.push(k);
        stack.at(-1).add(k);
      }
    }
    assert.deepEqual(dups, [], f);
  }
  const idx = JSON.parse(read(join(DOCS, 'index.json')));
  assert.notEqual(idx.apiPage.description, idx.apiPage.colDescription);
});
