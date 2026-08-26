"""IQM Resonance submit adapter for Garnet/Emerald via qiskit-iqm (methodology §7).

ODRA uses ``iqm-client`` (Month-1 ``run_hardware.py``); Garnet/Emerald are on IQM
Resonance and are driven through the **qiskit-iqm** provider instead. This module
is the thin, isolated adapter the generalized runners call so the rest of the code
stays provider-agnostic.

⚠️ ENVIRONMENT. ``qiskit-iqm`` must be installed where you run hardware (it failed
to build on py3.13 in Month 1 — use a py3.11 venv). Auth via the Resonance API
token. Set:
    export IQM_RESONANCE_URL="<per-device Resonance endpoint>"
    export IQM_TOKEN="<Resonance API token>"

Design: transpile against the **backend's live coupling map** (real connectivity,
not the idealized grid), pin qubits with the hand-given HARDWARE_PLACEMENTS
(validated against that live map), submit, and return per-circuit counts. This
module does NOT run automatically — the runners call ``submit`` only under
``--submit`` (a gated action).
"""

from __future__ import annotations

import os

from qiskit import QuantumCircuit, transpile


def _require_qiskit_iqm():
    try:
        from iqm.qiskit_iqm import IQMProvider  # qiskit-iqm >= 15
        return IQMProvider
    except Exception:
        try:
            from qiskit_iqm import IQMProvider  # older layout
            return IQMProvider
        except Exception as exc:  # pragma: no cover - env-dependent
            raise ImportError(
                "qiskit-iqm is required for Garnet/Emerald (IQM Resonance) and is not "
                "importable here. Install it in a compatible env (py3.11): "
                "`pip install qiskit-iqm`. Month-1 note: it does not build on py3.13."
            ) from exc


def get_backend(device: str, url: str | None = None, token: str | None = None):
    """Return a live qiskit-iqm backend for a Resonance device.

    ``url`` defaults to $IQM_RESONANCE_URL, ``token`` to $IQM_TOKEN. The returned
    backend carries the device's real coupling map / target used for transpilation.
    """
    IQMProvider = _require_qiskit_iqm()
    url = url or os.environ.get("IQM_RESONANCE_URL", "")
    if not url:
        raise SystemExit("set IQM_RESONANCE_URL (per-device Resonance endpoint) to submit.")
    # URL must be the BASE server URL (no /garnet suffix); the device is chosen via
    # the quantum_computer parameter. The IQM client auto-reads IQM_TOKEN from the
    # environment, and passing token= AND having IQM_TOKEN set is a hard error
    # ("must not mix sources"), so only pass an explicit token when it is not in env.
    if token and not os.environ.get("IQM_TOKEN"):
        return IQMProvider(url, quantum_computer=device, token=token).get_backend()
    return IQMProvider(url, quantum_computer=device).get_backend()


def backend_coupling_map(backend) -> list[list[int]]:
    """Live coupling map (bidirectional [a,b] edges) from a qiskit-iqm backend."""
    cm = backend.coupling_map
    return [list(e) for e in cm.get_edges()]


MAX_CIRCUITS_PER_JOB = 100  # IQM Resonance declines jobs above this.


def run_circuits(backend, circuits, shots, max_per_job: int = MAX_CIRCUITS_PER_JOB) -> list[dict]:
    """Run circuits in sub-jobs of <= max_per_job and return a flat list of counts.

    IQM Resonance caps a single job at 100 circuits, so large batches (e.g. 100 eval
    points x 3 ZNE scales = 300) must be chunked. Counts are returned in submission
    order, so downstream index math is unchanged.
    """
    counts: list[dict] = []
    for i in range(0, len(circuits), max_per_job):
        chunk = circuits[i:i + max_per_job]
        result = backend.run(chunk, shots=shots).result()
        counts.extend(result.get_counts(j) for j in range(len(chunk)))
    return counts


def backend_readout_errors(backend) -> list[float] | None:
    """Per-qubit readout error from the live backend (metadata, no QPU cost).

    Best-effort across API shapes (BackendV1 ``properties().readout_error`` and
    BackendV2 ``target["measure"]`` error). Returns a length-num_qubits list, or
    ``None`` if the backend does not expose readout errors (then REM falls back).
    """
    n = backend.num_qubits
    props = getattr(backend, "properties", None)
    if callable(props):
        try:
            p = props()
            if p is not None:
                vals = []
                for q in range(n):
                    try:
                        vals.append(float(p.readout_error(q)))
                    except Exception:
                        vals.append(None)
                if any(v is not None for v in vals):
                    return [v if v is not None else 0.0 for v in vals]
        except Exception:
            pass
    target = getattr(backend, "target", None)
    if target is not None:
        try:
            meas = target["measure"] if "measure" in target else None
        except Exception:
            meas = None
        if meas is not None:
            vals = []
            for q in range(n):
                inst = meas.get((q,)) if hasattr(meas, "get") else None
                err = getattr(inst, "error", None) if inst is not None else None
                vals.append(float(err) if err is not None else None)
            if any(v is not None for v in vals):
                return [v if v is not None else 0.0 for v in vals]
    return None


def transpile_for_backend(
    circuit: QuantumCircuit, backend, initial_layout: list[int] | None = None, seed: int = 42
) -> QuantumCircuit:
    """Transpile against the backend's real target + optional physical placement."""
    return transpile(circuit, backend=backend, initial_layout=initial_layout,
                     optimization_level=1, seed_transpiler=seed)


def submit(
    circuits: list[QuantumCircuit],
    device: str,
    shots: int = 4096,
    *,
    initial_layout: list[int] | None = None,
    url: str | None = None,
    token: str | None = None,
) -> list[dict]:
    """Submit circuits to a Resonance device and return per-circuit counts.

    Circuits must have measurements. Transpiles each against the live backend
    (real coupling map) with the given ``initial_layout`` (a validated
    ``topology.hardware_placement`` result), runs ``shots``, returns counts dicts.
    """
    backend = get_backend(device, url=url, token=token)
    tqcs = [transpile_for_backend(c, backend, initial_layout=initial_layout) for c in circuits]
    job = backend.run(tqcs, shots=shots)
    result = job.result()
    return [result.get_counts(i) for i in range(len(tqcs))]


def collect_calibration(device: str, out_path: str, url: str | None = None,
                        token: str | None = None) -> dict:
    """Best-effort: pull the live coupling map (+ error rates if exposed) to JSON.

    Writes a file loadable by ``noisy_sim.load_iqm_calibration`` (at minimum the
    coupling map; fill T1/T2/error fields from the Resonance calibration set where
    the backend exposes them). Lets the sim use the real lattice connectivity.
    """
    import json

    backend = get_backend(device, url=url, token=token)
    cm = backend_coupling_map(backend)
    data: dict = {"num_qubits": backend.num_qubits, "coupling_map": cm}
    # Where the backend exposes per-qubit properties, populate the arrays the
    # DeviceCalibration schema expects; otherwise leave for hand-fill.
    props = getattr(backend, "properties", None)
    if callable(props):
        try:
            p = props()
            data["_raw_properties_available"] = p is not None
        except Exception:
            pass
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    return data
