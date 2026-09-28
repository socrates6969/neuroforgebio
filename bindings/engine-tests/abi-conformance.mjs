// abi-conformance.mjs: editor-free, dotnet-free check that a Unity C# P/Invoke layer matches the
// C ABI header (bindings/c/include/neuroforge.h). Plain Node (node:fs, node:path); no dependencies.
//
// Scope (see docs/hive/SWARM1-BOARD.md gap E1):
// - Parses every extern "C" prototype in the header and every [DllImport] extern in a C# tree.
// - For each C# import: the function must exist in the header, have the same param count, and
//   every param/return type must be compatible under the mapping table below (from nfb-engine's
//   Unity DESIGN.md "Marshalling rules" and Runtime/Native/NativeMethods.cs header comment).
// - Header functions with no C# binding are reported only, never a failure (the streaming sender,
//   the HTTP API client and raw callbacks are deliberately unbound in v0).
// - Also compares each value struct's own field layout (nf_buf<->NfBuf, nf_recording_info<->
//   NfRecordingInfo, nf_writer_stats<->NfWriterStats, nf_stream_chunk_fields<->NfStreamChunkFields):
//   field count, order and type, and that the C# struct is [StructLayout(LayoutKind.Sequential)].
//   A [DllImport] param naming "NfBuf" only proves the name matches nf_buf; this checks separately
//   that NfBuf's own fields still line up with nf_buf's.
//
// Mapping table for function params/returns (documented; enforced by checkParam/checkReturn):
//   C bool                          <-> C# bool with [MarshalAs(UnmanagedType.U1)] (param or return)
//   C bool*  (out)                  <-> C# [MarshalAs(UnmanagedType.U1)] out bool
//   size_t / size_t*(out)           <-> C# UIntPtr|nuint / out UIntPtr|nuint
//   fixed-width int, float          <-> matching C# width (int8_t<->sbyte, ... uint64_t<->ulong)
//   double* (buffer, see below)     <-> C# double* | double[]
//   T* (out, T scalar, non-const)   <-> C# out T | ref T
//   const T* (array, T scalar)      <-> C# T* | T[]
//   const char* / (u)int8_t* bytes  <-> C# byte[] | byte* | IntPtr
//   opaque nf_x* handle             <-> C# <X>Handle (a SafeHandle, discovered from Handles.cs) | IntPtr
//   opaque nf_x** (out handle)      <-> C# out <X>Handle
//   struct nf_x* (value struct)     <-> C# ref NfX | out NfX
//
// The double* assumption: every `double*` param in this header is a buffer with an explicit
// count/capacity sibling param, never a single-value out-double (nf_recording_read_f64/_timestamps
// fill a caller buffer; nf_timing_sha256/nf_stream_writer_push read one) -- so it is a
// pointer/array rule (double*/double[]), not an out/ref rule. functionsWithDoublePointerParams()
// exports the exact function set this holds for, so a header change to that set fails a test
// instead of silently taking on the wrong rule.
//
// Mapping table for [StructLayout] struct fields (checkStructFieldType; stricter than the
// function-param table above, since a field can't be `out`/`ref` and a managed array field would
// break blittable Sequential layout):
//   C bool field                    <-> C# byte (not [MarshalAs(U1)] bool -- nfb-engine's DESIGN)
//   size_t field                    <-> C# UIntPtr | nuint
//   fixed-width int/float/double    <-> matching C# width
//   T* field (any const-ness)       <-> C# IntPtr | <matching raw pointer, e.g. byte*/double*>
//
// This module never runs anything. It only parses text; it is not part of the SDK and sends
// nothing to any device.

import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// ---------------------------------------------------------------------------
// Small generic helpers
// ---------------------------------------------------------------------------

export function stripComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
}

// Drops preprocessor directive lines (`#ifdef __cplusplus`, `#endif // __cplusplus`, ...),
// including backslash-line-continuations, so they never glue onto the next declaration's head.
// Bug found by swarm-web-engine's real-tree run: extractExternCBlock's captured block starts
// right after `extern "C" {`, which in this header is immediately followed by `#endif // ...` on
// the very next line -- splitting by `;` alone left that "#endif" text prefixed onto
// `uint32_t nf_abi_version(void)`, and parseCPrototype threw on the resulting head.
export function stripPreprocessor(text) {
  const out = [];
  let continuing = false;
  for (const line of text.split('\n')) {
    const isDirective = continuing || /^\s*#/.test(line);
    if (isDirective) {
      continuing = line.trimEnd().endsWith('\\');
      continue;
    }
    out.push(line);
  }
  return out.join('\n');
}

export function pascalCase(snakeName) {
  return snakeName
    .split('_')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join('');
}

