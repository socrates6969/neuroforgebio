// Typed registry fixtures for component tests (synthetic IDs, numbers and text; not real models).
import type { LineageGraph } from '../api/types';
import type {
  DeploymentOut,
  ModelCard,
  ModelDetailOut,
  ModelOut,
  VersionOut,
  VersionSummary,
  VocabularyOut,
} from '../registry/types';
import { uuid } from './helpers';

export const MODEL_ID = uuid(700);
export const CLEAN_MODEL_ID = uuid(701);
export const V1_ID = uuid(710);
export const V2_ID = uuid(711);
export const VERSION_NODE = uuid(720);
export const RECORDING_NODE = uuid(721);
export const TRAIN_ACTIVITY = uuid(722);
export const DELETION_JOB = uuid(730);

const m = (metric: string, value: number, method: string) => ({
  metric,
  value,
  method,
  split: 'test',
});

export const card: ModelCard = {
  card_schema: 'nf.model-card/v1',
  summary: 'Toy decoder trained on synthetic motor-imagery EEG.',
  task: 'decoding',
  inferences: ['motor_intent'],
  modalities: ['eeg'],
  limitations: 'Synthetic data only.\nNot validated on real recordings.',
  evaluation: [m('accuracy', 0.71, 'held-out subjects')],
  robustness: {
    noise: m('accuracy', 0.66, 'additive gaussian noise, SNR 10 dB'),
    channel_dropout: m('accuracy', 0.6, '20% channels dropped'),
    adversarial: m('accuracy', 0.41, 'FGSM, eps 0.01'),
  },
  privacy_risk: null,
  contact: null,
};

export const versions: VersionSummary[] = [
  {
    id: V1_ID,
    version: 1,
    visibility: 'private',
    weights_source: 'platform',
    created_at: '2026-09-20T09:00:00Z',
    retrain_required: false,
    deployments_blocked: false,
  },
  {
    id: V2_ID,
    version: 2,
    visibility: 'private',
    weights_source: 'platform',
    created_at: '2026-09-22T09:00:00Z',
    retrain_required: true,
    deployments_blocked: true,
  },
];

const base = (name: string, id: string): ModelOut => ({
  id,
  name,
  card,
  card_sha256: 'c'.repeat(64),
  created_by: 'user:scientist',
  created_at: '2026-09-20T09:00:00Z',
  latest_version: versions[1]!,
  retrain_required: true,
});

export const models: ModelOut[] = [
  base('motor-imagery-decoder', MODEL_ID),
  {
    ...base('sleep-stager', CLEAN_MODEL_ID),
    card: { ...card, task: 'classification' },
    latest_version: versions[0]!,
    retrain_required: false,
  },
];

export const modelDetail: ModelDetailOut = { ...models[0]!, versions };

export const taintedVersion: VersionOut = {
  id: V2_ID,
  model_id: MODEL_ID,
  version: 2,
  derived_object_id: uuid(750),
  weights_source: 'platform',
  weights_format: 'safetensors',
  weights_sha256: 'e'.repeat(64),
  prov_node_id: VERSION_NODE,
  manifest_sha256: 'd'.repeat(64),
  manifest_summary: {
    schema_id: 'nf.training-manifest.v1',
    n_subjects: 12,
    n_source_recordings: 24,
    n_inputs: 24,
    n_excluded_subjects: 0,
    n_shards: 4,
    recipe: 'sisa',
  },
  manifest: null,
  pipeline_version_ids: ['pv:sha256:' + 'a'.repeat(64)],
  code_commit: 'f'.repeat(40),
  intended_use:
    'Offline research analysis of motor-imagery EEG. Not intended for real-time or safety-critical control.',
  use_restrictions: ['no_realtime_control', 'research_only'],
  recipe: 'sisa',
  parent_version_id: V1_ID,
  parent_version: 1,
  visibility: 'private',
  published_at: null,
  created_by: 'user:scientist',
  created_at: '2026-09-22T09:00:00Z',
  retrain_required: true,
  deployments_blocked: true,
  taint: [
    {
      deletion_job_id: DELETION_JOB,
      created_at: '2026-09-25T12:00:00Z',
      block_deployments: true,
      reason: 'a training subject withdrew consent',
    },
  ],
};

