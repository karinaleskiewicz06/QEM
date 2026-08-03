"""Mirror-circuit fidelity for the banknote ansatz cost ladder (sim + hardware).

A mirror circuit runs U then U^dag: the ideal output is exactly |0...0>, so the
survival probability P(|0>^n) is a *task-agnostic* fidelity of that exact routing
structure on the device. It isolates hardware degradation from anything about the
classifier's decision boundary -- the clean companion to the accuracy story.

We build U = (Ry feature map + ansatz) with the trained weights bound and a
representative input bound, transpile to the native {r, cz} star basis, then
append a barrier and U^dag. The ladder is star < odra < simulator in CZ, so
fidelity should fall monotonically with 2*CZ (each mirror doubles the gate count).

Modes (same safety staging as run_hardware.py):
  (default)      ODRA-calibrated NOISY SIMULATOR -- safe, no token, run anytime.
  --submit       real ODRA hardware via iqm-client (reuses run_hardware helpers).
                 Requires IQM_SERVER_URL + IQM_TOKEN. --dry-run builds+validates
                 circuits and submits nothing.

Usage:
    python banknote_study/mirror_fidelity.py                       # sim, all 3 x depths
    python banknote_study/mirror_fidelity.py --depths 4 --shots 8192
    python banknote_study/mirror_fidelity.py --submit --dry-run    # validate hw circuits
    python banknote_study/mirror_fidelity.py --submit --dd-ablation # real QPU (when free)
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys

import numpy as np

QEM_ROOT = pathlib.Path(__file__).resolve().parents[1]
UPSTREAM = QEM_ROOT / "banknote_study" / "upstream"
sys.path.insert(0, str(QEM_ROOT))
sys.path.insert(0, str(UPSTREAM / "src"))

from qiskit import QuantumCircuit  # noqa: E402

from banknote_study.run_zne_banknote import (  # noqa: E402
    READOUT_QUBIT, build_full_circuit, load_eval_subset, load_weights,
)
from noisy_sim import load_iqm_calibration, make_noisy_simulator, schedule_with_idle  # noqa: E402
from zne_dryrun import native_transpile  # noqa: E402

# native_transpile already routes each ansatz onto the star coupling map with
# circuit-qubit 0 == hub, so we map circuit-qubit j -> device label PHYS[j]
# uniformly (hub QB3). The star ansatz's hub is baked into the routed circuit.
PHYS = ["QB3", "QB1", "QB2", "QB4", "QB5"]  # circuit-qubit 0 (hub) -> QB3


def mirror_native(ansatz: str, depth: int, x: np.ndarray, fold: int, epoch: int, n: int) -> QuantumCircuit:
    """Return the native {r,cz} mirror circuit U;barrier;U^dag (no measurements)."""
    full, xparams, wparams = build_full_circuit(ansatz, n, depth)
    weights = load_weights(ansatz, depth, fold, epoch)
    bound = full.assign_parameters(dict(zip(wparams, weights)) | dict(zip(xparams, x)))
    u = native_transpile(bound, n)                    # native, star-routed
    mirror = u.copy()
    mirror.barrier()                                  # protect U^dag from cancellation
    mirror.compose(u.inverse(), inplace=True)
    return mirror


def survival_prob(counts: dict, n: int) -> float:
    total = sum(counts.values())
    zero = "0" * n
    hit = 0
    for bitstr, c in counts.items():
        if str(bitstr).replace(" ", "")[-n:].zfill(n) == zero:
            hit += c
    return hit / total if total else 0.0


def run_sim(args, ansatze, n) -> list[dict]:
    cal = load_iqm_calibration(str(QEM_ROOT / args.calibration))
    sims = {"raw": make_noisy_simulator(cal, dd=False),
            "dd": make_noisy_simulator(cal, dd=True)}
    rows = []
    print(f"{'ansatz':>10} {'depth':>5} {'2*CZ':>6} {'F_raw':>7} {'F_dd':>7} {'F/CZ_dd':>8}")
    for name in ansatze:
        for depth in args.depths:
            # average survival over a few representative inputs (fidelity is
            # input-agnostic in the ideal, but binding real data keeps the native
            # angles realistic for coherent-error accumulation)
            X, _ = load_eval_subset(args.fold, args.reps_points, args.seed)
            f = {"raw": [], "dd": []}
            n2q = None
            for x in X:
                mir = mirror_native(name, depth, x, args.fold, args.epoch, n)
                n2q = sum(1 for i in mir.data if i.operation.name == "cz")
                for key, sim in sims.items():
                    sched = schedule_with_idle(mir, cal)
                    sched.measure_all()
                    counts = sim.run(sched, shots=args.shots).result().get_counts()
                    f[key].append(survival_prob(counts, n))
            fr, fd = float(np.mean(f["raw"])), float(np.mean(f["dd"]))
            per_cz = fd ** (1.0 / max(n2q, 1))
            rows.append({"ansatz": name, "depth": depth, "mirror_cz": n2q,
                         "readout_qubit": READOUT_QUBIT[name],
                         "F_survival_raw": round(fr, 4), "F_survival_dd": round(fd, 4),
                         "F_per_cz_dd": round(per_cz, 4),
                         "shots": args.shots, "points": len(X)})
            print(f"{name:>10} {depth:>5} {n2q:>6} {fr:>7.3f} {fd:>7.3f} {per_cz:>8.4f}")
    return rows


def run_hardware(args, ansatze, n) -> list[dict]:
    from run_hardware import qiskit_to_iqm, submit_batch, fetch_counts
    try:
        from iqm.iqm_client import validate_circuit
    except Exception:
        from iqm.iqm_client.models import validate_circuit  # type: ignore

    X, _ = load_eval_subset(args.fold, args.reps_points, args.seed)
    dd_modes = [False, True] if args.dd_ablation else [True]

    # build + validate all IQM circuits first (dry-run stops here)
    plan = []  # (ansatz, depth, iqm_circs, mirror_cz)
    total = 0
    for name in ansatze:
        for depth in args.depths:
            ics, n2q = [], None
            for x in X:
                mir = mirror_native(name, depth, x, args.fold, args.epoch, n)
                n2q = sum(1 for i in mir.data if i.operation.name == "cz")
                ic = qiskit_to_iqm(mir, phys=PHYS, meas_key="m")
                validate_circuit(ic)
                ics.append(ic)
            plan.append((name, depth, ics, n2q))
            total += len(ics) * len(dd_modes) * args.reps

    print("=" * 66)
    print(f"MIRROR fidelity on ODRA | ansatze={ansatze} depths={args.depths}")
    print(f"  points={len(X)} shots={args.shots} reps={args.reps} "
          f"DD={'ablation' if args.dd_ablation else 'on'}")
    print(f"  circuits={total} (guard --max-circuits={args.max_circuits})")
    print(f"  mode={'SUBMIT' if not args.dry_run else 'DRY-RUN (no submission)'}")
    print("=" * 66)
    if args.dry_run:
        ex = plan[0][2][0]
        print(f"DRY-RUN ok. example IQM mirror ({plan[0][0]} d{plan[0][1]}): "
              f"{len(ex.instructions)} instr, "
              f"{sum(1 for o in ex.instructions if o.name=='cz')} cz. Nothing submitted.")
        return []
    if total > args.max_circuits:
        raise SystemExit(f"{total} circuits > --max-circuits {args.max_circuits}")
    if not args.url:
        raise SystemExit("set IQM_SERVER_URL (and IQM_TOKEN) to submit.")

    from iqm.iqm_client import IQMClient
    client = IQMClient(args.url)
    rows = []
    for name, depth, ics, n2q in plan:
        for dd_on in dd_modes:
            fs = []
            for _ in range(args.reps):
                job = submit_batch(client, ics, args.shots, dd_on)
                counts_list, _ = fetch_counts(client, job)
                fs.extend(survival_prob(c, n) for c in counts_list)
            fmean = float(np.mean(fs))
            rows.append({"ansatz": name, "depth": depth, "mirror_cz": n2q,
                         "dd": dd_on, "F_survival": round(fmean, 4),
                         "F_survival_std": round(float(np.std(fs)), 4),
                         "F_per_cz": round(fmean ** (1.0 / max(n2q, 1)), 4),
                         "shots": args.shots, "reps": args.reps, "points": len(X)})
            print(f"  {name:>10} d{depth} DD={'on' if dd_on else 'off'} 2q={n2q:>3} "
                  f"F={fmean:.3f}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ansatze", nargs="+", default=["star", "odra", "simulator"])
    ap.add_argument("--depths", type=int, nargs="+", default=[2, 4, 6])
    ap.add_argument("--fold", type=int, default=1)
    ap.add_argument("--epoch", type=int, default=30)
    ap.add_argument("--reps-points", type=int, default=5,
                    help="representative inputs averaged for the native angles")
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--calibration", default="calibrations/odra.json")
    ap.add_argument("--seed", type=int, default=42)
    # hardware
    ap.add_argument("--submit", action="store_true", help="use real ODRA hardware")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --submit: build+validate circuits, submit nothing")
    ap.add_argument("--dd-ablation", action="store_true")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--url", default=os.environ.get("IQM_SERVER_URL", ""))
    ap.add_argument("--max-circuits", type=int, default=200)
    ap.add_argument("--out", default="banknote_study/banknote_mirror_fidelity.csv")
    args = ap.parse_args()
    n = 5

    rows = run_hardware(args, args.ansatze, n) if args.submit else run_sim(args, args.ansatze, n)
    if rows:
        out = QEM_ROOT / args.out
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
