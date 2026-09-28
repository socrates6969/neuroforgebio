"""DIGITISE per-electrode dominant PF hand segment from Greenspon et al. 2025 Nat Biomed Eng,
Extended Data Fig. 1 (PMID 39643730, PMC12176618, DOI 10.1038/s41551-024-01299-z).

Method (no modelling; pure figure read-out):
 1. Image: https://media.springernature.com/full/springer-static/esm/art%3A10.1038%2Fs41551-024-01299-z/MediaObjects/41551_2024_1299_Fig8_ESM.jpg
    (1718 x 2423 px). Legend: "The array diagrams show the dominant hand segment for each electrode."
 2. The figure was drawn by the authors' open code (github.com/CorticalBionics/StableAndPreciseICMS, MIT):
    PlotSegmentedHand.m / PlotGridSegments.m / GetSegmentLabels.m ('DailyCentroid': the segment that contains
    the across-session mean PF centroid). Cell colours are the exact segment colours in GetHandSegments.m;
    grey [.6 .6 .6] = wired electrode with no PF on that surface; white = unwired.
 3. Array geometry: each array outline is found as a non-white blob; its centre, rotation and size are
    fitted (minimum-area rectangle). Cell centres are then generated with the code's own geometry
    (10 x 6 ChannelNumbers grid, x_offset = 4, y_offset = 6, rotation from LoadSubjectChannelMap.m, YDir reverse).
    Orientation (4 sign/flip variants) is chosen by maximising agreement between wired/unwired cells and the
    code's chequerboard map; the agreement is reported.
 4. Colour of each wired cell = median RGB of a 7 x 7 px patch at the cell centre; classified as the nearest
    segment colour (or grey). Distance is reported; flagged if > 40 (RGB units).
 5. Segment centroids: regions of BoundaryMapPalm.png / BoundaryMapDorsum.png resized to 1200 x 1050 (as the
    code does), 4-connected components, tags in the code's order (column-major first pixel); one swap
    (D4p-u <-> D4d-dr) corrected by finger-axis geometry. Tags with identical colours (e.g. D2d-du / D2d-dr)
    cannot be separated in the figure and are merged; the merged centroid is the pixel-weighted mean.
    Hand-map scale: 5 px = 1 mm, as used in the authors' Figure3_Somatotopy.m (line 160, './ 5'); the paper
    text does not state it.
Run: .venv python extract_greenspon2025_pf_segments.py <scratch_dir_with_images_and_code>
"""
import sys, os, re, json, urllib.request
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

SCR = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = os.path.dirname(os.path.abspath(__file__))
ED1 = os.path.join(SCR, 'gs_ED1.jpg')
URL_ED1 = ('https://media.springernature.com/full/springer-static/esm/art%3A10.1038%2Fs41551-024-01299-z/'
           'MediaObjects/41551_2024_1299_Fig8_ESM.jpg')
RAW = 'https://raw.githubusercontent.com/CorticalBionics/StableAndPreciseICMS/HEAD/'
need = {ED1: URL_ED1,
        os.path.join(SCR, 'spi', 'GetHandSegments.m'): RAW + 'HelperFunctions/GetHandSegments.m',
        os.path.join(SCR, 'spi', 'BoundaryMapPalm.png'): RAW + 'ReferenceImages/BoundaryMapPalm.png',
        os.path.join(SCR, 'spi', 'BoundaryMapDorsum.png'): RAW + 'ReferenceImages/BoundaryMapDorsum.png'}
for p, u in need.items():
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        open(p, 'wb').write(urllib.request.urlopen(req, timeout=120).read())

# ---------------- channel maps (verbatim from LoadSubjectChannelMap.m) ----------------
PAT_A = [[65, None, 72, None, 85, 91], [None, 77, None, 81, None, 92], [67, None, 74, None, 87, None],
         [None, 79, None, 82, None, 93], [69, None, 76, None, 88, None], [None, 66, None, 84, None, 94],
         [71, None, 78, None, 89, None], [None, 68, None, 83, None, 96], [73, None, 80, None, 90, None],
         [75, 70, None, 86, None, 95]]
PAT_B = [[193, None, 200, None, 213, 219], [None, 205, None, 209, None, 220], [195, None, 202, None, 215, None],
         [None, 207, None, 210, None, 221], [197, None, 204, None, 216, None], [None, 194, None, 212, None, 222],
         [199, None, 206, None, 217, None], [None, 196, None, 211, None, 224], [201, None, 208, None, 218, None],
         [203, 198, None, 214, None, 223]]
