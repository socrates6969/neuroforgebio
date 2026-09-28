import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  DENYLIST,
  coveredBy,
  scanWebText,
  shouldScanWeb,
  shipsToUsers,
  workspaceMembers,
  deniedTerms,
  scanServiceText,
  scanText,
  shouldScan,
  shouldScanService,
  words,
} from '../lib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const cli = join(here, '..', 'cli.mjs');
const repoRoot = join(here, '..', '..', '..');
const run = (root) => spawnSync(process.execPath, [cli, '--root', root], { encoding: 'utf8' });
const fx = (name) => join(here, 'fixtures', name);

test('SEC-090: a proto with stimulation/pulse/trigger_out fails', () => {
  const r = run(fx('bad-proto'));
  assert.equal(r.status, 1);
  assert.match(r.stdout, /proto\/stream\.proto:5: SEC-090: stim\* \(SetStimulation\)/);
  assert.match(r.stdout, /pulse\* \(PulseTrain\)/);
  assert.match(r.stdout, /trigger_out \(trigger_out\)/);
});

test('SEC-090: an OpenAPI with command/amplitude_set/write_register/actuat* fails', () => {
  const r = run(fx('bad-openapi'));
  assert.equal(r.status, 1);
  for (const t of [
    'command \\(command\\)',
    'command \\(sendDeviceCommand\\)',
    'amplitude_set',
    'write_register',
    'actuat\\*',
  ])
    assert.match(r.stdout, new RegExp(t));
});

test('SEC-091: outlets and serial/USB/HID/Bluetooth outside tests/ fail', () => {
  const r = run(fx('bad-core'));
  assert.equal(r.status, 1);
  assert.match(r.stdout, /core\/nf-core\/Cargo\.toml:7: SEC-091: serial/);
  assert.match(r.stdout, /core\/nf-core\/src\/lsl\.rs:3: SEC-091: lsl-outlet/);
  assert.match(r.stdout, /bindings\/python\/device\.py:1: SEC-091: serial/);
  assert.match(r.stdout, /sdk\/web\/device\.ts:2: SEC-091: hid/);
});

test('clean tree passes; an outlet under tests/ is allowed; Markdown is not scanned', () => {
  const r = run(fx('clean'));
  assert.equal(r.status, 0, r.stdout);
});

test('this repository passes', () => {
  const r = run(repoRoot);
  assert.equal(r.status, 0, r.stdout);
});

test('identifier splitting and denylist', () => {
  assert.deepEqual(words('setStimAmplitude'), ['set', 'stim', 'amplitude']);
  assert.deepEqual(words('HTTPCommandQueue'), ['http', 'command', 'queue']);
  assert.deepEqual(deniedTerms('StimulusProtocol'), ['stim*']);
  assert.deepEqual(deniedTerms('AmplitudeSet'), ['amplitude_set']);
  assert.deepEqual(deniedTerms('writeRegister'), ['write_register']);
  assert.deepEqual(deniedTerms('TRIGGER_OUT'), ['trigger_out']);
  assert.deepEqual(deniedTerms('trigger_in'), []);
  assert.deepEqual(deniedTerms('sample_rate'), []);
  assert.deepEqual(deniedTerms('amplitude'), []);
  assert.deepEqual(
    scanText('core/x/tests/a.rs', 'let o = StreamOutlet::new();').map((h) => h.rule),
    [],
  );
  assert.deepEqual(
    scanText('core/x/src/a.rs', 'let o = StreamOutlet::new();').map((h) => h.rule),
    ['SEC-091'],
  );
  assert.ok(shouldScan('proto/a.proto'));
  assert.ok(!shouldScan('proto/README.md'));
  assert.ok(!shouldScan('core/target/debug/x.json'));
});

// ---- services/ scope (M2-REVIEW hw-guard decision): SEC-091 in full, SEC-090 on the external surface
test('services: a FastAPI route /v1/devices/{id}/stimulate fails (SEC-090 surface)', () => {
  const r = run(fx('bad-service-route'));
  assert.equal(r.status, 1);
  assert.match(
    r.stdout,
    /services\/platform\/nf_platform\/api\/device_routes\.py:6: SEC-090: stim\* \(route \/v1\/devices\/\{id\}\/stimulate\)/,
  );
  assert.match(r.stdout, /SEC-090: stim\* \(name stimulateDevice\)/);
});

