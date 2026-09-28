// /interface (3D neural interface): the deterministic scene model and the built page.
// - model: illustrative grid, spike glow and pulses as pure functions of time, replay timeline,
//   tour/record camera path, URL flags;
// - dist: both builds render the page with the honesty banner, the still fallback, the electrode
//   list from the asset, no inline script, and a lazily imported scene that fetches the playground asset.
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
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
  TOUR,
  TOUR_SECONDS,
  cameraAt,
  gridSlots,
  ORBIT_STEP,
  orbitKey,
  placeLabels,
  NARROW_STAGE_PX,
  lastSpikeIndex,
  parseFlags,
  recentSpikes,
  spikeGlow,
  timeline,
  unitsByElectrode,
} from '../src/lib/interface-model.mjs';
import { parsePlayground } from '../src/lib/playground-data.mjs';

const THEMES = ['clinical', 'cosmos'];
const model = parsePlayground(
  JSON.parse(readFileSync(join(WEB, 'src/assets/playground/mc-rtt-playground.json'), 'utf8')),
);

test('model: Utah-style grid is 10 x 10 minus corners, centred, unique', () => {
  const g = gridSlots(10);
  assert.equal(g.length, 96);
  assert.equal(new Set(g.map((p) => p.join())).size, 96);
  for (const c of [
    [-4.5, -4.5],
    [4.5, -4.5],
    [-4.5, 4.5],
    [4.5, 4.5],
  ])
    assert.ok(!g.some((p) => p[0] === c[0] && p[1] === c[1]), 'no corner sites');
  assert.equal(
    g.reduce((s, p) => s + p[0], 0),
    0,
  );
  assert.ok(
    model.unitElectrode.every((e) => e >= 1 && e <= g.length),
    'every unit has a site',
  );
});

test('model: units grouped by electrode cover every unit once', () => {
  const m = unitsByElectrode(model.unitElectrode);
  assert.equal([...m.values()].flat().length, model.units);
  assert.deepEqual(
    unitsByElectrode([3, 1, 3]),
    new Map([
      [3, [0, 2]],
      [1, [1]],
    ]),
  );
});

test('model: spike glow, pulses and last-spike search are pure functions of time', () => {
  const s = Int32Array.from([10, 50, 200]);
  assert.equal(lastSpikeIndex(s, 5), -1);
  assert.equal(lastSpikeIndex(s, 50), 1);
  assert.equal(lastSpikeIndex(s, 1000), 2);
  assert.equal(spikeGlow(s, 5), 0);
  assert.equal(spikeGlow(s, 50), 1);
  assert.ok(Math.abs(spikeGlow(s, 110, 60) - Math.exp(-1)) < 1e-12);
  assert.equal(spikeGlow(s, 110), spikeGlow(s, 110), 'deterministic');
  assert.deepEqual(recentSpikes(s, 205, 200), [10, 50, 200]);
  assert.deepEqual(recentSpikes(s, 205, 160), [50, 200]);
  assert.deepEqual(recentSpikes(s, 5, 100), []);
});

test('model: replay timeline plays every trial in order with gaps, looping', () => {
  const tl = timeline([100, 200], 50);
  assert.equal(tl.total, 400);
  assert.deepEqual(tl.at(0), { trial: 0, tMs: 0 });
  assert.deepEqual(tl.at(120), { trial: 0, tMs: 100 }, 'holds the last frame in the gap');
  assert.deepEqual(tl.at(160), { trial: 1, tMs: 10 });
  assert.deepEqual(tl.at(410), { trial: 0, tMs: 10 }, 'loops');
  const real = timeline(model.trials.map((t) => t.durationMs));
  const seen = new Set();
  for (let t = 0; t < real.total; t += 25) seen.add(real.at(t).trial);
  assert.equal(seen.size, model.trials.length);
});

test('model: tour camera path is continuous, deterministic and loops', () => {
  assert.equal(TOUR_SECONDS, TOUR[TOUR.length - 1].t);
  assert.deepEqual(cameraAt(0).pos, TOUR[0].pos);
  assert.deepEqual(cameraAt(TOUR_SECONDS).pos, TOUR[0].pos, 'ends where it starts');
  assert.deepEqual(cameraAt(7.3), cameraAt(7.3));
  let prev = cameraAt(0).pos;
  for (let t = 1 / 30; t <= TOUR_SECONDS; t += 1 / 30) {
    const p = cameraAt(t).pos;
    assert.ok(
      Math.hypot(p[0] - prev[0], p[1] - prev[1], p[2] - prev[2]) < 1,
      `jump at ${t.toFixed(2)} s`,
    );
    prev = p;
  }
  assert.deepEqual([...new Set(TOUR.map((k) => k.caption))].sort(), [
    'array',
    'decoder',
    'neurons',
    'overview',
    'signal',
  ]);
});

