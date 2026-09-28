// hw-guard: zero-dependency stimulation-exclusion guard (SEC-090, SEC-091; THREAT-MODEL T-40).
// The platform, API, protos, SDKs and nf-core never send anything TO acquisition or stimulation hardware.
// Data flows device -> SDK -> platform only. This guard fails on:
//   A. (SEC-090) identifiers in proto/, openapi/, core/, bindings/, sdk/, tools/arena-core/ whose name parts match the denylist
//      stim*, pulse*, amplitude_set, trigger_out, command, actuat*, write_register (checked everywhere,
//      tests included: a test fixture must not define such an API either)
//   B. (SEC-091) LSL outlets (StreamOutlet, lsl_create_outlet, lsl_push_*) and serial/USB/HID/Bluetooth
//      crates, packages or imports, except in files under a `tests/` directory. Engine SDKs (2026-09-27):
//      WinRT/Win32 device APIs, P/Invoke of device libraries, .NET device packages, Unity/OpenXR/Unreal
//      haptics and force feedback (actuation), UE serial plugins and mobile USB/BLE/accessory APIs.
//   C. services/ (M2-REVIEW hw-guard scope decision): the SEC-091 rules in full over code and manifests
//      outside `tests/`; SEC-090 over the service's EXTERNAL SURFACE only, not arbitrary Python identifiers
//      (so `from alembic import command` passes). Statically: HTTP route path literals, `operation_id=`
//      and `action_extra(...)` values. At runtime: services/platform/tests/security/test_hw_guard_surface.py
//      runs the same denylist (denylist.json) over app.openapi(), the gRPC servicer and _pb2 descriptors.
//   D. Data files (recordings, fixtures: .xdf .edf .tsv .csv .json under services/ ...) are never scanned:
//      a recorded "Stimulus" event marker is data, not an API.
// There is deliberately no inline allow marker: changing this list needs the owner's written approval
// and a new regulatory analysis (SECURITY-REQUIREMENTS §G), not a code comment.
import { readFileSync } from 'node:fs';

// tools/arena-core: Rust shipped to /arena visitors as WebAssembly (nfb-security, 2026-09-27).
export const SCAN_DIRS = ['proto', 'openapi', 'core', 'bindings', 'sdk', 'tools/arena-core'];
export const SERVICE_DIRS = ['services'];

// services/: code and dependency manifests only (JSON/YAML/CSV there are schemas, fixtures or data).
const SERVICE_EXT =
  /\.(py|pyi|pyx|rs|ts|tsx|js|mjs|cjs|c|cc|cpp|cxx|h|hh|hpp|hxx|go|java|kt|toml)$/i;
const SERVICE_NAMES = /^(package\.json|requirements[\w.-]*\.txt|setup\.py|setup\.cfg|Pipfile)$/;
// Recording/annotation data: never scanned anywhere (SEC-090 applies to APIs, not recorded values).
export const DATA_EXT =
  /\.(xdf|xdfz|edf|bdf|gdf|fif|set|fdt|vhdr|vmrk|eeg|nwb|mat|npy|npz|zarr|h5|hdf5|tsv|csv|parquet|bin|dat)$/i;

// Code, schema and manifest files. Prose (.md) is excluded: it may explain the ban itself.
export const SCAN_EXT =
  /\.(proto|ya?ml|json|rs|toml|py|pyi|pyx|ts|tsx|js|mjs|cjs|c|cc|cpp|cxx|h|hh|hpp|hxx|cs|go|java|kt|swift|m|mm|uproperty|uplugin|ini|cfg|txt|cmake|in)$/i;
const SCAN_NAMES =
  /^(CMakeLists\.txt|Makefile|Cargo\.toml|package\.json|pyproject\.toml|setup\.py|setup\.cfg)$/;
const SKIP_DIRS = new Set([
  'target',
  'node_modules',
  '.venv',
  'dist',
  'build',
  '__pycache__',
  '.git',
]);

/** Split an identifier into lower-case words: StimParams -> [stim, params], write_register -> [write, register]. */
export function words(ident) {
  return ident
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
    .map((w) => w.toLowerCase());
}

