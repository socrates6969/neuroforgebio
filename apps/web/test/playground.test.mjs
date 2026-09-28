// Neural Playground (/playground): the data loader, the committed asset and the built page.
// - loader: parses the asset written by tools/playground; rejects malformed assets; the math helpers
//   (R², interpolation, arm kinematics) behave;
// - asset: pinned dataset (hash shared with the pipeline), not an embargoed blind-test dataset, size
//   budget, results internally consistent;
// - dist: both builds render the page with the disclaimer, footer and complete results tables from the
//   asset, load the replay as an external module that fetches the identical hashed asset, and the home
//   page links to it.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import {
  REPO,
  WEB,
  attrs,
  inlineScriptProblems,
  brand,
  moduleClosureText,
  read,
  requireDist,
  unnamedControls,
  visibleText,
} from './_dist.mjs';
import {
  PlaygroundDataError,
  SCHEMA_COMPACT,
  expandCompact,
  activeUnits,
  armPoints,
  binsUpTo,
  formatR2,
  meanErrorMm,
  parsePlayground,
  r2,
  sampleAt,
  solveArm,
} from '../src/lib/playground-data.mjs';

const THEMES = ['clinical', 'cosmos'];
const ASSET = join(WEB, 'src/assets/playground/mc-rtt-playground.json');
const rawText = readFileSync(ASSET, 'utf8');
// The shipped asset is the compact nf-playground/2; the malformed-asset cases edit the expanded form.
const raw = () => expandCompact(JSON.parse(rawText));
const model = parsePlayground(raw());

// Files held back for blind tests by the motor-readout M1 track and the BCI hive (never used here).
const EMBARGOED_DANDISETS = ['000138', '000140', '001201'];

/* ------------------------------------------------------------------ loader */

test('loader: the committed asset parses into typed arrays', () => {
  assert.equal(model.dataset.dandiset, '000129');
  assert.equal(model.units, model.unitOrder.length);
  assert.equal(model.unitElectrode.length, model.units);
  assert.equal(model.electrodes, 96);
  assert.deepEqual(
    [...model.unitOrder].sort((a, b) => a - b),
    [...Array(model.units).keys()],
  );
  assert.ok(model.trials.length >= 6);
  for (const t of model.trials) {
    assert.ok(t.truePos instanceof Float32Array && t.truePos.length === 2 * t.bins);
    assert.equal(t.spikes.length, model.units);
    assert.ok(t.spikes.every((s) => s instanceof Int32Array));
    for (const d of model.decoders)
      for (const row of t.decoded[d]) for (const p of row) assert.equal(p.length, 2 * t.bins);
  }
});

test('loader: rejects malformed assets', () => {
  const cases = [
    ['schema', (a) => (a.schema = 'other/1')],
    ['sha256', (a) => (a.dataset.sha256 = 'abc')],
    ['unitOrder', (a) => (a.unitOrder[0] = a.unitOrder[1])],
    ['neuronCounts', (a) => (a.neuronCounts = [16, 8])],
    ['results rows', (a) => a.results.ridge.pop()],
    ['R² above one', (a) => (a.results.kalman[0][0].posR2 = 1.5)],
    ['truePos length', (a) => a.trials[0].truePos.pop()],
    ['durationMs', (a) => (a.trials[0].durationMs += 1)],
    ['spike outside trial', (a) => a.trials[0].spikes[0].push(a.trials[0].durationMs + 5)],
    ['noise level', (a) => a.trials[0].noiseSpikes.find((n) => n.length).splice(1, 1, 9)],
    ['noise pairs', (a) => a.trials[0].noiseSpikes.find((n) => n.length).pop()],
    ['decoded length', (a) => a.trials[0].decoded.ridge[0][0].pop()],
    ['missing decoder', (a) => delete a.trials[0].decoded.kalman],
    ['unitElectrode length', (a) => a.unitElectrode.pop()],
    ['electrode id', (a) => (a.unitElectrode[0] = a.electrodes + 1)],
  ];
  for (const [what, breakIt] of cases) {
    const a = raw();
    breakIt(a);
    assert.throws(() => parsePlayground(a), PlaygroundDataError, what);
  }
  assert.throws(() => parsePlayground(null), PlaygroundDataError);
});

test('loader: positions are converted to millimetres', () => {
  const a = raw();
  const t0 = a.trials[0];
  assert.ok(Math.abs(model.trials[0].truePos[0] - t0.truePos[0] / a.posScale) < 1e-4);
  assert.ok(Math.abs(model.trials[0].target[1] - t0.target[1] / a.posScale) < 1e-4);
});

