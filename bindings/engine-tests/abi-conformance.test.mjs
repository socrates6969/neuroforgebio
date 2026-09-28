// abi-conformance.test.mjs: node:test suite for abi-conformance.mjs. Plain Node (node:test,
// node:assert, node:fs, node:path); no dependencies. Run with:
//   node --test bindings/engine-tests/abi-conformance.test.mjs
//
// Two kinds of coverage (docs/hive/SWARM1-BOARD.md gap E1):
// 1. Small crafted fixtures (fixtures/abi/) with one planted mismatch each, proving the checker
//    fails for the right reason and only that reason.
// 2. The real tree: bindings/c/include/neuroforge.h against bindings/unity/Runtime, which must
//    come back with zero mismatches and zero missing-in-header entries.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  pascalCase,
  splitTopLevel,
  splitTypeAndName,
  normalizeCType,
  stripPreprocessor,
  parseHeader,
  loadCsDir,
  compareAbi,
  checkCsVersionRule,
  checkUnrealAbiRule,
  functionsWithDoublePointerParams,
  formatReport,
} from './abi-conformance.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(HERE, 'fixtures', 'abi');
const FIXTURE_HEADER = fs.readFileSync(path.join(FIXTURES, 'header.h'), 'utf8');

const REAL_HEADER_PATH = path.join(HERE, '..', 'c', 'include', 'neuroforge.h');
const REAL_UNITY_RUNTIME = path.join(HERE, '..', 'unity', 'Runtime');
const REAL_CORE_CS = path.join(REAL_UNITY_RUNTIME, 'Core.cs');
const REAL_UNREAL_ABI_H = path.join(
  HERE,
  '..',
  'unreal',
  'NeuroForge',
  'Source',
  'NeuroForge',
  'Public',
  'NeuroForgeCore',
  'NfAbi.h',
);

