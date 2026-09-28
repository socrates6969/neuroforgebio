import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ABSOLUTE_S,
  ACCESS_MAX_S,
  AuthError,
  CALLBACK_CHANNEL,
  IDLE_S,
  OidcSession,
  checkEndpoint,
  relayCallback,
  validateMetadata,
  type Channel,
} from './oidc';
import { base64url, challengeS256 } from './pkce';

const ISSUER = 'https://idp.example.test';
const CLIENT = 'nf-console';
const REDIRECT = 'https://console.example.test/';

const b64json = (o: unknown) => base64url(new TextEncoder().encode(JSON.stringify(o)));
const jwt = (claims: Record<string, unknown>) =>
  `${b64json({ alg: 'none' })}.${b64json(claims)}.sig`;

/** In-memory channel bus (BroadcastChannel stand-in). */
function bus() {
  const chans = new Set<Channel & { name: string }>();
  const make = (name: string) => {
    const ch: Channel & { name: string } = {
      name,
      onmessage: null,
      postMessage(msg: unknown) {
        for (const c of chans) if (c !== ch && c.name === name) c.onmessage?.({ data: msg });
      },
      close() {
        chans.delete(ch);
      },
    };
    chans.add(ch);
    return ch;
  };
  return { make, open: () => chans.size };
}

/** A mock IdP: discovery, authorize (via openLogin), token (PKCE + rotation), revocation. */
function mockIdp(opts: { expiresIn?: number; rotate?: boolean; nonceOverride?: string } = {}) {
  const codes = new Map<string, { challenge: string; nonce: string }>();
  const refresh = new Set<string>();
  const revoked: string[] = [];
  let n = 0;
  const b = bus();
  const tokenResponse = (nonce?: string) => {
    n += 1;
    const rt = `rt-${n}`;
    refresh.add(rt);
    return {
      access_token: `at-${n}`,
      token_type: 'Bearer',
      expires_in: opts.expiresIn ?? 3600,
      refresh_token: opts.rotate === false && n > 1 ? 'rt-1' : rt,
      id_token: jwt({
        iss: ISSUER,
        aud: CLIENT,
        sub: 'user-1',
        nonce: opts.nonceOverride ?? nonce,
      }),
    };
  };
  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === `${ISSUER}/.well-known/openid-configuration`)
      return Response.json({
        issuer: ISSUER,
        authorization_endpoint: `${ISSUER}/authorize`,
        token_endpoint: `${ISSUER}/token`,
        revocation_endpoint: `${ISSUER}/revoke`,
        code_challenge_methods_supported: ['S256'],
      });
    const form = new URLSearchParams(String(init?.body ?? ''));
    if (url === `${ISSUER}/token`) {
      if (form.get('grant_type') === 'authorization_code') {
        const c = codes.get(form.get('code') ?? '');
        if (!c) return new Response('{}', { status: 400 });
        const ok = (await challengeS256(form.get('code_verifier') ?? '')) === c.challenge;
        if (!ok) return new Response('{}', { status: 400 });
        codes.delete(form.get('code')!);
        return Response.json(tokenResponse(c.nonce));
      }
      if (form.get('grant_type') === 'refresh_token') {
        const rt = form.get('refresh_token') ?? '';
        if (!refresh.has(rt)) return new Response('{}', { status: 400 });
        if (opts.rotate !== false) refresh.delete(rt);
        return Response.json(tokenResponse());
      }
    }
    if (url === `${ISSUER}/revoke`) {
      revoked.push(form.get('token') ?? '');
      return new Response(null, { status: 200 });
    }
    return new Response('{}', { status: 404 });
  });
  /** Simulates the popup: IdP authenticates and redirects; the popup page relays the callback. */
  const openLogin = (url: string, tamper?: (q: URLSearchParams) => void) => {
    const q = new URL(url).searchParams;
    expect(q.get('code_challenge_method')).toBe('S256');
    expect(q.get('redirect_uri')).toBe(REDIRECT);
    const code = `code-${q.get('state')}`;
    codes.set(code, { challenge: q.get('code_challenge')!, nonce: q.get('nonce')! });
    const back = new URLSearchParams({ code, state: q.get('state')! });
    tamper?.(back);
    queueMicrotask(() => relayCallback(`?${back}`, b.make));
  };
  return { fetchImpl, openLogin, bus: b, revoked };
}

let now = 1_000_000;
beforeEach(() => {
  now = 1_000_000;
});
afterEach(() => vi.restoreAllMocks());

function session(idp: ReturnType<typeof mockIdp>, open?: (url: string) => void) {
  return new OidcSession(
    { issuer: ISSUER, clientId: CLIENT, redirectUri: REDIRECT, scope: 'openid profile' },
    {
      fetch: idp.fetchImpl as unknown as typeof fetch,
      now: () => now,
      openLogin: open ?? ((u) => idp.openLogin(u)),
      channel: idp.bus.make,
      origin: 'https://console.example.test',
    },
  );
}