test('model: URL flags', () => {
  assert.deepEqual(parseFlags('?record=1&t=4.5'), { record: true, t: 4.5, captions: true });
  assert.deepEqual(parseFlags('?captions=0'), { record: false, t: 0, captions: false });
  assert.deepEqual(parseFlags('?t=-3&record=yes'), { record: false, t: 0, captions: true });
});

function page(theme) {
  return read(join(requireDist(theme), 'interface/index.html'));
}

test('dist: both builds render the honest page and its controls', () => {
  const electrodes = new Set(model.unitElectrode).size;
  for (const t of THEMES) {
    const html = page(t);
    const text = visibleText(html);
    assert.equal((html.match(/<h1\b/g) ?? []).length, 1);
    assert.match(html, /id="ix-disclaimer"/);
    assert.match(text, /Illustrative anatomy and device; not a specific product/);
    assert.match(text, /Firing replayed from open data/);
    assert.match(text, /Not a medical device/);
    assert.match(text, /no hardware is controlled/);
    assert.match(text, /MC_RTT, DANDI 000129/);
    assert.doesNotMatch(text, /read(s|ing)? (the )?mind|mind[- ]reading|thought[- ]reading/i);
    assert.equal(
      (html.match(/<option value="\d+"/g) ?? []).length,
      electrodes,
      `${t}: electrode list`,
    );
    for (const k of ['tissue', 'electrodes', 'signals', 'decoder'])
      assert.match(html, new RegExp(`data-ix-layer="${k}"`));
    assert.ok(attrs(html, 'a', 'href').some((a) => a.value === '/playground/'));
  }
});

test('dist: electrode options use "unit" for exactly one unit, never "1 units" (both themes)', () => {
  const singles = [...unitsByElectrode(model.unitElectrode).values()].filter(
    (u) => u.length === 1,
  ).length;
  assert.ok(singles > 0, 'the asset has electrodes with exactly one unit');
  for (const t of THEMES) {
    const html = page(t);
    const options = [...html.matchAll(/<option value="\d+"[^>]*>([^<]*)<\/option>/g)].map((m) =>
      m[1].trim(),
    );
    assert.ok(!options.some((o) => / 1 units$/.test(o)), `${t}: an option says "1 units"`);
    assert.equal(
      options.filter((o) => / 1 unit$/.test(o)).length,
      singles,
      `${t}: one-unit electrodes`,
    );
    const ix = html.match(/<div\b[^>]*\sdata-interface[\s=>][^>]*>/g) ?? [];
    assert.equal(ix.length, 1, `${t}: one [data-interface]`);
    assert.match(ix[0], /\sdata-unit-word="unit"/, `${t}: data-unit-word`);
  }
});

test('dist: still fallback image is served per theme, only from <noscript> or on demand', () => {
  const srcs = {};
  for (const t of THEMES) {
    const dist = requireDist(t);
    const html = page(t);
    const noscript = [...html.matchAll(/<noscript>([\s\S]*?)<\/noscript>/g)]
      .map((m) => m[1])
      .join('');
    const img = attrs(noscript, 'img', 'src').find((a) => /interface-still\./.test(a.value));
    assert.ok(img, `${t}: still inside <noscript>`);
    assert.match(img.tag, /\salt="[^"]{40,}"/);
    assert.match(img.value, /interface-still\./);
    assert.ok(existsSync(join(dist, img.value)), `${t}: ${img.value} exists`);
    // <Picture>: an AVIF <source> first, the JPEG <img> as fallback
    const source = attrs(noscript, 'source', 'srcset').find((a) =>
      /interface-still\./.test(a.value),
    );
    assert.ok(source, `${t}: AVIF <source> inside <noscript>`);
    assert.match(source.tag, /type="image\/avif"/);
    // the script inserts the still (AVIF + JPEG) only when WebGL is missing or reduced motion is on
    const stage = /<div\b[^>]*data-ix-stage[^>]*>/.exec(html)[0];
    const jpg = /data-still-src="([^"]+)"/.exec(stage)?.[1];
    const avif = /data-still-avif="([^"]+)"/.exec(stage)?.[1];
    assert.match(jpg ?? '', /interface-still\..*\.jpg$/, `${t}: stage carries the JPEG`);
    assert.match(avif ?? '', /interface-still\..*\.avif$/, `${t}: stage carries the AVIF`);
    for (const u of [jpg, avif]) assert.ok(existsSync(join(dist, u)), `${t}: ${u} exists`);
    assert.match(stage, /data-still-alt="[^"]{40,}"/);
    // with scripting on, nothing on the normal path references the still
    assert.doesNotMatch(
      html
        .replace(/<noscript>[\s\S]*?<\/noscript>/g, '') // what a scripting browser loads
        .replace(/data-still-(src|avif)="[^"]*"/g, ''),
      /interface-still\./,
      `${t}: the still is not fetched on the normal path`,
    );
    srcs[t] = img.value;
  }
  assert.notEqual(srcs.clinical, srcs.cosmos);
});

