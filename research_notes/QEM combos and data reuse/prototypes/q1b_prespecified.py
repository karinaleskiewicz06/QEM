"""Q1b: prespecified equal-budget allocation (T=8192 target shots, N=20 training circuits x 819 shots),
paired against ZNE and against REM+ZNE (readout-corrected Richardson). Also a cost curve for the
untwirled arm: CDR expected error vs budget multiple, with ZNE/REM+ZNE fixed at 1x."""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa
from q1_equal_budget import cdr_draw
from q2_readout import readout_params, corr

B = 600


def main():
    recs = load("w01A")
    g = cdr_groups(recs)
    z = zne_groups(recs)
    e01, e10 = readout_params()
    for d in g.values():
        d["h_target"] = hw_hist(d["target"])
        d["h_train"] = {i: hw_hist(v) for i, v in d["train"].items()}
    rng = np.random.default_rng(7)
    lines = []
    for rung in ("star", "circular"):
        ideal = np.array([z[(rung, e)][("genuine", 1)].meta["ideal"] for e in EVAL])
        zne = np.abs(np.array([RICH[(1, 3, 5)] @ [z[(rung, e)][("genuine", s)].expval for s in (1, 3, 5)] for e in EVAL]) - ideal)
        rz = np.abs(np.array([RICH[(1, 3, 5)] @ [corr(z[(rung, e)][("genuine", s)], e01, e10) for s in (1, 3, 5)] for e in EVAL]) - ideal)
        lines.append(f"\n## {rung}: ZNE {zne.mean():.4f}, REM+ZNE {rz.mean():.4f} (both 24,576 shots)")
        for arm in ("off_copies", "twirl_native", "spread"):
            keys = [(rung, arm, "near_target", e) for e in EVAL]
            c = np.array([np.mean([cdr_draw(g[k], 8192, 20, 819, rng) for _ in range(B)]) for k in keys])
            lines.append(f"  CDR@24k {arm} (8192 + 20x819): {c.mean():.4f}")
            lines.append("    vs ZNE:     " + paired_report(c, zne, "CDR", "ZNE"))
            lines.append("    vs REM+ZNE: " + paired_report(c, rz, "CDR", "REM+ZNE"))
        # cost curve, off_copies & twirl_native: shots per training circuit s scaled, T scaled
        for arm in ("off_copies", "twirl_native"):
            keys = [(rung, arm, "near_target", e) for e in EVAL]
            pts = []
            for mult in (0.25, 0.5, 1, 2, 4, 8, 16, 42):
                tot = int(24576 * mult)
                T = min(49152, max(256, tot // 3))
                s = max(16, (tot - T) // 20)
                s = min(s, 49152)
                c = np.array([np.mean([cdr_draw(g[k], T, 20, s, rng) for _ in range(200)]) for k in keys])
                pts.append(f"{mult}x:{c.mean():.4f}")
            lines.append(f"  cost curve {arm} (budget multiple of 24,576: E|err|): " + "  ".join(pts))
    txt = "\n".join(lines)
    (OUT / "q1b_prespecified.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
