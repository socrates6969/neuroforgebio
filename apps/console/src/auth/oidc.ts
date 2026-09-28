// OIDC Authorization Code + PKCE for a public SPA client, with SEC-015 session rules as far as a
// browser app can enforce them. See README.md "Sessions" for what is (and is not) enforced here.
//
// - Tokens live ONLY in this object's memory: never localStorage, sessionStorage, IndexedDB or
//   cookies. A reload ends the session (the IdP's own SSO session makes re-login one click).
// - Login runs in a popup so the PKCE verifier, state and nonce never leave memory either: the
//   popup lands on the console origin with ?code&state, posts them on a same-origin
//   BroadcastChannel and closes. BroadcastChannel (not window.opener) because COOP same-origin
//   severs the opener link once the popup visits the IdP.
// - Access tokens are used for at most ACCESS_MAX_S (15 min) whatever the IdP says, then refreshed;
//   every refresh must return a NEW refresh token (rotation). Reuse detection is the IdP's job
//   (replaying a rotated token must revoke the family); the SPA never keeps an old one.
// - Idle logoff after IDLE_S (15 min without user input); absolute lifetime ABSOLUTE_S (12 h).

import { challengeS256, createVerifier, decodeJwtPayload, randomString } from './pkce';

export const ACCESS_MAX_S = 15 * 60;
export const IDLE_S = 15 * 60;
export const ABSOLUTE_S = 12 * 60 * 60;
/** Refresh this many seconds before the access token's (clamped) expiry. */
export const REFRESH_SKEW_S = 60;
export const LOGIN_TIMEOUT_MS = 5 * 60 * 1000;
export const CALLBACK_CHANNEL = 'nf-console-oidc';

export interface ProviderMetadata {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  revocation_endpoint?: string;
  end_session_endpoint?: string;
  code_challenge_methods_supported?: string[];
}

export interface TokenSet {
  accessToken: string;
  refreshToken: string | null;
  idToken: string | null;
  /** epoch ms after which the console no longer uses the access token */
  expiresAt: number;
}

export type SessionState =
  | { status: 'signed-out'; reason?: 'logout' | 'idle' | 'absolute' | 'refresh-failed' }
  | { status: 'signing-in' }
  | { status: 'signed-in'; subject: string; loginAt: number };

export interface Channel {
  postMessage(msg: unknown): void;
  close(): void;
  onmessage: ((ev: { data: unknown }) => void) | null;
}

export interface OidcDeps {
  fetch: typeof fetch;
  now: () => number;
  /** Opens the IdP authorization URL (a popup in the browser). */
  openLogin: (url: string) => void;
  channel: (name: string) => Channel;
  origin: string;
}

export interface OidcOptions {
  issuer: string;
  clientId: string;
  redirectUri: string;
  scope: string;
  audience?: string;
}

export class AuthError extends Error {}

const LOOPBACK = new Set(['localhost', '127.0.0.1', '[::1]']);

/** https everywhere except loopback (dev/e2e); endpoints must stay on the issuer's origin. */
export function checkEndpoint(url: string, issuer: string): string {
  const u = new URL(url);
  const iss = new URL(issuer);
  if (u.protocol !== 'https:' && !(u.protocol === 'http:' && LOOPBACK.has(u.hostname)))
    throw new AuthError(`insecure IdP endpoint: ${url}`);
  if (u.origin !== iss.origin) throw new AuthError(`IdP endpoint off the issuer origin: ${url}`);
  return u.toString();
}

export function validateMetadata(m: unknown, issuer: string): ProviderMetadata {
  const md = m as Partial<ProviderMetadata> | null;
  if (!md || typeof md !== 'object') throw new AuthError('bad discovery document');
  if (md.issuer !== issuer) throw new AuthError('discovery issuer mismatch');
  if (!md.authorization_endpoint || !md.token_endpoint) throw new AuthError('discovery incomplete');
  if (md.code_challenge_methods_supported && !md.code_challenge_methods_supported.includes('S256'))
    throw new AuthError('IdP does not support PKCE S256');
  return {
    issuer,
    authorization_endpoint: checkEndpoint(md.authorization_endpoint, issuer),
    token_endpoint: checkEndpoint(md.token_endpoint, issuer),
    revocation_endpoint: md.revocation_endpoint
      ? checkEndpoint(md.revocation_endpoint, issuer)
      : undefined,
    end_session_endpoint: md.end_session_endpoint
      ? checkEndpoint(md.end_session_endpoint, issuer)
      : undefined,
  };
}

interface Pending {
  state: string;
  nonce: string;
  verifier: string;
  resolve: (search: string) => void;
  reject: (e: Error) => void;
}

