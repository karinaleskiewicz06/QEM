"""Shared, read-only loaders and helpers for the offline prototypes.

Reads runs/odra_campaign/w01A and w01P5 counts.jsonl. Never writes into the repo outside
this prototypes/ folder. Bit order: qiskit convention (qubit q = s[-1-q]), as in
noisy_sim.perqubit_z_from_counts. Observable: mean-Z (coeffs 0.2 each).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from collections import defaultdict

import numpy as np

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
REPO = pathlib.Path("/Users/karinaleskiewicz/QEM")
sys.path.insert(0, str(REPO))
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

N = 5
COEFFS = np.full(N, 0.2)
#: wire q -> physical qubit (calibrations/odra_w01A_start.json meta.qubit_order_logical_to_physical)
PHYS = ["QB3", "QB1", "QB2", "QB4", "QB5"]
EVAL = [0, 3, 6, 9, 12, 15, 18, 21]


def load(window: str) -> list[dict]:
    p = REPO / "runs/odra_campaign" / window / "counts.jsonl"
    out = []
    for line in p.open():
        if line.strip():
            r = json.loads(line)
            r.pop("qasm3", None)
            out.append(r)
    return out


def counts_to_matrix(counts: dict) -> tuple[np.ndarray, np.ndarray]:
    """(bits[K, N] with bit of qubit q in column q, weights[K])."""
    keys = list(counts)
    w = np.array([counts[k] for k in keys], float)
    bits = np.zeros((len(keys), N), int)
    for i, k in enumerate(keys):
        s = k.replace(" ", "")[-N:].zfill(N)
        for q in range(N):
            bits[i, q] = int(s[N - 1 - q])
    return bits, w


class Rec:
    """One circuit execution, with per-shot observable values available for subsampling."""

    __slots__ = ("meta", "bits", "w", "zq", "shots", "o_vals")

    def __init__(self, r: dict):
        self.meta = r
        self.bits, self.w = counts_to_matrix(r["counts"])
        self.shots = int(self.w.sum())
        z = 1 - 2 * self.bits                       # K x N in {+1,-1}
        self.zq = (z * self.w[:, None]).sum(0) / self.shots
        self.o_vals = z @ COEFFS                     # per-outcome observable value

    @property
    def expval(self) -> float:
        return float(self.zq @ COEFFS)

    def shot_var(self) -> float:
        """Per-shot variance of the observable."""
        m = (self.o_vals * self.w).sum() / self.shots
        return float(((self.o_vals - m) ** 2 * self.w).sum() / self.shots)

    def subsample(self, k: int, rng) -> float:
        """Expectation of the observable from k shots drawn without replacement."""
        if k >= self.shots:
            return self.expval
        draw = rng.multivariate_hypergeometric(self.w.astype(np.int64), k)
        return float((self.o_vals * draw).sum() / k)


def pooled_subsample(recs: list[Rec], k: int, rng) -> float:
    """k shots without replacement from the pool of several executions of one circuit."""
    o = np.concatenate([r.o_vals for r in recs])
    w = np.concatenate([r.w for r in recs]).astype(np.int64)
    if k >= w.sum():
        return float((o * w).sum() / w.sum())
    draw = rng.multivariate_hypergeometric(w, k)
    return float((o * draw).sum() / k)


def cdr_groups(recs: list[dict]) -> dict:
    """(rung, arm, train_set, eval_index) -> {'target': [Rec]*M, 'train': {i: [Rec]*M}, 'ideal', 'train_ideal': {i: y}}."""
    g: dict = {}
    for r in recs:
        if r.get("kind") != "cdr":
            continue
        key = (r["rung"], r["arm"], r["train_set"], r["eval_index"])
        d = g.setdefault(key, {"target": [], "train": defaultdict(list), "train_ideal": {}})
        rec = Rec(r)
        if r["role"] == "target":
            d["target"].append(rec)
            d["ideal"] = r["ideal"]
        else:
            d["train"][r["train_index"]].append(rec)
            d["train_ideal"][r["train_index"]] = r["ideal"]
    for d in g.values():
        d["target"].sort(key=lambda x: x.meta["repeat_index"])
        for i in d["train"]:
            d["train"][i].sort(key=lambda x: x.meta["repeat_index"])
    return g


def zne_groups(recs: list[dict]) -> dict:
    """(rung, eval_index) -> {(variant, scale): Rec}; genuine scale 1 shared by all variants."""
    g: dict = defaultdict(dict)
    for r in recs:
        if r.get("kind") == "zne":
            g[(r["rung"], r["eval_index"])][(r["variant"], r["scale"])] = Rec(r)
    return g


def ols(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    A = np.vstack([x, np.ones_like(x)]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = a * x + b
    ss = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ((y - pred) ** 2).sum() / ss if ss > 1e-12 else 0.0
    return float(a), float(b), float(r2)


RICH = {(1, 3, 5): np.array([15 / 8, -5 / 4, 3 / 8]), (1, 3): np.array([1.5, -0.5])}


def boot_mean_ci(v, B=10000, seed=0, alpha=0.05):
    v = np.asarray(v, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(B, len(v)))
    m = v[idx].mean(1)
    return float(v.mean()), float(np.quantile(m, alpha / 2)), float(np.quantile(m, 1 - alpha / 2))


def paired_report(a, b, label_a="A", label_b="B", seed=0) -> str:
    """Paired comparison of per-point errors a vs b (lower is better)."""
    from scipy.stats import wilcoxon
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    d = a - b
    m, lo, hi = boot_mean_ci(d, seed=seed)
    lr = np.log(np.maximum(a, 1e-4)) - np.log(np.maximum(b, 1e-4))
    gm, glo, ghi = boot_mean_ci(lr, seed=seed + 1)
    try:
        p = wilcoxon(a, b).pvalue
    except ValueError:
        p = float("nan")
    wins = int((a < b).sum())
    return (f"mean err {label_a}={a.mean():.4f} {label_b}={b.mean():.4f}; "
            f"diff {m:+.4f} [95% boot {lo:+.4f},{hi:+.4f}]; "
            f"geo ratio {np.exp(gm):.2f} [{np.exp(glo):.2f},{np.exp(ghi):.2f}]; "
            f"{label_a} wins {wins}/{len(a)}; Wilcoxon 2-sided p={p:.3f}")


def hw_hist(recs: list[Rec]) -> np.ndarray:
    """Pooled histogram over the 6 values of mean-Z (Hamming weight 0..5), as int64 counts."""
    h = np.zeros(N + 1, np.int64)
    for r in recs:
        hw = r.bits.sum(1)
        np.add.at(h, hw, r.w.astype(np.int64))
    return h


HW_VAL = 1 - 2 * np.arange(N + 1) / N      # mean-Z of Hamming weight k


def sub_hist(h: np.ndarray, k: int, rng) -> float:
    if k >= h.sum():
        return float(HW_VAL @ h / h.sum())
    d = rng.multivariate_hypergeometric(h, k)
    return float(HW_VAL @ d / k)
