"""Run the locked VQC + DD/REM/ZNE routing ladder on real ODRA hardware.

This mirrors ``zne_dryrun.py`` but executes on the device instead of Aer. Only
EXECUTION changes; the science (per-pattern locked classifier, frozen 30-pt eval
subset, exact noiseless ⟨O⟩ reference, unitary folding, REM, extrapolation) is
identical, so hardware results are directly comparable to the simulator.

Submission uses ``iqm-client`` directly (no qiskit-iqm needed):
  Qiskit native {r, cz} circuit  ->  IQM Circuit (prx/cz/measure)
  -> submit_circuits(shots, CircuitCompilationOptions(dd_mode=...))
  -> wait -> measurement counts -> REM -> ZNE.

DD is NATIVE on hardware (a compile option), unlike the simulator's T2*->T2echo
model. ``--dd-ablation`` runs each batch twice (DD off / DD on) to measure DD's
real effect.

SAFETY (protects your allocation):
  default is --dry-run: build + validate circuits locally, print the shot/circuit
  budget, submit NOTHING. Real execution requires --submit, and staged scope:
    --smoke      1 pattern (star), 1 point, DD off        (~3 circuits)
    --go-no-go   star + all_to_all, 8 points              (Month-1 test)
    --full       4 patterns, 30 points                    (only after go/no-go)

Credentials: export IQM_SERVER_URL and IQM_TOKEN (see collect_odra_calibration.py).

Usage:
  python run_hardware.py --dry-run --go-no-go
  python run_hardware.py --submit --smoke
  python run_hardware.py --submit --go-no-go --dd-ablation
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import time

import numpy as np

from noisy_sim import (
    load_frozen_model,
    load_iqm_calibration,
    observable_coeffs,
    rem_correct_z,
)
from zne_dryrun import (
    SCALE_FACTORS,
    build_level_circuit,
    exact_ev,
    extrapolate,
    fold_global,
    native_transpile,
)

# logical qubit index -> physical ODRA label (hub QB3 = logical 0)
PHYS = ["QB3", "QB1", "QB2", "QB4", "QB5"]
OUT_CSV = pathlib.Path("hardware_results.csv")


# --------------------------------------------------------------------------- #
# Qiskit native circuit -> IQM Circuit                                          #
# --------------------------------------------------------------------------- #

def qiskit_to_iqm(circ, phys=PHYS, meas_key: str = "m"):
    """Convert a native {r, cz, barrier} Qiskit circuit to an IQM Circuit.

    A single ``measure`` over all qubits (logical order) carries the readout;
    its histogram bitstring is ordered by the measure locus = ``phys``.
    Barriers are preserved so the folded U^dag U structure is not compiled away.
    """
    from iqm.iqm_client import Circuit, CircuitOperation

    n = circ.num_qubits

    def qname(qubit) -> str:
        return phys[circ.find_bit(qubit).index]

    ops = []
    for inst in circ.data:
        name = inst.operation.name
        qs = inst.qubits
        if name == "r":
            theta, phi = (float(p) for p in inst.operation.params)
            ops.append(CircuitOperation(
                name="prx", locus=(qname(qs[0]),),
                args={"angle": theta, "phase": phi},
            ))
        elif name == "cz":
            ops.append(CircuitOperation(
                name="cz", locus=(qname(qs[0]), qname(qs[1])), args={},
            ))
        elif name == "barrier":
            ops.append(CircuitOperation(
                name="barrier", locus=tuple(qname(q) for q in qs), args={},
            ))
        elif name in ("id", "delay"):
            continue  # idle is physical on hardware
        elif name == "measure":
            continue  # appended once below
        else:
            raise ValueError(f"cannot convert gate {name!r} to IQM native set")

    ops.append(CircuitOperation(
        name="measure", locus=tuple(phys[:n]), args={"key": meas_key},
    ))
    return Circuit(name=(circ.name or "vqc"), instructions=tuple(ops))


def perqubit_z_iqm(counts: dict[str, int], n: int) -> np.ndarray:
    """Per-qubit ⟨Z_q⟩ from an IQM histogram (bit j = logical qubit j)."""
    total = sum(counts.values())
    z = np.zeros(n)
    for bitstr, c in counts.items():
        bits = str(bitstr).replace(" ", "")
        for q in range(n):
            z[q] += (1.0 - 2.0 * int(bits[q])) * c
    return z / total


def counts_of(cmc) -> dict[str, int]:
    """Extract {bitstring: count} from a CircuitMeasurementCounts element."""
    c = cmc.counts
    if isinstance(c, dict):
        # may be {key: {bitstring: n}} or {bitstring: n}
        if len(c) == 1 and isinstance(next(iter(c.values())), dict):
            return next(iter(c.values()))
        # if keyed by measurement key(s), merge the single key
        vals = list(c.values())
        if vals and isinstance(vals[0], dict):
            merged: dict[str, int] = {}
            for d in vals:
                for k, v in d.items():
                    merged[k] = merged.get(k, 0) + v
            return merged
        return c
    return dict(c)


# --------------------------------------------------------------------------- #
# Execution                                                                     #
# --------------------------------------------------------------------------- #

def _net_errors():
    """Transient network exceptions worth retrying (submission / fetch)."""
    errs = [ConnectionError, TimeoutError, OSError]
    try:
        import requests
        errs += [requests.exceptions.ConnectionError,
                 requests.exceptions.Timeout,
                 requests.exceptions.ChunkedEncodingError]
    except Exception:
        pass
    return tuple(errs)


def _retry(fn, what, attempts=5, base_delay=5.0):
    """Call fn() with exponential backoff on transient network errors."""
    last = None
    for a in range(attempts):
        try:
            return fn()
        except _net_errors() as e:
            last = e
            wait = base_delay * (2 ** a)
            print(f"  [retry] {what}: {type(e).__name__} "
                  f"(attempt {a + 1}/{attempts}) -> waiting {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"{what} failed after {attempts} attempts") from last


def submit_batch(client, batch, shots, dd_on):
    """Submit one CircuitBatch (with retry); return the job handle."""
    from iqm.iqm_client import CircuitCompilationOptions, DDMode, STANDARD_DD_STRATEGY

    opts = CircuitCompilationOptions(
        dd_mode=DDMode.ENABLED if dd_on else DDMode.DISABLED,
        dd_strategy=STANDARD_DD_STRATEGY if dd_on else None,
    )
    return _retry(lambda: client.submit_circuits(batch, shots=shots, options=opts),
                  what="submit_circuits")


def fetch_counts(client, job, timeout_s=1800):
    """Wait for a submitted job and return counts (with retry on transient errors).

    Only the wait/fetch is retried here; the job is already on the server, so a
    network blip during retrieval is fully recoverable via its job_id.
    """
    job_id = job.job_id

    def _go():
        try:
            job.wait_for_completion(timeout_secs=timeout_s)
        except TypeError:
            job.wait_for_completion()
        cmc_batch = client.get_job_measurement_counts(job_id)
        return [counts_of(cmc) for cmc in cmc_batch]

    return _retry(_go, what=f"fetch counts {job_id}"), str(job_id)


def evaluate(counts_list, ideal_evs, coeffs, p_ro, n, per_circ):
    """Turn a batch's counts into the ablation rungs raw -> +REM -> +REM+ZNE.

    DD is a batch-level compile option (fixed for this batch); REM and ZNE are
    both post-processing on the SAME counts, so one batch yields all three rungs:
      raw  = scale-1 ⟨O⟩, no REM
      rem  = scale-1 ⟨O⟩, REM applied
      zne_*= extrapolate REM-corrected ⟨O⟩ over SCALE_FACTORS to zero noise
    ``per_circ`` is the list of (point_index, scale) describing batch order.
    """
    # regroup by point -> {scale: (ev_raw, ev_rem)}
    by_point: dict[int, dict[int, tuple[float, float]]] = {}
    for (pi, s), counts in zip(per_circ, counts_list):
        zq = perqubit_z_iqm(counts, n)
        ev_raw = float(np.dot(coeffs, zq))
        ev_rem = float(np.dot(coeffs, rem_correct_z(zq, p_ro)))
        by_point.setdefault(pi, {})[s] = (ev_raw, ev_rem)

    err = {"raw": [], "rem": [], "zne_linear": [], "zne_richardson": [], "zne_exp": []}
    pred = {"raw": [], "rem": [], "zne_richardson": []}
    for pi, sv in by_point.items():
        ideal = ideal_evs[pi]
        raw1 = sv[SCALE_FACTORS[0]][0]
        rem1 = sv[SCALE_FACTORS[0]][1]
        rem_vals = [sv[s][1] for s in SCALE_FACTORS]  # REM-corrected, then extrapolate
        err["raw"].append(abs(raw1 - ideal))
        err["rem"].append(abs(rem1 - ideal))
        err["zne_linear"].append(abs(extrapolate(SCALE_FACTORS, rem_vals, "linear") - ideal))
        zrich = extrapolate(SCALE_FACTORS, rem_vals, "richardson")
        err["zne_richardson"].append(abs(zrich - ideal))
        err["zne_exp"].append(abs(extrapolate(SCALE_FACTORS, rem_vals, "exponential") - ideal))
        pred["raw"].append(np.sign(raw1))
        pred["rem"].append(np.sign(rem1))
        pred["zne_richardson"].append(np.sign(zrich))
    return by_point, err, pred


# --------------------------------------------------------------------------- #
# Main                                                                          #
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="submit", action="store_false",
                      help="build+validate circuits, submit nothing (default)")
    mode.add_argument("--submit", dest="submit", action="store_true",
                      help="actually submit to the device")
    ap.set_defaults(submit=False)

    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--smoke", action="store_true", help="1 pattern, 1 point")
    scope.add_argument("--go-no-go", action="store_true",
                       help="star + all_to_all, 8 points (Month-1 test)")
    scope.add_argument("--full", action="store_true", help="4 patterns, 30 points")

    ap.add_argument("--dd-ablation", action="store_true",
                    help="run each batch twice: DD off and DD on")
    ap.add_argument("--shots", type=int, default=4096)
    ap.add_argument("--reps", type=int, default=1,
                    help="resubmit each batch R times (drift / shot-noise bands)")
    ap.add_argument("--calibration", default="calibrations/odra.json",
                    help="calibration JSON (for REM p_ro)")
    ap.add_argument("--url", default=os.environ.get("IQM_SERVER_URL", ""))
    ap.add_argument("--max-circuits", type=int, default=400,
                    help="refuse to submit more than this many circuits (guard)")
    ap.add_argument("--out", default=str(OUT_CSV))
    ap.add_argument("--resume", action="store_true",
                    help="append to --out, skipping (pattern,DD) combos already "
                         "present so a crashed run continues instead of re-spending "
                         "hardware time")
    args = ap.parse_args()

    # scope
    if args.smoke:
        patterns, n_points = ["star"], 1
    elif args.full:
        patterns, n_points = ["star", "linear", "circular", "all_to_all"], 30
    else:  # default / --go-no-go
        patterns, n_points = ["star", "all_to_all"], 8

    # locked model + frozen reference (identical to zne_dryrun)
    _, observable, cfg = load_frozen_model()
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(pathlib.Path("trained_models") / f"{tag}_reference.npz")
    X_eval, y_eval = ref["X_eval"][:n_points], ref["y_eval"][:n_points]
    star_weights = np.load(pathlib.Path("trained_models") / cfg["weights_file"])
    coeffs = observable_coeffs(observable, n)

    cal = load_iqm_calibration(args.calibration)
    p_ro = cal.p_ro
    dd_modes = [False, True] if args.dd_ablation else [True]
    if args.smoke:
        dd_modes = [False]

    def weights_for(pattern):
        ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
                f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
        wp = pathlib.Path("trained_models") / f"{ptag}_weights.npy"
        return (np.load(wp), True) if wp.exists() else (star_weights, False)

    # ---- build all batches (per pattern) ----
    try:
        from iqm.iqm_client import validate_circuit
    except Exception:
        from iqm.iqm_client.models import validate_circuit  # type: ignore

    # already-finished (pattern, dd) rows — used by --resume
    done: set[tuple[str, bool]] = set()
    out_path = pathlib.Path(args.out)
    if args.resume and out_path.exists():
        with open(out_path, newline="") as f:
            for row in csv.DictReader(f):
                done.add((row["pattern"], str(row["dd"]).lower() in ("true", "1")))
        print(f"[resume] skipping {len(done)} finished (pattern,DD) combos in {out_path}")

    batches = {}   # pattern -> (iqm_circuits, per_circ[(pi,scale)], ideal_evs, n2q)
    total_circuits = 0
    remaining = 0
    for pattern in patterns:
        weights, per_pat = weights_for(pattern)
        circ, xparams, ans = build_level_circuit(cfg, pattern)
        wparams = ans.weight_parameters(circ)
        circ_w = circ.assign_parameters(dict(zip(wparams, weights)))
        tq = native_transpile(circ_w.assign_parameters({p: 0.0 for p in xparams}), n)
        n2q = sum(1 for i in tq.data if i.operation.name == "cz")

        iqm_circs, per_circ, ideal_evs = [], [], []
        for pi, x in enumerate(X_eval):
            bound = circ_w.assign_parameters(dict(zip(xparams, x)))
            ideal_evs.append(exact_ev(bound, observable))
            native = native_transpile(bound, n)
            for s in SCALE_FACTORS:
                folded = fold_global(native, s)
                ic = qiskit_to_iqm(folded, meas_key="m")
                validate_circuit(ic)  # local structural validation (no network)
                iqm_circs.append(ic)
                per_circ.append((pi, s))
        batches[pattern] = (iqm_circs, per_circ, np.asarray(ideal_evs), n2q, per_pat)
        for dd_on in dd_modes:
            total_circuits += len(iqm_circs) * args.reps
            if (pattern, dd_on) not in done:
                remaining += len(iqm_circs) * args.reps

    print("=" * 70)
    print(f"ODRA run | model {tag}")
    print(f"  scope     : patterns={patterns} points={n_points}")
    print(f"  scales    : {SCALE_FACTORS}  shots={args.shots}  reps={args.reps}")
    print(f"  DD        : {'ablation (off & on)' if args.dd_ablation else 'on'}"
          f"{' (forced off: smoke)' if args.smoke else ''}")
    print(f"  circuits  : {remaining} remaining / {total_circuits} full"
          f"  (guard --max-circuits={args.max_circuits})")
    if args.resume:
        print(f"  resume    : yes ({len(done)} already done)")
    print(f"  calibration for REM: {args.calibration}")
    print(f"  mode      : {'SUBMIT to device' if args.submit else 'DRY-RUN (no submission)'}")
    print("=" * 70)

    if not args.submit:
        print("\nDRY-RUN ok: all circuits built + validated. Nothing submitted.")
        print("Add --submit to run on the device. Example smoke test:")
        print("  python run_hardware.py --submit --smoke")
        # show one converted circuit as a sanity peek
        ex = batches[patterns[0]][0][0]
        print(f"\nexample IQM circuit ({patterns[0]}, first point, scale 1): "
              f"{len(ex.instructions)} instructions, "
              f"{sum(1 for o in ex.instructions if o.name=='cz')} cz")
        return

    if remaining > args.max_circuits:
        raise SystemExit(
            f"refusing to submit {remaining} circuits > --max-circuits "
            f"{args.max_circuits}. Raise the guard if intentional."
        )
    if remaining == 0:
        print("nothing left to run (all (pattern,DD) already in CSV).")
        return
    if not args.url:
        raise SystemExit("set IQM_SERVER_URL (and IQM_TOKEN) to submit.")

    from iqm.iqm_client import IQMClient
    client = IQMClient(args.url)  # token via IQM_TOKEN env
    print(f"connected: {client.get_about() if hasattr(client,'get_about') else args.url}\n")

    fieldnames = [
        "pattern", "per_pattern_weights", "transpiled_cz", "dd",
        "raw_err", "raw_err_std", "rem_err", "rem_err_std", "zne_linear_err",
        "zne_richardson_err", "zne_richardson_err_std", "zne_exp_err",
        "acc_raw", "acc_rem", "acc_zne_richardson",
        "reps", "n_points", "shots", "job_ids",
    ]
    # append on --resume so finished rows stay; otherwise rewrite from scratch
    write_header = not (args.resume and out_path.exists() and out_path.stat().st_size > 0)
    out_f = open(args.out, "a" if args.resume else "w", newline="")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()
        out_f.flush()
    jobs_log = pathlib.Path(args.out).with_suffix(".jobs.log")

    def log_job(pattern, dd_on, rep, jid):
        with open(jobs_log, "a") as jf:
            jf.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\t{pattern}\t"
                     f"dd={dd_on}\trep={rep}\t{jid}\n")

    for pattern in patterns:
        iqm_circs, per_circ, ideal_evs, n2q, per_pat = batches[pattern]
        for dd_on in dd_modes:
            if (pattern, dd_on) in done:
                print(f"  {pattern:>11} DD={'on ' if dd_on else 'off'} | SKIP (already in CSV)")
                continue
            rep_err = {"raw": [], "rem": [], "zne_linear": [],
                       "zne_richardson": [], "zne_exp": []}
            rep_acc = {"raw": [], "rem": [], "zne_richardson": []}
            job_ids = []
            for rep in range(args.reps):
                job = submit_batch(client, iqm_circs, args.shots, dd_on)
                # persist job id IMMEDIATELY: recoverable even if fetch dies
                log_job(pattern, dd_on, rep, job.job_id)
                counts_list, jid = fetch_counts(client, job)
                job_ids.append(jid)
                if args.smoke:
                    print(f"[smoke] job {jid} raw counts (first circuit):")
                    print("  ", counts_list[0])
                _, err, pred = evaluate(
                    counts_list, ideal_evs, coeffs, p_ro, n=n, per_circ=per_circ)
                for k in rep_err:
                    rep_err[k].append(float(np.mean(err[k])))
                for k in rep_acc:
                    rep_acc[k].append(float(np.mean(np.array(pred[k]) == y_eval)))

            def ms(v):
                a = np.asarray(v)
                return round(float(a.mean()), 4), round(float(a.std()), 4)

            raw_m, raw_s = ms(rep_err["raw"])
            rem_m, rem_s = ms(rep_err["rem"])
            zr_m, zr_s = ms(rep_err["zne_richardson"])
            zl_m, _ = ms(rep_err["zne_linear"])
            ze_m, _ = ms(rep_err["zne_exp"])
            a_raw, _ = ms(rep_acc["raw"])
            a_rem, _ = ms(rep_acc["rem"])
            a_zne, _ = ms(rep_acc["zne_richardson"])
            row = {
                "pattern": pattern, "per_pattern_weights": per_pat,
                "transpiled_cz": n2q, "dd": dd_on,
                "raw_err": raw_m, "raw_err_std": raw_s,
                "rem_err": rem_m, "rem_err_std": rem_s,
                "zne_linear_err": zl_m,
                "zne_richardson_err": zr_m, "zne_richardson_err_std": zr_s,
                "zne_exp_err": ze_m,
                "acc_raw": a_raw, "acc_rem": a_rem, "acc_zne_richardson": a_zne,
                "reps": args.reps, "n_points": len(X_eval), "shots": args.shots,
                "job_ids": ";".join(job_ids),
            }
            writer.writerow(row)
            out_f.flush()
            print(f"  {pattern:>11} DD={'on ' if dd_on else 'off'} | 2q={n2q:>3} | "
                  f"raw={raw_m:.3f} -> +REM={rem_m:.3f} -> +ZNE(rich)={zr_m:.3f}±{zr_s:.3f} "
                  f"(exp={ze_m:.3f}) | acc {a_raw:.2f}/{a_rem:.2f}/{a_zne:.2f}")

    out_f.close()
    print(f"\nwrote {args.out}  (job ids: {jobs_log})")


if __name__ == "__main__":
    main()
