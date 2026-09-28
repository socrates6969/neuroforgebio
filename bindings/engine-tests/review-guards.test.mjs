// Static regression guards for the ENGINE-SDKS-REVIEW.md fixes landed in 26408ec ("engine-sdks:
// address review (strict dtype mapping, absolute DLL load, thread-safety fixes)") (SWARM1-BOARD
// gap E3). These are grep-level/text checks: the C# and C++ they read have never been compiled
// (dotnet is not allowed here, Unity/Unreal are not installed -- ENGINE-SDKS-REVIEW.md U1/R2), so
// this is the only coverage available today. Each guard is labelled with its review finding ID and
// is proven against a fixture that reproduces the pre-fix bug, so it can't be a vacuous pass.
//
// Plain Node: node:test, node:assert, node:fs, node:path. No dependencies.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {
  FIXTURES,
  REPO_ROOT,
  readText,
  extractBody,
  PUSH_T_SIGNATURE,
  CHUNK_ID_T_SIGNATURE,
  SHUTDOWN_MODULE_SIGNATURE,
  hasStrictDtypeCheck,
  hasCheckedLongMultiply,
  bareNameGetDllHandle,
  shutdownFreesDll,
  walOpenRequiresPersistentKey,
  ephemeralWalOnlyForTesting,
  maxStoredBytesCapped,
  readIsChunked,
  READ_RAW_SIGNATURE,
  READ_DOUBLE_SIGNATURE,
  READ_TIMESTAMPS_SIGNATURE,
} from './helpers.mjs';

const STREAMING_CS = path.join(REPO_ROOT, 'bindings/unity/Runtime/Streaming.cs');
const HASHING_CS = path.join(REPO_ROOT, 'bindings/unity/Runtime/Hashing.cs');
const RECORDING_CS = path.join(REPO_ROOT, 'bindings/unity/Runtime/Recording.cs');
const MODULE_CPP = path.join(
  REPO_ROOT,
  'bindings/unreal/NeuroForge/Source/NeuroForge/Private/NeuroForgeModule.cpp',
);

const GUARDS = path.join(FIXTURES, 'guards');

// ---------------------------------------------------------------------------
// U2: StreamWriter.Push<T> and Hashing.ChunkId<T> map typeof(T) to a dtype and throw on mismatch,
// not only a same-size sizeof(T) check (int vs float32, both 4 bytes, silently reinterpreted).
// ---------------------------------------------------------------------------

test('U2: StreamWriter.Push<T> (Streaming.cs) maps typeof(T) to a dtype, not only sizeof(T)', () => {
  const body = extractBody(readText(STREAMING_CS), PUSH_T_SIGNATURE);
  assert.ok(body, 'could not find StreamWriter.Push<T> in Streaming.cs -- has the method signature changed?');
  assert.equal(hasStrictDtypeCheck(body), true);
});

test('U2: Hashing.ChunkId<T> (Hashing.cs) maps typeof(T) to a dtype, not only sizeof(T)', () => {
  const body = extractBody(readText(HASHING_CS), CHUNK_ID_T_SIGNATURE);
  assert.ok(body, 'could not find Hashing.ChunkId<T> in Hashing.cs -- has the method signature changed?');
  assert.equal(hasStrictDtypeCheck(body), true);
});

test('U2 regression fixture: a sizeof(T)-only check is caught by hasStrictDtypeCheck', () => {
  const source = readText(path.join(GUARDS, 'u2-weak-check.cs.txt'));
  const pushBody = extractBody(source, PUSH_T_SIGNATURE);
  const chunkBody = extractBody(source, CHUNK_ID_T_SIGNATURE);
  assert.ok(pushBody, 'fixture extraction failed for Push<T>');
  assert.ok(chunkBody, 'fixture extraction failed for ChunkId<T>');
  assert.equal(hasStrictDtypeCheck(pushBody), false);
  assert.equal(hasStrictDtypeCheck(chunkBody), false);
});

// ---------------------------------------------------------------------------
// U3: StreamWriter.Push<T>'s `timestamps.Length * ChannelCount` is checked/long, not a plain int
// multiply that can silently wrap on huge inputs.
// ---------------------------------------------------------------------------

