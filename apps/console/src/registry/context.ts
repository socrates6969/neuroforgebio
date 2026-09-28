// The deployment-context form: which fields a requester declares and the values offered.
// The values mirror the platform's DeploymentContext (nf_platform.registry.service) and its
// vocabulary (nf_platform.registry.vocab). The platform decides and refuses (EU AI Act Art. 5
// settings, use restrictions, retrain_required).
//
// SEC-092 (non-negotiable): the platform never controls stimulation or any actuator. The control
// settings (closed-loop stimulation, neuromodulation control, actuator control) are NOT offered
// here; the API refuses and audits them if a client sends them anyway. CONTROL_SETTINGS exists only
// so that a stored refusal naming one is rendered readably and so tests can assert it is absent.

/** authz actions (mirrored from src/api/authz.json; hiding only, never enforcement) */
export const MODEL_READ_ACTION = 'model:read';
export const DEPLOY_ACTION = 'model:deploy';
/** the version lineage route is authorized as model:read */
export const LINEAGE_ACTION = 'model:read';

export interface Option {
  value: string;
  label: string;
}

export interface ContextField {
  name: 'setting' | 'outputs';
  label: string;
  options: Option[];
  /** preselected value; none means the requester must choose */
  initial?: string;
}

/** Never offered (SEC-092); listed only to label a stored refusal. */
export const CONTROL_SETTINGS: Option[] = [
  { value: 'closed_loop_stimulation', label: 'Closed-loop stimulation (never allowed)' },
  { value: 'neuromodulation_control', label: 'Neuromodulation control (never allowed)' },
  { value: 'actuator_control', label: 'Actuator control (never allowed)' },
];

export const CONTEXT_FIELDS: ContextField[] = [
  {
    name: 'setting',
    label: 'Setting',
    options: [
      { value: 'research', label: 'Research' },
      { value: 'clinical_research', label: 'Clinical research' },
      { value: 'clinical_care', label: 'Clinical care' },
      { value: 'workplace', label: 'Workplace' },
      { value: 'education', label: 'Education' },
      { value: 'consumer_wellness', label: 'Consumer wellness' },
      { value: 'safety_monitoring', label: 'Safety monitoring' },
      { value: 'other', label: 'Other' },
    ],
  },
  {
    name: 'outputs',
    label: 'Outputs exposed',
    options: [
      { value: 'labels', label: 'Labels only' },
      { value: 'coarse_scores', label: 'Coarse scores' },
    ],
    initial: 'labels',
  },
];

/** "EU", an ISO 3166-1 alpha-2 code, or a subdivision such as "US-CO" (registry.vocab.JURISDICTION_RE). */
export const JURISDICTION_PATTERN = '[A-Z]{2}(-[A-Z0-9]{1,3})?';

/** Refusal / block reason codes of nf_platform.registry.vocab, with readable text. */
export const REASON_TEXT: Record<string, string> = {
  sec_092_control_context:
    'SEC-092: the platform never controls stimulation, neuromodulation or actuators; control contexts are always refused.',
  eu_ai_act_5_1_f:
    'EU AI Act Art. 5(1)(f): no emotion or cognitive-state inference in workplace or education settings in the EU without a documented medical or safety exception.',
  eu_ai_act_5_1_g:
    'EU AI Act Art. 5(1)(g): no biometric categorisation inferring sensitive traits in the EU.',
  eu_ai_act_5_1_a:
    'EU AI Act Art. 5(1)(a): a context declaring behaviour influence is refused in the EU for this model.',
  research_only: 'This version is restricted to research or clinical-research settings.',
  no_clinical_care: 'This version may not be deployed in clinical care.',
  sec_144_outputs: 'SEC-144: only labels or coarse scores may be exposed.',
  retrain_required:
    'Retrain required: a subject whose data trained this version withdrew consent, or (uploaded weights) a subject of the tenant withdrew after the version was registered.',
  exception_not_applicable:
    'The exception record does not cover this model, jurisdiction and setting.',
  upload_approval_required:
    'Uploaded weights: a governance approver other than the uploader must approve this version before it is deployed (four-eyes).',
};

/** AppSec M3: the taint reason the platform gives for uploaded weights. */
export const UPLOAD_TAINT_REASON = 'unverifiable lineage (uploaded weights)';

/** Readable text for a version's weights source. */
export const weightsSourceText = (s: 'platform' | 'upload'): string =>
  s === 'upload'
    ? 'Uploaded: the training data is declared by the uploader and not verified by the platform. Any consent withdrawal in your tenant after registration flags this version.'
    : 'Trained on the platform: the training data is known from the lineage.';

/** Readable text for a reason code; unknown codes and free text are shown as sent. */
export const reasonText = (r: string): string => REASON_TEXT[r] ?? r;

export const labelOf = (field: ContextField['name'], value: string): string =>
  (field === 'setting' ? CONTROL_SETTINGS.find((o) => o.value === value)?.label : undefined) ??
  CONTEXT_FIELDS.find((f) => f.name === field)?.options.find((o) => o.value === value)?.label ??
  value;
