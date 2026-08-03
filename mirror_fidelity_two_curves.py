"""Mirror-circuit fidelity for the two_curves routing ladder (sim + hardware).

The two_curves analogue of ``banknote_study/mirror_fidelity.py``. A mirror circuit
runs U then U^dag, so the ideal output is exactly |0...0> and the survival
probability P(|0>^n) is a *task-agnostic* fidelity of that exact routing structure
on the device. Unlike classification accuracy -- which is a sign() decision and
therefore largely insensitive to noise -- survival probability degrades smoothly
with routing cost, so it is the metric that actually resolves the ladder.

The ladder is the four entangling patterns at the locked (n, L), ordered by
transpiled CZ on the star coupling map:

    star (12) < linear (27) < circular (36) < all_to_all (54)

Each pattern uses its OWN trained classifier (train_patterns.py) when available,
falling back to the locked star weights -- identical to ``run_hardware.py``, so the
fidelity and the accuracy numbers describe the same circuits.

Modes (same safety staging as run_hardware.py):
  (default)  ODRA-calibrated NOISY SIMULATOR -- safe, no token, run anytime.
  --submit   real ODRA hardware via iqm-client (reuses run_hardware helpers).
             --dry-run builds + validates circuits and submits nothing.

Usage:
    python mirror_fidelity_two_curves.py                      # sim, all 4 patterns
    python mirror_fidelity_two_curves.py --submit --dry-run   # validate hw circuits
    python mirror_fidelity_two_curves.py --submit --no-dd     # real QPU, DD off
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib

import numpy as np
from qiskit import QuantumCircuit

from noisy_sim import (
    load_frozen_model,
    load_iqm_calibration,
    make_noisy_simulator,
    schedule_with_idle,
)
from zne_dryrun import LADDER_PATTERNS, build_level_circuit, native_transpile

MODELS_DIR = pathlib.Path("trained_models")


def load_ladder_inputs(cfg: dict, n: int, n_points: int) -> np.ndarray:
    """Representative feature vectors from the frozen two_curves reference set."""
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(MODELS_DIR / f"{tag}_reference.npz")
    return ref["X_eval"][:n_points]


def weights_for(cfg: dict, n: int, pattern: str) -> tuple[np.ndarray, bool]:
    """Per-pattern classifier if train_patterns.py produced one, else locked star."""
    ptag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
            f"{pattern}_{cfg['readout']}_L{cfg['n_layers']}")
    wp = MODELS_DIR / f"{ptag}_weights.npy"
    if wp.exists():
        return np.load(wp), True
    return np.load(MODELS_DIR / cfg["weights_file"]), False


def mirror_native(cfg: dict, n: int, pattern: str, x: np.ndarray,
                  weights: np.ndarray) -> QuantumCircuit:
    """Return the native {r,cz} mirror circuit U;barrier;U^dag (no measurements)."""
    circ, xparams, ans = build_level_circuit(cfg, pattern)
    wparams = ans.weight_parameters(circ)
    bound = circ.assign_parameters(dict(zip(wparams, weights))
                                   | dict(zip(xparams, x)))
    u = native_transpile(bound, n)
    mirror = u.copy()
    mirror.barrier()               # keep U^dag from being optimised away
    mirror.compose(u.inverse(), inplace=True)
    return mirror


def survival_prob(counts: dict, n: int) -> float:
    """P(all-zero) -- the ideal mirror outcome."""
    total = sum(counts.values())
    zero = "0" * n
    hit = sum(c for b, c in counts.items()
              if str(b).replace(" ", "")[-n:].zfill(n) == zero)
    return hit / total if total else 0.0


def build_plan(cfg, n, patterns, X):
    """[(pattern, mirror_circuits, mirror_cz, per_pattern_weights)] for the ladder."""
    plan = []
    for pattern in patterns:
        weights, per_pat = weights_for(cfg, n, pattern)
        mirrors, n2q = [], 0
        for x in X:
            mir = mirror_native(cfg, n, pattern, x, weights)
            n2q = sum(1 for i in mir.data if i.operation.name == "cz")
            mirrors.append(mir)
        plan.append((pattern, mirrors, n2q, per_pat))
    return plan


def run_sim(args, cfg, n, plan) -> list[dict]:
    cal = load_iqm_calibration(args.calibration)
    sims = {False: make_noisy_simulator(cal, dd=False),
            True: make_noisy_simulator(cal, dd=True)}
    dd_modes = [False, True] if args.dd_ablation else [not args.no_dd]
    rows = []
    for pattern, mirrors, n2q, per_pat in plan:
        for dd_on in dd_modes:
            fs = []
            for mir in mirrors:
                sched = schedule_with_idle(mir, cal)
                sched.measure_all()
                counts = sims[dd_on].run(sched, shots=args.shots).result().get_counts()
                fs.append(survival_prob(counts, n))
            rows.append(_row(pattern, n2q, per_pat, dd_on, fs, args, len(mirrors)))
            print(f"  {pattern:>11} DD={'on ' if dd_on else 'off'} 2q={n2q:>3} "
                  f"F={np.mean(fs):.4f}")
    return rows


def run_hardware(args, cfg, n, plan) -> list[dict]:
    from run_hardware import fetch_counts, qiskit_to_iqm, submit_batch
    try:
        from iqm.iqm_client import validate_circuit
    except Exception:
        from iqm.iqm_client.models import validate_circuit  # type: ignore

    dd_modes = [False, True] if args.dd_ablation else [not args.no_dd]

    iqm_plan, total = [], 0
    for pattern, mirrors, n2q, per_pat in plan:
        ics = []
        for mir in mirrors:
            ic = qiskit_to_iqm(mir, meas_key="m")
            validate_circuit(ic)
            ics.append(ic)
        iqm_plan.append((pattern, ics, n2q, per_pat))
        total += len(ics) * len(dd_modes) * args.reps

    dd_label = "ablation" if args.dd_ablation else ("off" if args.no_dd else "on")
    print("=" * 70)
    print(f"two_curves MIRROR fidelity on ODRA | patterns={[p[0] for p in plan]}")
    print(f"  points={len(plan[0][1])} shots={args.shots} reps={args.reps} DD={dd_label}")
    print(f"  circuits={total} (guard --max-circuits={args.max_circuits})")
    print(f"  mode={'SUBMIT' if not args.dry_run else 'DRY-RUN (no submission)'}")
    print("=" * 70)

    if args.dry_run:
        ex = iqm_plan[0][1][0]
        print(f"DRY-RUN ok. example IQM mirror ({iqm_plan[0][0]}): "
              f"{len(ex.instructions)} instr, "
              f"{sum(1 for o in ex.instructions if o.name == 'cz')} cz. Nothing submitted.")
        for pattern, ics, n2q, per_pat in iqm_plan:
            print(f"  {pattern:>11}: mirror 2q={n2q:>3} circuits={len(ics)}")
        return []
    if total > args.max_circuits:
        raise SystemExit(f"{total} circuits > --max-circuits {args.max_circuits}")
    if not args.url:
        raise SystemExit("set IQM_SERVER_URL (and IQM_TOKEN) to submit.")

    from iqm.iqm_client import IQMClient
    client = IQMClient(args.url)
    rows = []
    for pattern, ics, n2q, per_pat in iqm_plan:
        for dd_on in dd_modes:
            fs, job_ids = [], []
            for _ in range(args.reps):
                job = submit_batch(client, ics, args.shots, dd_on)
                counts_list, jid = fetch_counts(client, job)
                job_ids.append(jid)
                fs.extend(survival_prob(c, n) for c in counts_list)
            row = _row(pattern, n2q, per_pat, dd_on, fs, args, len(ics))
            row["job_ids"] = ";".join(job_ids)
            rows.append(row)
            print(f"  {pattern:>11} DD={'on ' if dd_on else 'off'} 2q={n2q:>3} "
                  f"F={np.mean(fs):.4f}")
    return rows


def _row(pattern, n2q, per_pat, dd_on, fs, args, points) -> dict:
    fmean = float(np.mean(fs))
    return {"pattern": pattern, "per_pattern_weights": per_pat, "mirror_cz": n2q,
            "dd": dd_on, "F_survival": round(fmean, 4),
            "F_survival_std": round(float(np.std(fs)), 4),
            "F_per_cz": round(fmean ** (1.0 / max(n2q, 1)), 4),
            "shots": args.shots, "reps": args.reps, "points": points}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patterns", nargs="+", default=LADDER_PATTERNS)
    ap.add_argument("--points", type=int, default=5,
                    help="representative inputs averaged (mirror ideal is "
                         "input-independent; real data keeps native angles realistic)")
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--submit", action="store_true", help="use real ODRA hardware")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --submit: build+validate circuits, submit nothing")
    ap.add_argument("--dd-ablation", action="store_true",
                    help="run each batch twice (DD off & on)")
    ap.add_argument("--no-dd", action="store_true",
                    help="DD OFF -- the sensible default on IQM Spark, where "
                         "STANDARD_DD was measured to lower fidelity")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--url", default=os.environ.get("IQM_SERVER_URL", ""))
    ap.add_argument("--max-circuits", type=int, default=200)
    ap.add_argument("--out", default="two_curves_mirror_fidelity.csv")
    args = ap.parse_args()

    _, _, cfg = load_frozen_model()
    n = cfg["n_qubits"]
    X = load_ladder_inputs(cfg, n, args.points)
    plan = build_plan(cfg, n, args.patterns, X)

    rows = (run_hardware(args, cfg, n, plan) if args.submit
            else run_sim(args, cfg, n, plan))
    if rows:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
