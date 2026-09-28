"""DIGITISE per-electrode receptive-field (projected-field) body region from Armenta Salas et al. 2018 eLife 7:e32904,
Figure 2B left panels ("Receptive Fields"), PMID 29633714, PMC5896877, DOI 10.7554/eLife.32904 (CC BY 4.0).
Image: https://cdn.elifesciences.org/articles/32904/elife-32904-fig2-v1.jpg (2004 x 1246 px).
Legend (quote): "(A) Receptive field location on anterior (lighter shades) and posterior (darker shades) planes of the right
upper arm (green), forearm (pink), and hand (cyan). ... (B) Schematic of the two electrode arrays implanted over S1 (Figure 1).
Left side panels display the reported receptive fields at each electrode location ... Light gray boxes show electrodes with
no reported sensation, while dark gray boxes represent reference channels which are not used in recording."
Arrays: "Two 7 x 7 SIROF ... microelectrode arrays (with 48 physically-connected channels each) were implanted in S1."
Electrode pitch is NOT stated in the paper; 400 um (Blackrock standard) is ASSUMED where mm are reported.
Method: grid borders located from the dark outline (medial array x 746-1193, y 197-643; lateral array y 759-1206 px);
each cell is sampled on a 6 x 6 lattice inside its central 70 %; each sample is assigned to the nearest reference colour;
a region is 'present' on an electrode if it covers >= 15 % of the samples (split cells = several regions reported
across amplitudes/sessions).
"""
import os, sys, json, csv, urllib.request
import numpy as np
from PIL import Image

SCR = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = os.path.dirname(os.path.abspath(__file__))
fn = os.path.join(SCR, 'arm_fig2_v1.jpg')
if not os.path.exists(fn):
    req = urllib.request.Request('https://cdn.elifesciences.org/articles/32904/elife-32904-fig2-v1.jpg',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    open(fn, 'wb').write(urllib.request.urlopen(req, timeout=120).read())
im = np.asarray(Image.open(fn).convert('RGB')).astype(float)

PAL = {  # measured from the figure (median RGB of clean cells)
    'UA_ant': (0, 255, 0), 'UA_post': (0, 128, 0), 'FA_ant': (255, 120, 212), 'FA_post': (191, 41, 140),
    'hand': (0, 204, 255), 'none': (214, 214, 212), 'reference': (64, 64, 64), 'outline': (0, 0, 0),
    'star_yellow': (250, 250, 11), 'star_magenta': (230, 0, 230)}
# region centres on a coarse arm axis (0 = shoulder/upper arm, 1 = forearm, 2 = hand) and plane (+1 ant, -1 post)
AXIS = {'UA_ant': (0, 1), 'UA_post': (0, -1), 'FA_ant': (1, 1), 'FA_post': (1, -1), 'hand': (2, 1)}
names = list(PAL); cols = np.array([PAL[k] for k in names], float)

grids = {'medial': (746, 1193, 197, 643), 'lateral': (746, 1193, 759, 1206)}
rows_out = []
for arr, (x0, x1, y0, y1) in grids.items():
    cw, ch = (x1 - x0) / 7, (y1 - y0) / 7
    for r in range(7):
        for c in range(7):
            cnt = {}
            for a in np.linspace(0.15, 0.85, 6):
                for b in np.linspace(0.15, 0.85, 6):
                    x = int(x0 + (c + a) * cw); y = int(y0 + (r + b) * ch)
                    rgb = np.median(im[y - 1:y + 2, x - 1:x + 2].reshape(-1, 3), 0)
                    k = names[int(np.argmin(((cols - rgb) ** 2).sum(1)))]
                    cnt[k] = cnt.get(k, 0) + 1
            n = sum(v for k, v in cnt.items() if k != 'outline')
            frac = {k: v / max(n, 1) for k, v in cnt.items() if k != 'outline'}
            regions = sorted([k for k, f in frac.items() if f >= 0.15 and k in AXIS], key=lambda k: -frac[k])
            status = ('reference' if frac.get('reference', 0) + frac.get('star_yellow', 0) + frac.get('star_magenta', 0) > 0.3
                      else ('responsive' if regions else 'no_sensation'))
            rows_out.append(dict(participant='FG', array=arr, grid_row=r, grid_col=c, x_mm_assumed=round(c * 0.4, 2),
                                 y_mm_assumed=round(r * 0.4, 2), status=status, regions='|'.join(regions),
                                 fractions=';'.join(f'{k}:{v:.2f}' for k, v in sorted(frac.items(), key=lambda t: -t[1]))))
path = os.path.join(OUT, 'pf_per_electrode_armentasalas2018.csv')
with open(path, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0]) + ['source', 'DIGITISED'])
    w.writeheader()
    for r in rows_out:
        r['source'] = 'Armenta Salas 2018 eLife Fig 2B (PMC5896877)'; r['DIGITISED'] = 'yes'
        w.writerow(r)
resp = [r for r in rows_out if r['status'] == 'responsive']
print('responsive electrodes:', len(resp), '(paper: 46/96 prompted at least one response)')
for a in grids:
    print(a, 'responsive', sum(1 for r in resp if r['array'] == a),
          'reference', sum(1 for r in rows_out if r['array'] == a and r['status'] == 'reference'))
print('multi-region electrodes:', sum(1 for r in resp if '|' in r['regions']))
