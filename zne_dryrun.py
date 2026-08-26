"""End-to-end DD+REM+ZNE experiment over the routing ladder (Month-1 go/no-go).

Full baseline-hygiene + mitigation pipeline per routing level (plan.md §7):
  routed circuit (native {r,cz})
    -> idle schedule (id windows carry thermal noise)
    -> Dynamical Decoupling (idle decoheres at Hahn-echo T2, not Ramsey T2*)
    -> unitary folding at scale factors [1,3,5]
    -> noisy execution
    -> Readout Error Mitigation (per-qubit, exact for Z observables)
    -> Zero-Noise Extrapolation (linear / Richardson / exponential).

Reports an ABLATION so each layer's contribution is visible, all vs the exact
noiseless ⟨O⟩ of that level's circuit (statevector):
  * raw    : no DD, no REM, no ZNE (scale-1)
  * ddrem  : DD + REM, no ZNE (scale-1)   <- baseline hygiene
  * zne    : DD + REM + ZNE                <- full pipeline

PRIMARY metric = mean |⟨O⟩ - ⟨O⟩_ideal| over the frozen eval subset (accuracy
secondary). With --reps R>1 each metric gets a mean +/- std error band over R
independent shot-noise realizations (plan.md: report bands, not point values).

ZNE is in-repo (no mitiq dependency):
  * unitary folding -- Giurgica-Tiron et al., arXiv:2005.10921 (odd scales 1,3,5)
  * Richardson / linear / exponential extrapolation -- Temme et al., PRL 119 (2017)

METHODOLOGY: each routing level uses its OWN classifier (train_patterns.py) at
matched trainable capacity. DD is modelled as idle dephasing improving from the
measured Ramsey T2* to the measured Hahn-echo T2 (a Markovian T2 channel cannot
be refocused by pulses in sim; the echo value is the physical DD ceiling).

Usage:
  python train_patterns.py                              # per-pattern classifiers
  python collect_odra_calibration.py --num-qubits 5     # live ODRA calibration
  python zne_dryrun.py --calibration calibrations/odra.json
  python zne_dryrun.py --calibration calibrations/odra.json --quick
  python zne_dryrun.py --no-dd --no-rem                 # ablation: ZNE only
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import SparsePauliOp, Statevector

from ansatz import HardwareEfficientAnsatz
from metrics import macro_f1
from noisy_sim import (
    DeviceCalibration,
    IQM_BASIS_GATES,
    execute_expectation,
    load_iqm_calibration,
    make_noisy_simulator,
    observable_coeffs,
    readout_observable,
    star_coupling_map,
)

SCALE_FACTORS = [1, 3, 5]
LADDER_PATTERNS = ["star", "linear", "circular", "all_to_all"]
OUT_CSV = pathlib.Path("zne_dryrun_results.csv")


# --------------------------------------------------------------------------- #
# ZNE primitives (in-repo)                                                      #
# --------------------------------------------------------------------------- #

def fold_global(native_circ: QuantumCircuit, scale: int) -> QuantumCircuit:
    """Global unitary folding U -> U (U^dag U)^k for odd scale=2k+1.

    Barriers separate copies so the U^dag U pairs are NOT optimised away.
    Input/output are measurement-free native circuits.
    """
    if scale < 1 or scale % 2 == 0:
        raise ValueError("scale must be a positive odd integer (1,3,5,...)")
    k = (scale - 1) // 2
    out = native_circ.copy()
    inv = native_circ.inverse()
    for _ in range(k):
        out.barrier()
        out = out.compose(inv)
        out.barrier()
        out = out.compose(native_circ)
    return out


# A mean-Z / hub-Z observable is bounded in [-1, 1]; a sane zero-noise estimate
# should not stray far outside. Estimates beyond this are extrapolation failures.
_EV_BOUND = 1.25


def _clamped(value: float, fallback: float) -> float:
    """Reject blown-up extrapolations (breakdown) -> use the linear fallback."""
    if not np.isfinite(value) or abs(value) > _EV_BOUND:
        return fallback
    return value


def extrapolate(scales, values, kind: str) -> float:
    """Zero-noise extrapolation. kind in {linear, richardson, exponential}.

    Non-linear fits are clamped to a physically plausible range; a blow-up
    (|estimate| > 1.25 or non-finite) is itself a breakdown indicator and we
    fall back to the linear estimate so one bad point does not corrupt the mean.
    """
    x = np.asarray(scales, float)
    y = np.asarray(values, float)
    linear = float(np.polyval(np.polyfit(x, y, 1), 0.0))
    if kind == "linear":
        return linear
    if kind == "richardson":
        c = np.polyfit(x, y, len(x) - 1)  # exact poly through all points
        return _clamped(float(np.polyval(c, 0.0)), linear)
    if kind == "exponential":
        from scipy.optimize import curve_fit
        try:
            p, _ = curve_fit(
                lambda t, a, b, c: a + b * np.exp(-c * t),
                x, y, p0=[y[-1], y[0] - y[-1], 0.5], maxfev=20000,
            )
            return _clamped(float(p[0] + p[1]), linear)  # value at t=0
        except Exception:
            return linear
    raise ValueError(f"unknown extrapolation {kind!r}")


# --------------------------------------------------------------------------- #
# Level construction                                                            #
# --------------------------------------------------------------------------- #

def build_level_circuit(cfg: dict, pattern: str) -> tuple[QuantumCircuit, list]:
    """HEA at the locked (n,L) with a given entangling pattern; return (circ, x-params)."""
    ans = HardwareEfficientAnsatz(
        cfg["n_qubits"], cfg["n_layers"],
        num_features=cfg["n_features"], entanglement=pattern,
        entangling_gate=cfg.get("entangling_gate", "cx"),
    )
    circ = ans.build()
    xparams = ans.feature_parameters(circ)   # only x[...] params, sorted
    return circ, xparams, ans


def native_transpile(circ: QuantumCircuit, n: int) -> QuantumCircuit:
    return transpile(circ, basis_gates=IQM_BASIS_GATES,
                     coupling_map=star_coupling_map(n), optimization_level=1)


def exact_ev(circ: QuantumCircuit, observable) -> float:
    return float(np.real(Statevector.from_instruction(circ).expectation_value(observable)))


# --------------------------------------------------------------------------- #
# Main pilot                                                                    #
# --------------------------------------------------------------------------- #

def _measure_scales(native, observable, sim, shots, cal, rem):
    """Fold at each SCALE_FACTOR and return the list of noisy ⟨O⟩ (with REM)."""
    vals = []
    for s in SCALE_FACTORS:
        folded = fold_global(native, s)
        vals.append(execute_expectation(
            folded, observable, sim, shots=shots,
            cal=cal, apply_idle_schedule=True, pre_transpiled=True, rem=rem,
        ))
    return vals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="6 pts, 2 patterns")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--reps", type=int, default=3,
                    help="independent shot-noise realizations for error bands")
    ap.add_argument("--calibration", default="",
                    help="calibration JSON (default: placeholder DeviceCalibration)")
    dd = ap.add_mutually_exclusive_group()
    dd.add_argument("--dd", dest="dd", action="store_true", help="DD on (default)")
    dd.add_argument("--no-dd", dest="dd", action="store_false")
    rem = ap.add_mutually_exclusive_group()
    rem.add_argument("--rem", dest="rem", action="store_true", help="REM on (default)")
    rem.add_argument("--no-rem", dest="rem", action="store_false")
    ap.set_defaults(dd=True, rem=True)
    ap.add_argument("--models-dir", default="trained_models",
                    help="model directory (trained_models_hard for the hard config)")
    ap.add_argument("--out", default=str(OUT_CSV))
    args = ap.parse_args()

    # locked model + frozen reference
    from noisy_sim import load_frozen_model
    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(pathlib.Path(args.models_dir) / f"{tag}_reference.npz")
    X_eval, y_eval = ref["X_eval"], ref["y_eval"]
    star_weights = np.load(pathlib.Path(args.models_dir) / cfg["weights_file"])

    def weights_for(pattern: str) -> tuple[np.ndarray, bool]:
        """Per-pattern weights; (weights, per_pattern?) with star fallback."""
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wpath = pathlib.Path(args.models_dir) / f"{ptag}_weights.npy"
        if wpath.exists():
            return np.load(wpath), True
        print(f"  [warn] no per-pattern weights for {pattern!r} "
              f"({wpath.name}); falling back to locked star weights")
        return star_weights, False

    patterns = ["star", "all_to_all"] if args.quick else LADDER_PATTERNS
    if args.quick:
        X_eval, y_eval = X_eval[:6], y_eval[:6]

    if args.calibration:
        cal = load_iqm_calibration(args.calibration)
        cal_src = args.calibration
    else:
        cal = DeviceCalibration()
        cal_src = "PLACEHOLDER (pass --calibration calibrations/odra.json)"

    # sim_raw: unprotected idle (T2*); sim_hyg: DD -> echo T2 for idle
    sim_raw = make_noisy_simulator(cal, dd=False)
    sim_hyg = make_noisy_simulator(cal, dd=args.dd)

    print(f"DD+REM+ZNE experiment | model {tag}")
    print(f"  calibration : {cal_src}")
    print(f"  eval points : {len(X_eval)} | patterns {patterns}")
    print(f"  scales {SCALE_FACTORS} | shots {args.shots} | reps {args.reps}")
    print(f"  hygiene     : DD={'on' if args.dd else 'OFF'}  "
          f"REM={'on' if args.rem else 'OFF'}")
    print("  metric = mean |<O> - <O>_ideal|; ablation raw -> DD+REM -> +ZNE\n")

    rows = []
    for pattern in patterns:
        weights, per_pattern = weights_for(pattern)
        circ, xparams, ans = build_level_circuit(cfg, pattern)
        wparams = ans.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, weights)))

        # transpiled 2q cost of this level (x-independent)
        tq = native_transpile(circ_w.assign_parameters({p: 0.0 for p in xparams}), n)
        n2q = sum(1 for i in tq.data if i.operation.name == "cz")

        # precompute ideal ⟨O⟩ and native circuits once (reused across reps)
        ideal_evs, natives = [], []
        for x in X_eval:
            bound = circ_w.assign_parameters(dict(zip(xparams, x)))
            ideal_evs.append(exact_ev(bound, observable))
            natives.append(native_transpile(bound, n))
        ideal_evs = np.asarray(ideal_evs)

        metrics = ["raw", "ddrem", "zne_linear", "zne_richardson", "zne_exp"]
        per_rep_err = {m: [] for m in metrics}
        per_rep_acc = {"raw": [], "ddrem": [], "zne_richardson": []}
        per_rep_f1 = {"raw": [], "ddrem": [], "zne_richardson": []}

        for _rep in range(args.reps):
            err = {m: [] for m in metrics}
            pred = {"raw": [], "ddrem": [], "zne_richardson": []}
            for i, native in enumerate(natives):
                ideal = ideal_evs[i]
                # raw baseline: no DD, no REM
                raw = execute_expectation(
                    native, observable, sim_raw, shots=args.shots,
                    cal=cal, apply_idle_schedule=True, pre_transpiled=True, rem=False,
                )
                # hygiene + folding: DD sim + REM
                vals = _measure_scales(native, observable, sim_hyg, args.shots,
                                       cal, args.rem)
                ddrem = vals[0]  # scale 1 = DD+REM, no ZNE
                zlin = extrapolate(SCALE_FACTORS, vals, "linear")
                zrich = extrapolate(SCALE_FACTORS, vals, "richardson")
                zexp = extrapolate(SCALE_FACTORS, vals, "exponential")

                err["raw"].append(abs(raw - ideal))
                err["ddrem"].append(abs(ddrem - ideal))
                err["zne_linear"].append(abs(zlin - ideal))
                err["zne_richardson"].append(abs(zrich - ideal))
                err["zne_exp"].append(abs(zexp - ideal))
                pred["raw"].append(np.sign(raw))
                pred["ddrem"].append(np.sign(ddrem))
                pred["zne_richardson"].append(np.sign(zrich))

            for m in metrics:
                per_rep_err[m].append(float(np.mean(err[m])))
            for k in per_rep_acc:
                per_rep_acc[k].append(float(np.mean(np.array(pred[k]) == y_eval)))
                per_rep_f1[k].append(macro_f1(y_eval, pred[k]))

        def ms(vals):  # mean, std across reps
            a = np.asarray(vals)
            return round(float(a.mean()), 4), round(float(a.std()), 4)

        raw_m, raw_s = ms(per_rep_err["raw"])
        dd_m, dd_s = ms(per_rep_err["ddrem"])
        lin_m, _ = ms(per_rep_err["zne_linear"])
        rich_m, rich_s = ms(per_rep_err["zne_richardson"])
        exp_m, _ = ms(per_rep_err["zne_exp"])
        arw, _ = ms(per_rep_acc["raw"])
        add, _ = ms(per_rep_acc["ddrem"])
        arich, _ = ms(per_rep_acc["zne_richardson"])
        f1rw, _ = ms(per_rep_f1["raw"])
        f1dd, _ = ms(per_rep_f1["ddrem"])
        f1rich, _ = ms(per_rep_f1["zne_richardson"])

        row = {
            "pattern": pattern,
            "per_pattern_weights": per_pattern,
            "transpiled_cz": n2q,
            "mean_ideal_abs": round(float(np.mean(np.abs(ideal_evs))), 4),
            "raw_err": raw_m, "raw_err_std": raw_s,
            "ddrem_err": dd_m, "ddrem_err_std": dd_s,
            "zne_linear_err": lin_m,
            "zne_richardson_err": rich_m, "zne_richardson_err_std": rich_s,
            "zne_exp_err": exp_m,
            "acc_raw": arw, "acc_ddrem": add, "acc_zne_richardson": arich,
            "f1_raw": f1rw, "f1_ddrem": f1dd, "f1_zne_richardson": f1rich,
            "dd": args.dd, "rem": args.rem,
            "reps": args.reps, "n_points": len(X_eval), "shots": args.shots,
        }
        rows.append(row)
        print(f"  {pattern:>11} | 2q={n2q:>3} | "
              f"raw={raw_m:.3f}±{raw_s:.3f} -> "
              f"DD+REM={dd_m:.3f}±{dd_s:.3f} -> "
              f"ZNE(rich)={rich_m:.3f}±{rich_s:.3f} (exp={exp_m:.3f}) | "
              f"acc {arw:.2f}->{add:.2f}->{arich:.2f} | "
              f"F1 {f1rw:.2f}->{f1dd:.2f}->{f1rich:.2f}")

    rows.sort(key=lambda r: r["transpiled_cz"])
    fields = list(rows[0].keys())
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"\nwrote {args.out}")
    print("y-axis = mean ⟨O⟩ error vs transpiled 2q cost; layers: raw -> DD+REM -> +ZNE.")
    print("Breakdown = where +ZNE stops beating DD+REM or error bands overlap / residuals blow up.")


if __name__ == "__main__":
    main()