test('U3: StreamWriter.Push<T> (Streaming.cs) multiplies timestamps.Length * ChannelCount as checked long', () => {
  const body = extractBody(readText(STREAMING_CS), PUSH_T_SIGNATURE);
  assert.ok(body, 'could not find StreamWriter.Push<T> in Streaming.cs');
  assert.equal(hasCheckedLongMultiply(body), true);
});

test('U3 regression fixture: a plain int multiply is caught by hasCheckedLongMultiply', () => {
  const source = readText(path.join(GUARDS, 'u3-unchecked-multiply.cs.txt'));
  const body = extractBody(source, PUSH_T_SIGNATURE);
  assert.ok(body, 'fixture extraction failed for Push<T>');
  assert.equal(hasCheckedLongMultiply(body), false);
  // This fixture isolates U3: it keeps U2's fix, so it shouldn't also trip the U2 guard.
  assert.equal(hasStrictDtypeCheck(body), true);
});

// ---------------------------------------------------------------------------
// R1: FNeuroForgeModule::StartupModule never resolves neuroforge.dll by bare name (that would use
// the default DLL search order -- app dir, system dirs, CWD, PATH -- letting a planted DLL load).
// ---------------------------------------------------------------------------

test('R1: NeuroForgeModule.cpp loads neuroforge.dll only by absolute path, never by bare name', () => {
  const source = readText(MODULE_CPP);
  const { bare, anyCall } = bareNameGetDllHandle(source);
  assert.equal(anyCall, true, 'expected at least one FPlatformProcess::GetDllHandle call');
  assert.equal(bare, false, 'found a bare-name GetDllHandle(TEXT("neuroforge.dll")) call (DLL planting risk)');
});

test('R1 regression fixture: a bare-name GetDllHandle call is caught', () => {
  const source = readText(path.join(GUARDS, 'r1-bare-dllhandle.cpp.txt'));
  const { bare, anyCall } = bareNameGetDllHandle(source);
  assert.equal(anyCall, true);
  assert.equal(bare, true);
});

// ---------------------------------------------------------------------------
// R3: FNeuroForgeModule::ShutdownModule does not FreeDllHandle while a stream component's worker
// thread may still be inside a native read.
// ---------------------------------------------------------------------------

test('R3: NeuroForgeModule.cpp ShutdownModule does not call FreeDllHandle', () => {
  const body = extractBody(readText(MODULE_CPP), SHUTDOWN_MODULE_SIGNATURE);
  assert.ok(body, 'could not find FNeuroForgeModule::ShutdownModule in NeuroForgeModule.cpp -- has it moved/renamed?');
  assert.equal(shutdownFreesDll(body), false);
});

test('R3 regression fixture: FreeDllHandle inside ShutdownModule is caught', () => {
  const source = readText(path.join(GUARDS, 'r3-free-dll-with-workers.cpp.txt'));
  const body = extractBody(source, SHUTDOWN_MODULE_SIGNATURE);
  assert.ok(body, 'fixture extraction failed for ShutdownModule');
  assert.equal(shutdownFreesDll(body), true);
});

// ---------------------------------------------------------------------------
// G1 (nfb-engine, ABI 1.2 WAL keys 551f1bc): no default value or overload of Wal.Open may reach
// nf_wal_open_ephemeral. The only C# path to it is Wal.OpenEphemeralForTesting, and Wal.Open
// requires key32 or dpapiKeyPath.
// ---------------------------------------------------------------------------

test('G1: Wal.Open (Streaming.cs) has no default key32/dpapiKeyPath, requires one, and calls nf_wal_open (not ephemeral)', () => {
  const source = readText(STREAMING_CS);
  const result = walOpenRequiresPersistentKey(source);
  assert.equal(result.found, true, 'could not find Wal.Open in Streaming.cs -- has the signature changed?');
  assert.equal(result.noDefaultKey32, true, 'key32 has a default value (should require an explicit argument)');
  assert.equal(result.noDefaultDpapiPath, true, 'dpapiKeyPath has a default value (should require an explicit argument)');
  assert.equal(result.throwsWithoutKey, true, 'expected a throw when both key32 and dpapiKeyPath are absent');
  assert.equal(result.callsPersistentOpen, true, 'expected Wal.Open to call nf_wal_open');
  assert.equal(result.callsEphemeral, false, 'Wal.Open must never call nf_wal_open_ephemeral');
  assert.equal(result.ok, true);
});

