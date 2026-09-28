export interface ConsoleBuildConfig {
  issuer: string;
  clientId: string;
  scope: string;
  audience: string;
  apiBase: string;
}
export const STAGES: string[];
export function consoleConfig(env?: Record<string, string | undefined>): ConsoleBuildConfig;
export function connectOrigins(config: ConsoleBuildConfig): string[];
export function resolveStage(value?: string): string;
export function hsts(stage?: string): string;
export function csp(opts?: { connect?: string[] }): string;
export const PERMISSIONS_POLICY: string;
export function globalHeaders(opts?: {
  stage?: string;
  connect?: string[];
}): Record<string, string>;
export const CACHE_IMMUTABLE: string;
export const CACHE_HTML: string;
export const HASHED_ASSET_PREFIX: string;
export function renderHeadersFile(opts: { stage?: string; connect: string[] }): string;
export function parseCsp(value: string): Map<string, string[]>;
export function assertCspSafe(value: string, opts?: { allowedOrigins?: string[] }): void;
