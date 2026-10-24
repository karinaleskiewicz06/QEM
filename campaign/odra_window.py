"""One calibration window of the ODRA campaign: plan, run (or simulate), archive, analyse.

Replaces ``overnight_odra.sh`` for the pre-registered campaign. One call is one window:

* **ladder**: star / linear / circular / all_to_all at L3 (12 / 30 / 39 / 57 CZ on the
  fixed-layout path) plus star at L6 / L9 / L13 without routing. Identity insertion is
  added by P5;
* **24 evaluation points** from ``campaign/eval_points.json``, the same in every window;
* **CDR arms** (``qem.arms``) at the equal budget ``(n_train + 1) * M * S`` per point:
  off_copies / twirl_logical / twirl_native / spread / spread_off x {shared_random,
  near_target}, the subset given by ``--cdr-arms``;
* **ZNE** at {1, 3, 5} with the matched-cost folding controls genuine / identity /
  garbage (``qem.folding``), folded on the native circuit;
* **block-randomised order**: every (rung, arm) is one block; the block order is shuffled
  with the window seed, recorded in the manifest;
* the **calibration set ID** is read before and after every block; if it changes the
  window is marked ``split`` in the manifest;
* ``--resume`` continues from ``counts.jsonl``: every circuit has a deterministic ID and
  its own seed (frames, garbage twins, training sets), so a re-run measures exactly the
  circuits that are missing.

Modes:

    python campaign/odra_window.py --dry-run --window-id test         # budget, nothing run
    python campaign/odra_window.py --sim-device spec/odra_cal_example.json \\
        --window-id sim1 --points optimal:star adverse:all_to_all     # end to end in Aer
    python campaign/odra_window.py --submit --window-id w01           # ODRA
    python campaign/odra_window.py --kappa --submit --window-id w01k  # kappa window
    python campaign/odra_window.py --analyse runs/odra_campaign/w01   # CSVs from counts

Outputs in ``runs/<campaign>/<window_id>/``: ``manifest.json``, ``counts.jsonl``,
``cdr.csv`` (one row per rung x arm x training set x point x fit) and ``zne.csv`` (one
row per rung x folding variant x point). The CSVs are derived; ``--analyse`` rebuilds them
from ``counts.jsonl`` alone.

ODRA has one placement (logical 0 = hub QB3), so ``optimal:`` and ``adverse:`` prefixes in
``--points`` both resolve to it; the prefix is accepted for compatibility and noted.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import math
import os
import pathlib
import random
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:                       # run as a script from anywhere
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
from qiskit import QuantumCircuit  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

from ansatz import HardwareEfficientAnsatz  # noqa: E402
from campaign.eval_points import load as load_eval_points  # noqa: E402
from cdr import near_clifford_training_circuits  # noqa: E402
from noisy_sim import perqubit_z_from_counts, readout_observable  # noqa: E402
from qem.arms import ARMS, IS_SPREAD, TWIRL_KIND, budget, plan_arm  # noqa: E402
from qem.cdr_fit import block_variance, fit_both, spread_x_variance  # noqa: E402
from qem.cdr_training import (build_training_set, clifford_ideal_expval,  # noqa: E402
                              stable_seed)
from qem.compile import compile_native, cz_skeleton  # noqa: E402
from qem.env_check import add_env_argument, require_locked_environment  # noqa: E402
from qem.folding import FOLD_VARIANTS, fold_native  # noqa: E402
from qem.identity_insertion import insert_identity, scheduled_duration  # noqa: E402
from qem.provenance import RunRecorder  # noqa: E402
from qem.twirl import twirl_logical, twirl_native_merged  # noqa: E402
from qem.zne import diagnose_point  # noqa: E402

MODELS = REPO / "trained_models_hard"
#: rung name -> (entanglement pattern, layers)
RUNGS: dict[str, tuple[str, int]] = {
    "star": ("star", 3), "linear": ("linear", 3), "circular": ("circular", 3),
    "all_to_all": ("all_to_all", 3),
    "star_L6": ("star", 6), "star_L9": ("star", 9), "star_L13": ("star", 13),
}
#: P5 identity insertion on the frozen star L3: rung -> (pairs, mode). 6/12/20 pairs take
#: the 12-CZ star to 24/36/52 CZ (cz_pairs), or to the same durations at 12 CZ (idle_matched)
INSERTIONS: dict[str, tuple[int, str]] = {
    f"star_{m}{n}": (k, mode) for n, k in ((24, 6), (36, 12), (52, 20))
    for m, mode in (("cz", "cz_pairs"), ("idle", "idle_matched"))}
RUNGS.update({name: ("star", 3) for name in INSERTIONS})
DEFAULT_ARMS = ("off_copies:near_target", "twirl_native:near_target", "spread:near_target",
                "twirl_logical:shared_random", "twirl_native:shared_random")
#: a window is split over two nights by rung, so every arm of a rung shares a calibration
NIGHTS = {"A": ("star", "circular"), "B": ("linear", "all_to_all"),
          # P5: what drives degradation -- CZ count, duration or PRX (L6/9/13 add PRX)
          "P5": ("star", "star_cz24", "star_cz36", "star_cz52", "star_idle24", "star_idle36",
                 "star_idle52", "star_L6", "star_L9", "star_L13")}
#: per-night overrides: P5 needs raw error and the untwirled CDR fit, nothing else
NIGHT_ARMS = {"P5": ("off_copies:near_target",)}
NIGHT_NO_ZNE = {"P5"}
ZNE_SCALES = (1, 3, 5)
#: measured on ODRA, 2026-10-23: ~0.3 s per circuit plus ~2.6e-4 s per shot
SEC_PER_CIRCUIT, SEC_PER_SHOT = 0.3, 2.6e-4
NIGHT_H = 8.0
N_QUBITS = 5
COEFFS = np.full(N_QUBITS, 1.0 / N_QUBITS)                # mean-Z readout


# --------------------------------------------------------------------------- #
# Plan                                                                           #
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class Job:
    """One circuit to execute, with everything its record needs."""

    cid: str
    block: str
    circuit: QuantumCircuit            # native, measured
    shots: int
    meta: dict


def _seed(*parts) -> int:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:16], 16)


def parse_points(specs) -> list[str]:
    out = []
    for s in specs:
        name = s.split(":", 1)[1] if ":" in s else s
        if name not in RUNGS:
            raise SystemExit(f"unknown rung {name!r}; expected one of {sorted(RUNGS)}")
        out.append(name)
    return out


def parse_arms(specs) -> list[tuple[str, str]]:
    out = []
    for s in specs:
        arm, _, ts = s.partition(":")
        ts = ts or "near_target"
        if arm not in ARMS:
            raise SystemExit(f"unknown arm {arm!r}; expected one of {ARMS}")
        if ts not in ("near_target", "shared_random"):
            raise SystemExit(f"unknown training set {ts!r}")
        if TWIRL_KIND[arm] == "logical" and ts != "shared_random":
            # logical twirling wraps the *logical* CZs before routing; near_target sets are
            # built on the native circuit and have no logical form
            raise SystemExit("twirl_logical needs logical training circuits: use "
                             "twirl_logical:shared_random")
        out.append((arm, ts))
    return out


def frozen(rung: str):
    pattern, layers = RUNGS[rung]
    w = np.load(MODELS / f"two_curves_d8_q5_deg8_{pattern}_mean_L{layers}_weights.npy")
    ans = HardwareEfficientAnsatz(N_QUBITS, layers, num_features=8, entanglement=pattern)
    c = ans.build()
    return c.assign_parameters(dict(zip(ans.weight_parameters(c), w))), ans.feature_parameters(c)


def build_plan(args, points: list[dict]) -> tuple[list[Job], dict]:
    """Every circuit of the window, deterministic given (seed, window_id)."""
    obs = readout_observable(N_QUBITS, "mean")
    jobs: list[Job] = []
    info: dict = {"rungs": {}, "blocks": {}}
    t_cz = getattr(args, "t_cz", 60e-9)
    t_prx = getattr(args, "t_prx", 20e-9)
    for rung in parse_points(args.points):
        cw, xp = frozen(rung)
        pairs, mode = INSERTIONS.get(rung, (0, "cz_pairs"))

        def native_of(c, measure=False):
            """compile_native, then the rung's identity insertion (none for most rungs)."""
            nat = insert_identity(compile_native(c).circuit, pairs, mode, t_cz=t_cz)
            if measure:
                nat.measure_all()
            return nat

        logical = [cw.assign_parameters(dict(zip(xp, p["x"]))) for p in points]
        natives = [native_of(c) for c in logical]
        ideal = [float(np.real(Statevector.from_instruction(c).expectation_value(obs)))
                 for c in logical]
        n_cz = natives[0].count_ops().get("cz", 0)
        info["rungs"][rung] = {"n_cz": n_cz, "skeleton": [list(e) for e in cz_skeleton(natives[0])],
                               "insertion": {"pairs": pairs, "mode": mode} if pairs else None}
        base = {"rung": rung, "n_cz": n_cz, "insert_pairs": pairs,
                "insert_mode": mode if pairs else None}

        for arm, ts in parse_arms(args.cdr_arms):
            block = f"{rung}/cdr/{arm}/{ts}"
            plan = plan_arm(arm, n_train=args.n_train, n_frames=args.frames,
                            shots=args.shots, train_set=ts)
            n_dist = plan.n_distinct_training_circuits
            for pi, p in enumerate(points):
                eix = p["eval_index"]
                if ts == "near_target":
                    tr_nat = build_training_set(natives[pi], n_train=n_dist, sampler="near_target",
                                                base_seed=args.seed, target_index=eix,
                                                window_id=args.window_id)
                    tr_log = None
                else:
                    tr_log = near_clifford_training_circuits(logical[pi], n_train=n_dist,
                                                             seed=args.seed)
                    tr_nat = [native_of(c) for c in tr_log]
                tr_ideal = [clifford_ideal_expval(c, obs) for c in tr_nat]
                for spec in plan.specs:
                    is_t = spec.role == "target"
                    cid = f"{block}/p{eix:02d}/{spec.circuit_id}"
                    rng = np.random.default_rng(_seed(args.seed, args.window_id, cid))
                    nat = natives[pi] if is_t else tr_nat[spec.train_index]
                    frame = ""
                    if TWIRL_KIND[arm] == "native":
                        tw = twirl_native_merged(nat, rng)
                        circ, frame = tw.circuit, tw.frame_str
                        circ.measure_all()
                    elif TWIRL_KIND[arm] == "logical":
                        lg = logical[pi] if is_t else tr_log[spec.train_index]
                        tw = twirl_logical(lg, rng)
                        circ, frame = native_of(tw.circuit, measure=True), tw.frame_str
                    else:
                        circ = nat.copy()
                        circ.measure_all()
                    jobs.append(Job(cid, block, circ, spec.shots, {
                        **base, "kind": "cdr", "arm": arm, "train_set": ts, "eval_index": eix,
                        "duration_sched_s": scheduled_duration(circ, t_prx=t_prx, t_cz=t_cz),
                        "role": spec.role, "train_index": spec.train_index,
                        "repeat_index": spec.repeat_index, "twirl": spec.twirl,
                        "twirl_kind": spec.twirl_kind, "frame": frame,
                        "ideal": ideal[pi] if is_t else tr_ideal[spec.train_index],
                        "skeleton_matches_target": cz_skeleton(circ) == cz_skeleton(natives[pi])
                        if spec.twirl_kind != "logical" else None}))
            info["blocks"][block] = {"budget_per_point": budget(args.n_train, args.frames,
                                                                args.shots)}

        if not args.no_zne:
            block = f"{rung}/zne"
            for pi, p in enumerate(points):
                eix = p["eval_index"]
                for v in FOLD_VARIANTS:
                    for s in ZNE_SCALES:
                        if s == 1 and v != "genuine":
                            continue                   # scale 1 is U for every variant
                        cid = f"{block}/{v}/p{eix:02d}/lam{s}"
                        circ = fold_native(natives[pi], s, v, measure=True,
                                           seed=_seed(args.seed, args.window_id, cid))
                        jobs.append(Job(cid, block, circ, args.shots, {
                            **base, "kind": "zne", "variant": v, "scale": s,
                            "duration_sched_s": scheduled_duration(circ, t_prx=t_prx,
                                                                   t_cz=t_cz),
                            "eval_index": eix, "ideal": ideal[pi]}))
    return jobs, info


