// Mock OpenID Provider for local development and the CI-only e2e tests. NEVER deploy it.
// Zero dependencies (node:crypto RS256). Mounted by e2e/serve.mjs under /mock-idp on the console
// origin, so the console's CSP stays connect-src 'self'.
//
// - /.well-known/openid-configuration, /jwks
// - GET /authorize: a plain HTML form (no script, CSP-clean) to pick a role; POST /authorize issues a
//   code bound to the PKCE challenge, nonce and roles, then 302s to redirect_uri?code&state.
// - POST /token: authorization_code (S256 PKCE verified) and refresh_token with rotation and reuse
//   detection (replaying a rotated refresh token revokes the whole family, SEC-015).
// - POST /revoke (RFC 7009).
// - POST /test/mint (only when MOCK_IDP_TEST_MINT=1): an access token for given roles, used by the
//   e2e setup to seed data through the public API.
import { createHash, generateKeyPairSync, randomBytes, sign } from 'node:crypto';

const b64u = (buf) => Buffer.from(buf).toString('base64url');
const sha256b64u = (s) => createHash('sha256').update(s).digest('base64url');
const ADMIN_CLASS = new Set(['owner', 'admin', 'data-steward', 'auditor']);
export const ROLES = ['owner', 'admin', 'data-steward', 'auditor', 'scientist', 'viewer'];

