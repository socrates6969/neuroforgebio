// Hand-written types for @nf/content. The runtime schema in ./schema.ts mirrors these
// shapes; keep both in sync (test/content.test.mjs validates every JSON file against the schema).
//
// Conventions
// - `Rich` strings may contain ONE inline tag only: <em>…</em> (emphasis painted by the theme).
//   Everything else is plain text; render Rich with set:html, plain strings as text.
// - Placeholders ({brand}, {legalName}, {domain}, {origin}, {pkg}) are already substituted
//   by the loader. Raw JSON is never imported directly by apps.
// - Every factual claim is a `Claim` (has `source`). Product plans are not claims; they carry
//   a `status` instead.

/** Only these four statuses exist (BLUEPRINT §2.6 item 1). */
export type Status = 'designed' | 'planned' | 'roadmap' | 'in-preparation';

/** Inline HTML with <em> only. */
export type Rich = string;

/** A factual statement with its provenance. */
export interface Claim {
  text: string;
  /** Repo path + section, e.g. "market/regulation.md §1". Always present. */
  source: string;
  /** Optional external URL that appears in the cited repo doc. */
  sourceUrl?: string;
  /** Evidence grade as given in the cited doc (A peer-reviewed/primary … D marketing). */
  grade?: 'A' | 'B' | 'B-' | 'C' | 'D';
}

export interface Link {
  label: string;
  href: string;
  /** Present when the target does not exist yet (e.g. docs). Render as non-link text + status pill. */
  status?: Status;
}

/** A call to action. `disabled: true` = render as a disabled button with `note`. */
export interface Cta {
  label: string;
  href: string;
  variant: 'primary' | 'ghost';
  disabled?: boolean;
  note?: string;
}

export interface Meta {
  /** Full <title>, brand already substituted. */
  title: string;
  description: string;
}

export interface Brand {
  name: string;
  legalName: string;
  legalNameIsPlaceholder: boolean;
  domain: string;
  domainIsPlaceholder: boolean;
  /** Host of the cosmos build (DECISIONS D3: a secondary host). Placeholder while domainIsPlaceholder. */
  secondaryHost: string;
  /** https://<domain>; placeholder while domainIsPlaceholder. Use for canonical/OG URLs. */
  origin: string;
  codeIdentifiers: {
    pythonImport: string;
    pypiPackage: string;
    grpcPackage: string;
    repoName: string;
    fixed: boolean;
    note: string;
  };
}

/* ---------------------------------------------------------------- site-wide */

/** English-only site chrome (nav items, footer copy). Localised chrome lives in Ui (ui.<locale>.json). */
export interface Site {
  nav: {
    items: Link[];
    cta: Cta;
  };
  footer: {
    tagline: string;
    disclaimer: string;
    copyright: string;
    groups: { heading: string; links: Link[] }[];
  };
  aria: {
    heroVisual: { clinical: string; cosmos: string };
    heroVisualCaption: string;
    formats: string;
    audienceTabs: string;
    codeSample: string;
  };
  earlyAccess: {
    heading: Rich;
    body: string;
    emailLabel: string;
    emailPlaceholder: string;
    submitLabel: string;
    disabled: true;
    disabledNote: string;
    status: Status;
  };
  banners: {
    notLegalAdvice: string;
    irbFda: string;
    demoData: string;
    illustrativeApi: string;
  };
  notFound: { meta: Meta; heading: Rich; body: string; homeLink: Link };
  /** UI strings around interactive figures. Figure status is "preliminary", never "verified". */
  figureUi: {
    dataTableSummary: string;
    readoutLabel: string;
    keyboardHint: string;
    downloadSvg: string;
    reproduceLink: string;
    manifestLabel: string;
    statusPreliminary: string;
  };
  /** Internal component gallery page (noindex). */
  gallery: { meta: Meta; heading: string };
}

/* ---------------------------------------------------------------- home */

export interface PipelineStep {
  id: 'ingest' | 'pipelines' | 'models' | 'sdks';
  number: string; // "01"
  kicker: string; // "Ingest"
  heading: string;
  body: string;
  tags: string[];
  status: Status;
  evidence?: Claim[];
}

