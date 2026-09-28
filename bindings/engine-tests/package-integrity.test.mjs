// Editor-free integrity tests for the Unity and Unreal SDK packages (SWARM1-BOARD gap E2).
//
// These enforce ENGINE-SDKS-REVIEW.md's ask (U1/R2) that both packages stay labelled "unverified"
// until Unity/UnrealBuildTool actually compile them, and catch the kind of package-metadata
// breakage (a moved sample, a stale asmdef reference, an inconsistent module name, mismatched or
// duplicate GUIDs once .meta files exist) that today only shows up when someone opens the editor
// (owner action #5 -- Unity/Epic sign-in is not ours to do).
//
// Plain Node: node:test, node:assert, node:fs, node:path. No dependencies. Never invokes Unity,
// dotnet or UnrealBuildTool.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {
  FIXTURES,
  UNITY_PKG_ROOT,
  UNREAL_PLUGIN_ROOT,
  REPO_ROOT,
  checkUnityPackageJson,
  checkUnitySamplesExist,
  checkUnverifiedStatus,
  checkAsmdefReferences,
  checkMetaFiles,
  checkUpluginModules,
  checkVerificationStatusSection,
  extractStageSdkStaticSourcePaths,
  readText,
} from './helpers.mjs';
import { existsSync } from 'node:fs';

const PKG = path.join(FIXTURES, 'pkg');

// ---------------------------------------------------------------------------
// Unity: the real package under bindings/unity
// ---------------------------------------------------------------------------

test('Unity package.json is valid JSON with name, version, displayName and unity', () => {
  const { pkg, missing } = checkUnityPackageJson(UNITY_PKG_ROOT);
  assert.deepEqual(missing, []);
  assert.equal(typeof pkg.name, 'string');
  assert.equal(typeof pkg.version, 'string');
  assert.equal(typeof pkg.displayName, 'string');
  assert.equal(typeof pkg.unity, 'string');
});

test('Unity package.json samples[].path all exist on disk', () => {
  const { pkg } = checkUnityPackageJson(UNITY_PKG_ROOT);
  const { samples, missing } = checkUnitySamplesExist(UNITY_PKG_ROOT, pkg);
  assert.ok(samples.length > 0, 'expected at least one sample to check');
  assert.deepEqual(missing, []);
});

test('Unity README or package.json states an unverified/never-compiled status (ENGINE-SDKS-REVIEW U1)', () => {
  const { pkg } = checkUnityPackageJson(UNITY_PKG_ROOT);
  const { found, checked } = checkUnverifiedStatus(UNITY_PKG_ROOT, pkg);
  assert.ok(checked, 'expected package.json description and/or README.md to be readable');
  assert.equal(
    found,
    true,
    'no "unverified"/"never compiled"/"not yet compiled" wording found in README.md or package.json ' +
      'description -- this is a finding for nfb-engine per ENGINE-SDKS-REVIEW.md U1, not something ' +
      'this test should paper over',
  );
});

test('every Unity .asmdef is valid JSON and its references resolve', () => {
  const result = checkAsmdefReferences(UNITY_PKG_ROOT);
  assert.ok(result.files.length > 0, 'expected at least one .asmdef under bindings/unity');
  assert.deepEqual(result.parseErrors, []);
  assert.deepEqual(result.problems, []);
});

test('Unity .meta files: zero .meta anywhere passes (Unity has never opened this package)', () => {
  const result = checkMetaFiles(UNITY_PKG_ROOT);
  assert.equal(result.state, 'none', 'expected no .meta files yet; if this package has since been opened in Unity, this test needs the other branch');
  assert.equal(result.ok, true);
});

// ---------------------------------------------------------------------------
// Unreal: the real plugin under bindings/unreal/NeuroForge
// ---------------------------------------------------------------------------

