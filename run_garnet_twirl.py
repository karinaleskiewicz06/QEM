"""Garnet twirling test — twirl on/off x {ZNE, CDR} across a CZ ladder.

IQM Resonance (iqm-client 34.x) exposes NO server-side twirling (only DD). So we
twirl CLIENT-SIDE: for each native 2q gate (post-transpilation CZ) we wrap it with a
random Pauli A and its compensator B = CZ.A.CZ† (validated: B.CZ.A = CZ, ideal
preserved). We submit M randomized instances and AVERAGE the counts -> the coherent
part of the CZ noise is Pauli-twirled (see raport_month_2.tex twirling section).

Hypothesis (from sim): twirling restores CDR's linear fit (r^2) and improves ZNE, and
the benefit GROWS with routing cost (coherent error accumulates with CZ count). Hence
a LADDER of points spanning low->high CZ, not a single point.

Each --points entry is "placement:pattern" (e.g. optimal:star, adverse:all_to_all).
twirl on/off are measured in the SAME submission per point, so the only difference is
the twirling.

SAFE BY DEFAULT: dry-run (builds circuits, runs the noiseless twirl sanity, prints a
per-point + total credit estimate, submits NOTHING). Add --submit to run on hardware.

    python run_garnet_twirl.py                                    # dry-run (no credits)
    python run_garnet_twirl.py --submit                          # real Garnet
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import pathlib

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector, Pauli, Clifford

from ansatz import HardwareEfficientAnsatz
from noisy_sim import (
    load_frozen_model, readout_observable, observable_coeffs, perqubit_z_from_counts,
    IQM_BASIS_GATES,
)
from cdr import near_clifford_training_circuits, clifford_ideal_expval, fit_cdr, apply_cdr
from zne_dryrun import SCALE_FACTORS, extrapolate, fold_global
from topology import device_coupling_map, hardware_placement, star_coupling_map

PAULIS = ["I", "X", "Y", "Z"]


def _pauli_char(P: Pauli, q: int) -> str:
    x, z = bool(P.x[q]), bool(P.z[q])
    return {(False, False): "I", (True, False): "X", (False, True): "Z", (True, True): "Y"}[(x, z)]


def _emit_pauli_r(qc: QuantumCircuit, ch: str, qubit) -> None:
    """Emit a single-qubit Pauli as native IQM `r` (PRX) gates (up to global phase)."""
    if ch == "X":
        qc.r(np.pi, 0.0, qubit)
    elif ch == "Y":
        qc.r(np.pi, np.pi / 2, qubit)
    elif ch == "Z":  # Z = Y·X up to global phase -> two PRX gates
        qc.r(np.pi, 0.0, qubit)
        qc.r(np.pi, np.pi / 2, qubit)
    # "I": nothing


def twirl_native(tqc: QuantumCircuit, rng) -> QuantumCircuit:
    """Wrap each native 2q gate with A before and B=G·A·G† after, emitting the Pauli
    wrappers directly as native `r` gates so the circuit stays fully native (r/cz) —
    no re-transpilation, physical-qubit connectivity/naming preserved. Validated:
    ideal (⟨O⟩) unchanged, only r/cz remain, CZ count unchanged."""
    out = QuantumCircuit(*tqc.qregs, *tqc.cregs)
    for ins in tqc.data:
        qi = [tqc.find_bit(q).index for q in ins.qubits]
        if len(qi) == 2 and ins.operation.name in ("cz", "cx"):
            A = Pauli("".join(rng.choice(PAULIS, size=2)))
            g = QuantumCircuit(2); g.append(ins.operation, [0, 1])
            B = A.evolve(Clifford(g), frame="s")
            _emit_pauli_r(out, _pauli_char(A, 0), qi[0]); _emit_pauli_r(out, _pauli_char(A, 1), qi[1])
            out.append(ins.operation, qi)
            _emit_pauli_r(out, _pauli_char(B, 0), qi[0]); _emit_pauli_r(out, _pauli_char(B, 1), qi[1])
        else:
            out.append(ins.operation, qi, [tqc.find_bit(c).index for c in ins.clbits])
    return out


def expval_meanz(counts, coeffs, wires):
    n = len(coeffs); tot = sum(counts.values()); acc = 0.0
    for b, c in counts.items():
        s = b.replace(" ", "")
        val = sum(coeffs[q] * (1 - 2 * int(s[len(s) - 1 - wires[q]])) for q in range(n))
        acc += val * c
    return acc / tot


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet")
    ap.add_argument("--points", nargs="+", default=["optimal:star", "adverse:all_to_all"],
                    help='ladder of "placement:pattern" points spanning low->high CZ')
    ap.add_argument("--models-dir", default="trained_models_hard")
    ap.add_argument("--eval-points", type=int, default=5)
    ap.add_argument("--shots", type=int, default=2048)
    ap.add_argument("--n-train", type=int, default=8)
    ap.add_argument("--n-twirl", type=int, default=6)
    ap.add_argument("--arms", nargs="+", default=["cdr", "zne"], choices=["raw", "cdr", "zne"])
    ap.add_argument("--twirl-arms", nargs="*", default=["cdr"], choices=["raw", "cdr", "zne"],
                    help="which arms get the twirl ON/OFF comparison (matched). Arms NOT listed run "
                         "twirl-OFF only, giving the breakdown-region drift bands (BRKD-01) cheaply. "
                         "Default: cdr (H4 — twirl helps CDR's linear fit, not ZNE's extrapolation).")
    ap.add_argument("--match-shots", action=argparse.BooleanOptionalAction, default=True,
                    help="shot-matched OFF control: average M identical UNTWIRLED copies so OFF and "
                         "ON use the SAME total sampling — the ON-vs-OFF gap then isolates coherent-"
                         "error suppression, not the M-fold averaging advantage (--no-match-shots to "
                         "disable; the confound was caught in --sim under depolarizing noise).")
    ap.add_argument("--submit", action="store_true")
    ap.add_argument("--sim", action="store_true",
                    help="run full pipeline on a NOISY SIMULATOR (no credits) — validation")
    ap.add_argument("--sim-coh", type=float, default=0.0,
                    help="[--sim only] inject a COHERENT Z over-rotation (rad) on every cz instead of "
                         "depolarizing noise — the POSITIVE control (twirl should help; Δr²>0), "
                         "bracketing the depolarizing null (--sim with sim-coh 0 → Δr²≈0).")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--window-id", default="w1",
                    help="drift-window tag stamped on every row; run once per calibration window "
                         "(different times), then combine with aggregate_twirl_windows.py")
    ap.add_argument("--out", default="garnet_twirl_results.csv")
    ap.add_argument("--resume", action="store_true",
                    help="skip (placement,pattern) points already present in --out and APPEND the "
                         "rest — so a network drop mid-run does not re-submit (or re-pay for) the "
                         "points already collected. Results are written per-point (crash-safe).")
    args = ap.parse_args()

    points = [tuple(p.split(":")) for p in args.points]
    _, observable, cfg = load_frozen_model(models_dir=args.models_dir)
    n = cfg["n_qubits"]; md = pathlib.Path(args.models_dir)
    startag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_star_{cfg['readout']}_L{cfg['n_layers']}"
    X = np.load(md / f"{startag}_reference.npz")["X_eval"][: args.eval_points]
    coeffs = observable_coeffs(observable, n)
    obs_op = readout_observable(n, cfg["readout"])
    # Twirl randomizations use a per-WINDOW seed so each drift window draws an INDEPENDENT set of
    # M Pauli dressings -> between-window std then captures BOTH drift and finite-M randomization
    # variance (honest bands). CDR construction + transpile stay on the fixed args.seed so we track
    # the SAME estimator's drift, not training-set resampling. hashlib (not hash()) for a stable,
    # process-independent window seed.
    twirl_seed = args.seed + int(hashlib.sha256(args.window_id.encode()).hexdigest(), 16) % 100000
    rng = np.random.default_rng(twirl_seed)

    def build_circ_w(pattern):
        ptag = f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_{pattern}_{cfg['readout']}_L{cfg['n_layers']}"
        wpath = md / f"{ptag}_weights.npy"
        weights = np.load(wpath) if wpath.exists() else np.load(md / cfg["weights_file"])
        ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                      entanglement=pattern, entangling_gate=cfg.get("entangling_gate", "cx"))
        c = ans.build()
        xp = ans.feature_parameters(c); wp = ans.weight_parameters(c)
        return c.assign_parameters(dict(zip(wp, weights))), xp

    if args.submit:
        from iqm_resonance import get_backend, transpile_for_backend, run_circuits
        backend = get_backend(args.device)
        def tpile(c, layout): return transpile_for_backend(c, backend, initial_layout=layout)
        def run(circs): return run_circuits(backend, circs, args.shots)
    else:
        cmap = device_coupling_map(args.device)
        def tpile(c, layout):
            return transpile(c, basis_gates=IQM_BASIS_GATES, coupling_map=cmap,
                             initial_layout=layout, optimization_level=1, seed_transpiler=args.seed)
        if args.sim:
            # full-pipeline validation on a NOISY simulator (no credits): exercises twirl,
            # fold, readout, CDR, ZNE on every point incl. adverse routing, exactly as hardware.
            ndev = max(max(e) for e in cmap) + 1
            if args.sim_coh > 0:
                # POSITIVE control: inject a COHERENT Z over-rotation on every cz (Rz(coh)⊗Rz(coh)).
                # Pauli twirl converts this coherent rotation into stochastic dephasing -> restores
                # CDR linearity, so twirl SHOULD help here (unlike the depolarizing null). Same
                # matched pipeline -> directly brackets the hardware result (depol Δr²≈0 vs coherent
                # Δr²>0). Coherent error only (no depol) isolates the coherent contribution.
                from qiskit_aer import AerSimulator
                from qiskit_aer.noise import NoiseModel, coherent_unitary_error
                rz = np.diag([np.exp(-1j * args.sim_coh / 2), np.exp(1j * args.sim_coh / 2)])
                nm = NoiseModel()
                nm.add_all_qubit_quantum_error(coherent_unitary_error(np.kron(rz, rz)), ["cz"])
                _sim = AerSimulator(noise_model=nm)
            else:
                from noisy_sim import make_noisy_simulator, DeviceCalibration
                _sim = make_noisy_simulator(
                    DeviceCalibration(num_qubits=ndev, coupling_map=cmap, p_2q=0.01))
            def run(circs):
                return [_sim.run(c, shots=args.shots).result().get_counts() for c in circs]
        else:
            run = None

    # ---- noiseless twirl SANITY (once) ---- #
    cw0, xp0 = build_circ_w(points[0][1])
    test = transpile(cw0.assign_parameters(dict(zip(xp0, X[0]))), basis_gates=IQM_BASIS_GATES,
                     coupling_map=star_coupling_map(n, 0), optimization_level=1, seed_transpiler=args.seed)
    ideal0 = float(np.real(Statevector.from_instruction(test).expectation_value(obs_op)))
    tw0 = twirl_native(test, np.random.default_rng(1)); tw0.remove_final_measurements(inplace=True)
    sane = abs(float(np.real(Statevector.from_instruction(tw0).expectation_value(obs_op))) - ideal0) < 1e-9
    print(f"twirl sanity (noiseless): {'OK' if sane else 'FAIL — ABORT'}")
    if not sane:
        raise SystemExit("twirl construction broke the ideal — aborting")

    # ---- cost estimate ---- #
    per_pt = 0
    jobs = 0  # ACTUAL job count: one batched run() per (placement, arm, twirl), chunked <=100
    for arm in args.arms:
        has_on = arm in args.twirl_arms
        off_c = args.n_twirl if (args.match_shots and has_on) else 1  # OFF matches ON only if paired
        on_c = args.n_twirl if has_on else 0
        base = (args.n_train + 1) if arm == "cdr" else (len(SCALE_FACTORS) if arm == "zne" else 1)
        per_pt += base * (off_c + on_c) * len(X)
        for k in (off_c, on_c):  # OFF and ON are separate batched submissions
            if k > 0:
                jobs += math.ceil(base * k * len(X) / 100) * len(points)
    off_mult = args.n_twirl if args.match_shots else 1  # for the PLAN print (paired arms)
    tot_circuits = per_pt * len(points)
    total_shots = tot_circuits * args.shots
    est = total_shots * 0.0002 + jobs * 0.33
    print(f"\nPLAN: {args.device} | points {args.points} | arms {args.arms} | "
          f"{len(X)} eval pts | shots {args.shots} | M_twirl {args.n_twirl} | n_train {args.n_train} "
          f"| match_shots {args.match_shots} (OFF averages {off_mult} copy/ies)")
    print(f"  circuits {tot_circuits} ({per_pt}/point) | shots {total_shots} | jobs {jobs}")
    print(f"  ESTIMATED COST: ~{est:.1f} credits")

    if not (args.submit or args.sim):
        print("\n[DRY-RUN] built + sanity OK, nothing submitted. Add --submit (or --sim) to run.")
        return

    # ---- SUBMIT (or --sim noisy-simulator validation) ---- #
    if args.submit:
        print("\n>>> note your credit balance NOW <<<\n")
    else:
        print("\n[--sim] running full pipeline on noisy simulator (no credits)\n")
    fieldnames = (["window", "placement", "pattern", "transpiled_cz", "arm", "twirl",
                   "err", "cdr_r2", "n_avg", "shots"]
                  + [f"abs_lam{s}" for s in SCALE_FACTORS] + ["retention_R"])
    done = set()
    if args.resume and os.path.exists(args.out):
        with open(args.out, newline="") as f:
            for r in csv.DictReader(f):
                done.add((r["placement"], r["pattern"]))
        print(f"[resume] {len(done)} point(s) already in {args.out}: {sorted(done)}")
    _new = not (os.path.exists(args.out) and os.path.getsize(args.out) > 0)
    fout = open(args.out, "a", newline="")
    writer = csv.DictWriter(fout, fieldnames=fieldnames)
    if _new:
        writer.writeheader(); fout.flush()
    for placement, pattern in points:
        if (placement, pattern) in done:
            print(f"  [skip] {placement}:{pattern} — already in {args.out}")
            continue
        circ_w, xp = build_circ_w(pattern)
        layout = hardware_placement(args.device, placement)

        def measured(bound, fold=1):
            c = bound.copy()
            if fold > 1:
                c = fold_global(c, fold)
            c.measure_all()
            return tpile(c, layout)

        def eval_groups(specs):
            """Batched executor. specs = list of (bound, twirl, fold, kcopies). Each spec expands to
            kcopies circuits (M native-r-twirled if twirl, else kcopies identical untwirled), ALL
            flattened and submitted in ONE run() (which chunks <=100/job) -> ~13x fewer QPU jobs than
            one submit per group. Same math: run_circuits returns counts in submission order, so each
            spec's ⟨O⟩ is the mean over its own kcopies (twirl average / shot-matched OFF baseline).
            Twirl is LOGICAL (wrap logical cx), then measured()->transpile_for_backend (pilot-proven
            path); readout via perqubit_z_from_counts (clbit/logical order, NOT physical wire)."""
            flat, ksizes = [], []
            for bound, twirl, fold, kcopies in specs:
                if twirl:
                    reps = [twirl_native(bound, rng) for _ in range(args.n_twirl)]
                elif kcopies > 1:
                    reps = [bound] * kcopies
                else:
                    reps = [bound]
                ksizes.append(len(reps))
                flat.extend(measured(b, fold) for b in reps)
            counts = run(flat)
            vals = [float(np.dot(coeffs, perqubit_z_from_counts(c, n))) for c in counts]
            out, i = [], 0
            for k in ksizes:
                out.append(float(np.mean(vals[i:i + k]))); i += k
            return out

        n2q = sum(1 for i in measured(circ_w.assign_parameters(dict(zip(xp, X[0])))).data
                  if i.operation.name in ("cz", "cx"))
        targets = [circ_w.assign_parameters(dict(zip(xp, x))) for x in X]
        ideals = [float(np.real(Statevector.from_instruction(t).expectation_value(obs_op)))
                  for t in targets]
        prows = []
        for arm in args.arms:
            has_on = arm in args.twirl_arms
            off_copies = args.n_twirl if (args.match_shots and has_on) else 1
            twirls = (False, True) if has_on else (False,)  # non-twirl arms: OFF only (breakdown band)
            for twirl in twirls:
                errs, r2s, zne_diag = [], [], {}
                if arm == "cdr":
                    specs, per_x = [], []
                    for target in targets:
                        train = near_clifford_training_circuits(target, n_train=args.n_train, seed=args.seed)
                        iv = [clifford_ideal_expval(t, obs_op) for t in train]
                        base = len(specs)
                        specs.extend((t, twirl, 1, off_copies) for t in train)
                        specs.append((target, twirl, 1, off_copies))  # target last in each block
                        per_x.append((base, len(train), iv))
                    vals = eval_groups(specs)
                    for (base, ntr, iv), ideal in zip(per_x, ideals):
                        nv = vals[base:base + ntr]; tv = vals[base + ntr]
                        a, b, rr = fit_cdr(nv, iv); r2s.append(rr)
                        errs.append(abs(ideal - apply_cdr(tv, a, b)))
                elif arm == "zne":
                    specs = [(target, twirl, s, off_copies) for target in targets for s in SCALE_FACTORS]
                    vals = eval_groups(specs)
                    ns = len(SCALE_FACTORS)
                    for xi, ideal in enumerate(ideals):
                        zv = vals[xi * ns:(xi + 1) * ns]
                        errs.append(abs(ideal - extrapolate(SCALE_FACTORS, zv, "richardson")))
                    # Signal-retention diagnostic (Köster & Mauerer, arXiv:2607.09360): if <O> has
                    # collapsed toward the observable floor (0 for mean-Z) at the largest folding
                    # scale, Richardson degenerates into a rescaling of a single measurement and the
                    # reported ZNE improvement is an artefact. Keep the per-scale magnitudes so the
                    # check is possible post-hoc — they were previously discarded.
                    per_scale = [float(np.mean([abs(vals[xi * ns + k]) for xi in range(len(ideals))]))
                                 for k in range(ns)]
                    zne_diag = {f"abs_lam{SCALE_FACTORS[k]}": round(per_scale[k], 4) for k in range(ns)}
                    zne_diag["retention_R"] = round(per_scale[-1] / per_scale[0], 4) if per_scale[0] > 0 else ""
                else:  # raw: uncorrected ⟨O⟩-error (breakdown baseline, drift-banded across windows)
                    vals = eval_groups([(t, twirl, 1, off_copies) for t in targets])
                    errs = [abs(ideal - v) for ideal, v in zip(ideals, vals)]
                row = {"window": args.window_id,
                       "placement": placement, "pattern": pattern, "transpiled_cz": n2q,
                       "arm": arm, "twirl": twirl, "err": round(float(np.mean(errs)), 4),
                       "cdr_r2": round(float(np.mean(r2s)), 4) if r2s else "",
                       "n_avg": args.n_twirl if twirl else off_copies,
                       "shots": args.shots, **zne_diag}
                prows.append(row)
                print(f"  {placement:>8} {pattern:>11} cz={n2q:>3} | {arm:>3} twirl={str(twirl):>5} "
                      f"| err {row['err']:.4f} | r2 {row['cdr_r2']}")
        writer.writerows(prows); fout.flush()  # persist THIS point immediately (crash-safe)
        print(f"  [saved] {placement}:{pattern} -> {args.out}")

    fout.close()
    print(f"\nwrote/updated {args.out}")
    print("READ: hypothesis holds if twirl improves err/r2, and the improvement GROWS with CZ.")


if __name__ == "__main__":
    main()