// Splits `str` on `sep` at bracket depth 0 (tracks (), [], {}), trimming each piece.
export function splitTopLevel(str, sep) {
  const parts = [];
  let depth = 0;
  let current = '';
  for (const ch of str) {
    if ('([{'.includes(ch)) depth++;
    else if (')]}'.includes(ch)) depth--;
    if (ch === sep && depth === 0) {
      parts.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  if (current.trim() !== '') parts.push(current.trim());
  return parts;
}

// Splits a "TYPE NAME" fragment into { type, name }, name being the trailing identifier.
export function splitTypeAndName(fragment) {
  const m = fragment.trim().match(/^(.*[\s*[\]])([A-Za-z_]\w*)$/);
  if (!m) return null;
  return { type: m[1].trim(), name: m[2] };
}

// Normalizes a raw C type string (e.g. "const struct nf_recording *") into
// { base, ptrDepth, isConst, raw }.
export function normalizeCType(raw) {
  const original = raw.trim();
  const isConst = /\bconst\b/.test(original);
  let s = original.replace(/\bconst\b/g, '').replace(/\bstruct\b/g, '');
  const ptrDepth = (s.match(/\*/g) || []).length;
  const base = s.replace(/\*/g, '').replace(/\s+/g, ' ').trim();
  return { base, ptrDepth, isConst, raw: original };
}

const FIXED_WIDTH_MAP = {
  int8_t: 'sbyte',
  uint8_t: 'byte',
  int16_t: 'short',
  uint16_t: 'ushort',
  int32_t: 'int',
  uint32_t: 'uint',
  int64_t: 'long',
  uint64_t: 'ulong',
  float: 'float',
  double: 'double',
};

// Header typedefs that are plain aliases of a fixed-width type (hashing.md sec. 5.2, header L84/94).
const RESOLVED_TYPEDEFS = { nf_status: 'int32_t', nf_dtype: 'int32_t' };

export function resolveBase(base) {
  return RESOLVED_TYPEDEFS[base] || base;
}

// ---------------------------------------------------------------------------
// C# parsing (Unity Runtime **/*.cs with [DllImport] externs, and SafeHandle subclasses)
// ---------------------------------------------------------------------------

// Finds every `[DllImport(...)] ... name(params);` statement in `text` and returns the raw
// substring after the `[DllImport(...)]` attribute up to (not including) the terminating `;`.
export function findDllImportStatements(text) {
  const statements = [];
  const attrStart = /\[DllImport\s*\(/g;
  let m;
  while ((m = attrStart.exec(text))) {
    let i = attrStart.lastIndex;
    let depth = 1;
    while (depth > 0 && i < text.length) {
      if (text[i] === '(') depth++;
      else if (text[i] === ')') depth--;
      i++;
    }
    const closeBracket = text.indexOf(']', i);
    const semi = text.indexOf(';', closeBracket);
    if (closeBracket === -1 || semi === -1) break;
    statements.push(text.slice(closeBracket + 1, semi));
    attrStart.lastIndex = semi;
  }
  return statements;
}

const CS_MODIFIER_WORDS = new Set(['internal', 'public', 'private', 'protected', 'static', 'extern', 'unsafe']);

function stripCsModifiers(head) {
  const parts = head.trim().split(/\s+/);
  let i = 0;
  while (i < parts.length && CS_MODIFIER_WORDS.has(parts[i])) i++;
  return parts.slice(i).join(' ');
}

// Parses one C# parameter fragment (attribute/modifier already may be present), e.g.
// "[MarshalAs(UnmanagedType.U1)] out bool valid" -> { marshalU1, modifier, type, name }.
export function parseCsParam(fragment) {
  let s = fragment.trim();
  let marshalU1 = false;
  const marshalMatch = s.match(/^\[MarshalAs\(UnmanagedType\.(\w+)\)\]\s*/);
  if (marshalMatch) {
    marshalU1 = marshalMatch[1] === 'U1';
    s = s.slice(marshalMatch[0].length);
  }
  let modifier = '';
  const modMatch = s.match(/^(out|ref|in)\s+/);
  if (modMatch) {
    modifier = modMatch[1];
    s = s.slice(modMatch[0].length);
  }
  const parsed = splitTypeAndName(s);
  if (!parsed) throw new Error(`abi-conformance: cannot parse C# param: "${fragment}"`);
  return { marshalU1, modifier, type: parsed.type, name: parsed.name };
}

// Parses one DllImport statement's remainder (everything after `[DllImport(...)]`, before `;`).
export function parseCsImport(rest) {
  let s = rest.trim();
  let returnMarshalU1 = false;
  const retAttr = s.match(/^\[return:\s*MarshalAs\(UnmanagedType\.(\w+)\)\]\s*/);
  if (retAttr) {
    returnMarshalU1 = retAttr[1] === 'U1';
    s = s.slice(retAttr[0].length);
  }
  s = stripCsModifiers(s);
  const parenIdx = s.indexOf('(');
  const head = s.slice(0, parenIdx).trim();
  const paramsBlock = s.slice(parenIdx + 1).replace(/\)\s*$/, '').trim();
  const headParts = splitTypeAndName(head);
  if (!headParts) throw new Error(`abi-conformance: cannot parse C# DllImport head: "${head}"`);
  const paramFrags = paramsBlock === '' ? [] : splitTopLevel(paramsBlock, ',');
  const params = paramFrags.map(parseCsParam);
  return {
    name: headParts.name,
    returnType: { type: headParts.type, marshalU1: returnMarshalU1 },
    params,
  };
}

// Parses all [DllImport] externs in one C# source file's text.
export function parseCsFile(text, filePath) {
  return findDllImportStatements(text).map((rest) => ({ ...parseCsImport(rest), file: filePath }));
}

// Parses one field of a [StructLayout] struct body, e.g. "public IntPtr Data" -> { name, type }.
// A leading attribute (e.g. a per-field [MarshalAs(...)], not used by the 4 structs today but
// tolerated for robustness) and modifiers (public/internal/...) are stripped first.
function parseCsStructField(fragment) {
  let s = fragment.trim();
  const attrMatch = s.match(/^\[[^\]]*\]\s*/);
  if (attrMatch) s = s.slice(attrMatch[0].length);
  s = stripCsModifiers(s);
  const parsed = splitTypeAndName(s);
  return parsed && { name: parsed.name, type: parsed.type };
}

// Finds every `[StructLayout(LayoutKind.X)] ... struct Name { fields }` in `text` and returns
// Map<StructName, { sequential: bool, fields: [{name, type}] }>, fields in declaration order.
export function parseCsStructs(text) {
  const structs = new Map();
  const re = /\[StructLayout\(LayoutKind\.(\w+)\)\]\s*(?:internal|public|private|protected)?\s*(?:unsafe\s+)?struct\s+(\w+)\s*\{([\s\S]*?)\}/g;
  let m;
  while ((m = re.exec(text))) {
    const [, layoutKind, name, body] = m;
    const fields = stripComments(body)
      .split(';')
      .map((f) => f.trim())
      .filter(Boolean)
      .map(parseCsStructField)
      .filter(Boolean);
    structs.set(name, { sequential: layoutKind === 'Sequential', fields });
  }
  return structs;
}

// Discovers `class <X>Handle : SafeHandle { ... ReleaseHandle() { NativeMethods.nf_x_free(...) } }`
// and returns a Map<opaque C struct name, C# handle class name>, e.g. "nf_recording" -> "RecordingHandle".
export function discoverHandleClasses(text) {
  const map = new Map();
  const re = /class\s+(\w+)\s*:\s*SafeHandle[\s\S]*?ReleaseHandle\s*\([^)]*\)\s*\{[\s\S]*?NativeMethods\.(nf_\w+)\s*\(/g;
  let m;
  while ((m = re.exec(text))) map.set(m[2].replace(/_free$/, ''), m[1]);
  return map;
}

function listCsFilesRecursive(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listCsFilesRecursive(full));
    else if (entry.isFile() && entry.name.endsWith('.cs')) out.push(full);
  }
  return out;
}

// Reads every .cs file under `dir` and returns [{ path, text }, ...].
export function loadCsDir(dir) {
  return listCsFilesRecursive(dir).map((p) => ({ path: p, text: fs.readFileSync(p, 'utf8') }));
}

// Parses a set of already-loaded C# files into { imports, handleClasses, structs }.
export function parseCsFiles(files) {
  const imports = [];
  const handleClasses = new Map();
  const structs = new Map();
  for (const { path: p, text } of files) {
    imports.push(...parseCsFile(text, p));
    for (const [struct, cls] of discoverHandleClasses(text)) handleClasses.set(struct, cls);
    for (const [name, def] of parseCsStructs(text)) structs.set(name, def);
  }
  return { imports, handleClasses, structs };
}

// ---------------------------------------------------------------------------
// Header parsing (bindings/c/include/neuroforge.h)
// ---------------------------------------------------------------------------

export function parseDefines(headerText) {
  const defines = new Map();
  const re = /^#define\s+(NF_\w+)\s+(-?\d+)/gm;
  let m;
  while ((m = re.exec(headerText))) defines.set(m[1], Number(m[2]));
  return defines;
}

// Opaque handle structs: `typedef struct nf_x nf_x;` (forward-declared, no body).
export function parseOpaqueStructs(headerText) {
  const names = new Set();
  const re = /typedef\s+struct\s+(\w+)\s+\1;/g;
  let m;
  while ((m = re.exec(headerText))) names.add(m[1]);
  return names;
}

// Value structs: `typedef struct nf_x { ... } nf_x;` (same name, with a body). Returns
// Map<structName, [{name, type: normalizeCType()}]>, fields in declaration order.
export function parseValueStructFields(headerText) {
  const result = new Map();
  const re = /typedef\s+struct\s+(\w+)\s*\{([\s\S]*?)\}\s*\1;/g;
  let m;
  while ((m = re.exec(headerText))) {
    const [, name, body] = m;
    const fields = stripComments(body)
      .split(';')
      .map((f) => f.trim())
      .filter(Boolean)
      .map((f) => {
        const parsed = splitTypeAndName(f);
        if (!parsed) throw new Error(`abi-conformance: cannot parse header struct field: "${f}"`);
        return { name: parsed.name, type: normalizeCType(parsed.type) };
      });
    result.set(name, fields);
  }
  return result;
}

// Just the value-struct names, e.g. for checkParam's ctx.valueStructs.has(...).
export function parseValueStructs(headerText) {
  return new Set(parseValueStructFields(headerText).keys());
}

function extractExternCBlock(headerText) {
  const m = headerText.match(/extern\s+"C"\s*\{([\s\S]*?)\}\s*\/\/\s*extern\s+"C"/);
  if (!m) throw new Error('abi-conformance: no extern "C" { ... } // extern "C" block found in header');
  return m[1];
}

// Drops a leading all-caps export/visibility macro (e.g. `NF_API nf_status foo(...)`), which the
// current header does not use but a future one might (cbindgen `export_expr` config).
function stripExportMacro(head) {
  const parts = head.trim().split(/\s+/);
  const first = parts[0] || '';
  if (parts.length >= 3 && /^[A-Z][A-Z0-9_]*$/.test(first)) return parts.slice(1).join(' ');
  return head;
}

// Parses one `RETURNTYPE name(params);` statement (semicolon already stripped).
export function parseCPrototype(statement) {
  const stmt = statement.trim();
  if (!stmt) return null;
  const parenIdx = stmt.indexOf('(');
  if (parenIdx === -1) return null; // not a function statement (shouldn't happen in this block)
  const head = stripExportMacro(stmt.slice(0, parenIdx).trim());
  const paramsBlock = stmt.slice(parenIdx + 1).replace(/\)\s*$/, '');
  const headParts = splitTypeAndName(head);
  if (!headParts) throw new Error(`abi-conformance: cannot parse header declaration head: "${head}"`);
  const paramsRaw = paramsBlock.trim() === 'void' || paramsBlock.trim() === '' ? [] : splitTopLevel(paramsBlock, ',');
  const params = paramsRaw.map((p) => {
    const parsed = splitTypeAndName(p);
    if (!parsed) throw new Error(`abi-conformance: cannot parse header param: "${p}"`);
    return { name: parsed.name, type: normalizeCType(parsed.type) };
  });
  return { name: headParts.name, returnType: normalizeCType(headParts.type), params };
}

