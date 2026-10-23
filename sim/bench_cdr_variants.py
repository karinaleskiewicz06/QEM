"""CDR arms at an equal budget on the device-calibrated simulator.

A port of ``spec/sim_cdr_variants_bench2.py`` onto the campaign modules: targets are
compiled once by ``qem.compile``, training sets are built on the native circuit by
``qem.cdr_training`` (so every training circuit shares the target's CZ skeleton), the
arms and their budgets come from ``qem.arms``, frames from ``qem.twirl``, fits from
``qem.cdr_fit``, and execution from ``sim.device_model``. What the spec script did by
hand -- its own merge, its own near-target sampler, its own fit -- is now the code the
campaign will run.

Arms: ``off_copies``, ``twirl_native``, ``spread``, ``spread_off`` crossed with the
training set ``shared_random`` (the archived behaviour) or ``near_target``.
``twirl_logical`` is not available: it wraps the *logical* circuit before routing, and
training circuits built on the native circuit have no logical form.

Two things differ from the spec script and make its numbers (0.0190 against 0.0357 at
54 CZ, theta = 0.05) not directly comparable: the noise model is pinned to the per-gate
RB/IRB fidelities and includes idle relaxation, and the fixed-layout ladder on Qiskit
2.4.1 puts all_to_all at 57 CZ, not 54.

    python -m sim.bench_cdr_variants --calibration calibrations/odra_raw_20260803.json \\
        --theta 0.05 --phi 0.03 --patterns all_to_all --reps 8
"""

from __future__ import annotations

import argparse
import pathlib
import time

import numpy as np
import pandas as pd
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import perqubit_z_from_counts, readout_observable
from qem.arms import IS_SPREAD, TWIRL_KIND, plan_arm
from qem.cdr_fit import block_variance, fit_both, spread_x_variance
from qem.cdr_training import (build_legacy_shared_training, build_training_set,
                              clifford_ideal_expval)
from qem.compile import compile_native
from qem.twirl import twirl_native_merged
from sim.device_model import DeviceModel, build_noise_model

ARMS = ("off_copies", "twirl_native", "spread", "spread_off")
TRAIN_SETS = ("shared_random", "near_target")
OUT_DIR = pathlib.Path("results_sim/bench_cdr")


def frozen_circuit(pattern: str, models_dir: str = "trained_models_hard"):
    """The frozen classifier for one pattern, weights bound, features free."""
    md = pathlib.Path(models_dir)
    w = np.load(md / f"two_curves_d8_q5_deg8_{pattern}_mean_L3_weights.npy")
    ans = HardwareEfficientAnsatz(5, 3, num_features=8, entanglement=pattern)
    c = ans.build()
    cw = c.assign_parameters(dict(zip(ans.weight_parameters(c), w)))
    return cw, ans.feature_parameters(c)


def _measured(c: QuantumCircuit) -> QuantumCircuit:
    m = c.copy()
    m.measure_all()
    return m


def reference_points(models_dir: str = "trained_models_hard") -> np.ndarray:
    """The frozen evaluation set of the classifier (``X_eval``, 100 points).

    These are draws from the ``two_curves`` data, on which the classifier was trained to
    produce a large margin |<O>| -- about 0.36 on average against 0.21 for features drawn
    uniformly. CDR's error grows with |<O>|, so a benchmark on uniform features tests
    easier circuits than the campaign will run.
    """
    md = pathlib.Path(models_dir)
    return np.load(md / "two_curves_d8_q5_deg8_star_mean_L3_reference.npz")["X_eval"]


