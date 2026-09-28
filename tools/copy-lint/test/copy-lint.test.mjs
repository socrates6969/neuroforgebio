import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { lintSource, RULES } from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const fx = (n) => join(here, 'fixtures', n);
const cli = join(here, '..', 'cli.mjs');
const run = (...a) => spawnSync(process.execPath, [cli, ...a], { encoding: 'utf8' });
const lint = (s, name = 'x.html') => lintSource(s, name);
const terms = (s, name) => lint(s, name).map((h) => h.term);

test('fixture with every banned phrase fails with file and line', () => {
  const r = run(fx('banned.html'));
  assert.equal(r.status, 1);
  const lines = r.stdout.trim().split('\n');
  const expected = [
    [5, 'built-in'],
    [6, 'live'],
    [7, 'available now'],
    [8, 'certified'],
    [9, 'HIPAA-compliant'],
    [10, 'SOC 2 compliant'],
    [11, 'treat'],
    [12, 'diagnose'],
    [13, 'cure'],
    [14, 'restore'],
    [15, 'automated neuro-cleaning'],
    [16, 'live'],
  ];
  for (const [line, term] of expected) {
    assert.ok(
      lines.some((l) => l.endsWith(`banned.html:${line}: ${term}`)),
      `missing ${line}: ${term}\n${r.stdout}`,
    );
  }
  // every rule is exercised by the fixture
  for (const rule of RULES)
    assert.ok(
      lines.some((l) => l.endsWith(`: ${rule.term}`)),
      `rule not covered: ${rule.term}`,
    );
});

test('allowlisted footer sentence and non-copy markup pass', () => {
  const r = run(fx('footer-allowed.html'));
  assert.equal(r.status, 0, r.stdout);
  assert.equal(r.stdout, '');
});

test('markdown, json and astro fixtures report the right lines', () => {
  const md = run(fx('banned.md'));
  assert.equal(md.status, 1);
  assert.match(md.stdout, /banned\.md:3: built-in/);
  assert.match(md.stdout, /banned\.md:5: live/);
  assert.match(md.stdout, /banned\.md:9: live/);
  assert.match(md.stdout, /banned\.md:11: available now/);
  const js = run(fx('banned.json'));
  assert.equal(js.status, 1);
  assert.match(js.stdout, /banned\.json:3: automated neuro-cleaning/);
  assert.match(js.stdout, /banned\.json:4: live/);
  assert.match(js.stdout, /banned\.json:6: HIPAA-compliant/);
  assert.match(js.stdout, /banned\.json:6: SOC 2 compliant/);
  assert.doesNotMatch(js.stdout, /banned\.json:7/); // href value is a URL, skipped
  const as = run(fx('page.astro'));
  assert.equal(as.status, 1);
  assert.equal(as.stdout.trim().split('\n').length, 2, as.stdout);
  assert.match(as.stdout, /page\.astro:7: available now/);
  assert.match(as.stdout, /page\.astro:8: certified/);
});

test('--json output', () => {
  const r = run('--json', fx('banned.json'));
  assert.equal(r.status, 1);
  const o = JSON.parse(r.stdout);
  assert.ok(Array.isArray(o.results) && o.results.length === 4);
  assert.deepEqual(Object.keys(o.results[0]).sort(), ['file', 'line', 'match', 'term']);
});

test('mock UI numbers need a demo data / target / ESTIMATE label', () => {
  const h = run(fx('mock.html'));
  assert.equal(h.status, 1);
  assert.deepEqual(
    h.stdout
      .trim()
      .split('\n')
      .map((l) => l.replace(/^.*mock\.html:/, '')),
    ['1: mock-number-unlabelled', '6: mock-number-unlabelled'],
  );
  const j = run(fx('mock.json'));
  assert.deepEqual(
    j.stdout
      .trim()
      .split('\n')
      .map((l) => l.replace(/^.*mock\.json:/, '')),
    ['3: mock-number-unlabelled'],
  );
});

test('live: status uses are banned, other uses are not', () => {
  for (const s of [
    'Now live',
    'We are live!',
    'go live in May',
    'Status: live',
    'Live now',
    'a live product',
    'It went live.',
  ]) {
    assert.deepEqual(terms(`<p>${s}</p>`), ['live'], s);
  }
  for (const s of [
    'deliver',
    'alive',
    'olive',
    'live streams from LSL',
    'where people live',
    'not a live product',
    'We will never go live without review',
    'liveness',
  ]) {
    assert.deepEqual(terms(`<p>${s}</p>`), [], s);
  }
});

test('word boundaries and case-insensitivity', () => {
  assert.deepEqual(terms('<p>CERTIFIED</p>'), ['certified']);
  assert.deepEqual(terms('<p>Built‑in</p>'), ['built-in']); // U+2011 non-breaking hyphen
  assert.deepEqual(terms('<p>HIPAA&#8209;compliant</p>'), ['HIPAA-compliant']);
  assert.deepEqual(terms('<p>treatment curation restoration diagnostics</p>'), []);
  assert.deepEqual(terms('<p>treats</p>'), ['treat']);
  assert.deepEqual(terms('<p>built in Rust</p>'), []);
});

