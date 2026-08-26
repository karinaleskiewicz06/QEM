"""Full, methodologically-correct k-fold cross-validation for the banknote VQCs.

Runs on the ODRA-calibrated NOISY SIMULATOR (no token needed) so the entire CV is
reproducible offline, and mirrors the exact protocol used for the QPU 5-fold check
in the report.

Why this is methodologically correct
-------------------------------------
For every (ansatz, depth) it sweeps all K folds, and for each fold it uses THAT
FOLD'S OWN trained weights -- fit by the upstream project on ``fold_f/train_data.csv``
-- evaluated on ``fold_f/test_data.csv``. Because the train/test split is disjoint
per fold, no evaluation point is ever scored with weights that were trained on it
(no data leakage). The full test fold is used by default (natural 153/122 class
imbalance, 0.556 majority floor), which is the only setting in which macro-F1 can
expose majority-class collapse. Results are aggregated as mean +/- BETWEEN-FOLD
standard deviation (ddof=1), which is the paper's reporting convention and the one
used for tab.~bank-qpu-cv in the report.

Mitigation ladder (per point): ideal (noiseless statevector) -> raw (noisy, no
mitigation) -> +REM -> +REM+ZNE (Richardson over scale factors [1,3,5]). DD is OFF
by default -- the report's headline pipeline is REM+ZNE, because DD adds coherent
error on IQM Spark; pass --dd to fold DD into the +REM/+ZNE rungs (reproduces the
original ``run_zne_banknote`` behaviour).

Outputs
-------
  * per-fold CSV   (--out):        one row per (ansatz, depth, fold) -- the raw material
  * summary  CSV   (--summary-out): one row per (ansatz, depth) -- mean +/- fold std

Usage (from the QEM project root)
---------------------------------
  # full CV: 3 ansatze x {2,4,6} x 5 folds, full test fold, DD off (canonical, slow):
  python banknote_study/run_cv_banknote.py

  # scoped: only the L=6 ring ansatze whose collapse the paper reports:
  python banknote_study/run_cv_banknote.py --ansatze odra simulator --depths 6

  # re-aggregate an EXISTING per-fold CSV (e.g. the real QPU run) into a summary,
  # using the identical mean+/-std protocol -- no simulation performed:
  python banknote_study/run_cv_banknote.py \
      --aggregate-csv banknote_study/banknote_hardware_cv_d6.csv \
      --summary-out banknote_study/banknote_hardware_cv_d6_summary.csv

Runtime note: the full default run is ~3*3*5*275*4 noisy-shot simulations and can
take on the order of an hour. Scope it with --ansatze/--depths/--folds/--n-samples
for quick checks.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import numpy as np

QEM_ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = QEM_ROOT / "banknote_study" / "upstream"
sys.path.insert(0, str(QEM_ROOT))
sys.path.insert(0, str(UPSTREAM / "src"))

import torch  # noqa: E402

from banknote_study.run_zne_banknote import (  # noqa: E402
    MODEL_DIRNAME, READOUT_QUBIT, build_full_circuit, load_eval_subset, zobs,
)
from noisy_sim import (  # noqa: E402
    execute_expectation, load_iqm_calibration, make_noisy_simulator,
)
from zne_dryrun import (  # noqa: E402
    SCALE_FACTORS, exact_ev, extrapolate, fold_global, native_transpile,
)

N_QUBITS = 5
LADDER = ("raw", "rem", "zne")  # rungs carrying acc / f1 / <O>-error


def macro_f1(pred, y) -> float:
    """Unweighted mean of the two per-class F1 scores (paper's headline metric).

    Drops toward 0 when a class stops being predicted -- the majority-class
    collapse the KN-Axion paper reports for ring ansatze at depth 6. Identical to
    the definition in ``run_hardware_banknote.py`` so sim and QPU CV are comparable.
    """
    pred = np.asarray(pred); y = np.asarray(y)
    f1s = []
    for cls in (-1.0, 1.0):
        tp = float(np.sum((pred == cls) & (y == cls)))
        fp = float(np.sum((pred == cls) & (y != cls)))
        fn = float(np.sum((pred != cls) & (y == cls)))
        denom = 2 * tp + fp + fn
        f1s.append(2 * tp / denom if denom else 0.0)
    return float(np.mean(f1s))


def load_weights_cv(name: str, depth: int, fold: int, epoch: int, noise: bool) -> np.ndarray:
    """Per-fold trained weights (fit on ``fold_f/train_data.csv``).

    Supports both the clean checkpoints and the noise-aware (``_noise_``) ones.
    """
    model = MODEL_DIRNAME[name]
    tag = "_noise" if noise else ""
    path = (UPSTREAM / "cross_validation" / "Models" / "Weights" / f"depth {depth}"
            / model / f"fold_{fold}"
            / f"{model}_fold_{fold}_depth_{depth}{tag}_epoch_{epoch}_weights.pth")
    if not path.exists():
        raise FileNotFoundError(path)
    sd = torch.load(path, map_location="cpu", weights_only=False)
    for key in ("quantum_layer._weights", "quantum_layer.weight", "_weights"):
        if key in sd:
            return np.asarray(sd[key].detach().cpu().numpy(), dtype=float)
    raise KeyError(f"no weight tensor in {path} (keys: {list(sd.keys())})")


def eval_ansatz_fold(name, depth, fold, X, y, cal, sim_raw, sim_mit,
                     shots, reps, epoch, noise) -> dict:
    """Evaluate one (ansatz, depth) on one fold's held-out test set.

    Returns fold-level metrics for the raw/+REM/+ZNE rungs (accuracy, macro-F1 and
    mean |<O>-error| vs the noiseless ideal), each averaged over ``reps`` shot draws.
    """
    n = N_QUBITS
    full, xparams, wparams = build_full_circuit(name, n, depth)
    weights = load_weights_cv(name, depth, fold, epoch, noise)
    if len(weights) != len(wparams):
        raise ValueError(f"{name} d{depth} f{fold}: {len(weights)} weights "
                         f"!= {len(wparams)} params")
    circ_w = full.assign_parameters(dict(zip(wparams, weights)))
    mq = READOUT_QUBIT[name]

    # deterministic per-point precompute: noiseless ideal, transpiled native, and
    # the PHYSICAL wire that holds logical readout qubit `mq` after routing (the
    # star hub lands off wire 0; a no-op for odra/simulator).
    ideal, natives, readwire = [], [], []
    n2q = 0
    for x in X:
        bound = circ_w.assign_parameters(dict(zip(xparams, x)))
        ideal.append(exact_ev(bound, zobs(n, mq)))
        native = native_transpile(bound, n)
        readwire.append(native.layout.final_index_layout()[mq])
        natives.append(native)
        n2q = sum(1 for i in native.data if i.operation.name == "cz")
    ideal = np.asarray(ideal)

    rep = {f"{m}_{r}": [] for m in ("acc", "f1", "err") for r in LADDER}
    for _ in range(reps):
        raw_ev, rem_ev, zne_ev = [], [], []
        for native, rw in zip(natives, readwire):
            obs = zobs(n, rw)
            raw_ev.append(execute_expectation(
                fold_global(native, 1), obs, sim_raw, shots=shots, cal=cal,
                apply_idle_schedule=True, pre_transpiled=True, rem=False))
            vals = [execute_expectation(
                fold_global(native, s), obs, sim_mit, shots=shots, cal=cal,
                apply_idle_schedule=True, pre_transpiled=True, rem=True)
                for s in SCALE_FACTORS]
            rem_ev.append(vals[0])
            zne_ev.append(extrapolate(SCALE_FACTORS, vals, "richardson"))
        for r, ev in (("raw", raw_ev), ("rem", rem_ev), ("zne", zne_ev)):
            ev = np.asarray(ev)
            rep[f"acc_{r}"].append(float(np.mean(np.sign(ev) == y)))
            rep[f"f1_{r}"].append(macro_f1(np.sign(ev), y))
            rep[f"err_{r}"].append(float(np.mean(np.abs(ev - ideal))))

    out = {
        "ansatz": name, "depth": depth, "fold": fold,
        "readout_qubit": mq, "transpiled_cz": n2q, "n_points": len(y),
        "acc_ideal": round(float(np.mean(np.sign(ideal) == y)), 4),
        "f1_ideal": round(macro_f1(np.sign(ideal), y), 4),
    }
    for k, v in rep.items():
        out[k] = round(float(np.mean(v)), 4)
    return out


# --------------------------------------------------------------------------- #
# Aggregation (shared by sim CV and by --aggregate-csv on the QPU per-fold CSV) #
# --------------------------------------------------------------------------- #
_NON_METRIC = {"fold", "n_points", "shots", "reps", "readout_qubit", "job_ids"}


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def aggregate_rows(rows: list[dict], ddof: int) -> list[dict]:
    """Group per-fold rows by (ansatz, depth[, dd]) and report mean +/- fold std.

    Generic over the metric columns present, so it aggregates BOTH this script's
    sim output and the QPU per-fold CSV (``banknote_hardware_cv_d6.csv``) with the
    same code path. ``ddof=1`` gives the sample (between-fold) std used in the report.
    """
    if not rows:
        return []
    cols = list(rows[0].keys())
    has_dd = "dd" in cols
    # skip per-fold std columns (e.g. raw_err_std): the summary reports the
    # BETWEEN-FOLD std of each mean, not the mean of within-fold stds.
    metric_cols = [c for c in cols
                   if c not in _NON_METRIC and c not in ("ansatz", "depth", "dd")
                   and not c.endswith("_std")
                   and all(_is_number(r.get(c, "")) for r in rows)]

    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        key = (r["ansatz"], int(float(r["depth"])),
               (str(r["dd"]).lower() in ("true", "1")) if has_dd else None)
        groups.setdefault(key, []).append(r)

    summary = []
    for (ansatz, depth, dd), grp in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        agg = {"ansatz": ansatz, "depth": depth, "n_folds": len(grp)}
        if has_dd:
            agg["dd"] = dd
        for c in metric_cols:
            vals = np.asarray([float(r[c]) for r in grp])
            agg[f"{c}_mean"] = round(float(vals.mean()), 4)
            agg[f"{c}_std"] = round(float(vals.std(ddof=ddof)) if len(vals) > ddof else 0.0, 4)
        summary.append(agg)
    return summary


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ansatze", nargs="+", default=["star", "odra", "simulator"],
                    choices=["star", "odra", "simulator"])
    ap.add_argument("--depths", type=int, nargs="+", default=[2, 4, 6], choices=(2, 4, 6))
    ap.add_argument("--folds", type=int, nargs="+", default=[1, 2, 3, 4, 5],
                    choices=(1, 2, 3, 4, 5))
    ap.add_argument("--epoch", type=int, default=30, choices=(20, 30))
    ap.add_argument("--noise-weights", action="store_true",
                    help="use the noise-aware (_noise_) checkpoints instead of clean")
    ap.add_argument("--n-samples", type=int, default=0,
                    help="test-subset size per fold; 0 = FULL fold (default, keeps "
                         "the natural class imbalance so macro-F1 is meaningful)")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--reps", type=int, default=1,
                    help="shot-draw repetitions averaged per fold (between-fold std "
                         "is the primary uncertainty; >1 only adds shot-noise bands)")
    ap.add_argument("--dd", dest="dd", action="store_true",
                    help="fold DD into the +REM/+ZNE rungs (default: DD off, the "
                         "report's REM+ZNE headline)")
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ddof", type=int, default=1,
                    help="delta-dof for the between-fold std (1 = sample std, report")
    ap.add_argument("--out", default="banknote_study/banknote_cv_sim.csv",
                    help="per-fold CSV output")
    ap.add_argument("--summary-out", default="banknote_study/banknote_cv_sim_summary.csv",
                    help="aggregated (mean +/- fold std) CSV output")
    ap.add_argument("--aggregate-csv", default=None,
                    help="skip simulation; just aggregate this existing per-fold CSV "
                         "into --summary-out (use for the QPU CV CSV)")
    args = ap.parse_args()

    # ---- aggregate-only mode: reuse the exact protocol on an existing CSV -----
    if args.aggregate_csv:
        src = pathlib.Path(args.aggregate_csv)
        rows = list(csv.DictReader(open(src)))
        summary = aggregate_rows(rows, args.ddof)
        out = pathlib.Path(args.summary_out)
        write_csv(out, summary)
        print(f"aggregated {len(rows)} per-fold rows from {src}")
        for s in summary:
            dd = f" dd={s['dd']}" if "dd" in s else ""
            acc_std = s.get("acc_raw_std", s.get("acc_zne_richardson_std", 0.0))
            print(f"  {s['ansatz']:>10} d{s['depth']}{dd} (n={s['n_folds']}): "
                  f"acc_raw={s.get('acc_raw_mean','?')}+/-{acc_std}")
        print(f"\nwrote {out}")
        return

    # ---- full simulator CV ----------------------------------------------------
    cal = load_iqm_calibration(str(QEM_ROOT / args.calibration))
    sim_raw = make_noisy_simulator(cal, dd=False)          # raw rung: unmitigated, DD off
    sim_mit = make_noisy_simulator(cal, dd=args.dd)        # +REM/+ZNE rung
    dd_label = "on" if args.dd else "off"

    print("=" * 78)
    print(f"BANKNOTE k-fold CV (noisy sim) | ansatze={args.ansatze} "
          f"depths={args.depths} folds={args.folds}")
    print(f"  epoch={args.epoch}{' noise' if args.noise_weights else ''} "
          f"n_samples={'FULL fold' if args.n_samples <= 0 else args.n_samples} "
          f"shots={args.shots} reps={args.reps} DD(+REM/ZNE)={dd_label}")
    print(f"  per-fold weights on held-out test set (no leakage); "
          f"summary = mean +/- fold std (ddof={args.ddof})")
    print("=" * 78)

    perfold: list[dict] = []
    for fold in args.folds:
        X, y = load_eval_subset(fold, args.n_samples, args.seed)
        for depth in args.depths:
            for name in args.ansatze:
                row = eval_ansatz_fold(name, depth, fold, X, y, cal, sim_raw,
                                       sim_mit, args.shots, args.reps,
                                       args.epoch, args.noise_weights)
                row["shots"] = args.shots
                row["reps"] = args.reps
                row["dd"] = args.dd
                perfold.append(row)
                print(f"  f{fold} d{depth} {name:>10} 2q={row['transpiled_cz']:>3} | "
                      f"acc ideal={row['acc_ideal']:.2f} raw={row['acc_raw']:.2f} "
                      f"+REM={row['acc_rem']:.2f} +ZNE={row['acc_zne']:.2f} | "
                      f"F1 raw={row['f1_raw']:.2f} +ZNE={row['f1_zne']:.2f} | "
                      f"<O>err raw={row['err_raw']:.3f}->ZNE={row['err_zne']:.3f}")

    out = QEM_ROOT / args.out
    write_csv(out, perfold)
    summary = aggregate_rows(perfold, args.ddof)
    sout = QEM_ROOT / args.summary_out
    write_csv(sout, summary)

    print("\n" + "=" * 78)
    print("CROSS-VALIDATION SUMMARY (mean +/- between-fold std)")
    print("=" * 78)
    for s in summary:
        print(f"  {s['ansatz']:>10} d{s['depth']} (n={s['n_folds']}, "
              f"CZ~{s['transpiled_cz_mean']:.0f}): "
              f"acc raw={s['acc_raw_mean']}+/-{s['acc_raw_std']} "
              f"ZNE={s['acc_zne_mean']}+/-{s['acc_zne_std']} | "
              f"F1 raw={s['f1_raw_mean']}+/-{s['f1_raw_std']} "
              f"ZNE={s['f1_zne_mean']}+/-{s['f1_zne_std']}")
    print(f"\nwrote per-fold: {out}\nwrote summary : {sout}")


if __name__ == "__main__":
    main()
