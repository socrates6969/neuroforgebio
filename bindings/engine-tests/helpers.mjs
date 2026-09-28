// Shared helpers for the editor-free Unity/Unreal package-integrity and review-fix regression
// tests (SWARM1-BOARD gaps E2+E3). Plain Node, no dependencies.
//
// These checks are static: they read files with node:fs and reason about text/JSON. They never
// invoke Unity, dotnet, UnrealBuildTool or any compiler, because none of those are available or
// allowed on this machine (see ENGINE-SDKS-REVIEW.md U1/R2).
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// bindings/engine-tests -> bindings -> repo root
export const REPO_ROOT = path.join(HERE, '..', '..');
export const FIXTURES = path.join(HERE, 'fixtures');

export const UNITY_PKG_ROOT = path.join(REPO_ROOT, 'bindings/unity');
export const UNREAL_PLUGIN_ROOT = path.join(REPO_ROOT, 'bindings/unreal/NeuroForge');
export const WINHTTP_SHIPPED_INCLUDE_ROOT = path.join(REPO_ROOT, 'bindings/transport-conformance/winhttp/include');
export const WINHTTP_TESTING_HEADER = path.join(
  REPO_ROOT,
  'bindings/transport-conformance/winhttp/tests/nf_winhttp_testing.hpp',
);

/** Recursively list every file under `dir` (absolute paths). Missing dir -> []. */
export function walk(dir) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

export function readJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

export function readText(file) {
  return readFileSync(file, 'utf8');
}

/** True if any path segment of `rel` ends with '~' (Unity hides such folders from the editor:
 * no import, no .meta, ever -- e.g. Samples~, Tests~). */
function hasTildeSegment(rel) {
  return rel.split(path.sep).some((seg) => seg.endsWith('~'));
}

// ---------------------------------------------------------------------------
// Unity package.json
// ---------------------------------------------------------------------------

export const REQUIRED_PACKAGE_JSON_FIELDS = ['name', 'version', 'displayName', 'unity'];

export function checkUnityPackageJson(pkgRoot) {
  const file = path.join(pkgRoot, 'package.json');
  const pkg = readJson(file); // throws SyntaxError if not valid JSON -- caller decides how to assert
  const missing = REQUIRED_PACKAGE_JSON_FIELDS.filter(
    (k) => !(k in pkg) || pkg[k] === '' || pkg[k] === null || pkg[k] === undefined,
  );
  return { file, pkg, missing };
}

export function checkUnitySamplesExist(pkgRoot, pkg) {
  const samples = Array.isArray(pkg.samples) ? pkg.samples : [];
  const missing = samples.filter((s) => !s || !s.path || !existsSync(path.join(pkgRoot, s.path)));
  return { samples, missing };
}

const UNVERIFIED_PATTERNS = [/unverified/i, /never\s+(been\s+)?compiled/i, /not\s+(yet\s+)?compiled/i];

/** README.md or package.json "description" must say the package is unverified / never compiled,
 * per ENGINE-SDKS-REVIEW.md U1/R2 ("label the package 'unverified' until compiled"). */
export function checkUnverifiedStatus(pkgRoot, pkg) {
  const texts = [];
  if (pkg && typeof pkg.description === 'string') texts.push(pkg.description);
  const readmeFile = ['README.md', 'Readme.md', 'readme.md']
    .map((n) => path.join(pkgRoot, n))
    .find((p) => existsSync(p));
  if (readmeFile) texts.push(readText(readmeFile));
  const combined = texts.join('\n');
  const found = UNVERIFIED_PATTERNS.some((re) => re.test(combined));
  return { found, readmeFile, checked: texts.length > 0 };
}

// ---------------------------------------------------------------------------
// Unity .asmdef
// ---------------------------------------------------------------------------

// Unity/NUnit assemblies an EditMode/PlayMode test asmdef may legitimately reference without
// those assemblies existing inside this package.
export const KNOWN_UNITY_TEST_ASSEMBLIES = new Set([
  'UnityEngine.TestRunner',
  'UnityEditor.TestRunner',
  'Unity.PerformanceTesting',
  'nunit.framework',
]);