test('G1: nf_wal_open_ephemeral (Streaming.cs) is only reachable from Wal.OpenEphemeralForTesting', () => {
  const source = readText(STREAMING_CS);
  const result = ephemeralWalOnlyForTesting(source);
  assert.equal(result.found, true, 'could not find Wal.OpenEphemeralForTesting in Streaming.cs');
  assert.equal(result.totalCalls, 1, `expected exactly one nf_wal_open_ephemeral call in the file, found ${result.totalCalls}`);
  assert.equal(result.testingCalls, 1, 'expected the one nf_wal_open_ephemeral call to be inside Wal.OpenEphemeralForTesting');
  assert.equal(result.ok, true);
});

test('G1 regression fixture: a default-null Wal.Open that falls back to nf_wal_open_ephemeral is caught', () => {
  const source = readText(path.join(GUARDS, 'g1-wal-open-defaults-to-ephemeral.cs.txt'));
  const openResult = walOpenRequiresPersistentKey(source);
  assert.equal(openResult.found, true, 'fixture extraction failed for Wal.Open');
  assert.equal(openResult.noDefaultKey32, false);
  assert.equal(openResult.noDefaultDpapiPath, false);
  assert.equal(openResult.callsEphemeral, true);
  assert.equal(openResult.ok, false);

  const ephemeralResult = ephemeralWalOnlyForTesting(source);
  // The fixture has no OpenEphemeralForTesting method at all -- the only call is from Open itself.
  assert.equal(ephemeralResult.found, false);
  assert.equal(ephemeralResult.ok, false);
});

// ---------------------------------------------------------------------------
// G2 (nfb-engine, chunked recording reads 9b5a861): MaxStoredBytesPerCall <= 2^30 (1 GiB), and the
// read loop splits into calls no larger than it.
// ---------------------------------------------------------------------------

test('G2: Recording.MaxStoredBytesPerCall (Recording.cs) rejects values over 1 GiB', () => {
  const source = readText(RECORDING_CS);
  const result = maxStoredBytesCapped(source);
  assert.equal(result.found, true, 'could not find the MaxStoredBytesPerCall property in Recording.cs');
  assert.equal(result.hasGiBCap, true, 'expected a 1 GiB (1 << 30) upper bound');
  assert.equal(result.throwsOnExcess, true, 'expected a throw when the value is out of range');
  assert.equal(result.ok, true);
});

test('G2: Recording.ReadRaw/Read(double)/ReadTimestamps (Recording.cs) chunk native calls to at most RowsPerCall/tsPerCall rows', () => {
  const source = readText(RECORDING_CS);
  for (const [name, sig] of [
    ['ReadRaw', READ_RAW_SIGNATURE],
    ['Read(double)', READ_DOUBLE_SIGNATURE],
    ['ReadTimestamps', READ_TIMESTAMPS_SIGNATURE],
  ]) {
    const result = readIsChunked(source, sig);
    assert.equal(result.found, true, `could not find ${name} in Recording.cs`);
    assert.equal(result.hasLoop, true, `${name}: expected a "for (int done = 0; done < rows;)" loop`);
    assert.equal(result.boundsEachCall, true, `${name}: expected each native call bounded by Math.Min(rows - done, RowsPerCall/tsPerCall)`);
    assert.equal(result.ok, true, name);
  }
});

test('G2 regression fixture: an unbounded cap and an unchunked ReadRaw are both caught', () => {
  const source = readText(path.join(GUARDS, 'g2-unbounded-read.cs.txt'));
  const capResult = maxStoredBytesCapped(source);
  assert.equal(capResult.found, true, 'fixture extraction failed for MaxStoredBytesPerCall');
  assert.equal(capResult.hasGiBCap, false);
  assert.equal(capResult.ok, false);

  const readResult = readIsChunked(source, READ_RAW_SIGNATURE);
  assert.equal(readResult.found, true, 'fixture extraction failed for ReadRaw');
  assert.equal(readResult.hasLoop, false);
  assert.equal(readResult.boundsEachCall, false);
  assert.equal(readResult.ok, false);
});