# CRS02 sensory arrays differ slightly (rows 4-6)
PAT_A_CRS02 = [[65, None, 72, None, 85, 91], [None, 77, None, 81, None, 92], [67, None, 74, None, 87, None],
               [None, None, None, 82, None, 94], [69, 79, 76, None, 88, None], [None, 66, None, 84, None, 93],
               [71, None, 78, None, 89, None], [None, 68, None, 83, None, 96], [73, None, 80, None, 90, None],
               [75, 70, None, 86, None, 95]]
PAT_B_CRS02 = [[193, None, 200, None, 213, 219], [None, 205, None, 209, None, 220], [195, None, 202, None, 215, None],
               [None, 207, None, 210, None, 222], [197, None, 204, None, 216, None], [None, 194, None, 212, None, 221],
               [199, None, 206, None, 217, None], [None, 196, None, 211, None, 224], [201, None, 208, None, 218, None],
               [203, 198, None, 214, None, 223]]


def channel_numbers(pat, offset):
    vals = sorted(v for r in pat for v in r if v is not None)
    rank = {v: i + 1 + offset for i, v in enumerate(vals)}
    return [[rank[v] if v is not None else None for v in r] for r in pat]


# sensory array 1 = first 'Sensory' entry in ArrayNames (channels 1-32), array 2 = channels 33-64
SUBJ = {
    'C1': dict(code='BCI02', arrays=[('MedialSensory', -105, PAT_A), ('LateralSensory', 45, PAT_B)]),
    'P2': dict(code='CRS02', arrays=[('LateralSensory', 60, PAT_A_CRS02), ('MedialSensory', 15, PAT_B_CRS02)]),
    'P3': dict(code='CRS07', arrays=[('LateralSensory', 75, PAT_A), ('MedialSensory', -10, PAT_B)]),
}
PART_ORDER = ['C1', 'P2', 'P3']  # figure rows


# ---------------- hand segments ----------------
def parse_tags(txt):
    return [(m.group(1), [float(v) / 100 for v in re.split(r'[,\s]+', m.group(2).strip())])
            for m in re.finditer(r"'([^']+)',\s*\[([^\]]+)\]", txt)]


src = open(os.path.join(SCR, 'spi', 'GetHandSegments.m')).read()
pb, db = src.split('% Dorsum segments')
TAGS = {'palm': parse_tags(pb), 'dors': parse_tags(db.split('for i = 1:size(dbt_regions')[0])}