def plan_counts(args, n_points: int) -> dict[str, tuple[int, int]]:
    """``{block: (circuits, shots per circuit)}`` without building a circuit.

    Exactly what :func:`build_plan` would emit (a test checks it), in milliseconds instead
    of minutes, so a dry run of a full window is instant.
    """
    out = {}
    for rung in parse_points(args.points):
        for arm, ts in parse_arms(args.cdr_arms):
            plan = plan_arm(arm, n_train=args.n_train, n_frames=args.frames,
                            shots=args.shots, train_set=ts)
            out[f"{rung}/cdr/{arm}/{ts}"] = (plan.n_circuits * n_points, args.shots)
        if not args.no_zne:
            per = 1 + len(FOLD_VARIANTS) * (len(ZNE_SCALES) - 1)
            out[f"{rung}/zne"] = (per * n_points, args.shots)
    return out


def block_order(blocks, seed: int, window_id: str) -> list[str]:
    """Blocks shuffled with a seed derived from (seed, window_id), recorded in the manifest."""
    blocks = sorted(set(blocks))
    random.Random(_seed("block-order", seed, window_id)).shuffle(blocks)
    return blocks


# --------------------------------------------------------------------------- #
# Budget                                                                         #
# --------------------------------------------------------------------------- #

def seconds(n_circuits: int, shots: int) -> float:
    return n_circuits * (SEC_PER_CIRCUIT + SEC_PER_SHOT * shots)


