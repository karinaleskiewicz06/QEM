"""Shared loaders for the offline paper analyses (no QPU).

Every hardware window is read from its ``counts.jsonl`` (the raw record), never from the
derived CSVs, so budgets can be subsampled copy by copy. The matched simulations
(``runs/odra_sim_match/<window>``) were made with the same window id, hence the same
circuits, training sets and shots, under the device model built from that window's
start calibration.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

REPO = pathlib.Path(__file__).resolve().parent.parent
HW = REPO / "runs" / "odra_campaign"
SIM = REPO / "runs" / "odra_sim_match"
OUT = REPO / "paper_analysis" / "out"
FLOOR = 1e-3

#: hardware windows used and their CDR-like records
WINDOWS = ["w01A", "w01B", "w01P5", "w02vn", "w03dd"]
KEEP = ["circuit_id", "expval", "shots", "kind", "rung", "n_cz", "arm", "train_set", "eval_index",
        "role", "train_index", "repeat_index", "ideal", "variant", "scale", "level", "dd",
        "duration_s", "n_prx", "calibration_set_id"]


def load_window(path: pathlib.Path) -> pd.DataFrame:
    """One row per executed circuit, without counts / QASM."""
    rows = []
    with (path / "counts.jsonl").open() as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            rows.append({k: r.get(k) for k in KEEP})
    df = pd.DataFrame(rows)
    df["window"] = path.name
    return df


def available(root: pathlib.Path = HW) -> list[pathlib.Path]:
    return [root / w for w in WINDOWS if (root / w / "counts.jsonl").exists()]


def cdr_sets(df: pd.DataFrame) -> dict:
    """``{(window, rung, arm, eval_index): dict}`` with per-copy values of target and training.

    ``arm`` is the CDR arm (``off_copies`` / ``twirl_native`` ...) for night windows, the
    level-free base for w02vn (``vn_base``) and ``dd_off`` / ``dd_on`` for w03dd. Only
    near_target training sets (built on the native circuit), so every arm is comparable.
    """
    out: dict = {}
    for _, g in df.groupby("window"):
        w = g.window.iloc[0]
        if (g.kind == "cdr").any():
            sub = g[(g.kind == "cdr") & (g.train_set == "near_target")
                    & g.arm.isin(["off_copies", "twirl_native"])]
            keyed = sub.assign(arm_key=sub.arm)
        elif (g.kind == "vncdr").any():
            sub = g[(g.kind == "vncdr") & (g.level == "base")]
            keyed = sub.assign(arm_key="off_copies")
        elif (g.kind == "dd_cdr").any():
            sub = g[g.kind == "dd_cdr"]
            keyed = sub.assign(arm_key=np.where(sub.arm == "dd", "dd_on", "off_copies"))
        else:
            continue
        for (rung, arm, ei), s in keyed.groupby(["rung", "arm_key", "eval_index"]):
            t = s[s.role == "target"].sort_values("repeat_index")
            tr = s[s.role == "train"]
            if t.empty or tr.empty:
                continue
            n_tr = int(tr.train_index.max()) + 1
            reps = sorted(t.repeat_index.unique())
            X = np.full((n_tr, len(reps)), np.nan)
            for _, r in tr.iterrows():
                X[int(r.train_index), reps.index(int(r.repeat_index))] = r.expval
            y = tr.groupby("train_index").ideal.first().reindex(range(n_tr)).to_numpy(float)
            out[(w, rung, arm, int(ei))] = {
                "target": t.expval.to_numpy(float), "X": X, "y": y,
                "ideal": float(t.ideal.iloc[0]), "n_cz": int(t.n_cz.iloc[0]),
                "shots": int(t.shots.iloc[0]), "duration_s": t.duration_s.iloc[0],
                "calibration_set_id": t.calibration_set_id.iloc[0]}
    return out


def ols(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    vx = np.var(x)
    if vx <= 1e-14:
        return 0.0, float(np.mean(y))
    a = np.cov(x, y, bias=True)[0, 1] / vx
    return float(a), float(np.mean(y) - a * np.mean(x))


def logratio(a, b):
    return np.log(np.maximum(np.asarray(a, float), FLOOR)) - np.log(np.maximum(np.asarray(b, float), FLOOR))


def labels() -> dict[int, int]:
    """``{eval_index: y in {-1, +1}}`` from the frozen reference set."""
    ref = np.load(REPO / "trained_models_hard" / "two_curves_d8_q5_deg8_star_mean_L3_reference.npz")
    pts = json.load(open(REPO / "campaign" / "eval_points.json"))["points"]
    return {p["eval_index"]: int(ref["y_eval"][p["reference_index"]]) for p in pts}
