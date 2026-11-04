"""Shared pieces of the noise-informed CDR study (NI-CDR): data loading, the noise model,
fits and paired statistics.

Two ideas are tested, both offline:

* **MI-CDR** (model-informed CDR): one noise model per measurement window, fitted to the
  near-Clifford training circuits of *all* evaluation points at once,

      E = f + g * exp(-(a_cz * n_cz + a_t * T_us + a_p * n_prx / 10)) * O_ideal,

  where ``f`` is the floor (readout + relaxation offset), ``g`` the readout gain, and the
  exponent splits the signal loss into a CZ part and a duration part. The target is then
  corrected by inverting the model at the target's own n_cz, duration and n_prx. Because the
  model only re-uses the training data CDR already measured, the shot budget is unchanged.
* **2-axis vnCDR**: CDR whose regressors are the noisy values of the same circuit at several
  noise levels, scaled separately along CZ count (CZ.CZ pairs) and duration (matched idle),
  as in the P5 night.

Nothing here contacts a QPU; inputs are the recorded counts in runs/odra_campaign.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import wilcoxon

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
RUNS = REPO / "runs" / "odra_campaign"
OUT_HW = REPO / "runs" / "nicdr_offline"
OUT_SIM = REPO / "results_sim" / "nicdr"
N_Q = 5
FLOOR = 1e-3          # log-error floor, about the shot standard error (review recommendation)


# --------------------------------------------------------------------------- #
# Hardware records                                                              #
# --------------------------------------------------------------------------- #

def load_records(window: str) -> list[dict]:
    out = []
    with (RUNS / window / "counts.jsonl").open() as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                r.pop("qasm3", None)
                r.pop("frame", None)
                out.append(r)
    return out


def n_cz_of(r: dict) -> int:
    sk = r.get("cz_skeleton")
    return len(sk) if sk is not None else int(r["n_cz"])


def duration_us(r: dict) -> float:
    d = r.get("duration_sched_s")
    if d is None:
        d = r.get("duration_s")
    return float(d) * 1e6


def per_shot_values(counts: dict) -> tuple[np.ndarray, np.ndarray]:
    """(mean-Z value per distinct bitstring, its count); qiskit bit order (q = s[-1-q])."""
    vals, w = [], []
    for k, c in counts.items():
        s = k.replace(" ", "")[-N_Q:].zfill(N_Q)
        z = [1 - 2 * int(s[N_Q - 1 - q]) for q in range(N_Q)]
        vals.append(np.mean(z))
        w.append(c)
    return np.array(vals), np.array(w, float)


@dataclass
class Circ:
    """One logical circuit of a CDR arm: all its repeats (copies or frames) pooled."""
    rung: str
    arm: str
    train_set: str
    eval_index: int
    role: str
    train_index: int | None
    ideal: float
    n_cz: int
    n_prx: float
    t_us: float
    reps: list            # list of (values, weights) per repeat, in repeat_index order
    calib: str

    def mean(self, reps=None) -> float:
        rs = self.reps if reps is None else [self.reps[i] for i in reps]
        num = sum(float(np.dot(v, w)) for v, w in rs)
        den = sum(float(w.sum()) for v, w in rs)
        return num / den

    def var_of_mean(self, reps=None) -> float:
        rs = self.reps if reps is None else [self.reps[i] for i in reps]
        m = self.mean(reps)
        num = sum(float(np.dot((v - m) ** 2, w)) for v, w in rs)
        den = sum(float(w.sum()) for v, w in rs)
        return (num / den) / den

    @property
    def shots(self) -> int:
        return int(sum(w.sum() for _, w in self.reps))


def cdr_circuits(window: str, arm: str, train_set: str = "near_target") -> dict:
    """{(rung, eval_index): {"target": Circ, "train": [Circ ...]}} for one CDR arm."""
    groups: dict = defaultdict(list)
    for r in load_records(window):
        if r.get("kind") != "cdr" or r.get("arm") != arm or r.get("train_set") != train_set:
            continue
        key = (r["rung"], r["eval_index"], r["role"], r.get("train_index"))
        groups[key].append(r)
    out: dict = defaultdict(lambda: {"target": None, "train": []})
    for (rung, ei, role, ti), rs in groups.items():
        rs.sort(key=lambda x: (x.get("repeat_index") or 0))
        r0 = rs[0]
        c = Circ(rung=rung, arm=arm, train_set=train_set, eval_index=int(ei), role=role,
                 train_index=ti, ideal=float(r0["ideal"]), n_cz=n_cz_of(r0),
                 n_prx=float(np.mean([x["n_prx"] for x in rs])),
                 t_us=float(np.mean([duration_us(x) for x in rs])),
                 reps=[per_shot_values(x["counts"]) for x in rs],
                 calib=str(r0.get("calibration_set_id")))
        if role == "target":
            out[(rung, int(ei))]["target"] = c
        else:
            out[(rung, int(ei))]["train"].append(c)
    for v in out.values():
        v["train"].sort(key=lambda c: c.train_index)
    return dict(out)


def zne_records(window: str, variant: str = "genuine") -> list[dict]:
    rows = []
    for r in load_records(window):
        if r.get("kind") == "zne" and r.get("variant") == variant:
            rows.append({"rung": r["rung"], "eval_index": int(r["eval_index"]),
                         "scale": int(r["scale"]), "E": float(r["expval"]),
                         "ideal": float(r["ideal"]), "n_cz": n_cz_of(r),
                         "n_prx": float(r["n_prx"]), "t_us": duration_us(r),
                         "shots": int(r["shots"])})
    return rows


# --------------------------------------------------------------------------- #
# The noise model                                                                #
# --------------------------------------------------------------------------- #

#: which exponent terms each named model uses
MODELS = {
    "M_cz":  ("cz",),
    "M_t":   ("t",),
    "M_2":   ("cz", "t"),
    "M_3":   ("cz", "t", "prx"),
}


def _feat(n_cz, t_us, n_prx):
    return {"cz": np.asarray(n_cz, float), "t": np.asarray(t_us, float),
            "prx": np.asarray(n_prx, float) / 10.0}


@dataclass
class NoiseFit:
    name: str
    terms: tuple
    f: float
    g: float
    rates: dict          # term -> rate
    rmse: float
    n: int

    def attenuation(self, n_cz, t_us, n_prx):
        F = _feat(n_cz, t_us, n_prx)
        expo = sum(self.rates[k] * F[k] for k in self.terms)
        return np.exp(-expo)

    def predict(self, ideal, n_cz, t_us, n_prx):
        return self.f + self.g * self.attenuation(n_cz, t_us, n_prx) * np.asarray(ideal, float)

    def invert(self, E, n_cz, t_us, n_prx):
        return (np.asarray(E, float) - self.f) / (self.g * self.attenuation(n_cz, t_us, n_prx))

    def as_dict(self):
        d = {"model": self.name, "f": self.f, "g": self.g, "rmse": self.rmse, "n": self.n}
        d.update({f"rate_{k}": v for k, v in self.rates.items()})
        return d


def fit_noise(name: str, E, ideal, n_cz, t_us, n_prx, w=None) -> NoiseFit:
    """Weighted least squares; rates >= 0, g in (0, 1.5], f in [-0.3, 0.5]."""
    terms = MODELS[name]
    E = np.asarray(E, float)
    ideal = np.asarray(ideal, float)
    F = _feat(n_cz, t_us, n_prx)
    w = np.ones_like(E) if w is None else np.asarray(w, float)
    sw = np.sqrt(w / w.mean())

    def resid(p):
        f, g, *rates = p
        expo = sum(r * F[k] for r, k in zip(rates, terms))
        return sw * (f + g * np.exp(-expo) * ideal - E)

    x0 = [0.02, 0.95] + [0.01] * len(terms)
    lo = [-0.3, 1e-3] + [0.0] * len(terms)
    hi = [0.5, 1.5] + [5.0] * len(terms)
    res = least_squares(resid, x0, bounds=(lo, hi))
    f, g, *rates = res.x
    pred = f + g * np.exp(-sum(r * F[k] for r, k in zip(rates, terms))) * ideal
    rmse = float(np.sqrt(np.mean((pred - E) ** 2)))
    return NoiseFit(name, terms, float(f), float(g), dict(zip(terms, map(float, rates))),
                    rmse, int(E.size))


# --------------------------------------------------------------------------- #
# CDR fits                                                                       #
# --------------------------------------------------------------------------- #

def ols_line(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    vx = np.var(x)
    if vx <= 1e-14:
        return 0.0, float(np.mean(y))
    a = np.cov(x, y, bias=True)[0, 1] / vx
    return float(a), float(np.mean(y) - a * np.mean(x))


def ridge_to_prior(x, y, a0, b0, lam):
    """argmin sum (y - a x - b)^2 + lam * n * ((a - a0)^2 + (b - b0)^2)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = x.size
    X = np.column_stack([x, np.ones(n)])
    A = X.T @ X + lam * n * np.eye(2)
    rhs = X.T @ y + lam * n * np.array([a0, b0])
    a, b = np.linalg.solve(A, rhs)
    return float(a), float(b)