test('dist: scene is an external module; three.js only via import(); asset fetched same-origin', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const html = page(t);
    // only JSON-LD may be inline (valid JSON, no script tags); everything else is an external module
    assert.deepEqual(inlineScriptProblems(html), [], 'no inline scripts except JSON-LD');
    const own = attrs(html, 'script', 'src')
      .map((a) => a.value)
      .filter((s) => /interface/.test(s));
    assert.equal(own.length, 1);
    const entry = moduleClosureText(dist, own[0]);
    assert.doesNotMatch(entry, /WebGLRenderer/, `${t}: three.js is not in the entry`);
    assert.match(entry, /import\(["'][^"']+\.js["']\)/, `${t}: scene loaded with import()`);
    assert.match(
      entry,
      /\/_assets\/mc-rtt-playground\.[\w-]+\.json/,
      `${t}: same asset as /playground/`,
    );
    assert.doesNotMatch(entry, /https?:\/\//, `${t}: no remote origin`);
  }
});

test('model: keyboard orbit keys mirror drag, scroll and reset', () => {
  assert.deepEqual(orbitKey('ArrowLeft'), { rotate: [-ORBIT_STEP, 0] });
  assert.deepEqual(orbitKey('ArrowDown'), { rotate: [0, ORBIT_STEP] });
  assert.ok(orbitKey('+').zoom < 1 && orbitKey('-').zoom > 1, 'plus zooms in, minus out');
  assert.ok(
    Math.abs(orbitKey('PageUp').zoom * orbitKey('PageDown').zoom - 1) < 1e-12,
    'zoom steps undo',
  );
  assert.deepEqual(orbitKey('Home'), { reset: true });
  assert.equal(orbitKey('a'), null);
  assert.equal(orbitKey('Tab'), null, 'Tab is never captured');
});

test('dist: keyboard and screen-reader basics (both themes)', () => {
  for (const t of THEMES) {
    const html = page(t);
    assert.deepEqual(unnamedControls(html), [], `${t}: every control has an accessible name`);
    // the per-frame readout must not be a live region (an <output> is role=status by default)
    assert.match(html, /<output\b[^>]*data-ix-readout[^>]*aria-live="off"/);
    assert.match(html, /<p\b[^>]*aria-live="polite"[^>]*data-ix-live/);
    assert.match(html, /id="ix-hint"[^>]*>[^<]*arrow keys/, 'keyboard instructions in the hint');
    assert.doesNotMatch(
      html,
      /data-ix-play[^>]*aria-pressed/,
      'play toggles its label, not aria-pressed',
    );
    assert.match(html, /data-ix-tour[^>]*aria-pressed="false"/);
    // reduced motion: a still image and an explicit opt-in, no autoplay
    assert.match(html, /data-ix-reduced[^>]*hidden/);
    assert.match(html, /<button\b[^>]*data-ix-show/);
  }
});

