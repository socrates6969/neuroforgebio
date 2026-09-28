// Launch gate for the placeholder host (scripts/host-gate.mjs): a launch/public build must not ship any built
// text file that still names a `.invalid` host; previews keep it. See docs/hive/HOSTING-HEADERS.md.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  PLACEHOLDER_HOST,
  assertNoPlaceholderHost,
  placeholderHosts,
} from '../scripts/host-gate.mjs';
import { postbuild } from '../scripts/postbuild.mjs';
import { brand, files, read, requireDist } from './_dist.mjs';

const REAL = {
  ...brand,
  domain: 'example.org',
  secondaryHost: 'cosmos.example.org',
  domainIsPlaceholder: false,
};

test('placeholderHosts: finds .invalid hosts in built text files, names file and line, skips JS/CSS', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-host-gate-'));
  try {
    writeFileSync(
      join(d, 'index.html'),
      '<p>ok</p>\n<link rel="canonical" href="https://site.invalid/">',
    );
    writeFileSync(join(d, 'sitemap.xml'), '<loc>https://cosmos.site.invalid/x/</loc>');
    writeFileSync(join(d, '_headers'), '/*\n  X: 1\n');
    writeFileSync(join(d, 'app.js'), 'if(e.invalid)return;const u="https://site.invalid"');
    writeFileSync(join(d, 'site.css'), '.x{content:"a.invalid"}');
    assert.deepEqual(placeholderHosts(d).sort(), [
      'index.html:2: site.invalid',
      'sitemap.xml:1: cosmos.site.invalid',
    ]);
    assert.doesNotThrow(() => assertNoPlaceholderHost(d, { stage: 'preview' }));
    for (const stage of ['launch', 'public'])
      assert.throws(
        () => assertNoPlaceholderHost(d, { stage }),
        new RegExp(
          `^Error: host gate: SITE_STAGE=${stage} but the placeholder host remains in 2 place\\(s\\)[\\s\\S]*index\\.html:2: site\\.invalid`,
        ),
      );
    writeFileSync(join(d, '_headers'), '/*\n  Link: <https://site.invalid/>; rel=canonical\n');
    assert.ok(placeholderHosts(d).includes('_headers:2: site.invalid'), '_headers is scanned');
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('postbuild: a preview build keeps the placeholder host and passes', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-host-preview-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    assert.ok(placeholderHosts(d).length > 0, 'today the build names the placeholder host');
    assert.doesNotThrow(() => postbuild('clinical', { dist: d, stage: 'preview' }));
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('postbuild: a launch build with a real brand domain but a leftover placeholder host fails and names the file', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-host-launch-bad-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    // security.txt is regenerated from the real brand, so only the leftover pages trip the gate
    assert.throws(
      () => postbuild('clinical', { dist: d, stage: 'launch', site: REAL }),
      /host gate: SITE_STAGE=launch but the placeholder host remains in \d+ place\(s\)[\s\S]*index\.html:\d+: [a-z0-9.-]+\.invalid/,
    );
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});

test('postbuild: a launch build with a real host everywhere passes', () => {
  const d = mkdtempSync(join(tmpdir(), 'nf-host-launch-ok-'));
  try {
    cpSync(requireDist('clinical'), d, { recursive: true });
    // what a rebuild after the owner sets the domain would contain
    for (const f of [
      ...files(d, '.html'),
      ...files(d, '.xml'),
      ...files(d, '.txt'),
      ...files(d, '.json'),
    ])
      writeFileSync(f, read(f).replace(new RegExp(PLACEHOLDER_HOST.source, 'gi'), 'example.org'));
    assert.doesNotThrow(() => postbuild('clinical', { dist: d, stage: 'launch', site: REAL }));
    assert.deepEqual(placeholderHosts(d), []);
    assert.match(
      readFileSync(join(d, '.well-known/security.txt'), 'utf8'),
      /security@example\.org/,
    );
  } finally {
    rmSync(d, { recursive: true, force: true });
  }
});