def run_rep(dev: DeviceModel, pattern: str, rep: int, *, n_targets: int = 8,
            n_train: int = 10, n_frames: int = 6, shots: int = 8192,
            arms=ARMS, train_sets=TRAIN_SETS, combos=None,
            points: str = "reference",
            models_dir: str = "trained_models_hard") -> list[dict]:
    """One repetition: fresh targets, fresh training sets, fresh frames, all arms.

    Every arm spends ``(n_train + 1) * n_frames * shots`` per target. Returns one row per
    (target, arm, train_set, fit). ``combos`` -- a list of ``(arm, train_set)`` --
    restricts the run to those pairs instead of the full cross. ``points`` is
    ``"reference"`` (repetition ``r`` takes reference points ``r*n_targets ..``, so
    repetitions never share a target) or ``"uniform"`` (features uniform in
    ``[-pi, pi]``, as the spec script did).
    """
    pairs = (list(combos) if combos is not None
             else [(a, ts) for ts in train_sets for a in arms])
    for a, ts in pairs:
        if a not in ARMS:
            raise ValueError(f"arm {a!r} is not available here; expected one of {ARMS}")
        if ts not in TRAIN_SETS:
            raise ValueError(f"unknown training set {ts!r}; expected one of {TRAIN_SETS}")
    train_sets = sorted({ts for _, ts in pairs})
    rng = np.random.default_rng(1000 * rep + 7)
    cw, xp = frozen_circuit(pattern, models_dir)
    if points == "reference":
        ref = reference_points(models_dir)
        lo = rep * n_targets
        if lo + n_targets > len(ref):
            raise ValueError(f"repetition {rep} needs reference points {lo}..{lo + n_targets - 1}; "
                             f"only {len(ref)} exist")
        X = ref[lo:lo + n_targets]
    elif points == "uniform":
        X = rng.uniform(-np.pi, np.pi, (n_targets, len(xp)))
    else:
        raise ValueError(f"points must be 'reference' or 'uniform'; got {points!r}")
    natives = [compile_native(cw.assign_parameters(dict(zip(xp, x)))).circuit for x in X]
    obs = readout_observable(5, "mean")
    coeffs = np.full(5, 0.2)
    ideal_t = [float(np.real(Statevector.from_instruction(t).expectation_value(obs)))
               for t in natives]
    n_cz = natives[0].count_ops().get("cz", 0)

    n_big = n_train * n_frames
    window = f"bench{rep}"
    train = {}
    if "shared_random" in train_sets:
        shared = build_legacy_shared_training(natives, n_train=n_big, base_seed=42 + rep)
        for e in range(n_targets):
            train[("shared_random", e)] = shared[e]
    if "near_target" in train_sets:
        for e, t in enumerate(natives):
            train[("near_target", e)] = build_training_set(
                t, n_train=n_big, sampler="near_target", target_index=e, window_id=window)
    ideal_train = {k: [clifford_ideal_expval(c, obs) for c in v] for k, v in train.items()}

    # assemble every circuit of the repetition, run once
    circs, labels = [], []
    for arm, ts in pairs:
        plan = plan_arm(arm, n_train=n_train, n_frames=n_frames, shots=shots,
                        train_set=ts)
        for e in range(n_targets):
            for spec in plan.specs:
                base = natives[e] if spec.role == "target" else train[(ts, e)][spec.train_index]
                if spec.twirl:
                    base = twirl_native_merged(base, np.random.default_rng(
                        rng.integers(1 << 62))).circuit
                circs.append(_measured(base))
                labels.append((ts, arm, e, spec.role, spec.train_index))
    counts = dev.run(circs, shots, seed=int(rng.integers(1 << 30)))
    vals: dict = {}
    for lab, c in zip(labels, counts):
        vals.setdefault(lab, []).append(float(np.dot(coeffs, perqubit_z_from_counts(c, 5))))

    rows = []
    for arm, ts in pairs:
        for e in range(n_targets):
            tvals = vals[(ts, arm, e, "target", None)]
            t_mean = float(np.mean(tvals))
            n_pts = n_big if IS_SPREAD[arm] else n_train
            xs, vx = [], []
            for i in range(n_pts):
                v = vals[(ts, arm, e, "train", i)]
                xs.append(float(np.mean(v)))
                vx.append(spread_x_variance(xs[-1], 5, shots, tvals) if IS_SPREAD[arm]
                          else block_variance(v))
            ys = ideal_train[(ts, e)][:n_pts]
            for name, fit in fit_both(xs, ys, vx).items():
                rows.append({
                    "theta": dev.theta_zz, "phi": dev.phi_z, "eps": dev.eps_prx,
                    "pattern": pattern, "cz": n_cz, "rep": rep, "target": e,
                    "points": points, "ideal": ideal_t[e],
                    "arm": arm, "train_set": ts, "twirled": TWIRL_KIND[arm] is not None,
                    "fit": name, "err": abs(fit.apply(t_mean) - ideal_t[e]),
                    "err_raw": abs(t_mean - ideal_t[e]), "a": fit.a, "b": fit.b,
                    "r2": fit.r2, "n_points": n_pts})
    return rows


def wins(df: pd.DataFrame, a: tuple[str, str], b: tuple[str, str], fit: str = "ols"):
    """Per repetition: does arm ``a`` have a lower mean error than ``b``?"""
    sel = df[df["fit"] == fit]
    ma = sel[(sel.arm == a[0]) & (sel.train_set == a[1])].groupby("rep")["err"].mean()
    mb = sel[(sel.arm == b[0]) & (sel.train_set == b[1])].groupby("rep")["err"].mean()
    return (ma < mb), ma, mb


