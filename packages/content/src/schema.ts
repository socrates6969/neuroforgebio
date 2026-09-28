// Zero-dependency runtime schema for @nf/content. Mirrors ./types.ts by hand.
// Descriptor language (plain objects so it runs under `node --experimental-strip-types`):
//   S.str()            non-empty plain string (no HTML tags)
//   S.rich()           non-empty string whose only allowed tags are <em> and </em>
//   S.bool() / S.lit(v)
//   S.enum([...])
//   S.arr(item, min?)  array with at least `min` items (default 1)
//   S.obj(required, optional?)  object; unknown keys are an error
//   S.rec(value)       Record<string, value>
//   S.claim()          Claim object (text + source required)

export type Schema =
  | { k: 'str' }
  | { k: 'rich' }
  | { k: 'bool' }
  | { k: 'lit'; v: unknown }
  | { k: 'enum'; v: readonly string[] }
  | { k: 'arr'; item: Schema; min: number }
  | { k: 'obj'; req: Record<string, Schema>; opt: Record<string, Schema> }
  | { k: 'rec'; value: Schema };

export const STATUSES = ['designed', 'planned', 'roadmap', 'in-preparation'] as const;
export const GRADES = ['A', 'B', 'B-', 'C', 'D'] as const;

export const S = {
  str: (): Schema => ({ k: 'str' }),
  rich: (): Schema => ({ k: 'rich' }),
  bool: (): Schema => ({ k: 'bool' }),
  lit: (v: unknown): Schema => ({ k: 'lit', v }),
  enum: (v: readonly string[]): Schema => ({ k: 'enum', v }),
  arr: (item: Schema, min = 1): Schema => ({ k: 'arr', item, min }),
  obj: (req: Record<string, Schema>, opt: Record<string, Schema> = {}): Schema => ({
    k: 'obj',
    req,
    opt,
  }),
  rec: (value: Schema): Schema => ({ k: 'rec', value }),
};

const status = S.enum(STATUSES);
const claimReq = { text: S.str(), source: S.str() };
const claimOpt = { sourceUrl: S.str(), grade: S.enum(GRADES) };
export const claim = S.obj(claimReq, claimOpt);
const meta = S.obj({ title: S.str(), description: S.str() });
const link = S.obj({ label: S.str(), href: S.str() }, { status });
const cta = S.obj(
  { label: S.str(), href: S.str(), variant: S.enum(['primary', 'ghost']) },
  { disabled: S.bool(), note: S.str() },
);
const sectionHead = { eyebrow: S.str(), heading: S.rich(), lede: S.str() };
const code = S.obj({ language: S.lit('python'), lines: S.arr(S.str()), note: S.str() });
const statusText = S.obj({ text: S.str() }, { status });

const researchCard = S.obj(
  { slug: S.str(), title: S.str(), summary: S.str(), status, kind: S.str() },
  { featured: S.bool(), banner: S.str(), href: S.str(), cta },
);

export const siteSchema = S.obj({
  nav: S.obj({
    items: S.arr(link),
    cta,
  }),
  footer: S.obj({
    tagline: S.str(),
    disclaimer: S.str(),
    copyright: S.str(),
    groups: S.arr(S.obj({ heading: S.str(), links: S.arr(link) })),
  }),
  aria: S.obj({
    heroVisual: S.obj({ clinical: S.str(), cosmos: S.str() }),
    heroVisualCaption: S.str(),
    formats: S.str(),
    audienceTabs: S.str(),
    codeSample: S.str(),
  }),
  earlyAccess: S.obj({
    heading: S.rich(),
    body: S.str(),
    emailLabel: S.str(),
    emailPlaceholder: S.str(),
    submitLabel: S.str(),
    disabled: S.lit(true),
    disabledNote: S.str(),
    status,
  }),
  banners: S.obj({
    notLegalAdvice: S.str(),
    irbFda: S.str(),
    demoData: S.str(),
    illustrativeApi: S.str(),
  }),
  notFound: S.obj({ meta, heading: S.rich(), body: S.str(), homeLink: link }),
  figureUi: S.obj({
    dataTableSummary: S.str(),
    readoutLabel: S.str(),
    keyboardHint: S.str(),
    downloadSvg: S.str(),
    reproduceLink: S.str(),
    manifestLabel: S.str(),
    statusPreliminary: S.str(),
  }),
  gallery: S.obj({ meta, heading: S.str() }),
});

