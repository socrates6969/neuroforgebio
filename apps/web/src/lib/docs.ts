// Docs content (BUILD-GUIDE 4.5): quickstarts, SDK guides, overview, changelog and the generated API
// reference live as JSON in src/docs so tools/doc-snippets/run.py can execute every quickstart code
// block the pages show. A guide's code block either names a quickstart block ("doctest") or is a
// verbatim excerpt of a repository file ("source"); apps/web/test/docs.test.mjs checks both. {brand} and {pkg} are substituted from the brand token (never typed, BLUEPRINT §2.2).
import brand from '@nf/content/brand.json' with { type: 'json' };
import index from '../docs/index.json' with { type: 'json' };
import changelog from '../docs/changelog.json' with { type: 'json' };
import api from '../docs/api-reference.json' with { type: 'json' };
import type { Status } from '@nf/content';

const quickstartFiles = import.meta.glob('../docs/quickstarts/*.json', {
  eager: true,
  import: 'default',
});
const guideFiles = import.meta.glob('../docs/guides/*.json', { eager: true, import: 'default' });

export interface DocCode {
  language: string;
  lines: string[];
  /** Repository path the lines are copied from verbatim. */
  source?: string;
  /** "<quickstart>#<section>": the lines are that quickstart block, executed by run.py. */
  doctest?: string;
}
export interface DocItem {
  heading: string;
  body: string;
  status?: Status;
}
export interface DocSection {
  id: string;
  heading: string;
  body: string[];
  code?: DocCode;
  items?: DocItem[];
}
export interface DocPage {
  slug: string;
  order: number;
  meta: { title: string; description: string };
  navLabel: string;
  eyebrow: string;
  heading: string;
  lede: string;
  status?: Status;
  /** Where the page's facts come from (repository path, branch and commit when not on main). */
  source?: string;
  sections: DocSection[];
  endpoints?: DocEndpoints;
}
/** SDK coverage of the v1 operations (Python SDK guide). */
export interface DocEndpoints {
  heading: string;
  body: string[];
  labels: { endpoint: string; call: string };
  /** Operations an SDK function calls: the function and the line in `file` that names the path. */
  wrapped: { operationId: string; call: string; file: string; needle: string }[];
  /** Operations the SDK cannot call yet, with the reason. */
  unsupported: { operationId: string; reason: string }[];
  /** Call for any other operation, per HTTP method ("{path}" is replaced), and its note. */
  generic: Record<string, string>;
  genericNote: string;
}

const pkg = brand.codeIdentifiers.pythonImport;
const sub = (s: string) => s.replaceAll('{brand}', brand.name).replaceAll('{pkg}', pkg);
function deep<T>(v: T): T {
  if (typeof v === 'string') return sub(v) as T;
  if (Array.isArray(v)) return v.map(deep) as T;
  if (v && typeof v === 'object')
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, deep(x)])) as T;
  return v;
}

export const quickstarts: DocPage[] = Object.entries(quickstartFiles)
  .map(([file, doc]) => ({
    ...deep(doc as Omit<DocPage, 'slug'>),
    slug: file.replace(/^.*\/|\.json$/g, ''),
  }))
  .sort((a, b) => a.order - b.order);

// Guides reuse quickstart blocks by reference, so the text shown is the text run.py executes.
function resolveDoctest(c: DocCode): DocCode {
  if (!c.doctest) return c;
  const [slug, id] = c.doctest.split('#');
  const q = quickstarts.find((x) => x.slug === slug);
  const code = q?.sections.find((x) => x.id === id)?.code;
  if (!code) throw new Error(`docs: unknown doctest block ${c.doctest}`);
  return { ...c, language: code.language, lines: code.lines };
}

export const guides: DocPage[] = Object.entries(guideFiles)
  .map(([file, doc]) => {
    const g = deep(doc as Omit<DocPage, 'slug'>);
    return {
      ...g,
      slug: file.replace(/^.*\/|\.json$/g, ''),
      sections: g.sections.map((s) => (s.code ? { ...s, code: resolveDoctest(s.code) } : s)),
    };
  })
  .sort((a, b) => a.order - b.order);

export const overview = deep(index) as Omit<DocPage, 'slug' | 'order' | 'navLabel'> & {
  nav: {
    label: string;
    overview: string;
    api: string;
    changelog: string;
    source: string;
    doctest: string;
    pageSource: string;
  };
};
export const changes = deep(changelog);
export const apiReference = deep(api);

/** SDK call shown for an operation: its wrapper, a generic Client call, or why there is none. */
export function endpointCalls(e: DocEndpoints) {
  return (o: { operationId: string; method: string; path: string }) => {
    const w = e.wrapped.find((x) => x.operationId === o.operationId);
    if (w) return { call: w.call, note: '' };
    const u = e.unsupported.find((x) => x.operationId === o.operationId);
    if (u) return { call: '-', note: u.reason };
    const g = e.generic[o.method] ?? e.generic.other;
    return { call: g.replace('{method}', o.method).replace('{path}', o.path), note: e.genericNote };
  };
}

export const DOCS_ROUTES = [
  '/docs/',
  ...guides.map((g) => `/docs/${g.slug}/`),
  ...quickstarts.map((q) => `/docs/quickstart/${q.slug}/`),
  '/docs/api/',
  '/docs/changelog/',
];

export const codeText = (c: DocCode) => c.lines.join(String.fromCharCode(10));
