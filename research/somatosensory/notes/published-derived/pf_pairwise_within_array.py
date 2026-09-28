"""Within-array PF-independence quantities computed DIRECTLY from digitised per-electrode data (no model fitting).

Inputs (produced by the two extract_*.py scripts in this folder):
  <scratch>/ed1_extraction.json        Greenspon 2025 ED Fig 1 read-out (dominant PF segment per electrode, palm + dorsum)
  pf_per_electrode_armentasalas2018.csv Armenta Salas 2018 Fig 2B read-out (body regions per electrode)
Outputs (this folder):
  pf_per_electrode_greenspon2025.csv, pf_pairs_greenspon2025.csv, pf_pairs_armentasalas2018.csv,
  pf_pairwise_summary.json (printed as well)
Definitions
  cortical distance = 0.4 mm x Euclidean grid distance (same array only). 400 um pitch is stated for the Pitt/Chicago
    arrays (Hughes 2022, Fifer 2022; code multiplies by 0.4); for Armenta Salas it is ASSUMED.
  Greenspon PF location = centroid of the dominant hand segment (the segment containing the across-session mean PF
    centroid, per the authors' GetSegmentLabels 'DailyCentroid'); coordinates = the authors' 1050 x 1200 px hand map,
    x right, y down, converted with 5 px = 1 mm (authors' Figure3_Somatotopy.m). Palm and dorsum are separate maps;
    distances are only computed within one surface. Segment quantisation: pairs in the same segment have distance 0.
  same_segment = the two electrodes share a dominant segment on at least one surface.
  jaccard = |A n B| / |A u B| over each electrode's set {palm segment, dorsum segment} (a coarse overlap proxy).
  same_digit = share a digit (D1..D5 on either surface; palm/dorsum of the same finger count as the same digit;
    palm-body and dorsum-body regions count as the non-digit classes 'palm' and 'dorsum').
  Permutation test: electrode PF labels are shuffled across the wired sites of the same array (positions fixed),
    5000 shuffles, seed 20260926; statistic = Spearman rho (distance metrics) or the difference in P(same segment)
    between pairs <= 0.57 mm (nearest + diagonal neighbours) and all pairs.
"""
import os, sys, json, csv, itertools, re
import numpy as np
from scipy import stats

SCR = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(20260926)
NPERM = 5000

_f = os.path.join(OUT, 'greenspon2025_ed1_extraction.json')
D = json.load(open(_f if os.path.exists(_f) else os.path.join(SCR, 'ed1_extraction.json')))
SEG = {k: {s['label']: s for s in v} for k, v in D['segments'].items()}


def digit_of(label, surf):
    m = re.match(r'D(\d)', label)
    if m:
        return 'D' + m.group(1)
    return 'palm' if surf == 'palm' else 'dorsum'


# ---------------- per-electrode table (Greenspon) ----------------
E = {}
for r in D['records']:
    key = (r['participant'], r['array'], r['grid_row'], r['grid_col'])
    e = E.setdefault(key, dict(participant=r['participant'], subject_code=r['subject_code'], array=r['array'],
                               electrode_channel=r['channel'], channel_label=r['channel_label'],
                               grid_row=r['grid_row'], grid_col=r['grid_col'],
                               x_mm=round(r['grid_col'] * 0.4, 2), y_mm=round(r['grid_row'] * 0.4, 2)))
    seg = '' if r['seg'] == 'NONE' else r['seg']
    e[r['surface'] + '_segment'] = seg
    if seg:
        s = SEG[r['surface']][seg]
        e[r['surface'] + '_centroid_x_mm'] = round(s['cx'] / 5, 2)
        e[r['surface'] + '_centroid_y_mm'] = round(s['cy'] / 5, 2)
        e[r['surface'] + '_segment_area_mm2'] = round(s['area_mm2'], 1)
    else:
        e[r['surface'] + '_centroid_x_mm'] = e[r['surface'] + '_centroid_y_mm'] = e[r['surface'] + '_segment_area_mm2'] = ''
    e[r['surface'] + '_colour_dist'] = r['dist']
