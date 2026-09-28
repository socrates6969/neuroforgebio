// Role-based UI hiding that mirrors the server's authz matrix (nf_platform.auth.authorize).
// src/api/authz.json is GENERATED from the Python module by scripts/gen-api.mjs; the drift test
// fails when the matrix changes and the console is not regenerated.
//
// THIS IS NOT ENFORCEMENT. The platform authorizes every request (deny by default, tenant check,
// RLS in Postgres). Hiding a control only avoids offering an action that would get a 403; a user who
// calls the API directly gets exactly the server's answer. Never skip a server check because the UI
// hid something, and never show data just because the UI "allowed" it.
import matrix from '../api/authz.json';

export type Action = keyof typeof matrix.permissions;

export const ROLES: readonly string[] = matrix.roles;
export const ADMIN_CLASS: ReadonlySet<string> = new Set(matrix.adminClass);
export const QUARANTINE_READERS: ReadonlySet<string> = new Set(matrix.quarantineReaders);

const PERMS = matrix.permissions as Record<string, string[]>;

/**
 * Whether any of `roles` may perform `action`. Pass the EFFECTIVE roles from GET /v1/whoami (the
 * server already drops admin-class roles without a phishing-resistant login).
 */
export function can(roles: readonly string[], action: string): boolean {
  const allowed = PERMS[action];
  if (!allowed) return false; // unknown action: deny, like the server
  return roles.some((r) => allowed.includes(r));
}

export function canReadQuarantined(roles: readonly string[]): boolean {
  return roles.some((r) => QUARANTINE_READERS.has(r));
}

/** Every action the given roles may perform (for the account panel). */
export function allowedActions(roles: readonly string[]): string[] {
  return Object.keys(PERMS).filter((a) => can(roles, a));
}
