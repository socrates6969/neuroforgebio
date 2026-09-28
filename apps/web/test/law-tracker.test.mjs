// BUILD-GUIDE 5.6: /law-tracker is generated from rules/*.yaml at build time.
// - loader: rows come from the RuleSet; a changed rule file changes the rows (temp copy);
// - dist: every rule of the current RuleSet is a table row in BOTH builds, with its review badge;
//   unverified rules are shown as unverified; the banner stays; never "not regulated";
// - rebuild (NF_WEB_REBUILD_TEST=1, slow: one astro build into a temp dir): a changed rule file
//   changes the built page. Run locally on demand and in CI.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { REPO, WEB, read, requireDist } from './_dist.mjs';
import { loadRuleSet } from '../src/lib/rules.mjs';

const THEMES = ['clinical', 'cosmos'];
const RULES = join(REPO, 'rules');

function tempRules() {
  const dir = mkdtempSync(join(tmpdir(), 'nf-rules-'));
  cpSync(RULES, dir, { recursive: true });
  return dir;
}

const esc = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

test('loader: one row per rule of the RuleSet, Montana unverified', () => {
  const rs = loadRuleSet(RULES);
  assert.ok(rs.version >= 1);
  assert.match(rs.contentSha256, /^[0-9a-f]{64}$/);
  const ids = rs.rows.map((r) => r.id);
  for (const f of ['co', 'ca', 'ct', 'mt', 'eu']) {
    const n = [...readFileSync(join(RULES, `${f}.yaml`), 'utf8').matchAll(/^ {2}- id: (\S+)/gm)];
    for (const m of n) assert.ok(ids.includes(m[1]), `${f}.yaml rule ${m[1]} missing`);
  }
  const mt = rs.rows.find((r) => r.jurisdiction === 'MT');
  assert.equal(mt.reviewStatus, 'unverified');
  assert.equal(mt.verified, false);
  for (const r of rs.rows) {
    assert.ok(r.citation.source, `${r.id}: citation`);
    assert.ok(r.obligations.length > 0, `${r.id}: what it covers`);
  }
});

test('loader: a changed rule file changes the rows (temp copy)', () => {
  const dir = tempRules();
  try {
    const f = join(dir, 'co.yaml');
    writeFileSync(
      f,
      readFileSync(f, 'utf8')
        .replace(/title: .*/, 'title: CHANGED TITLE FOR THE 5.6 TEST')
        .replace('review_status: draft', 'review_status: unverified'),
    );
    const row = loadRuleSet(dir).rows.find((r) => r.jurisdiction === 'CO');
    assert.equal(row.title, 'CHANGED TITLE FOR THE 5.6 TEST');
    assert.equal(row.verified, false);
    writeFileSync(f, readFileSync(f, 'utf8').replace(/review_status: \w+/, 'review_status: ok'));
    assert.throws(() => loadRuleSet(dir), /review_status/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

function assertPageMatchesRuleSet(html, rs) {
  assert.match(html, /id="not-legal-advice"/);
  assert.doesNotMatch(html, /not regulated|unregulated/i);
  assert.match(html, new RegExp(`data-ruleset-version="${rs.version}"`));
  const trs = [...html.matchAll(/<tr\b[^>]*data-rule-id="([^"]+)"[\s\S]*?<\/tr>/g)];
  assert.deepEqual(
    trs.map((m) => m[1]),
    rs.rows.map((r) => r.id),
    'table rows = RuleSet rules, in order',
  );
  for (const r of rs.rows) {
    const tr = trs.find((m) => m[1] === r.id)[0];
    assert.match(tr, new RegExp(`data-review-status="${r.reviewStatus}"`));
    assert.ok(tr.includes(esc(r.title)), `${r.id}: title`);
    assert.ok(tr.includes(esc(r.citation.source)), `${r.id}: citation source`);
    if (r.effectiveDate) assert.ok(tr.includes(`datetime="${r.effectiveDate}"`), `${r.id}: date`);
    if (!r.verified) {
      assert.match(tr, /is-unverified/);
      assert.match(tr, /data-verified="false"/);
      assert.match(tr, /Unverified:/);
    } else if (r.reviewStatus === 'draft') {
      assert.match(tr, /Draft:/);
    }
  }
}

test('dist: both builds render every rule of the RuleSet with its review badge', () => {
  const rs = loadRuleSet(RULES);
  for (const t of THEMES) {
    const html = read(join(requireDist(t), 'law-tracker/index.html'));
    assertPageMatchesRuleSet(html, rs);
  }
});

test(
  'rebuild: a changed rule file changes the built page at the next build',
  { skip: process.env.NF_WEB_REBUILD_TEST === '1' ? false : 'set NF_WEB_REBUILD_TEST=1 (slow)' },
  () => {
    const dir = tempRules();
    const out = mkdtempSync(join(tmpdir(), 'nf-web-out-'));
    try {
      const f = join(dir, 'ct.yaml');
      writeFileSync(
        f,
        readFileSync(f, 'utf8')
          .replace(/title: .*/, 'title: Rebuilt from a changed rule file')
          .replace("effective_date: '2026-07-01'", "effective_date: '2026-07-02'"),
      );
      const require = createRequire(join(WEB, 'package.json'));
      const astro = join(dirname(require.resolve('astro/package.json')), 'astro.js');
      const r = spawnSync(process.execPath, [astro, 'build'], {
        cwd: WEB,
        stdio: 'inherit',
        env: {
          ...process.env,
          THEME: 'clinical',
          NF_RULES_DIR: dir,
          NF_WEB_OUT_DIR: out,
          ASTRO_TELEMETRY_DISABLED: '1',
        },
      });
      assert.equal(r.status, 0, 'astro build');
      const html = read(join(out, 'law-tracker/index.html'));
      assert.match(html, /Rebuilt from a changed rule file/);
      assert.match(html, /datetime="2026-07-02"/);
      assertPageMatchesRuleSet(html, loadRuleSet(dir));
    } finally {
      rmSync(dir, { recursive: true, force: true });
      rmSync(out, { recursive: true, force: true });
    }
  },
);