def multi_reg(Xtr, ytr, Xte, intercept=True):
    """Least squares of y on columns of X (vnCDR); returns prediction for Xte rows."""
    Xtr = np.atleast_2d(np.asarray(Xtr, float))
    Xte = np.atleast_2d(np.asarray(Xte, float))
    if intercept:
        Xtr = np.column_stack([Xtr, np.ones(len(Xtr))])
        Xte = np.column_stack([Xte, np.ones(len(Xte))])
    coef, *_ = np.linalg.lstsq(Xtr, np.asarray(ytr, float), rcond=None)
    return Xte @ coef, coef


# --------------------------------------------------------------------------- #
# Paired statistics                                                              #
# --------------------------------------------------------------------------- #

def paired(err_a, err_b, n_boot=10000, seed=0) -> dict:
    """A vs B on the same points: wins of A, geometric ratio A/B with bootstrap CI,
    one-sided Wilcoxon (A < B), mean errors."""
    a = np.maximum(np.asarray(err_a, float), FLOOR)
    b = np.maximum(np.asarray(err_b, float), FLOOR)
    d = np.log(a) - np.log(b)
    rng = np.random.default_rng(seed)
    boots = np.exp(rng.choice(d, (n_boot, d.size)).mean(axis=1))
    try:
        p = float(wilcoxon(d, alternative="less").pvalue) if np.any(d != 0) else 1.0
    except ValueError:
        p = float("nan")
    return {"n": int(d.size), "wins_A": int((d < 0).sum()),
            "mean_A": float(np.mean(err_a)), "mean_B": float(np.mean(err_b)),
            "rms_A": float(np.sqrt(np.mean(np.square(err_a)))),
            "rms_B": float(np.sqrt(np.mean(np.square(err_b)))),
            "geo_ratio": float(np.exp(d.mean())),
            "ci_lo": float(np.quantile(boots, 0.025)), "ci_hi": float(np.quantile(boots, 0.975)),
            "p_wilcoxon_less": p}


def fmt_paired(name: str, s: dict) -> str:
    return (f"{name:<44s} n={s['n']:2d} wins={s['wins_A']:2d}/{s['n']:<2d} "
            f"mean {s['mean_A']:.4f} vs {s['mean_B']:.4f}  geo {s['geo_ratio']:.2f} "
            f"[{s['ci_lo']:.2f},{s['ci_hi']:.2f}]  p={s['p_wilcoxon_less']:.3f}")
