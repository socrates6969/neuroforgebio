// /interface WebGL scene (three.js, bundled locally, loaded only by a dynamic import from
// interface.ts). Illustrative anatomy and device: a translucent block of motor cortex, a Utah-style
// microelectrode array, the lead to a headstage, a data stream to a decoder, and the decoded
// movement driving a cursor screen and a simulated arm. The firing is replayed from the same open
// MC_RTT recording as /playground; the decoded path is the precomputed ridge-filter output on test
// reaches. Every frame is a pure function of scene time t (seconds), so record mode can seek.
// Graphics only: nothing here talks to any device.
import {
  AmbientLight,
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  CatmullRomCurve3,
  Color,
  ConeGeometry,
  CylinderGeometry,
  DirectionalLight,
  DoubleSide,
  Group,
  InstancedMesh,
  LineBasicMaterial,
  LineSegments,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Object3D,
  PerspectiveCamera,
  PlaneGeometry,
  Points,
  PointsMaterial,
  Quaternion,
  Raycaster,
  Scene,
  SphereGeometry,
  Spherical,
  SRGBColorSpace,
  TubeGeometry,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { armPoints, binsUpTo, sampleAt, solveArm } from '../lib/playground-data.mjs';
import {
  cameraAt,
  gridSlots,
  recentSpikes,
  spikeGlow,
  timeline,
  TOUR_SECONDS,
} from '../lib/interface-model.mjs';
import type { parsePlayground } from '../lib/playground-data.mjs';

type Model = ReturnType<typeof parsePlayground>;
export type Layer = 'tissue' | 'electrodes' | 'signals' | 'decoder';

/** Replay runs at half speed so single spikes stay visible. */
export const REPLAY_SPEED = 0.5;
const PITCH = 0.8; // array pitch in scene units (scene unit = 0.5 mm)
const ARRAY_Z = -2.5;
const BASE_Y = 0.45;
const SHANK = 3;
const TIP_Y = BASE_Y - SHANK - 0.1;
const LEAD_WINDOW_MS = 260; // a spike's pulse takes this long to reach the headstage
const PACKET_MS = 50; // one packet per decoder bin
const PACKET_TRAVEL_MS = 420;

// Anatomy and device colours are illustrative materials, not UI colours (UI hues come from tokens).
const MATERIAL = {
  pia: '#d7a29c',
  grey: '#c49590',
  white: '#eadfd2',
  bone: '#e6dfcf',
  vessel: '#9b3b40',
  silicon: '#8d939c',
  gold: '#c9a45c',
  soma: '#8a5f5c',
};

export interface Theme {
  bg: string;
  ink: string;
  muted: string;
  accent: string;
  accentInk: string;
  secondary: string;
}

export interface SceneApi {
  renderAt(tS: number): void;
  setLayer(layer: Layer, on: boolean): void;
  select(electrode: number | null): void;
  setTour(on: boolean, tS: number): void;
  resetView(): void;
  zoom(factor: number): void;
  rotate(dAzimuth: number, dPolar: number): void;
  labelAnchors(): { key: string; x: number; y: number; visible: boolean }[];
  caption(): string;
  replay(tS: number): { trial: number; tMs: number };
  resize(): void;
  dispose(): void;
}

interface Options {
  host: HTMLElement;
  model: Model;
  theme: Theme;
  interactive: boolean;
  onPick: (electrode: number) => void;
}

// Deterministic hash in [0, 1).
function hash(n: number) {
  let x = Math.imul(n ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13;
  x = Math.imul(x, 0xc2b2ae35);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

function surfaceY(x: number, z: number) {
  // gentle gyri, flattened under the array and at the cut edges
  const g =
    0.32 * Math.sin(x * 0.55 + 0.6) * Math.cos(z * 0.5 - 0.3) + 0.12 * Math.sin(x * 1.3 + z * 0.9);
  const underArray = Math.max(Math.abs(x) / 5.5, Math.abs(z - ARRAY_Z) / 5.5);
  const flat = Math.min(1, Math.max(0, (underArray - 0.7) / 0.3));
  const edge = Math.min(1, (3 - z) / 1.2, (z + 7) / 1.2, (9 - Math.abs(x)) / 1.2);
  return g * flat * Math.max(0, edge);
}

/** Cross-section texture: cortical layers I-VI and white matter, with cell speckle. */
function sectionTexture(): CanvasTexture {
  const c = document.createElement('canvas');
  c.width = 512;
  c.height = 256;
  const ctx = c.getContext('2d')!;
  const bands: [number, string][] = [
    [0.06, '#dcb4ad'],
    [0.26, '#c99a94'],
    [0.36, '#c28f8a'],
    [0.56, '#b98580'],
    [0.7, '#bf8e89'],
    [1, MATERIAL.white],
  ];
  let y0 = 0;
  for (const [y1, col] of bands) {
    ctx.fillStyle = col;
    ctx.fillRect(0, y0 * c.height, c.width, (y1 - y0) * c.height + 1);
    y0 = y1;
  }
  for (let i = 0; i < 2600; i++) {
    const y = hash(i * 7 + 1) * 0.7 * c.height;
    const x = hash(i * 13 + 5) * c.width;
    const big = y > 0.56 * c.height * 0.9 && y < 0.7 * c.height && hash(i) > 0.7;
    ctx.globalAlpha = 0.25 + hash(i * 3) * 0.3;
    ctx.fillStyle = MATERIAL.vessel;
    ctx.fillRect(x, y, big ? 3 : 1.6, big ? 3 : 1.6);
  }
  ctx.globalAlpha = 0.5;
  ctx.strokeStyle = MATERIAL.vessel;
  for (let v = 0; v < 7; v++) {
    const x = hash(v * 31) * c.width;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.bezierCurveTo(x + 10, 60, x - 14, 120, x + 6, 180);
    ctx.stroke();
  }
  const tex = new CanvasTexture(c);
  tex.colorSpace = SRGBColorSpace;
  return tex;
}

export function createScene(o: Options): SceneApi {
  const { host, model, theme } = o;
  const renderer = new WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: 'low-power',
  });
  // laptops: cap at 1.5; record mode (stills, video frames) may use 2
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, o.interactive ? 1.5 : 2));
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.setClearColor(new Color(theme.bg), 1);
  renderer.domElement.setAttribute('aria-hidden', 'true');
  host.appendChild(renderer.domElement);

  const scene = new Scene();
  const camera = new PerspectiveCamera(38, 16 / 9, 0.1, 200);
  const layers: Record<Layer, Group> = {
    tissue: new Group(),
    electrodes: new Group(),
    signals: new Group(),
    decoder: new Group(),
  };
  for (const g of Object.values(layers)) scene.add(g);
  const always = new Group();
  scene.add(always);

  scene.add(new AmbientLight(0xffffff, 0.75));
  const key = new DirectionalLight(0xffffff, 1.6);
  key.position.set(6, 14, 10);
  scene.add(key);
  const rim = new DirectionalLight(0xffffff, 0.5);
  rim.position.set(-10, 6, -8);
  scene.add(rim);

  const cAccent = new Color(theme.accent);
  const cAccentInk = new Color(theme.accentInk);
  const cSecondary = new Color(theme.secondary);
  const cMuted = new Color(theme.muted);

  /* ---------------------------------------------------------------- tissue */
  const surf = new PlaneGeometry(18, 10, 120, 70);
  surf.rotateX(-Math.PI / 2);
  surf.translate(0, 0, -2);
  const sp = surf.getAttribute('position');
  for (let i = 0; i < sp.count; i++) sp.setY(i, surfaceY(sp.getX(i), sp.getZ(i)));
  surf.computeVertexNormals();
  const tissueMat = new MeshStandardMaterial({
    color: MATERIAL.pia,
    roughness: 0.75,
    transparent: true,
    opacity: 0.42,
    depthWrite: false,
    side: DoubleSide,
  });
  layers.tissue.add(new Mesh(surf, tissueMat));
  const section = sectionTexture();
  const faceMat = new MeshStandardMaterial({
    map: section,
    roughness: 0.9,
    transparent: true,
    opacity: 0.5,
    depthWrite: false,
    side: DoubleSide,
  });
  const face = (w: number, pos: [number, number, number], rotY: number) => {
    const m = new Mesh(new PlaneGeometry(w, 8), faceMat);
    m.position.set(...pos);
    m.rotation.y = rotY;
    layers.tissue.add(m);
  };
  face(18, [0, -4, 3], 0); // the cut face towards the viewer
  face(10, [9, -4, -2], Math.PI / 2);
  face(10, [-9, -4, -2], -Math.PI / 2);
  // skull plate with a craniotomy over the array (left part only)
  const bone = new Mesh(
    new BoxGeometry(4.6, 0.9, 10),
    new MeshStandardMaterial({ color: MATERIAL.bone, roughness: 0.95 }),
  );
  bone.position.set(-6.7, 0.75, -2);
  layers.tissue.add(bone);
  // surface vessels
  const vesselPts: number[] = [];
  for (let v = 0; v < 5; v++) {
    let x = -8 + hash(v + 40) * 16;
    let z = -6.5;
    for (let s = 0; s < 22; s++) {
      const nx = x + (hash(v * 100 + s) - 0.5) * 1.1;
      const nz = z + 0.45;
      if (Math.abs(nx) < 4.3 && Math.abs(nz - ARRAY_Z) < 4.3) break;
      vesselPts.push(x, surfaceY(x, z) + 0.03, z, nx, surfaceY(nx, nz) + 0.03, nz);
      x = nx;
      z = nz;
    }
  }
  const vesselGeo = new BufferGeometry();
  vesselGeo.setAttribute('position', new BufferAttribute(new Float32Array(vesselPts), 3));
  layers.tissue.add(
    new LineSegments(
      vesselGeo,
      new LineBasicMaterial({ color: MATERIAL.vessel, transparent: true, opacity: 0.8 }),
    ),
  );
  // unrecorded neighbours: a static speckle of somata through the grey matter
  const bgN = 700;
  const bgPos = new Float32Array(bgN * 3);
  for (let i = 0; i < bgN; i++) {
    bgPos[3 * i] = -8.6 + hash(i * 3 + 1) * 17.2;
    bgPos[3 * i + 1] = -0.4 - hash(i * 3 + 2) * 5.4;
    bgPos[3 * i + 2] = -6.6 + hash(i * 3 + 3) * 9.4;
  }
  const bgGeo = new BufferGeometry();
  bgGeo.setAttribute('position', new BufferAttribute(bgPos, 3));
  layers.tissue.add(
    new Points(
      bgGeo,
      new PointsMaterial({ color: MATERIAL.soma, size: 0.09, transparent: true, opacity: 0.55 }),
    ),
  );

  /* ---------------------------------------------------------------- electrodes */
  const slots = gridSlots(10);
  const slotPos = slots.map(([sx, sz]) => new Vector3(sx * PITCH, 0, ARRAY_Z + sz * PITCH));
  const silicon = new MeshStandardMaterial({
    color: MATERIAL.silicon,
    metalness: 0.65,
    roughness: 0.35,
  });
  const base = new Mesh(new BoxGeometry(PITCH * 10 + 0.2, 0.25, PITCH * 10 + 0.2), silicon);
  base.position.set(0, BASE_Y + 0.12, ARRAY_Z);
  layers.electrodes.add(base);
  const shankGeo = new ConeGeometry(0.075, SHANK, 10);
  shankGeo.rotateX(Math.PI); // apex down
  const shanks = new InstancedMesh(
    shankGeo,
    new MeshStandardMaterial({ metalness: 0.6, roughness: 0.3 }),
    slots.length,
  );
  const m4 = new Matrix4();
  slotPos.forEach((p, i) => {
    m4.makeTranslation(p.x, BASE_Y - SHANK / 2, p.z);
    shanks.setMatrixAt(i, m4);
    shanks.setColorAt(i, new Color(MATERIAL.silicon));
  });
  layers.electrodes.add(shanks);
  const tipGeo = new SphereGeometry(0.1, 10, 8);
  const tips = new InstancedMesh(tipGeo, new MeshBasicMaterial(), slots.length);
  slotPos.forEach((p, i) => {
    m4.makeTranslation(p.x, TIP_Y + 0.05, p.z);
    tips.setMatrixAt(i, m4);
    tips.setColorAt(i, cMuted);
  });
  layers.electrodes.add(tips);

  const leadStart = new Vector3(-PITCH * 5 - 0.1, BASE_Y + 0.15, ARRAY_Z);
  const pedestalTop = new Vector3(-7, 3.1, -3.4);
  const lead = new CatmullRomCurve3([
    leadStart,
    new Vector3(-5.1, 1.2, -2.6),
    new Vector3(-6.1, 2.1, -3.0),
    pedestalTop.clone().add(new Vector3(0.6, -0.3, 0)),
  ]);
  layers.electrodes.add(
    new Mesh(
      new TubeGeometry(lead, 60, 0.13, 8, false),
      new MeshStandardMaterial({ color: MATERIAL.gold, metalness: 0.7, roughness: 0.35 }),
    ),
  );
  const pedestal = new Mesh(new CylinderGeometry(0.9, 1.15, 1.8, 24), silicon);
  pedestal.position.set(-7, 2.1, -3.4);
  layers.electrodes.add(pedestal);
  const headstage = new Mesh(
    new BoxGeometry(1.9, 0.8, 1.4),
    new MeshStandardMaterial({ color: theme.muted, metalness: 0.3, roughness: 0.5 }),
  );
  headstage.position.set(-7, 3.4, -3.4);
  layers.electrodes.add(headstage);
  const headstageOut = new Vector3(-7, 3.85, -3.4);

  /* ---------------------------------------------------------------- recorded neurons */
  const units = model.units;
  const somaPos: Vector3[] = [];
  const perElectrode = new Map<number, number>();
  const unitElectrode: number[] = model.unitElectrode;
  for (let u = 0; u < units; u++) {
    const e = unitElectrode[u];
    const k = perElectrode.get(e) ?? 0;
    perElectrode.set(e, k + 1);
    const p = slotPos[(e - 1) % slotPos.length];
    const a = hash(u * 17 + 3) * Math.PI * 2 + k * 2.1;
    const r = 0.28 + hash(u * 5 + 1) * 0.22;
    somaPos.push(
      new Vector3(p.x + Math.cos(a) * r, TIP_Y - 0.1 + hash(u * 11) * 0.5, p.z + Math.sin(a) * r),
    );
  }
  const somaGeo = new SphereGeometry(0.075, 12, 10);
  const somas = new InstancedMesh(
    somaGeo,
    new MeshStandardMaterial({ roughness: 0.6, emissive: 0x000000 }),
    units,
  );
  const halos = new InstancedMesh(
    new SphereGeometry(0.075, 12, 10),
    new MeshBasicMaterial({
      color: cSecondary,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
    }),
    units,
  );
  const dendrites: number[] = [];
  somaPos.forEach((p, u) => {
    m4.makeTranslation(p.x, p.y, p.z);
    somas.setMatrixAt(u, m4);
    somas.setColorAt(u, new Color(MATERIAL.soma));
    const tilt = (hash(u * 7) - 0.5) * 0.4;
    dendrites.push(p.x, p.y, p.z, p.x + tilt, p.y + 1.6, p.z + tilt * 0.5);
    for (let b = 0; b < 3; b++) {
      const a = hash(u * 29 + b) * Math.PI * 2;
      dendrites.push(
        p.x,
        p.y,
        p.z,
        p.x + Math.cos(a) * 0.45,
        p.y - 0.25 - hash(u + b) * 0.2,
        p.z + Math.sin(a) * 0.45,
      );
    }
  });
  const dendGeo = new BufferGeometry();
  dendGeo.setAttribute('position', new BufferAttribute(new Float32Array(dendrites), 3));
  always.add(
    new LineSegments(
      dendGeo,
      new LineBasicMaterial({ color: MATERIAL.soma, transparent: true, opacity: 0.6 }),
    ),
  );
  always.add(somas);
  always.add(halos);

  /* ---------------------------------------------------------------- signals */
  const MAX_PULSES = 600;
  const pulsePos = new Float32Array(MAX_PULSES * 3);
  const pulseGeo = new BufferGeometry();
  pulseGeo.setAttribute('position', new BufferAttribute(pulsePos, 3));
  const pulses = new Points(
    pulseGeo,
    new PointsMaterial({
      color: cSecondary,
      size: 0.3,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
    }),
  );
  layers.signals.add(pulses);

  /* ---------------------------------------------------------------- decoder, screen, arm */
  const decoderPos = new Vector3(-3.6, 7.3, -5);
  const decoder = new Mesh(
    new BoxGeometry(2.6, 1.4, 0.5),
    new MeshStandardMaterial({
      color: theme.ink,
      emissive: cAccent,
      emissiveIntensity: 0.25,
      roughness: 0.4,
    }),
  );
  decoder.position.copy(decoderPos);
  layers.decoder.add(decoder);
  const screenPos = new Vector3(2.4, 8.1, -5.4);
  const screenCanvas = document.createElement('canvas');
  screenCanvas.width = 640;
  screenCanvas.height = 400;
  const screenTex = new CanvasTexture(screenCanvas);
  screenTex.colorSpace = SRGBColorSpace;
  const screen = new Mesh(new PlaneGeometry(4.8, 3), new MeshBasicMaterial({ map: screenTex }));
  screen.position.copy(screenPos);
  const bezel = new Mesh(
    new BoxGeometry(5.0, 3.2, 0.12),
    new MeshStandardMaterial({ color: theme.ink, roughness: 0.5 }),
  );
  bezel.position.copy(screenPos).add(new Vector3(0, 0, -0.08));
  layers.decoder.add(bezel, screen);
  const shoulder = new Vector3(7.6, 6.2, -5.2);
  const armMat = new MeshStandardMaterial({ color: theme.muted, metalness: 0.4, roughness: 0.4 });
  const jointMat = new MeshStandardMaterial({ color: theme.ink, roughness: 0.5 });
  const upper = new Mesh(new CylinderGeometry(0.2, 0.24, 1, 16), armMat);
  const fore = new Mesh(new CylinderGeometry(0.15, 0.2, 1, 16), armMat);
  const jShoulder = new Mesh(new SphereGeometry(0.34, 16, 12), jointMat);
  const jElbow = new Mesh(new SphereGeometry(0.26, 16, 12), jointMat);
  const hand = new Mesh(
    new SphereGeometry(0.24, 16, 12),
    new MeshStandardMaterial({ color: cAccentInk, emissive: cAccentInk, emissiveIntensity: 0.4 }),
  );
  const mount = new Mesh(new BoxGeometry(1.2, 0.5, 1.0), jointMat);
  mount.position.copy(shoulder).add(new Vector3(0, -0.5, 0));
  jShoulder.position.copy(shoulder);
  layers.decoder.add(upper, fore, jShoulder, jElbow, hand, mount);
  const L1 = 2.2;
  const L2 = 2.0;

  const MAX_PACKETS = 60;
  const packetPos = new Float32Array(MAX_PACKETS * 3);
  const packetGeo = new BufferGeometry();
  packetGeo.setAttribute('position', new BufferAttribute(packetPos, 3));
  const packets = new Points(
    packetGeo,
    new PointsMaterial({
      color: cAccent,
      size: 0.4,
      transparent: true,
      opacity: 0.95,
      depthWrite: false,
    }),
  );
  layers.decoder.add(packets);
  const streamGeo = new BufferGeometry().setFromPoints([
    headstageOut,
    decoderPos,
    decoderPos,
    screenPos,
    decoderPos,
    shoulder,
  ]);
  layers.decoder.add(
    new LineSegments(
      streamGeo,
      new LineBasicMaterial({ color: cAccent, transparent: true, opacity: 0.35 }),
    ),
  );

  /* ---------------------------------------------------------------- camera + controls */
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.minDistance = 3;
  controls.maxDistance = 45;
  controls.maxPolarAngle = Math.PI * 0.62;
  controls.enabled = o.interactive;
  let tour = !o.interactive;
  let tourStart = 0;
  const home = cameraAt(0);
  const setCam = (pos: number[], target: number[]) => {
    camera.position.set(pos[0], pos[1], pos[2]);
    controls.target.set(target[0], target[1], target[2]);
    camera.lookAt(controls.target);
  };
  setCam(home.pos, home.target);
  controls.update();

  let selected: number | null = null;
  const ray = new Raycaster();
  const ndc = new Vector2();
  let down: { x: number; y: number } | null = null;
  const onDown = (e: PointerEvent) => (down = { x: e.clientX, y: e.clientY });
  const onUp = (e: PointerEvent) => {
    if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
    const r = renderer.domElement.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects([shanks, tips], false)[0];
    if (hit && hit.instanceId !== undefined) o.onPick(hit.instanceId + 1);
  };
  if (o.interactive) {
    renderer.domElement.addEventListener('pointerdown', onDown);
    renderer.domElement.addEventListener('pointerup', onUp);
  }

  /* ---------------------------------------------------------------- per-frame state */
  const tl = timeline(
    model.trials.map((t) => t.durationMs),
    400,
  );
  const lastCount = model.neuronCounts.length - 1;
  const decoderName = model.decoders[0];
  const white = new Color(1, 1, 1);
  const tmp = new Color();
  const somaBase = new Color(MATERIAL.soma);
  const tipBase = new Color(theme.muted);
  const shankBase = new Color(MATERIAL.silicon);
  const obj = new Object3D();
  const up = new Vector3(0, 1, 0);
  const q = new Quaternion();
  const v = new Vector3();
  let captionKey = 'overview';

  function placeLimb(mesh: Mesh, a: Vector3, b: Vector3) {
    v.subVectors(b, a);
    const len = v.length();
    mesh.position.copy(a).addScaledVector(v, 0.5);
    q.setFromUnitVectors(up, v.normalize());
    mesh.quaternion.copy(q);
    mesh.scale.set(1, len, 1);
  }

  function drawScreen(trialIdx: number, tMs: number) {
    const ctx = screenCanvas.getContext('2d')!;
    const w = screenCanvas.width;
    const h = screenCanvas.height;
    ctx.fillStyle = theme.bg;
    ctx.fillRect(0, 0, w, h);
    const tr = model.trials[trialIdx];
    const est = tr.decoded[decoderName][lastCount][0];
    const lo = [tr.target[0], tr.target[1]];
    const hi = [tr.target[0], tr.target[1]];
    for (const p of [tr.truePos, est])
      for (let i = 0; i < p.length; i++) {
        lo[i % 2] = Math.min(lo[i % 2], p[i]);
        hi[i % 2] = Math.max(hi[i % 2], p[i]);
      }
    const half = Math.max(30, (hi[0] - lo[0]) / 2 + 8, (hi[1] - lo[1]) / 2 + 8);
    const min = [(lo[0] + hi[0]) / 2 - half * 1.6, (lo[1] + hi[1]) / 2 - half];
    const max = [(lo[0] + hi[0]) / 2 + half * 1.6, (lo[1] + hi[1]) / 2 + half];
    const s = Math.min((w - 40) / (max[0] - min[0]), (h - 40) / (max[1] - min[1]));
    const ox = (w - s * (max[0] - min[0])) / 2;
    const oy = (h - s * (max[1] - min[1])) / 2;
    const map = (x: number, y: number): [number, number] => [
      ox + (x - min[0]) * s,
      h - oy - (y - min[1]) * s,
    ];
    const [gx, gy] = map(tr.target[0], tr.target[1]);
    ctx.lineWidth = 5;
    ctx.strokeStyle = theme.secondary;
    ctx.strokeRect(gx - 18, gy - 18, 36, 36);
    ctx.lineWidth = 6;
    const n = binsUpTo(model.binMs, tMs, tr.bins);
    const trace = (p: Float32Array, color: string, dash: number[]) => {
      if (n < 1) return;
      ctx.strokeStyle = color;
      ctx.setLineDash(dash);
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const [x, y] = map(p[2 * i], p[2 * i + 1]);
        if (i) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };
    trace(tr.truePos, theme.ink, []);
    trace(est, theme.accentInk, [14, 8]);
    const [ax, ay] = map(...sampleAt(tr.truePos, model.binMs, tMs));
    ctx.fillStyle = theme.ink;
    ctx.beginPath();
    ctx.arc(ax, ay, 12, 0, Math.PI * 2);
    ctx.fill();
    const [dx, dy] = map(...sampleAt(est, model.binMs, tMs));
    ctx.lineWidth = 6;
    ctx.strokeStyle = theme.accentInk;
    ctx.beginPath();
    ctx.arc(dx, dy, 20, 0, Math.PI * 2);
    ctx.stroke();
    screenTex.needsUpdate = true;
  }

  function renderAt(tS: number) {
    const { trial, tMs } = tl.at(tS * 1000 * REPLAY_SPEED);
    const tr = model.trials[trial];

    // camera: guided tour (and record mode) follow the fixed path; otherwise the user orbits
    if (tour) {
      const c = cameraAt((tS - tourStart) % TOUR_SECONDS);
      setCam(c.pos, c.target);
      captionKey = c.caption;
    }

    // neurons and electrode tips
    const tipGlow = new Float32Array(slots.length);
    for (let u = 0; u < units; u++) {
      const g = spikeGlow(tr.spikes[u], tMs, 70);
      const slot = (unitElectrode[u] - 1) % slots.length;
      tipGlow[slot] = Math.max(tipGlow[slot], g);
      const lit = g < 0.05 ? 0 : g;
      tmp
        .copy(somaBase)
        .lerp(white, lit * 0.25)
        .lerp(cSecondary, lit);
      somas.setColorAt(u, tmp);
      const sc = lit ? 1.4 + lit * 3 : 0;
      obj.position.copy(somaPos[u]);
      obj.scale.setScalar(sc);
      obj.updateMatrix();
      halos.setMatrixAt(u, obj.matrix);
    }
    somas.instanceColor!.needsUpdate = true;
    halos.instanceMatrix.needsUpdate = true;
    for (let i = 0; i < slots.length; i++) {
      tips.setColorAt(i, tmp.copy(tipBase).lerp(cSecondary, Math.min(1, tipGlow[i] * 1.4)));
      shanks.setColorAt(i, i + 1 === selected ? cAccentInk : shankBase);
    }
    tips.instanceColor!.needsUpdate = true;
    shanks.instanceColor!.needsUpdate = true;

    // pulses up the shanks and the lead
    let k = 0;
    for (let u = 0; u < units && k < MAX_PULSES; u++) {
      const slot = (unitElectrode[u] - 1) % slots.length;
      const sp0 = slotPos[slot];
      for (const s of recentSpikes(tr.spikes[u], tMs, LEAD_WINDOW_MS)) {
        if (k >= MAX_PULSES) break;
        const f = (tMs - s) / LEAD_WINDOW_MS;
        if (f < 0.25) v.set(sp0.x, TIP_Y + (BASE_Y - TIP_Y) * (f / 0.25), sp0.z);
        else if (f < 0.4) v.set(sp0.x, BASE_Y + 0.2, sp0.z).lerp(leadStart, (f - 0.25) / 0.15);
        else lead.getPoint((f - 0.4) / 0.6, v);
        pulsePos.set([v.x, v.y, v.z], 3 * k++);
      }
    }
    pulseGeo.setDrawRange(0, k);
    pulseGeo.getAttribute('position').needsUpdate = true;

    // packets: one per decoder bin, headstage -> decoder -> screen and arm
    let p = 0;
    const tReplay = tS * 1000 * REPLAY_SPEED;
    const lastPacket = Math.floor(tReplay / PACKET_MS) * PACKET_MS;
    for (
      let pt = lastPacket;
      pt > tReplay - PACKET_TRAVEL_MS * 2 && p < MAX_PACKETS - 2;
      pt -= PACKET_MS
    ) {
      const f = (tReplay - pt) / PACKET_TRAVEL_MS;
      if (f < 1) {
        v.copy(headstageOut).lerp(decoderPos, f);
        packetPos.set([v.x, v.y, v.z], 3 * p++);
      } else {
        const g = f - 1;
        v.copy(decoderPos).lerp(screenPos, g);
        packetPos.set([v.x, v.y, v.z], 3 * p++);
        v.copy(decoderPos).lerp(shoulder, g);
        packetPos.set([v.x, v.y, v.z], 3 * p++);
      }
    }
    packetGeo.setDrawRange(0, p);
    packetGeo.getAttribute('position').needsUpdate = true;
    (decoder.material as MeshStandardMaterial).emissiveIntensity =
      0.25 + 0.25 * Math.exp(-((tReplay - lastPacket) / 30));

    // decoded movement: screen cursor and arm
    drawScreen(trial, tMs);
    const est = tr.decoded[decoderName][lastCount][0];
    const [px, py] = sampleAt(est, model.binMs, tMs);
    const { min, max } = model.bounds;
    const hx = -1.6 + ((px - min[0]) / (max[0] - min[0])) * 3.2;
    const hy = 1.2 + ((py - min[1]) / (max[1] - min[1])) * 2.4;
    const sol = solveArm(hx, hy, L1, L2);
    const pts = armPoints(sol.shoulder, sol.elbow, L1, L2);
    const elbow = new Vector3(shoulder.x + pts.elbow[0], shoulder.y + pts.elbow[1], shoulder.z);
    const wrist = new Vector3(shoulder.x + pts.hand[0], shoulder.y + pts.hand[1], shoulder.z);
    placeLimb(upper, shoulder, elbow);
    placeLimb(fore, elbow, wrist);
    jElbow.position.copy(elbow);
    hand.position.copy(wrist);

    renderer.render(scene, camera);
  }

  const anchors: Record<string, Vector3> = {
    cortex: new Vector3(-7.5, -1.2, 3),
    array: new Vector3(3.6, 0.9, 1.3),
    neurons: new Vector3(2.2, -2.9, 1.1),
    headstage: new Vector3(-7, 4.4, -3.4),
    decoder: new Vector3(-3.6, 8.4, -5),
    screen: new Vector3(2.4, 10, -5.4),
    arm: new Vector3(7.6, 9.6, -5.2),
  };
  const anchorLayer: Record<string, Layer | null> = {
    cortex: 'tissue',
    array: 'electrodes',
    neurons: null,
    headstage: 'electrodes',
    decoder: 'decoder',
    screen: 'decoder',
    arm: 'decoder',
  };

  function resize() {
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // portrait screens: widen the field of view so the tour framing still fits
    camera.fov = camera.aspect < 1.3 ? Math.min(72, (38 * 1.3) / camera.aspect) : 38;
    camera.updateProjectionMatrix();
  }
  resize();

  return {
    renderAt,
    resize,
    setLayer(layer, on) {
      layers[layer].visible = on;
    },
    select(e) {
      selected = e;
    },
    setTour(on, tS) {
      tour = on;
      tourStart = tS;
      controls.enabled = o.interactive && !on;
      if (!on) controls.update();
    },
    resetView() {
      setCam(home.pos, home.target);
      controls.update();
    },
    zoom(factor) {
      v.subVectors(camera.position, controls.target).multiplyScalar(factor);
      const d = Math.min(controls.maxDistance, Math.max(controls.minDistance, v.length()));
      camera.position.copy(controls.target).add(v.setLength(d));
      controls.update();
    },
    rotate(dAz, dPolar) {
      const sph = new Spherical().setFromVector3(v.subVectors(camera.position, controls.target));
      sph.theta += dAz;
      sph.phi = Math.min(controls.maxPolarAngle, Math.max(0.05, sph.phi + dPolar));
      camera.position.copy(controls.target).add(v.setFromSpherical(sph));
      camera.lookAt(controls.target);
      controls.update();
    },
    labelAnchors() {
      const w = host.clientWidth;
      const h = host.clientHeight;
      return Object.entries(anchors).map(([k, a]) => {
        v.copy(a).project(camera);
        const layer = anchorLayer[k];
        return {
          key: k,
          x: (v.x * 0.5 + 0.5) * w,
          y: (-v.y * 0.5 + 0.5) * h,
          visible: v.z < 1 && (!layer || layers[layer].visible),
        };
      });
    },
    caption: () => captionKey,
    replay: (tS) => tl.at(tS * 1000 * REPLAY_SPEED),
    dispose() {
      renderer.domElement.removeEventListener('pointerdown', onDown);
      renderer.domElement.removeEventListener('pointerup', onUp);
      controls.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
