/**
 * Scheme allow-listing for URLs that arrive from investigation data.
 *
 * Source URLs, OSINT results, and entity labels are untrusted: they come from
 * ingested pages, imported files, and third-party lookups. React does not
 * sanitize the `href` attribute, so rendering one directly allows
 * `javascript:` and `data:` navigations. The app's CSP blocks inline script
 * execution, but a `data:` document navigation is not covered by `script-src`,
 * and defence should not rest on a single control.
 *
 * `safeExternalHref` returns `undefined` for anything that is not plain
 * http(s), so callers can render inert text instead of a link.
 */

const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function safeExternalHref(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    // Relative or malformed values are never linked out to.
    return undefined;
  }
  if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) return undefined;
  return parsed.href;
}

export function isSafeExternalHref(value: string | null | undefined): boolean {
  return safeExternalHref(value) !== undefined;
}