test('helpers: R², interpolation, bins drawn, unit subsets, formatting', () => {
  const truth = Float32Array.from([0, 0, 1, 2, 2, 4, 3, 6]);
  assert.equal(r2(truth, truth), 1);
  const mean = Float32Array.from([1.5, 3, 1.5, 3, 1.5, 3, 1.5, 3]);
  assert.ok(Math.abs(r2(truth, mean)) < 1e-9);
  assert.ok(Number.isNaN(r2(truth, truth.subarray(0, 6))));
  // bin centres at 25, 75, 125, 175 ms (50 ms bins)
  assert.deepEqual(sampleAt(truth, 50, 0), [0, 0]);
  assert.deepEqual(sampleAt(truth, 50, 50), [0.5, 1]);
  assert.deepEqual(sampleAt(truth, 50, 1000), [3, 6]);
  assert.equal(binsUpTo(50, 0, 4), 0);
  assert.equal(binsUpTo(50, 25, 4), 1);
  assert.equal(binsUpTo(50, 999, 4), 4);
  const s8 = activeUnits(model, 8);
  assert.equal(s8.size, 8);
  for (const u of s8) assert.ok(activeUnits(model, 16).has(u), 'subsets are nested');
  assert.equal(meanErrorMm(truth, truth), 0);
  const shifted = Float32Array.from(truth, (v, i) => (i % 2 ? v + 4 : v + 3));
  assert.ok(Math.abs(meanErrorMm(truth, shifted) - 5) < 1e-6, '3-4-5 offset gives 5 mm');
  assert.ok(Number.isNaN(meanErrorMm(truth, truth.subarray(0, 6))));
  assert.equal(formatR2(0.6014), '0.60');
  assert.equal(formatR2(-0.05), '−0.05');
  assert.equal(formatR2(NaN), '–');
});

test('helpers: arm inverse kinematics reaches reachable points and clamps the rest', () => {
  const [l1, l2] = [1, 0.8];
  for (const [x, y] of [
    [0.5, 1.2],
    [-0.9, 0.7],
    [1.2, 0.1],
    [0.3, 0.4],
  ]) {
    const s = solveArm(x, y, l1, l2);
    const { hand } = armPoints(s.shoulder, s.elbow, l1, l2);
    assert.ok(Math.hypot(hand[0] - x, hand[1] - y) < 1e-6, `reach ${x},${y}`);
  }
  const far = solveArm(10, 0, l1, l2);
  const { hand } = armPoints(far.shoulder, far.elbow, l1, l2);
  assert.ok(Math.abs(Math.hypot(...hand) - (l1 + l2)) < 1e-4, 'clamped to full reach');
  assert.ok(hand[1] < 1e-3 && hand[0] > 0, 'pointing at the target');
  const zero = solveArm(0, 0, l1, l2);
  assert.ok(Number.isFinite(zero.shoulder) && Number.isFinite(zero.elbow));
});

/* ------------------------------------------------------------------ asset */

