"""Pull Garnet's live coupling map and derive placements — METADATA ONLY, no QPU cost.

Reading the backend's connectivity does NOT execute any circuit, so it costs zero
credits. Saves the real coupling map for the simulator and prints hand-checkable
optimal/adverse placements to lock into topology.HARDWARE_PLACEMENTS.

Run in YOUR terminal (with IQM_RESONANCE_URL + IQM_TOKEN set):
    export IQM_RESONANCE_URL="https://resonance.iqm.tech"
    export IQM_TOKEN="<your token>"
    python pull_garnet.py
Then paste the two placement lines back.
"""

from __future__ import annotations

import argparse
import json
import pathlib

from iqm_resonance import backend_coupling_map, backend_readout_errors, get_backend
from topology import derive_placements, topological_distance


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="garnet", help="garnet or emerald")
    args = ap.parse_args()

    b = get_backend(args.device)
    cm = backend_coupling_map(b)
    n = b.num_qubits
    print(f"backend: {b.name} | {n} qubits | {len(cm) // 2} undirected edges")

    p_ro = backend_readout_errors(b)  # per-qubit readout error, or None if unavailable
    if p_ro is not None:
        print(f"readout errors (p_ro): min {min(p_ro):.3f} max {max(p_ro):.3f} "
              f"mean {sum(p_ro) / len(p_ro):.3f}  -> REM enabled")
    else:
        print("readout errors: NOT exposed by backend -> REM will fall back "
              "(pass p_ro by hand, or run REM-off)")

    pl = derive_placements(cm, n, 5)
    opt, adv = pl["optimal"], pl["adverse"]
    d_opt = [topological_distance(cm, n, opt[0], opt[i]) for i in range(1, 5)]
    spread_adv = sum(
        min(topological_distance(cm, n, adv[i], adv[j]) for j in range(5) if j != i)
        for i in range(5)
    )
    print(f"\noptimal (compact, hub->spokes dist {d_opt}): {opt}")
    print(f"adverse (dispersed, min-pair spread {spread_adv}): {adv}")

    pathlib.Path("calibrations").mkdir(exist_ok=True)
    out = pathlib.Path("calibrations") / f"{args.device}.json"
    data = {"num_qubits": n, "coupling_map": cm}
    if p_ro is not None:
        data["p_ro"] = list(p_ro)   # enables REM (classical, no extra shots)
    json.dump(data, out.open("w"), indent=2)
    print(f"\nsaved {out} (coupling map{' + readout errors' if p_ro is not None else ''})")
    print(f"\n>>> Paste the 'optimal' and 'adverse' lines back to lock into "
          f"topology.HARDWARE_PLACEMENTS['{args.device}'].")


if __name__ == "__main__":
    main()
