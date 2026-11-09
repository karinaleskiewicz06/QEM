"""Q2: tensored (per-qubit) readout correction from the SSRO numbers in the calibration dump.

Per qubit, measured <Z>_m = (1 - e01 - e10) <Z> + (e10 - e01)  =>  <Z> = (<Z>_m - (e10 - e01)) / (1 - e01 - e10).
For a mean-Z observable this is identical to applying the tensor-product inverse confusion
matrix to the counts (mean-Z depends only on single-qubit marginals). Fields read:
raw.readout.QBk.error_0_to_1 / error_1_to_0 only (no URL / token fields touched).
Wire -> physical qubit: PHYS in common.py (meta.qubit_order_logical_to_physical).
Sensitivity: (i) qubit-averaged correction (mapping-free), (ii) a random wire permutation.
"""
from __future__ import annotations

import itertools
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa


def readout_params(fname="odra_raw_w01A_start.json", phys=PHYS):
    ro = json.load(open(REPO / "calibrations" / fname))["raw"]["readout"]
    e01 = np.array([ro[p]["error_0_to_1"] for p in phys])
    e10 = np.array([ro[p]["error_1_to_0"] for p in phys])
    return e01, e10


def corr(rec_or_recs, e01, e10):
    recs = rec_or_recs if isinstance(rec_or_recs, list) else [rec_or_recs]
    zq = np.mean([r.zq for r in recs], axis=0)
    return float(COEFFS @ ((zq - (e10 - e01)) / (1 - e01 - e10)))


def main():
    recs = load("w01A")
    z = zne_groups(recs)
    g = cdr_groups(recs)
    e01, e10 = readout_params()
    lines = [f"e01={e01}, e10={e10}; mean-Z offset d=mean(e10-e01)={np.mean(e10-e01):.4f}, "
             f"gain g=1-e01-e10 mean {np.mean(1-e01-e10):.4f}"]
    # check end-of-window dump is identical
    e01b, e10b = readout_params("odra_raw_w01A_end.json")
    lines.append(f"end-of-window SSRO identical to start: {np.allclose(e01, e01b) and np.allclose(e10, e10b)}")
    variants = {"per-qubit (PHYS map)": (e01, e10),
                "qubit-averaged": (np.full(N, e01.mean()), np.full(N, e10.mean()))}
    rng = np.random.default_rng(0)
    perm = rng.permutation(N)
    variants["random wire permutation"] = (e01[perm], e10[perm])
    for rung in ("star", "circular"):
        lines.append(f"\n## {rung}")
        ideal = np.array([z[(rung, e)][("genuine", 1)].meta["ideal"] for e in EVAL])
        E = np.array([[z[(rung, e)][("genuine", s)].expval for s in (1, 3, 5)] for e in EVAL])
        zne = E @ RICH[(1, 3, 5)]
        raw1 = E[:, 0]
        offk = [(rung, "off_copies", "near_target", e) for e in EVAL]
        raw6 = np.array([np.mean([r.expval for r in g[k]["target"]]) for k in offk])
        lines.append(f"uncorrected: raw(λ1) {np.abs(raw1-ideal).mean():.4f}, raw(6 copies) {np.abs(raw6-ideal).mean():.4f}, ZNE {np.abs(zne-ideal).mean():.4f}")
        lines.append("  ZNE vs raw(λ1) uncorrected: " + paired_report(np.abs(zne - ideal), np.abs(raw1 - ideal), "ZNE", "raw"))
        for name, (a01, a10) in variants.items():
            Ec = np.array([[corr(z[(rung, e)][("genuine", s)], a01, a10) for s in (1, 3, 5)] for e in EVAL])
            znec = Ec @ RICH[(1, 3, 5)]
            raw1c = Ec[:, 0]
            raw6c = np.array([corr(g[k]["target"], a01, a10) for k in offk])
            # CDR with readout-corrected training and target (off_copies)
            cdrc, cdru = [], []
            for k in offk:
                d = g[k]
                ks = sorted(d["train"])
                xs = [corr(d["train"][i], a01, a10) for i in ks]
                xu = [np.mean([r.expval for r in d["train"][i]]) for i in ks]
                ys = [d["train_ideal"][i] for i in ks]
                a, b, _ = ols(xs, ys)
                cdrc.append(abs(a * corr(d["target"], a01, a10) + b - d["ideal"]))
                a, b, _ = ols(xu, ys)
                cdru.append(abs(a * np.mean([r.expval for r in d["target"]]) + b - d["ideal"]))
            lines.append(f" [{name}] REM raw(λ1) {np.abs(raw1c-ideal).mean():.4f}; REM raw(6 copies) {np.abs(raw6c-ideal).mean():.4f}; "
                         f"REM+ZNE {np.abs(znec-ideal).mean():.4f}; CDR(off) uncorr {np.mean(cdru):.4f} -> REM {np.mean(cdrc):.4f}")
            lines.append("   REM+ZNE vs REM raw(λ1): " + paired_report(np.abs(znec - ideal), np.abs(raw1c - ideal), "REM+ZNE", "REMraw"))
            lines.append("   REM+ZNE vs raw(λ1) unc.: " + paired_report(np.abs(znec - ideal), np.abs(raw1 - ideal), "REM+ZNE", "raw"))
            lines.append("   REM+ZNE vs ZNE unc.:     " + paired_report(np.abs(znec - ideal), np.abs(zne - ideal), "REM+ZNE", "ZNE"))
            lines.append("   REM raw vs raw (λ1):     " + paired_report(np.abs(raw1c - ideal), np.abs(raw1 - ideal), "REMraw", "raw"))
        # signed residuals: is the error mostly a +offset (T1/readout pull to +1)?
        lines.append(f"  signed (raw λ1 - ideal): {np.round(raw1-ideal,4)}")
        lines.append(f"  signed (ZNE - ideal):    {np.round(zne-ideal,4)}")
        lines.append(f"  ideal:                   {np.round(ideal,4)}")
    txt = "\n".join(lines)
    (OUT / "q2_readout.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