export const homeSchema = S.obj({
  meta,
  hero: S.obj({ eyebrow: S.str(), heading: S.rich(), sub: S.str(), ctas: S.arr(cta) }),
  formats: S.obj({ lead: S.str(), items: S.arr(S.str()), note: S.str() }),
  pipeline: S.obj({
    ...sectionHead,
    steps: S.arr(
      S.obj(
        {
          id: S.enum(['ingest', 'pipelines', 'models', 'sdks']),
          number: S.str(),
          kicker: S.str(),
          heading: S.str(),
          body: S.str(),
          tags: S.arr(S.str()),
          status,
        },
        { evidence: S.arr(claim) },
      ),
      4,
    ),
    code: S.obj({
      heading: S.str(),
      body: S.str(),
      language: S.lit('python'),
      lines: S.arr(S.str()),
      note: S.str(),
    }),
  }),
  governance: S.obj({
    ...sectionHead,
    points: S.arr(S.obj({ heading: S.str(), body: S.str(), status })),
    link,
    evidence: S.arr(claim),
  }),
  audience: S.obj({
    ...sectionHead,
    panels: S.arr(
      S.obj({
        id: S.enum(['researchers', 'hardware']),
        tabLabel: S.str(),
        tier: S.str(),
        heading: S.rich(),
        body: S.str(),
        bullets: S.arr(statusText),
        cta,
      }),
      2,
    ),
  }),
  compliance: S.obj({
    ...sectionHead,
    rows: S.arr(S.obj({ control: S.str(), description: S.str(), status }, { claim })),
    legal: S.str(),
    link,
  }),
  pricing: S.obj({
    ...sectionHead,
    tiers: S.arr(
      S.obj(
        {
          id: S.enum(['academic', 'startup', 'enterprise']),
          name: S.str(),
          price: S.str(),
          who: S.str(),
          features: S.arr(statusText),
          cta,
        },
        { featured: S.bool() },
      ),
      3,
    ),
    link,
  }),
  research: S.obj({ ...sectionHead, cards: S.arr(researchCard, 3), link }),
  cta: S.obj({ heading: S.rich(), body: S.str(), ctas: S.arr(cta) }),
});

export const pageSchema = S.obj(
  {
    meta,
    hero: S.obj(sectionHead),
    sections: S.arr(
      S.obj(
        { id: S.str(), heading: S.rich(), body: S.arr(S.str()) },
        {
          items: S.arr(
            S.obj(
              { heading: S.str(), body: S.str() },
              { status, buildState: S.str(), buildSource: S.str() },
            ),
          ),
          evidence: S.arr(claim),
          code,
        },
      ),
    ),
  },
  {
    banner: S.str(),
    placeholder: S.bool(),
    cta: S.arr(cta),
    earlyAccessNote: S.obj({ text: S.str(), linkLabel: S.str(), href: S.str() }),
    reviewed: S.bool(),
  },
);

const lawRow = S.obj(
  {
    ...claimReq,
    id: S.str(),
    jurisdiction: S.str(),
    instrument: S.str(),
    status: S.str(),
    verified: S.bool(),
  },
  { ...claimOpt, definition: S.str(), note: S.str() },
);

export const lawTrackerSchema = S.obj({
  meta,
  hero: S.obj(sectionHead),
  banner: S.str(),
  asOf: S.str(),
  legend: S.obj({ verified: S.str(), unverified: S.str() }),
  // 5.6: labels for the rules table; its rows come from rules/*.yaml at build time
  ruleset: S.obj({
    heading: S.str(),
    intro: S.str(),
    generatedFrom: S.str(),
    hashLabel: S.str(),
    caption: S.str(),
    columns: S.obj({
      jurisdiction: S.str(),
      citation: S.str(),
      effective: S.str(),
      covers: S.str(),
      review: S.str(),
    }),
    badges: S.obj({ draft: S.str(), unverified: S.str(), counselReviewed: S.str() }),
    effectiveNone: S.str(),
    definitionLabel: S.str(),
    absenceNote: S.str(),
    contextHeading: S.str(),
    contextIntro: S.str(),
  }),
  groups: S.arr(S.obj({ id: S.str(), heading: S.str(), rows: S.arr(lawRow) }, { intro: S.str() })),
  openHeading: S.str(),
  openItems: S.arr(S.str()),
  sourceNote: S.str(),
});