def print_budget(counts: dict[str, tuple[int, int]], order: list[str]) -> float:
    """Table per block, total hours, and a split into nights when over NIGHT_H."""
    by = {b: (n, n * s) for b, (n, s) in counts.items()}
    total_s = 0.0
    print(f"{'block':52s} {'circuits':>9s} {'shots':>12s} {'hours':>7s}")
    for blk in order:
        n, sh = by[blk]
        sec = seconds(n, sh / n)
        total_s += sec
        print(f"{blk:52s} {n:9d} {sh:12d} {sec / 3600:7.2f}")
    n_all = sum(v[0] for v in by.values())
    print(f"{'TOTAL':52s} {n_all:9d} {sum(v[1] for v in by.values()):12d} "
          f"{total_s / 3600:7.2f}")
    print(f"  time model: {SEC_PER_CIRCUIT} s/circuit + {SEC_PER_SHOT:.1e} s/shot "
          f"(ODRA pilot, 2026-10-23)")
    if total_s / 3600 > NIGHT_H:
        print(f"\nThe window exceeds {NIGHT_H:.0f} h. Proposed split into nights "
              f"(each night is then its own calibration window):")
        nights, cur, cur_s = [], [], 0.0
        for blk in order:
            n, sh = by[blk]
            s = seconds(n, sh / n)
            if cur and cur_s + s > NIGHT_H * 3600:
                nights.append((cur, cur_s)); cur, cur_s = [], 0.0
            cur.append(blk); cur_s += s
        if cur:
            nights.append((cur, cur_s))
        for k, (blks, s) in enumerate(nights, 1):
            rungs = sorted({b.split("/")[0] for b in blks})
            print(f"  night {k}: {len(blks)} blocks, {s / 3600:.1f} h, rungs {rungs}")
        print("  Or shrink the window: fewer --points or --cdr-arms (fixed in P9).")
    return total_s / 3600