test('asset: pinned dataset hash matches the offline pipeline; licence and citation recorded', () => {
  const py = read(join(REPO, 'tools/playground/nf_playground/dataset.py'));
  const pinned = /^SHA256 = "([0-9a-f]{64})"$/m.exec(py)?.[1];
  assert.equal(model.dataset.sha256, pinned);
  const readme = read(join(REPO, 'tools/playground/README.md'));
  assert.ok(readme.includes(pinned), 'README pins the same hash');
  assert.equal(model.dataset.licence, 'CC-BY-4.0');
  assert.match(model.dataset.citation, /O'Doherty/);
  assert.match(model.dataset.doi, /^10\.48324\/dandi\.000129\//);
});

test('asset: not an embargoed blind-test dataset', () => {
  assert.ok(!EMBARGOED_DANDISETS.includes(model.dataset.dandiset));
  assert.doesNotMatch(JSON.stringify(model.dataset), /MC_Maze|EEGMMIDB|eegmmidb|LINK/);
});

test('asset: under the size budget', () => {
  assert.ok(statSync(ASSET).size < 3 * 1024 * 1024, 'asset under 3 MB');
});

test('asset: results are internally consistent and computed on test reaches', () => {
  assert.ok(model.method.reaches.test > 0 && model.method.testBins > 0);
  assert.ok(model.method.controlShuffledPosR2 < 0.1, 'negative control near zero');
  const last = model.neuronCounts.length - 1;
  for (const d of model.decoders)
    model.results[d].forEach((row, ci) =>
      row.forEach((c) => {
        assert.ok(c.posR2Min <= c.posR2Mean + 1e-9 && c.posR2Mean <= c.posR2Max + 1e-9);
        assert.ok(c.posR2Min <= c.posR2 + 1e-9 && c.posR2 <= c.posR2Max + 1e-9);
        if (ci === last) assert.equal(c.subsets, 1, 'all units: one subset');
      }),
    );
  // More neurons help, with no added noise (a sanity check on the pipeline, not a claim).
  for (const d of model.decoders) {
    const col = model.results[d].map((row) => row[0].posR2Mean);
    assert.ok(col[col.length - 1] > col[0] + 0.3, `${d}: all units beat the smallest subset`);
  }
  // Nested noise: every level's spikes include the previous level's.
  for (const t of model.trials)
    for (const n of t.noise)
      for (const lv of n.level) assert.ok(lv >= 1 && lv < model.noiseHz.length);
});

/* ------------------------------------------------------------------ dist */

function page(theme) {
  return read(join(requireDist(theme), 'playground/index.html'));
}

test('dist: both builds render the page, disclaimer and footer from content + asset', () => {
  for (const t of THEMES) {
    const html = page(t);
    // visibleText puts a space where a tag was; undo it around punctuation
    const text = visibleText(html)
      .replace(/\( /g, '(')
      .replace(/ ([,)])/g, '$1');
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1, `${t}: one h1`);
    assert.match(html, /id="pg-disclaimer"/);
    assert.match(text, /Not a medical device/);
    assert.match(text, /no hardware is controlled/);
    assert.match(
      text,
      /Research demo on open monkey motor-cortex data \(MC_RTT, DANDI 000129, CC-BY-4\.0\)\. Not a medical device\. Offline replay; no hardware is controlled\./,
    );
    assert.ok(text.includes(model.dataset.sha256), `${t}: pinned hash shown`);
    assert.doesNotMatch(text, /read(s|ing)? (the )?mind|mind[- ]reading|thought[- ]reading/i);
  }
});

test('dist: results tables list every configuration with the asset values', () => {
  for (const t of THEMES) {
    const html = page(t);
    for (const key of ['posR2', 'velR2']) {
      const at = html.indexOf(`data-pg-table="${key}"`);
      assert.ok(at > 0, `${t}: ${key} table`);
      const table = html.slice(at, html.indexOf('</table>', at));
      const rows = table.slice(table.indexOf('<tbody')).split(/<tr\b/).slice(1);
      assert.equal(rows.length, model.decoders.length * model.neuronCounts.length);
      let r = 0;
      for (const d of model.decoders)
        model.neuronCounts.forEach((_, ci) => {
          const cells = [...rows[r++].matchAll(/<td[^>]*>([^<]*)<\/td>/g)].map((m) => m[1]);
          assert.deepEqual(
            cells,
            model.results[d][ci].map((c) => formatR2(c[key])),
          );
        });
    }
  }
});

test('dist: replay script is an external module that fetches the identical hashed asset', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const html = page(t);
    // only JSON-LD may be inline (valid JSON, no script tags); everything else is an external module
    assert.deepEqual(inlineScriptProblems(html), [], 'no inline scripts except JSON-LD');
    const srcs = attrs(html, 'script', 'src').map((a) => a.value);
    const own = srcs.filter((s) => /playground/.test(s));
    assert.equal(own.length, 1, `${t}: one playground module`);
    const js = moduleClosureText(dist, own[0]);
    const url = /["'](\/_assets\/mc-rtt-playground\.[\w-]+\.json)["']/.exec(js)?.[1];
    assert.ok(url, `${t}: the module references the hashed asset`);
    assert.equal(read(join(dist, url)), rawText, `${t}: shipped asset is the committed one`);
    assert.doesNotMatch(js, /https?:\/\//, `${t}: the module names no remote origin`);
    // Budget: page JS + data well under 3 MB.
    const bytes = statSync(join(dist, own[0])).size + statSync(join(dist, url)).size;
    assert.ok(bytes < 3 * 1024 * 1024);
  }
});

test('dist: /playground/ links to /interface/; both are in the sitemap (not linked from /)', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    assert.ok(
      attrs(page(t), 'a', 'href').some((a) => a.value === '/interface/'),
      `${t}: link to the 3D scene`,
    );
    const sm = read(join(dist, 'sitemap.xml'));
    assert.match(sm, /\/playground\/<\/loc>/);
    assert.match(sm, /\/interface\/<\/loc>/);
  }
});