export function findAsmdefFiles(pkgRoot) {
  return walk(pkgRoot).filter((f) => f.endsWith('.asmdef'));
}

/** Every .asmdef must be valid JSON, and every entry in its "references" array must resolve to
 * either another asmdef's "name" found inside pkgRoot, or a known Unity/test assembly. */
export function checkAsmdefReferences(pkgRoot) {
  const files = findAsmdefFiles(pkgRoot);
  const parsed = [];
  const parseErrors = [];
  for (const f of files) {
    try {
      parsed.push({ file: f, json: readJson(f) });
    } catch (err) {
      parseErrors.push({ file: f, message: err.message });
    }
  }
  const byName = new Map(parsed.map(({ file, json }) => [json.name, file]));
  const problems = [];
  for (const { file, json } of parsed) {
    const refs = Array.isArray(json.references) ? json.references : [];
    for (const ref of refs) {
      if (!byName.has(ref) && !KNOWN_UNITY_TEST_ASSEMBLIES.has(ref)) {
        problems.push({ file, ref });
      }
    }
  }
  return { files, parsed, parseErrors, problems, ok: parseErrors.length === 0 && problems.length === 0 };
}

// ---------------------------------------------------------------------------
// Unity .meta / GUIDs
// ---------------------------------------------------------------------------

const GUID_LINE = /^guid:\s*([0-9a-fA-F]{32})\s*$/m;

/**
 * Unity has never opened this package (no editor on this machine), so today there are zero .meta
 * files anywhere under pkgRoot -- that must PASS. If any .meta file exists (a future state, once
 * someone opens the package in Unity), every .cs/.asmdef OUTSIDE a tilde-suffixed folder
 * (Samples~, Tests~ are hidden from Unity and never get a .meta) must have one, and every GUID
 * found must be well-formed 32-hex and unique.
 */
export function checkMetaFiles(pkgRoot) {
  const all = walk(pkgRoot);
  const relevant = all.filter((f) => {
    const rel = path.relative(pkgRoot, f);
    return !hasTildeSegment(rel) && (f.endsWith('.cs') || f.endsWith('.asmdef'));
  });
  const metaFiles = all.filter((f) => f.endsWith('.meta'));

  if (metaFiles.length === 0) {
    return { state: 'none', ok: true, missing: [], duplicateGuids: [], invalidGuid: [] };
  }

  const metaSet = new Set(metaFiles);
  const missing = relevant.filter((f) => !metaSet.has(`${f}.meta`));

  const owners = new Map(); // guid -> first .meta file that had it
  const duplicateGuids = [];
  const invalidGuid = [];
  for (const m of metaFiles) {
    const match = GUID_LINE.exec(readText(m));
    if (!match) {
      invalidGuid.push(m);
      continue;
    }
    const guid = match[1].toLowerCase();
    if (owners.has(guid)) duplicateGuids.push({ guid, files: [owners.get(guid), m] });
    else owners.set(guid, m);
  }

  const ok = missing.length === 0 && duplicateGuids.length === 0 && invalidGuid.length === 0;
  return { state: 'present', ok, missing, duplicateGuids, invalidGuid };
}

// ---------------------------------------------------------------------------
// Unreal .uplugin / Build.cs / README
// ---------------------------------------------------------------------------

export function findUpluginFile(pluginRoot) {
  return walk(pluginRoot).find((f) => f.endsWith('.uplugin'));
}

/** Every Modules[].Name in the .uplugin must have Source/<Name>/<Name>.Build.cs whose
 * `class <Name> : ModuleRules` matches the module name. */
