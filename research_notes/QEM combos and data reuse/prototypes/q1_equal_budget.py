"""Q1: CDR subsampled to ZNE's budget (24,576 shots/point) vs ZNE (genuine, Richardson 1,3,5).

For each (rung, arm, point) and each allocation (target shots T, n_train N, shots per training
circuit s; T + N*s <= 24,576) we draw B random subsamples: N training circuits chosen at random
(without replacement), s shots without replacement from each circuit's pooled repeats/frames,
T shots from the pooled target. Expected |err| per point = mean over draws. Compared, paired
by point, with ZNE's realized error at its own 24,576 shots, and with raw at 24,576 shots.
"""
from __future__ import annotations

import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import *  # noqa

B = 400
BUDGET = 24576
CONFIGS = [  # (T, N, s)
    (8192, 20, 819), (8192, 10, 1638), (8192, 8, 2048), (8192, 4, 4096),
    (4096, 10, 2048), (12288, 6, 2048), (16384, 4, 2048), (4096, 20, 1024),
]
FULL_MULT = [1, 2, 4, 8, 16, 42]   # budget multiples for a cost curve with best config shape


def cdr_draw(d, T, N, s, rng):
    keys = sorted(d["train"])
    pick = rng.choice(keys, size=min(N, len(keys)), replace=False)
    xs = [sub_hist(d["h_train"][i], s, rng) for i in pick]
    ys = [d["train_ideal"][i] for i in pick]
    a, b, _ = ols(xs, ys)
    xt = sub_hist(d["h_target"], T, rng)
    return abs(a * xt + b - d["ideal"])


def main():
    recs = load("w01A")
    g = cdr_groups(recs)
    z = zne_groups(recs)
    for d in g.values():
        d["h_target"] = hw_hist(d["target"])
        d["h_train"] = {i: hw_hist(v) for i, v in d["train"].items()}
    rng = np.random.default_rng(1)
    rows = []
    lines = []
    for rung in ("star", "circular"):
        zerr = np.array([abs(RICH[(1, 3, 5)] @ [z[(rung, e)][("genuine", s)].expval for s in (1, 3, 5)]
                             - z[(rung, e)][("genuine", 1)].meta["ideal"]) for e in EVAL])
        # raw at equal budget: 24,576 shots of the (untwirled) target
        offk = [(rung, "off_copies", "near_target", e) for e in EVAL]
        raw24 = np.array([np.mean([abs(sub_hist(g[k]["h_target"], BUDGET, rng) - g[k]["ideal"])
                                   for _ in range(B)]) for k in offk])
        zraw = np.array([abs(z[(rung, e)][("genuine", 1)].expval - z[(rung, e)][("genuine", 1)].meta["ideal"]) for e in EVAL])
        lines.append(f"\n## {rung}  (n_cz={g[offk[0]]['target'][0].meta['n_cz']})")
        lines.append(f"ZNE genuine realized: mean err {zerr.mean():.4f}; raw(λ1, 8192 sh) {zraw.mean():.4f}; "
                     f"raw at 24,576 sh (expected) {raw24.mean():.4f}")
        lines.append("ZNE vs raw24: " + paired_report(zerr, raw24, "ZNE", "raw24"))
        for arm, ts in (("off_copies", "near_target"), ("twirl_native", "near_target"), ("spread", "near_target"),
                        ("twirl_logical", "shared_random"), ("twirl_native", "shared_random")):
            keys = [(rung, arm, ts, e) for e in EVAL]
            if ts == "near_target" and arm == "spread":
                cfgs = [(8192, 20, 819), (8192, 16, 1024), (8192, 8, 2048), (12288, 6, 2048), (4096, 20, 1024)]
            else:
                cfgs = CONFIGS
            best = None
            for (T, Nn, s) in cfgs:
                assert T + Nn * s <= BUDGET
                per_pt, pwin = [], []
                for k, ze in zip(keys, zerr):
                    e = np.array([cdr_draw(g[k], T, Nn, s, rng) for _ in range(B)])
                    per_pt.append(e.mean())
                    pwin.append((e < ze).mean())
                per_pt = np.array(per_pt)
                full = np.array([abs(ols([np.mean([r.expval for r in g[k]["train"][i]]) for i in sorted(g[k]["train"])],
                                         [g[k]["train_ideal"][i] for i in sorted(g[k]["train"])])[0]
                                     * np.mean([r.expval for r in g[k]["target"]])
                                     + ols([np.mean([r.expval for r in g[k]["train"][i]]) for i in sorted(g[k]["train"])],
                                           [g[k]["train_ideal"][i] for i in sorted(g[k]["train"])])[1] - g[k]["ideal"])
                                 for k in keys])
                rows.append(dict(rung=rung, arm=arm, train_set=ts, T=T, N=Nn, s=s, cdr_err=per_pt.mean(),
                                 zne_err=zerr.mean(), raw24=raw24.mean(), cdr_full=full.mean(),
                                 p_single_draw_beats_zne=float(np.mean(pwin))))
                if best is None or per_pt.mean() < best[0].mean():
                    best = (per_pt, (T, Nn, s), np.mean(pwin), full)
                lines.append(f"  {arm}:{ts} T={T} N={Nn} s={s}: E|err| {per_pt.mean():.4f}  "
                             f"(full-budget CDR {full.mean():.4f}); P(single CDR draw < ZNE) {np.mean(pwin):.2f}")
            per_pt, cfg, pw, full = best
            lines.append(f" BEST {arm}:{ts} {cfg}: " + paired_report(per_pt, zerr, "CDR@24k", "ZNE"))
            lines.append(f"      vs raw24: " + paired_report(per_pt, raw24, "CDR@24k", "raw24"))
    import pandas as pd
    pd.DataFrame(rows).to_csv(OUT / "q1_equal_budget.csv", index=False)
    txt = "\n".join(lines)
    (OUT / "q1_equal_budget.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
