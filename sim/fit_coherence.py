"""How coherent is ODRA's CZ? ABC fit of (theta, eps) to the archived twirl windows.

Two hardware statistics carry the coherent signature, per ladder point:

* ``r2_off`` -- the CDR fit quality *without* twirling. Coherent error bends the
  noisy-vs-ideal relation away from a line, so r2 falls with CZ count;
* ``log_ratio`` -- ``log(err_twirl / err_off)`` at equal budget. Twirling converts
  coherent into stochastic error, so the gain grows with the coherent part.

For every point of a grid over the ZZ angle ``theta`` and the PRX over-rotation ``eps``,
the *same* runner that produced the hardware numbers (``run_garnet_twirl.py``, same
protocol: logical twirl, shared training set, n_train = 10, M = 6, 4 evaluation points,
8192 shots) is run on ``sim.device_model`` with ``--sim-device``. The distance to the
hardware is

    d^2 = sum_points ((r2_sim - r2_hw) / s_r2)^2 + ((lr_sim - lr_hw) / s_lr)^2

with ``s^2 = s_hw^2 + s_sim^2 / R``: the between-window variance of the hardware
statistic (pooled over points) plus the variance of the mean of ``R`` simulated draws
at that grid point. Without the second term a single noisy draw can land close to the
hardware by chance and dominate. The grid gets kernel-ABC weights ``exp(-d^2 / 2)``
(flat prior). The predictive
check fits on all ladder points but the held-out one(s) and compares the weighted
prediction there with the hardware.

Caveats, all stated in the output: two hardware windows only, so ``s`` is crude; the
calibration snapshot (2026-08-03) is six weeks older than the windows (2026-09-13/15);
the simulation is one draw per grid point unless ``--sim-reps`` is raised.

    python -m sim.fit_coherence                               # full grid, ~30 min
    python -m sim.fit_coherence --quick                       # smoke: 2x1 grid, 2 points
"""

from __future__ import annotations

import argparse
import itertools
import os
import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd

REPO = pathlib.Path(__file__).resolve().parent.parent
THETAS = (0.0, 0.01, 0.02, 0.03, 0.05)
EPSES = (0.0, 0.005, 0.01)
HARDWARE = ("odra_twirl_o1.csv", "odra_twirl_o2.csv")
OUT_DIR = pathlib.Path("results_sim/fit_coherence")


def ladder_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """Per (window, pattern): ``cz``, ``r2_off`` and ``log_ratio`` from a twirl CSV."""
    cdr = df[df["arm"] == "cdr"].copy()
    cdr["twirl"] = cdr["twirl"].astype(str).str.lower() == "true"
    key = ["window", "pattern"]
    off = cdr[~cdr.twirl].set_index(key)
    on = cdr[cdr.twirl].set_index(key)
    out = pd.DataFrame({
        "cz": off["transpiled_cz"].astype(int),
        "r2_off": off["cdr_r2"].astype(float),
        "log_ratio": np.log(on["err"].astype(float) / off["err"].astype(float)),
    })
    return out.reset_index()


def hardware_targets(paths) -> tuple[pd.DataFrame, float, float]:
    """Mean statistics per pattern, and the pooled between-window SDs."""
    st = pd.concat([ladder_statistics(pd.read_csv(REPO / p)) for p in paths])
    g = st.groupby("pattern")
    mean = g[["cz", "r2_off", "log_ratio"]].mean()
    if st["window"].nunique() < 2:
        raise ValueError("need at least two windows to estimate the spread")
    s_r2 = float(np.sqrt(g["r2_off"].var(ddof=1).mean()))
    s_lr = float(np.sqrt(g["log_ratio"].var(ddof=1).mean()))
    return mean, s_r2, s_lr