function fixtureReport(caseDir) {
  const csFiles = loadCsDir(path.join(FIXTURES, caseDir));
  return compareAbi({ headerText: FIXTURE_HEADER, csFiles });
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

describe('small helpers', () => {
  test('pascalCase follows the header-to-C#-struct-name convention', () => {
    assert.equal(pascalCase('nf_buf'), 'NfBuf');
    assert.equal(pascalCase('nf_stream_chunk_fields'), 'NfStreamChunkFields');
    assert.equal(pascalCase('nf_recording_info'), 'NfRecordingInfo');
  });

  test('splitTopLevel ignores commas inside nested brackets/attributes', () => {
    assert.deepEqual(splitTopLevel('a, b', ','), ['a', 'b']);
    assert.deepEqual(splitTopLevel('[MarshalAs(UnmanagedType.U1)] out bool valid, byte[] id', ','), [
      '[MarshalAs(UnmanagedType.U1)] out bool valid',
      'byte[] id',
    ]);
  });

  test('splitTypeAndName finds the trailing identifier regardless of * spacing', () => {
    assert.deepEqual(splitTypeAndName('const char *name'), { type: 'const char *', name: 'name' });
    assert.deepEqual(splitTypeAndName('ulong* shape'), { type: 'ulong*', name: 'shape' });
    assert.deepEqual(splitTypeAndName('byte[] id'), { type: 'byte[]', name: 'id' });
  });

  test('stripPreprocessor drops directive lines, including backslash-continuations, but keeps everything else', () => {
    const input = ['#endif // __cplusplus', '', 'uint32_t nf_abi_version(void);', '#define X 1 \\', '  + 2', 'void f(void);'].join(
      '\n',
    );
    assert.equal(stripPreprocessor(input), ['', 'uint32_t nf_abi_version(void);', 'void f(void);'].join('\n'));
  });

  test('normalizeCType strips const/struct and counts pointer depth', () => {
    assert.deepEqual(normalizeCType('const struct nf_recording *'), {
      base: 'nf_recording',
      ptrDepth: 1,
      isConst: true,
      raw: 'const struct nf_recording *',
    });
    assert.deepEqual(normalizeCType('struct nf_recording **'), {
      base: 'nf_recording',
      ptrDepth: 2,
      isConst: false,
      raw: 'struct nf_recording **',
    });
  });
});

// ---------------------------------------------------------------------------
// Header parsing (fixture)
// ---------------------------------------------------------------------------

describe('parseHeader (fixture)', () => {
  const header = parseHeader(FIXTURE_HEADER);

  test('finds every extern "C" function', () => {
    assert.deepEqual(
      [...header.functions.keys()].sort(),
      ['nf_widget_free', 'nf_widget_get_score', 'nf_widget_is_ready', 'nf_widget_open', 'nf_widget_read'].sort(),
    );
  });

  test('classifies nf_widget as opaque and nf_buf as a value struct', () => {
    assert.ok(header.opaqueStructs.has('nf_widget'));
    assert.ok(header.valueStructs.has('nf_buf'));
    assert.ok(!header.opaqueStructs.has('nf_buf'));
  });

  test('reads the ABI version defines', () => {
    assert.equal(header.defines.get('NF_ABI_VERSION_MAJOR'), 1);
    assert.equal(header.defines.get('NF_ABI_VERSION_MINOR'), 1);
  });
});

// ---------------------------------------------------------------------------
// Fixtures: one planted mismatch per rule
// ---------------------------------------------------------------------------

describe('fixtures/abi: planted mismatches', () => {
  test('ok: a correct binding produces zero mismatches and zero missing functions', () => {
    const report = fixtureReport('ok');
    assert.deepEqual(report.mismatches, []);
    assert.deepEqual(report.missingInHeader, []);
    assert.equal(report.imports.length, 5);
  });

  test('wrong-arg-count: dropping a param is a count mismatch on that function only', () => {
    const report = fixtureReport('wrong-arg-count');
    assert.equal(report.mismatches.length, 1);
    assert.equal(report.mismatches[0].name, 'nf_widget_read');
    assert.match(report.mismatches[0].issues[0].message, /param count mismatch: header has 6, C# has 5/);
    assert.deepEqual(report.missingInHeader, []);
  });

  test('size-t-as-int: size_t declared as C# int is a param type mismatch', () => {
    const report = fixtureReport('size-t-as-int');
    assert.equal(report.mismatches.length, 1);
    assert.equal(report.mismatches[0].name, 'nf_widget_read');
    const messages = report.mismatches[0].issues.map((i) => i.message).join('\n');
    assert.match(messages, /param 4 \(capacity\)/);
    assert.match(messages, /size_t must be UIntPtr or nuint/);
  });

  test('bool-without-u1: a bool return missing [return: MarshalAs(U1)] is a return mismatch', () => {
    const report = fixtureReport('bool-without-u1');
    assert.equal(report.mismatches.length, 1);
    assert.equal(report.mismatches[0].name, 'nf_widget_is_ready');
    const messages = report.mismatches[0].issues.map((i) => i.message).join('\n');
    assert.match(messages, /return:/);
    assert.match(messages, /MarshalAs\(UnmanagedType\.U1\)\] bool/);
  });

  test('missing-function: a C# import naming a function absent from the header is reported', () => {
    const report = fixtureReport('missing-function');
    assert.deepEqual(report.mismatches, []);
    assert.equal(report.missingInHeader.length, 1);
    assert.equal(report.missingInHeader[0].name, 'nf_widget_frobnicate');
  });

  test('wrong-return-type: nf_status returned as C# long instead of int is a return mismatch', () => {
    const report = fixtureReport('wrong-return-type');
    assert.equal(report.mismatches.length, 1);
    assert.equal(report.mismatches[0].name, 'nf_widget_open');
    const messages = report.mismatches[0].issues.map((i) => i.message).join('\n');
    assert.match(messages, /return: nf_status return must be int, got long/);
  });

  test('struct-fields-reordered: NfBuf with Len before Data is a struct-layout mismatch, no function-level noise', () => {
    const report = fixtureReport('struct-fields-reordered');
    assert.deepEqual(report.mismatches, []);
    assert.deepEqual(report.missingInHeader, []);
    assert.equal(report.structMismatches.length, 1);
    assert.equal(report.structMismatches[0].struct, 'nf_buf');
    const messages = report.structMismatches[0].issues.map((i) => i.message).join('\n');
    assert.match(messages, /field 0: expected name Data \(from data\), got Len/);
    assert.match(messages, /field 1: expected name Len \(from len\), got Data/);
  });

  test('struct-field-missing: NfBuf missing Len is a struct field-count mismatch, no function-level noise', () => {
    const report = fixtureReport('struct-field-missing');
    assert.deepEqual(report.mismatches, []);
    assert.deepEqual(report.missingInHeader, []);
    assert.equal(report.structMismatches.length, 1);
    assert.equal(report.structMismatches[0].struct, 'nf_buf');
    assert.match(report.structMismatches[0].issues[0].message, /field count mismatch: header has 2, C# has 1/);
  });

  test('ok: NfBuf struct layout also matches (Sequential, field count/order/type)', () => {
    const report = fixtureReport('ok');
    assert.deepEqual(report.structMismatches, []);
  });

  test('formatReport renders a human-readable summary for a mismatching fixture', () => {
    const text = formatReport(fixtureReport('wrong-arg-count'));
    assert.match(text, /MISMATCH nf_widget_read/);
    assert.match(text, /param count mismatch/);
  });
});

// ---------------------------------------------------------------------------
// The real tree: bindings/c/include/neuroforge.h vs. bindings/unity/Runtime
// ---------------------------------------------------------------------------

describe('real tree: neuroforge.h vs. Unity Runtime', () => {
  const headerText = fs.readFileSync(REAL_HEADER_PATH, 'utf8');
  const csFiles = loadCsDir(REAL_UNITY_RUNTIME);
  const report = compareAbi({ headerText, csFiles });

  test('every bound function matches the header (arg count, types, return)', () => {
    if (report.mismatches.length > 0) {
      const detail = report.mismatches.map((m) => `${m.name}: ${m.issues.map((i) => i.message).join('; ')}`).join('\n');
      assert.fail(`unexpected ABI mismatches:\n${detail}`);
    }
  });

  test('every C# import names a real header function', () => {
    assert.deepEqual(report.missingInHeader, []);
  });

  test('the parser actually found DllImport declarations (a silent parse failure would pass vacuously)', () => {
    const rawCount = csFiles.reduce((n, f) => n + (f.text.match(/\[DllImport/g) || []).length, 0);
    assert.ok(rawCount > 0, 'expected at least one [DllImport] in bindings/unity/Runtime');
    assert.equal(report.imports.length, rawCount, 'parsed import count should match a raw [DllImport] count');
  });

  test('the streaming sender and API client are unbound in v0 (report only)', () => {
    assert.ok(report.unbound.includes('nf_sender_run'));
    assert.ok(report.unbound.includes('nf_api_client_request'));
    assert.ok(!report.unbound.includes('nf_recording_open'), 'nf_recording_open should be bound');
  });

  test('the 4 bound value structs are found and their field layouts match the header', () => {
    const bound = ['NfBuf', 'NfRecordingInfo', 'NfWriterStats', 'NfStreamChunkFields'];
    assert.deepEqual([...report.structs.keys()].sort(), [...bound].sort());
    if (report.structMismatches.length > 0) {
      const detail = report.structMismatches
        .map((m) => `${m.struct}: ${m.issues.map((i) => i.message).join('; ')}`)
        .join('\n');
      assert.fail(`unexpected struct-layout mismatches:\n${detail}`);
    }
  });

  test('every double* param function is exactly the expected set (the double-buffer rule scope)', () => {
    assert.deepEqual(
      functionsWithDoublePointerParams(report.header),
      ['nf_recording_read_f64', 'nf_recording_read_timestamps', 'nf_stream_writer_push', 'nf_timing_sha256'].sort(),
    );
  });
});

// ---------------------------------------------------------------------------
// ABI version-rule consistency (Core.cs EnsureCompatible / Unreal NfAbi.h vs. the header macros)
// ---------------------------------------------------------------------------

describe('ABI version-rule consistency', () => {
  test("Unity Core.cs's minimum ABI does not exceed what the header declares", () => {
    const headerText = fs.readFileSync(REAL_HEADER_PATH, 'utf8');
    const coreText = fs.readFileSync(REAL_CORE_CS, 'utf8');
    const result = checkCsVersionRule(headerText, coreText);
    assert.equal(result.ok, true, result.message);
  });

  test('Unreal NfAbi.h enforces major==/minor>=, defaulted from the header macros', () => {
    const nfAbiText = fs.readFileSync(REAL_UNREAL_ABI_H, 'utf8');
    const result = checkUnrealAbiRule(nfAbiText);
    assert.equal(result.ok, true, result.message);
  });
});