// Parses the full header text into
// { functions: Map<name, proto>, defines, opaqueStructs, valueStructs, valueStructFields }.
export function parseHeader(headerText) {
  const defines = parseDefines(headerText);
  const opaqueStructs = parseOpaqueStructs(headerText);
  const valueStructFields = parseValueStructFields(headerText);
  const valueStructs = new Set(valueStructFields.keys());
  const block = stripComments(stripPreprocessor(extractExternCBlock(headerText)));
  const functions = new Map();
  for (const stmt of block.split(';')) {
    const proto = parseCPrototype(stmt);
    if (proto) functions.set(proto.name, proto);
  }
  return { functions, defines, opaqueStructs, valueStructs, valueStructFields };
}

// The exact set of header function names with at least one `double*` param -- the assumption
// behind checkParam's double-buffer rule (every double* here is a buffer with a count/capacity
// sibling, never a single out-double). Exported so a test can assert this set exactly, so a
// header change that adds/removes/repurposes a double* param is a loud, reviewed failure instead
// of silently falling under (or escaping) that rule.
export function functionsWithDoublePointerParams(header) {
  const names = [];
  for (const fn of header.functions.values()) {
    if (fn.params.some((p) => resolveBase(p.type.base) === 'double' && p.type.ptrDepth === 1)) names.push(fn.name);
  }
  return names.sort();
}