export interface AudiencePanel {
  id: 'researchers' | 'hardware';
  tabLabel: string;
  tier: string;
  heading: Rich;
  body: string;
  bullets: { text: string; status?: Status }[];
  cta: Cta;
}

export interface ComplianceRow {
  control: string;
  description: string;
  status: Status;
  claim?: Claim;
}

export interface PricingTier {
  id: 'academic' | 'startup' | 'enterprise';
  name: string;
  price: string;
  who: string;
  features: { text: string; status?: Status }[];
  featured?: boolean;
  cta: Cta;
}

export interface ResearchCard {
  slug: string;
  title: string;
  summary: string;
  status: Status;
  kind: string; // "Whitepaper · computational study"
  featured?: boolean;
  banner?: string; // IRB/FDA banner on the featured card
  href?: string; // only when a page exists
  cta?: Cta;
}

export interface SectionHead {
  eyebrow: string;
  heading: Rich;
  lede: string;
}

export interface Home {
  meta: Meta;
  hero: {
    eyebrow: string;
    heading: Rich;
    sub: string;
    ctas: Cta[];
  };
  formats: { lead: string; items: string[]; note: string };
  pipeline: SectionHead & {
    steps: PipelineStep[];
    code: { heading: string; body: string; language: 'python'; lines: string[]; note: string };
  };
  governance: SectionHead & {
    points: { heading: string; body: string; status: Status }[];
    link: Link;
    evidence: Claim[];
  };
  audience: SectionHead & { panels: AudiencePanel[] };
  compliance: SectionHead & { rows: ComplianceRow[]; legal: string; link: Link };
  pricing: SectionHead & { tiers: PricingTier[]; link: Link };
  research: SectionHead & { cards: ResearchCard[]; link: Link };
  cta: { heading: Rich; body: string; ctas: Cta[] };
}

/* ---------------------------------------------------------------- generic pages */

export interface PageItem {
  heading: string;
  body: string;
  status?: Status;
  /** Build state indicator: e.g. 'built-internal' for features verified in testing. */
  buildState?: string;
  /** Source citation for buildState, e.g. 'docs/hive/M2-REPORT.md step 2.5'. */
  buildSource?: string;
}

export interface PageSection {
  id: string;
  heading: Rich;
  body: string[];
  items?: PageItem[];
  evidence?: Claim[];
  code?: { language: 'python'; lines: string[]; note: string };
}

/** /platform, /governance, /sdks, /security, /pricing, /legal/* */
export interface Page {
  meta: Meta;
  hero: SectionHead;
  banner?: string;
  placeholder?: boolean; // true on /legal/* : render a visible "Placeholder" marker
  sections: PageSection[];
  cta?: Cta[];
  /** NO /pricing only: replaces the English-only early-access form with a note linking to it. */
  earlyAccessNote?: { text: string; linkLabel: string; href: string };
  /**
   * Translated inner pages only: true once the owner has reviewed the wording. Until then the page is
   * built but unpublished: noindex, not in the sitemap, not in LOCALISED_ROUTES (see publishedInnerPages).
   */
  reviewed?: boolean;
}

/* ---------------------------------------------------------------- law tracker */

export interface LawRow extends Claim {
  id: string;
  jurisdiction: string;
  instrument: string;
  /** Status / key dates as stated in the source. */
  status: string;
  /** Verbatim or summarised definition of neural data, where the source gives one. */
  definition?: string;
  /** `text` (from Claim) = effect in one sentence. */
  verified: boolean;
  /** Why a row is unverified, or an interpretation caveat. */
  note?: string;
}

export interface LawTracker {
  meta: Meta;
  hero: SectionHead;
  banner: string;
  asOf: string; // date the source research was prepared
  legend: { verified: string; unverified: string };
  /** 5.6: labels for the rules table. Its rows come from rules/*.yaml at build time. */
  ruleset: {
    heading: string;
    intro: string;
    generatedFrom: string;
    hashLabel: string;
    caption: string;
    columns: {
      jurisdiction: string;
      citation: string;
      effective: string;
      covers: string;
      review: string;
    };
    badges: { draft: string; unverified: string; counselReviewed: string };
    effectiveNone: string;
    definitionLabel: string;
    absenceNote: string;
    contextHeading: string;
    contextIntro: string;
  };
  /** Context rows NOT encoded in the RuleSet (maintained by hand). */
  groups: { id: string; heading: string; intro?: string; rows: LawRow[] }[];
  /** Heading for the open-questions section (its own h2; not borrowed from sourceNote). */
  openHeading: string;
  openItems: string[];
  sourceNote: string;
}