export function checkUpluginModules(pluginRoot) {
  const upluginFile = findUpluginFile(pluginRoot);
  if (!upluginFile) return { upluginFile: null, modules: [], problems: [{ reason: 'no .uplugin file found' }] };
  const plugin = readJson(upluginFile);
  const modules = Array.isArray(plugin.Modules) ? plugin.Modules : [];
  const problems = [];
  for (const mod of modules) {
    const name = mod && mod.Name;
    if (!name) {
      problems.push({ module: mod, reason: 'module entry has no Name' });
      continue;
    }
    const buildCsFile = path.join(pluginRoot, 'Source', name, `${name}.Build.cs`);
    if (!existsSync(buildCsFile)) {
      problems.push({ module: name, reason: `missing ${path.relative(pluginRoot, buildCsFile)}` });
      continue;
    }
    const content = readText(buildCsFile);
    const classRe = new RegExp(`\\bclass\\s+${name}\\s*:\\s*ModuleRules\\b`);
    if (!classRe.test(content)) {
      problems.push({ module: name, reason: `${path.relative(pluginRoot, buildCsFile)} has no "class ${name} : ModuleRules"` });
    }
  }
  return { upluginFile, plugin, modules, problems, ok: problems.length === 0 };
}

/** README.md must have an explicit "Verification status" section (the review asked both SDKs to
 * carry one until the code has been compiled). */
export function checkVerificationStatusSection(root) {
  const readmeFile = ['README.md', 'Readme.md', 'readme.md']
    .map((n) => path.join(root, n))
    .find((p) => existsSync(p));
  if (!readmeFile) return { found: false, readmeFile: null };
  return { found: /verification status/i.test(readText(readmeFile)), readmeFile };
}

/** Build-output directories stage-sdk.cmd itself derives from %ROOT% (e.g. `set "TARGET=%ROOT%\target"`
 * when CARGO_TARGET_DIR isn't set) rather than a file it copies FROM the checked-out repo. Named
 * explicitly here -- not "skip whatever happens to be missing" -- so a genuinely broken/renamed
 * source path still fails loudly; cargo's target/ is the only one this script writes to today. */
export const STAGE_SDK_BUILD_OUTPUT_DIRS = new Set(['target']);

/** Extract every repo-relative path stage-sdk.cmd copies FROM the checked-out repo (via %ROOT%),
 * as opposed to build output paths (%SRC%, %TARGET%, and %ROOT%\target itself -- see
 * STAGE_SDK_BUILD_OUTPUT_DIRS), which don't exist until cargo has run and so aren't statically
 * checkable. */
