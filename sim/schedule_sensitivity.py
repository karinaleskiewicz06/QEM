"""How much does the assumed gate timing move the simulated result?

``sim.device_model`` relaxes idle qubits according to a schedule. How IQM's server
places gates in time is not documented to us, so the model cannot claim the right
one. This script measures what the choice costs instead: for every ladder rung and the
classifier's reference points it runs the same circuits under ALAP, ASAP and no idle
noise, and reports the raw error under each and the mean |<O>_ALAP - <O>_ASAP|.

    python -m sim.schedule_sensitivity
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
import pandas as pd
from qiskit.quantum_info import Statevector

from noisy_sim import perqubit_z_from_counts, readout_observable
from qem.compile import compile_native
from sim.bench_cdr_variants import frozen_circuit, reference_points
from sim.device_model import build_noise_model

LADDER = ("star", "linear", "circular", "all_to_all")
OUT = pathlib.Path("results_sim/device_model/schedule_sensitivity.csv")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibration", default="calibrations/odra_raw_20260803.json")
    ap.add_argument("--points", type=int, default=24)
    ap.add_argument("--shots", type=int, default=8192)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    models = {"alap": build_noise_model(args.calibration, schedule="alap"),
              "asap": build_noise_model(args.calibration, schedule="asap"),
              "noidle": build_noise_model(args.calibration, with_idle=False)}
    obs = readout_observable(5, "mean")
    coeffs = np.full(5, 0.2)
    X = reference_points()[: args.points]
    rows = []
    for pattern in LADDER:
        cw, xp = frozen_circuit(pattern)
        natives = [compile_native(cw.assign_parameters(dict(zip(xp, x)))).circuit for x in X]
        ideal = np.array([float(np.real(Statevector.from_instruction(c).expectation_value(obs)))
                          for c in natives])
        measured = []
        for c in natives:
            m = c.copy()
            m.measure_all()
            measured.append(m)
        ev = {}
        for name, dev in models.items():
            counts = dev.run(measured, args.shots, seed=args.seed)
            ev[name] = np.array([float(np.dot(coeffs, perqubit_z_from_counts(c, 5)))
                                 for c in counts])
        idle_ns = {name: float(np.mean([sum(i.operation.duration for i in dev.prepare(m).data
                                            if i.operation.name == "delay")
                                        for m in measured[:4]]))
                   for name, dev in models.items() if dev.with_idle}
        row = {"pattern": pattern, "cz": natives[0].count_ops().get("cz", 0),
               **{f"err_{k}": float(np.mean(np.abs(v - ideal))) for k, v in ev.items()},
               "mean_abs_alap_minus_asap": float(np.mean(np.abs(ev["alap"] - ev["asap"]))),
               "mean_abs_alap_minus_noidle": float(np.mean(np.abs(ev["alap"] - ev["noidle"]))),
               **{f"idle_ns_{k}": v for k, v in idle_ns.items()},
               "points": args.points, "shots": args.shots}
        rows.append(row)
        print(f"{pattern:<11} cz={row['cz']:>3} | err alap {row['err_alap']:.4f} "
              f"asap {row['err_asap']:.4f} noidle {row['err_noidle']:.4f} | "
              f"|alap-asap| {row['mean_abs_alap_minus_asap']:.4f} | idle ns "
              f"{idle_ns['alap']:.0f} / {idle_ns['asap']:.0f}")
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {out}")
    print(f"shot noise of one <O> at {args.shots} shots is ~{1 / np.sqrt(5 * args.shots):.4f}")


if __name__ == "__main__":
    main()