# --------------------------------------------------------------------------- #
# Execution                                                                      #
# --------------------------------------------------------------------------- #

class Executor:
    """Hardware, device-model simulator, or nothing."""

    def __init__(self, args):
        self.args = args
        self.dev = None
        self.backend = None
        if args.sim_device:
            from sim.device_model import build_noise_model
            self.dev = build_noise_model(args.sim_device, args.sim_theta, args.sim_phi,
                                         args.sim_eps)
            self.t_1q, self.t_2q = self.dev.calibration.t_prx, self.dev.calibration.t_cz
        elif args.submit:
            from odra_backend import get_backend
            self.backend = get_backend("odra")
            self.t_1q, self.t_2q = 20e-9, 60e-9
        else:
            self.t_1q, self.t_2q = 20e-9, 60e-9

    def calibration_set_id(self) -> str | None:
        if self.dev is not None:
            return f"sim:{self.dev.tag}"
        if self.backend is not None:
            try:
                return str(self.backend.client.get_dynamic_quantum_architecture()
                           .calibration_set_id)
            except Exception as e:                     # record, never abort the window
                return f"unreadable:{type(e).__name__}"
        return None

    def run(self, circs: list[QuantumCircuit], shots: int, on_job=None) -> list[dict]:
        if self.dev is not None:
            # Aer takes a signed 32/64-bit seed; keep it well inside
            return self.dev.run(circs, shots, seed=_seed("sim", self.args.window_id,
                                                        circs[0].name, len(circs),
                                                        shots) % (2 ** 31 - 1))
        from odra_backend import run_circuits
        return run_circuits(self.backend, circs, shots, on_job=on_job)


