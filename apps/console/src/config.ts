// Build-time configuration (vite.config.ts injects NF_CONSOLE_* from the environment; see README).
// The same values feed the CSP connect-src in dist/_headers, so a configured issuer or API origin is
// the only non-self origin the console can ever talk to.

export interface ConsoleConfig {
  /** OIDC issuer URL. A path ("/mock-idp") is resolved against the console origin (dev/e2e only). */
  issuer: string;
  clientId: string;
  /** Extra OIDC scopes after "openid". */
  scope: string;
  /** Optional `audience` authorization parameter (IdPs that need it for JWT access tokens). */
  audience: string;
  /** Platform API base URL; "" = same origin as the console. */
  apiBase: string;
}

declare const __NF_CONSOLE_CONFIG__: ConsoleConfig | undefined;

export const DEFAULT_CONFIG: ConsoleConfig = {
  issuer: '/mock-idp',
  clientId: 'nf-console',
  scope: 'openid profile',
  audience: '',
  apiBase: '',
};

export function loadConfig(): ConsoleConfig {
  const injected = typeof __NF_CONSOLE_CONFIG__ === 'undefined' ? undefined : __NF_CONSOLE_CONFIG__;
  return { ...DEFAULT_CONFIG, ...(injected ?? {}) };
}

/** Absolute issuer URL (no trailing slash). */
export function resolveIssuer(issuer: string, origin: string): string {
  return new URL(issuer, origin).toString().replace(/\/+$/, '');
}

/** True when the console runs against the built-in development IdP (shown as a banner). */
export const isDevIdp = (c: ConsoleConfig): boolean => c.issuer.startsWith('/');