export const researchIndexSchema = S.obj({
  meta,
  hero: S.obj(sectionHead),
  banner: S.str(),
  cards: S.arr(researchCard),
});

// Neural Playground (/playground). Numbers (R², dataset ids, noise rates) come from the precomputed
// asset in apps/web/src/assets/playground at build time, never from copy.
const headed = (extra: Record<string, Schema> = {}) =>
  S.obj({ heading: S.str(), caption: S.str(), label: S.str(), ...extra });
export const playgroundSchema = S.obj({
  meta,
  hero: S.obj(sectionHead),
  banner: S.str(),
  controls: S.obj({
    heading: S.str(),
    trial: S.str(),
    trialOption: S.str(),
    play: S.str(),
    pause: S.str(),
    time: S.str(),
    seconds: S.str(),
    speed: S.str(),
    neurons: S.str(),
    neuronsUnit: S.str(),
    noise: S.str(),
    noiseNone: S.str(),
    noiseUnit: S.str(),
    decoder: S.str(),
    decoders: S.obj({ ridge: S.str(), kalman: S.str() }),
    autoAdvance: S.str(),
  }),
  panels: S.obj({
    raster: headed(),
    path: headed({ actual: S.str(), decoded: S.str(), target: S.str() }),
    arm: headed(),
  }),
  score: S.obj({
    heading: S.str(),
    testSet: S.str(),
    velocity: S.str(),
    trial: S.str(),
    trialUnit: S.str(),
    explain: S.str(),
    chartHeading: S.str(),
    chartCaption: S.str(),
    chartLabel: S.str(),
  }),
  how: S.obj({ heading: S.str(), steps: S.arr(S.obj({ heading: S.str(), body: S.str() })) }),
  limits: S.obj({ heading: S.str(), items: S.arr(S.str()) }),
  data: S.obj({
    heading: S.str(),
    dataset: S.str(),
    recording: S.str(),
    licence: S.str(),
    citation: S.str(),
    hash: S.str(),
    split: S.str(),
    shown: S.str(),
    noise: S.str(),
    control: S.str(),
    controlText: S.str(),
    reproduce: S.str(),
    tablesSummary: S.str(),
    tablePosition: S.str(),
    tableVelocity: S.str(),
    rowHeader: S.str(),
    noiseHeader: S.str(),
    terms: S.obj({
      version: S.str(),
      units: S.str(),
      meanRate: S.str(),
      rateUnit: S.str(),
      training: S.str(),
      validation: S.str(),
      test: S.str(),
      bins: S.str(),
    }),
  }),
  still: S.obj({ alt: S.str(), caption: S.str() }),
  noscript: S.str(),
  loading: S.str(),
  loadError: S.str(),
  footer: S.obj({ lead: S.str(), tail: S.str() }),
  interfaceLink: link,
});

// Neural interface 3D scene (/interface). Illustrative anatomy and device; firing from the playground asset.
const words = (keys: string[]) => S.obj(Object.fromEntries(keys.map((k) => [k, S.str()])));
export const interfaceSchema = S.obj({
  meta,
  hero: S.obj(sectionHead),
  banner: S.str(),
  sceneLabel: S.str(),
  loading: S.str(),
  fallback: words(['alt', 'noWebgl', 'reducedMotion', 'show', 'caption', 'noscript']),
  controls: S.obj({
    heading: S.str(),
    play: S.str(),
    pause: S.str(),
    tour: S.str(),
    reset: S.str(),
    zoomIn: S.str(),
    zoomOut: S.str(),
    layers: S.str(),
    layerNames: words(['tissue', 'electrodes', 'signals', 'decoder']),
    inspect: S.str(),
    inspectNone: S.str(),
    electrode: S.str(),
    unitWord: S.str(),
    unitsWord: S.str(),
    trial: S.str(),
    of: S.str(),
    orbitHint: S.str(),
  }),
  tour: words(['overview', 'array', 'neurons', 'signal', 'decoder']),
  labels: words(['cortex', 'array', 'neurons', 'headstage', 'decoder', 'screen', 'arm']),
  inspect: words(['heading', 'empty', 'trace', 'traceNote', 'raster', 'noUnits']),
  notes: S.obj({ heading: S.str(), items: S.arr(S.str()) }),
  playgroundLink: link,
  recordCredit: S.str(),
});

