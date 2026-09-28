# @nf/copy-lint

Zero-dependency linter that enforces the copy rules in `architecture/BLUEPRINT.md` §2.6 and §10
(status labels say designed / planned / roadmap / in preparation; no medical or compliance claims).

```sh
node tools/copy-lint/cli.mjs <files|dirs...>          # prints file:line: term, exit 1 on any hit
node tools/copy-lint/cli.mjs --json <files|dirs...>   # {results:[{file,line,term,match}], errors:[...]}
node --test "tools/copy-lint/test/*.test.mjs"         # tests (node:test)
```

Exit codes: `0` clean, `1` at least one hit, `2` usage error or a file that could not be parsed.

## What is scanned

- Extensions: `.json .md .mdx .html .htm .astro`. Other files are ignored (a warning is printed if one is passed explicitly).
- Directories recurse. `node_modules`, `dist`, `.git`, `.astro`, `.venv`, `target` are skipped while recursing,
  but a path you pass explicitly is always scanned (so `copy-lint apps/web/dist/clinical` lints the built HTML).
- **HTML / Astro / MDX:** visible text only. Tags, attribute values (class names, URLs, ids), `<script>`, `<style>`
  and comments are ignored. The exceptions are attributes people read or hear: `alt`, `title`, `aria-label`,
  `placeholder`, and `content` on `<meta>`. In `.astro` the frontmatter is skipped, and `{expressions}` in
  `.astro`/`.mdx` are skipped except for string literals inside them. Entities are decoded.
- **Markdown:** everything except link targets `](...)` and reference definitions. Frontmatter is linted (titles are copy).
- **JSON:** string values (not keys). Values of keys that hold identifiers or URLs are skipped:
  `href url src source sources slug id path icon class className $schema image file doi pmid arxiv rel type key`.
- URLs (`http(s)://…`, `mailto:`, `www.…`) are blanked everywhere, so hosts such as `live.example.com` never match.
- Phrases may span lines; the hit is reported on the line where it starts.

## Banned terms

Case-insensitive, whole words (Unicode letter/number boundaries; any hyphen-like character or space run counts as the hyphen).

| Term reported | Matches (examples) |
|---|---|
| `built-in` | built-in, built‑in, builtin (not "built in Rust") |
| `live` | see below |
| `available now` | available now, now available |
| `certified` | certified |
| `HIPAA-compliant` | HIPAA-compliant, HIPAA compliant |
| `SOC 2 compliant` | SOC 2 compliant, SOC2-compliant, SOC 2 Type II compliant |
| `treat` | treat, treats, treated, treating (not "treatment") |
| `diagnose` | diagnose, diagnoses, diagnosed, diagnosing (not "diagnostics") |
| `cure` | cure, cures, cured, curing (not "curation") |
| `restore` | restore, restores, restored, restoring (not "restoration") |
| `automated neuro-cleaning` | automated neuro-cleaning, automated neuro cleaning |
| `mock-number-unlabelled` | see "Mock UI numbers" |

### The `live` rule

"live" is only banned as a **status claim**, because the word has honest uses in this product
("live streams over LSL", "where our users live"). A hit is any of:

1. a verb or adverb directly before it: `is|are|was|were|be|been|being|go|goes|going|went|gone|now|currently|already live`;
2. a status noun or time word directly after it: `live now|today|product|service|platform|beta|release|version|in production`;
3. `status: live`, `state = live`;
4. a label that is only the word: an HTML text node, a JSON string value, a Markdown line or table cell whose letters are just "live" (for example a `<span class="badge">Live</span>` or `"status": "live"`).

"deliver", "alive", "olive", "liveness" never match (word boundaries).

### Negation allowlist

A hit is ignored when a negation word appears **up to 4 words before it in the same clause** (clauses end at `. ; : ! ?` or a blank line).
Negations: `not never no non nor neither without cannot isn't aren't wasn't weren't don't doesn't didn't won't can't`.
Norwegian (bokmål): `ikke aldri ingen uten verken hverken` ("skal ikke brukes til diagnose" passes).
So these pass: "design concept, not a live product", "does not diagnose, treat or cure", "we never go live without review".
These still fail: "Not reviewed. It is certified." (different clause) and a negation more than 4 words back.

### Reviewed exact-phrase allowlist (`allow.json`)

For reviewed legal wording that uses a banned word about **someone else** (for example the EU-US Data Privacy
Framework's "certified US recipients"), `allow.json` lists `{term, phrase, reason}` entries. A hit is ignored only
when the matched words lie **inside an occurrence of that exact phrase** (case-insensitive, any whitespace between
words); the same word anywhere else still fails. Each entry must name an existing term, contain it, and carry a
written reason; the loader throws otherwise. The banned-term list is unchanged. Changes to `allow.json` are
reviewed like code (CODEOWNERS).

## Mock UI numbers

Numbers in mock UI must sit next to `demo data`, `target` or `ESTIMATE` (case-insensitive; `estimated` also counts). Pragmatic version:

- **HTML / Astro / MDX:** any element with a `data-mock` attribute. If its visible text (or, for a self-closing
  component such as `<Stat data-mock value="17" />`, its attribute values) contains a digit, the same element must
  contain one of the labels. Reported at the line of the opening tag.
- **JSON:** any object with `"mock": true`. If it (recursively) contains a number or a string with a digit, one of
  its string values must contain a label. Reported at the line of the `"mock"` key.

Numbers outside mock UI are not checked (copy with numbers must cite a `source`; that is the content package's test).

## Known limits

- It is a lint, not a parser for every templating form: JSX-heavy `.astro` files with text built in code are only
  checked through their string literals. Lint the **built HTML** as well (the web build does both).
- The negation rule can be gamed ("not only certified"): reviewers still read copy.
