// The committed API client (src/api/authz.json, generated.ts) must match what the
// platform FastAPI app produces now. Needs the repo .venv (Python + nf_platform); skipped locally
// without it, required with CI=true.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { drift, dumpPlatform, findPython, generate } from '../scripts/gen-api.mjs';

const CI = /^(1|true)$/i.test(process.env.CI || '');
const python = findPython();

test(
  'generated API client matches the platform OpenAPI + authz matrix',
  { skip: !python && !CI ? 'no .venv Python' : false },
  async () => {
    assert.ok(python, 'CI needs the platform venv (uv sync --locked)');
    const files = await generate(dumpPlatform(python));
    assert.deepEqual(drift(files), [], 'run: node apps/console/scripts/gen-api.mjs');
  },
);
