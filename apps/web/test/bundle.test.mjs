// Bundle test (BUILD-GUIDE 1.6): clinical ships no three.js; cosmos loads three lazily only.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { THEMES_DIR, attrs, files, read, requireDist } from './_dist.mjs';

const THREE_SIGNATURES = [
  'WebGLRenderer',
  'BufferGeometry',
  'three.module',
  'WebGLRenderTarget',
  'three/build/three',
];

// The one exception (owner request 2026-09-27): /interface/ is a 3D scene in both themes. Its three.js
// chunk may exist in clinical only as a dynamic import() of that page's own script; every other page,
// the home page included, stays three-free (checked by page closure below).
const THREE_ROUTE = 'interface/index.html';

test('clinical dist contains no three.js code outside the lazy /interface/ scene', () => {
  const dist = requireDist('clinical');
  const hits = new Set();
  for (const f of files(dist, '.js').concat(files(dist, '.mjs'))) {
    const s = read(f);
    if (THREE_SIGNATURES.some((sig) => s.includes(sig))) hits.add(f);
  }
  const page = read(join(dist, THREE_ROUTE));
  const initial = initialClosure(dist, page);
  // chunks reachable from the /interface/ entry only through import(), plus their static imports
  const lazy = new Set();
  const stack = [];
  for (const f of initial)
    for (const m of read(f).matchAll(/import\(\s*["']([^"']+\.js)["']\s*\)/g))
      stack.push(m[1].startsWith('/') ? join(dist, m[1]) : resolve(dirname(f), m[1]));
  while (stack.length) {
    const f = stack.pop();
    if (lazy.has(f) || !existsSync(f)) continue;
    lazy.add(f);
    for (const m of read(f).matchAll(
      /(?:^|[;\s}])(?:import|export)\s*(?:[\w$*{},\s]+from\s*)?["']([^"']+\.js)["']/g,
    ))
      stack.push(m[1].startsWith('/') ? join(dist, m[1]) : resolve(dirname(f), m[1]));
  }
  const outside = [...hits].filter((f) => !lazy.has(f) || initial.has(f));
  assert.deepEqual(
    outside.map((f) => relative(dist, f)),
    [],
    'three.js only as a lazy chunk of /interface/',
  );
  assert.ok(hits.size > 0, 'expected the /interface/ scene chunk');
  for (const p of files(dist, '.html')) {
    const closure = initialClosure(dist, read(p));
    for (const h of hits)
      assert.ok(
        !closure.has(h),
        `${relative(dist, p)} loads three.js up front (${relative(dist, h)})`,
      );
  }
});

/** Static-import closure of the scripts an HTML page loads up front. */
function initialClosure(dist, html) {
  const entries = [
    ...attrs(html, 'script', 'src').map((a) => a.value),
    ...attrs(html, 'link', 'href')
      .filter((a) => /rel=["']?modulepreload/i.test(a.tag))
      .map((a) => a.value),
  ].filter((u) => u.startsWith('/'));
  const seen = new Set();
  const stack = entries.map((u) => join(dist, u));
  while (stack.length) {
    const f = stack.pop();
    if (seen.has(f) || !existsSync(f)) continue;
    seen.add(f);
    const src = readFileSync(f, 'utf8');
    // static imports only: `import{a}from"./x.js"`, `import"./x.js"`, `export*from"./x.js"`
    for (const m of src.matchAll(
      /(?:^|[;\s}])(?:import|export)\s*(?:[\w$*{},\s]+from\s*)?["']([^"']+\.js)["']/g,
    )) {
      stack.push(m[1].startsWith('/') ? join(dist, m[1]) : resolve(dirname(f), m[1]));
    }
  }
  return seen;
}

const themesPkg = JSON.parse(readFileSync(join(THEMES_DIR, 'package.json'), 'utf8'));
const cosmosUsesThree = Boolean({ ...themesPkg.dependencies, ...themesPkg.devDependencies }.three);

test(
  'cosmos: three.js is a lazy chunk, not loaded by the initial HTML',
  {
    skip:
      !cosmosUsesThree && 'three is not yet a dependency of packages/themes (designer step 1.5)',
  },
  () => {
    const dist = requireDist('cosmos');
    // The chunk that CONTAINS three.js, identified by three's own diagnostic strings (they survive
    // minification). The lazy importer necessarily mentions the chunk path ("three.module...") and
    // export names ("WebGLRenderer"), so THREE_SIGNATURES would wrongly flag it as a three chunk.
    const threeChunks = files(dist, '.js').filter((f) =>
      /THREE\.(WebGLRenderer|BufferGeometry)\b/.test(read(f)),
    );
    assert.ok(threeChunks.length > 0, 'expected a three.js chunk in dist/cosmos');
    for (const page of files(dist, '.html')) {
      const html = read(page);
      for (const c of threeChunks)
        assert.ok(
          !html.includes(relative(dist, c).split('\\').join('/')),
          `${relative(dist, page)} references ${relative(dist, c)} directly`,
        );
      const closure = initialClosure(dist, html);
      for (const c of threeChunks)
        assert.ok(
          !closure.has(c),
          `${relative(dist, page)} statically imports ${relative(dist, c)}`,
        );
    }
    // it must be reachable through a dynamic import() somewhere
    const dynamic = files(dist, '.js').some((f) =>
      threeChunks.some((c) =>
        new RegExp(
          `import\\(\\s*["'][^"']*${relative(dirname(f), c)
            .split('\\')
            .join('/')
            .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
            .replace(/^\\\.\//, '')}["']`,
        ).test(read(f)),
      ),
    );
    assert.ok(dynamic, 'expected the three chunk to be loaded via dynamic import()');
  },
);