test('services: a pylsl.StreamOutlet under services/platform/nf_platform/ fails (SEC-091)', () => {
  const r = run(fx('bad-service-outlet'));
  assert.equal(r.status, 1);
  assert.match(r.stdout, /services\/platform\/nf_platform\/lsl_out\.py:4: SEC-091: lsl-outlet/);
});

test('services: `from alembic import command`, tests/ outlets, data files and XDF "Stimulus" markers pass', () => {
  const tmp = mkdtempSync(join(tmpdir(), 'hw-guard-'));
  try {
    cpSync(fx('service-ok'), tmp, { recursive: true });
    // A minimal XDF file (magic + FileHeader chunk + a Markers stream header + one string sample),
    // written at test time: recordings are never tracked in git (SEC-087).
    const xml = (s) => Buffer.from(`<?xml version="1.0"?>${s}`, 'utf8');
    const chunk = (tag, body) => {
      const len = Buffer.alloc(5);
      len.writeUInt8(4, 0);
      len.writeUInt32LE(body.length + 2, 1);
      const t = Buffer.alloc(2);
      t.writeUInt16LE(tag, 0);
      return Buffer.concat([len, t, body]);
    };
    const xdf = Buffer.concat([
      Buffer.from('XDF:'),
      chunk(1, xml('<info><version>1.0</version></info>')),
      chunk(
        2,
        Buffer.concat([
          Buffer.from([1, 0, 0, 0]),
          xml(
            '<info><name>Stimulus markers</name><type>Markers</type><channel_count>1</channel_count>' +
              '<channel_format>string</channel_format><nominal_srate>0</nominal_srate></info>',
          ),
        ]),
      ),
      chunk(3, Buffer.concat([Buffer.from([1, 0, 0, 0]), Buffer.from('Stimulus/S  1 stimulate')])),
    ]);
    for (const rel of [
      'services/platform/nf_platform/recordings/sub-01_task-oddball_eeg.xdf',
      'sdk/python/tests/data/markers.xdf',
      'core/nf-core/fixtures/markers.xdf',
    ]) {
      mkdirSync(dirname(join(tmp, rel)), { recursive: true });
      writeFileSync(join(tmp, rel), xdf);
    }
    mkdirSync(join(tmp, 'services/platform/nf_platform/recordings'), { recursive: true });
    writeFileSync(
      join(tmp, 'services/platform/nf_platform/recordings/events.tsv'),
      'onset\tduration\ttrial_type\n1.5\t0\tStimulus\n',
    );
    const ok = run(tmp);
    assert.equal(ok.status, 0, ok.stdout + ok.stderr);
    // contrast: the same word as an API route in service code is caught
    writeFileSync(
      join(tmp, 'services/platform/nf_platform/api/bad.py'),
      'ROUTE = "/v1/stimulus/{id}"\n',
    );
    const bad = run(tmp);
    assert.equal(bad.status, 1);
    assert.match(bad.stdout, /api\/bad\.py:1: SEC-090: stim\* \(route \/v1\/stimulus\/\{id\}\)/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('services: scope and surface rules', () => {
  assert.ok(shouldScanService('services/platform/nf_platform/app.py'));
  assert.ok(shouldScanService('services/platform/pyproject.toml'));
  assert.ok(!shouldScanService('services/platform/tests/ingest/test_edge_lsl.py'));
  assert.ok(!shouldScanService('services/workers/steps/x/tests/golden/a.py'));
  assert.ok(!shouldScanService('services/workers/steps/x/examples/map.json'));
  assert.ok(!shouldScanService('services/platform/nf_platform/recordings/a.xdf'));
  assert.ok(!shouldScan('sdk/python/tests/data/markers.xdf'));
  assert.ok(!shouldScan('core/fixtures/events.tsv'));
  const rules = (t) => scanServiceText('services/platform/nf_platform/x.py', t).map((h) => h.rule);
  assert.deepEqual(rules('from alembic import command\ncommand.upgrade(cfg, "head")'), []);
  assert.deepEqual(rules('import subprocess\nsubprocess.run(["git", "status"])'), []);
  assert.deepEqual(rules('label = "Stimulus/S  1"'), []);
  assert.deepEqual(rules('_route("POST", "/devices/{id}/commands", "device:write")'), ['SEC-090']);
  assert.deepEqual(rules('openapi_extra=action_extra("device:actuate")'), ['SEC-090']);
  assert.deepEqual(rules('@router.get("/x", operation_id="setAmplitude")'), ['SEC-090']);
  assert.deepEqual(rules('outlet = pylsl.StreamOutlet(info)'), ['SEC-091']);
  assert.deepEqual(rules('import serial'), ['SEC-091']);
  assert.deepEqual(rules('from bleak import BleakClient'), ['SEC-091']);
});

test('the denylist file drives the lint (shared with the Python surface test)', () => {
  assert.deepEqual(DENYLIST.prefixes, ['stim', 'pulse', 'actuat']);
  for (const k of [...DENYLIST.prefixes, ...DENYLIST.words])
    assert.ok(DENYLIST.terms[k], `term for ${k}`);
  for (const s of DENYLIST.sequences) assert.ok(DENYLIST.terms[s.join(' ')], `term for ${s}`);
});

// ---- M4: external-surface scan (M2-REVIEW decision; the platform tests feed it the live OpenAPI)
const surface = (...files) =>
  spawnSync(process.execPath, [cli, ...files.flatMap((f) => ['--surface', f])], {
    encoding: 'utf8',
  });

test('SEC-090 surface: paths, operationIds, actions, params, properties, enums, webhooks fail', () => {
  const r = surface(fx('surface/bad.json'));
  assert.equal(r.status, 1, r.stderr);
  for (const t of [
    /paths: SEC-090: stim\* \(stimulate\)/,
    /operationId: SEC-090: pulse\* \(sendPulseTrain\)/,
    /x-nf-action: SEC-090: actuat\* \(actuate\)/,
    /parameters: SEC-090: amplitude_set \(amplitudeSet\)/,
    /enum: SEC-090: trigger_out \(trigger_out\)/,
    /properties: SEC-090: write_register \(writeRegister\)/,
    /webhooks: SEC-090: command \(deviceCommand\)/,
    /components\.schemas: SEC-090: stim\* \(StimParams\)/,
    /x-nf-grpc\.methods: SEC-090: actuat\* \(ActuatorSet\)/,
  ])
    assert.match(r.stdout, t);
});

test('SEC-090 surface: neutral names pass; prose descriptions are not names', () => {
  const r = surface(fx('surface/clean.json'));
  assert.equal(r.status, 0, r.stdout + r.stderr);
});

test('surface: a missing file is an error (exit 2), never a pass', () => {
  const r = surface(fx('surface/does-not-exist.json'));
  assert.equal(r.status, 2);
});

// ---- Engine SDKs (C#, Unreal C++, mobile native plugins): SEC-091 device-API rules
// (docs/hive/HW-GUARD-ENGINE-PROPOSAL.md, approved with amendments by nfb-security 2026-09-27)
const ENGINE_BAD = [
  ['winrt-devices', 'bindings/unity/Runtime/Bad.cs', 'using Windows.Devices.HumanInterfaceDevice;'],
  [
    'winrt-devices',
    'bindings/unity/Runtime/Bad.cs',
    'var d = await Windows.Devices.SerialCommunication.SerialDevice.FromIdAsync(id);',
  ],
  ['win32-device-io', 'bindings/unreal/Source/Bad.cpp', 'HidD_SetOutputReport(h, buf, len);'],
  [
    'win32-device-io',
    'bindings/unreal/Source/Bad.cpp',
    'DeviceIoControl(h, code, nullptr, 0, nullptr, 0, &n, nullptr);',
  ],
  [
    'dllimport-device-libs',
    'bindings/unity/Runtime/Bad.cs',
    '[DllImport("hid.dll", EntryPoint="Foo")] static extern bool Foo(IntPtr h);',
  ],
  [
    'dllimport-device-libs',
    'bindings/unity/Runtime/Bad.cs',
    '[LibraryImport("libusb-1.0")] private static partial int Open();',
  ],
  [
    'dllimport-device-libs',
    'bindings/unity/Runtime/Bad.cs',
    '[DllImport(@"hid.dll")] static extern bool Foo();',
  ],
  [
    'dllimport-device-libs',
    'bindings/unity/Runtime/Bad.cs',
    '[DllImport(dllName: "setupapi")] static extern bool Foo();',
  ],
  ['dotnet-libusb-hid', 'bindings/unity/Runtime/Bad.cs', 'using HidSharp;'],
  ['unity-haptics', 'bindings/unity/Runtime/Bad.cs', 'Gamepad.current.SetMotorSpeeds(0.5f, 0.5f);'],
  ['unity-haptics', 'bindings/unity/Runtime/Bad.cs', 'device.SendHapticImpulse(0, amp, 0.1f);'],
  [
    'unity-haptics',
    'bindings/unity/Plugins/Bad.cpp',
    'xrApplyHapticFeedback(session, &info, &vib);',
  ],
  [
    'unreal-haptics-ffb',
    'bindings/unreal/Source/Bad.cpp',
    'PC->SetHapticsByValue(1.f, 1.f, EControllerHand::Left);',
  ],
  ['unreal-haptics-ffb', 'bindings/unreal/Source/Bad.h', 'UHapticFeedbackEffect_Curve* Effect;'],
  [
    'unreal-haptics-ffb',
    'bindings/unreal/Source/Bad.cpp',
    'class FMyDevice : public IInputDeviceModule {};',
  ],
  ['unreal-serial', 'bindings/unreal/Source/Bad.cpp', 'FSerialPort Port; USerialComPort* P;'],
  [
    'mobile-device-apis',
    'bindings/unity/Plugins/Android/Bad.java',
    'import android.hardware.usb.UsbManager;',
  ],
  ['mobile-device-apis', 'bindings/unity/Plugins/iOS/Bad.mm', '#import <IOKit/hid/IOHIDManager.h>'],
  [
    'mobile-device-apis',
    'bindings/unity/Plugins/iOS/Bad.swift',
    'let m = CBCentralManager(delegate: self, queue: nil)',
  ],
  ['mobile-device-apis', 'bindings/unity/Plugins/iOS/Bad.m', 'EAAccessory *acc = nil;'],
];

test('SEC-091 engine rules: each device API fails with its rule name', () => {
  for (const [rule, path, line] of ENGINE_BAD) {
    const hits = scanText(path, line).filter((h) => h.rule === 'SEC-091');
    assert.ok(
      hits.some((h) => h.detail === rule),
      `${path}: expected SEC-091 ${rule} for ${line}; got ${JSON.stringify(hits)}`,
    );
  }
});

test('SEC-091 engine rules: near-misses pass', () => {
  const clean = [
    'public bool HasTimestamps { get; }',
    'var ts = TimeStamp.Now; // no haptics, no device access',
    '/// <summary>Plug in the "UsbCable" before recording (docs only).</summary>',
    'FSerializer Ser; FArchive& Ar = Ser;',
    'var caps = device.HapticCapabilities; // a capability query only',
    '[DllImport("neuroforge", CallingConvention = CallingConvention.Cdecl)] internal static extern uint nf_abi_version();',
    'IInputDevice* Unused = nullptr; // an interface name, not the device module',
  ];
  for (const line of clean)
    assert.deepEqual(
      scanText('bindings/unity/Runtime/Ok.cs', line).filter((h) => h.rule === 'SEC-091'),
      [],
      line,
    );
});

test('SEC-091 engine rules: the CLI reports rule and SEC-091, and mobile plugin files are scanned', () => {
  const tmp = mkdtempSync(join(tmpdir(), 'hw-guard-engine-'));
  try {
    const files = {
      'bindings/unity/Runtime/Native/Bad.cs':
        'class N { [DllImport("hid.dll", EntryPoint="Foo")] static extern bool Foo(System.IntPtr h); }\n',
      'bindings/unity/Plugins/Android/Usb.kt': 'import android.hardware.usb.UsbManager\n',
      'bindings/unity/Plugins/iOS/Hid.mm': '#import <IOKit/hid/IOHIDManager.h>\n',
      'bindings/unity/Runtime/Ok.cs': 'public bool HasTimestamps { get; }\n',
    };
    for (const [rel, text] of Object.entries(files)) {
      mkdirSync(dirname(join(tmp, rel)), { recursive: true });
      writeFileSync(join(tmp, rel), text);
    }
    const r = run(tmp);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(r.stdout, /Native\/Bad\.cs:1: SEC-091: dllimport-device-libs/);
    assert.match(r.stdout, /Android\/Usb\.kt:1: SEC-091: mobile-device-apis/);
    assert.match(r.stdout, /iOS\/Hid\.mm:1: SEC-091: mobile-device-apis/);
    assert.doesNotMatch(r.stdout, /Ok\.cs/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

// ---- Scan coverage (nfb-security, 2026-09-27): shipping workspace crates must be under SCAN_DIRS
test('coverage: tools/arena-core is scanned', () => {
  assert.ok(coveredBy('tools/arena-core'));
  assert.ok(coveredBy('tools/arena-core/src/wasm.rs'));
  assert.ok(!coveredBy('tools/arena-core-extra'));
  assert.ok(!coveredBy('tools/repro-check'));
});

test('coverage: workspace members and shipping detection', () => {
  const root = `[workspace]\nresolver = "3"\nmembers = [\n  "core/nf-core",\n  "bindings/python",\n  'tools/x',\n]\n\n[workspace.package]\nedition = "2024"\n`;
  assert.deepEqual(workspaceMembers(root), ['core/nf-core', 'bindings/python', 'tools/x']);
  assert.equal(shipsToUsers('[lib]\ncrate-type = ["cdylib", "rlib"]\n'), true);
  assert.equal(shipsToUsers('[lib]\ncrate-type = ["staticlib"]\n'), true);
  assert.equal(
    shipsToUsers('[dependencies]\nwasm-bindgen = { version = "=0.2.129", optional = true }\n'),
    true,
  );
  assert.equal(shipsToUsers('[lib]\ncrate-type = ["rlib"]\n[dependencies]\nserde = "1"\n'), false);
});

test('coverage: a shipping crate outside SCAN_DIRS fails the CLI; a non-shipping one passes', () => {
  const tmp = mkdtempSync(join(tmpdir(), 'hw-guard-cov-'));
  try {
    const put = (rel, text) => {
      mkdirSync(dirname(join(tmp, rel)), { recursive: true });
      writeFileSync(join(tmp, rel), text);
    };
    put('Cargo.toml', '[workspace]\nmembers = ["core/a", "tools/lib-only", "tools/wasm-thing"]\n');
    put('core/a/Cargo.toml', '[lib]\ncrate-type = ["cdylib"]\n');
    put('tools/lib-only/Cargo.toml', '[package]\nname = "x"\n');
    put('tools/wasm-thing/Cargo.toml', '[lib]\ncrate-type = ["cdylib", "rlib"]\n');
    const r = run(tmp);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(
      r.stdout,
      /tools\/wasm-thing\/Cargo\.toml:1: SEC-091: scan-coverage: ships to users/,
    );
    assert.doesNotMatch(r.stdout, /lib-only|core\/a/);
    // glob members are refused, not silently skipped
    put('Cargo.toml', '[workspace]\nmembers = ["tools/*"]\n');
    assert.match(run(tmp).stdout, /scan-coverage: glob workspace members/);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

// ---- Coverage follow-up (nfb-security verify of b35c61d): wasm-bindgen forms, unreadable members,
// crates outside the root workspace; and JS/TS packages under SEC-091 device rules only.
test('coverage: every wasm-bindgen dependency form counts as shipping', () => {
  for (const toml of [
    '[dependencies]\nwasm-bindgen.workspace = true\n',
    '[target.\'cfg(target_arch = "wasm32")\'.dependencies]\nwasm-bindgen = { workspace = true }\n',
    '[dependencies.wasm-bindgen]\nversion = "0.2"\n',
    '[target.\'cfg(target_arch = "wasm32")\'.dependencies.wasm-bindgen]\nversion = "0.2"\n',
    '[target.wasm32-unknown-unknown.dependencies.wasm-bindgen]\nversion = "0.2"\n',
  ])
    assert.equal(shipsToUsers(toml), true, toml);
  assert.equal(shipsToUsers('[dependencies]\nwasm-bindgen-futures-docs = "1"\n'), false);
});

test('coverage: an unreadable member and a shipping crate outside the root workspace fail', () => {
  const tmp = mkdtempSync(join(tmpdir(), 'hw-guard-cov2-'));
  try {
    const put = (rel, text) => {
      mkdirSync(dirname(join(tmp, rel)), { recursive: true });
      writeFileSync(join(tmp, rel), text);
    };
    put(
      'Cargo.toml',
      '[workspace]\nmembers = ["core/a", "core/missing"]\nexclude = ["tools/excluded"]\n',
    );
    put('core/a/Cargo.toml', '[lib]\ncrate-type = ["rlib"]\n');
    put('tools/excluded/Cargo.toml', '[lib]\ncrate-type = ["cdylib"]\n');
    put('tools/nested/Cargo.toml', '[workspace]\n\n[dependencies.wasm-bindgen]\nversion = "0.2"\n');
    put('tools/nested/target/x/Cargo.toml', '[lib]\ncrate-type = ["cdylib"]\n'); // pruned
    put('tools/tests/fixture/Cargo.toml', '[lib]\ncrate-type = ["cdylib"]\n'); // test fixture
    const r = run(tmp);
    assert.equal(r.status, 1, r.stdout + r.stderr);
    assert.match(
      r.stdout,
      /core\/missing\/Cargo\.toml:1: SEC-091: scan-coverage: workspace member without a readable Cargo\.toml/,
    );
    assert.match(
      r.stdout,
      /tools\/excluded\/Cargo\.toml:1: SEC-091: scan-coverage: ships to users/,
    );
    assert.match(r.stdout, /tools\/nested\/Cargo\.toml:1: SEC-091: scan-coverage: ships to users/);
    assert.doesNotMatch(r.stdout, /target\/x|tests\/fixture|core\/a\//);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('web: device APIs and device packages in apps/packages src fail; website words pass', () => {
  const bad = [
    ['web-serial', 'const port = await navigator.serial.requestPort();'],
    ['web-usb', 'navigator . usb.getDevices();'],
    ['web-hid', 'const [d] = await navigator.hid.requestDevice({ filters: [] });'],
    ['web-bluetooth', 'navigator.bluetooth.getAvailability();'],
    ['web-request-device', 'const dev = await bt.requestDevice({ acceptAllDevices: true });'],
    ['web-midi', 'const midi = await navigator.requestMIDIAccess({ sysex: true });'],
    ['js-device-packages', "import { SerialPort } from 'serialport';"],
    ['js-device-packages', "const HID = require('node-hid');"],
    ['js-device-packages', "const m = await import('@serialport/bindings-cpp');"],
    // package subpaths and side-effect imports (nfb-security nit 1)
    ['js-device-packages', "import x from 'usb/dist/index.js';"],
    ['js-device-packages', "const p = require('serialport/lib/parsers');"],
    ['js-device-packages', "import 'node-hid/nodehid.js';"],
    ['js-device-packages', "const b = await import('@serialport/bindings-cpp/dist/index.js');"],
  ];
  for (const [rule, line] of bad) {
    const hits = scanWebText('apps/web/src/scripts/bad.ts', line);
    assert.ok(
      hits.some((h) => h.rule === 'SEC-091' && h.detail === rule),
      `${rule}: ${line}`,
    );
  }
  assert.deepEqual(
    scanWebText('apps/web/package.json', '    "serialport": "^12.0.0",').map((h) => h.detail),
    ['js-device-packages'],
  );
  const clean = [
    '.pulse { animation: pulse 2s infinite; } // cosmos theme',
    'Stimulus-free research demo. No Bluetooth, USB or HID devices are used.',
    "const usbCable = 'docs only';",
    'navigator.clipboard.writeText(text);',
    'const res = await fetch(assetUrl);',
  ];
  for (const line of clean)
    assert.deepEqual(scanWebText('apps/web/src/pages/x.astro', line), [], line);
  // tests/ are exempt; files outside apps/*/src and packages/*/src are not in scope
  assert.deepEqual(scanWebText('apps/web/src/tests/x.ts', 'navigator.usb.getDevices();'), []);
  assert.equal(shouldScanWeb('apps/web/src/scripts/arena.ts'), true);
  assert.equal(shouldScanWeb('packages/ui/src/Tabs.ts'), true);
  assert.equal(shouldScanWeb('apps/web/package.json'), true);
  // static JS shipped verbatim (nfb-security nit 2)
  assert.equal(shouldScanWeb('apps/web/public/vendor/x.js'), true);
  assert.equal(shouldScanWeb('packages/ui/public/y.mjs'), true);
  assert.equal(shouldScanWeb('apps/web/public/images/logo.svg'), false);
  // near-misses: other packages whose names merely start like a device package
  assert.deepEqual(scanWebText('apps/web/src/a.ts', "import u from 'usb-cable-docs';"), []);
  assert.deepEqual(scanWebText('apps/web/src/a.ts', "import s from 'serialport-free-docs';"), []);
  assert.equal(shouldScanWeb('apps/web/test/security.test.mjs'), false);
  assert.equal(shouldScanWeb('apps/web/node_modules/x/src/a.js'), false);
  assert.equal(shouldScanWeb('packages/content/content/pages/home.json'), false);
});