// Denylist (denylist.json, shared with the Python surface test). Prefix entries (`stim*`) match any
// word starting with the prefix; sequences match adjacent words.
export const DENYLIST = JSON.parse(
  readFileSync(new URL('./denylist.json', import.meta.url), 'utf8'),
);
function seq(w, a, b) {
  for (let i = 0; i + 1 < w.length; i++) if (w[i] === a && w[i + 1] === b) return true;
  return false;
}

/** Return denylisted terms for one identifier (e.g. `setStimAmplitude` -> ['stim*']). */
export function deniedTerms(ident) {
  const w = words(ident);
  const { prefixes, sequences, terms } = DENYLIST;
  const hits = [
    ...prefixes.filter((p) => w.some((x) => x.startsWith(p))),
    ...DENYLIST.words.filter((x) => w.includes(x)),
    ...sequences.filter(([a, b]) => seq(w, a, b)).map((ab) => ab.join(' ')),
  ].map((k) => terms[k]);
  return [...new Set(hits)];
}

// SEC-091: LSL outlets and device-handle libraries (Rust crates, Python/JS packages, C headers, Web APIs).
const HW_PATTERNS = [
  {
    name: 'lsl-outlet',
    re: /\bStreamOutlet\b|\blsl_create_outlet\b|\blsl_push_(?:sample|chunk)\w*/,
  },
  {
    name: 'serial',
    re: /\b(?:serialport|tokio[-_]serial|mio[-_]serial|serial2|pyserial|serial_asyncio)\b|^\s*(?:import|from)\s+serial\b|\bnavigator\.serial\b|\bSerialPort\b/,
  },
  {
    name: 'usb',
    re: /\b(?:rusb|libusb\w*|nusb|pyusb|usb[-_]device|webusb)\b|^\s*(?:import|from)\s+usb\b|\bnavigator\.usb\b|['"]usb['"]/,
  },
  {
    name: 'hid',
    re: /\b(?:hidapi|node[-_]hid|hidraw)\b|^\s*(?:import|from)\s+hid\b|\bnavigator\.hid\b|['"]hid['"]/,
  },
  {
    name: 'bluetooth',
    re: /\b(?:btleplug|bluer|bluez|bleak|pybluez|noble|bluetooth\w*)\b|\bnavigator\.bluetooth\b|^\s*(?:import|from)\s+bluetooth\b/i,
  },
  // ---- Engine SDKs (bindings/unity C#, bindings/unreal C++): nfb-security approved 2026-09-27
  // (docs/hive/HW-GUARD-ENGINE-PROPOSAL.md + amendments). Broadening only.
  {
    // Why: WinRT namespaces that open device handles or drive pins from C# or C++/WinRT.
    name: 'winrt-devices',
    re: /\bWindows\.Devices\.(?:HumanInterfaceDevice|SerialCommunication|Bluetooth\w*|Usb|Gpio|I2c|Spi|Pwm)\b/,
  },
  {
    // Why: Win32 device enumeration and HID/USB/device I/O, from C++ or via P/Invoke.
    name: 'win32-device-io',
    re: /\b(?:SetupDiGetClassDevs\w*|HidD_\w+|WinUsb_\w+|DeviceIoControl)\b/,
  },
  {
    // Why: P/Invoke by library name catches EntryPoint aliasing that renames HidD_* etc. (verbatim @"..."
    // and a named first argument too); a library name held in a constant cannot be caught by a regex:
    // win32-device-io (unless aliased) and CODEOWNERS review on bindings/ are the backstop.
    name: 'dllimport-device-libs',
    re: /\b(?:DllImport|LibraryImport)\s*\(\s*(?:\w+\s*:\s*)?@?"(?:hid|setupapi|winusb|(?:lib)?hidapi|libusb[-\w.]*)(?:\.dll|\.so|\.dylib)?"/i,
  },
  {
    // Why: common .NET USB, HID and Bluetooth packages.
    name: 'dotnet-libusb-hid',
    re: /\b(?:LibUsbDotNet|HidSharp|HidLibrary|Device\.Net|InTheHand\.Net)\b/,
  },
  {
    // Why: haptic output is actuation; "vibrate on a neural event" is the closed-loop write path SEC-090..094 exclude.
    name: 'unity-haptics',
    re: /\b(?:SetMotorSpeeds|SendHapticImpulse|InputSystem\.Haptics|IDualMotorRumble|IHaptics|xrApplyHapticFeedback|XrHapticVibration|Windows\.Devices\.Haptics)\b/,
  },
  {
    // Why: Unreal force feedback and haptics are actuation; a custom input-device module is how a UE plugin talks to hardware.
    name: 'unreal-haptics-ffb',
    re: /\b(?:IForceFeedbackSystem|SetHapticsByValue|PlayHapticEffect|ClientPlayForceFeedback\w*|SetForceFeedbackChannelValue|IInputDeviceModule|UHapticFeedbackEffect\w*)\b/,
  },
  {
    // Why: community UE serial plugins (narrow, so FSerializer-style names do not match).
    name: 'unreal-serial',
    re: /\bFSerialPort\w*\b|\bUSerial\w*Port\b/,
  },
  {
    // Why: Unity mobile native plugins (Plugins/Android, Plugins/iOS) reaching USB, BLE or accessory hardware.
    name: 'mobile-device-apis',
    re: /\bandroid\.hardware\.usb\b|\b(?:UsbManager|BluetoothGatt\w*|BluetoothLeScanner|CoreBluetooth|CBCentralManager|IOHIDManager\w*|ExternalAccessory|EAAccessory)\b|IOKit\/hid/,
  },
];

export function isTestPath(path) {
  return /(^|\/)tests\//.test(path.replace(/\\/g, '/'));
}

const IDENT_RE = /[A-Za-z_][A-Za-z0-9_]*(?:[-.][A-Za-z_][A-Za-z0-9_]*)*/g;

/** Scan one file's text. `path` is repo-relative. Returns [{line, rule, detail}]. */
export function scanText(path, text) {
  const hits = [];
  const test = isTestPath(path);
  text.split(/\r?\n/).forEach((line, i) => {
    const seen = new Set();
    for (const m of line.matchAll(IDENT_RE)) {
      for (const part of m[0].split(/[-.]/)) {
        for (const term of deniedTerms(part)) {
          const key = `${term}:${part}`;
          if (seen.has(key)) continue;
          seen.add(key);
          hits.push({ line: i + 1, rule: 'SEC-090', detail: `${term} (${part})` });
        }
      }
    }
    if (!test)
      for (const p of HW_PATTERNS)
        if (p.re.test(line)) hits.push({ line: i + 1, rule: 'SEC-091', detail: p.name });
  });
  return hits;
}

export function shouldScan(relPath) {
  const p = relPath.replace(/\\/g, '/');
  if (p.split('/').some((s) => SKIP_DIRS.has(s))) return false;
  const base = p.slice(p.lastIndexOf('/') + 1);
  if (DATA_EXT.test(base)) return false;
  return SCAN_EXT.test(base) || SCAN_NAMES.test(base);
}

/** services/: code and manifests, never tests/ (SEC-091 exception) and never data files. */
export function shouldScanService(relPath) {
  const p = relPath.replace(/\\/g, '/');
  if (p.split('/').some((s) => SKIP_DIRS.has(s)) || isTestPath(p)) return false;
  const base = p.slice(p.lastIndexOf('/') + 1);
  if (DATA_EXT.test(base)) return false;
  return SERVICE_EXT.test(base) || SERVICE_NAMES.test(base);
}

// Static view of a service's external surface: URL path literals ("/v1/devices/{id}/..."),
// FastAPI `operation_id=` values and `action_extra("...")` / `x-nf-action` values.
const ROUTE_LITERAL = /(['"])(\/[A-Za-z0-9_.{}~/-]*)\1/g;
const SURFACE_KWARG =
  /\b(?:operation_id|operationId)\s*[=:]\s*(['"])([^'"]+)\1|\baction_extra\(\s*(['"])([^'"]+)\3|['"]x-nf-action['"]\s*:\s*(['"])([^'"]+)\5/g;

/** Scan one services/ file (repo-relative path, outside tests/). Returns [{line, rule, detail}]. */
export function scanServiceText(path, text) {
  const hits = [];
  text.split(/\r?\n/).forEach((line, i) => {
    const seen = new Set();
    const surface = [
      ...[...line.matchAll(ROUTE_LITERAL)].map((m) => ['route', m[2]]),
      ...[...line.matchAll(SURFACE_KWARG)].map((m) => ['name', m[2] || m[4] || m[6]]),
    ];
    for (const [kind, value] of surface)
      for (const m of value.matchAll(IDENT_RE))
        for (const part of m[0].split(/[-.]/))
          for (const term of deniedTerms(part)) {
            const key = `${term}:${part}`;
            if (seen.has(key)) continue;
            seen.add(key);
            hits.push({ line: i + 1, rule: 'SEC-090', detail: `${term} (${kind} ${value})` });
          }
    for (const p of HW_PATTERNS)
      if (p.re.test(line)) hits.push({ line: i + 1, rule: 'SEC-091', detail: p.name });
  });
  return hits;
}

// ---------------------------------------------------------------------------------------------
// SEC-090 external-surface scan (M2-REVIEW hw-guard decision; M4 4.1/4.6). Input: a JSON document
// produced at runtime by the service (the OpenAPI generated from the FastAPI app, incl. its
// `webhooks` payload schemas; optionally `x-nf-grpc` = gRPC service/method/field names). Checked
// names: path segments, operationIds, x-nf-action values, parameter and header names, schema names,
// schema property names, string enum/const values and webhook names. Descriptions (prose) are not
// names and are not checked here (the directory scan above still covers committed spec files).

const SCHEMA_KEYS = ['properties', 'patternProperties', '$defs', 'definitions'];

/** Every externally visible name of an OpenAPI(+webhooks) document: [{where, name}]. */
export function surfaceNames(doc) {
  const out = [];
  const add = (where, name) => {
    if (typeof name === 'string' && name) out.push({ where, name });
  };
  const walkSchema = (s, where) => {
    if (!s || typeof s !== 'object') return;
    if (Array.isArray(s)) return s.forEach((x, i) => walkSchema(x, `${where}[${i}]`));
    for (const k of SCHEMA_KEYS)
      if (s[k] && typeof s[k] === 'object')
        for (const [name, sub] of Object.entries(s[k])) {
          add(`${where}.${k}`, name);
          walkSchema(sub, `${where}.${k}.${name}`);
        }
    if (Array.isArray(s.enum)) s.enum.forEach((v) => add(`${where}.enum`, v));
    if (typeof s.const === 'string') add(`${where}.const`, s.const);
    if (Array.isArray(s.required)) s.required.forEach((v) => add(`${where}.required`, v));
    for (const k of ['items', 'additionalProperties', 'not', 'contains', 'propertyNames'])
      if (s[k] && typeof s[k] === 'object') walkSchema(s[k], `${where}.${k}`);
    for (const k of ['allOf', 'anyOf', 'oneOf', 'prefixItems'])
      if (Array.isArray(s[k])) walkSchema(s[k], `${where}.${k}`);
  };
  const walkOp = (op, where) => {
    if (!op || typeof op !== 'object') return;
    add(`${where}.operationId`, op.operationId);
    add(`${where}.x-nf-action`, op['x-nf-action']);
    for (const p of op.parameters || []) {
      add(`${where}.parameters`, p.name);
      walkSchema(p.schema, `${where}.parameters.${p.name}`);
    }
    const bodies = [op.requestBody, ...Object.values(op.responses || {})];
    for (const b of bodies) {
      if (!b || typeof b !== 'object') continue;
      for (const h of Object.keys(b.headers || {})) add(`${where}.headers`, h);
      for (const [mt, c] of Object.entries(b.content || {}))
        walkSchema(c?.schema, `${where}.${mt}`);
    }
  };
  const METHODS = ['get', 'put', 'post', 'delete', 'patch', 'options', 'head', 'trace'];
  for (const [path, item] of Object.entries(doc.paths || {})) {
    for (const seg of path.split('/')) add(`paths`, seg.replace(/[{}]/g, ''));
    for (const m of METHODS) if (item[m]) walkOp(item[m], `paths.${path}.${m}`);
  }
  for (const [name, item] of Object.entries(doc.webhooks || {})) {
    add('webhooks', name);
    for (const m of METHODS) if (item[m]) walkOp(item[m], `webhooks.${name}.${m}`);
  }
  for (const [name, s] of Object.entries(doc.components?.schemas || {})) {
    add('components.schemas', name);
    walkSchema(s, `components.schemas.${name}`);
  }
  for (const [where, list] of Object.entries(doc['x-nf-grpc'] || {}))
    for (const n of list) add(`x-nf-grpc.${where}`, n);
  return out;
}

/** SEC-090 hits on a surface document: [{where, name, detail}]. */
export function scanSurface(doc) {
  const hits = [];
  for (const { where, name } of surfaceNames(doc))
    for (const part of name.split(/[-.:/\s]+/))
      for (const term of deniedTerms(part))
        hits.push({ where, name, rule: 'SEC-090', detail: `${term} (${part})` });
  return hits;
}

// ---------------------------------------------------------------------------------------------
// Coverage guard (nfb-security, 2026-09-27): every Cargo workspace member that ships to users --
// a cdylib/staticlib (C ABI, Python extension, WebAssembly) or a crate using wasm-bindgen -- must
// lie under a SCAN_DIRS path, so a new shipping crate cannot silently escape SEC-090/091.

/** Paths listed in `[workspace] members = [...]` of a root Cargo.toml text. */
export function workspaceMembers(cargoToml) {
  // The [workspace] table runs until the next table header (or the end of the file).
  const ws = /^\[workspace\][^\S\n]*\n([\s\S]*?)(?=^\[|$(?![\s\S]))/m.exec(cargoToml);
  const m = ws && /^\s*members\s*=\s*\[([\s\S]*?)\]/m.exec(ws[1]);
  if (!m) return [];
  return [...m[1].matchAll(/"([^"]+)"|'([^']+)'/g)].map((x) => (x[1] ?? x[2]).replace(/\\/g, '/'));
}

/** Whether a member's Cargo.toml text describes a crate that ships to users. */
export function shipsToUsers(memberToml) {
  const ct = /^\s*crate-type\s*=\s*\[([^\]]*)\]/m.exec(memberToml);
  if (ct && /["'](?:cdylib|staticlib)["']/.test(ct[1])) return true;
  // wasm-bindgen as `wasm-bindgen = ...`, `wasm-bindgen.workspace = true`, or its own table
  // `[dependencies.wasm-bindgen]` / `[target.'cfg(...)'.dependencies.wasm-bindgen]`.
  if (/^\s*["']?wasm-bindgen["']?\s*(?:=|\.)/m.test(memberToml)) return true;
  return /^\s*\[(?:target\.(?:'[^']*'|"[^"]*"|[^\].]+)\.)?dependencies\.["']?wasm-bindgen["']?\]/m.test(
    memberToml,
  );
}

/** Whether repo-relative `path` lies under one of `dirs`. */
export function coveredBy(path, dirs = SCAN_DIRS) {
  const p = path.replace(/\\/g, '/').replace(/\/+$/, '');
  return dirs.some((d) => p === d || p.startsWith(d + '/'));
}

/** Shipping workspace members outside SCAN_DIRS: [{member, reason}]. `read(rel)` returns file text or null. */
export function uncoveredShippingCrates(read, dirs = SCAN_DIRS) {
  const root = read('Cargo.toml');
  if (root == null) return [];
  const out = [];
  for (const member of workspaceMembers(root)) {
    if (member.includes('*')) {
      out.push({
        member,
        reason:
          'glob workspace members are not supported by the coverage guard; list crates explicitly',
      });
      continue;
    }
    const toml = read(member + '/Cargo.toml');
    if (toml == null) {
      out.push({ member, reason: 'workspace member without a readable Cargo.toml' });
      continue;
    }
    if (shipsToUsers(toml) && !coveredBy(member, dirs))
      out.push({
        member,
        reason: 'ships to users (cdylib/staticlib/wasm) but is outside SCAN_DIRS',
      });
  }
  return out;
}

/** Every shipping crate in the repo, not only root workspace members (excluded members and nested
 * workspaces too): `manifests` are repo-relative paths of all Cargo.toml files (SKIP_DIRS already
 * pruned). Returns [{member, reason}] for shipping crates outside SCAN_DIRS. */
export function uncoveredShippingManifests(read, manifests, dirs = SCAN_DIRS) {
  const out = [];
  for (const rel of manifests) {
    const p = rel.replace(/\\/g, '/');
    if (isTestPath(p)) continue; // fixtures under tests/ never ship (same exemption as SEC-091)
    const member = p.includes('/') ? p.slice(0, p.lastIndexOf('/')) : '.';
    const toml = read(p);
    if (toml != null && shipsToUsers(toml) && !coveredBy(member, dirs))
      out.push({
        member,
        reason: 'ships to users (cdylib/staticlib/wasm) but is outside SCAN_DIRS',
      });
  }
  return out;
}

/** Whether a directory name is pruned from repo walks (build output, dependencies, VCS). */
export function isSkippedDir(name) {
  return SKIP_DIRS.has(name);
}

// ---------------------------------------------------------------------------------------------
// JS/TS packages (nfb-security, 2026-09-27): SEC-091 device rules ONLY (the SEC-090 name denylist
// would false-positive on website code, e.g. cosmos "pulse" animations). Scope: apps/*/src, apps/*/public,
// packages/*/src, packages/*/public and each app/package's package.json. Defence in depth behind the site's
// Permissions-Policy (SEC-152): code that tries these APIs should not exist at all.
export const WEB_ROOTS = ['apps', 'packages'];
const WEB_EXT = /\.(?:js|mjs|cjs|jsx|ts|mts|cts|tsx|astro|svelte|vue)$/i;
const WEB_DEVICE_PACKAGES =
  'serialport|@serialport/[\\w-]+|node-hid|usb|webusb|noble|@abandonware/noble|johnny-five|onoff|i2c-bus|spi-device';
const WEB_PATTERNS = [
  // Why: Web Serial/USB/HID/Bluetooth open device handles from the page.
  { name: 'web-serial', re: /\bnavigator\s*\.\s*serial\b/ },
  { name: 'web-usb', re: /\bnavigator\s*\.\s*usb\b/ },
  { name: 'web-hid', re: /\bnavigator\s*\.\s*hid\b/ },
  { name: 'web-bluetooth', re: /\bnavigator\s*\.\s*bluetooth\b/ },
  // Why: the device-chooser entry point of Web Bluetooth/USB/HID, however the object is reached.
  { name: 'web-request-device', re: /\.\s*requestDevice\s*\(/ },
  // Why: Web MIDI can send output (including sysex) to instruments and devices.
  { name: 'web-midi', re: /\brequestMIDIAccess\b|\bMIDIOutput\b/ },
  // Why: Node device packages (serial, HID, USB, BLE, GPIO/I2C/SPI) imported or required.
  {
    name: 'js-device-packages',
    re: new RegExp(
      // `from 'pkg'`, side-effect `import 'pkg'`, `require('pkg')`, `import('pkg')`; subpaths too.
      `(?:\\bfrom\\s+|\\bimport\\s+|\\brequire\\s*\\(\\s*|\\bimport\\s*\\(\\s*)['"](?:${WEB_DEVICE_PACKAGES})(?:/[^'"]*)?['"]`,
    ),
  },
];
const PKG_DEVICE_DEP = new RegExp(`^\\s*"(?:${WEB_DEVICE_PACKAGES})"\\s*:`);

/** Whether a repo-relative path is in the JS/TS device scan (apps/<x>/{src,public}/**, packages/<x>/{src,public}/**,
 * apps/<x>/package.json, packages/<x>/package.json). */
export function shouldScanWeb(relPath) {
  const p = relPath.replace(/\\/g, '/');
  if (p.split('/').some((s) => SKIP_DIRS.has(s))) return false;
  const parts = p.split('/');
  if (!WEB_ROOTS.includes(parts[0]) || parts.length < 3) return false;
  if (parts.length === 3 && parts[2] === 'package.json') return true;
  return (parts[2] === 'src' || parts[2] === 'public') && WEB_EXT.test(p);
}

/** SEC-091 web/device scan of one JS/TS source or package.json (tests/ exempt as elsewhere). */
export function scanWebText(path, text) {
  const hits = [];
  if (isTestPath(path)) return hits;
  const manifest = path.replace(/\\/g, '/').endsWith('/package.json');
  text.split(/\r?\n/).forEach((line, i) => {
    if (manifest) {
      if (PKG_DEVICE_DEP.test(line))
        hits.push({ line: i + 1, rule: 'SEC-091', detail: 'js-device-packages' });
      return;
    }
    for (const p of WEB_PATTERNS)
      if (p.re.test(line)) hits.push({ line: i + 1, rule: 'SEC-091', detail: p.name });
  });
  return hits;
}