// ---------------------------------------------------------------------------
// Mapping-table rules: is a C type compatible with a C# param/return?
// ---------------------------------------------------------------------------

const ok = () => ({ ok: true });
const fail = (message) => ({ ok: false, message });

function describeCsParam(p) {
  const attr = p.marshalU1 ? '[MarshalAs(UnmanagedType.U1)] ' : '';
  const mod = p.modifier ? `${p.modifier} ` : '';
  return `${attr}${mod}${p.type}`;
}

function handleAcceptable(rbase, ctx) {
  const cls = ctx.opaqueHandleMap.get(rbase);
  return { cls, accepted: ['IntPtr', cls].filter(Boolean) };
}

// Checks one header param against its C# counterpart. `ctx` = { opaqueStructs, valueStructs, opaqueHandleMap }.
export function checkParam(cParam, csParam, ctx) {
  const { base, ptrDepth, isConst } = cParam.type;
  const rbase = resolveBase(base);
  const { type: csT, modifier: mod, marshalU1: u1 } = csParam;

  if (rbase === 'bool' && ptrDepth === 0)
    return csT === 'bool' && u1 ? ok() : fail(`bool must be [MarshalAs(UnmanagedType.U1)] bool, got ${describeCsParam(csParam)}`);
  if (rbase === 'bool' && ptrDepth === 1)
    return mod === 'out' && csT === 'bool' && u1
      ? ok()
      : fail(`bool* must be [MarshalAs(UnmanagedType.U1)] out bool, got ${describeCsParam(csParam)}`);

  if (rbase === 'size_t' && ptrDepth === 0)
    return csT === 'UIntPtr' || csT === 'nuint' ? ok() : fail(`size_t must be UIntPtr or nuint, got ${csT}`);
  if (rbase === 'size_t' && ptrDepth === 1)
    return mod === 'out' && (csT === 'UIntPtr' || csT === 'nuint')
      ? ok()
      : fail(`size_t* must be out UIntPtr/nuint, got ${describeCsParam(csParam)}`);

  // uint8_t*/char* are always treated as byte buffers (rule: byte[] <-> const char*/const uint8_t*),
  // const or not -- checked before the generic fixed-width rules below, since uint8_t is also a
  // FIXED_WIDTH_MAP entry and a non-const `uint8_t *out` (e.g. nf_recording_read's buffer) is a
  // byte* buffer, not a single scalar `out byte`.
  if ((rbase === 'char' || rbase === 'uint8_t') && ptrDepth === 1) {
    const accepted = ['byte[]', 'byte*', 'IntPtr'];
    return mod === '' && accepted.includes(csT)
      ? ok()
      : fail(`${isConst ? 'const ' : ''}${base}* must be byte[]/byte*/IntPtr, got ${describeCsParam(csParam)}`);
  }

  // Every `double*` in this header is a buffer with an explicit count/capacity sibling param
  // (never a single-value out-double), const or not: nf_recording_read_f64/_timestamps fill a
  // caller buffer, nf_timing_sha256/nf_stream_writer_push read one. DESIGN.md: "double* out,
  // size_t <-> double[] / Span<double> via fixed" -- so this is a pointer/array rule, not out/ref.
  if (rbase === 'double' && ptrDepth === 1) {
    const accepted = ['double*', 'double[]'];
    return mod === '' && accepted.includes(csT)
      ? ok()
      : fail(`${isConst ? 'const ' : ''}double* must be double*/double[], got ${describeCsParam(csParam)}`);
  }

  if (FIXED_WIDTH_MAP[rbase] && ptrDepth === 0) {
    const want = FIXED_WIDTH_MAP[rbase];
    return csT === want ? ok() : fail(`${base} must be C# ${want}, got ${csT}`);
  }
  if (FIXED_WIDTH_MAP[rbase] && ptrDepth === 1 && !isConst) {
    const want = FIXED_WIDTH_MAP[rbase];
    return (mod === 'out' || mod === 'ref') && csT === want
      ? ok()
      : fail(`${base}* (out param) must be out/ref ${want}, got ${describeCsParam(csParam)}`);
  }
  if (FIXED_WIDTH_MAP[rbase] && ptrDepth === 1 && isConst) {
    const want = FIXED_WIDTH_MAP[rbase];
    const accepted = [`${want}*`, `${want}[]`];
    return mod === '' && accepted.includes(csT)
      ? ok()
      : fail(`const ${base}* must be ${accepted.join(' or ')}, got ${describeCsParam(csParam)}`);
  }

  if (ctx.opaqueStructs.has(rbase)) {
    const { cls, accepted } = handleAcceptable(rbase, ctx);
    if (ptrDepth === 1)
      return mod === '' && accepted.includes(csT)
        ? ok()
        : fail(`${base}* must be ${accepted.join(' or ')}, got ${describeCsParam(csParam)}`);
    if (ptrDepth === 2)
      return mod === 'out' && cls && csT === cls
        ? ok()
        : fail(`${base}** must be out ${cls || '<handle>'}, got ${describeCsParam(csParam)}`);
  }

  if (ctx.valueStructs.has(rbase) && ptrDepth === 1) {
    const csStruct = pascalCase(rbase);
    return (mod === 'ref' || mod === 'out') && csT === csStruct
      ? ok()
      : fail(`${base}* must be ref/out ${csStruct}, got ${describeCsParam(csParam)}`);
  }

  return fail(`unrecognized C type "${cParam.type.raw}" -- no mapping-table rule covers it`);
}

