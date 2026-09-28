// Content tests for @nf/content. Run from anywhere:
//   node --experimental-strip-types --no-warnings --test "packages/content/test/*.test.mjs"
// (the loader is erasable TypeScript, so Node 22 needs --experimental-strip-types).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, relative, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import {
  schemas,
  raw,
  loadContent,
  content,
  validate,
  walkStrings,
  getContent,
  publishedInnerPages,
  INNER_PAGE_KEYS,
  SECURITY_ANCHORS,
} from '../src/index.ts';
import { outputs as legalOutputs } from '../scripts/import-legal.mjs';
import { claim as claimSchema } from '../src/schema.ts';

const PKG = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = join(PKG, '..', '..');
const posix = (p) => p.split(sep).join('/');

/* ------------------------------------------------------------------ helpers */

/** Every object in a JSON tree, with its path. */
function objects(value, path = '$', out = []) {
  if (Array.isArray(value)) value.forEach((v, i) => objects(v, `${path}[${i}]`, out));
  else if (value && typeof value === 'object') {
    out.push({ obj: value, path });
    for (const [k, v] of Object.entries(value)) objects(v, `${path}.${k}`, out);
  }
  return out;
}

/** Objects that are factual claims: under a claim-bearing key, or claim-shaped. */
function claimObjects(entry) {
  const found = [];
  for (const { obj, path } of objects(entry.value)) {
    const underClaimKey =
      /\.(evidence\[\d+\]|claim|groups\[\d+\]\.rows\[\d+\]|questions\[\d+\])$/.test(path);
    const claimShaped = 'text' in obj && ('grade' in obj || 'sourceUrl' in obj || 'source' in obj);
    if (underClaimKey || claimShaped) found.push({ obj, path: `${entry.path} ${path}` });
  }
  return found;
}

const docCache = new Map();
function docsText() {
  if (docCache.has('all')) return docCache.get('all');
  const files = [];
  const walk = (d) => {
    for (const n of readdirSync(d)) {
      const p = join(d, n);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(md|txt)$/.test(n)) files.push(p);
    }
  };
  walk(join(ROOT, 'market'));
  walk(join(ROOT, 'research'));
  const text = files
    .map((f) => readFileSync(f, 'utf8'))
    .join('\n')
    .toLowerCase();
  docCache.set('all', text);
  return text;
}

/* ------------------------------------------------------------------ schema */

test('every content file validates against its schema', () => {
  for (const { path, value, schema } of schemas) {
    assert.deepEqual(validate(value, schema), [], `${path} has schema errors`);
  }
});