/* ---------------------------------------------------------------- research */

export interface ResearchIndex {
  meta: Meta;
  hero: SectionHead;
  banner: string;
  cards: ResearchCard[];
}

export interface Whitepaper {
  slug: string;
  meta: Meta;
  title: string;
  status: Status;
  kind: string;
  banner: string;
  statusNote: string;
  intro: string[];
  abstractPlaceholder: string;
  questions: { heading: string; body: string; source: string }[];
  citationNote: string;
  evidenceLegend?: string;
  citation?: { bibtex?: string };
  printNote?: string;
  /** Keyed by figure id from packages/figures manifests. Captions describe only what is plotted. */
  figures?: Record<string, { title: string; caption: string; note?: string }>;
}

/* ---------------------------------------------------------------- playground */

/** A canvas panel on /playground: visible heading and caption, plus the canvas's accessible name. */
export interface PlaygroundPanel {
  heading: string;
  caption: string;
  label: string;
}

/**
 * /playground copy. Numbers (R², dataset ids, noise rates, durations) are not copy: the page reads them
 * from the precomputed asset (apps/web/src/assets/playground, written by tools/playground).
 */
export interface Playground {
  meta: Meta;
  hero: SectionHead;
  banner: string;
  controls: {
    heading: string;
    trial: string;
    trialOption: string;
    play: string;
    pause: string;
    time: string;
    seconds: string;
    speed: string;
    neurons: string;
    neuronsUnit: string;
    noise: string;
    noiseNone: string;
    noiseUnit: string;
    decoder: string;
    decoders: { ridge: string; kalman: string };
    autoAdvance: string;
  };
  panels: {
    raster: PlaygroundPanel;
    path: PlaygroundPanel & { actual: string; decoded: string; target: string };
    arm: PlaygroundPanel;
  };
  score: {
    heading: string;
    testSet: string;
    velocity: string;
    trial: string;
    trialUnit: string;
    explain: string;
    chartHeading: string;
    chartCaption: string;
    chartLabel: string;
  };
  how: { heading: string; steps: { heading: string; body: string }[] };
  limits: { heading: string; items: string[] };
  data: {
    heading: string;
    dataset: string;
    recording: string;
    licence: string;
    citation: string;
    hash: string;
    split: string;
    shown: string;
    noise: string;
    control: string;
    controlText: string;
    reproduce: string;
    tablesSummary: string;
    tablePosition: string;
    tableVelocity: string;
    rowHeader: string;
    noiseHeader: string;
    /** Words placed around numbers from the asset in the data facts list. */
    terms: {
      version: string;
      units: string;
      meanRate: string;
      rateUnit: string;
      training: string;
      validation: string;
      test: string;
      bins: string;
    };
  };
  /** Static still shown before the replay starts or when it cannot run (no JS). */
  still: { alt: string; caption: string };
  noscript: string;
  loading: string;
  loadError: string;
  /** Footer line: `${lead} (${dataset id}, ${licence}). ${tail}` */
  footer: { lead: string; tail: string };
  /** Link to the 3D neural interface page. */
  interfaceLink: Link;
}

/** /interface copy: illustrative 3D neural interface driven by the playground asset. */
export interface Interface {
  meta: Meta;
  hero: SectionHead;
  banner: string;
  sceneLabel: string;
  loading: string;
  fallback: {
    alt: string;
    noWebgl: string;
    reducedMotion: string;
    show: string;
    /** Visible caption under the still (no WebGL, no JS, reduced motion). */
    caption: string;
    noscript: string;
  };
  controls: {
    heading: string;
    play: string;
    pause: string;
    tour: string;
    reset: string;
    zoomIn: string;
    zoomOut: string;
    layers: string;
    layerNames: { tissue: string; electrodes: string; signals: string; decoder: string };
    inspect: string;
    inspectNone: string;
    electrode: string;
    unitWord: string;
    unitsWord: string;
    trial: string;
    of: string;
    orbitHint: string;
  };
  /** Guided-tour captions, keyed by the camera keyframes in apps/web/src/lib/interface-model.mjs. */
  tour: { overview: string; array: string; neurons: string; signal: string; decoder: string };
  labels: {
    cortex: string;
    array: string;
    neurons: string;
    headstage: string;
    decoder: string;
    screen: string;
    arm: string;
  };
  inspect: {
    heading: string;
    empty: string;
    trace: string;
    traceNote: string;
    raster: string;
    noUnits: string;
  };
  notes: { heading: string; items: string[] };
  playgroundLink: Link;
  recordCredit: string;
}