test('Unreal NeuroForge.uplugin is valid JSON and every module has a matching Build.cs class', () => {
  const result = checkUpluginModules(UNREAL_PLUGIN_ROOT);
  assert.ok(result.upluginFile, 'no .uplugin file found');
  assert.ok(result.modules.length > 0, 'expected at least one module');
  assert.deepEqual(result.problems, []);
  assert.equal(result.ok, true);
});

test('Unreal README has a verification-status section', () => {
  // bindings/unreal/README.md (the plugin-level doc, one level above NeuroForge.uplugin) is the
  // README the review means; also accept one directly inside the plugin folder if ever added there.
  const outer = checkVerificationStatusSection(path.join(REPO_ROOT, 'bindings/unreal'));
  const inner = checkVerificationStatusSection(UNREAL_PLUGIN_ROOT);
  assert.ok(outer.found || inner.found, 'expected a "Verification status" section in bindings/unreal/README.md');
});

test('Unreal stage-sdk.cmd only references statically-checkable repo paths (headers), not build output', () => {
  const cmdFile = path.join(UNREAL_PLUGIN_ROOT, 'Scripts/stage-sdk.cmd');
  assert.ok(existsSync(cmdFile), 'stage-sdk.cmd not found');
  const content = readText(cmdFile);
  const relPaths = extractStageSdkStaticSourcePaths(content);
  // Pinned, not just "> 0": stage-sdk.cmd also derives %ROOT%\target for its own build-output
  // TARGET var (when CARGO_TARGET_DIR isn't set) -- that must be excluded BY NAME
  // (STAGE_SDK_BUILD_OUTPUT_DIRS), not by silently skipping whatever happens to be missing.
  assert.deepEqual(relPaths, ['bindings\\c\\include\\neuroforge.h', 'bindings\\cpp\\include\\neuroforge.hpp']);
  assert.ok(!relPaths.some((rel) => rel.split('\\')[0] === 'target'), 'target/ (build output) leaked into the statically-checked paths');
  for (const rel of relPaths) {
    const abs = path.join(REPO_ROOT, ...rel.split('\\'));
    assert.ok(existsSync(abs), `stage-sdk.cmd references ${rel} (resolved ${abs}), which does not exist in the repo`);
  }
});

test('fixture: stage-sdk.cmd excludes build-output dirs by name, not by "skip if missing"', () => {
  // A synthetic stage-sdk.cmd-like snippet with one real header copy and one reference to a
  // made-up, definitely-nonexistent %ROOT%\nonexistent-source-dir\file.h path that is NOT in
  // STAGE_SDK_BUILD_OUTPUT_DIRS. It must still be extracted (and would fail existence), proving
  // the exclusion is a named allowlist of known build-output dirs, not a blanket "ignore missing".
  const synthetic = [
    'set "TARGET=%ROOT%\\target"',
    'copy /y "%ROOT%\\bindings\\c\\include\\neuroforge.h" "%TP%\\include\\" >nul || exit /b 1',
    'copy /y "%ROOT%\\nonexistent-source-dir\\file.h" "%TP%\\include\\" >nul || exit /b 1',
  ].join('\r\n');
  const relPaths = extractStageSdkStaticSourcePaths(synthetic);
  assert.deepEqual(relPaths, ['bindings\\c\\include\\neuroforge.h', 'nonexistent-source-dir\\file.h']);
  assert.ok(!existsSync(path.join(REPO_ROOT, 'nonexistent-source-dir', 'file.h')), 'fixture path must not actually exist');
});

// ---------------------------------------------------------------------------
// Fixtures: prove each check actually catches the regression it claims to (not vacuous passes).
// ---------------------------------------------------------------------------

test('fixture: samples[].path pointing nowhere is caught', () => {
  const root = path.join(PKG, 'unity-invalid-samples');
  const { pkg } = checkUnityPackageJson(root);
  const { missing } = checkUnitySamplesExist(root, pkg);
  assert.equal(missing.length, 1);
  assert.equal(missing[0].path, 'Samples~/DoesNotExist');
});