test('loadContent() returns substituted content without throwing', () => {
  const c = loadContent();
  assert.equal(c.brand.name, raw.brand.name);
  assert.match(c.brand.origin, /^https:\/\//);
  walkStrings(
    { site: c.site, home: c.home, pages: c.pages, whitepapers: c.whitepapers },
    (s, p) => {
      assert.doesNotMatch(s, /\{[a-zA-Z]+\}/, `unresolved placeholder at ${p}`);
    },
  );
});

test('the validator rejects bad content (self-test)', () => {
  const bad = structuredClone(raw.home);
  bad.pipeline.steps[0].status = 'available';
  bad.hero.heading = 'The data layer <strong>now</strong>';
  delete bad.pipeline.steps[1].evidence[0].source;
  bad.extra = 1;
  const errs = validate(bad, schemas.find((s) => s.path === 'content/home.json').schema);
  assert.ok(
    errs.some((e) => e.includes('steps[0].status')),
    'bad status not caught',
  );
  assert.ok(
    errs.some((e) => e.includes('hero.heading')),
    'disallowed tag not caught',
  );
  assert.ok(
    errs.some((e) => e.includes('evidence[0].source: missing')),
    'missing source not caught',
  );
  assert.ok(
    errs.some((e) => e.includes('extra: unknown key')),
    'unknown key not caught',
  );
});

test('placeholder domain is flagged as a placeholder', () => {
  if (raw.brand.domainIsPlaceholder) assert.match(raw.brand.domain, /\.(invalid|example|test)$/);
  assert.equal(typeof raw.brand.legalNameIsPlaceholder, 'boolean');
});

/* ------------------------------------------------------------------ sources */

test('every factual claim has a source', () => {
  let n = 0;
  for (const entry of schemas) {
    for (const { obj, path } of claimObjects(entry)) {
      n++;
      assert.equal(typeof obj.source, 'string', `${path}: claim without source`);
      assert.ok(obj.source.trim().length > 0, `${path}: empty source`);
      if (!path.includes('.questions[')) {
        // claims proper (not research-question pointers) must satisfy the Claim schema
        const errs = validate(
          { text: obj.text, source: obj.source, ...pick(obj, ['sourceUrl', 'grade']) },
          claimSchema,
        );
        assert.deepEqual(errs, [], `${path}: not a valid claim`);
      }
    }
  }
  assert.ok(n >= 15, `expected many claims, found ${n}`);
});

function pick(o, keys) {
  return Object.fromEntries(keys.filter((k) => k in o).map((k) => [k, o[k]]));
}

test('every source points into market/ or research/ and exists (with its § section)', () => {
  for (const entry of schemas) {
    for (const { obj, path } of claimObjects(entry)) {
      const m = /^((?:market|research)\/[\w./-]+?\.md)(?: §(\d+[a-z]?))?$/.exec(obj.source);
      assert.ok(
        m,
        `${path}: source "${obj.source}" must be "market/<file>.md §N" or a research/ path`,
      );
      const file = join(ROOT, m[1]);
      assert.ok(existsSync(file), `${path}: ${m[1]} does not exist`);
      if (m[2]) {
        const md = readFileSync(file, 'utf8');
        const re = new RegExp(`^#{2,3} ${m[2]}[.\\s]`, 'm');
        assert.match(md, re, `${path}: section §${m[2]} not found in ${m[1]}`);
      }
    }
  }
});

test('every sourceUrl appears in the market/ or research/ docs', () => {
  const docs = docsText();
  for (const entry of schemas) {
    for (const { obj, path } of claimObjects(entry)) {
      if (!obj.sourceUrl) continue;
      const u = obj.sourceUrl.toLowerCase();
      const needle = u.startsWith('https://doi.org/')
        ? u.slice('https://doi.org/'.length)
        : u.replace(/^https?:\/\//, '');
      assert.ok(
        docs.includes(needle),
        `${path}: ${obj.sourceUrl} not found in market/ or research/ docs`,
      );
    }
  }
});

// A digit outside a claim usually means an unsourced fact. Allowed: section/step numbers,
// protocol/standard names, versions in illustrative code, dates of our own notes, figure captions.
const ALLOWED_NUMBER_PATTERNS = [
  /^\d{2}( · .*)?$/, // "01", "01 · Platform"
  /AES-256|TLS 1\.3|SOC 2|Art\. [59]|5\(1\)\(f\)|© 2026|C\/C\+\+/,
  /^2026-\d\d-\d\d$/,
];
// Licence identifiers, matched as exact strings (not patterns) and stripped before the digit check.
const LICENCE_IDS = ['CC BY 4.0', 'CC-BY-4.0', 'Apache-2.0'];

/** The string with allowed licence names and non-claim patterns removed; any digit left is a finding. */
function stripAllowedNumbers(s) {
  const noLicences = LICENCE_IDS.reduce((acc, id) => acc.split(id).join(''), s);
  return ALLOWED_NUMBER_PATTERNS.reduce(
    (acc, re) => acc.replace(new RegExp(re.source, 'g'), ''),
    noLicences,
  );
}

test('digit rule: licence names pass, but a number next to one still fails', () => {
  for (const ok of [
    'Derived from MC_RTT (CC BY 4.0); changes were made',
    'CC-BY-4.0',
    'Apache-2.0',
  ])
    assert.doesNotMatch(stripAllowedNumbers(ok), /\d/, ok);
  for (const bad of [
    'CC BY 4.0 and 42 labs',
    'CC BY 4.0 and 99% accurate',
    'CC BY 4.01',
    'CC-BY-4.0: 3 datasets',
    'Apache-2.0, 12 contributors',
  ])
    assert.match(stripAllowedNumbers(bad), /\d/, `must still fail: ${bad}`);
});

test('numbers in copy appear only inside sourced claims or known non-claim patterns', () => {
  const skipPath =
    /(\.code\.lines|\.figures\.|\.rows\[|\.evidence\[|\.claim\.|\.questions\[|\.openItems|\.buildSource)/;
  for (const { path: file, value } of schemas) {
    if (file === 'brand.json') continue;
    // The security page (nfb-security) and the legal drafts (nfb-legal) are owner-reviewed texts about
    // our own controls and the law (TLS 1.3, Art. 6(1)(f), 24 hours); they make no market claims.
    if (/^content\/(security\.|legal\/)/.test(file)) continue;
    walkStrings(value, (s, p) => {
      if (!/\d/.test(s) || skipPath.test(p)) return;
      assert.doesNotMatch(stripAllowedNumbers(s), /\d/, `${file} ${p}: unsourced number in "${s}"`);
    });
  }
});

test('buildSource: every buildSource points to docs/hive/M*-REPORT.md and cites a valid step', () => {
  // buildSource is internal evidence for BuildStatePill: one or more sources joined by "; ". The first
  // is always "docs/hive/M{N}-REPORT.md step {id}"; later ones are further report steps or a repo
  // test file that exercises the feature where the report row doesn't name it (e.g.
  // "services/platform/tests/governance/test_gov_rules.py").
  const buildSourcePattern = /^docs\/hive\/M\d+-REPORT\.md step [\d.–\-]+$/;
  const testFilePattern =
    /^(services|tools|packages|bindings)\/[\w./-]*test[\w./-]*\.(py|rs|mjs|ts)$/;
  const docPath = join(ROOT, 'docs/hive');
  const reportFiles = readdirSync(docPath).filter((f) => /^M\d+-REPORT\.md$/.test(f));
  const reportSteps = Object.fromEntries(
    reportFiles.map((f) => {
      const content = readFileSync(join(docPath, f), 'utf8');
      // Extract table step ids: lines starting with "| " followed by step number(s), possibly with markdown
      // Matches "| 2.5 |", "| **5.5** |", "| 4.2–4.3 |" at the start of a table row
      const steps = new Set();
      const lines = content.split('\n');
      for (const line of lines) {
        const match = line.match(/^\|\s+\*{0,2}([\d.–\-]+)\*{0,2}\s+\|/);
        if (match) steps.add(match[1].trim());
      }
      return [f, steps];
    }),
  );

  for (const { path: file, value } of schemas) {
    walkStrings(value, (full, p) => {
      if (!/buildSource/.test(p)) return;
      const [first, ...rest] = full.split('; ');
      assert.match(
        first,
        buildSourcePattern,
        `${file} ${p}: first buildSource must be a report step`,
      );
      for (const s of [first, ...rest]) checkSource(s, `${file} ${p}`);
    });
  }

  function checkSource(s, where) {
    if (!buildSourcePattern.test(s)) {
      assert.match(s, testFilePattern, `${where}: invalid buildSource "${s}"`);
      assert.ok(existsSync(join(ROOT, s)), `${where}: buildSource file not found: ${s}`);
      return;
    }
    const [, reportFile, stepRange] = s.match(/^docs\/hive\/(M\d+-REPORT\.md) step ([\d.–\-]+)$/);
    assert.ok(reportSteps[reportFile], `${where}: report file not found: ${reportFile}`);
    // Handle step ranges like "4.2–4.3" (en-dash) or "2.1–2.8"
    // Also handle single steps like "2.5" and hyphenated like "4.2-4.3" (hyphen)
    const steps = stepRange.includes('–')
      ? stepRange.split('–')
      : stepRange.includes('-')
        ? stepRange.split('-')
        : [stepRange];
    for (const step of steps) {
      assert.ok(
        reportSteps[reportFile].has(step.trim()),
        `${where}: step id "${step.trim()}" not found in ${reportFile}`,
      );
    }
  }
});

test('buildSource is not rendered on pages (internal evidence only)', () => {
  // buildSource provides evidence to BuildStatePill, but the value itself is not shown to users
  for (const dist of ['clinical', 'cosmos']) {
    const indexPath = join(ROOT, `apps/web/dist/${dist}/index.html`);
    const html = readFileSync(indexPath, 'utf8');
    // buildSource would appear as text if rendered (e.g. "docs/hive/M2-REPORT.md")
    assert.doesNotMatch(
      html,
      /docs\/hive\/M\d+-REPORT\.md/,
      `${dist} homepage: buildSource leaked into HTML`,
    );
  }
  // Check inner pages (sample a few)
  for (const dist of ['clinical', 'cosmos']) {
    const platformPath = join(ROOT, `apps/web/dist/${dist}/platform/index.html`);
    const html = readFileSync(platformPath, 'utf8');
    // BuildStatePill renders the label "Built, tested internally", not the buildSource value
    if (html.includes('built-internal') || html.includes('Built, tested internally')) {
      assert.doesNotMatch(
        html,
        /docs\/hive\/M\d+-REPORT\.md/,
        `${dist} /platform: buildSource leaked into HTML`,
      );
    }
  }
});

/* ------------------------------------------------------------------ binding copy rules */

test('binding copy fixes (BLUEPRINT §2.6, DECISIONS D1, CONTENT-SPEC) are applied verbatim', () => {
  const h = raw.home;
  assert.equal(
    h.hero.sub,
    'Versioned, comparable pipelines and neural-data governance, from electrode to model.',
  );
  const step2 = h.pipeline.steps.find((s) => s.id === 'pipelines');
  assert.equal(
    step2.body,
    'Versioned preprocessing pipelines with full provenance. Run one, or run a grid of them and see how your results move.',
  );
  const models = h.pipeline.steps.find((s) => s.id === 'models');
  assert.match(
    models.body,
    /^Governed model registry \(roadmap\): versioned models with provenance, documented intended use and use restrictions\./,
  );
  assert.match(models.body, /benchmarks will be published with methods/i);
  assert.equal(models.status, 'roadmap');
  assert.deepEqual(h.pipeline.code.lines, [
    'import {pkg} as nf            # Illustrative API, subject to change',
    'rec = nf.open("sub-01_task-motor_eeg.edf")',
    'run = nf.pipelines.get("eeg-basic@1.0.0").run(rec)',
    'print(run.provenance.id)          # every parameter, version and input hash',
  ]);
  const titles = h.research.cards.map((c) => c.title);
  assert.ok(
    titles.includes(
      'How preprocessing choices change decoding results: a multiverse analysis on public EEG',
    ),
  );
  const all = JSON.stringify(raw).toLowerCase();
  assert.ok(!all.includes('benchmarked on public datasets'));
  assert.ok(!all.includes('marketplace'), '"marketplace" must be reframed as a governed registry');
  assert.ok(!all.includes('ica-default'));
});

test('compliance wording matches CONTENT-SPEC exactly', () => {
  const desc = raw.home.compliance.rows.map((r) => r.description).join('\n');
  for (const phrase of [
    'AES-256 at rest, TLS 1.3 in transit',
    'RBAC + audit logs',
    'Designed for HIPAA-aligned workflows',
    'BAA available for enterprise (planned)',
    'SOC 2 Type II: on roadmap',
    'Data residency options (planned)',
    'Built to support emerging US state neural-data privacy laws (e.g. Colorado, California, Connecticut, Montana)',
    'De-identification tooling',
  ]) {
    assert.ok(desc.includes(phrase), `compliance grid is missing "${phrase}"`);
  }
});

test('no banned status or medical terms, and no certification claims (backup for copy-lint)', () => {
  const banned =
    /\b(built-?in|available now|certified|hipaa[- ]compliant|soc ?2[\w ]* compliant|treat(s|ed|ing)?|diagnos(e|es|ed|ing)|cure[sd]?|curing|restor(e|es|ed|ing)|automated neuro-?cleaning)\b/i;
  const liveStatus =
    /\b(is|are|now|go|goes|currently|already) live\b|\blive (now|today|product|service|platform|beta)\b|^live$/i;
  for (const { path: file, value } of schemas) {
    // Legal drafts quote law and third-party terms verbatim (nfb-legal); copy-lint with its negation
    // and reviewed-phrase rules is their gate (last test in this file, and the web build on the dist).
    if (file.startsWith('content/legal/')) continue;
    walkStrings(value, (s, p) => {
      if (/\.(href|source|sourceUrl|slug|id)$/.test(p)) return;
      assert.doesNotMatch(s, banned, `${file} ${p}: banned term in "${s}"`);
      assert.doesNotMatch(s, liveStatus, `${file} ${p}: "live" status in "${s}"`);
    });
  }
});

test('research: IRB/FDA banner, statuses, and nothing labelled verified', () => {
  const banner =
    'Computational/theoretical work; any clinical application requires IRB/FDA oversight';
  const idx = raw.pages.research;
  assert.equal(idx.banner, banner);
  assert.equal(raw.site.banners.irbFda, banner);
  const wp = idx.cards.find((c) => c.slug === 'somatosensory-closed-loop');
  assert.equal(wp.title, 'Bidirectional closed-loop somatosensory feedback: a computational study');
  assert.equal(wp.status, 'in-preparation');
  assert.equal(wp.banner, banner);
  assert.equal(idx.cards.find((c) => c.slug === 'preprocessing-multiverse').status, 'planned');
  assert.equal(
    idx.cards.find((c) => c.slug === 'hipaa-aligned-reference-architecture').status,
    'planned',
  );
  const paper = raw.whitepapers['somatosensory-closed-loop'];
  assert.equal(paper.banner, banner);
  assert.equal(paper.status, 'in-preparation');
  walkStrings({ idx, paper, home: raw.home.research }, (s, p) => {
    assert.doesNotMatch(s, /\bverified\b/i, `${p}: research copy must not label anything verified`);
  });
});

test('law tracker: every row sourced; unverified rows flagged; banner present', () => {
  const lt = raw.pages.lawTracker;
  assert.match(lt.banner, /^Not legal advice\./);
  const rows = lt.groups.flatMap((g) => g.rows);
  // 5.6: the state rules (CO, CA, CT, MT) and GDPR moved to rules/*.yaml (rendered at build time,
  // tested in apps/web/test/law-tracker.test.mjs); the rows here are the hand-kept context.
  assert.ok(rows.length >= 5);
  for (const r of rows)
    assert.ok(r.source && typeof r.verified === 'boolean', `${r.id}: needs source + verified`);
  assert.ok(lt.ruleset.badges.unverified.startsWith('Unverified'));
  for (const s of [lt.ruleset.absenceNote, lt.ruleset.intro, lt.ruleset.contextIntro])
    assert.doesNotMatch(s, /not regulated|unregulated/i, 'never "not regulated"');
  assert.equal(
    rows.find((r) => r.id === 'us-mind-act').verified,
    false,
    'MIND Act status is unverified',
  );
  for (const r of rows.filter((x) => !x.verified))
    assert.ok(r.note, `${r.id}: unverified rows need a note`);
});

test('early-access form is disabled with "opens soon" copy; legal pages are marked DRAFT', () => {
  assert.equal(raw.site.earlyAccess.disabled, true);
  assert.match(raw.site.earlyAccess.disabledNote, /early-access list opens soon/i);
  for (const [l, notice] of [
    ['en', /^DRAFT – not legal advice\./],
    ['no', /^UTKAST – ikke juridisk rådgivning\./],
  ]) {
    for (const key of ['privacy', 'terms', 'cookies', 'company']) {
      const p = raw.locales[l].legal[key];
      assert.equal(p.draft, true, `${l} ${key} must stay a draft until advokat review`);
      assert.match(p.draftNotice, notice, `${l} ${key} draft notice`);
    }
  }
  // any "Join ..." CTA must be disabled until step 4.7 (plain navigation to the section is fine)
  for (const { path: file, value } of schemas) {
    for (const { obj, path } of objects(value)) {
      if ('variant' in obj && /^join/i.test(obj.label))
        assert.equal(obj.disabled, true, `${file} ${path}: early-access CTA must be disabled`);
    }
  }
});

test('headings mark emphasis with <em> only', () => {
  const headings = [];
  for (const { path: file, value } of schemas) {
    walkStrings(value, (s, p) => {
      if (/\.heading$/.test(p) && s.includes('<')) headings.push(`${file} ${p}`);
      if (s.includes('<') && !/\.heading$/.test(p))
        assert.fail(`${file} ${p}: HTML outside a heading`);
    });
  }
  assert.ok(headings.length >= 10, 'expected emphasised headings');
});

/* ------------------------------------------------------------------ i18n (EN + NO bokmål) */

/** Key paths of a JSON tree with array indices collapsed: {a:[{b:1}]} -> ["$.a[].b"]. */
function keyPaths(v, p = '$', out = new Set()) {
  if (Array.isArray(v)) v.forEach((x) => keyPaths(x, `${p}[]`, out));
  else if (v && typeof v === 'object')
    for (const [k, x] of Object.entries(v)) keyPaths(x, `${p}.${k}`, out);
  else out.add(p);
  return out;
}

test('i18n: every NO file has the same keys as its EN counterpart', () => {
  const pairs = [
    ['ui', raw.locales.en.ui, raw.locales.no.ui],
    ['security', raw.locales.en.security, raw.locales.no.security],
    ...['privacy', 'terms', 'cookies', 'company'].map((k) => [
      `legal/${k}`,
      raw.locales.en.legal[k],
      raw.locales.no.legal[k],
    ]),
  ];
  for (const [name, en, no] of pairs) {
    const a = [...keyPaths(en)].sort();
    const b = [...keyPaths(no)].sort();
    assert.deepEqual(b, a, `${name}.no.json keys differ from ${name}.en.json`);
  }
});

// Keys that NO may add to an inner page, and nothing else: /no/pricing shows a note instead of the
// English-only early-access form (web-queen scope, 2026-09-27).
// Every NO inner page also carries `reviewed` (owner language review gate).
const NO_ONLY_KEYS = {
  platform: ['$.reviewed'],
  governance: ['$.reviewed'],
  sdks: ['$.reviewed'],
  pricing: [
    '$.reviewed',
    '$.earlyAccessNote.href',
    '$.earlyAccessNote.linkLabel',
    '$.earlyAccessNote.text',
  ],
};

/** Keys whose values a translation must not change: claims' sources, statuses, links, code. */
const FIXED_KEYS = new Set(
  'id status buildState buildSource source sourceUrl grade href variant disabled language lines'.split(
    ' ',
  ),
);

function fixedValues(v, p = '$', out = []) {
  if (Array.isArray(v)) v.forEach((x, i) => fixedValues(x, `${p}[${i}]`, out));
  else if (v && typeof v === 'object')
    for (const [k, x] of Object.entries(v)) {
      if (FIXED_KEYS.has(k)) out.push([`${p}.${k}`, x]);
      else fixedValues(x, `${p}.${k}`, out);
    }
  return out;
}

test('i18n: NO inner pages have the EN keys, evidence and tags (platform, governance, sdks, pricing)', () => {
  const en = raw.locales.en.innerPages;
  const no = raw.locales.no.innerPages;
  assert.deepEqual(Object.keys(no).sort(), Object.keys(en).sort());
  for (const k of Object.keys(en)) {
    const extra = NO_ONLY_KEYS[k] ?? [];
    const a = [...keyPaths(en[k]), ...extra].sort();
    const b = [...keyPaths(no[k])].sort();
    assert.deepEqual(b, a, `pages/${k}.no.json keys differ from pages/${k}.json`);
    // Same number of array entries everywhere (keyPaths collapses indices), so no claim is dropped or added.
    const shape = (s) =>
      s.sections.map((x) => ({
        id: x.id,
        body: x.body.length,
        items: x.items?.length ?? 0,
        evidence: x.evidence?.length ?? 0,
        code: x.code?.lines.length ?? 0,
      }));
    assert.deepEqual(shape(no[k]), shape(en[k]), `pages/${k}.no.json section shape`);
    assert.equal(no[k].cta?.length ?? 0, en[k].cta?.length ?? 0, `pages/${k}.no.json cta count`);
    assert.deepEqual(
      fixedValues({ ...no[k], earlyAccessNote: undefined }),
      fixedValues(en[k]),
      `pages/${k}.no.json changed a fixed value`,
    );
  }
});

test('i18n: unreviewed NO inner pages are not published (owner language review gate)', () => {
  const no = raw.locales.no.innerPages;
  for (const k of Object.keys(no))
    assert.equal(typeof no[k].reviewed, 'boolean', `pages/${k}.no.json needs "reviewed"`);
  for (const k of Object.keys(raw.locales.en.innerPages))
    assert.equal(
      raw.locales.en.innerPages[k].reviewed,
      undefined,
      `pages/${k}.json: EN has no gate`,
    );
  assert.deepEqual(publishedInnerPages('en'), [...INNER_PAGE_KEYS]);
  const expected = INNER_PAGE_KEYS.filter((k) => no[k].reviewed === true);
  assert.deepEqual(publishedInnerPages('no'), expected);
  // Pending owner review (2026-09-27): none of the four is published yet. Flip "reviewed" only on the
  // owner's word, and update this line with it.
  assert.deepEqual(publishedInnerPages('no'), []);
  assert.throws(() => publishedInnerPages('de'));
});

test('i18n: the NO early-access note links to the English form', () => {
  const n = raw.locales.no.innerPages.pricing.earlyAccessNote;
  assert.equal(n.href, '/pricing#early-access');
  assert.ok(raw.locales.en.innerPages.pricing.sections.some((s) => s.id === 'early-access'));
  for (const k of ['platform', 'governance', 'sdks'])
    assert.equal(raw.locales.no.innerPages[k].earlyAccessNote, undefined);
});

test('i18n: the NO security page mirrors the EN structure (anchors, rows, statuses)', () => {
  const shape = (s) =>
    s.sections.map((x) => ({
      id: x.id,
      body: x.body?.length ?? 0,
      after: x.after?.length ?? 0,
      status: x.status ?? null,
      headers: x.table?.headers.length ?? 0,
      rows: x.table?.rows.map((r) => ({ cells: r.cells.length, status: r.status })) ?? [],
      bullets: x.bullets?.map((b) => b.status ?? null) ?? [],
    }));
  const en = raw.locales.en.security;
  const no = raw.locales.no.security;
  assert.deepEqual(shape(no), shape(en));
  assert.deepEqual(
    no.legend.map((x) => x.status),
    en.legend.map((x) => x.status),
  );
  assert.deepEqual(
    en.sections.map((s) => s.id),
    [...SECURITY_ANCHORS],
    'anchors #data #never #software #standards #testing #incidents #disclosure, in order',
  );
});

test('i18n: status labels as given (EN Designed/Planned/Roadmap, NO Designet/Planlagt/Veikart)', () => {
  const pick3 = (l) => {
    const s = raw.locales[l].ui.statusLabels;
    return [s.designed, s.planned, s.roadmap];
  };
  assert.deepEqual(pick3('en'), ['Designed', 'Planned', 'Roadmap']);
  assert.deepEqual(pick3('no'), ['Designet', 'Planlagt', 'Veikart']);
});

test('security page: <title> and meta from website-security-page.md, brand as a token', () => {
  const en = raw.locales.en.security;
  const no = raw.locales.no.security;
  assert.equal(en.meta.title, 'Security | {brand}');
  assert.equal(no.meta.title, 'Sikkerhet | {brand}');
  assert.match(en.meta.description, /^How \{brand\} is designed to protect neural data: /);
  assert.match(no.meta.description, /^Slik er \{brand\} utformet for å beskytte nevrale data: /);
  for (const s of [en, no]) {
    const disclosure = s.sections.find((x) => x.id === 'disclosure');
    assert.ok(disclosure.bullets.some((b) => b.text.includes('security@{domain}')));
    assert.ok(disclosure.bullets.some((b) => b.text.includes('(/.well-known/security.txt)')));
  }
});

test('legal: committed JSON matches the nfb-legal drafts in docs/inputs/legal-website', () => {
  for (const { path, json } of legalOutputs()) {
    const committed = JSON.parse(readFileSync(path, 'utf8'));
    assert.deepEqual(
      committed,
      JSON.parse(json),
      `${path} is stale: run node packages/content/scripts/import-legal.mjs`,
    );
  }
});

test('legal: footer labels (EN Privacy/Terms/Cookies; NO the titles from the drafts)', () => {
  const en = raw.locales.en.ui.legal;
  assert.deepEqual(
    [en.privacy, en.terms, en.cookies, en.company],
    ['Privacy', 'Terms', 'Cookies', 'Company information'],
  );
  const no = raw.locales.no;
  for (const k of ['privacy', 'terms', 'cookies', 'company'])
    assert.equal(no.ui.legal[k], no.legal[k].shortTitle, `NO footer label for ${k}`);
});

test('getContent(locale): English is complete; Norwegian has ui, security, legal and innerPages', () => {
  const en = getContent('en');
  const no = getContent('no');
  assert.equal(en.locale, 'en');
  assert.ok(en.home && en.pages && en.site && en.security && en.legal.privacy);
  assert.equal(
    en.pages.lawTracker.groups.length > 0,
    true,
    'innerPages must not shadow Content.pages',
  );
  assert.equal(en.innerPages.platform.meta.title, en.pages.platform.meta.title);
  assert.equal(no.locale, 'no');
  assert.deepEqual(Object.keys(no).sort(), [
    'brand',
    'innerPages',
    'legal',
    'locale',
    'security',
    'ui',
  ]);
  assert.deepEqual(Object.keys(no.innerPages).sort(), [
    'governance',
    'platform',
    'pricing',
    'sdks',
  ]);
  assert.match(no.innerPages.platform.meta.title, /^Plattform · /);
  assert.doesNotMatch(JSON.stringify(no.innerPages), /\{(brand|pkg)\}/, 'tokens substituted');
  assert.equal(no.ui.statusLabels.designed, 'Designet');
  assert.throws(() => getContent('de'));
});

/* ------------------------------------------------------------------ brand token */

// Built from brand.json so this file never contains the name itself. Case-insensitive: catches the
// display name, the short name and the lowercase code identifier.
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const NAME_RE = new RegExp(
  [raw.brand.name, raw.brand.name.split(' ')[0], raw.brand.codeIdentifiers.pythonImport]
    .map(esc)
    .join('|'),
  'i',
);
const SKIP_DIRS = new Set(['node_modules', 'dist', '.astro', '.turbo', 'coverage', '.git']);
const BINARY = /\.(png|jpe?g|gif|webp|avif|ico|woff2?|ttf|otf|eot|zip|gz|pdf|npz|wasm)$/i;

function scan(dir, hits) {
  if (!existsSync(dir)) return;
  for (const n of readdirSync(dir)) {
    if (SKIP_DIRS.has(n)) continue;
    const p = join(dir, n);
    const st = statSync(p);
    if (st.isDirectory()) scan(p, hits);
    else if (!BINARY.test(n) && st.size < 5_000_000) {
      const rel = posix(relative(ROOT, p));
      if (rel === 'packages/content/brand.json') continue;
      const lines = readFileSync(p, 'utf8').split('\n');
      lines.forEach((l, i) => {
        if (NAME_RE.test(l)) hits.push(`${rel}:${i + 1}: ${l.trim().slice(0, 100)}`);
      });
    }
  }
}

test('brand token: the company name appears only in packages/content/brand.json (packages/, apps/, openapi/)', () => {
  const hits = [];
  for (const d of ['packages', 'apps', 'openapi']) scan(join(ROOT, d), hits);
  assert.deepEqual(
    hits,
    [],
    `literal company name / code identifier outside brand.json:\n${hits.join('\n')}`,
  );
});

test('brand token: a changed brand flows through the loader everywhere', () => {
  const c = loadContent({
    brand: {
      name: 'Acme Neuro',
      legalName: 'Acme Neuro Ltd',
      domain: 'acme-neuro.invalid',
      codeIdentifiers: { ...raw.brand.codeIdentifiers, pythonImport: 'acmeneuro' },
    },
  });
  const body = JSON.stringify({
    site: c.site,
    home: c.home,
    pages: c.pages,
    whitepapers: c.whitepapers,
  });
  assert.doesNotMatch(body, NAME_RE, 'old name survived a brand change');
  assert.doesNotMatch(JSON.stringify(c.locales), NAME_RE, 'old name survived in localised content');
  assert.equal(c.locales.en.security.meta.title, 'Security | Acme Neuro');
  assert.equal(c.locales.no.security.meta.title, 'Sikkerhet | Acme Neuro');
  assert.equal(c.locales.en.security.heading, 'Security at Acme Neuro');
  assert.match(c.locales.en.ui.brandHomeLabel, /^Acme Neuro, /);
  for (const l of ['en', 'no'])
    for (const [k, p] of Object.entries(c.locales[l].legal))
      assert.match(p.meta.title, /Acme Neuro$/, `locales.${l}.legal.${k}.meta.title`);
  assert.match(c.home.meta.title, /^Acme Neuro /);
  assert.equal(c.locales.en.ui.brandHomeLabel, 'Acme Neuro, home');
  assert.equal(c.locales.no.ui.brandHomeLabel, 'Acme Neuro, forside');
  assert.equal(c.site.footer.copyright, '© 2026 Acme Neuro Ltd');
  assert.match(c.site.footer.disclaimer, /^Acme Neuro /);
  assert.match(c.pages.platform.meta.title, /Acme Neuro$/);
  assert.match(c.site.notFound.meta.title, /Acme Neuro$/);
  assert.equal(c.home.pipeline.code.lines[0].startsWith('import acmeneuro as nf'), true);
  assert.equal(c.brand.origin, 'https://acme-neuro.invalid');
  // every page <title> carries the brand
  for (const [k, p] of Object.entries(c.pages))
    assert.match(p.meta.title, /Acme Neuro/, `pages.${k}.meta.title`);
  // the default export still uses the real brand
  assert.equal(content.brand.name, raw.brand.name);
});

/* ------------------------------------------------------------------ copy-lint */

const LINT = join(ROOT, 'tools', 'copy-lint', 'cli.mjs');
test(
  'copy-lint passes on packages/content',
  {
    skip: existsSync(LINT)
      ? false
      : 'tools/copy-lint/cli.mjs not present yet (owned by nfb-platform-eng)',
  },
  () => {
    const r = spawnSync(process.execPath, [LINT, 'packages/content'], {
      cwd: ROOT,
      encoding: 'utf8',
    });
    assert.equal(r.status, 0, `copy-lint failed:\n${r.stdout}${r.stderr}`);
  },
);