// Checks a header return type against its C# counterpart. `cReturn` is a normalizeCType() result
// (flat: {base, ptrDepth, isConst, raw}), unlike a param's {name, type: normalizeCType()}.
export function checkReturn(cReturn, csReturn, ctx) {
  const { base, ptrDepth } = cReturn;
  const rbase = resolveBase(base);
  const { type: csT, marshalU1: u1 } = csReturn;

  if (rbase === 'void' && ptrDepth === 0) return csT === 'void' ? ok() : fail(`return must be void, got ${csT}`);
  if (rbase === 'bool' && ptrDepth === 0)
    return csT === 'bool' && u1 ? ok() : fail(`bool return must be [return: MarshalAs(UnmanagedType.U1)] bool, got ${csT}`);
  if (rbase === 'size_t' && ptrDepth === 0)
    return csT === 'UIntPtr' || csT === 'nuint' ? ok() : fail(`size_t return must be UIntPtr/nuint, got ${csT}`);
  if (FIXED_WIDTH_MAP[rbase] && ptrDepth === 0) {
    const want = FIXED_WIDTH_MAP[rbase];
    return csT === want ? ok() : fail(`${base} return must be ${want}, got ${csT}`);
  }
  if ((rbase === 'char' || rbase === 'uint8_t') && ptrDepth === 1)
    return ['IntPtr', 'byte*', 'byte[]'].includes(csT) ? ok() : fail(`${base}* return must be IntPtr/byte*, got ${csT}`);
  if (FIXED_WIDTH_MAP[rbase] && ptrDepth === 1) {
    const want = FIXED_WIDTH_MAP[rbase];
    return [`${want}*`, 'IntPtr'].includes(csT) ? ok() : fail(`${base}* return must be ${want}* or IntPtr, got ${csT}`);
  }
  if (ctx.opaqueStructs.has(rbase) && ptrDepth === 1) {
    const { accepted } = handleAcceptable(rbase, ctx);
    return accepted.includes(csT) ? ok() : fail(`${base}* return must be ${accepted.join(' or ')}, got ${csT}`);
  }
  return fail(`unrecognized C return type "${cReturn.raw}" -- no mapping-table rule covers it`);
}

