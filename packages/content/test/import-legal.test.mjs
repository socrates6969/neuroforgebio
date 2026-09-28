// Tests for packages/content/scripts/import-legal.mjs's meta-description directive (web-seo T2):
// draftNotice must stay exactly the pinned DRAFT/UTKAST banner (content.test.mjs asserts this too),
// while meta.description becomes independently sourced and unique per page.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { convert, outputs, LEGAL_PAGES, LOCALES } from '../scripts/import-legal.mjs';

const DRAFT_LINE =
  '> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.';

test('meta-description directive: sets meta.description independently of draftNotice', () => {
  // Exact approved placement (nfb-legal): banner, blank, comment, blank, H1 — never directly under
  // the "> " line, so a plain markdown renderer never pulls it into the blockquote.
  const md = [
    DRAFT_LINE,
    '',
    '<!-- meta-description: A distinct description for this page. -->',
    '',
    '# Example page',
    '',
    'Body text.',
  ].join('\n');
  const out = convert(md);
  assert.equal(
    out.draftNotice,
    'DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.',
  );
  assert.equal(out.meta.description, 'A distinct description for this page.');
  // never rendered as a block
  assert.ok(!out.blocks.some((b) => JSON.stringify(b).includes('distinct description')));
});

test('a draft without the directive: meta.description falls back to draftNotice', () => {
  const md = [DRAFT_LINE, '', '# Example page', '', 'Body text.'].join('\n');
  const out = convert(md);
  assert.equal(out.meta.description, out.draftNotice);
  assert.equal(
    out.meta.description,
    'DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.',
  );
});

test('meta-description directive: rejected before the draft notice, after the title, or twice', () => {
  assert.throws(
    () => convert(['<!-- meta-description: too early -->', DRAFT_LINE, '# T'].join('\n')),
    /must come after the draft notice/,
  );
  assert.throws(
    () => convert([DRAFT_LINE, '# T', '<!-- meta-description: too late -->'].join('\n')),
    /must come before the title/,
  );
  assert.throws(
    () =>
      convert(
        [
          DRAFT_LINE,
          '<!-- meta-description: one -->',
          '<!-- meta-description: two -->',
          '# T',
        ].join('\n'),
      ),
    /more than one meta-description directive/,
  );
});

test('the 4 real legal drafts each have a unique meta.description, per locale', () => {
  const all = outputs();
  for (const locale of LOCALES) {
    const docs = Object.keys(LEGAL_PAGES).map((page) =>
      JSON.parse(all.find((o) => o.path.endsWith(`${page}.${locale}.json`)).json),
    );
    const descriptions = docs.map((d) => d.meta.description);
    assert.equal(
      new Set(descriptions).size,
      descriptions.length,
      `${locale}: legal pages must have distinct meta.description (found: ${JSON.stringify(descriptions)})`,
    );
    // and distinct from the (still shared, pinned) draftNotice banner
    for (const doc of docs)
      assert.notEqual(
        doc.meta.description,
        doc.draftNotice,
        `${locale}: expected a real meta-description directive, not the draftNotice fallback`,
      );
  }
});
