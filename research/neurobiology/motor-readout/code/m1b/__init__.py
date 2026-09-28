r"""m1b: M1b confirmatory re-registration (prereg\M1b_confirmatory.md, SHA c30873de...d9a1).

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. Computational decoding of recorded activity only.
Reuses m1lib, nfharness and edf_reader by import only (unchanged). Deviations: code\DEVIATIONS_M1b.md.
"""
import os
import sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CODE not in sys.path:
    sys.path.insert(0, CODE)

from m1lib import NB_CODE, RAW, ROOT, SEED  # noqa: E402,F401  (puts nfharness on sys.path)

PREREG = os.path.join(ROOT, "prereg", "M1b_confirmatory.md")
PREREG_SHA = "c30873dec5c65929462dfc9c06451f6e68c1e997207757b16be113484710d9a1"
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
MANIFEST = os.path.join(ROOT, "data", "manifests", "motor_manifest.csv")
DEVIATIONS = os.path.join(CODE, "DEVIATIONS_M1b.md")
POWER_JSON = os.path.join(RES, "POWER_M1b.json")
RUO = ("RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or "
       "treatment decisions may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical "
       "use requires regulatory clearance and clinical validation (IRB/ethics approval).")

# ---- §1.5 input locks (text copied from the prereg; hashes checked by assert_input_lock)
FRESH_LOCK = (
    "000139|0.220113.0408|7ef450a8-8684-42e2-8598-cd38ca2b2e50\n"
    "001201|0.251023.2336|A1:fc9220d7-f3ad-40eb-9cc0-9e2ffd5bd016,f6533dca-9bf3-4656-9718-dce7f1ed83ee,"
    "7cbe4ac7-237d-4bab-96f7-f0cf22a57ee9,3a7198bd-4db8-401e-bd3b-fb3d051e24cc,1910e1d3-ccd7-465e-8456-812358683ed4;"
    "A2:09987453-cf36-4c89-b4a5-29912abb8248,07331f03-5c37-4bd0-bd8f-bb2748c12e41,430ff4b8-1058-4d88-9180-c0aea6ba0c34,"
    "2c5414ff-1263-48d3-b4cc-e37a2dd72c41,84ce09b4-6859-49f0-b262-9802a96c6000,eb507345-bb97-42fc-bc96-4b19bfebb757,"
    "890cd908-7f96-4eae-ac60-fac59aa52d06,19b99ead-c2e8-4a06-b3e4-d2a659634089\n"
    "eegmmidb|1.0.0|S001-S020|R04,R08,R12")
FRESH_LOCK_SHA = "e6856172aea86e5a0cf6992112824ae45d15803842d2969489d3796d9a112792"
POWER_LOCK = ("000138|0.220113.0407|e67b57b2-e9ad-4d95-b9e3-1262997360dc\n"
              "000140|0.220113.0408|7821971e-c6a4-4568-8773-1bfa205c13f8\n"
              "001201|0.251023.2336|c002a9a1-664d-4a69-af02-ba810046c4fb,88039197-6170-4d06-ba3e-f58b68c6eb7f")
POWER_LOCK_SHA = "01cf828b85ba1ec252dd50a89bd53204b02c8287724f436afec6ddf7d33e5ce9"

# ---- §1.1 / §1.2 fresh assets: (anchor, target L, lag d, date, bytes, asset_id, dandi sha256)
MEDIUM = dict(dandiset="000139", version="0.220113.0408", asset_id="7ef450a8-8684-42e2-8598-cd38ca2b2e50",
              rel="000139/sub-Jenkins_ses-medium_desc-train_behavior+ecephys.nwb", bytes=76604764,
              sha256="3852799f85f662f1cacadb0d758ba8fa0dc6cca318f46c9b131978adf1baffb6")
