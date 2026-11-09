"""'Free' mitigation: invert the line predicted by the calibrated simulator (exploratory).

For every (window, rung, point) the device-model simulation of the same night has run the
same 20 near-Clifford training circuits; its CDR fit (a_sim, b_sim) is applied to the
HARDWARE raw target value. No hardware training shots are used. Compared with raw and with
hardware CDR (untwirled and twirled) at the same points.

    python -m paper_analysis.sim_line_mitigation
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

REPO = pathlib.Path(__file__).resolve().parent.parent
HW = REPO / "runs" / "odra_campaign"
SIM = REPO / "runs" / "odra_sim_match"


def pooled_line(window: str, rung: str) -> tuple[float, float]:
    """OLS line ideal ~ a*noisy + b over all simulated off_copies training circuits of a rung."""
    xs, ys = {}, {}
    for line in open(SIM / window / "counts.jsonl"):
        d = json.loads(line)
        if d.get("kind") != "cdr" or d.get("arm") != "off_copies" or d.get("role") != "train":
            continue
        if d["rung"] != rung:
            continue
        k = (d["eval_index"], d["train_index"])
        xs.setdefault(k, []).append(d["expval"])
        ys[k] = d["ideal"]
    x = np.array([np.mean(v) for v in xs.values()])
    y = np.array([ys[k] for k in xs])
    a, b = np.polyfit(x, y, 1)
    return a, b


def main() -> None:
    rows = []
    for w in ("w01A", "w01B", "w01P5"):
        hw = pd.read_csv(HW / w / "cdr.csv")
        sm = pd.read_csv(SIM / w / "cdr.csv")
        hw = hw[hw.fit == "ols"]
        sm = sm[(sm.fit == "ols") & (sm.arm == "off_copies") & (sm.train_set == "near_target")]
        off = hw[(hw.arm == "off_copies") & (hw.train_set == "near_target")]
        tw = hw[(hw.arm == "twirl_native") & (hw.train_set == "near_target")]
        for rung, g in off.groupby("rung"):
            ap, bp = pooled_line(w, rung)
            for _, r in g.iterrows():
                s = sm[(sm.rung == rung) & (sm.eval_index == r.eval_index)].iloc[0]
                t = tw[(tw.rung == rung) & (tw.eval_index == r.eval_index)]
                rows.append(dict(window=w, rung=rung, n_cz=r.n_cz, point=r.eval_index,
                                 err_raw=r.err_raw, err_cdr=r.err,
                                 err_cdr_twirl=float(t.err.iloc[0]) if len(t) else np.nan,
                                 err_sim_point=abs(s.a * r.raw + s.b - r.ideal),
                                 err_sim_rung=abs(ap * r.raw + bp - r.ideal)))
    d = pd.DataFrame(rows)
    out = REPO / "paper_analysis" / "out"
    d.to_csv(out / "sim_line_points.csv", index=False)
    cols = ["err_raw", "err_sim_rung", "err_sim_point", "err_cdr", "err_cdr_twirl"]
    t = d.groupby(["window", "rung", "n_cz"])[cols].mean().round(4)
    t["sim_beats_raw"] = d.groupby(["window", "rung", "n_cz"]).apply(
        lambda g: f"{(g.err_sim_rung < g.err_raw).sum()}/{len(g)}")
    t["sim_beats_cdr"] = d.groupby(["window", "rung", "n_cz"]).apply(
        lambda g: f"{(g.err_sim_rung < g.err_cdr).sum()}/{len(g)}")
    lines = [t.sort_values("n_cz").to_string(), ""]

    def test(a, b, name):
        x, y = np.log(np.maximum(d[a], 1e-4)), np.log(np.maximum(d[b], 1e-4))
        p = wilcoxon(x, y).pvalue
        lines.append(f"{name}: wins {(d[a] < d[b]).sum()}/{len(d)}, geo ratio "
                     f"{np.exp(np.mean(x - y)):.3f}, two-sided Wilcoxon p = {p:.2g}")
    test("err_sim_rung", "err_raw", "sim line (pooled per rung) vs raw")
    test("err_sim_point", "err_raw", "sim line (per point) vs raw")
    test("err_sim_rung", "err_cdr", "sim line (pooled) vs hardware CDR")
    test("err_cdr", "err_raw", "hardware CDR vs raw (reference)")
    lad = d[d.window != "w01P5"].dropna()
    x, y = np.log(np.maximum(lad.err_sim_rung, 1e-4)), np.log(np.maximum(lad.err_cdr_twirl, 1e-4))
    lines.append(f"ladder only, sim line vs hardware CDR+twirl: wins {(lad.err_sim_rung < lad.err_cdr_twirl).sum()}/{len(lad)}, "
                 f"geo {np.exp(np.mean(x - y)):.3f}, p = {wilcoxon(x, y).pvalue:.2g}")
    txt = "\n".join(lines)
    (out / "sim_line_mitigation.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
