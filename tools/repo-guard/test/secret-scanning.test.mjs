// SEC-086: gitleaks config, the opt-in pre-commit hook and the CI step stay wired together.
// (gitleaks itself is CI-only; the local proof is repo-guard's fake-AWS-key test in repo-guard.test.mjs.)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const read = (p) => readFileSync(join(root, p), 'utf8');

test('.gitleaks.toml extends the default rules', () => {
  const t = read('.gitleaks.toml');
  assert.match(t, /^\[extend\]\s*\nuseDefault = true/m);
  assert.doesNotMatch(t, /^paths = \[[^\]]*'''\.\*'''/m, 'no allow-everything path');
});

test('pre-commit config pins gitleaks by commit and runs repo-guard + hw-guard', () => {
  const p = read('.pre-commit-config.yaml');
  assert.match(
    p,
    /repo: https:\/\/github\.com\/gitleaks\/gitleaks\n\s+rev: [0-9a-f]{40} # v\d+\.\d+\.\d+/,
  );
  assert.match(p, /- id: gitleaks\b/);
  assert.match(p, /entry: node tools\/repo-guard\/cli\.mjs/);
  assert.match(p, /entry: node tools\/hw-guard\/cli\.mjs/);
});

test('CI scans full history with a checksum-verified gitleaks and the repo config', () => {
  const ci = read('.github/workflows/ci.yml');
  assert.match(ci, /fetch-depth: 0/);
  assert.match(ci, /sha256sum -c -/);
  assert.match(ci, /gitleaks git --config \.gitleaks\.toml .*--exit-code 1/);
});