describe('OIDC Authorization Code + PKCE', () => {
  it('logs in through the popup relay and keeps tokens in memory only', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const cookie = vi.spyOn(document, 'cookie', 'set');
    const idp = mockIdp();
    const s = session(idp);
    const states: string[] = [];
    s.subscribe((st) => states.push(st.status));
    await s.login();
    expect(s.getState()).toMatchObject({ status: 'signed-in', subject: 'user-1' });
    expect(states).toEqual(['signing-in', 'signed-in']);
    expect(await s.accessToken()).toBe('at-1');
    expect(setItem).not.toHaveBeenCalled();
    expect(cookie).not.toHaveBeenCalled();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(idp.bus.open()).toBe(0); // callback channel closed after use
  });

  it('ignores a callback with a foreign state and rejects a wrong nonce', async () => {
    const idp = mockIdp();
    let forgedFirst = false;
    const s = session(idp, (u) => {
      // a forged callback (other state) arrives first and must be ignored; then the real one
      const b = idp.bus.make;
      queueMicrotask(() => {
        forgedFirst = relayCallback('?code=forged-code&state=forged', b);
      });
      idp.openLogin(u);
    });
    await s.login();
    expect(forgedFirst).toBe(true);
    expect(await s.accessToken()).toBe('at-1');
    const idp2 = mockIdp({ nonceOverride: 'other' });
    await expect(session(idp2).login()).rejects.toThrow(/nonce/);
    expect(idp2.bus.open()).toBe(0);
  });

  it('never uses an access token for more than 15 minutes and rotates the refresh token', async () => {
    const idp = mockIdp({ expiresIn: 3600 });
    const s = session(idp);
    await s.login();
    now += (ACCESS_MAX_S - 120) * 1000;
    s.touch();
    expect(await s.accessToken()).toBe('at-1');
    now += 90 * 1000; // inside the 60 s refresh skew of the 15-min cap
    s.touch();
    expect(await s.accessToken()).toBe('at-2');
    const bodies = idp.fetchImpl.mock.calls
      .map((c) => new URLSearchParams(String((c[1] as RequestInit | undefined)?.body ?? '')))
      .filter((f) => f.get('grant_type') === 'refresh_token');
    expect(bodies.map((f) => f.get('refresh_token'))).toEqual(['rt-1']);
  });

  it('signs out when the IdP does not rotate the refresh token', async () => {
    const idp = mockIdp({ rotate: false, expiresIn: 60 });
    const s = session(idp);
    await s.login();
    now += 30 * 1000;
    s.touch();
    await expect(s.accessToken()).rejects.toThrow(/rotated/);
    expect(s.getState()).toEqual({ status: 'signed-out', reason: 'refresh-failed' });
  });

  it('logs off after 15 minutes idle', async () => {
    const idp = mockIdp();
    const s = session(idp);
    await s.login();
    now += (IDLE_S - 1) * 1000;
    expect(s.check()).toBe(true);
    now += 2000;
    expect(s.check()).toBe(false);
    expect(s.getState()).toEqual({ status: 'signed-out', reason: 'idle' });
    await expect(s.accessToken()).rejects.toThrow(AuthError);
  });

  it('ends the session after 12 hours even with activity', async () => {
    const idp = mockIdp({ expiresIn: 600 });
    const s = session(idp);
    await s.login();
    for (let t = 0; t < ABSOLUTE_S; t += 600) {
      now += 600 * 1000;
      s.touch();
      if (!s.check()) break;
      await s.accessToken();
    }
    expect(s.getState()).toEqual({ status: 'signed-out', reason: 'absolute' });
  });

  it('revokes the refresh token on logout and forgets everything', async () => {
    const idp = mockIdp();
    const s = session(idp);
    await s.login();
    await s.logout();
    expect(idp.revoked).toEqual(['rt-1']);
    expect(s.hasTokens()).toBe(false);
    expect(s.currentSubject()).toBe('');
  });
});

describe('discovery validation', () => {
  it('rejects issuer mismatch, missing S256, http and off-origin endpoints', () => {
    const base = {
      issuer: ISSUER,
      authorization_endpoint: `${ISSUER}/a`,
      token_endpoint: `${ISSUER}/t`,
    };
    expect(validateMetadata(base, ISSUER).token_endpoint).toBe(`${ISSUER}/t`);
    expect(() => validateMetadata({ ...base, issuer: 'https://evil.test' }, ISSUER)).toThrow(
      /issuer/,
    );
    expect(() =>
      validateMetadata({ ...base, code_challenge_methods_supported: ['plain'] }, ISSUER),
    ).toThrow(/S256/);
    expect(() => checkEndpoint('http://idp.example.test/t', ISSUER)).toThrow(/insecure/);
    expect(() => checkEndpoint('https://other.test/t', ISSUER)).toThrow(/off the issuer/);
    expect(
      checkEndpoint('http://127.0.0.1:4173/mock-idp/t', 'http://127.0.0.1:4173/mock-idp'),
    ).toBe('http://127.0.0.1:4173/mock-idp/t');
  });
});

describe('relayCallback', () => {
  it('relays only real callbacks', () => {
    const b = bus();
    const got: unknown[] = [];
    const listener = b.make(CALLBACK_CHANNEL);
    listener.onmessage = (e) => got.push(e.data);
    expect(relayCallback('', b.make)).toBe(false);
    expect(relayCallback('?code=x', b.make)).toBe(false);
    expect(relayCallback('?code=x&state=s', b.make)).toBe(true);
    expect(got).toEqual([{ type: 'oidc-callback', search: '?code=x&state=s' }]);
  });
});
