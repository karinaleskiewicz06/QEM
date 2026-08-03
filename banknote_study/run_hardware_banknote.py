"""Run the 3 banknote ansatze (star/odra/simulator) on real ODRA hardware.

Hardware analogue of ``run_zne_banknote.py``: same circuits, same raw -> +REM ->
+REM+ZNE ablation, but executed on the device via iqm-client (reusing the
submit/fetch/retry/convert helpers from the two_curves ``run_hardware.py``).

The three ansatze are a routing-cost ladder at fixed noiseless accuracy (~0.88),
so this measures whether QEM recovers accuracy as transpiled CZ grows -- and where
recovery breaks down. Readout is a single Z on each ansatz's trained qubit; because
the transpiler permutes qubits, we read the PHYSICAL wire that holds that logical
qubit after routing (fil[mq]), which is the same fix applied in the simulator study.

SAFETY (identical staging to run_hardware.py):
  default --dry-run : build + validate all IQM circuits locally, submit NOTHING.
  --submit          : execute on the device (needs IQM_SERVER_URL + IQM_TOKEN).
  --dd-ablation     : run each batch twice (DD off / DD on).
  --resume          : skip (ansatz,DD) combos already in the CSV (crash recovery).

Usage:
  python banknote_study/run_hardware_banknote.py --dry-run --depth 4
  python banknote_study/run_hardware_banknote.py --submit --depth 4 --dd-ablation
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys
import time

import numpy as np

QEM_ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = QEM_ROOT / "banknote_study" / "upstream"
sys.path.insert(0, str(QEM_ROOT))
sys.path.insert(0, str(UPSTREAM / "src"))

from banknote_study.run_zne_banknote import (  # noqa: E402
    READOUT_QUBIT, build_full_circuit, load_eval_subset, load_weights, zobs,
)
from noisy_sim import load_iqm_calibration, rem_correct_z  # noqa: E402
from run_hardware import (  # noqa: E402
    PHYS, fetch_counts, perqubit_z_iqm, qiskit_to_iqm, submit_batch,
)
from zne_dryrun import SCALE_FACTORS, exact_ev, extrapolate, fold_global, native_transpile  # noqa: E402


def macro_f1(pred, y) -> float:
    """Unweighted mean of the two per-class F1 scores (paper's headline metric).

    Accuracy on a balanced subset hides majority-class collapse; macro-F1 drops
    toward 0 when a class stops being predicted, which is exactly the failure the
    KN-Axion paper reports for the ring ansatze at depth 6.
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


def evaluate(counts_list, per_circ, ideal, readwire, p_ro, n):
    """raw -> +REM -> +REM+ZNE from a batch's counts (per-point readout wire)."""
    by_point: dict[int, dict[int, np.ndarray]] = {}
    for (pi, s), counts in zip(per_circ, counts_list):
        by_point.setdefault(pi, {})[s] = perqubit_z_iqm(counts, n)
    err = {"raw": [], "rem": [], "zne_linear": [], "zne_richardson": [], "zne_exp": []}
    pred = {"raw": [], "rem": [], "zne_richardson": []}
    for pi, sv in by_point.items():
        rw = readwire[pi]
        raw1 = sv[SCALE_FACTORS[0]][rw]
        rem_vals = [rem_correct_z(sv[s], p_ro)[rw] for s in SCALE_FACTORS]
        err["raw"].append(abs(raw1 - ideal[pi]))
        err["rem"].append(abs(rem_vals[0] - ideal[pi]))
        err["zne_linear"].append(abs(extrapolate(SCALE_FACTORS, rem_vals, "linear") - ideal[pi]))
        zr = extrapolate(SCALE_FACTORS, rem_vals, "richardson")
        err["zne_richardson"].append(abs(zr - ideal[pi]))
        err["zne_exp"].append(abs(extrapolate(SCALE_FACTORS, rem_vals, "exponential") - ideal[pi]))
        pred["raw"].append(np.sign(raw1))
        pred["rem"].append(np.sign(rem_vals[0]))
        pred["zne_richardson"].append(np.sign(zr))
    return err, pred


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    m = ap.add_mutually_exclusive_group()
    m.add_argument("--dry-run", dest="submit", action="store_false")
    m.add_argument("--submit", dest="submit", action="store_true")
    ap.set_defaults(submit=False)
    ap.add_argument("--ansatze", nargs="+", default=["star", "odra", "simulator"])
    ap.add_argument("--depths", type=int, nargs="+", default=[2, 4, 6],
                    choices=(2, 4, 6), help="sweep these ansatz depths in one run")
    ap.add_argument("--fold", type=int, default=1)
    ap.add_argument("--folds", type=int, nargs="+", default=None,
                    help="sweep these CV folds in one run (each has its own test set "
                         "and trained weights); overrides --fold. Use for the L=6 "
                         "5-fold check where the paper reports ring collapse.")
    ap.add_argument("--epoch", type=int, default=30)
    ap.add_argument("--n-samples", type=int, default=40,
                    help="balanced test subset size; use 0 for the FULL fold "
                         "(275 pts, natural 153/122 imbalance) which is the paper's "
                         "evaluation set and the only one where macro-F1 can show "
                         "majority-class collapse")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--reps", type=int, default=3,
                    help="batch resubmissions for drift/shot-noise bands "
                         "(matches two_curves reps=3 and upstream iterations=3)")
    ap.add_argument("--dd-ablation", action="store_true",
                    help="run each batch twice (DD off & on)")
    ap.add_argument("--no-dd", action="store_true",
                    help="DD OFF only -- the sensible headline on IQM Spark, where "
                         "STANDARD_DD adds coherent error and lowers both fidelity "
                         "and accuracy (observed in the d6 ablation)")
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--url", default=os.environ.get("IQM_SERVER_URL", ""))
    ap.add_argument("--max-circuits", type=int, default=800)
    ap.add_argument("--chunk-size", type=int, default=0,
                    help="split each ansatz batch into slices of this many circuits "
                         "before submitting (avoids IQM DataSizeError on deep d4/d6 "
                         "circuits); 0 = submit the whole batch at once")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--out", default="banknote_study/banknote_hardware_results.csv")
    args = ap.parse_args()
    n = 5

    cal = load_iqm_calibration(str(QEM_ROOT / args.calibration))
    p_ro = cal.p_ro
    folds = args.folds if args.folds else [args.fold]
    dd_modes = [False, True] if args.dd_ablation else ([False] if args.no_dd else [True])

    try:
        from iqm.iqm_client import validate_circuit
    except Exception:
        from iqm.iqm_client.models import validate_circuit  # type: ignore

    # build + validate all batches, keyed by (ansatz, depth, fold); each fold has
    # its own test set, trained weights, ideal expectations, and labels.
    batches = {}
    total = 0
    for fold in folds:
        X_eval, y_eval = load_eval_subset(fold, args.n_samples, args.seed)
        for depth in args.depths:
            for name in args.ansatze:
                full, xparams, wparams = build_full_circuit(name, n, depth)
                weights = load_weights(name, depth, fold, args.epoch)
                circ_w = full.assign_parameters(dict(zip(wparams, weights)))
                mq = READOUT_QUBIT[name]
                ics, per_circ, ideal, readwire = [], [], [], []
                n2q = None
                for pi, x in enumerate(X_eval):
                    bound = circ_w.assign_parameters(dict(zip(xparams, x)))
                    ideal.append(exact_ev(bound, zobs(n, mq)))
                    native = native_transpile(bound, n)
                    readwire.append(native.layout.final_index_layout()[mq])
                    n2q = sum(1 for i in native.data if i.operation.name == "cz")
                    for s in SCALE_FACTORS:
                        ic = qiskit_to_iqm(fold_global(native, s), phys=PHYS, meas_key="m")
                        validate_circuit(ic)
                        ics.append(ic)
                        per_circ.append((pi, s))
                batches[(name, depth, fold)] = (
                    ics, per_circ, np.asarray(ideal), readwire, n2q, np.asarray(y_eval))
                total += len(ics) * len(dd_modes) * args.reps

    print("=" * 70)
    print(f"BANKNOTE on ODRA | ansatze={args.ansatze} depths={args.depths} folds={folds}")
    print(f"  scales={SCALE_FACTORS} shots={args.shots} reps={args.reps}")
    dd_label = "ablation" if args.dd_ablation else ("off" if args.no_dd else "on")
    print(f"  DD={dd_label}  circuits={total} "
          f"(guard --max-circuits={args.max_circuits})")
    print(f"  mode={'SUBMIT' if args.submit else 'DRY-RUN (no submission)'}")
    print("=" * 70)

    if not args.submit:
        ex = next(iter(batches.values()))[0][0]
        print(f"DRY-RUN ok. example IQM circuit: {len(ex.instructions)} instr, "
              f"{sum(1 for o in ex.instructions if o.name=='cz')} cz. Nothing submitted.")
        for fold in folds:
            for depth in args.depths:
                for name in args.ansatze:
                    b = batches[(name, depth, fold)]
                    print(f"  f{fold} d{depth} {name:>10}: 2q={b[4]:>3} "
                          f"readwire(per-pt)[0]={b[3][0]}  acc_ideal="
                          f"{np.mean(np.sign(b[2]) == b[5]):.2f}")
        return
    if total > args.max_circuits:
        raise SystemExit(f"{total} circuits > --max-circuits {args.max_circuits}")
    if not args.url:
        raise SystemExit("set IQM_SERVER_URL (and IQM_TOKEN) to submit.")

    done: set[tuple[str, int, int, bool]] = set()
    out_path = pathlib.Path(args.out)
    if args.resume and out_path.exists():
        with open(out_path, newline="") as f:
            for row in csv.DictReader(f):
                done.add((row["ansatz"], int(row["depth"]),
                          int(row.get("fold", args.fold)),
                          str(row["dd"]).lower() in ("true", "1")))

    from iqm.iqm_client import IQMClient
    client = IQMClient(args.url)
    fields = ["ansatz", "readout_qubit", "transpiled_cz", "depth", "fold", "dd",
              "raw_err", "raw_err_std", "rem_err", "rem_err_std",
              "zne_linear_err", "zne_richardson_err", "zne_richardson_err_std", "zne_exp_err",
              "acc_ideal", "acc_raw", "acc_rem", "acc_zne_richardson",
              "f1_ideal", "f1_raw", "f1_rem", "f1_zne_richardson",
              "reps", "n_points", "shots", "job_ids"]
    write_header = not (args.resume and out_path.exists() and out_path.stat().st_size > 0)
    out_f = open(args.out, "a" if args.resume else "w", newline="")
    writer = csv.DictWriter(out_f, fieldnames=fields)
    if write_header:
        writer.writeheader(); out_f.flush()
    jobs_log = out_path.with_suffix(".jobs.log")

    for fold in folds:
      for depth in args.depths:
        for name in args.ansatze:
          ics, per_circ, ideal, readwire, n2q, y_eval = batches[(name, depth, fold)]
          acc_ideal = float(np.mean(np.sign(ideal) == y_eval))
          f1_ideal = macro_f1(np.sign(ideal), y_eval)
          for dd_on in dd_modes:
            if (name, depth, fold, dd_on) in done:
                print(f"  f{fold} d{depth} {name:>10} DD={'on' if dd_on else 'off'} SKIP (in CSV)")
                continue
            rep_err = {k: [] for k in ("raw", "rem", "zne_linear", "zne_richardson", "zne_exp")}
            rep_acc = {k: [] for k in ("raw", "rem", "zne_richardson")}
            rep_f1 = {k: [] for k in ("raw", "rem", "zne_richardson")}
            job_ids = []
            for rep in range(args.reps):
                # Deeper circuits (d4/d6) can exceed IQM's payload byte limit as a
                # single 825-circuit batch (DataSizeError). --chunk-size splits the
                # submission into consecutive slices and concatenates the counts in
                # the SAME order, so per_circ / ZNE-scale bookkeeping stays aligned.
                cs = args.chunk_size if args.chunk_size else len(ics)
                counts_list, chunk_jids = [], []
                for c0 in range(0, len(ics), cs):
                    sub = ics[c0:c0 + cs]
                    job = submit_batch(client, sub, args.shots, dd_on)
                    with open(jobs_log, "a") as jf:
                        jf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\t{name}"
                                 f"\td{depth}\tdd={dd_on}\trep={rep}\tchunk={c0}"
                                 f"\t{job.job_id}\n")
                    cl, jid = fetch_counts(client, job)
                    counts_list.extend(cl)
                    chunk_jids.append(jid)
                jid = ";".join(chunk_jids)
                job_ids.append(jid)
                err, pred = evaluate(counts_list, per_circ, ideal, readwire, p_ro, n)
                for k in rep_err:
                    rep_err[k].append(float(np.mean(err[k])))
                for k in rep_acc:
                    rep_acc[k].append(float(np.mean(np.array(pred[k]) == y_eval)))
                for k in rep_f1:
                    rep_f1[k].append(macro_f1(pred[k], y_eval))

            def ms(v):
                a = np.asarray(v); return round(float(a.mean()), 4), round(float(a.std()), 4)
            raw_m, raw_s = ms(rep_err["raw"]); rem_m, rem_s = ms(rep_err["rem"])
            zr_m, zr_s = ms(rep_err["zne_richardson"])
            writer.writerow({
                "ansatz": name, "readout_qubit": READOUT_QUBIT[name], "transpiled_cz": n2q,
                "depth": depth, "fold": fold, "dd": dd_on,
                "raw_err": raw_m, "raw_err_std": raw_s, "rem_err": rem_m, "rem_err_std": rem_s,
                "zne_linear_err": ms(rep_err["zne_linear"])[0],
                "zne_richardson_err": zr_m, "zne_richardson_err_std": zr_s,
                "zne_exp_err": ms(rep_err["zne_exp"])[0],
                "acc_ideal": round(acc_ideal, 4), "acc_raw": ms(rep_acc["raw"])[0],
                "acc_rem": ms(rep_acc["rem"])[0], "acc_zne_richardson": ms(rep_acc["zne_richardson"])[0],
                "f1_ideal": round(f1_ideal, 4), "f1_raw": ms(rep_f1["raw"])[0],
                "f1_rem": ms(rep_f1["rem"])[0], "f1_zne_richardson": ms(rep_f1["zne_richardson"])[0],
                "reps": args.reps, "n_points": len(y_eval), "shots": args.shots,
                "job_ids": ";".join(job_ids)})
            out_f.flush()
            print(f"  f{fold} d{depth} {name:>10} DD={'on' if dd_on else 'off'} 2q={n2q:>3} | "
                  f"raw={raw_m:.3f}->+REM={rem_m:.3f}->+ZNE={zr_m:.3f} | "
                  f"acc ideal={acc_ideal:.2f}/{ms(rep_acc['raw'])[0]:.2f}/"
                  f"{ms(rep_acc['rem'])[0]:.2f}/{ms(rep_acc['zne_richardson'])[0]:.2f} | "
                  f"F1 ideal={f1_ideal:.2f}/{ms(rep_f1['raw'])[0]:.2f}/"
                  f"{ms(rep_f1['rem'])[0]:.2f}/{ms(rep_f1['zne_richardson'])[0]:.2f}")
    out_f.close()
    print(f"\nwrote {args.out}  (jobs: {jobs_log})")


if __name__ == "__main__":
    main()