/** AppSec M3: an uploaded-weights version flagged by an unrelated withdrawal. */
export const uploadedVersion: VersionOut = {
  ...taintedVersion,
  weights_source: 'upload',
  taint: [
    {
      deletion_job_id: DELETION_JOB,
      created_at: '2026-09-25T12:00:00Z',
      block_deployments: true,
      reason: 'unverifiable lineage (uploaded weights)',
    },
  ],
};

export const cleanVersion: VersionOut = {
  ...taintedVersion,
  id: V1_ID,
  version: 1,
  parent_version_id: null,
  parent_version: null,
  retrain_required: false,
  deployments_blocked: false,
  taint: [],
};

const dep = (over: Partial<DeploymentOut>): DeploymentOut => ({
  id: uuid(740),
  model_id: MODEL_ID,
  version_id: V2_ID,
  version: 2,
  jurisdiction: 'DE',
  setting: 'research',
  purpose: 'offline motor-imagery research',
  context: { outputs: 'labels', influences_behaviour: false },
  exception_id: null,
  state: 'approved',
  effective_state: 'approved',
  reasons: [],
  requested_by: 'user:scientist',
  created_at: '2026-09-24T13:00:00Z',
  ...over,
});

/** approved before the withdrawal, blocked now (retrain_required) */
export const blockedDeployment = dep({ effective_state: 'blocked' });

export const refusedDeployment = dep({
  id: uuid(741),
  jurisdiction: 'EU',
  setting: 'workplace',
  purpose: 'staff stress monitoring',
  state: 'refused',
  effective_state: 'refused',
  reasons: ['eu_ai_act_5_1_f'],
  created_at: '2026-09-25T13:00:00Z',
});

export const approvedDeployment = dep({ id: uuid(742), version_id: V1_ID, version: 1 });

export const vocabulary: VocabularyOut = {
  restrictions: [],
  settings: [
    'clinical_care',
    'clinical_research',
    'consumer_wellness',
    'education',
    'other',
    'research',
    'safety_monitoring',
    'workplace',
  ],
  outputs: ['labels', 'coarse_scores', 'logits', 'embeddings'],
  allowed_outputs: ['coarse_scores', 'labels'],
  reason_codes: ['sec_092_control_context', 'eu_ai_act_5_1_f', 'retrain_required'],
  statement: 'Not intended for real-time or safety-critical control.',
};

export const versionLineage: LineageGraph & { n_training_subjects: number } = {
  root: VERSION_NODE,
  direction: 'up',
  depth: null,
  truncated: false,
  n_training_subjects: 12,
  nodes: [
    {
      id: VERSION_NODE,
      kind: 'entity',
      type: 'model',
      ref_id: null,
      content_hash: null,
      node_hash: 'h1',
      attrs: {},
      batch_seq: 2,
      created_at: '2026-09-22T09:00:00Z',
      depth: 0,
    },
    {
      id: TRAIN_ACTIVITY,
      kind: 'activity',
      type: 'train',
      ref_id: null,
      content_hash: null,
      node_hash: 'h2',
      attrs: {},
      batch_seq: 2,
      created_at: '2026-09-22T09:00:00Z',
      depth: 1,
    },
    {
      id: RECORDING_NODE,
      kind: 'entity',
      type: 'recording',
      ref_id: uuid(3),
      content_hash: null,
      node_hash: 'h3',
      attrs: {},
      batch_seq: 1,
      created_at: '2026-09-21T09:00:00Z',
      depth: 2,
    },
  ],
  edges: [
    { src: VERSION_NODE, rel: 'wasGeneratedBy', dst: TRAIN_ACTIVITY },
    { src: TRAIN_ACTIVITY, rel: 'used', dst: RECORDING_NODE },
  ],
};
