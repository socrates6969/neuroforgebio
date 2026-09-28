// Regenerate bindings/c/include/neuroforge.h with cbindgen, or check that it is up to date (ADR 0013).
//   node bindings/c/tools/header.mjs           write the header
//   node bindings/c/tools/header.mjs --check   exit 1 if the checked-in header differs
// Needs `cbindgen` on PATH (cargo install cbindgen --locked).
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const crate = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const header = join(crate, 'include', 'neuroforge.h');
const check = process.argv.includes('--check');

const dir = mkdtempSync(join(tmpdir(), 'nf-header-'));
const fresh = join(dir, 'neuroforge.h');
try {
  execFileSync(
    'cbindgen',
    [
      '--config',
      join(crate, 'cbindgen.toml'),
      '--crate',
      'neuroforge-c',
      '--quiet',
      '--output',
      fresh,
      crate,
    ],
    { stdio: ['ignore', 'inherit', 'inherit'] },
  );
  const lf = (s) => s.replace(/\r\n/g, '\n');
  const want = lf(readFileSync(fresh, 'utf8'));
  if (check) {
    let have = '';
    try {
      have = lf(readFileSync(header, 'utf8'));
    } catch {
      // missing header counts as out of date
    }
    if (have !== want) {
      process.stderr.write(
        'bindings/c/include/neuroforge.h is out of date: run `node bindings/c/tools/header.mjs` and commit it\n',
      );
      process.exit(1);
    }
    process.stdout.write('neuroforge.h is up to date\n');
  } else {
    writeFileSync(header, want);
    process.stdout.write(`wrote ${header}\n`);
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}