LINK = [
    ("A1", 0, 0, "20200708", 38287314, "fc9220d7-f3ad-40eb-9cc0-9e2ffd5bd016", "77e36c28afcce55cbd8f2c8761a9bb17556fc008041c11b7b8273613314d2839"),
    ("A1", 3, 6, "20200714", 40729090, "f6533dca-9bf3-4656-9718-dce7f1ed83ee", "62ae4e1dec6495243c9e1982220b77acf07cdbb9ad7805f0fc0e6a7694eb6a93"),
    ("A1", 120, 120, "20201105", 36474162, "7cbe4ac7-237d-4bab-96f7-f0cf22a57ee9", "8cd8e3688952fb3d576edffcaf6d7953f7e84ef9f1eb2271fcf0141e2e6d715a"),
    ("A1", 240, 244, "20210309", 39664146, "3a7198bd-4db8-401e-bd3b-fb3d051e24cc", "bf4802fa9e39830d9716928664593dd57fcfd84c02dc5ef12779015950913837"),
    ("A1", 365, 366, "20210709", 35226610, "1910e1d3-ccd7-465e-8456-812358683ed4", "546f074266ddb8870aa2cf80972987ccc2f5d23637244d3d2dd5328013acf589"),
    ("A2", 0, 0, "20210706", 36703634, "09987453-cf36-4c89-b4a5-29912abb8248", "859b94786b0481fdf3d7ad7674fdd8b51deea3c626da07fe65a5610d737142c1"),
    ("A2", 7, 7, "20210713", 37096322, "07331f03-5c37-4bd0-bd8f-bb2748c12e41", "e149b2ce3b52793207a40faa676f6bbd3246f159ee3f12da0086c1e82e909fba"),
    ("A2", 14, 14, "20210720", 36789282, "430ff4b8-1058-4d88-9180-c0aea6ba0c34", "289003c68af0b75406aa172fcfd4ed548c973c508466438c21696f56156a026b"),
    ("A2", 30, 30, "20210805", 38054610, "2c5414ff-1263-48d3-b4cc-e37a2dd72c41", "bad4ae1fb0f1a082980ece42549178a1d56ab584727a9f2ca9134576c64e78f1"),
    ("A2", 60, 62, "20210906", 38983810, "84ce09b4-6859-49f0-b262-9802a96c6000", "685557f907abd0df18ed0310ed6f8ba45374a28e2496353d074ed384ce7a4ecc"),
    ("A2", 120, 129, "20211112", 41619506, "eb507345-bb97-42fc-bc96-4b19bfebb757", "39b64443c9ebb1b86e253c0eadd3aa974f65af5f440fbde3f2e437625beaad8c"),
    ("A2", 240, 244, "20220307", 39088850, "890cd908-7f96-4eae-ac60-fac59aa52d06", "4cd2bbb8cf1d1ebb6de1ebc667ccc8458c22da7377e167b668171097a65f39bb"),
    ("A2", 365, 377, "20220718", 35818066, "19b99ead-c2e8-4a06-b3e4-d2a659634089", "aed9f3433689af14224e46ff3a586f315dfcffc7fb21c52204b7a58db2d4f712"),
]
LINK_TOTAL_BYTES = 494535402
BUDGET_TOTAL_BYTES = 1301333592
BUDGET_CAP_BYTES = 1.5e9
PL2_SESSION = {"A1": "20201105", "A2": "20210805"}      # first lag >= 30 d session per anchor (§6.2 PL-2')
H4B_SESSIONS = ["20200714", "20210713", "20210720"]    # lag 3-14 d
H4A_SESSIONS = ["20201105", "20210309", "20210709", "20210805", "20210906", "20211112", "20220307", "20220718"]


def link_rel(date):
    return "001201/sub-Monkey-N_ses-%s_ecephys.nwb" % date


def raw_path(rel):
    return os.path.join(RAW, rel.replace("/", os.sep))


# ---- OLD files (power check)
OLD_LARGE = "000138/sub-Jenkins_ses-large_desc-train_behavior+ecephys.nwb"
OLD_SMALL = "000140/sub-Jenkins_ses-small_desc-train_behavior+ecephys.nwb"
OLD_LINK0 = link_rel("20200127")
OLD_LINK1 = link_rel("20200626")

# ---- RNG streams (§10 step 9)
K_BOOT, K_SHUF, K_NULL, K_SIGNFLIP, K_D3PERM, K_PLANT, K_SYN, K_NL1 = 1, 2, 3, 4, 5, 6, 7, 8
GRU_SEEDS3 = (20261001, 20261002, 20261003)
GRU_SEED1 = (20261001,)
B_BOOT = 2000
N_NULL = 200