test('fixture: a package with no unverified/never-compiled wording anywhere is caught', () => {
  const root = path.join(PKG, 'unity-no-unverified');
  const { pkg } = checkUnityPackageJson(root);
  const { found } = checkUnverifiedStatus(root, pkg);
  assert.equal(found, false);
});

test('fixture: a package that claims "verified"/"compiled and tested" (wrong polarity) is still caught', () => {
  // Distinct from unity-no-unverified (which has no status wording at all): this fixture has
  // plenty of status-shaped wording, just none of it the required unverified/never-compiled kind,
  // so it proves the check isn't loosely matching any status-sounding word.
  const root = path.join(PKG, 'unity-claims-verified');
  const { pkg } = checkUnityPackageJson(root);
  const { found } = checkUnverifiedStatus(root, pkg);
  assert.equal(found, false);
});

test('fixture: an asmdef reference to an assembly that does not exist is caught', () => {
  const root = path.join(PKG, 'unity-bad-asmdef-ref');
  const result = checkAsmdefReferences(root);
  assert.deepEqual(result.parseErrors, []);
  assert.equal(result.problems.length, 1);
  assert.equal(result.problems[0].ref, 'TotallyUnknownAssembly');
  assert.equal(result.ok, false);
});

test('fixture: invalid JSON in an .asmdef is caught', () => {
  const root = path.join(PKG, 'unity-bad-asmdef-json');
  const result = checkAsmdefReferences(root);
  assert.equal(result.parseErrors.length, 1);
  assert.equal(result.ok, false);
});

test('fixture: zero .meta files passes (the "Unity never ran" state)', () => {
  const root = path.join(PKG, 'unity-meta-none');
  const result = checkMetaFiles(root);
  assert.equal(result.state, 'none');
  assert.equal(result.ok, true);
});

test('fixture: complete, unique 32-hex .meta GUIDs passes (the "Unity has run" state)', () => {
  const root = path.join(PKG, 'unity-meta-complete');
  const result = checkMetaFiles(root);
  assert.equal(result.state, 'present');
  assert.equal(result.ok, true);
  assert.deepEqual(result.missing, []);
  assert.deepEqual(result.duplicateGuids, []);
  assert.deepEqual(result.invalidGuid, []);
});

test('fixture: a .cs file with no .meta (once other .meta exist) is caught', () => {
  const root = path.join(PKG, 'unity-meta-missing');
  const result = checkMetaFiles(root);
  assert.equal(result.state, 'present');
  assert.equal(result.ok, false);
  assert.equal(result.missing.length, 1);
  assert.ok(result.missing[0].endsWith('Bar.cs'));
});

test('fixture: two assets sharing the same GUID are caught', () => {
  const root = path.join(PKG, 'unity-meta-duplicate');
  const result = checkMetaFiles(root);
  assert.equal(result.state, 'present');
  assert.equal(result.ok, false);
  assert.equal(result.duplicateGuids.length, 1);
  assert.equal(result.duplicateGuids[0].guid, 'd2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2');
});

test('fixture: a valid Unreal module (uplugin + matching Build.cs class) passes', () => {
  const root = path.join(PKG, 'unreal-valid');
  const result = checkUpluginModules(root);
  assert.equal(result.ok, true);
  assert.deepEqual(result.problems, []);
});

test('fixture: an Unreal Build.cs class name that does not match the module name is caught', () => {
  const root = path.join(PKG, 'unreal-mismatched-module');
  const result = checkUpluginModules(root);
  assert.equal(result.ok, false);
  assert.equal(result.problems.length, 1);
  assert.equal(result.problems[0].module, 'Alpha');
});

test('fixture: an Unreal README with no verification-status section is caught', () => {
  const root = path.join(PKG, 'unreal-no-verification');
  const result = checkVerificationStatusSection(root);
  assert.equal(result.found, false);
});

test('fixture: an Unreal README with a verification-status section passes', () => {
  const root = path.join(PKG, 'unreal-valid');
  const result = checkVerificationStatusSection(root);
  assert.equal(result.found, true);
});