elec = list(E.values())
for e in elec:
    e['has_PF'] = int(bool(e['palm_segment'] or e['dors_segment']))
    e['digits'] = '|'.join(sorted({digit_of(e[s + '_segment'], s) for s in ('palm', 'dors') if e[s + '_segment']}))
    e['source'] = 'Greenspon 2025 NBE Extended Data Fig 1 (PMC12176618) + code geometry (StableAndPreciseICMS)'
    e['DIGITISED'] = 'yes'
cols = ['participant', 'subject_code', 'array', 'electrode_channel', 'channel_label', 'grid_row', 'grid_col', 'x_mm', 'y_mm',
        'has_PF', 'digits', 'palm_segment', 'palm_centroid_x_mm', 'palm_centroid_y_mm', 'palm_segment_area_mm2',
        'dors_segment', 'dors_centroid_x_mm', 'dors_centroid_y_mm', 'dors_segment_area_mm2', 'palm_colour_dist',
        'dors_colour_dist', 'source', 'DIGITISED']
with open(os.path.join(OUT, 'pf_per_electrode_greenspon2025.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for e in sorted(elec, key=lambda e: (e['participant'], e['array'], e['grid_row'], e['grid_col'])):
        w.writerow({k: e.get(k, '') for k in cols})


# ---------------- pair measures ----------------
def pair_measures(a, b):
    out = {}
    A = {(s, a[s + '_segment']) for s in ('palm', 'dors') if a[s + '_segment']}
    B = {(s, b[s + '_segment']) for s in ('palm', 'dors') if b[s + '_segment']}
    out['same_segment'] = int(len(A & B) > 0)
    out['jaccard'] = len(A & B) / len(A | B)
    da, db = set(a['digits'].split('|')), set(b['digits'].split('|'))
    out['same_digit'] = int(len(da & db) > 0)
    for s in ('palm', 'dors'):
        if a[s + '_segment'] and b[s + '_segment']:
            p = np.array([a[s + '_centroid_x_mm'], a[s + '_centroid_y_mm']], float)
            q = np.array([b[s + '_centroid_x_mm'], b[s + '_centroid_y_mm']], float)
            out[s + '_centroid_dist_mm'] = float(np.linalg.norm(p - q))
        else:
            out[s + '_centroid_dist_mm'] = np.nan
    return out


def cort(a, b):
    return 0.4 * np.hypot(a['grid_row'] - b['grid_row'], a['grid_col'] - b['grid_col'])


arrays = sorted({(e['participant'], e['array']) for e in elec})
pairs = []
for pa in arrays:
    es = [e for e in elec if (e['participant'], e['array']) == pa and e['has_PF']]
    for a, b in itertools.combinations(es, 2):
        m = pair_measures(a, b)
        pairs.append(dict(participant=pa[0], array=pa[1], ch_a=a['electrode_channel'], ch_b=b['electrode_channel'],
                          cortical_mm=round(cort(a, b), 3), **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}))
with open(os.path.join(OUT, 'pf_pairs_greenspon2025.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(pairs[0])); w.writeheader(); w.writerows(pairs)

BINS = [0, 0.45, 0.6, 0.9, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0, 3.5, 4.7]


def binned(ps, key):
    x = np.array([p['cortical_mm'] for p in ps]); y = np.array([p[key] for p in ps], float)
    ok = ~np.isnan(y); x, y = x[ok], y[ok]
    rows = []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (x >= lo) & (x < hi)
        if m.sum():
            rows.append(dict(bin=f'[{lo},{hi})', n=int(m.sum()), mean=round(float(y[m].mean()), 3),
                             median=round(float(np.median(y[m])), 3)))
    return rows


def spearman_perm(es, key, surf=None):
    """Spearman(cortical distance, measure) over within-array pairs + label-shuffle permutation p (one-sided, expects
    rho > 0 for distances and rho < 0 for overlap measures)."""
    n_e = len(es)
    iu = np.triu_indices(n_e, 1)
    pos = np.array([(e['grid_row'], e['grid_col']) for e in es], float)
    cx = 0.4 * np.hypot(pos[iu[0], 0] - pos[iu[1], 0], pos[iu[0], 1] - pos[iu[1], 1])
    M = np.full((n_e, n_e), np.nan)
    for i in range(n_e):
        for j in range(n_e):
            if i != j:
                M[i, j] = pair_measures(es[i], es[j])[key]

    def stat(order):
        order = np.asarray(order)
        y = M[order[iu[0]], order[iu[1]]]
        ok = ~np.isnan(y)
        if ok.sum() < 5 or np.nanstd(y) == 0:
            return np.nan, int(ok.sum())
        return stats.spearmanr(cx[ok], y[ok])[0], int(ok.sum())
    r0, n = stat(list(range(len(es))))
    if np.isnan(r0):
        return dict(rho=None, n_pairs=n, p_perm=None)
    null = []
    for _ in range(NPERM):
        null.append(stat(list(rng.permutation(len(es))))[0])
    null = np.array(null); null = null[~np.isnan(null)]
    p = (np.sum(null >= r0) + 1) / (len(null) + 1) if 'dist' in key else (np.sum(null <= r0) + 1) / (len(null) + 1)
    return dict(rho=round(float(r0), 3), n_pairs=n, p_perm=round(float(p), 4), null_mean=round(float(null.mean()), 3),
                null_sd=round(float(null.std()), 3))


summary = dict(greenspon2025={}, armentasalas2018={})
G = summary['greenspon2025']
G['n_electrodes_wired'] = len(elec)
G['n_electrodes_with_PF'] = sum(e['has_PF'] for e in elec)
G['n_within_array_pairs'] = len(pairs)
G['per_array'] = {}
for pa in arrays:
    es = [e for e in elec if (e['participant'], e['array']) == pa and e['has_PF']]
    ps = [p for p in pairs if (p['participant'], p['array']) == pa]
    near = [p for p in ps if p['cortical_mm'] <= 0.57]
    G['per_array'][f'{pa[0]}_{pa[1]}'] = dict(
        n_PF=len(es), n_pairs=len(ps),
        P_same_segment_all=round(np.mean([p['same_segment'] for p in ps]), 3),
        P_same_segment_near=round(np.mean([p['same_segment'] for p in near]), 3) if near else None,
        n_near=len(near),
        P_same_digit_all=round(np.mean([p['same_digit'] for p in ps]), 3),
        spearman_palm_dist=spearman_perm(es, 'palm_centroid_dist_mm'),
        spearman_dors_dist=spearman_perm(es, 'dors_centroid_dist_mm'),
        spearman_jaccard=spearman_perm(es, 'jaccard'))
for key in ['palm_centroid_dist_mm', 'dors_centroid_dist_mm', 'same_segment', 'jaccard', 'same_digit']:
    G['pooled_binned_' + key] = binned(pairs, key)
# analogue of Fig 3e: same-digit pairs only, palm centroid distance, authors' 7 bins on [0,4] mm
fd = [p for p in pairs if p['same_digit'] and not np.isnan(p['palm_centroid_dist_mm'])]
x = np.array([p['cortical_mm'] for p in fd]); y = np.array([p['palm_centroid_dist_mm'] for p in fd])
edges = np.linspace(0, 4, 8)
G['fig3e_analogue_same_digit_palm'] = [dict(bin_centre=round((lo + hi) / 2, 2), n=int(((x >= lo) & (x < hi)).sum()),
                                            mean_mm=round(float(y[(x >= lo) & (x < hi)].mean()), 2) if ((x >= lo) & (x < hi)).any() else None)
                                       for lo, hi in zip(edges[:-1], edges[1:])]
G['fig3e_analogue_pearson_r'] = round(float(stats.pearsonr(x, y)[0]), 3) if len(x) > 3 else None
G['fig3e_analogue_n_pairs'] = int(len(x))
# stricter analogue: both palm segments on the SAME FINGER (D1..D5), palm-body segments excluded
ff = [p for p in pairs if not np.isnan(p['palm_centroid_dist_mm'])]
lab = {(e['participant'], e['array'], e['electrode_channel']): e['palm_segment'] for e in elec}
ff = [p for p in ff if re.match(r'D\d', lab[(p['participant'], p['array'], p['ch_a'])]) and
      lab[(p['participant'], p['array'], p['ch_a'])][:2] == lab[(p['participant'], p['array'], p['ch_b'])][:2]]
x = np.array([p['cortical_mm'] for p in ff]); y = np.array([p['palm_centroid_dist_mm'] for p in ff])
G['fig3e_analogue_same_finger_palm'] = [dict(bin_centre=round((lo + hi) / 2, 2), n=int(((x >= lo) & (x < hi)).sum()),
                                             mean_mm=round(float(y[(x >= lo) & (x < hi)].mean()), 2) if ((x >= lo) & (x < hi)).any() else None)
                                        for lo, hi in zip(edges[:-1], edges[1:])]
G['fig3e_analogue_same_finger_pearson_r'] = round(float(stats.pearsonr(x, y)[0]), 3) if len(x) > 3 else None
G['fig3e_analogue_same_finger_n_pairs'] = int(len(x))
# baseline (all within-array PF pairs) P(same segment), for the 'independence distance'
G['P_same_segment_all_pairs'] = round(float(np.mean([p['same_segment'] for p in pairs])), 3)

# ---------------- categorical-set sources (Armenta Salas 2018; Fifer 2022) ----------------
def categorical(csvname, keep, setcol, rowcol, colcol, arrays_, outname, pitch_note):
    R = [r for r in csv.DictReader(open(os.path.join(OUT, csvname))) if r['status'] == keep and r[setcol]]
    for r in R:
        r['set'] = set(r[setcol].split('|')); r['grid_row'] = int(r[rowcol]); r['grid_col'] = int(r[colcol])
    res = dict(n_electrodes=len(R), pitch=pitch_note)
    allp = []
    for arr in arrays_:
        es = [r for r in R if r['array'] == arr]
        if len(es) < 3:
            continue
        idx = list(itertools.combinations(range(len(es)), 2))
        cx = np.array([cort(es[i], es[j]) for i, j in idx])

        def jac(order):
            return np.array([len(es[order[i]]['set'] & es[order[j]]['set']) / len(es[order[i]]['set'] | es[order[j]]['set']) for i, j in idx])

        def same(order):
            return np.array([float(len(es[order[i]]['set'] & es[order[j]]['set']) > 0) for i, j in idx])
        j0 = jac(range(len(es))); s0 = same(range(len(es)))
        r0 = stats.spearmanr(cx, j0)[0]
        null = np.array([stats.spearmanr(cx, jac(rng.permutation(len(es))))[0] for _ in range(NPERM)])
        near = cx <= 0.57
        res[arr] = dict(n=len(es), n_pairs=len(idx), spearman_jaccard_vs_dist=round(float(r0), 3),
                        p_perm_one_sided=round(float((np.sum(null <= r0) + 1) / (NPERM + 1)), 4),
                        mean_jaccard_near=round(float(j0[near].mean()), 3) if near.any() else None, n_near=int(near.sum()),
                        mean_jaccard_all=round(float(j0.mean()), 3),
                        P_same_near=round(float(s0[near].mean()), 3) if near.any() else None,
                        P_same_all=round(float(s0.mean()), 3))
        for (i, j_), c, jj, ss in zip(idx, cx, j0, s0):
            allp.append(dict(array=arr, a=f"{es[i]['grid_row']},{es[i]['grid_col']}", b=f"{es[j_]['grid_row']},{es[j_]['grid_col']}",
                             cortical_mm=round(float(c), 3), jaccard=round(float(jj), 3), same_class_any=int(ss)))
    with open(os.path.join(OUT, outname), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(allp[0])); w.writeheader(); w.writerows(allp)
    res['n_pairs'] = len(allp)
    res['pooled_binned_jaccard'] = binned(allp, 'jaccard')
    res['pooled_binned_same_class'] = binned(allp, 'same_class_any')
    return res


summary['armentasalas2018'] = categorical('pf_per_electrode_armentasalas2018.csv', 'responsive', 'regions', 'grid_row', 'grid_col',
                                          ('medial', 'lateral'), 'pf_pairs_armentasalas2018.csv',
                                          '400 um ASSUMED (not stated in the paper)')
summary['fifer2022'] = categorical('pf_per_electrode_fifer2022.csv', 'PF', 'hue_classes', 'grid_long', 'grid_short',
                                   ('left_array_A', 'left_array_B', 'right_array'), 'pf_pairs_fifer2022.csv',
                                   '400 um (stated, Fifer 2022 Methods)')

json.dump(summary, open(os.path.join(OUT, 'pf_pairwise_summary.json'), 'w'), indent=1, default=float)
print(json.dumps(summary, indent=1, default=float))