// ---------------------------------------------------------------------------
// Struct layout: value-struct fields (e.g. nf_buf) vs. a C# [StructLayout(LayoutKind.Sequential)]
// struct's fields, compared by field count, order and type. A [DllImport] param/return naming
// "NfBuf" only proves the two names match; it says nothing about whether NfBuf's own fields still
// line up with nf_buf's, which this checks separately.
// ---------------------------------------------------------------------------

// Checks one struct field's C type against its C# counterpart. Unlike a function param, a struct
// field is never `out`/`ref` and never a managed array (a `byte[]`/`double[]` field breaks
// [StructLayout(Sequential)] blittability), so a pointer field accepts only IntPtr or the field's
// own raw unsafe-pointer spelling (e.g. nf_buf's `uint8_t *data` -> `IntPtr Data`,
// nf_stream_chunk_fields' `const double *lsl_timestamps` -> `double* LslTimestamps`).
export function checkStructFieldType(cType, csT) {
  const rbase = resolveBase(cType.base);
  if (rbase === 'bool' && cType.ptrDepth === 0)
    return csT === 'byte' ? ok() : fail(`bool field must be C# byte (not [MarshalAs(U1)] bool), got ${csT}`);
  if (rbase === 'size_t' && cType.ptrDepth === 0)
    return csT === 'UIntPtr' || csT === 'nuint' ? ok() : fail(`size_t field must be UIntPtr or nuint, got ${csT}`);
  if (FIXED_WIDTH_MAP[rbase] && cType.ptrDepth === 0) {
    const want = FIXED_WIDTH_MAP[rbase];
    return csT === want ? ok() : fail(`${cType.base} field must be ${want}, got ${csT}`);
  }
  if (cType.ptrDepth === 1) {
    const raw = rbase === 'char' || rbase === 'uint8_t' ? 'byte*' : FIXED_WIDTH_MAP[rbase] ? `${FIXED_WIDTH_MAP[rbase]}*` : null;
    const accepted = ['IntPtr', raw].filter(Boolean);
    return accepted.includes(csT) ? ok() : fail(`${cType.raw} field must be ${accepted.join(' or ')}, got ${csT}`);
  }
  return fail(`unrecognized struct field C type "${cType.raw}" -- no mapping-table rule covers it`);
}