def simulate(theta: float, eps: float, *, calibration: str, patterns, phi: float,
             rep: int, cache: pathlib.Path, eval_points: int, shots: int,
             n_train: int, n_twirl: int, gate_t2: str = "echo",
             schedule: str = "alap") -> pd.DataFrame:
    """One draw at one grid point through ``run_garnet_twirl.py --sim-device``.

    Runs the archived protocol, including its compilation path (``--legacy-transpile``),
    because the hardware statistics it is compared with were produced that way. Cached
    under a key that names every model setting, so a changed model never reuses a stale
    draw.
    """
    key = (f"{pathlib.Path(calibration).stem}_g{gate_t2}_{schedule}_th{theta}_eps{eps}"
           f"_phi{phi}_r{rep}_{'-'.join(patterns)}_S{shots}_legacyT")
    out = cache / f"{key}.csv"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".partial.csv")
        tmp.unlink(missing_ok=True)
        cmd = [sys.executable, "run_garnet_twirl.py", "--device", "odra",
               "--sim-device", calibration, "--sim-theta", str(theta),
               "--sim-phi", str(phi), "--sim-eps", str(eps),
               "--sim-gate-t2", gate_t2, "--sim-schedule", schedule, "--legacy-transpile",
               "--points", *[f"optimal:{p}" for p in patterns],
               "--arms", "cdr", "--twirl-arms", "cdr", "--eval-points", str(eval_points),
               "--shots", str(shots), "--n-train", str(n_train), "--n-twirl", str(n_twirl),
               "--window-id", f"fit{rep}", "--no-provenance", "--out", str(tmp)]
        env = {**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE"}
        res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            raise RuntimeError(f"simulation failed for theta={theta} eps={eps}:\n"
                               + res.stderr[-3000:])
        tmp.rename(out)
    return ladder_statistics(pd.read_csv(out))


def distances(sim: pd.DataFrame, hw: pd.DataFrame, s_r2: float, s_lr: float,
              patterns) -> float:
    """``d^2`` over ``patterns`` (both statistics), simulation noise included.

    ``sim`` holds one row per (draw, pattern). With two or more draws the variance of
    their mean is added to the hardware variance; with one draw it cannot be estimated
    and only the hardware term is used.
    """
    g = sim.groupby("pattern")[["r2_off", "log_ratio"]]
    m, n = g.mean(), g.count()
    v = g.var(ddof=1).fillna(0.0)
    d2 = 0.0
    for p in patterns:
        for stat, s_hw in (("r2_off", s_r2), ("log_ratio", s_lr)):
            var = s_hw ** 2 + (v.loc[p, stat] / n.loc[p, stat] if n.loc[p, stat] > 1 else 0.0)
            d2 += (m.loc[p, stat] - hw.loc[p, stat]) ** 2 / var
    return float(d2)


def abc(table: pd.DataFrame, col: str = "d2") -> pd.Series:
    """Normalised kernel weights ``exp(-d^2 / 2)``."""
    w = np.exp(-(table[col] - table[col].min()) / 2.0)
    return w / w.sum()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", default="calibrations/odra_raw_20260803.json")
    ap.add_argument("--hardware", nargs="+", default=list(HARDWARE))
    ap.add_argument("--thetas", type=float, nargs="+", default=list(THETAS))
    ap.add_argument("--eps", type=float, nargs="+", default=list(EPSES))
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--holdout", nargs="+", default=["all_to_all"],
                    help="ladder points left out of the fit and predicted")
    ap.add_argument("--sim-reps", type=int, default=3)
    ap.add_argument("--gate-t2", choices=["echo", "ramsey"], default="echo")
    ap.add_argument("--schedule", choices=["alap", "asap"], default="alap")
    ap.add_argument("--eval-points", type=int, default=4)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--n-train", type=int, default=10)
    ap.add_argument("--n-twirl", type=int, default=6)
    ap.add_argument("--quick", action="store_true",
                    help="smoke run: theta {0, 0.05}, eps {0}, star + linear, 1024 shots")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    hw, s_r2, s_lr = hardware_targets(args.hardware)
    patterns = list(hw.index)
    if args.quick:
        args.thetas, args.eps, args.shots, args.sim_reps = [0.0, 0.05], [0.0], 1024, 2
        patterns, args.holdout = ["star", "linear"], ["linear"]
    fit_on = [p for p in patterns if p not in args.holdout]
    if not fit_on:
        raise SystemExit("nothing left to fit on after --holdout")
    out_dir = pathlib.Path(args.out_dir)
    print(f"hardware ({', '.join(args.hardware)}): between-window SD r2 {s_r2:.3f}, "
          f"log-ratio {s_lr:.3f}")
    print(hw.round(3).to_string())

    rows, sims = [], {}
    for theta, eps in itertools.product(args.thetas, args.eps):
        reps = [simulate(theta, eps, calibration=args.calibration, patterns=patterns,
                         phi=args.phi, rep=r, cache=out_dir / "cache",
                         eval_points=args.eval_points, shots=args.shots,
                         n_train=args.n_train, n_twirl=args.n_twirl,
                         gate_t2=args.gate_t2, schedule=args.schedule).assign(draw=r)
                for r in range(args.sim_reps)]
        sim = pd.concat(reps)
        sims[(theta, eps)] = sim
        rows.append({"theta": theta, "eps": eps,
                     "d2": distances(sim, hw, s_r2, s_lr, fit_on),
                     "d2_all": distances(sim, hw, s_r2, s_lr, patterns),
                     **{f"r2_{p}": float(sim[sim.pattern == p].r2_off.mean()) for p in patterns},
                     **{f"lr_{p}": float(sim[sim.pattern == p].log_ratio.mean())
                        for p in patterns}})
        print(f"  theta={theta:<5} eps={eps:<6} d2(fit)={rows[-1]['d2']:8.2f}", flush=True)

    table = pd.DataFrame(rows)
    table["weight"] = abc(table)
    post = {k: float((table[k] * table.weight).sum()) for k in ("theta", "eps")}
    post_sd = {k: float(np.sqrt((table.weight * (table[k] - post[k]) ** 2).sum()))
               for k in ("theta", "eps")}
    best = table.loc[table.d2.idxmin()]

    pred = []
    for p in args.holdout:
        for stat, col, s in (("r2_off", f"r2_{p}", s_r2), ("log_ratio", f"lr_{p}", s_lr)):
            m = float((table[col] * table.weight).sum())
            pred.append({"pattern": p, "statistic": stat, "predicted": m,
                         "hardware": float(hw.loc[p, stat]), "s_window": s,
                         "z": (m - float(hw.loc[p, stat])) / s})

    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "grid.csv", index=False)
    pd.DataFrame(pred).to_csv(out_dir / "predictive_check.csv", index=False)
    print("\n" + table.round(3).to_string(index=False))
    print(f"\nABC posterior (fit on {fit_on}): theta = {post['theta']:.4f} +/- "
          f"{post_sd['theta']:.4f}, eps = {post['eps']:.4f} +/- {post_sd['eps']:.4f}")
    print(f"best grid point: theta = {best.theta}, eps = {best.eps} (d2 = {best.d2:.2f})")
    print("\npredictive check on held-out points:")
    for r in pred:
        print(f"  {r['pattern']:<11} {r['statistic']:<9} predicted {r['predicted']:+.3f} "
              f"hardware {r['hardware']:+.3f}  z = {r['z']:+.2f}")
    print(f"\nwrote {out_dir / 'grid.csv'} and predictive_check.csv")
    print(f"CAVEATS: two hardware windows (crude SD); calibration {args.calibration} predates "
          f"the windows (2026-09-13/15); {args.sim_reps} simulated draw(s) per grid point.")


if __name__ == "__main__":
    main()
