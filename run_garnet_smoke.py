"""Garnet smoke test — ONE circuit, 1000 shots. First real QPU submission.

Purpose (methodology_month_2.md §7, staged rollout):
  * confirm the pipeline reaches Garnet and returns counts,
  * verify bit order / readout is sane (measured <O> should be close to the ideal),
  * MEASURE the real cost — note your credit balance before and after (pricing is
    per QPU-second), so we can calibrate the campaign budget against 3700.50.

Costs only a tiny number of credits (1 shallow circuit, 1000 shots). Run in YOUR
terminal with IQM_RESONANCE_URL + IQM_TOKEN set. This SUBMITS to hardware.

    python run_garnet_smoke.py

Uses the star-pattern VQC at one eval point with the OPTIMAL Garnet placement.
Measurements are added before transpilation, so the count bitstrings are already in
logical-qubit order (clbit i = logical qubit i, wherever routing moved it).
"""

from __future__ import annotations

import pathlib
import time

import numpy as np
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from iqm_resonance import get_backend, transpile_for_backend
from noisy_sim import expval_z_from_counts, load_frozen_model, observable_coeffs
from topology import hardware_placement

SHOTS = 1000


def main() -> None:
    _, observable, cfg = load_frozen_model()
    n = cfg["n_qubits"]
    tag = (f"two_curves_d{cfg['n_features']}_q{n}_deg{cfg['degree']}_"
           f"{cfg['entanglement']}_{cfg['readout']}_L{cfg['n_layers']}")
    ref = np.load(pathlib.Path("trained_models") / f"{tag}_reference.npz")
    x0 = ref["X_eval"][0]
    weights = np.load(pathlib.Path("trained_models") / cfg["weights_file"])

    ans = HardwareEfficientAnsatz(n, cfg["n_layers"], num_features=cfg["n_features"],
                                  entanglement=cfg["entanglement"],
                                  entangling_gate=cfg.get("entangling_gate", "cx"))
    circ = ans.build()
    xparams = ans.feature_parameters(circ)
    wparams = ans.weight_parameters(circ)
    bound = circ.assign_parameters({**dict(zip(wparams, weights)), **dict(zip(xparams, x0))})

    ideal = float(np.real(Statevector.from_instruction(bound).expectation_value(observable)))

    backend = get_backend("garnet")
    layout = hardware_placement("garnet", "optimal")
    bound.measure_all()  # clbit i <- logical qubit i (survives routing)
    tqc = transpile_for_backend(bound, backend, initial_layout=layout)
    n2q = sum(1 for i in tqc.data if i.operation.name in ("cz", "cx"))

    print(f"backend {backend.name} | placement optimal {layout} | "
          f"transpiled 2q={n2q} | {SHOTS} shots")
    print(">>> note your credit balance NOW, before submitting <<<\n")

    t0 = time.time()
    job = backend.run(tqc, shots=SHOTS)
    counts = job.result().get_counts()
    wall = time.time() - t0

    coeffs = observable_coeffs(observable, n)
    ev = expval_z_from_counts(counts, coeffs)
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
    print(f"top counts (logical-qubit order): {top}")
    print(f"<O> measured = {ev:+.3f} | ideal = {ideal:+.3f} | |err| = {abs(ev - ideal):.3f}")
    print(f"wall time {wall:.1f}s (includes queue — NOT the billable cost)")
    print("\n>>> note your credit balance AGAIN — the difference is the real cost of "
          f"1 circuit x {SHOTS} shots. Divide by {SHOTS} for credits/shot. <<<")


if __name__ == "__main__":
    main()