// Compares one header value struct's fields against its C# [StructLayout] counterpart, in order.
export function compareStructFields(structName, cFields, csStruct) {
  if (!csStruct) return { ok: false, issues: [{ message: `no C# [StructLayout] struct ${pascalCase(structName)} found` }] };
  const issues = [];
  if (!csStruct.sequential)
    issues.push({ message: `${pascalCase(structName)} must be [StructLayout(LayoutKind.Sequential)]` });
  if (cFields.length !== csStruct.fields.length) {
    issues.push({ message: `field count mismatch: header has ${cFields.length}, C# has ${csStruct.fields.length}` });
    return { ok: false, issues };
  }
  cFields.forEach((cField, i) => {
    const csField = csStruct.fields[i];
    const expectedName = pascalCase(cField.name);
    if (csField.name !== expectedName) {
      issues.push({ index: i, message: `field ${i}: expected name ${expectedName} (from ${cField.name}), got ${csField.name}` });
      return;
    }
    const r = checkStructFieldType(cField.type, csField.type);
    if (!r.ok) issues.push({ index: i, message: `field ${i} (${cField.name}): ${r.message}` });
  });
  return { ok: issues.length === 0, issues };
}

// Compares every header value struct that has a same-named ([StructLayout]) C# counterpart.
// A header value struct with no C# struct at all (e.g. nf_http_request, used only by the unbound
// API client) is skipped, not a failure -- the same "unbound is report only" rule as for functions.
export function compareAllStructFields(header, csStructs) {
  const mismatches = [];
  for (const [structName, cFields] of header.valueStructFields) {
    const csStruct = csStructs.get(pascalCase(structName));
    if (!csStruct) continue;
    const cmp = compareStructFields(structName, cFields, csStruct);
    if (!cmp.ok) mismatches.push({ struct: structName, issues: cmp.issues });
  }
  return mismatches;
}

// ---------------------------------------------------------------------------
// Per-function comparison and whole-tree orchestration
// ---------------------------------------------------------------------------

export function compareFunctionSignature(headerFn, csFn, ctx) {
  const issues = [];
  if (headerFn.params.length !== csFn.params.length) {
    issues.push({
      index: -1,
      message: `param count mismatch: header has ${headerFn.params.length}, C# has ${csFn.params.length}`,
    });
    return { ok: false, issues };
  }
  headerFn.params.forEach((cParam, i) => {
    const r = checkParam(cParam, csFn.params[i], ctx);
    if (!r.ok) issues.push({ index: i, message: `param ${i} (${cParam.name}): ${r.message}` });
  });
  const r = checkReturn(headerFn.returnType, csFn.returnType, ctx);
  if (!r.ok) issues.push({ index: 'return', message: `return: ${r.message}` });
  return { ok: issues.length === 0, issues };
}

// Main entry point: { headerText, csFiles: [{path, text}] } -> a full conformance report.
// - mismatches: C# imports that exist in the header but disagree on arg count/types (FAILURE).
// - missingInHeader: C# imports naming a function absent from the header (FAILURE).
// - unbound: header functions with no C# import at all (REPORT ONLY, never a failure -- the
//   streaming sender, the HTTP API client and raw callbacks are deliberately unbound in v0).
// - structMismatches: value structs whose C# [StructLayout] fields disagree with the header
//   (FAILURE); a header value struct with no C# struct at all is skipped, not a failure.
export function compareAbi({ headerText, csFiles }) {
  const header = parseHeader(headerText);
  const { imports, handleClasses, structs } = parseCsFiles(csFiles);
  const ctx = { opaqueStructs: header.opaqueStructs, valueStructs: header.valueStructs, opaqueHandleMap: handleClasses };

  const mismatches = [];
  const missingInHeader = [];
  const boundNames = new Set();
  for (const csFn of imports) {
    boundNames.add(csFn.name);
    const headerFn = header.functions.get(csFn.name);
    if (!headerFn) {
      missingInHeader.push({ name: csFn.name, file: csFn.file });
      continue;
    }
    const cmp = compareFunctionSignature(headerFn, csFn, ctx);
    if (!cmp.ok) mismatches.push({ name: csFn.name, file: csFn.file, issues: cmp.issues });
  }
  const unbound = [...header.functions.keys()].filter((n) => !boundNames.has(n)).sort();
  const structMismatches = compareAllStructFields(header, structs);

  return { header, imports, handleClasses, structs, mismatches, missingInHeader, unbound, structMismatches };
}

// ---------------------------------------------------------------------------
// ABI version-rule consistency (NfAbi.h / Core.cs EnsureCompatible vs. the header's own macros)
// ---------------------------------------------------------------------------

