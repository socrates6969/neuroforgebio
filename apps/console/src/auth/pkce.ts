// PKCE (RFC 7636, S256 only) and random values from the Web Crypto API.

export function base64url(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function randomString(byteLength = 32): string {
  const b = new Uint8Array(byteLength);
  crypto.getRandomValues(b);
  return base64url(b);
}

/** 43-char verifier from 32 random bytes (RFC 7636 §4.1: 43..128 chars of [A-Za-z0-9-._~]). */
export const createVerifier = (): string => randomString(32);

export async function challengeS256(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(digest));
}

/** Decode a JWT payload WITHOUT verifying it (the API verifies tokens; the SPA only reads claims). */
export function decodeJwtPayload(jwt: string): Record<string, unknown> {
  const part = jwt.split('.')[1];
  if (!part) throw new Error('malformed JWT');
  const b64 = part.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
}