test('negation is limited to the same clause and a 4-word window', () => {
  assert.deepEqual(terms('<p>Not reviewed. It is certified.</p>'), ['certified']);
  assert.deepEqual(terms('<p>not a single, reviewed, audited, signed, certified thing</p>'), [
    'certified',
  ]);
  assert.deepEqual(terms('<p>It is not certified.</p>'), []);
});

test('multi-line phrases are caught and reported at the first line', () => {
  assert.deepEqual(lint('<p>\nAvailable\nnow\n</p>'), [
    { line: 2, term: 'available now', match: 'Available now' },
  ]);
});

test('directories recurse but skip node_modules and dist unless passed explicitly', () => {
  const root = mkdtempSync(join(tmpdir(), 'copy-lint-'));
  try {
    for (const d of ['node_modules/pkg', 'dist/clinical', 'src'])
      mkdirSync(join(root, d), { recursive: true });
    writeFileSync(join(root, 'node_modules/pkg/readme.md'), 'certified\n');
    writeFileSync(join(root, 'dist/clinical/index.html'), '<p>certified</p>\n');
    writeFileSync(join(root, 'src/ok.md'), 'Designed, planned, roadmap.\n');
    writeFileSync(join(root, 'src/notes.txt'), 'certified\n');
    assert.equal(run(root).status, 0);
    const d = run(join(root, 'dist'));
    assert.equal(d.status, 1);
    assert.match(d.stdout, /index\.html:1: certified/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('Norwegian negations allowlist a negated hit in the same clause', () => {
  assert.deepEqual(lintSource('Tjenesten skal ikke brukes til diagnose.\n', 'x.md'), []);
  assert.deepEqual(lintSource('{"t": "Vi vil aldri diagnose noen"}', 'x.json'), []);
  assert.deepEqual(lintSource('Uten diagnose.\n', 'x.md'), []);
  // no negation, or a negation in another clause: still a hit
  assert.deepEqual(
    lintSource('Brukes til diagnose.\n', 'x.md').map((h) => h.term),
    ['diagnose'],
  );
  assert.deepEqual(
    lintSource('Ikke klinisk. Vi kan diagnose.\n', 'x.md').map((h) => h.term),
    ['diagnose'],
  );
});

test('reviewed exact-phrase allowlist: "certified US recipients" passes, "certified" elsewhere fails', () => {
  assert.deepEqual(
    lintSource('Transfers go to certified US recipients only.\n', 'legal/privacy.en.md'),
    [],
  );
  assert.deepEqual(
    lintSource('<p>Data goes to Certified\n US  recipients.</p>', 'dist/legal/privacy/index.html'),
    [],
  );
  assert.deepEqual(
    lintSource('{"body": "certified US recipients"}', 'content/legal/privacy.en.json'),
    [],
  );
  assert.deepEqual(
    lintSource(
      'Our platform is certified. We share with certified US recipients.\n',
      'legal/privacy.en.md',
    ).map((h) => h.term),
    ['certified'],
  );
  assert.deepEqual(
    lintSource('certified US partners\n', 'legal/privacy.en.md').map((h) => h.term),
    ['certified'],
  );
  assert.deepEqual(lintSource('certified US recipients\n', 'legal/privacy.en.md'), []);
});

test('allowlist entries with paths apply only to those files', async () => {
  assert.deepEqual(
    lintSource('certified US recipients\n', 'content/home.md').map((h) => h.term),
    ['certified'],
  );
  // Windows paths are normalised to forward slashes before matching
  assert.deepEqual(lintSource('certified US recipients\n', 'dist\\legal\\privacy\\index.md'), []);
  const { compileAllow } = await import('../lib.mjs');
  assert.throws(
    () =>
      compileAllow([
        { term: 'certified', phrase: 'certified US recipients', reason: 'x'.repeat(25), paths: [] },
      ]),
    /paths/,
  );
});

test('allow.json entries are valid and need a reason; unknown terms are rejected', async () => {
  const { ALLOW, compileAllow } = await import('../lib.mjs');
  assert.ok(ALLOW.length >= 1);
  assert.throws(
    () => compileAllow([{ term: 'certified', phrase: 'certified US recipients' }]),
    /reason/,
  );
  assert.throws(
    () =>
      compileAllow([{ term: 'nope', phrase: 'x', reason: 'a long enough written reason here' }]),
    /unknown term/,
  );
  assert.throws(
    () =>
      compileAllow([
        { term: 'certified', phrase: 'US recipients', reason: 'a long enough written reason here' },
      ]),
    /does not contain/,
  );
});