// The C# package declares a minimum ABI (AbiMajor.AbiMinor) it was written for. That minimum must
// not exceed what the header itself declares, or the package could never be satisfied.
export function checkCsVersionRule(headerText, coreCsText) {
  const defines = parseDefines(headerText);
  const headerMajor = defines.get('NF_ABI_VERSION_MAJOR');
  const headerMinor = defines.get('NF_ABI_VERSION_MINOR');
  if (headerMajor === undefined || headerMinor === undefined)
    return { ok: false, message: 'header does not define NF_ABI_VERSION_MAJOR/NF_ABI_VERSION_MINOR' };
  const m = coreCsText.match(/AbiMajor\s*=\s*(\d+)\s*,\s*AbiMinor\s*=\s*(\d+)/);
  if (!m) return { ok: false, message: 'C# AbiMajor/AbiMinor constants not found (expected "AbiMajor = X, AbiMinor = Y")' };
  const csMajor = Number(m[1]);
  const csMinor = Number(m[2]);
  const tooHigh = csMajor > headerMajor || (csMajor === headerMajor && csMinor > headerMinor);
  return tooHigh
    ? {
        ok: false,
        message: `C# requires ABI ${csMajor}.${csMinor}+ but the header only declares ${headerMajor}.${headerMinor}`,
      }
    : { ok: true, message: `C# minimum ABI ${csMajor}.${csMinor} <= header ${headerMajor}.${headerMinor}` };
}

// Unreal has no [DllImport]s; NfAbi.h holds only the same major==/minor>= rule, defaulted from the
// header's own macros. This is a light, parseable smoke check, not a full re-derivation.
export function checkUnrealAbiRule(nfAbiHeaderText) {
  const compact = nfAbiHeaderText.replace(/\s+/g, '');
  const hasDefaults =
    compact.includes('header_major=NF_ABI_VERSION_MAJOR') && compact.includes('header_minor=NF_ABI_VERSION_MINOR');
  const hasRule = compact.includes('(packed>>16)==header_major&&((packed>>8)&0xffu)>=header_minor');
  if (!hasDefaults)
    return { ok: false, message: "NfAbi.h does not default header_major/header_minor to the header's macros" };
  if (!hasRule)
    return { ok: false, message: 'NfAbi.h abi_compatible() rule text changed; re-check major==/minor>= still holds' };
  return { ok: true, message: 'NfAbi.h reads the header macros as defaults and enforces major==, minor>=' };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

export function formatReport(report) {
  const lines = [];
  lines.push(`Header functions: ${report.header.functions.size}; C# imports: ${report.imports.length}`);
  lines.push(`Mismatches: ${report.mismatches.length}; missing-in-header: ${report.missingInHeader.length}`);
  for (const miss of report.missingInHeader) {
    lines.push(`  MISSING  ${miss.name} (${miss.file}) -- no such function in the header`);
  }
  for (const mm of report.mismatches) {
    lines.push(`  MISMATCH ${mm.name} (${mm.file})`);
    for (const issue of mm.issues) lines.push(`    - ${issue.message}`);
  }
  lines.push(`Unbound header functions (report only, not a failure): ${report.unbound.length}`);
  for (const name of report.unbound) lines.push(`  unbound  ${name}`);
  lines.push(`Struct-layout mismatches: ${report.structMismatches.length}`);
  for (const sm of report.structMismatches) {
    lines.push(`  STRUCT   ${sm.struct}`);
    for (const issue of sm.issues) lines.push(`    - ${issue.message}`);
  }
  return lines.join('\n');
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
      args[argv[i].slice(2)] = argv[i + 1];
      i++;
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.header || !args.cs) {
    console.error('usage: node abi-conformance.mjs --header <neuroforge.h path> --cs <C# dir> [--core <Core.cs path>]');
    process.exitCode = 2;
    return;
  }
  const headerText = fs.readFileSync(args.header, 'utf8');
  const csFiles = loadCsDir(args.cs);
  const report = compareAbi({ headerText, csFiles });
  console.log(formatReport(report));

  const corePath = args.core || csFiles.map((f) => f.path).find((p) => p.endsWith('Core.cs'));
  if (corePath) {
    const coreText = csFiles.find((f) => f.path === corePath)?.text ?? fs.readFileSync(corePath, 'utf8');
    const versionCheck = checkCsVersionRule(headerText, coreText);
    console.log(`\nABI version rule: ${versionCheck.ok ? 'OK' : 'FAIL'} -- ${versionCheck.message}`);
    if (!versionCheck.ok) process.exitCode = 1;
  }

  if (report.mismatches.length > 0 || report.missingInHeader.length > 0 || report.structMismatches.length > 0)
    process.exitCode = 1;
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main();
}