export function extractStageSdkStaticSourcePaths(cmdContent) {
  const re = /%ROOT%\\([^"%]+)"/g;
  const out = [];
  let m;
  while ((m = re.exec(cmdContent)) !== null) {
    const rel = m[1];
    const firstSegment = rel.split('\\')[0];
    if (STAGE_SDK_BUILD_OUTPUT_DIRS.has(firstSegment)) continue;
    out.push(rel);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Static text guards (E3): review-fix regressions, C#/C++ source read as text.
// ---------------------------------------------------------------------------

/** Remove `// ...` line comments so a guard can't be fooled by a comment that merely *mentions*
 * the risky call (e.g. NeuroForgeModule.cpp's ShutdownModule explains in a comment why it does
 * NOT call FreeDllHandle). Good enough for the controlled snippets these guards read; there are
 * no string literals containing "//" in the checked bodies. */
export function stripLineComments(code) {
  return code
    .split('\n')
    .map((line) => {
      const i = line.indexOf('//');
      return i === -1 ? line : line.slice(0, i);
    })
    .join('\n');
}

/** Extract the brace-balanced body of the first method/function whose signature matches
 * `signatureRegex` (matched up to and including its opening parenthesis), or null if not found. */
export function extractBody(source, signatureRegex) {
  const match = signatureRegex.exec(source);
  if (!match) return null;
  const openBrace = source.indexOf('{', match.index + match[0].length);
  if (openBrace === -1) return null;
  let depth = 0;
  for (let i = openBrace; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    else if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(openBrace, i + 1);
    }
  }
  return null;
}

export const PUSH_T_SIGNATURE = /public\s+int\s+Push<T>\s*\(/;
export const CHUNK_ID_T_SIGNATURE = /public\s+static\s+string\s+ChunkId<T>\s*\(/;
export const STARTUP_MODULE_SIGNATURE = /void\s+FNeuroForgeModule::StartupModule\s*\(\s*\)/;
export const SHUTDOWN_MODULE_SIGNATURE = /void\s+FNeuroForgeModule::ShutdownModule\s*\(\s*\)/;

/** U2: the method body must call NeuroForgeCore.CheckElementType<T>(...), which maps typeof(T) to
 * an exact Dtype and throws on mismatch. A same-size `sizeof(T) == ItemSize(dtype)` check alone
 * (the pre-fix bug: int vs float32, both 4 bytes, silently reinterpreted) does not satisfy this. */
export function hasStrictDtypeCheck(methodBody) {
  return !!methodBody && /CheckElementType<T>/.test(methodBody);
}

/** U3: Push<T>'s length check must multiply as `checked` `long`, not a plain `int` multiply that
 * can silently wrap on huge inputs. */
export function hasCheckedLongMultiply(methodBody) {
  return (
    !!methodBody &&
    /checked\s*\(\s*\(long\)\s*timestamps\.Length\s*\*\s*ChannelCount\s*\)/.test(methodBody)
  );
}

/** R1: StartupModule must never resolve the DLL by bare name (that uses the default search order:
 * app dir, system dirs, CWD, PATH -- DLL planting). It must still call GetDllHandle at all (with a
 * computed absolute path), so an empty file doesn't vacuously pass. */
export function bareNameGetDllHandle(source) {
  const stripped = stripLineComments(source);
  const bare = /GetDllHandle\s*\(\s*TEXT\(\s*"neuroforge\.dll"\s*\)\s*\)/.test(stripped);
  const anyCall = /GetDllHandle\s*\(/.test(stripped);
  return { bare, anyCall };
}

/** R3: ShutdownModule must not call FreeDllHandle while a worker thread may still be inside a
 * native read. */
export function shutdownFreesDll(methodBody) {
  if (!methodBody) return false;
  return /FreeDllHandle\s*\(/.test(stripLineComments(methodBody));
}

// ---------------------------------------------------------------------------
// G1: Wal.Open requires a persistent key; only Wal.OpenEphemeralForTesting may reach
// nf_wal_open_ephemeral (ABI 1.2 WAL keys, 551f1bc).
// ---------------------------------------------------------------------------

export const WAL_OPEN_SIGNATURE = /public\s+static\s+Wal\s+Open\s*\(/;
export const WAL_OPEN_EPHEMERAL_SIGNATURE = /public\s+static\s+Wal\s+OpenEphemeralForTesting\s*\(/;

/** Everything from `signatureRegex`'s match up to (but not including) the following method body's
 * opening brace -- i.e. the return type through the parameter list, so a caller can inspect
 * parameter defaults. */
export function extractDeclaration(source, signatureRegex) {
  const match = signatureRegex.exec(source);
  if (!match) return null;
  const openBrace = source.indexOf('{', match.index + match[0].length);
  if (openBrace === -1) return null;
  return source.slice(match.index, openBrace);
}

/** G1a: Wal.Open's `key32`/`dpapiKeyPath` parameters must have no default value (so a caller can't
 * accidentally omit both), it must throw when both are absent, and it must call `nf_wal_open` (the
 * persistent-key path) and never `nf_wal_open_ephemeral`. */
export function walOpenRequiresPersistentKey(source) {
  const decl = extractDeclaration(source, WAL_OPEN_SIGNATURE);
  const body = extractBody(source, WAL_OPEN_SIGNATURE);
  if (!decl || !body) return { found: false, ok: false };
  const stripped = stripLineComments(body);
  const noDefaultKey32 = !/key32\s*=\s*null/.test(decl);
  const noDefaultDpapiPath = !/dpapiKeyPath\s*=\s*null/.test(decl);
  const throwsWithoutKey =
    /key32\s*==\s*null/.test(stripped) && /dpapiKeyPath/.test(stripped) && /throw/.test(stripped);
  const callsPersistentOpen = /\bnf_wal_open\(/.test(stripped);
  const callsEphemeral = /nf_wal_open_ephemeral\(/.test(stripped);
  return {
    found: true,
    ok: noDefaultKey32 && noDefaultDpapiPath && throwsWithoutKey && callsPersistentOpen && !callsEphemeral,
    noDefaultKey32,
    noDefaultDpapiPath,
    throwsWithoutKey,
    callsPersistentOpen,
    callsEphemeral,
  };
}

/** G1b: `nf_wal_open_ephemeral` must be called from exactly one place in the file --
 * Wal.OpenEphemeralForTesting -- and nowhere else (in particular not from Wal.Open). */
export function ephemeralWalOnlyForTesting(source) {
  const stripped = stripLineComments(source);
  const totalCalls = (stripped.match(/nf_wal_open_ephemeral\(/g) || []).length;
  const testingBody = extractBody(source, WAL_OPEN_EPHEMERAL_SIGNATURE);
  const testingCalls = testingBody
    ? (stripLineComments(testingBody).match(/nf_wal_open_ephemeral\(/g) || []).length
    : 0;
  return {
    found: !!testingBody,
    ok: !!testingBody && totalCalls === 1 && testingCalls === 1,
    totalCalls,
    testingCalls,
  };
}

// ---------------------------------------------------------------------------
// G2: Recording reads are chunked -- MaxStoredBytesPerCall <= 1 GiB, and every read loop splits
// into calls no larger than it (9b5a861).
// ---------------------------------------------------------------------------

export const MAX_STORED_BYTES_PROPERTY_SIGNATURE = /public\s+int\s+MaxStoredBytesPerCall\b/;
export const READ_RAW_SIGNATURE = /public\s+int\s+ReadRaw\s*\(/;
export const READ_DOUBLE_SIGNATURE =
  /public\s+int\s+Read\s*\(\s*long\s+start\s*,\s*int\s+count\s*,\s*Span<double>\s+dest\s*\)/;
export const READ_TIMESTAMPS_SIGNATURE = /public\s+int\s+ReadTimestamps\s*\(/;

/** G2a: the MaxStoredBytesPerCall setter must reject anything over 1 GiB (2^30), the core's own
 * hard cap on a single native read. */
export function maxStoredBytesCapped(source) {
  const body = extractBody(source, MAX_STORED_BYTES_PROPERTY_SIGNATURE);
  if (!body) return { found: false, ok: false };
  const hasGiBCap = /1\s*<<\s*30/.test(body) || /1073741824/.test(body);
  const throwsOnExcess = /throw/.test(body);
  return { found: true, ok: hasGiBCap && throwsOnExcess, hasGiBCap, throwsOnExcess };
}

/** G2b: a read method must loop, each native call bounded to at most RowsPerCall (or the
 * timestamps equivalent, tsPerCall) rows, instead of handing the whole request to one native call. */
export function readIsChunked(source, signatureRegex) {
  const body = extractBody(source, signatureRegex);
  if (!body) return { found: false, ok: false };
  const stripped = stripLineComments(body);
  const hasLoop = /for\s*\(\s*int\s+done\s*=\s*0\s*;\s*done\s*<\s*rows\s*;\s*\)/.test(stripped);
  const boundsEachCall = /Math\.Min\(\s*rows\s*-\s*done\s*,\s*(RowsPerCall|tsPerCall)\s*\)/.test(stripped);
  return { found: true, ok: hasLoop && boundsEachCall, hasLoop, boundsEachCall };
}

// ---------------------------------------------------------------------------
// T1/T2/T3 (nfb-security, WinHTTP transport packaging, cb0fd54/b976337): the test-only trust-bypass
// hook (tests/nf_winhttp_testing.hpp) must never ship, and the shipped transport must not disable
// certificate revocation checking. "Shipped" = bindings/transport-conformance/winhttp/include/**;
// tests/ is never shipped.
// ---------------------------------------------------------------------------

/** List every file under WINHTTP_SHIPPED_INCLUDE_ROOT (currently just nf_winhttp_transport.hpp,
 * but this walks the directory so a future added header is covered automatically). */
export function shippedWinHttpFiles() {
  return walk(WINHTTP_SHIPPED_INCLUDE_ROOT);
}

/** Strip `//` line comments, `/* ... *\/` block comments, and the string-literal text of `#error`
 * and `#pragma message(...)` diagnostics (developer-facing compiler messages, not linked code --
 * same reasoning as stripLineComments: a diagnostic that merely *names* the test header, to warn a
 * developer away from misusing a macro, is not "shipping" it). */
export function stripCppNoise(code) {
  let out = stripLineComments(code);
  out = out.replace(/\/\*[\s\S]*?\*\//g, '');
  out = out.replace(/#\s*error\s*"[^"]*"/g, '#error');
  out = out.replace(/#\s*pragma\s+message\s*\([^)]*\)/g, '#pragma message');
  return out;
}

/** T1: no shipped file DEFINES `struct TestAccess` (`struct TestAccess {` or `struct
 * ns::TestAccess {`) -- only a forward declaration (`struct TestAccess;`) is allowed. Shipping a
 * definition would ship the test-only trust-bypass hook's friend-access point. */
export function definesTestAccess(source) {
  const stripped = stripCppNoise(source);
  const re = /struct\s+(?:\w+::)?TestAccess\b/g;
  const matches = [];
  let m;
  while ((m = re.exec(stripped)) !== null) {
    const rest = stripped.slice(m.index + m[0].length);
    const nextBrace = rest.indexOf('{');
    const nextSemi = rest.indexOf(';');
    const isDefinition = nextBrace !== -1 && (nextSemi === -1 || nextBrace < nextSemi);
    matches.push({ text: m[0], isDefinition });
  }
  return { matches, definesIt: matches.some((x) => x.isDefinition) };
}

/** T2 (literal reading, nfb-engine ruling): a plain substring match for "nf_winhttp_testing" over
 * the RAW file bytes -- no stripping of comments, #error text or #pragma message strings. A
 * shipped file must not mention the test-only header's name anywhere, including in a comment. */
export function mentionsTestingHeader(source) {
  const includesIt = /#\s*include\s*["<][^">]*nf_winhttp_testing[^">]*[">]/.test(source);
  const mentionsIt = source.includes('nf_winhttp_testing');
  return { includesIt, mentionsIt, violates: includesIt || mentionsIt };
}

// Any SECURITY_FLAG_IGNORE_<...> identifier is forbidden (not just the 3 originally enumerated --
// nfb-security's extended ruling), plus this one WINHTTP_OPTION that isn't under that prefix.
const SECURITY_FLAG_IGNORE_PREFIX_RE = /SECURITY_FLAG_IGNORE_[A-Z0-9_]*/g;
const WINHTTP_OPTION_FORBIDDEN = 'WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE';

/** T3 (nfb-security, extended ruling): a literal raw substring match over the file bytes -- no
 * comment stripping, same as T2 -- for WINHTTP_ENABLE_SSL_REVOCATION (required, and only checked
 * for nf_winhttp_transport.hpp) and for any SECURITY_FLAG_IGNORE_* identifier or
 * WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE (forbidden in every shipped file, comments
 * included). Test-only ignore options may appear only under tests/ (excluded from "shipped"). */
export function transportRevocationConfig(source) {
  // The enable flag must appear in code: a comment or #error text naming it does not count.
  const hasRevocationEnable = stripCppNoise(source).includes('WINHTTP_ENABLE_SSL_REVOCATION');
  const forbiddenFound = [];
  const seen = new Set();
  let m;
  SECURITY_FLAG_IGNORE_PREFIX_RE.lastIndex = 0;
  while ((m = SECURITY_FLAG_IGNORE_PREFIX_RE.exec(source)) !== null) {
    if (!seen.has(m[0])) {
      seen.add(m[0]);
      forbiddenFound.push(m[0]);
    }
  }
  if (source.includes(WINHTTP_OPTION_FORBIDDEN) && !seen.has(WINHTTP_OPTION_FORBIDDEN)) {
    forbiddenFound.push(WINHTTP_OPTION_FORBIDDEN);
  }
  return { hasRevocationEnable, forbiddenFound, ok: hasRevocationEnable && forbiddenFound.length === 0 };
}
