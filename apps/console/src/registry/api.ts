// Registry calls used by the model pages, over the generated operation table. The server
// authorizes every call (policy.check, tenant isolation, the deployment-context rules); nothing
// here decides anything.
import { ApiError, type ApiClient } from '../api/client';
import type { LineageGraph } from '../api/types';
import type { ContextIn, DeploymentOut } from './types';

export const PAGE = 50;

export function listModels(client: ApiClient, offset: number, signal?: AbortSignal) {
  return client.call('listModels', { query: { limit: PAGE, offset }, signal });
}

export function getModel(client: ApiClient, id: string, signal?: AbortSignal) {
  return client.call('getModel', { path: { model_id: id }, signal });
}

export function getVersion(client: ApiClient, id: string, version: number, signal?: AbortSignal) {
  return client.call('getVersion', { path: { model_id: id, version }, signal });
}

/** Lineage of the version's model node. The generated type leaves nodes/edges untyped; they are
 * the provenance node/edge shapes of src/api/types.ts (same serializer as /v1/provenance). */
export async function getVersionLineage(
  client: ApiClient,
  id: string,
  version: number,
  signal?: AbortSignal,
): Promise<LineageGraph & { n_training_subjects: number }> {
  const g = await client.call('getVersionLineage', { path: { model_id: id, version }, signal });
  return g as unknown as LineageGraph & { n_training_subjects: number };
}

export function listDeployments(client: ApiClient, id: string, signal?: AbortSignal) {
  return client.call('listDeployments', {
    path: { model_id: id },
    query: { limit: 200 },
    signal,
  });
}

export function getVocabulary(client: ApiClient, signal?: AbortSignal) {
  return client.call('getVocabulary', { signal });
}

export type DeploymentOutcome =
  | { kind: 'approved'; deployment: DeploymentOut }
  | { kind: 'refused'; code: string; reasons: string[]; deploymentId: string | null };

/**
 * Request a deployment of `version` with the declared context. The platform stores and audits a
 * refusal, then answers 403 problem+json `deployment-refused` with a machine `code`, `reasons` and
 * the stored `deployment_id`; that becomes `refused`. Anything else (a plain 403 authz denial,
 * 404, validation, network) is thrown for the error box.
 */
export async function requestDeployment(
  client: ApiClient,
  id: string,
  version: number,
  context: ContextIn,
): Promise<DeploymentOutcome> {
  try {
    const d = await client.call('requestDeployment', {
      path: { model_id: id },
      body: { version, context },
    });
    if (d.state === 'refused')
      return {
        kind: 'refused',
        code: d.reasons[0] ?? 'refused',
        reasons: d.reasons,
        deploymentId: d.id,
      };
    return { kind: 'approved', deployment: d };
  } catch (e) {
    const r = refusalFromError(e);
    if (r) return { kind: 'refused', ...r };
    throw e;
  }
}

/** A deployment refusal (not an authz denial): a problem with a machine code and reasons. */
export function refusalFromError(
  e: unknown,
): { code: string; reasons: string[]; deploymentId: string | null } | null {
  if (!(e instanceof ApiError)) return null;
  const p = e.problem;
  const code = typeof p.code === 'string' ? p.code : null;
  if (!code || !Array.isArray(p.reasons)) return null;
  return {
    code,
    reasons: p.reasons.map(String),
    deploymentId: typeof p.deployment_id === 'string' ? p.deployment_id : null,
  };
}