test('dist: keyboard and screen-reader basics (both themes)', () => {
  for (const t of THEMES) {
    const html = page(t);
    assert.deepEqual(unnamedControls(html), [], `${t}: every control has an accessible name`);
    // readouts that change every frame or every slider step must not be live regions
    assert.match(html, /<output\b[^>]*data-pg-time[^>]*aria-live="off"/);
    assert.match(html, /<output\b[^>]*data-pg-neurons-out[^>]*aria-live="off"/);
    assert.match(html, /aria-live="polite"[^>]*data-pg-live/);
    assert.doesNotMatch(
      html,
      /data-pg-play[^>]*aria-pressed/,
      'play toggles its label, not aria-pressed',
    );
    assert.match(html, /<fieldset\b[^>]*>\s*<legend[^>]*>[^<]*Added noise/, 'noise radios grouped');
    assert.match(html, /aria-valuetext="130 neurons"/, 'slider speaks its value');
  }
});

test('dist: the replay script handles reduced motion (no autoplay; stops when switched on)', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const own = attrs(page(t), 'script', 'src')
      .map((a) => a.value)
      .find((s) => /playground/.test(s));
    const js = moduleClosureText(dist, own);
    assert.match(js, /prefers-reduced-motion: reduce/);
    assert.match(js, /addEventListener\(\s*["']change["']/);
  }
});

test('dist: JS-off fallback: still + caption only inside <noscript>; live panels hidden', () => {
  const srcs = {};
  for (const t of THEMES) {
    const dist = requireDist(t);
    const html = page(t);
    const fig =
      /<noscript>\s*<figure\b[^>]*data-pg-still[^>]*>[\s\S]*?<\/figure>\s*<\/noscript>/.exec(
        html,
      )?.[0];
    assert.ok(fig, `${t}: still figure inside <noscript>`);
    const img = attrs(fig, 'img', 'src')[0];
    assert.match(img.tag, /\salt="[^"]{40,}"/);
    assert.match(img.value, /playground-still\./);
    assert.ok(existsSync(join(dist, img.value)), `${t}: ${img.value} exists`);
    const avif = attrs(fig, 'source', 'srcset')[0];
    assert.match(avif?.tag ?? '', /type="image\/avif"/, `${t}: AVIF <source> before the JPEG`);
    // srcset lists candidates ("url 640w, url 1152w"): every file must be served
    for (const u of avif.value.split(',').map((c) => c.trim().split(/\s+/)[0]))
      assert.ok(existsSync(join(dist, u)), `${t}: ${u} exists`);
    srcs[t] = img.value;
    assert.match(fig, /<figcaption\b[^>]*>[^<]{20,}<\/figcaption>/, 'visible caption');
    // with scripting on, the still is never referenced, so it costs nothing on the normal path
    assert.doesNotMatch(html.replace(/<noscript>[\s\S]*?<\/noscript>/g, ''), /playground-still\./);
    for (const sel of ['class="stage"', 'data-pg-controls', 'class="chart"'])
      assert.match(html, new RegExp(`<[a-z]+\\b[^>]*${sel}[^>]*\\shidden`), `${t}: ${sel} hidden`);
    assert.match(html, /<noscript>[\s\S]*?needs JavaScript[\s\S]*?<\/noscript>/);
    assert.match(html, /data-pg-table="posR2"/, 'results tables stay available without JS');
  }
  assert.notEqual(srcs.clinical, srcs.cosmos);
});

test('dist: CC BY 4.0 attribution is visible: dataset, author, licence with link, source link', () => {
  for (const t of THEMES) {
    const html = page(t);
    const text = visibleText(html).replace(/&#39;/g, "'");
    const hrefs = attrs(html, 'a', 'href').map((a) => a.value);
    assert.match(text, /MC_RTT/, `${t}: dataset name`);
    assert.match(text, /DANDI 000129/, `${t}: archive id`);
    assert.match(text, /O'Doherty, Joseph \(2024\)/, `${t}: author as in the licensor's citation`);
    assert.match(text, /CC-BY-4\.0/, `${t}: licence`);
    assert.ok(hrefs.includes('https://creativecommons.org/licenses/by/4.0/'), `${t}: licence link`);
    assert.ok(
      hrefs.includes(`https://doi.org/${model.dataset.doi}`) &&
        hrefs.includes(
          `https://dandiarchive.org/dandiset/${model.dataset.dandiset}/${model.dataset.version}`,
        ),
      `${t}: DOI and DANDI links`,
    );
  }
});

test('dist: CC BY 4.0 "changes were made" notice is visible', () => {
  for (const t of THEMES) {
    const text = visibleText(page(t));
    assert.match(
      text,
      /Derived from MC_RTT \(CC BY 4\.0\); changes were made:/,
      `${t}: modification notice`,
    );
    assert.ok(
      text.includes(
        `The dataset's creators do not endorse ${brand.name}.`.replace(/'/g, '&#39;'),
      ) || text.includes(`The dataset's creators do not endorse ${brand.name}.`),
      `${t}: no-endorsement line`,
    );
    for (const change of [
      'fifty-millisecond bins',
      'training, validation and test sets',
      'simulated random spikes',
    ])
      assert.ok(text.includes(change), `${t}: names the change "${change}"`);
  }
});

test('dist: a normal inline script on /playground would still fail the check (both themes)', () => {
  for (const t of THEMES) {
    const html = page(t);
    assert.deepEqual(inlineScriptProblems(html), [], `${t}: built page is clean`);
    const tampered = html.replace('</body>', '<script>alert(1)</script></body>');
    assert.ok(inlineScriptProblems(tampered).length > 0, `${t}: injected inline script is caught`);
    const badLd = html.replace(
      '</body>',
      '<script type="application/ld+json">{not json}</script></body>',
    );
    assert.ok(
      inlineScriptProblems(badLd).length > 0,
      `${t}: ld+json that does not parse is caught`,
    );
  }
});

// Digest of everything the pages display or compute from: unit order and electrodes, results, bounds
// and, per trial, the true path, target, spikes, noise spikes and every decoded path. PINNED is the
// digest of the model decoded from the last nf-playground/1 asset (main before the compact encoding),
// so equality proves the compact asset changes no displayed value.
const PINNED_MODEL_DIGEST = '09bc1544f019c3a82cc4833cfc25c1f76ba38736a5c7e4f38f6d463f395bc9f5';

function modelDigest(m) {
  const h = createHash('sha256');
  const put = (a) => h.update(JSON.stringify(Array.from(a)));
  put(m.unitOrder);
  put(m.unitElectrode);
  h.update(JSON.stringify(m.results));
  h.update(JSON.stringify(m.bounds));
  // pass-through fields the page also shows (web-perf review)
  const { dataset, method, neuronCounts, noiseHz, decoders } = m;
  h.update(JSON.stringify({ dataset, method, neuronCounts, noiseHz, decoders }));
  for (const t of m.trials) {
    put(t.truePos);
    put(t.target);
    t.spikes.forEach(put);
    for (const n of t.noise) {
      put(n.ms);
      put(n.level);
    }
    for (const d of m.decoders) for (const row of t.decoded[d]) row.forEach(put);
  }
  return h.digest('hex');
}

test('asset: the compact encoding is lossless (every displayed value unchanged)', () => {
  assert.equal(JSON.parse(rawText).schema, SCHEMA_COMPACT, 'shipped asset is the compact form');
  assert.equal(modelDigest(model), PINNED_MODEL_DIGEST);
});

test('loader: malformed compact assets fail with PlaygroundDataError, not TypeError', () => {
  const compact = () => JSON.parse(rawText);
  const cases = [
    ['noise entry null', (a) => (a.trials[0].noiseSpikes[0] = null)],
    [
      'level 0',
      (a) => {
        const n = a.trials[0].noiseSpikes.find((x) => x.l.length);
        n.l = '0' + n.l.slice(1);
      },
    ],
    ['level digits short', (a) => (a.trials[0].noiseSpikes.find((x) => x.l.length).l = '')],
    ['decoded grid not an array', (a) => (a.trials[0].decoded.ridge = {})],
    ['decoded row not an array', (a) => (a.trials[0].decoded.ridge[0] = 5)],
    ['decoded missing', (a) => delete a.trials[0].decoded],
    ['spikes missing', (a) => delete a.trials[0].spikes],
    ['trial null', (a) => (a.trials[0] = null)],
  ];
  for (const [what, breakIt] of cases) {
    const a = compact();
    breakIt(a);
    assert.throws(() => parsePlayground(a), PlaygroundDataError, what);
  }
});

test('asset: neuron counts never equal 1, so the plural "neurons" is always right', () => {
  assert.ok(
    model.neuronCounts.every((n) => n > 1),
    'add a singular neuron word before allowing 1',
  );
});
