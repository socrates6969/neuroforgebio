// Safe renderer for the inline markup used in the security and legal copy:
// **bold**, *em*, `code`, [text](href), bare https:// URLs, and line breaks. Everything is HTML-escaped
// first; only these constructs become tags. Link targets must be site-relative, #fragments, https: or
// mailto: (no javascript:, no protocol-relative URLs). No inline styles or handlers are ever emitted.

const ESC: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};
export const escapeHtml = (s: string) => s.replace(/[&<>"']/g, (c) => ESC[c]);

export function safeHref(href: string): boolean {
  return /^(\/(?!\/)|#|https:\/\/|mailto:)/i.test(href);
}

export interface InlineOptions {
  /** Rewrites internal hrefs (e.g. to the Norwegian page when it exists). */
  mapHref?: (href: string) => string;
}

export function inline(src: string, opts: InlineOptions = {}): string {
  const keep: string[] = [];
  const stash = (html: string) => `\u0000${keep.push(html) - 1}\u0000`;
  const map = opts.mapHref ?? ((h: string) => h);
  let s = src;
  // `code` first: its content is literal
  s = s.replace(/`([^`]+)`/g, (_, c: string) => stash(`<code>${escapeHtml(c)}</code>`));
  // [text](href)
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text: string, href: string) => {
    if (!safeHref(href)) return m;
    const ext = /^https:/i.test(href);
    return stash(
      `<a href="${escapeHtml(map(href))}"${ext ? ' rel="noopener noreferrer"' : ''}>${inlineText(text)}</a>`,
    );
  });
  // bare https URLs (legal sources); trailing punctuation stays outside the link
  s = s.replace(/https:\/\/[^\s<>()[\]]+[^\s<>()[\].,;:]/g, (u) =>
    stash(`<a href="${escapeHtml(u)}" rel="noopener noreferrer">${escapeHtml(u)}</a>`),
  );
  return inlineText(s).replace(/\u0000(\d+)\u0000/g, (_, i: string) => keep[Number(i)]);
}

/** Escape, then **bold**, *em* and line breaks. */
function inlineText(s: string): string {
  return escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*\w])\*(?![\s*])(.+?)\*(?!\w)/g, '$1<em>$2</em>')
    .replace(/\n/g, '<br>');
}
