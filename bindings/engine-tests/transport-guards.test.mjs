// Static packaging guards for the WinHTTP transport (nfb-security, CABI-M1 review of cb0fd54,
// first run against b976337, green since 5db14b2) (SWARM1-BOARD gap E3 follow-up). "Shipped" = every file under
// bindings/transport-conformance/winhttp/include/**; tests/ is never shipped. These are
// grep-level/text checks -- nothing here is compiled (no C++ toolchain run) -- so they only catch
// what's visible as text: an accidental #include, a defined-not-behind-a-declaration symbol, a
// missing/weak security option, or (T2) the test header's name appearing at all.
//
// T1 strips `//`/`/* */` comments and #error/#pragma-message diagnostic text before matching
// (stripCppNoise), the same way R3's C++ guard strips `//` comments, so a doc comment or a
// developer-facing compile error that merely *names* something doesn't fool that check. T2 and T3
// do NOT strip anything (nfb-engine/nfb-security ruling: too permissive for a security-owned file)
// -- both are plain substring matches over the raw bytes, so even a comment-only mention fails them.
//
// Plain Node: node:test, node:assert, node:fs, node:path. No dependencies.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {
  FIXTURES,
  REPO_ROOT,
  WINHTTP_SHIPPED_INCLUDE_ROOT,
  WINHTTP_TESTING_HEADER,
  readText,
  shippedWinHttpFiles,
  definesTestAccess,
  mentionsTestingHeader,
  transportRevocationConfig,
} from './helpers.mjs';

const TRANSPORT_FIXTURES = path.join(FIXTURES, 'transport');
const TRANSPORT_HPP = path.join(WINHTTP_SHIPPED_INCLUDE_ROOT, 'nf_winhttp_transport.hpp');

// ---------------------------------------------------------------------------
// T1: no shipped file DEFINES struct TestAccess (`struct TestAccess {` or `struct TestAccess`
// followed by a body). The declaration `struct TestAccess;` is allowed.
// ---------------------------------------------------------------------------

test('T1: no file under bindings/transport-conformance/winhttp/include/** defines struct TestAccess', () => {
  const files = shippedWinHttpFiles();
  assert.ok(files.length > 0, `expected at least one shipped file under ${WINHTTP_SHIPPED_INCLUDE_ROOT}`);
  for (const file of files) {
    const result = definesTestAccess(readText(file));
    assert.equal(
      result.definesIt,
      false,
      `${path.relative(REPO_ROOT, file)} defines struct TestAccess (only a forward declaration is allowed)`,
    );
  }
});

test('T1 regression fixture: a shipped-style header defining struct TestAccess is caught', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't1-defines-test-access.hpp.txt'));
  const result = definesTestAccess(source);
  assert.equal(result.definesIt, true);
});

// ---------------------------------------------------------------------------
// T2: no shipped file mentions or #includes nf_winhttp_testing. Literal reading (nfb-engine
// ruling): a raw substring match over the whole file, comments and diagnostics included -- no
// stripping. A comment-only mention fails this just as an #include does.
//
// Failed on b976337 (3 doc-comment mentions + the #error text); fixed in 5db14b2, where nfb-engine
// reworded all 4 lines.
// ---------------------------------------------------------------------------

test('T2: no file under bindings/transport-conformance/winhttp/include/** mentions or #includes nf_winhttp_testing', () => {
  const files = shippedWinHttpFiles();
  assert.ok(files.length > 0, `expected at least one shipped file under ${WINHTTP_SHIPPED_INCLUDE_ROOT}`);
  for (const file of files) {
    const result = mentionsTestingHeader(readText(file));
    assert.equal(
      result.violates,
      false,
      `${path.relative(REPO_ROOT, file)} mentions or #includes nf_winhttp_testing (raw substring match, comments included)`,
    );
  }
});

test('T2 regression fixture: a shipped-style header #including nf_winhttp_testing.hpp is caught', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't2-includes-testing-header.hpp.txt'));
  const result = mentionsTestingHeader(source);
  assert.equal(result.includesIt, true);
  assert.equal(result.violates, true);
});

test('T2 regression fixture: a comment-only mention of nf_winhttp_testing is also caught (literal reading)', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't2-comment-only-mention.hpp.txt'));
  const result = mentionsTestingHeader(source);
  assert.equal(result.includesIt, false, 'this fixture has no #include, only a comment mention');
  assert.equal(result.mentionsIt, true);
  assert.equal(result.violates, true);
});

test('T2 fixture: a clean file with no mention of nf_winhttp_testing passes', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't2-clean.hpp.txt'));
  const result = mentionsTestingHeader(source);
  assert.equal(result.includesIt, false);
  assert.equal(result.mentionsIt, false);
  assert.equal(result.violates, false);
});

