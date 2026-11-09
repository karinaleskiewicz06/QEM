"""Offline toy study: noise-informed CDR variants on a 5-qubit star (PRX + CZ).

Self-contained numpy density-matrix simulator with ASAP scheduling, so idle time
(spokes waiting for the hub) is modelled. Writes only to this directory.

Truth noise: CZ depolarizing + coherent ZZ over-rotation (or its exact Pauli twirl),
1q depolarizing, T1/T2 relaxation during gates and idles, symmetric readout flip.

Variants compared at equal total shot budget per target:
  cdr_drop      repo behaviour: snapped theta=0 rotations removed (shorter schedule)
  cdr_matched   theta=0 rotations replaced by a 20 ns delay (identical schedule)
  vncdr         training+target folded at lambda 1,3,5; y = a.x (no intercept), Lowe 2021
  vncdr_int     same with intercept
  zne_lin       target only, linear extrapolation over 1,3,5
  model_sub     fit (p_cz, idle-rate scale, readout factor) to the Clifford training data,
                then subtract the model-predicted bias of the target (needs target sim)
  model_cdr     fitted model generates 100 synthetic Clifford training points (no QPU)
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys
import time

import numpy as np
from scipy.optimize import least_squares

OUT = pathlib.Path(__file__).resolve().parent
N = 5
T_PRX, T_CZ = 20e-9, 60e-9
I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], complex)
Y = np.array([[0, -1j], [1j, 0]], complex)
Z = np.diag([1, -1]).astype(complex)
PAULI1 = [I2, X, Y, Z]
PAULI2 = [np.kron(a, b) for a in PAULI1 for b in PAULI1]
CZ = np.diag([1, 1, 1, -1]).astype(complex)
ZZ = np.kron(Z, Z)


def rgate(theta, phi):
    return (np.cos(theta / 2) * I2
            - 1j * np.sin(theta / 2) * (np.cos(phi) * X + np.sin(phi) * Y))


# ----------------------------------------------------------------- simulator
def apply(rho, K, qs):
    """rho -> K rho K^dag for one operator K on qubits qs (rho as 2N-index tensor)."""
    k = len(qs)
    Kt = K.reshape((2,) * (2 * k))
    rows = list(qs)
    cols = [N + q for q in qs]
    # left multiply
    rho = np.tensordot(Kt, rho, axes=(list(range(k, 2 * k)), rows))
    rho = np.moveaxis(rho, list(range(k)), rows)
    rho = np.tensordot(Kt.conj(), rho, axes=(list(range(k, 2 * k)), cols))
    rho = np.moveaxis(rho, list(range(k)), cols)
    return rho


def channel(rho, kraus, qs):
    return sum(apply(rho, K, qs) for K in kraus)


def depol_kraus(p, nq):
    P = PAULI1 if nq == 1 else PAULI2
    d = len(P)
    return [np.sqrt(1 - p) * P[0]] + [np.sqrt(p / (d - 1)) * Pk for Pk in P[1:]]


_relax_cache: dict = {}


def relax_kraus(t, T1, T2):
    key = (round(t * 1e12), T1, T2)
    if key in _relax_cache:
        return _relax_cache[key]
    g = 1 - np.exp(-t / T1)
    tphi_rate = max(1 / T2 - 1 / (2 * T1), 0.0)
    c = np.exp(-t * tphi_rate)
    ad = [np.array([[1, 0], [0, np.sqrt(1 - g)]], complex),
          np.array([[0, np.sqrt(g)], [0, 0]], complex)]
    pd = [np.array([[1, 0], [0, c]], complex),
          np.array([[0, 0], [0, np.sqrt(max(1 - c * c, 0))]], complex)]
    out = [b @ a for a in ad for b in pd]
    _relax_cache[key] = out
    return out


def simulate(circ, nm):
    """Exact noisy <mean Z> (readout included) of a gate list under noise dict nm."""
    rho = np.zeros((2,) * (2 * N), complex)
    rho[(0,) * (2 * N)] = 1.0
    free = np.zeros(N)
    last = np.zeros(N)

    def idle(rho, q, upto):
        dt = upto - last[q]
        if dt > 1e-12 and nm["T1"] < np.inf:
            rho = channel(rho, relax_kraus(dt, nm["T1"], nm["T2"]), [q])
        last[q] = upto
        return rho

    for g in circ:
        if g[0] == "delay":
            free[g[1]] += g[2]
            continue
        qs = [g[1]] if g[0] == "r" else [g[1], g[2]]
        start = max(free[q] for q in qs)
        for q in qs:
            rho = idle(rho, q, start)
        if g[0] == "r":
            rho = apply(rho, rgate(g[2], g[3]), qs)
            dur = T_PRX
            if nm["p1"] > 0:
                rho = channel(rho, depol_kraus(nm["p1"], 1), qs)
        else:
            rho = apply(rho, CZ, qs)
            dur = T_CZ
            if nm.get("eps", 0) and not nm.get("twirl", False):
                e = nm["eps"]
                U = np.cos(e / 2) * np.eye(4) - 1j * np.sin(e / 2) * ZZ
                rho = apply(rho, U, qs)
            if nm.get("eps", 0) and nm.get("twirl", False):
                s = np.sin(nm["eps"] / 2) ** 2
                rho = channel(rho, [np.sqrt(1 - s) * np.eye(4), np.sqrt(s) * ZZ], qs)
            if nm["p2"] > 0:
                rho = channel(rho, depol_kraus(nm["p2"], 2), qs)
        for q in qs:
            last[q] = start  # gate-time decoherence applied as idle over the gate
            free[q] = start + dur
        for q in qs:
            rho = idle(rho, q, start + dur)
    T_end = free.max()
    for q in range(N):
        rho = idle(rho, q, T_end)
    probs = np.real(np.diagonal(rho.reshape(2 ** N, 2 ** N)))
    zs = []
    for q in range(N):
        sign = np.array([1 - 2 * ((i >> (N - 1 - q)) & 1) for i in range(2 ** N)])
        zs.append(float(probs @ sign))
    return float(np.mean(zs)) * (1 - 2 * nm["pro"])


def ideal(circ):
    nm = dict(T1=np.inf, T2=np.inf, p1=0, p2=0, eps=0, pro=0)
    return simulate(circ, nm)


def schedule_duration(circ):
    free = np.zeros(N)
    for g in circ:
        if g[0] == "delay":
            free[g[1]] += g[2]
            continue
        qs = [g[1]] if g[0] == "r" else [g[1], g[2]]
        s = max(free[q] for q in qs)
        for q in qs:
            free[q] = s + (T_PRX if g[0] == "r" else T_CZ)
    return float(free.max())


# ----------------------------------------------------------------- circuits
CLIFF = np.array([0, np.pi / 2, np.pi, 3 * np.pi / 2])


def star_target(rng, layers=3):
    c = []
    for _ in range(layers):
        for q in range(N):
            c.append(("r", q, rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi)))
        for k in range(1, N):
            c.append(("cz", 0, k))
    for q in range(N):
        c.append(("r", q, rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi)))
    return c


def angdist(a, b):
    return np.abs((a - b % (2 * np.pi) + np.pi) % (2 * np.pi) - np.pi)


def snap(c, rng, mode, sigma=np.pi / 4, nearest=False):
    out = []
    for g in c:
        if g[0] != "r":
            out.append(g)
            continue
        th_ph = []
        for a in g[2:4]:
            d = angdist(CLIFF, a)
            if nearest:
                th_ph.append(float(CLIFF[np.argmin(d)]))
            else:
                w = np.exp(-(d / sigma) ** 2)
                th_ph.append(float(rng.choice(CLIFF, p=w / w.sum())))
        th, ph = th_ph
        if abs(np.sin(th / 2)) < 1e-12:
            if mode == "matched":
                out.append(("delay", g[1], T_PRX))
            continue
        out.append(("r", g[1], th, ph))
    return out


def inverse(c):
    out = []
    for g in reversed(c):
        if g[0] == "r":
            out.append(("r", g[1], -g[2], g[3]))
        else:
            out.append(g)
    return out


def fold(c, lam):
    k = (lam - 1) // 2
    out = list(c)
    inv = inverse(c)
    for _ in range(k):
        out += inv + c
    return out


# ----------------------------------------------------------------- methods
def ols(x, y, intercept=True):
    x = np.atleast_2d(np.asarray(x, float))
    if x.shape[0] != len(y):
        x = x.T
    A = np.hstack([x, np.ones((len(y), 1))]) if intercept else x
    coef, *_ = np.linalg.lstsq(A, np.asarray(y, float), rcond=None)
    return coef


def predict(coef, x, intercept=True):
    x = np.atleast_1d(np.asarray(x, float))
    return float(x @ coef[:len(x)] + (coef[-1] if intercept else 0.0))


def shot_sd(v, shots):
    return np.sqrt(max(1 - v * v, 1e-6) / (N * shots))


def main(n_targets=8, n_train=20, budget=42000, reps=300, seed=7, twirl=False,
         eps=0.10, tag=""):
    rng = np.random.default_rng(seed)
    truth = dict(T1=40e-6, T2=25e-6, p1=1e-3, p2=0.012, eps=eps, twirl=twirl, pro=0.02)
    rows = []
    t0 = time.time()
    for t in range(n_targets):
        tgt = star_target(rng)
        trs = {m: [snap(tgt, rng, m, nearest=True)] for m in ("drop", "matched")}
        # same random draws for both modes: re-seed per circuit
        for i in range(1, n_train):
            s = int(rng.integers(1 << 30))
            for m in ("drop", "matched"):
                trs[m].append(snap(tgt, np.random.default_rng(s), m))
        rec = dict(target=t, ideal=ideal(tgt),
                   dur_target=schedule_duration(tgt),
                   dur_train_drop=float(np.mean([schedule_duration(c) for c in trs["drop"]])),
                   dur_train_matched=float(np.mean([schedule_duration(c) for c in trs["matched"]])),
                   prx_target=sum(g[0] == "r" for g in tgt),
                   prx_train_drop=float(np.mean([sum(g[0] == "r" for g in c) for c in trs["drop"]])))
        rec["tgt"] = {lam: simulate(fold(tgt, lam), truth) for lam in (1, 3, 5)}
        rec["y"] = [ideal(c) for c in trs["matched"]]
        assert np.allclose(rec["y"], [ideal(c) for c in trs["drop"]])
        rec["x_drop"] = [simulate(c, truth) for c in trs["drop"]]
        rec["x_m"] = {lam: [simulate(fold(c, lam), truth) for c in trs["matched"]]
                      for lam in (1, 3, 5)}

        # --- model-informed: fit (p2, idle-rate scale k, readout factor r) to training data
        def model(params):
            p2, k, r = params
            return dict(T1=40e-6 / k, T2=25e-6 / k, p1=1e-3, p2=p2, eps=0, twirl=False,
                        pro=(1 - r) / 2)

        def fit_model(xs):
            res = least_squares(
                lambda p: np.array([simulate(c, model(p)) for c in trs["matched"]]) - xs,
                x0=[0.01, 1.0, 0.96], bounds=([0, 0.05, 0.5], [0.2, 20, 1.0]),
                diff_step=1e-3, max_nfev=40)
            return res.x
        p_inf = fit_model(np.array(rec["x_m"][1]))
        rec["model_params_infshot"] = p_inf.tolist()
        m_inf = model(p_inf)
        rec["model_bias_tgt"] = simulate(tgt, m_inf) - rec["ideal"]
        synth_rng = np.random.default_rng(1000 + t)
        synth = [snap(tgt, synth_rng, "matched") for _ in range(60)]
        sx = [simulate(c, m_inf) for c in synth]
        sy = [ideal(c) for c in synth]
        rec["model_cdr_coef"] = ols(sx, sy).tolist()
        rows.append(rec)
        print(f"target {t} done {time.time()-t0:.0f}s ideal={rec['ideal']:+.3f} "
              f"raw={rec['tgt'][1]:+.3f} fit={np.round(p_inf,4)}", flush=True)

    # ------------------------------------------------- shot-noise Monte Carlo at equal budget
    S21 = budget // (n_train + 1)          # single-level CDR
    S63 = budget // (3 * (n_train + 1))    # three-level vnCDR
    S3 = budget // 3                       # ZNE target only
    mrng = np.random.default_rng(seed + 1)
    errs = {k: [] for k in ("raw", "cdr_drop", "cdr_matched", "vncdr", "vncdr_int",
                            "zne_lin", "model_sub", "model_cdr")}
    bias = {k: [] for k in errs}

    def noisy(v, S):
        v = np.asarray(v, float)
        return v + mrng.normal(0, 1, v.shape) * np.sqrt(np.clip(1 - v ** 2, 1e-6, None) / (N * S))

    for r in rows:
        y = np.array(r["y"])
        idl = r["ideal"]
        # infinite-shot bias
        bias["raw"].append(r["tgt"][1] - idl)
        bias["cdr_drop"].append(predict(ols(r["x_drop"], y), r["tgt"][1]) - idl)
        bias["cdr_matched"].append(predict(ols(r["x_m"][1], y), r["tgt"][1]) - idl)
        X3 = np.array([r["x_m"][l] for l in (1, 3, 5)]).T
        tv = np.array([r["tgt"][l] for l in (1, 3, 5)])
        bias["vncdr"].append(predict(ols(X3, y, False), tv, False) - idl)
        bias["vncdr_int"].append(predict(ols(X3, y), tv) - idl)
        lam = np.array([1, 3, 5.0])
        bias["zne_lin"].append(float(np.polyfit(lam, tv, 1)[1]) - idl)
        bias["model_sub"].append(r["tgt"][1] - r["model_bias_tgt"] - idl)
        bias["model_cdr"].append(predict(np.array(r["model_cdr_coef"]), r["tgt"][1]) - idl)
        for _ in range(reps):
            t1 = noisy(r["tgt"][1], S21)
            errs["raw"].append(abs(noisy(r["tgt"][1], budget) - idl))
            errs["cdr_drop"].append(abs(predict(ols(noisy(r["x_drop"], S21), y), t1) - idl))
            errs["cdr_matched"].append(abs(predict(ols(noisy(r["x_m"][1], S21), y), t1) - idl))
            Xn = noisy(X3, S63)
            tn = noisy(tv, S63)
            errs["vncdr"].append(abs(predict(ols(Xn, y, False), tn, False) - idl))
            errs["vncdr_int"].append(abs(predict(ols(Xn, y), tn) - idl))
            tz = noisy(tv, S3)
            errs["zne_lin"].append(abs(float(np.polyfit(lam, tz, 1)[1]) - idl))
            # model methods: approximate shot effect by noise on target only
            # (model fit to 20x2000-shot data; fit noise neglected -> optimistic, flagged)
            errs["model_sub"].append(abs(t1 - r["model_bias_tgt"] - idl))
            errs["model_cdr"].append(abs(predict(np.array(r["model_cdr_coef"]), t1) - idl))

    summary = {k: dict(mae_equal_budget=float(np.mean(v)),
                       mean_abs_bias_infshot=float(np.mean(np.abs(bias[k]))))
               for k, v in errs.items()}
    meta = dict(truth={k: (v if not isinstance(v, float) or np.isfinite(v) else str(v))
                       for k, v in truth.items()},
                n_targets=n_targets, n_train=n_train, budget=budget, reps=reps,
                dur_target_ns=1e9 * np.mean([r["dur_target"] for r in rows]),
                dur_train_drop_ns=1e9 * np.mean([r["dur_train_drop"] for r in rows]),
                dur_train_matched_ns=1e9 * np.mean([r["dur_train_matched"] for r in rows]),
                prx_target=np.mean([r["prx_target"] for r in rows]),
                prx_train_drop=np.mean([r["prx_train_drop"] for r in rows]),
                model_params=[r["model_params_infshot"] for r in rows])
    out = dict(meta=meta, summary=summary)
    (OUT / f"nicdr_results{tag}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    tw = "--twirl" in sys.argv
    eps = 0.0 if "--noeps" in sys.argv else 0.10
    tag = ("_twirl" if tw else "_coherent") if eps else "_pauli_only"
    main(twirl=tw, eps=eps, tag=tag)
