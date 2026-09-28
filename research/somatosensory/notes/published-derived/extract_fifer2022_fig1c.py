"""DIGITISE per-electrode PF finger (hue class) from Fifer et al. 2022 Neurology 98(7):e679, Figure 1C
(PMID 34880087, PMC8865889, DOI 10.1212/WNL.0000000000013173). One JHU participant, 3 stimulating arrays (bilateral).
Image: https://cdn.ncbi.nlm.nih.gov/pmc/blobs/fa94/8865889/f3ebe80069bc/NEUROLOGY2021174458F1.jpg (694 x 356 px; the only
resolution reachable without a login/bot wall). Legend (quote): "Hue denotes finger; saturation denotes finger segment; and
hatching denotes a dorsal hand percept ... For each electrode on the array, the set of colors present within the square
corresponds to a finger segment in panel A that was reported for that electrode. Gray squares are electrodes not wired for
stimulation, and white squares did not elicit any single percept multiple times."
Pitch: "32-channel stimulating array (4 x 2.4 mm, 400-um pitch, custom population within 6 x 10 configuration...)" (Methods).
Method: array blobs = non-white pixels after a 5x5 opening (removes the thin zoom lines) + closing + hole filling; minimum-area
rectangle -> 10 x 6 cell lattice; each cell sampled on a 5 x 5 lattice in its central 60 %; samples classified as grey
(unwired), white (no repeatable percept), or a hue class: red (<15 deg or >340), orange (15-38), yellow (38-70), green (70-170);
low-saturation pale samples (S < 0.12) and hatching pixels are ignored. A hue class is 'present' if >= 20 % of the coloured
samples. Which finger each hue denotes is NOT resolved here (only within-array identity of hue classes is used).
LOW RESOLUTION: cells are ~14 px; expect some errors on striped (multi-segment) cells.
"""
import os, sys, csv, colorsys, urllib.request
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

SCR = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = os.path.dirname(os.path.abspath(__file__))
fn = os.path.join(SCR, 'fifer_f1.jpg')
if not os.path.exists(fn):
    req = urllib.request.Request('https://cdn.ncbi.nlm.nih.gov/pmc/blobs/fa94/8865889/f3ebe80069bc/NEUROLOGY2021174458F1.jpg',
                                 headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0',
                                          'Referer': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8865889/', 'Accept': 'image/*'})
    open(fn, 'wb').write(urllib.request.urlopen(req, timeout=120).read())
im = np.asarray(Image.open(fn).convert('RGB')).astype(float)
H, W, _ = im.shape
nw = im.min(2) < 225
nw[:188, :] = False  # panel C only (top of middle array is at y ~ 192)
nw = ndi.binary_opening(nw, np.ones((5, 5)))
nw = ndi.binary_fill_holes(ndi.binary_closing(nw, np.ones((5, 5))))
lab, n = ndi.label(nw)
blobs = []
for i, sl in enumerate(ndi.find_objects(lab)):
    ys, xs = np.nonzero(lab == i + 1)
    if len(xs) > 3000:
        blobs.append((xs.astype(float), ys.astype(float)))
blobs.sort(key=lambda b: b[0].mean())
names = ['left_array_A', 'left_array_B', 'right_array']  # left-to-right in Fig 1C


def classify(rgb):
    r, g, b = rgb / 255
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if v < 0.25:
        return 'black'
    if s < 0.12:
        return 'white' if v > 0.85 else 'grey'
    hd = h * 360
    if hd < 15 or hd > 340:
        return 'red'
    if hd < 38:
        return 'orange'
    if hd < 70:
        return 'yellow'
    if hd < 170:
        return 'green'
    return 'other'


rows = []
for name, (xs, ys) in zip(names, blobs):
    cx, cy = xs.mean(), ys.mean(); best = None
    for a in np.arange(0, 180, 0.2):
        t = np.deg2rad(a)
        u = (xs - cx) * np.cos(t) + (ys - cy) * np.sin(t); v = -(xs - cx) * np.sin(t) + (ys - cy) * np.cos(t)
        area = np.ptp(u) * np.ptp(v)
        if best is None or area < best[0]:
            best = (area, a, u.min(), u.max(), v.min(), v.max())
    _, a, u0, u1, v0, v1 = best
    t = np.deg2rad(a); eu = np.array([np.cos(t), np.sin(t)]); ev = np.array([-np.sin(t), np.cos(t)])
    if (u1 - u0) < (v1 - v0):
        eu, ev, u0, u1, v0, v1 = ev, -eu, v0, v1, -u1, -u0
    print(name, 'angle %.1f' % a, 'long %.1f short %.1f ratio %.3f' % (u1 - u0, v1 - v0, (u1 - u0) / (v1 - v0)))
    for i in range(10):
        for j in range(6):
            cnt = {}
            for fa in np.linspace(0.2, 0.8, 5):
                for fb in np.linspace(0.2, 0.8, 5):
                    p = np.array([cx, cy]) + (u0 + (i + fa) * (u1 - u0) / 10) * eu + (v0 + (j + fb) * (v1 - v0) / 6) * ev
                    x, y = int(round(p[0])), int(round(p[1]))
                    k = classify(im[y, x])
                    cnt[k] = cnt.get(k, 0) + 1
            col = {k: v for k, v in cnt.items() if k in ('red', 'orange', 'yellow', 'green')}
            ncol = sum(col.values())
            if cnt.get('grey', 0) >= 13:
                status = 'unwired'
            elif ncol >= 5:
                status = 'PF'
            elif cnt.get('white', 0) >= 10:
                status = 'no_repeatable_percept'
            else:
                status = 'ambiguous'
            hues = sorted([k for k, v in col.items() if ncol and v / ncol >= 0.2], key=lambda k: -col[k]) if status == 'PF' else []
            rows.append(dict(participant='JHU-1', array=name, grid_long=i, grid_short=j, x_mm=round(i * 0.4, 2),
                             y_mm=round(j * 0.4, 2), status=status, hue_classes='|'.join(hues),
                             samples=';'.join(f'{k}:{v}' for k, v in sorted(cnt.items(), key=lambda t: -t[1])),
                             source='Fifer 2022 Neurology Fig 1C (PMC8865889)', DIGITISED='yes'))
with open(os.path.join(OUT, 'pf_per_electrode_fifer2022.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for name in names:
    rs = [r for r in rows if r['array'] == name]
    c = {}
    for r in rs:
        c[r['status']] = c.get(r['status'], 0) + 1
    print(name, c)
    for i in range(10):
        print('   ', ' '.join('%-13s' % (r['hue_classes'] or r['status'][:6]) for r in rs if r['grid_long'] == i))