def paired_test(df: pd.DataFrame, a: tuple[str, str], b: tuple[str, str],
                fit: str = "ols") -> dict:
    """Is ``a`` better than ``b`` target by target? One-sided, paired.

    Both arms see the same targets in a repetition, so the error difference per
    (rep, target) is a paired observation. With 8 repetitions of 8 targets that is 64
    pairs instead of 8 repetition means, and the reference arm's heavy tail (degenerate
    fits when every training ideal is 0) no longer decides the outcome by itself.

    Returns:
        ``n``, ``n_better`` (pairs where ``a`` has the smaller error), the one-sided
        Wilcoxon signed-rank and sign-test p-values, and both mean errors.
    """
    from scipy.stats import binomtest, wilcoxon
    sel = df[df["fit"] == fit]
    ea = sel[(sel.arm == a[0]) & (sel.train_set == a[1])].set_index(["rep", "target"]).err
    eb = sel[(sel.arm == b[0]) & (sel.train_set == b[1])].set_index(["rep", "target"]).err
    diff = (eb - ea).dropna()
    better = int((diff > 0).sum())
    return {"n": int(len(diff)), "n_better": better,
            "p_wilcoxon": float(wilcoxon(diff, alternative="greater").pvalue),
            "p_sign": float(binomtest(better, len(diff), alternative="greater").pvalue),
            "mean_a": float(ea.mean()), "mean_b": float(eb.mean())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", default="calibrations/odra_raw_20260803.json")
    ap.add_argument("--theta", type=float, default=0.05)
    ap.add_argument("--phi", type=float, default=0.03)
    ap.add_argument("--eps", type=float, default=0.0)
    ap.add_argument("--no-idle", action="store_true")
    ap.add_argument("--gate-t2", choices=["echo", "ramsey"], default="echo")
    ap.add_argument("--schedule", choices=["alap", "asap"], default="alap")
    ap.add_argument("--patterns", nargs="+", default=["star", "linear", "circular", "all_to_all"])
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--rep0", type=int, default=0)
    ap.add_argument("--targets", type=int, default=8)
    ap.add_argument("--n-train", type=int, default=10)
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    ap.add_argument("--train-sets", nargs="+", default=list(TRAIN_SETS), choices=TRAIN_SETS)
    ap.add_argument("--points", choices=["reference", "uniform"], default="reference",
                    help="targets from the classifier's evaluation set, or uniform features")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    dev = build_noise_model(args.calibration, args.theta, args.phi, args.eps,
                            with_idle=not args.no_idle, gate_t2=args.gate_t2,
                            schedule=args.schedule)
    print(dev.describe())
    out = pathlib.Path(args.out or OUT_DIR / f"{dev.tag}_{args.points}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, t0 = [], time.time()
    for pattern in args.patterns:
        for rep in range(args.rep0, args.rep0 + args.reps):
            rows += run_rep(dev, pattern, rep, n_targets=args.targets, n_train=args.n_train,
                            n_frames=args.frames, shots=args.shots, arms=args.arms,
                            train_sets=args.train_sets, points=args.points)
            pd.DataFrame(rows).to_csv(out, index=False)
            print(f"  {pattern} rep {rep} cz={rows[-1]['cz']} {time.time() - t0:.0f}s", flush=True)

    df = pd.DataFrame(rows)
    summ = (df[df.fit == "ols"].groupby(["pattern", "cz", "arm", "train_set"])["err"]
            .mean().unstack(["arm"]).round(4))
    print("\nmean |error| (OLS) by arm:\n", summ.to_string())
    if {"spread", "twirl_native"} <= set(args.arms) and set(TRAIN_SETS) <= set(args.train_sets):
        for pattern in args.patterns:
            w, ma, mb = wins(df[df.pattern == pattern], ("spread", "near_target"),
                             ("twirl_native", "shared_random"))
            t = paired_test(df[df.pattern == pattern], ("spread", "near_target"),
                            ("twirl_native", "shared_random"))
            print(f"{pattern}: spread+near_target beats twirl_native+shared_random in "
                  f"{int(w.sum())}/{len(w)} reps ({ma.mean():.4f} vs {mb.mean():.4f}); "
                  f"per target {t['n_better']}/{t['n']}, Wilcoxon p = {t['p_wilcoxon']:.2g}, "
                  f"sign p = {t['p_sign']:.2g}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
