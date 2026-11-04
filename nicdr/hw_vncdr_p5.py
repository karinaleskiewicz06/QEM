"""Two-axis vnCDR on the recorded P5 night -- offline, no QPU, EQUAL shot budget.

P5 measured, for the same 8 evaluation points of the star model, the target and the same
20 near-Clifford training circuits at several noise levels: the base circuit, the base with
k CZ.CZ pairs (more CZ, longer) and the base with matched idle (longer only). That is
exactly the data vnCDR needs, with the noise scaled along two separate axes.

Equal budget: plain CDR uses the 6 copies of every circuit at the base level. A vnCDR
variant with L levels uses 6/L copies of each circuit at each level (3 per level for 2
levels, 2 per level for 3 levels), so the total number of shots is identical. Which
copies are used is randomised over many draws; the deterministic first-copies draw is
reported too.

Pre-specified (before running): the PRIMARY comparison is 2-axis vnCDR with k = 36
(+12 CZ pairs; star, star_cz36 and star_idle36 all ran on the same calibration set), with an
intercept, against plain CDR. Everything else -- 1-axis variants, k = 24 / 52 (cz24 and
cz52 ran partly or fully on a new calibration set), no-intercept fits -- is secondary.

    python -m nicdr.hw_vncdr_p5
"""
from __future__ import annotations

import csv
import itertools

import numpy as np

from nicdr.common import OUT_HW, cdr_circuits, fmt_paired, multi_reg, ols_line, paired

M = 6
N_DRAWS = 200


def level_sets(k):
    return {"CDR": ["star"],
            f"vn_t{k}": ["star", f"star_idle{k}"],
            f"vn_cz{k}": ["star", f"star_cz{k}"],
            f"vn_2ax{k}": ["star", f"star_cz{k}", f"star_idle{k}"]}


def check_alignment(groups):
    """Training circuit i of a point must be the same circuit (same ideal) at every level."""
    bad = 0
    for ei in sorted({e for (_, e) in groups}):
        base = groups[("star", ei)]["train"]
        for (rung, e2), g in groups.items():
            if e2 != ei or rung.startswith("star_L"):
                continue
            for a, b in zip(base, g["train"]):
                if a.train_index != b.train_index or abs(a.ideal - b.ideal) > 1e-9:
                    bad += 1
            if abs(g["target"].ideal - groups[("star", ei)]["target"].ideal) > 1e-9:
                bad += 1
    return bad


def estimate(groups, ei, levels, reps_per_level, intercept=True):
    """vnCDR (or CDR for one level) estimate for point ei with given copies per level."""
    X_tr, X_te = [], []
    for lvl, reps in zip(levels, reps_per_level):
        g = groups[(lvl, ei)]
        X_tr.append([c.mean(reps) for c in g["train"]])
        X_te.append(g["target"].mean(reps))
    y = np.array([c.ideal for c in groups[(levels[0], ei)]["train"]])
    X_tr = np.array(X_tr).T
    X_te = np.array(X_te)[None, :]
    if len(levels) == 1:
        a, b = ols_line(X_tr[:, 0], y)
        return float(a * X_te[0, 0] + b)
    pred, _ = multi_reg(X_tr, y, X_te, intercept=intercept)
    return float(pred[0])


def draw_reps(L, rng, first=False):
    per = M // L
    if first:
        return [list(range(per))] * L if L > 1 else [list(range(M))]
    if L == 1:
        return [list(range(M))]
    # disjoint-in-spirit random subsets per level (levels are different circuits anyway)
    return [sorted(rng.choice(M, per, replace=False).tolist()) for _ in range(L)]


def main():
    OUT_HW.mkdir(parents=True, exist_ok=True)
    log = []

    def say(s=""):
        print(s)
        log.append(s)

    groups = cdr_circuits("w01P5", "off_copies")
    bad = check_alignment(groups)
    say(f"training-circuit alignment across levels: {'OK' if bad == 0 else f'{bad} MISMATCHES'}")
    points = sorted({e for (r, e) in groups if r == "star"})
    ideal = {ei: groups[("star", ei)]["target"].ideal for ei in points}
    shots = {r: groups[(r, points[0])]["target"].shots for r, _ in groups if _ == points[0]}
    say(f"points {points}; copies per circuit {M}; shots per target copy "
        f"{shots['star'] // M}")

    rng = np.random.default_rng(12345)
    rows = []
    results = {}
    for k in (36, 24, 52):
        for name, levels in level_sets(k).items():
            if name == "CDR" and k != 36:
                continue
            for intercept in (True, False):
                if name == "CDR" and not intercept:
                    continue
                key = name + ("" if intercept else "_noint")
                err_first, err_draws = [], []
                for ei in points:
                    est = estimate(groups, ei, levels, draw_reps(len(levels), rng, first=True), intercept)
                    err_first.append(abs(est - ideal[ei]))
                    e = [abs(estimate(groups, ei, levels, draw_reps(len(levels), rng), intercept) - ideal[ei])
                         for _ in range(N_DRAWS if len(levels) > 1 else 1)]
                    err_draws.append(float(np.mean(e)))
                results[key] = (np.array(err_first), np.array(err_draws))
                for ei, ef, ed in zip(points, err_first, err_draws):
                    rows.append({"method": key, "levels": "+".join(levels), "eval_index": ei,
                                 "err_first_copies": ef, "err_mean_over_draws": ed})

    base_f, base_d = results["CDR"]
    say(f"\nplain CDR (6 copies at base): mean error {base_d.mean():.4f}")
    say("\n--- PRIMARY: 2-axis vnCDR k=36, intercept, vs CDR at equal budget ---")
    say(fmt_paired("vn_2ax36 vs CDR (mean over draws)", paired(results["vn_2ax36"][1], base_d)))
    say(fmt_paired("vn_2ax36 vs CDR (first copies)", paired(results["vn_2ax36"][0], base_f)))
    say("\n--- secondary ---")
    for key in results:
        if key in ("CDR", "vn_2ax36"):
            continue
        say(fmt_paired(f"{key} vs CDR (draws)", paired(results[key][1], base_d)))

    # how much does noise scaling help with MORE shots? use all 6 copies at every level
    say("\n--- not budget-matched (all 6 copies at every level; L x the shots of CDR) ---")
    for k in (36, 24, 52):
        for name, levels in level_sets(k).items():
            if name == "CDR":
                continue
            err = [abs(estimate(groups, ei, levels, [list(range(M))] * len(levels)) - ideal[ei])
                   for ei in points]
            say(fmt_paired(f"{name} x{len(levels)} budget vs CDR", paired(err, base_d)))

    with (OUT_HW / "vncdr_p5_points.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT_HW / "hw_vncdr_p5.log").write_text("\n".join(log) + "\n")
    print(f"\nwrote {OUT_HW}/vncdr_p5_points.csv, hw_vncdr_p5.log")


if __name__ == "__main__":
    main()
