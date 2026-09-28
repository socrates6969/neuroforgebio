// The dev/e2e mock IdP behaves like a strict OP: PKCE S256 enforced, refresh-token rotation with
// reuse detection (SEC-015), RS256 tokens verifiable with its JWKS.
import assert from 'node:assert/strict';
import { createHash, createPublicKey, randomBytes, verify } from 'node:crypto';
import { createServer } from 'node:http';
import { after, before, test } from 'node:test';
import { createMockIdp } from '../e2e/mock-idp.mjs';

let base;
let server;
const TENANT = '5e2e0000-0000-4000-8000-000000000001';

before(async () => {
  server = createServer();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
  const idp = createMockIdp({
    issuer: `${base}/mock-idp`,
    redirectUris: [`${base}/`],
    tenant: TENANT,
    testMint: false,
  });
  server.on('request', async (req, res) => {
    const path = new URL(req.url, base).pathname;
    const handled = path.startsWith('/mock-idp/')
      ? await idp.handle(req, res, path.slice('/mock-idp'.length))
      : false;
    if (handled === false) {
      res.writeHead(404);
      res.end();
    }
  });
});
after(() => server.close());

const form = (o) => new URLSearchParams(o).toString();
const post = (path, body) =>
  fetch(`${base}/mock-idp${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: form(body),
    redirect: 'manual',
  });
const claims = (jwt) => JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString());

async function login(role, { verifier = randomBytes(32).toString('base64url'), badVerifier } = {}) {
  const challenge = createHash('sha256').update(verifier).digest('base64url');
  const r = await post('/authorize', {
    client_id: 'nf-console',
    redirect_uri: `${base}/`,
    response_type: 'code',
    state: 'st',
    nonce: 'n1',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    role,
  });
  assert.equal(r.status, 302);
  const loc = new URL(r.headers.get('location'));
  assert.equal(loc.searchParams.get('state'), 'st');
  return post('/token', {
    grant_type: 'authorization_code',
    client_id: 'nf-console',
    code: loc.searchParams.get('code'),
    redirect_uri: `${base}/`,
    code_verifier: badVerifier ?? verifier,
  });
}

test('discovery + authorization code with PKCE; tokens verify with the JWKS', async () => {
  const md = await (await fetch(`${base}/mock-idp/.well-known/openid-configuration`)).json();
  assert.equal(md.issuer, `${base}/mock-idp`);
  assert.deepEqual(md.code_challenge_methods_supported, ['S256']);
  const t = await (await login('data-steward')).json();
  const at = claims(t.access_token);
  assert.equal(at.nf_tenant, TENANT);
  assert.deepEqual(at.nf_roles, ['data-steward']);
  assert.ok(at.amr.includes('hwk'));
  assert.equal(claims(t.id_token).nonce, 'n1');
  const { keys } = await (await fetch(`${base}/mock-idp/jwks`)).json();
  const [h, b, s] = t.access_token.split('.');
  const ok = verify(
    'sha256',
    Buffer.from(`${h}.${b}`),
    createPublicKey({ key: keys[0], format: 'jwk' }),
    Buffer.from(s, 'base64url'),
  );
  assert.ok(ok);
  assert.deepEqual(claims((await (await login('scientist')).json()).access_token).amr, ['pwd']);
});

test('a wrong PKCE verifier is refused', async () => {
  const r = await login('viewer', { badVerifier: 'x'.repeat(43) });
  assert.equal(r.status, 400);
});

test('refresh tokens rotate; replaying a rotated one kills the family', async () => {
  const t0 = await (await login('scientist')).json();
  const r1 = await post('/token', {
    grant_type: 'refresh_token',
    client_id: 'nf-console',
    refresh_token: t0.refresh_token,
  });
  assert.equal(r1.status, 200);
  const t1 = await r1.json();
  assert.notEqual(t1.refresh_token, t0.refresh_token);
  const replay = await post('/token', {
    grant_type: 'refresh_token',
    client_id: 'nf-console',
    refresh_token: t0.refresh_token,
  });
  assert.equal(replay.status, 400);
  const after = await post('/token', {
    grant_type: 'refresh_token',
    client_id: 'nf-console',
    refresh_token: t1.refresh_token,
  });
  assert.equal(after.status, 400, 'the newer token of the family is revoked too');
});

test('test mint is off unless enabled', async () => {
  const r = await post('/test/mint', { roles: 'admin' });
  assert.equal(r.status, 404);
});