export const whitepaperSchema = S.obj(
  {
    slug: S.str(),
    meta,
    title: S.str(),
    status,
    kind: S.str(),
    banner: S.str(),
    statusNote: S.str(),
    intro: S.arr(S.str()),
    abstractPlaceholder: S.str(),
    questions: S.arr(S.obj({ heading: S.str(), body: S.str(), source: S.str() })),
    citationNote: S.str(),
  },
  {
    evidenceLegend: S.str(),
    citation: S.obj({}, { bibtex: S.str() }),
    printNote: S.str(),
    figures: S.rec(S.obj({ title: S.str(), caption: S.str() }, { note: S.str() })),
  },
);

export const brandSchema = S.obj({
  name: S.str(),
  legalName: S.str(),
  legalNameIsPlaceholder: S.bool(),
  domain: S.str(),
  domainIsPlaceholder: S.bool(),
  secondaryHost: S.str(),
  codeIdentifiers: S.obj({
    pythonImport: S.str(),
    pypiPackage: S.str(),
    grpcPackage: S.str(),
    repoName: S.str(),
    fixed: S.bool(),
    note: S.str(),
  }),
});

/* ---------------------------------------------------------------- locales */

export const LOCALES = ['en', 'no'] as const;
export const SECURITY_ANCHORS = [
  'data',
  'never',
  'software',
  'standards',
  'testing',
  'incidents',
  'disclosure',
] as const;

export const uiSchema = S.obj(
  {
    statusLabels: S.obj({
      designed: S.str(),
      planned: S.str(),
      roadmap: S.str(),
      'in-preparation': S.str(),
    }),
    statusPill: S.str(),
    brandHomeLabel: S.str(),
    skipLink: S.str(),
    primaryNav: S.str(),
    footerNav: S.str(),
    menuOpenLabel: S.str(),
    menuCloseLabel: S.str(),
    securityVisual: S.str(),
    languageSwitch: S.obj({ label: S.str(), names: S.obj({ en: S.str(), no: S.str() }) }),
    legal: S.obj({
      heading: S.str(),
      privacy: S.str(),
      terms: S.str(),
      cookies: S.str(),
      company: S.str(),
    }),
    draftLabel: S.str(),
    /** Accessible name for a whitepaper's scrollable, focusable BibTeX citation block. */
    citation: S.str(),
  },
  {
    buildStateLabels: S.obj({
      'built-internal': S.str(),
    }),
  },
);

const statusRef = S.obj({ status }, { note: S.str() });

export const securitySchema = S.obj({
  meta,
  heading: S.str(),
  intro: S.arr(S.str()),
  note: S.obj({ lead: S.str(), body: S.str() }),
  legend: S.arr(S.obj({ status, text: S.str() }), 3),
  afterLegend: S.arr(S.str()),
  sections: S.arr(
    S.obj(
      { id: S.enum(SECURITY_ANCHORS), heading: S.str() },
      {
        body: S.arr(S.str()),
        table: S.obj({
          headers: S.arr(S.str(), 2),
          rows: S.arr(S.obj({ cells: S.arr(S.str()), status: S.arr(statusRef) })),
        }),
        bullets: S.arr(S.obj({ text: S.str() }, { status })),
        after: S.arr(S.str()),
        status,
      },
    ),
    SECURITY_ANCHORS.length,
  ),
});

export const legalSchema = S.obj({
  meta,
  draft: S.bool(),
  draftNotice: S.str(),
  title: S.str(),
  shortTitle: S.str(),
  blocks: S.arr(
    S.obj(
      { type: S.enum(['h2', 'h3', 'p', 'ul', 'table', 'quote']) },
      {
        id: S.str(),
        text: S.str(),
        items: S.arr(S.str()),
        head: S.arr(S.str()),
        rows: S.arr(S.arr(S.str())),
      },
    ),
  ),
});