def regions(fn):
    im = np.asarray(Image.open(fn).convert('RGB').resize((1050, 1200), Image.BILINEAR)).astype(float)
    free = ~(im.mean(2) < 128)
    lab, n = ndi.label(free, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    H = lab.shape[0]
    regs = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < 50:
            continue
        regs.append(((xs * H + ys).min(), xs.mean(), ys.mean(), len(xs)))
    regs.sort()
    return regs[1:]  # drop background


SEG = {}
for key, fn in [('palm', 'BoundaryMapPalm.png'), ('dors', 'BoundaryMapDorsum.png')]:
    regs = regions(os.path.join(SCR, 'spi', fn))
    assert len(regs) == len(TAGS[key])
    rows = [dict(tag=t, rgb=c, cx=r[1], cy=r[2], npx=r[3]) for r, (t, c) in zip(regs, TAGS[key])]
    if key == 'palm':  # geometric fix: the tip region labelled D4p-u is D4d-du's partner (D4d-dr), and vice versa
        a = [r for r in rows if r['tag'] == 'D4p-u'][0]; b = [r for r in rows if r['tag'] == 'D4d-dr'][0]
        a['tag'], b['tag'] = 'D4d-dr', 'D4p-u'
        a['rgb'], b['rgb'] = [1 / 100 * 1, 66 / 100, 96 / 100], [51 / 100, 83 / 100, 98 / 100]
    # merge identical colours
    merged = {}
    for r in rows:
        k = tuple(round(v, 3) for v in r['rgb'])
        m = merged.setdefault(k, dict(tags=[], rgb=list(k), sx=0, sy=0, npx=0))
        m['tags'].append(r['tag']); m['sx'] += r['cx'] * r['npx']; m['sy'] += r['cy'] * r['npx']; m['npx'] += r['npx']
    SEG[key] = [dict(label='+'.join(m['tags']), rgb=m['rgb'], cx=m['sx'] / m['npx'], cy=m['sy'] / m['npx'],
                     area_mm2=m['npx'] / 25.0) for m in merged.values()]

palm_area = sum(s['area_mm2'] for s in SEG['palm'] if s['label'] != 'W')
print('palmar hand area excl. wrist (5 px/mm): %.1f cm2 (paper: palmar surface 165 cm2)' % (palm_area / 100))

# ---------------- arrays in ED Fig 1 ----------------
im = np.asarray(Image.open(ED1).convert('RGB')).astype(float)
nw = im.min(axis=2) < 225
nw[:, :460] = False; nw[:, 1215:] = False
nw = ndi.binary_fill_holes(ndi.binary_closing(nw, np.ones((9, 9))))
lab, n = ndi.label(nw)
blobs = []
for i, sl in enumerate(ndi.find_objects(lab)):
    if sl[0].stop - sl[0].start > 120 and sl[1].stop - sl[1].start > 120:
        ys, xs = np.nonzero(lab == i + 1)
        blobs.append((xs.astype(float), ys.astype(float)))
assert len(blobs) == 12
blobs.sort(key=lambda b: (round(b[1].mean() / 150), b[0].mean()))  # rows, then left(palm)/right(dorsum)


def fit_rect(xs, ys):
    cx, cy = xs.mean(), ys.mean(); best = None
    for a in np.arange(0, 90, 0.1):
        t = np.deg2rad(a)
        u = (xs - cx) * np.cos(t) + (ys - cy) * np.sin(t); v = -(xs - cx) * np.sin(t) + (ys - cy) * np.cos(t)
        ar = np.ptp(u) * np.ptp(v)
        if best is None or ar < best[0]:
            best = (ar, np.ptp(u), np.ptp(v))
    return cx, cy, max(best[1], best[2]) / 10.0, min(best[1], best[2]) / 6.0


GREY = [0.8, 0.8, 0.8]  # code uses .6 but the published raster shows (204,204,204) for no-PF cells (measured)


def classify(rgb, key):
    cands = [(s['label'], np.array(s['rgb']) * 255) for s in SEG[key]] + [('NONE', np.array(GREY) * 255)]
    d = [(np.linalg.norm(rgb - c), lab_) for lab_, c in cands]
    d.sort()
    return d[0][1], d[0][0], d[1][0]


records = []
report = []
for bi in range(0, 12, 2):
    part = PART_ORDER[bi // 4]
    upper = (bi % 4) == 0
    S = SUBJ[part]
    # PlotSegmentedHand: the Medial array is always drawn in the upper inset
    arr_i = [k for k, a in enumerate(S['arrays']) if ('Medial' in a[0]) == upper][0]
    name, rot, pat = S['arrays'][arr_i]
    chnum = channel_numbers(pat, 32 * arr_i)
    for surf_i, key in enumerate(['palm', 'dors']):
        xs, ys = blobs[bi + surf_i]
        cx, cy, s1, s2 = fit_rect(xs, ys)
        s = (s1 + s2) / 2
        best = None
        for sx in (1, -1):
            for sy in (1, -1):
                for rs in (1, -1):
                    agree = 0; cells = []
                    r = np.deg2rad(rs * rot)
                    for gy in range(10):
                        for gx in range(6):
                            x = sx * (gx + 1 + 0.5 - 4); y = sy * (gy + 1 + 0.5 - 6)
                            xr = x * np.cos(r) - y * np.sin(r); yr = y * np.cos(r) + x * np.sin(r)
                            px, py = cx + s * xr, cy + s * yr
                            patch = im[int(round(py)) - 3:int(round(py)) + 4, int(round(px)) - 3:int(round(px)) + 4].reshape(-1, 3)
                            rgb = np.median(patch, axis=0)
                            wired_img = rgb.min() < 235
                            wired = pat[gy][gx] is not None
                            agree += (wired_img == wired)
                            cells.append((gy, gx, px, py, rgb, wired))
                    if best is None or agree > best[0]:
                        best = (agree, (sx, sy, rs), cells)
        agree, variant, cells = best
        report.append(dict(participant=part, array=name, surface=key, agreement=f'{agree}/60', variant=variant,
                           cell_px=round(s, 2)))
        for gy, gx, px, py, rgb, wired in cells:
            if not wired:
                continue
            labl, dist, d2 = classify(rgb, key)
            records.append(dict(participant=part, subject_code=S['code'], array=name, rotation=rot, surface=key,
                                grid_row=gy, grid_col=gx, channel=chnum[gy][gx], channel_label=pat[gy][gx],
                                seg=labl, rgb=[int(v) for v in rgb], dist=round(dist, 1), margin=round(d2 - dist, 1),
                                px=round(px, 1), py=round(py, 1)))

json.dump(dict(report=report, records=records, segments=SEG), open(os.path.join(OUT, 'greenspon2025_ed1_extraction.json'), 'w'), indent=1)
for r in report:
    print(r)
bad = [r for r in records if r['dist'] > 40]
print('cells:', len(records), ' colour distance > 40:', len(bad))
for r in bad:
    print('  FLAG', r['participant'], r['array'], r['surface'], r['grid_row'], r['grid_col'], r['rgb'], r['seg'], r['dist'])