test('dist: the scene script handles reduced motion and keyboard orbit', () => {
  for (const t of THEMES) {
    const dist = requireDist(t);
    const own = attrs(page(t), 'script', 'src')
      .map((a) => a.value)
      .find((s) => /interface/.test(s));
    const js = moduleClosureText(dist, own);
    assert.match(js, /prefers-reduced-motion: reduce/);
    assert.match(js, /addEventListener\(\s*["']change["']/, 'reacts when the setting changes');
    assert.match(js, /ArrowLeft/, 'keyboard orbit shipped');
  }
});

test('dist: static fallback before the script runs (no JS / no WebGL): still, caption, no dead controls', () => {
  for (const t of THEMES) {
    const html = page(t);
    assert.match(
      html,
      /<p\b[^>]*data-ix-still-caption[^>]*\shidden[^>]*>[^<]{20,}<\/p>/,
      'caption shown by the script when the still is',
    );
    assert.match(
      html,
      /<noscript>[\s\S]*?class="still-cap"[\s\S]*?needs JavaScript and WebGL[\s\S]*?<\/noscript>/,
    );
    assert.match(
      html,
      /<form\b[^>]*data-ix-controls[^>]*\shidden/,
      'controls hidden until the scene runs',
    );
    assert.match(
      html,
      /<div\b[^>]*class="inspect[^"]*"[^>]*\shidden/,
      'inspector hidden until the scene runs',
    );
    assert.match(html, /data-ix-nowebgl hidden/, 'no-WebGL message present, shown by the script');
    assert.match(html, /id="h-ix-notes"/, 'text explanation of what is real and what is drawn');
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
    assert.ok(text.includes('fifty-millisecond bins'), `${t}: names the binning`);
  }
});

test('dist: <noscript> stills are responsive, eager and high priority, with no inline style', () => {
  for (const t of THEMES) {
    for (const html of [page(t), read(join(requireDist(t), 'playground/index.html'))]) {
      const pic = /<noscript>[\s\S]*?(<picture\b[\s\S]*?<\/picture>)[\s\S]*?<\/noscript>/.exec(
        html,
      )?.[1];
      assert.ok(pic, `${t}: <picture> in <noscript>`);
      const sources = [...pic.matchAll(/<source\b[^>]*>/g)].map((m) => m[0]);
      assert.match(sources[0] ?? '', /type="image\/avif"/, 'first <source> is AVIF');
      assert.match(sources[0], /sizes="[^"]*1152px"/, 'sizes matches the 1152 CSS px stage');
      const widths = [...sources[0].matchAll(/\s(\d+)w\b/g)].map((m) => Number(m[1]));
      assert.ok(widths.length >= 2 && Math.max(...widths) <= 1600, `widths ${widths} (max 1600)`);
      const img = /<img\b[^>]*>/.exec(pic)[0];
      assert.match(img, /loading="eager"/);
      assert.match(img, /fetchpriority="high"/);
      assert.doesNotMatch(pic, /\sstyle=/, 'no inline style (CSP)');
    }
  }
});

test('inline-script rule: JSON-LD passes; anything else, or JSON-LD that could run or break out, fails', () => {
  const ok = [
    '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Dataset"}</script>',
    '<script type="module" src="/_assets/x.js"></script>',
  ];
  for (const html of ok) assert.deepEqual(inlineScriptProblems(html), [], html);
  const bad = [
    '<script>alert(1)</script>',
    '<script type="module">import "/x.js"</script>',
    '<script type="text/javascript">1</script>',
    '<script type="application/json">{}</script>',
    '<script type="application/ld+json">{"a":"</script><script>alert(1)"}</script>',
    '<script type="application/ld+json">{"a": 1</script>',
    '<script type="application/ld+json">alert(1)</script>',
    '<script type="application/ld+json" onload="alert(1)">{}</script>',
  ];
  for (const html of bad) assert.ok(inlineScriptProblems(html).length > 0, `must fail: ${html}`);
});

test('dist: a normal inline script on /interface would still fail the check (both themes)', () => {
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

test('model: 3D labels never overlap or clip; narrow stages keep primary labels', () => {
  const L = (key, x, y, w = 120, h = 20, visible = true) => ({ key, x, y, w, h, visible });
  // overlap: the lower-priority label gives way
  let shown = placeLabels([L('cortex', 200, 100), L('array', 210, 105)], 800, 450);
  assert.deepEqual([...shown], ['array']);
  // clipping at the stage edges
  shown = placeLabels([L('array', 30, 100), L('decoder', 400, 10), L('arm', 400, 300)], 800, 450);
  assert.deepEqual([...shown], ['arm'], 'left-clipped and top-clipped labels are hidden');
  // hidden anchors stay hidden
  assert.equal(placeLabels([L('array', 400, 200, 120, 20, false)], 800, 450).size, 0);
  // narrow stage: secondary labels dropped even without collisions
  shown = placeLabels(
    [L('array', 100, 100, 60), L('headstage', 100, 300, 60), L('cortex', 250, 300, 60)],
    NARROW_STAGE_PX - 1,
    600,
  );
  assert.deepEqual([...shown], ['array']);
  // random stress: whatever is shown is pairwise disjoint and inside the stage
  let seed = 7;
  const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let run = 0; run < 200; run++) {
    const W = 300 + rnd() * 1300;
    const H = 300 + rnd() * 600;
    const labels = ['array', 'neurons', 'decoder', 'screen', 'arm', 'headstage', 'cortex'].map(
      (k) => L(k, rnd() * W, rnd() * H, 60 + rnd() * 140, 18),
    );
    const on = labels.filter((l) => placeLabels(labels, W, H).has(l.key));
    for (const a of on) {
      assert.ok(a.x - a.w / 2 >= 0 && a.x + a.w / 2 <= W && a.y - a.h >= 0 && a.y <= H, 'inside');
      for (const b of on)
        if (a !== b)
          assert.ok(
            a.x + a.w / 2 <= b.x - b.w / 2 ||
              b.x + b.w / 2 <= a.x - a.w / 2 ||
              a.y <= b.y - b.h ||
              b.y <= a.y - a.h,
            `${a.key} overlaps ${b.key}`,
          );
    }
  }
});

test('dist: the script-inserted still <picture> gets a box of its own (no-WebGL regression)', () => {
  // Layout can't run in node, so pin the rule that gives <picture data-ix-still> its size: without it
  // the <picture> has no box (its <img> is absolutely positioned) and the fallback reads as hidden.
  for (const t of THEMES) {
    const dist = requireDist(t);
    const css = attrs(page(t), 'link', 'href')
      .filter((a) => /rel=["']?stylesheet/i.test(a.tag))
      .map((a) => read(join(dist, a.value)))
      .join('\n');
    assert.match(
      css,
      /picture\[data-ix-still\][^{]*\{[^}]*position:\s*absolute[^}]*\}/,
      `${t}: rule for picture[data-ix-still]`,
    );
    assert.match(
      css,
      /picture\[data-ix-still\][^{]*\{[^}]*display:\s*block/,
      `${t}: display block`,
    );
  }
});

test('dist: each theme ships only its own fallback stills (imported via @theme)', () => {
  const src = (theme, name) =>
    readFileSync(join(REPO, `packages/themes/${theme}/stills/${name}-still.jpg`));
  for (const t of THEMES) {
    const other = t === 'clinical' ? 'cosmos' : 'clinical';
    const assets = join(requireDist(t), '_assets');
    for (const name of ['interface', 'playground']) {
      // Astro emits the untouched original as <name>-still.<hash>.jpg next to its resized variants
      const originals = readdirSync(assets).filter((f) =>
        new RegExp(`^${name}-still\.[^_]+\.jpg$`).test(f),
      );
      assert.equal(originals.length, 1, `${t}: one original ${name} still`);
      const bytes = readFileSync(join(assets, originals[0]));
      assert.ok(bytes.equals(src(t, name)), `${t}: ${name} still is this theme's`);
      assert.ok(!bytes.equals(src(other, name)), `${t}: not the ${other} still`);
    }
    // no copy of the other theme's still anywhere in this build
    const others = ['interface', 'playground'].map((n) => src(other, n));
    for (const f of readdirSync(assets).filter((n) => /-still\./.test(n)))
      assert.ok(
        !others.some((o) => readFileSync(join(assets, f)).equals(o)),
        `${t}: ${f} is the ${other} still`,
      );
  }
});

test('dist: the reduced-motion opt-in moves focus to the stage before hiding the button (T12)', () => {
  // e2e is CI-only, so pin the built handler: stage.tabIndex = -1, stage.focus(), then box.hidden
  for (const t of THEMES) {
    const dist = requireDist(t);
    const own = attrs(page(t), 'script', 'src')
      .map((a) => a.value)
      .find((s) => /interface/.test(s));
    const js = moduleClosureText(dist, own);
    const at = js.indexOf('[data-ix-show]');
    assert.ok(at >= 0, `${t}: opt-in handler present`);
    const handler = js.slice(at, at + 400);
    const focus = handler.search(/\.focus\(\)/);
    const hide = handler.search(/\.hidden\s*=\s*(!0|true)/);
    assert.match(
      handler,
      /\[data-ix-stage\][\s\S]*tabIndex\s*=\s*-1/,
      `${t}: stage made focusable`,
    );
    assert.ok(
      focus > 0 && hide > 0 && focus < hide,
      `${t}: focus() comes before hiding the button`,
    );
  }
});