def recorded_ids(path: pathlib.Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as fh:
        return {json.loads(l)["circuit_id"] for l in fh if l.strip()}


def run_window(args, jobs: list[Job], order: list[str], rec: RunRecorder, ex: Executor):
    done = recorded_ids(rec.counts_path) if args.resume else set()
    if done:
        print(f"[resume] {len(done)} circuits already recorded")
    blocks_log = rec.manifest.extra.setdefault("blocks", [])
    first_cal = None
    for k, blk in enumerate(order):
        pending = [j for j in jobs if j.block == blk and j.cid not in done]
        if not pending:
            print(f"  [{k + 1}/{len(order)}] {blk}: complete, skipped")
            continue
        cal0 = ex.calibration_set_id()
        first_cal = first_cal or cal0
        if rec.manifest.calibration_set_id["start"] is None:
            rec.set_calibration_set_id("start", cal0)
        t0 = time.time()
        print(f"  [{k + 1}/{len(order)}] {blk}: {len(pending)} circuits", flush=True)
        by_shots: dict[int, list[Job]] = {}
        for j in pending:
            by_shots.setdefault(j.shots, []).append(j)
        for shots, group in by_shots.items():
            for s in range(0, len(group), args.chunk):
                part = group[s:s + args.chunk]
                counts = ex.run([j.circuit for j in part], shots, on_job=rec.add_job)
                for j, cnt in zip(part, counts):
                    val = float(np.dot(COEFFS, perqubit_z_from_counts(cnt, N_QUBITS)))
                    rec.record_circuit(j.cid, cnt, native=j.circuit, t_1q=ex.t_1q,
                                       t_2q=ex.t_2q, with_qasm=not args.no_qasm,
                                       block=j.block, expval=val,
                                       coeffs=list(map(float, COEFFS)),
                                       reduction="dot_perqubit", calibration_set_id=cal0,
                                       **j.meta)
        cal1 = ex.calibration_set_id()
        blocks_log.append({"block": blk, "order": k, "n": len(pending),
                           "cal_before": cal0, "cal_after": cal1,
                           "seconds": round(time.time() - t0, 1)})
        rec.set_calibration_set_id("end", cal1)
        if cal0 != cal1 or (first_cal and cal1 != first_cal):
            rec.note(f"calibration set changed during block {blk}: {cal0} -> {cal1}")
        rec.manifest.save(rec.manifest_path)


# --------------------------------------------------------------------------- #
# Analysis                                                                       #
# --------------------------------------------------------------------------- #

def analyse(run_dir: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """``cdr.csv`` and ``zne.csv`` from ``counts.jsonl`` alone."""
    recs = [json.loads(l) for l in (run_dir / "counts.jsonl").open() if l.strip()]
    cdr_rows, zne_rows = [], []

    groups: dict[tuple, list[dict]] = {}
    for r in recs:
        if r.get("kind") == "cdr":
            groups.setdefault((r["rung"], r["arm"], r["train_set"], r["eval_index"]), []).append(r)
    for (rung, arm, ts, eix), rs in sorted(groups.items()):
        tgt = [r for r in rs if r["role"] == "target"]
        tr: dict[int, list[dict]] = {}
        for r in rs:
            if r["role"] == "train":
                tr.setdefault(r["train_index"], []).append(r)
        if not tgt or not tr:
            continue
        tvals = [r["expval"] for r in tgt]
        t_mean, ideal = float(np.mean(tvals)), tgt[0]["ideal"]
        xs, ys, vx = [], [], []
        for i in sorted(tr):
            v = [r["expval"] for r in tr[i]]
            xs.append(float(np.mean(v)))
            ys.append(tr[i][0]["ideal"])
            shots = tr[i][0]["shots"]
            vx.append(spread_x_variance(xs[-1], N_QUBITS, shots, tvals) if IS_SPREAD[arm]
                      else block_variance(v))
        for name, fit in fit_both(xs, ys, vx).items():
            cdr_rows.append({"rung": rung, "n_cz": tgt[0]["n_cz"], "arm": arm,
                             "train_set": ts, "eval_index": eix, "fit": name,
                             "ideal": ideal, "raw": t_mean, "mitigated": fit.apply(t_mean),
                             "err_raw": abs(t_mean - ideal),
                             "err": abs(fit.apply(t_mean) - ideal), "a": fit.a, "b": fit.b,
                             "r2": fit.r2, "n_train_points": len(xs),
                             "shots_total": sum(r["shots"] for r in rs),
                             "n_prx": tgt[0].get("n_prx"),
                             "duration_sched_s": tgt[0].get("duration_sched_s"),
                             "insert_pairs": tgt[0].get("insert_pairs"),
                             "insert_mode": tgt[0].get("insert_mode"),
                             "calibration_set_id": tgt[0].get("calibration_set_id")})

    zg: dict[tuple, dict] = {}
    for r in recs:
        if r.get("kind") == "zne":
            zg.setdefault((r["rung"], r["eval_index"]), {})[(r["variant"], r["scale"])] = r
    for (rung, eix), d in sorted(zg.items()):
        base = d.get(("genuine", 1))
        if base is None:
            continue
        g_lmax = [x for (v, s), x in d.items() if v == "garbage" and s == ZNE_SCALES[-1]]
        floor = None
        for v in FOLD_VARIANTS:
            sel = [base] + [d.get((v, s)) for s in ZNE_SCALES[1:]]
            if any(x is None for x in sel):
                continue
            row = diagnose_point(ZNE_SCALES, [x["expval"] for x in sel], ideal=base["ideal"],
                                 counts_per_scale=[x["counts"] for x in sel],
                                 coeffs=COEFFS,
                                 floor=g_lmax[0]["expval"] if g_lmax else floor)
            zne_rows.append({"rung": rung, "n_cz": base["n_cz"], "variant": v,
                             "eval_index": eix, **row})

    out = []
    for name, rows in (("cdr.csv", cdr_rows), ("zne.csv", zne_rows)):
        p = run_dir / name
        if rows:
            with p.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        out.append(p)
    return out[0], out[1]


def summary(run_dir: pathlib.Path) -> None:
    import pandas as pd
    cdr_p, zne_p = run_dir / "cdr.csv", run_dir / "zne.csv"
    if cdr_p.exists():
        d = pd.read_csv(cdr_p)
        d = d[d.fit == "ols"]
        print("\nCDR mean |error| (OLS) by rung x arm:")
        print(d.pivot_table(index=["n_cz", "rung"], columns=["arm", "train_set"],
                            values="err").round(4).to_string())
        print("raw:", d.groupby("rung").err_raw.mean().round(4).to_dict())
    if zne_p.exists():
        z = pd.read_csv(zne_p)
        print("\nZNE mean |error| by rung x variant (w_neg in brackets):")
        print(z.pivot_table(index=["n_cz", "rung"], columns="variant",
                            values=["err_zne", "w_neg"]).round(4).to_string())


# --------------------------------------------------------------------------- #
# Kappa window                                                                   #
# --------------------------------------------------------------------------- #

def kappa_window(args) -> None:
    """12 and 39 CZ (star, circular), 45 repetitions, uniform and Neyman allocation."""
    root = pathlib.Path(args.root) / args.campaign / args.window_id
    for pattern in ("star", "circular"):
        for alloc in ("uniform", "neyman"):
            wid = f"{args.window_id}_kappa_{pattern}_{alloc}"
            cmd = [sys.executable, str(REPO / "zne_shot_boundary.py"), "--device", "odra",
                   "--points", f"optimal:{pattern}", "--allocation", alloc,
                   "--budgets", "256", "512", "1024", "2048", "4096", "--reps", "45",
                   "--eval-points", "4", "--campaign", args.campaign, "--window-id", wid,
                   "--out", str(pathlib.Path(args.root) / args.campaign / wid / "kappa.csv"),
                   "--resume"]
            if args.submit:
                cmd.append("--submit")
            elif args.sim_device:
                cmd += ["--sim-device", args.sim_device]
            if args.allow_env_mismatch:
                cmd.append("--allow-env-mismatch")
            print("$", " ".join(cmd), flush=True)
            subprocess.run(cmd, cwd=os.getcwd(), check=False)
    print(f"kappa windows under {root.parent}")


# --------------------------------------------------------------------------- #
# CLI                                                                            #
# --------------------------------------------------------------------------- #

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="plan and budget only (default)")
    mode.add_argument("--submit", action="store_true", help="run on ODRA")
    mode.add_argument("--sim-device", metavar="CALIBRATION_JSON",
                      help="run on sim.device_model built from this calibration")
    mode.add_argument("--analyse", metavar="RUN_DIR", help="rebuild cdr.csv / zne.csv")
    ap.add_argument("--kappa", action="store_true", help="kappa window instead of the ladder")
    ap.add_argument("--dd-ablation", action="store_true", help="DD interleaving (P6)")
    ap.add_argument("--window-id", default="w01")
    ap.add_argument("--campaign", default="odra_campaign")
    ap.add_argument("--root", default="runs")
    ap.add_argument("--points", nargs="+", default=list(RUNGS),
                    help="rungs, optionally prefixed optimal:/adverse: (one layout on ODRA)")
    ap.add_argument("--cdr-arms", nargs="+", default=list(DEFAULT_ARMS),
                    help="arm:train_set pairs, e.g. spread:near_target")
    ap.add_argument("--eval-points", type=int, default=24,
                    help="use the first K of the 24 fixed points (for tests)")
    ap.add_argument("--point-set", type=int, choices=[0, 1, 2], default=None,
                    help="rotation: every third point (2 per margin quartile, 8 in all); "
                         "window w uses set (w-1) mod 3")
    ap.add_argument("--night", choices=sorted(NIGHTS), default=None,
                    help="A = star + circular (12/39 CZ), B = linear + all_to_all (30/57 CZ)")
    ap.add_argument("--n-train", type=int, default=20)
    ap.add_argument("--frames", type=int, default=6, help="M")
    ap.add_argument("--shots", type=int, default=8192, help="S")
    ap.add_argument("--no-zne", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--chunk", type=int, default=400,
                    help="circuits per executor call (ODRA splits into jobs of 100)")
    ap.add_argument("--no-qasm", action="store_true", help="skip QASM3 in records")
    ap.add_argument("--sim-theta", type=float, default=0.0)
    ap.add_argument("--sim-phi", type=float, default=0.0)
    ap.add_argument("--sim-eps", type=float, default=0.0)
    add_env_argument(ap)
    args = ap.parse_args(argv)
    require_locked_environment(allow_mismatch=args.allow_env_mismatch)

    if args.analyse:
        d = pathlib.Path(args.analyse)
        print("wrote", *analyse(d))
        summary(d)
        return
    if args.dd_ablation:
        raise SystemExit("--dd-ablation is implemented with P6 (interleaved ABAB DD in "
                         "run_hardware.py); not part of this window yet")
    if args.kappa:
        kappa_window(args)
        return

    if any(s.startswith("adverse:") for s in args.points):
        print("note: ODRA has a single placement; adverse: resolves to the same layout")
    if args.night:
        args.points = list(NIGHTS[args.night])
        if args.night in NIGHT_ARMS:
            args.cdr_arms = list(NIGHT_ARMS[args.night])
        if args.night in NIGHT_NO_ZNE:
            args.no_zne = True
    points = load_eval_points(REPO / "campaign" / "eval_points.json")[: args.eval_points]
    if args.point_set is not None:
        points = [p for k, p in enumerate(points) if k % 3 == args.point_set]
    counts = plan_counts(args, len(points))
    order = block_order(counts, args.seed, args.window_id)
    print(f"window {args.window_id}: {len(points)} points, rungs {parse_points(args.points)}, "
          f"n_train {args.n_train} (spread {args.n_train * args.frames}), M {args.frames}, "
          f"S {args.shots}, ZNE {'off' if args.no_zne else ZNE_SCALES}")
    print_budget(counts, order)
    if not (args.submit or args.sim_device):
        print("\n[DRY-RUN] nothing executed. --sim-device <cal.json> or --submit to run.")
        return
    if args.sim_device:
        from sim.device_model import load_calibration
        _c = load_calibration(args.sim_device)
        args.t_prx, args.t_cz = _c.t_prx, _c.t_cz
    jobs, info = build_plan(args, points)
    print("CZ per rung:", {r: v["n_cz"] for r, v in info["rungs"].items()})

    ex = Executor(args)
    rec = RunRecorder.open(args.campaign, window_id=args.window_id, args=vars(args),
                           seed=args.seed, device="odra", submitted=bool(args.submit),
                           root=args.root)
    rec.set_extra("plan", {"block_order": order, "block_order_seed": args.seed,
                           "rungs": info["rungs"], "n_circuits": len(jobs),
                           "eval_points": [p["eval_index"] for p in points]})
    if ex.dev is not None:
        from sim.device_model import manifest_entry
        rec.set_extra("device_model", manifest_entry(ex.dev))
    print(f"[provenance] {rec.dir}")
    run_window(args, jobs, order, rec, ex)
    rec.close()
    if rec.manifest.is_split:
        print("WARNING: calibration set changed during the window -> marked split")
    print("wrote", *analyse(rec.dir))
    summary(rec.dir)


if __name__ == "__main__":
    main()