export class OidcSession {
  private metadata: ProviderMetadata | null = null;
  private tokens: TokenSet | null = null;
  private loginAt = 0;
  private lastActivity = 0;
  private subject = '';
  private refreshing: Promise<TokenSet> | null = null;
  private pending: Pending | null = null;
  private listeners = new Set<(s: SessionState) => void>();
  private state: SessionState = { status: 'signed-out' };

  constructor(
    readonly opts: OidcOptions,
    private readonly deps: OidcDeps,
  ) {}

  getState(): SessionState {
    return this.state;
  }

  subscribe(fn: (s: SessionState) => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private set(s: SessionState): void {
    this.state = s;
    for (const fn of this.listeners) fn(s);
  }

  async discover(): Promise<ProviderMetadata> {
    if (this.metadata) return this.metadata;
    const r = await this.deps.fetch(`${this.opts.issuer}/.well-known/openid-configuration`, {
      credentials: 'omit',
      cache: 'no-store',
    });
    if (!r.ok) throw new AuthError(`discovery failed (${r.status})`);
    this.metadata = validateMetadata(await r.json(), this.opts.issuer);
    return this.metadata;
  }

  /** Starts the popup login and resolves once tokens are in memory. */
  async login(): Promise<void> {
    if (this.pending) this.pending.reject(new AuthError('superseded by a new login'));
    this.set({ status: 'signing-in' });
    try {
      const md = await this.discover();
      const verifier = createVerifier();
      const state = randomString(16);
      const nonce = randomString(16);
      const q = new URLSearchParams({
        response_type: 'code',
        client_id: this.opts.clientId,
        redirect_uri: this.opts.redirectUri,
        scope: this.opts.scope,
        state,
        nonce,
        code_challenge: await challengeS256(verifier),
        code_challenge_method: 'S256',
      });
      if (this.opts.audience) q.set('audience', this.opts.audience);
      const search = await this.awaitCallback({ state, nonce, verifier }, () =>
        this.deps.openLogin(`${md.authorization_endpoint}?${q}`),
      );
      const params = new URLSearchParams(search);
      if (params.get('error')) throw new AuthError(`IdP error: ${params.get('error')}`);
      const code = params.get('code');
      if (!code) throw new AuthError('callback without code');
      const tokens = await this.tokenRequest(md, {
        grant_type: 'authorization_code',
        code,
        redirect_uri: this.opts.redirectUri,
        client_id: this.opts.clientId,
        code_verifier: verifier,
      });
      const sub = this.checkIdToken(tokens.idToken, nonce);
      const now = this.deps.now();
      this.tokens = tokens;
      this.loginAt = now;
      this.lastActivity = now;
      this.subject = sub;
      this.set({ status: 'signed-in', subject: sub, loginAt: now });
    } catch (e) {
      this.clear();
      this.set({ status: 'signed-out' });
      throw e;
    }
  }

  private awaitCallback(p: Omit<Pending, 'resolve' | 'reject'>, open: () => void): Promise<string> {
    const ch = this.deps.channel(CALLBACK_CHANNEL);
    return new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => done(new AuthError('login timed out')), LOGIN_TIMEOUT_MS);
      const done = (err: Error | null, search?: string) => {
        clearTimeout(timer);
        ch.close();
        this.pending = null;
        if (err) reject(err);
        else resolve(search as string);
      };
      this.pending = {
        ...p,
        resolve: (s) => done(null, s),
        reject: (e) => done(e),
      };
      ch.onmessage = (ev) => {
        const msg = ev.data as { type?: string; search?: string } | null;
        if (!msg || msg.type !== 'oidc-callback' || typeof msg.search !== 'string') return;
        const state = new URLSearchParams(msg.search).get('state');
        // A callback for another login attempt (or a forged one) is ignored, not accepted.
        if (!this.pending || state !== this.pending.state) return;
        this.pending.resolve(msg.search);
      };
      open();
    });
  }

  private async tokenRequest(
    md: ProviderMetadata,
    form: Record<string, string>,
  ): Promise<TokenSet> {
    const r = await this.deps.fetch(md.token_endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(form).toString(),
      credentials: 'omit',
      cache: 'no-store',
    });
    if (!r.ok) throw new AuthError(`token endpoint returned ${r.status}`);
    const t = (await r.json()) as Record<string, unknown>;
    if (typeof t.access_token !== 'string' || !t.access_token)
      throw new AuthError('no access token');
    if (typeof t.token_type !== 'string' || t.token_type.toLowerCase() !== 'bearer')
      throw new AuthError('token_type must be Bearer');
    const lifetime = typeof t.expires_in === 'number' && t.expires_in > 0 ? t.expires_in : 0;
    // SEC-015: never use an access token longer than 15 min, even if the IdP allows it.
    const useFor = Math.min(lifetime || ACCESS_MAX_S, ACCESS_MAX_S);
    return {
      accessToken: t.access_token,
      refreshToken: typeof t.refresh_token === 'string' ? t.refresh_token : null,
      idToken: typeof t.id_token === 'string' ? t.id_token : null,
      expiresAt: this.deps.now() + useFor * 1000,
    };
  }

  private checkIdToken(idToken: string | null, nonce: string): string {
    if (!idToken) throw new AuthError('no id_token');
    const c = decodeJwtPayload(idToken);
    if (c.iss !== this.opts.issuer) throw new AuthError('id_token issuer mismatch');
    const aud = Array.isArray(c.aud) ? c.aud : [c.aud];
    if (!aud.includes(this.opts.clientId)) throw new AuthError('id_token audience mismatch');
    if (c.nonce !== nonce) throw new AuthError('id_token nonce mismatch');
    if (typeof c.sub !== 'string' || !c.sub) throw new AuthError('id_token without sub');
    return c.sub;
  }

  /** Record user activity (keyboard/pointer); resets the idle timer. */
  touch(): void {
    if (this.tokens) this.lastActivity = this.deps.now();
  }

  /** Enforce idle/absolute limits; returns false (and signs out) when the session ended. */
  check(): boolean {
    if (!this.tokens) return false;
    const now = this.deps.now();
    if (now - this.loginAt >= ABSOLUTE_S * 1000) {
      void this.logout('absolute');
      return false;
    }
    if (now - this.lastActivity >= IDLE_S * 1000) {
      void this.logout('idle');
      return false;
    }
    return true;
  }

  /** A usable access token, refreshing (single-flight) shortly before the 15-min limit. */
  async accessToken(): Promise<string> {
    if (!this.check() || !this.tokens) throw new AuthError('not signed in');
    if (this.deps.now() < this.tokens.expiresAt - REFRESH_SKEW_S * 1000)
      return this.tokens.accessToken;
    return (await this.refresh()).accessToken;
  }

  refresh(): Promise<TokenSet> {
    if (this.refreshing) return this.refreshing;
    const current = this.tokens;
    this.refreshing = (async () => {
      try {
        if (!current?.refreshToken) throw new AuthError('no refresh token');
        const md = await this.discover();
        const next = await this.tokenRequest(md, {
          grant_type: 'refresh_token',
          refresh_token: current.refreshToken,
          client_id: this.opts.clientId,
        });
        // Rotation is mandatory: an IdP that hands back the same (or no) refresh token is not
        // configured for SEC-015; end the session instead of silently keeping a long-lived token.
        if (!next.refreshToken || next.refreshToken === current.refreshToken)
          throw new AuthError('refresh token was not rotated');
        if (this.tokens !== current) throw new AuthError('session changed during refresh');
        this.tokens = { ...next, idToken: next.idToken ?? current.idToken };
        return this.tokens;
      } catch (e) {
        if (this.tokens === current) await this.logout('refresh-failed');
        throw e;
      } finally {
        this.refreshing = null;
      }
    })();
    return this.refreshing;
  }

  private clear(): void {
    this.tokens = null;
    this.loginAt = 0;
    this.lastActivity = 0;
    this.subject = '';
  }

  /** Forget tokens; best-effort RFC 7009 revocation of the refresh token. */
  async logout(reason: 'logout' | 'idle' | 'absolute' | 'refresh-failed' = 'logout') {
    const t = this.tokens;
    this.clear();
    this.set({ status: 'signed-out', reason });
    const md = this.metadata;
    if (t?.refreshToken && md?.revocation_endpoint) {
      try {
        await this.deps.fetch(md.revocation_endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            token: t.refreshToken,
            token_type_hint: 'refresh_token',
            client_id: this.opts.clientId,
          }).toString(),
          credentials: 'omit',
          cache: 'no-store',
        });
      } catch {
        // revocation is best effort; the refresh token expires at the IdP anyway
      }
    }
  }

  /** For tests and diagnostics only: whether any token is held. */
  hasTokens(): boolean {
    return this.tokens !== null;
  }

  currentSubject(): string {
    return this.subject;
  }
}

/**
 * In the login popup: if this page load is an OIDC callback, hand ?code&state (or ?error) to the
 * main window over the same-origin channel and report true (the caller then closes the popup).
 */
export function relayCallback(search: string, channel: (name: string) => Channel): boolean {
  const p = new URLSearchParams(search);
  if (!p.get('state') || !(p.get('code') || p.get('error'))) return false;
  const ch = channel(CALLBACK_CHANNEL);
  ch.postMessage({ type: 'oidc-callback', search });
  ch.close();
  return true;
}