// ---------------------------------------------------------------------------
// T3: nf_winhttp_transport.hpp sets WINHTTP_ENABLE_SSL_REVOCATION in code (comments and #error
// text don't count; this half stays scoped to that one file). No file under bindings/transport-conformance/winhttp/include/** may contain ANY
// SECURITY_FLAG_IGNORE_<...> identifier (extended per nfb-security to the whole prefix, not just
// the 3 originally enumerated -- SECURITY_FLAG_IGNORE_CERT_DATE_INVALID and every other
// cert-validation bypass flag under that prefix are just as forbidden) or
// WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE. This is a literal raw substring match, like T2 --
// no comment stripping -- because the unshipped tests/nf_winhttp_testing.hpp legitimately uses
// SECURITY_FLAG_IGNORE_UNKNOWN_CA and WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE, so a shipped file
// can't be allowed to even mention them in a comment. tests/ stays excluded throughout.
//
// Failed on b976337 (no revocation-enable flag); fixed in 5db14b2.
// ---------------------------------------------------------------------------

test('T3: nf_winhttp_transport.hpp enables revocation checking and carries none of the weakening flags', () => {
  const result = transportRevocationConfig(readText(TRANSPORT_HPP));
  assert.equal(result.hasRevocationEnable, true, 'expected WINHTTP_ENABLE_SSL_REVOCATION in nf_winhttp_transport.hpp');
  assert.deepEqual(
    result.forbiddenFound,
    [],
    `nf_winhttp_transport.hpp carries revocation-weakening flag(s): ${result.forbiddenFound.join(', ')}`,
  );
});

test('T3: no file under bindings/transport-conformance/winhttp/include/** carries a revocation-weakening flag', () => {
  const files = shippedWinHttpFiles();
  assert.ok(files.length > 0, `expected at least one shipped file under ${WINHTTP_SHIPPED_INCLUDE_ROOT}`);
  for (const file of files) {
    const result = transportRevocationConfig(readText(file));
    assert.deepEqual(
      result.forbiddenFound,
      [],
      `${path.relative(REPO_ROOT, file)} carries revocation-weakening flag(s): ${result.forbiddenFound.join(', ')}`,
    );
  }
});

test('T3 sanity: SECURITY_FLAG_IGNORE_UNKNOWN_CA legitimately exists, just only in the unshipped test header', () => {
  const testingResult = transportRevocationConfig(readText(WINHTTP_TESTING_HEADER));
  assert.ok(
    testingResult.forbiddenFound.includes('SECURITY_FLAG_IGNORE_UNKNOWN_CA'),
    'expected SECURITY_FLAG_IGNORE_UNKNOWN_CA in tests/nf_winhttp_testing.hpp (this is not a violation: that file is never shipped)',
  );
});

test('T3 regression fixture: disabled revocation plus forbidden flags are caught', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't3-ignores-revocation.hpp.txt'));
  const result = transportRevocationConfig(source);
  assert.equal(result.hasRevocationEnable, false);
  assert.ok(result.forbiddenFound.includes('SECURITY_FLAG_IGNORE_CERT_REV_FAILED'));
  assert.ok(result.forbiddenFound.includes('SECURITY_FLAG_IGNORE_UNKNOWN_CA'));
  assert.equal(result.ok, false);
});

test('T3 regression fixture: a forbidden flag in a second (non-transport) include/ file is caught', () => {
  // Simulates the widened check: a hypothetical second shipped header, not
  // nf_winhttp_transport.hpp, carrying SECURITY_FLAG_IGNORE_CERT_REV_FAILED. The real-tree "no file
  // under include/**" test above would catch this if it existed in the repo; this fixture proves
  // the underlying checker itself flags it regardless of which shipped file it's in.
  const source = readText(path.join(TRANSPORT_FIXTURES, 't3-forbidden-flag-in-second-file.hpp.txt'));
  const result = transportRevocationConfig(source);
  assert.ok(result.forbiddenFound.includes('SECURITY_FLAG_IGNORE_CERT_REV_FAILED'));
});

test('T3 regression fixture: a SECURITY_FLAG_IGNORE_* flag outside the old fixed list of 3 is caught', () => {
  // SECURITY_FLAG_IGNORE_CERT_DATE_INVALID was never one of the 3 originally enumerated flags.
  // Proves the prefix-based match catches any SECURITY_FLAG_IGNORE_<...> identifier, not just a
  // fixed allowlist of names someone already thought to ban.
  const source = readText(path.join(TRANSPORT_FIXTURES, 't3-new-unlisted-flag.hpp.txt'));
  const result = transportRevocationConfig(source);
  assert.ok(result.forbiddenFound.includes('SECURITY_FLAG_IGNORE_CERT_DATE_INVALID'));
});

test('T3 regression fixture: a forbidden flag mentioned only in a comment is caught (literal reading)', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't3-forbidden-comment-only.hpp.txt'));
  const result = transportRevocationConfig(source);
  assert.ok(result.forbiddenFound.includes('SECURITY_FLAG_IGNORE_CERT_REV_FAILED'));
});

test('T3 regression fixture: the revocation-enable flag named only in a comment does not count', () => {
  const source = readText(path.join(TRANSPORT_FIXTURES, 't3-enable-comment-only.hpp.txt'));
  const result = transportRevocationConfig(source);
  assert.equal(result.hasRevocationEnable, false);
  assert.equal(result.ok, false);
});