export function createMockIdp({
  issuer,
  clientId = 'nf-console',
  redirectUris,
  audience = 'nf-platform',
  tenant,
  accessTtlS = 300,
  testMint = process.env.MOCK_IDP_TEST_MINT === '1',
}) {
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const kid = b64u(randomBytes(8));
  const jwk = { ...publicKey.export({ format: 'jwk' }), kid, use: 'sig', alg: 'RS256' };
  const codes = new Map(); // code -> {challenge, nonce, roles, redirectUri, exp}
  const refresh = new Map(); // token -> {family, roles, sub, used}
  const revokedFamilies = new Set();

  const jwt = (claims) => {
    const head = b64u(JSON.stringify({ alg: 'RS256', typ: 'JWT', kid }));
    const body = b64u(JSON.stringify(claims));
    const sig = sign('sha256', Buffer.from(`${head}.${body}`), privateKey);
    return `${head}.${body}.${b64u(sig)}`;
  };

  const now = () => Math.floor(Date.now() / 1000);
  const subjectFor = (roles) => `mock-${roles.join('+')}`;

  function tokens({ roles, sub, nonce, family }) {
    const iat = now();
    const rt = b64u(randomBytes(24));
    refresh.set(rt, { family, roles, sub, used: false });
    const out = {
      token_type: 'Bearer',
      expires_in: accessTtlS,
      access_token: jwt({
        iss: issuer,
        aud: audience,
        sub,
        iat,
        exp: iat + accessTtlS,
        nf_tenant: tenant,
        nf_roles: roles,
        // phishing-resistant (RFC 8176 "hwk") for admin-class roles, like a passkey login
        amr: roles.some((r) => ADMIN_CLASS.has(r)) ? ['hwk', 'mfa'] : ['pwd'],
      }),
      refresh_token: rt,
    };
    if (nonce !== undefined)
      out.id_token = jwt({ iss: issuer, aud: clientId, sub, iat, exp: iat + 300, nonce });
    return out;
  }

  const json = (res, status, body) => {
    res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify(body));
  };
  const html = (res, body) => {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
    res.end(body);
  };
  const esc = (s) =>
    String(s).replace(
      /[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
    );
  const readForm = (req) =>
    new Promise((resolve) => {
      let b = '';
      req.on('data', (c) => (b += c));
      req.on('end', () => resolve(new URLSearchParams(b)));
    });

  /** Handles `path` (below the mount point). Returns false when the path is not the IdP's. */
  async function handle(req, res, path) {
    const url = new URL(req.url, 'http://x');
    if (req.method === 'GET' && path === '/.well-known/openid-configuration')
      return json(res, 200, {
        issuer,
        authorization_endpoint: `${issuer}/authorize`,
        token_endpoint: `${issuer}/token`,
        revocation_endpoint: `${issuer}/revoke`,
        jwks_uri: `${issuer}/jwks`,
        response_types_supported: ['code'],
        grant_types_supported: ['authorization_code', 'refresh_token'],
        code_challenge_methods_supported: ['S256'],
        id_token_signing_alg_values_supported: ['RS256'],
        token_endpoint_auth_methods_supported: ['none'],
      });
    if (req.method === 'GET' && path === '/jwks') return json(res, 200, { keys: [jwk] });
    if (path === '/authorize') {
      const q = req.method === 'POST' ? await readForm(req) : url.searchParams;
      if (q.get('client_id') !== clientId) return json(res, 400, { error: 'invalid_client' });
      if (!redirectUris.includes(q.get('redirect_uri')))
        return json(res, 400, { error: 'invalid_request', error_description: 'redirect_uri' });
      if (q.get('code_challenge_method') !== 'S256' || !q.get('code_challenge'))
        return json(res, 400, {
          error: 'invalid_request',
          error_description: 'PKCE S256 required',
        });
      if (req.method === 'GET') {
        const hidden = [...q.entries()]
          .map(([k, v]) => `<input type="hidden" name="${esc(k)}" value="${esc(v)}">`)
          .join('');
        const options = ROLES.map((r) => `<option value="${r}">${r}</option>`).join('');
        return html(
          res,
          `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Mock IdP sign-in</title></head>
<body><main><h1>Mock identity provider (development only)</h1>
<form method="post" action="${esc(issuer)}/authorize">${hidden}
<label for="role">Sign in as</label> <select id="role" name="role">${options}</select>
<button type="submit">Sign in</button></form></main></body></html>`,
        );
      }
      const role = q.get('role');
      if (!ROLES.includes(role)) return json(res, 400, { error: 'access_denied' });
      const code = b64u(randomBytes(24));
      codes.set(code, {
        challenge: q.get('code_challenge'),
        nonce: q.get('nonce') ?? '',
        roles: [role],
        redirectUri: q.get('redirect_uri'),
        exp: now() + 60,
      });
      const back = new URL(q.get('redirect_uri'));
      back.searchParams.set('code', code);
      back.searchParams.set('state', q.get('state') ?? '');
      res.writeHead(302, { location: back.toString(), 'cache-control': 'no-store' });
      return res.end();
    }
    if (req.method === 'POST' && path === '/token') {
      const f = await readForm(req);
      if (f.get('client_id') !== clientId) return json(res, 401, { error: 'invalid_client' });
      if (f.get('grant_type') === 'authorization_code') {
        const c = codes.get(f.get('code') ?? '');
        codes.delete(f.get('code') ?? '');
        if (!c || c.exp < now() || c.redirectUri !== f.get('redirect_uri'))
          return json(res, 400, { error: 'invalid_grant' });
        if (sha256b64u(f.get('code_verifier') ?? '') !== c.challenge)
          return json(res, 400, { error: 'invalid_grant', error_description: 'PKCE' });
        const family = b64u(randomBytes(8));
        return json(
          res,
          200,
          tokens({ roles: c.roles, sub: subjectFor(c.roles), nonce: c.nonce, family }),
        );
      }
      if (f.get('grant_type') === 'refresh_token') {
        const t = refresh.get(f.get('refresh_token') ?? '');
        if (!t || revokedFamilies.has(t.family)) return json(res, 400, { error: 'invalid_grant' });
        if (t.used) {
          revokedFamilies.add(t.family); // reuse detected: the whole family is dead
          return json(res, 400, {
            error: 'invalid_grant',
            error_description: 'refresh token reuse',
          });
        }
        t.used = true;
        return json(res, 200, tokens({ roles: t.roles, sub: t.sub, family: t.family }));
      }
      return json(res, 400, { error: 'unsupported_grant_type' });
    }
    if (req.method === 'POST' && path === '/revoke') {
      const f = await readForm(req);
      const t = refresh.get(f.get('token') ?? '');
      if (t) revokedFamilies.add(t.family);
      res.writeHead(200);
      return res.end();
    }
    if (req.method === 'POST' && path === '/test/mint' && testMint) {
      const f = await readForm(req);
      const roles = (f.get('roles') ?? '').split(',').filter((r) => ROLES.includes(r));
      const t = tokens({ roles, sub: subjectFor(roles), family: b64u(randomBytes(8)) });
      return json(res, 200, { access_token: t.access_token, expires_in: t.expires_in });
    }
    return false;
  }

  return { handle, jwk, issuer };
}
