// Resumable-upload client for POST /v1/datasets/{id}/uploads (2.6): create the session, PUT each part
// to its target, complete with the whole file's SHA-256, then poll until the worker converted it.
import type { ApiClient } from './api/client';
import type { UploadOut } from './api/generated';

export const TERMINAL_UPLOAD_STATES = new Set(['done', 'failed', 'rejected']);

function readBlob(data: Blob): Promise<ArrayBuffer> {
  if (typeof data.arrayBuffer === 'function') return data.arrayBuffer();
  // older engines (and jsdom) without Blob.arrayBuffer
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as ArrayBuffer);
    r.onerror = () => reject(r.error);
    r.readAsArrayBuffer(data);
  });
}

export async function sha256Hex(data: Blob): Promise<string> {
  const buf = await readBlob(data);
  const d = new Uint8Array(await crypto.subtle.digest('SHA-256', buf));
  return [...d].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export interface UploadProgress {
  phase: 'hashing' | 'uploading' | 'completing' | 'processing' | 'done' | 'failed';
  partsDone: number;
  parts: number;
  upload?: UploadOut;
}

export async function uploadFile(
  client: ApiClient,
  opts: { datasetId: string; sessionId: string; file: File; synthetic: boolean; origin: string },
  onProgress: (p: UploadProgress) => void,
  {
    pollMs = 1000,
    maxPolls = 600,
    signal,
  }: { pollMs?: number; maxPolls?: number; signal?: AbortSignal } = {},
): Promise<UploadOut> {
  const { file } = opts;
  onProgress({ phase: 'hashing', partsDone: 0, parts: 0 });
  const sha256 = await sha256Hex(file);
  let up = await client.call('createUpload', {
    path: { dataset_id: opts.datasetId },
    body: {
      session_id: opts.sessionId,
      filename: file.name,
      size_bytes: file.size,
      synthetic: opts.synthetic,
    },
    signal,
  });
  const received = new Set(up.received_parts.map((p) => p.part_number));
  let done = received.size;
  onProgress({ phase: 'uploading', partsDone: done, parts: up.n_parts, upload: up });
  for (const target of up.parts) {
    if (received.has(target.part_number)) continue;
    const start = (target.part_number - 1) * up.part_size;
    await client.putPart(target, file.slice(start, start + up.part_size), opts.origin, signal);
    done += 1;
    onProgress({ phase: 'uploading', partsDone: done, parts: up.n_parts, upload: up });
  }
  onProgress({ phase: 'completing', partsDone: done, parts: up.n_parts, upload: up });
  up = await client.call('completeUpload', {
    path: { upload_id: up.id },
    body: { sha256 },
    signal,
  });
  for (let i = 0; i < maxPolls && !TERMINAL_UPLOAD_STATES.has(up.state); i++) {
    onProgress({ phase: 'processing', partsDone: done, parts: up.n_parts, upload: up });
    await new Promise((r) => setTimeout(r, pollMs));
    up = await client.call('getUpload', { path: { upload_id: up.id }, signal });
  }
  onProgress({
    phase: up.state === 'done' ? 'done' : 'failed',
    partsDone: done,
    parts: up.n_parts,
    upload: up,
  });
  return up;
}
