"""Power of the w02vn primary test under the ODRA device model -- Aer, offline.

For each design (shots per point B, number of points) the window is replayed many times
from exact simulated outcome distributions: each replay draws fresh shot noise, computes
plain CDR (all base copies) and 2-axis vnCDR (equal budget split over 3 levels), and runs
the pre-registered one-sided Wilcoxon. Power = share of replays with p < 0.05 and
geometric ratio < 1.

    python -m nicdr.power_vn
"""
from __future__ import annotations

import csv
import json

import numpy as np
from qiskit.quantum_info import Statevector
from scipy.stats import wilcoxon

from nicdr.common import OUT_SIM, REPO, multi_reg, ols_line
from nicdr.sim_budget_scan import CAL, EXACT_SHOTS, N_TRAIN, outcome_dist, sample_mean

PAIRS = 12
EVALS = [0, 1, 3, 4, 6, 7, 9, 10, 12, 13, 15, 16, 18, 19, 21, 22]
DESIGNS = [(1_032_192, 16), (2_064_384, 8), (2_064_384, 16), (4_128_768, 8), (4_128_768, 16)]
REPLAYS = 300


def circuits(t_cz, t_prx):
    from campaign.odra_window import frozen
    from qem.cdr_training import build_training_set, clifford_ideal_expval
    from qem.compile import compile_native
    from qem.identity_insertion import insert_identity
    from noisy_sim import readout_observable
    obs = readout_observable(5, "mean")
    pts = [p for p in json.load(open(REPO / "campaign/eval_points.json"))["points"]
           if p["eval_index"] in EVALS]
    cw, xp = frozen("star")
    specs = []
    for p in pts:
        ei = p["eval_index"]
        lg = cw.assign_parameters(dict(zip(xp, p["x"])))
        ideal_t = float(np.real(Statevector.from_instruction(lg).expectation_value(obs)))
        nat = compile_native(lg).circuit
        train = build_training_set(nat, n_train=N_TRAIN, sampler="near_target", base_seed=42,
                                   target_index=ei, window_id="w02vn")
        for role, ti, base, ideal in [("target", None, nat, ideal_t)] + [
                ("train", i, c, float(clifford_ideal_expval(c, obs))) for i, c in enumerate(train)]:
            for lv in ("base", "cz", "idle"):
                c = base.copy() if lv == "base" else insert_identity(
                    base, PAIRS, "cz_pairs" if lv == "cz" else "idle_matched", t_cz=t_cz)
                c.measure_all()
                specs.append({"ei": ei, "role": role, "ti": ti, "lv": lv, "ideal": ideal, "circ": c})
    return specs


def main():
    from sim.device_model import build_noise_model
    OUT_SIM.mkdir(parents=True, exist_ok=True)
    rows, lines = [], []
    for theta in (0.0, 0.05):
        dev = build_noise_model(str(CAL), theta, 0.0, 0.0)
        specs = circuits(dev.calibration.t_cz, dev.calibration.t_prx)
        for i in range(0, len(specs), 120):
            part = specs[i:i + 120]
            for s, cn in zip(part, dev.run([s["circ"] for s in part], EXACT_SHOTS, seed=7 + i)):
                s["dist"] = outcome_dist(cn)
                s.pop("circ")
        idx = {(s["ei"], s["role"], s["ti"], s["lv"]): s for s in specs}
        for B, npts in DESIGNS:
            evals = EVALS[:npts] if npts == 16 else EVALS[::2]
            rng = np.random.default_rng(int(B) + npts + int(theta * 1000))
            succ, ratios = 0, []
            for _ in range(REPLAYS):
                e_cdr, e_vn = [], []
                for ei in evals:
                    y = np.array([idx[(ei, "train", i, "base")]["ideal"] for i in range(N_TRAIN)])
                    ideal = idx[(ei, "target", None, "base")]["ideal"]
                    n1, n3 = B // (N_TRAIN + 1), B // (3 * (N_TRAIN + 1))
                    xb = [sample_mean(idx[(ei, "train", i, "base")]["dist"], n1, rng) for i in range(N_TRAIN)]
                    tb = sample_mean(idx[(ei, "target", None, "base")]["dist"], n1, rng)
                    a, b = ols_line(xb, y)
                    e_cdr.append(abs(a * tb + b - ideal))
                    X = np.array([[sample_mean(idx[(ei, "train", i, lv)]["dist"], n3, rng)
                                   for lv in ("base", "cz", "idle")] for i in range(N_TRAIN)])
                    xt = np.array([[sample_mean(idx[(ei, "target", None, lv)]["dist"], n3, rng)
                                    for lv in ("base", "cz", "idle")]])
                    e_vn.append(abs(float(multi_reg(X, y, xt)[0][0]) - ideal))
                d = np.log(np.maximum(e_vn, 1e-3)) - np.log(np.maximum(e_cdr, 1e-3))
                p = wilcoxon(d, alternative="less").pvalue if np.any(d != 0) else 1.0
                ratios.append(float(np.exp(d.mean())))
                succ += int(p < 0.05 and np.exp(d.mean()) < 1)
            row = {"theta": theta, "budget_per_point": B, "points": npts,
                   "power": succ / REPLAYS, "median_geo_ratio": float(np.median(ratios))}
            rows.append(row)
            line = (f"theta={theta:<4} B={B:>9,d} points={npts:2d}  power={row['power']:.2f}  "
                    f"median geo ratio={row['median_geo_ratio']:.2f}")
            print(line, flush=True)
            lines.append(line)
    with (OUT_SIM / "power_vn.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT_SIM / "power_vn.log").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