/* ---------------------------------------------------------------- root */

export interface Pages {
  platform: Page;
  governance: Page;
  sdks: Page;
  pricing: Page;
  lawTracker: LawTracker;
  investors: Page;
  research: ResearchIndex;
  playground: Playground;
  interface: Interface;
}

/* ---------------------------------------------------------------- locales (EN + NO bokmål) */

/** Content locales. URL prefix: en = "/", no = "/no/". HTML lang: en = "en", no = "nb" (BCP 47 bokmål). */
export type Locale = 'en' | 'no';

/** Localised site chrome: one file per locale with identical keys (ui.en.json, ui.no.json). */
export interface Ui {
  statusLabels: Record<Status, string>;
  /** Visually hidden prefix read before a status label, e.g. "Status:". */
  statusPill: string;
  brandHomeLabel: string;
  skipLink: string;
  primaryNav: string;
  footerNav: string;
  menuOpenLabel: string;
  menuCloseLabel: string;
  securityVisual: string;
  languageSwitch: { label: string; names: Record<Locale, string> };
  legal: { heading: string; privacy: string; terms: string; cookies: string; company: string };
  draftLabel: string;
  /** Labels for build states (e.g. 'built-internal'). Optional. */
  buildStateLabels?: Record<string, string>;
  /** Accessible name for a whitepaper's scrollable, focusable BibTeX citation block. */
  citation: string;
}

/** A status pill with an optional qualifier, e.g. Roadmap (EU). */
export interface StatusRef {
  status: Status;
  note?: string;
}

/**
 * /security (SEC-158), from docs/inputs/security/website-security-page.md.
 * Plain strings may carry inline markup: **bold**, *em*, [text](href). Render with a safe inline renderer.
 */
export interface SecurityPage {
  meta: Meta;
  heading: string;
  intro: string[];
  note: { lead: string; body: string };
  legend: { status: Status; text: string }[];
  afterLegend: string[];
  sections: {
    id: 'data' | 'never' | 'software' | 'standards' | 'testing' | 'incidents' | 'disclosure';
    heading: string;
    body?: string[];
    table?: { headers: string[]; rows: { cells: string[]; status: StatusRef[] }[] };
    bullets?: { text: string; status?: Status }[];
    after?: string[];
    status?: Status;
  }[];
}

/** A block of a legal draft (generated from docs/inputs/legal-website by scripts/import-legal.mjs). */
export interface LegalBlock {
  type: 'h2' | 'h3' | 'p' | 'ul' | 'table' | 'quote';
  id?: string;
  text?: string;
  items?: string[];
  head?: string[];
  rows?: string[][];
}

export interface LegalPage {
  meta: Meta;
  /** True while the text awaits advokat review: render the DRAFT banner and noindex. */
  draft: boolean;
  draftNotice: string;
  title: string;
  shortTitle: string;
  blocks: LegalBlock[];
}

export type LegalKey = 'privacy' | 'terms' | 'cookies' | 'company';

/** Inner pages that exist in every locale. EN entries are the same objects as `Content.pages`. */
export type InnerPageKey = 'platform' | 'governance' | 'sdks' | 'pricing';
export interface LocaleContent {
  locale: Locale;
  ui: Ui;
  security: SecurityPage;
  legal: Record<LegalKey, LegalPage>;
  /** Named innerPages, not pages: getContent('en') spreads this over Content, which has `pages`. */
  innerPages: Record<InnerPageKey, Page>;
}

export interface Content {
  brand: Brand;
  /** Localised pages and chrome. English is complete; Norwegian covers /security, the legal pages and the inner pages. */
  locales: Record<Locale, LocaleContent>;
  site: Site;
  home: Home;
  pages: Pages;
  whitepapers: Record<string, Whitepaper>;
}
