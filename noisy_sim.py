"""Device-calibrated noisy simulator for the Tier-A 5-qubit star (ODRA / IQM Spark-class).

Month-1 deliverable (plan.md §9): build a noise-calibrated classical simulator that
reproduces Tier-A error rates, so the VQC-ZNE pipeline can be validated end-to-end
*in simulation* before any hardware time is spent.

Design
------
* IQM Spark-class native gate set: single-qubit **PRX** (Qiskit ``r``) + two-qubit **CZ**.
* Star coupling: hub = physical qubit 0, outer qubits 1..4.
* Noise per component:
    - 1q gate: thermal relaxation (T1/T2 over gate duration) ∘ depolarizing.
    - 2q gate (CZ): 2q depolarizing ∘ (thermal ⊗ thermal).
    - idle: thermal relaxation on ``id`` (and scheduled ``delay`` expanded to ``id``),
      so Dynamical Decoupling has something to suppress in simulation.
    - readout: per-qubit bit-flip confusion matrix.

The default :class:`DeviceCalibration` holds **placeholder** Spark-class numbers, clearly
flagged. Replace them with live ODRA calibration (see :func:`load_iqm_calibration` /
``collect_odra_calibration.py``) before using any results quantitatively.

On real ODRA hardware, idle decoherence is physical and always present; the idle-``id``
model is only needed so simulated DD/REM dry-runs are meaningful.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import SparsePauliOp
from qiskit.transpiler import InstructionDurations
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    coherent_unitary_error,
    depolarizing_error,
    thermal_relaxation_error,
)

from ansatz import HardwareEfficientAnsatz
# star_coupling_map now lives in topology.py (single source of truth for the
# cross-topology port, plan_month_2.md W1); re-exported here for back-compat.
from topology import star_coupling_map  # noqa: F401  (re-export)

# IQM native basis. Qiskit ``r`` == PRX(theta, phi); ``cz`` == CZ.
# ``id`` is kept so scheduled idle windows can carry thermal noise.
IQM_BASIS_GATES: list[str] = ["r", "cz", "id", "measure"]
# Time unit for InstructionDurations / id padding (nanoseconds).
DT_NS: float = 1.0


@dataclass
class DeviceCalibration:
    """Per-qubit calibration for the 5-qubit star.

    NOTE: defaults are PLACEHOLDER Spark-class order-of-magnitude values.
    Replace with live ODRA calibration before quantitative use.
    """

    num_qubits: int = 5
    hub: int = 0
    # coherence times (seconds). t2 = Ramsey T2* (free-induction idle dephasing).
    # Per-qubit values may be scalars (broadcast to num_qubits) or length-n arrays.
    t1: np.ndarray | float = 40e-6
    t2: np.ndarray | float = 15e-6
    # Hahn-echo T2 (idle dephasing achievable UNDER dynamical decoupling). If not
    # provided it defaults to t2 (i.e. DD gives no modelled benefit).
    t2_echo: np.ndarray | float | None = None
    # gate durations (seconds)
    t_1q: float = 40e-9
    t_2q: float = 100e-9
    # depolarizing gate error probabilities
    p_1q: np.ndarray | float = 1e-3
    p_2q: float = 1e-2
    # symmetric readout error probability per qubit  P(0|1) = P(1|0)
    p_ro: np.ndarray | float = 3e-2
    # Device coupling map (bidirectional [a,b] edges). If None, defaults to the
    # star on this device's num_qubits/hub (Month-1 ODRA behaviour unchanged).
    # Set it (or load it) for lattice devices — Garnet (4x5) / Emerald (6x9).
    coupling_map: list[list[int]] | None = None

    def __post_init__(self) -> None:
        # allow scalars -> broadcast to arrays
        n = self.num_qubits
        if self.coupling_map is None:
            self.coupling_map = star_coupling_map(n, self.hub)
        self.t1 = np.broadcast_to(np.asarray(self.t1, float), (n,)).copy()
        self.t2 = np.broadcast_to(np.asarray(self.t2, float), (n,)).copy()
        self.p_1q = np.broadcast_to(np.asarray(self.p_1q, float), (n,)).copy()
        self.p_ro = np.broadcast_to(np.asarray(self.p_ro, float), (n,)).copy()
        # physical constraint: T2 <= 2*T1
        self.t2 = np.minimum(self.t2, 2.0 * self.t1)
        if self.t2_echo is None:
            self.t2_echo = self.t2.copy()
        else:
            self.t2_echo = np.broadcast_to(
                np.asarray(self.t2_echo, float), (n,)
            ).copy()
        # echo T2 must also respect T2 <= 2*T1, and never be worse than T2*
        self.t2_echo = np.clip(self.t2_echo, self.t2, 2.0 * self.t1)


def load_iqm_calibration(path: str | pathlib.Path) -> DeviceCalibration:
    """Load a DeviceCalibration from an IQM/ODRA calibration JSON.

    Expected flat schema (produced by ``collect_odra_calibration.py``)::

        {t1, t2, p_1q, p_ro (lists), t_1q, t_2q, p_2q (scalars), num_qubits, hub}

    Extra keys (e.g. ``meta``) are ignored.
    """
    d = json.loads(pathlib.Path(path).read_text())
    return DeviceCalibration(
        num_qubits=int(d.get("num_qubits", 5)),
        hub=int(d.get("hub", 0)),
        t1=np.asarray(d["t1"], float),
        t2=np.asarray(d["t2"], float),
        t2_echo=(np.asarray(d["t2_echo"], float) if "t2_echo" in d else None),
        t_1q=float(d.get("t_1q", 40e-9)),
        t_2q=float(d.get("t_2q", 100e-9)),
        p_1q=np.asarray(d["p_1q"], float),
        p_2q=float(d["p_2q"]),
        p_ro=np.asarray(d["p_ro"], float),
        # A lattice calibration must carry its coupling map; if absent we fall
        # back to the star (via __post_init__) for back-compat with ODRA files.
        coupling_map=(
            [list(e) for e in d["coupling_map"]] if "coupling_map" in d else None
        ),
    )


def synthesize_lattice_calibration(
    device: str,
    *,
    seed: int = 0,
    jitter: float = 0.0,
    **overrides,
) -> DeviceCalibration:
    """PLACEHOLDER Spark-class calibration for a named lattice device (Garnet/Emerald).

    Spark-class scalar error rates broadcast onto the device, carrying the device's
    real grid coupling map (from ``topology``). Lets §1/§3/§4 sim runs work *before*
    live lattice calibration exists. ``jitter`` (fractional, e.g. 0.1) adds seeded
    per-qubit variation to T1/T2/p_1q/p_ro; any field is overridable via kwargs.

    NOTE: clearly a stand-in — replace with real calibration before quantitative use.
    """
    from topology import device_coupling_map, device_num_qubits

    n = device_num_qubits(device)
    base = dict(t1=40e-6, t2=15e-6, p_1q=1e-3, p_2q=1e-2, p_ro=3e-2)
    fields: dict = {"num_qubits": n, "coupling_map": device_coupling_map(device)}
    rng = np.random.default_rng(seed)
    for key, val in base.items():
        if key == "p_2q":  # scalar in the model
            fields[key] = val
            continue
        arr = np.full(n, val, float)
        if jitter:
            arr = arr * (1.0 + jitter * (2.0 * rng.random(n) - 1.0))
        fields[key] = arr
    fields.update(overrides)
    return DeviceCalibration(**fields)


def build_noise_model(
    cal: DeviceCalibration,
    *,
    idle_t2: np.ndarray | None = None,
    with_idle: bool = True,
    coherent_theta: float = 0.0,
) -> NoiseModel:
    """Assemble an Aer :class:`NoiseModel` for the star from a calibration.

    Args:
        idle_t2: T2 used for the idle (``id``) thermal channel. Defaults to
            ``cal.t2`` (Ramsey T2*). Pass ``cal.t2_echo`` to model dynamical
            decoupling (DD), which refocuses low-frequency dephasing so idle
            qubits decohere at the slower Hahn-echo rate.
        with_idle: if False, omit the ``id`` idle channel entirely (ablation).
        coherent_theta: if non-zero, compose a coherent ``Rz(theta) x Rz(theta)``
            over-rotation into every ``cz`` error, on top of the calibrated
            stochastic channels. This yields *nested* noise models — theta=0 and
            theta>0 differ by exactly one term — which is what makes "excess r2
            decay over the device null" a meaningful quantity.

            It must be composed here, per qubit pair, rather than registered as
            an all-qubit error afterwards: Aer silently drops an all-qubit error
            for a gate that already has qubit-specific errors, so adding it later
            would leave the model unchanged while appearing to work.

    Gate (``r``/``cz``) thermal channels always use ``cal.t2`` — DD protects
    *idle* windows, not the gates themselves. Use :func:`schedule_with_idle`
    so idle windows become ``id`` sequences that carry this channel.
    """
    nm = NoiseModel(basis_gates=IQM_BASIS_GATES)
    idle_t2 = cal.t2 if idle_t2 is None else np.broadcast_to(
        np.asarray(idle_t2, float), (cal.num_qubits,)
    )

    # single-qubit gate errors (PRX ~ Qiskit 'r') + idle ('id')
    for q in range(cal.num_qubits):
        relax = thermal_relaxation_error(cal.t1[q], cal.t2[q], cal.t_1q)
        err_1q = relax.compose(depolarizing_error(cal.p_1q[q], 1))
        nm.add_quantum_error(err_1q, ["r"], [q])
        if with_idle:
            # Idle: thermal relaxation over one 1q-gate duration, at idle_t2
            # (T2* by default, echo T2 under DD).
            nm.add_quantum_error(
                thermal_relaxation_error(cal.t1[q], idle_t2[q], cal.t_1q),
                ["id"], [q],
            )
        # readout confusion matrix
        p = cal.p_ro[q]
        nm.add_readout_error(ReadoutError([[1 - p, p], [p, 1 - p]]), [q])

    # optional coherent over-rotation, composed into every cz below
    coh = None
    if coherent_theta:
        rz = np.diag([np.exp(-1j * coherent_theta / 2), np.exp(1j * coherent_theta / 2)])
        coh = coherent_unitary_error(np.kron(rz, rz))

    # two-qubit gate errors (CZ), on both edge orientations
    for a, b in {tuple(sorted(e)) for e in cal.coupling_map}:
        relax_a = thermal_relaxation_error(cal.t1[a], cal.t2[a], cal.t_2q)
        relax_b = thermal_relaxation_error(cal.t1[b], cal.t2[b], cal.t_2q)
        err_2q = depolarizing_error(cal.p_2q, 2).compose(relax_a.tensor(relax_b))
        if coh is not None:
            err_2q = coh.compose(err_2q)   # over-rotation first, then stochastic channels
        nm.add_quantum_error(err_2q, ["cz"], [a, b])
        nm.add_quantum_error(err_2q, ["cz"], [b, a])

    return nm


def instruction_durations(cal: DeviceCalibration) -> InstructionDurations:
    """Gate durations in ``DT_NS`` units for scheduling / idle padding."""
    t1q = max(1, int(round(cal.t_1q * 1e9 / DT_NS)))
    t2q = max(1, int(round(cal.t_2q * 1e9 / DT_NS)))
    return InstructionDurations(
        [
            ("r", None, t1q),
            ("cz", None, t2q),
            ("id", None, t1q),
            ("measure", None, max(t2q, 1000)),
            ("delay", None, 1),
        ],
        dt=DT_NS * 1e-9,
    )


def schedule_with_idle(
    circuit: QuantumCircuit,
    cal: DeviceCalibration | None = None,
) -> QuantumCircuit:
    """Insert ``id`` gates on idle qubits so Aer applies thermal idle noise.

    For each non-barrier / non-delay op of duration ``D``, every qubit *not*
    participating gets ``round(D / t_1q)`` identity gates (each carrying T1/T2
    noise via the noise model). Measurements are appended unchanged at the end.

    This avoids Qiskit 2.x ``PadDelay`` / ``InstructionDurations`` issues while
    still giving Dynamical Decoupling something non-trivial to suppress in sim.
    On real ODRA, idle decoherence is physical — skip this helper.
    """
    cal = cal or DeviceCalibration()
    t1q = cal.t_1q
    t2q = cal.t_2q
    n = circuit.num_qubits

    compute = QuantumCircuit(n, name=circuit.name)
    measures: list = []
    for inst in circuit.data:
        name = inst.operation.name
        if name == "barrier":
            continue
        if name == "measure":
            measures.append(inst)
            continue
        if name == "delay":
            # Expand an existing delay into ids on that qubit.
            dur = float(getattr(inst.operation, "duration", t1q) or t1q)
            # duration may be in dt units; treat large ints as ns, floats as seconds
            if dur > 1.0:  # likely ns or dt counts
                dur_s = dur * 1e-9
            else:
                dur_s = dur
            n_ids = max(1, int(round(dur_s / t1q)))
            for _ in range(n_ids):
                compute.id(inst.qubits[0])
            continue

        # Duration of this op
        nq = inst.operation.num_qubits
        dur_s = t2q if nq >= 2 else t1q
        active = {compute.find_bit(q).index for q in inst.qubits}
        n_ids = max(1, int(round(dur_s / t1q)))
        for q in range(n):
            if q not in active:
                for _ in range(n_ids):
                    compute.id(q)
        compute.append(inst.operation, inst.qubits, inst.clbits)

    # Re-attach classical registers / measurements if present
    if circuit.num_clbits:
        out = QuantumCircuit(*circuit.qregs, *circuit.cregs, name=circuit.name)
        for inst in compute.data:
            out.append(inst.operation, inst.qubits, inst.clbits)
        for inst in measures:
            out.append(inst.operation, inst.qubits, inst.clbits)
        return out
    return compute


def make_noisy_simulator(
    cal: DeviceCalibration | None = None,
    *,
    with_idle: bool = True,
    dd: bool = False,
) -> AerSimulator:
    """Return an AerSimulator configured with the star noise model + topology.

    ``with_idle=True`` (default) includes ``id`` thermal errors. Pair with
    :func:`schedule_with_idle` before execution for a meaningful DD dry-run.
    ``dd=True`` models dynamical decoupling: idle qubits decohere at the
    Hahn-echo rate ``cal.t2_echo`` instead of Ramsey ``cal.t2``.
    """
    cal = cal or DeviceCalibration()
    idle_t2 = cal.t2_echo if dd else cal.t2
    nm = build_noise_model(cal, idle_t2=idle_t2, with_idle=with_idle)
    return AerSimulator(
        noise_model=nm,
        coupling_map=cal.coupling_map,
        basis_gates=IQM_BASIS_GATES,
    )


# --------------------------------------------------------------------------- #
# Frozen-model loading + expectation-value execution (executor for ZNE later)  #
# --------------------------------------------------------------------------- #

def load_frozen_model(
    models_dir: str | pathlib.Path = "trained_models",
    tag: str | None = None,
) -> tuple[QuantumCircuit, SparsePauliOp, dict]:
    """Rebuild the trained (weight-bound) circuit + observable from a saved model.

    Returns ``(bound_circuit, observable, config)`` where ``bound_circuit`` still
    has its feature parameters ``x[...]`` free (bind per data point at inference).
    If ``tag`` is None, picks the highest test-accuracy model in ``models_dir``.
    """
    models_dir = pathlib.Path(models_dir)
    lock_file = models_dir / "LOCKED.json"
    if tag is None and lock_file.exists():
        # Prefer the explicit lock pointer (methodological: select by tag, not acc).
        tag = json.loads(lock_file.read_text()).get("locked_tag")
    if tag is not None:
        cfg = json.loads((models_dir / f"{tag}.json").read_text())
    else:
        candidates = []
        for jf in models_dir.glob("*_q*_*.json"):  # only new-schema files
            if jf.name == "LOCKED.json":
                continue
            try:
                c = json.loads(jf.read_text())
                candidates.append((c.get("test_acc", -1), jf, c))
            except Exception:
                continue
        if not candidates:
            raise FileNotFoundError(f"no frozen models found in {models_dir}")
        _, _, cfg = max(candidates, key=lambda t: t[0])

    ans = HardwareEfficientAnsatz(
        num_qubits=cfg["n_qubits"],
        num_layers=cfg["n_layers"],
        num_features=cfg["n_features"],
        entanglement=cfg["entanglement"],
        entangling_gate=cfg.get("entangling_gate", "cx"),
    )
    circ = ans.build()
    weights = np.load(models_dir / cfg["weights_file"])
    wparams = ans.weight_parameters(circ)
    bound = circ.assign_parameters(dict(zip(wparams, weights)))

    observable = readout_observable(cfg["n_qubits"], cfg["readout"])
    return bound, observable, cfg


def readout_observable(num_qubits: int, readout: str) -> SparsePauliOp:
    """Build the study observable: 'hub' -> Z on qubit 0; 'mean' -> (1/n) Σ Zᵢ."""
    if readout == "hub":
        lab = ["I"] * num_qubits
        lab[num_qubits - 1] = "Z"  # qubit 0 is rightmost in Qiskit label order
        return SparsePauliOp.from_list([("".join(lab), 1.0)])
    # mean-Z
    terms = []
    for q in range(num_qubits):
        lab = ["I"] * num_qubits
        lab[num_qubits - 1 - q] = "Z"
        terms.append(("".join(lab), 1.0 / num_qubits))
    return SparsePauliOp.from_list(terms)


def expval_z_from_counts(counts: dict[str, int], coeffs: np.ndarray) -> float:
    """Expectation of Σ_q coeffs[q]·Z_q from measurement counts.

    ``coeffs`` is length n (qubit 0 == least-significant bit, Qiskit convention).
    Bitstrings in ``counts`` are big-endian (qubit n-1 .. qubit 0).
    """
    n = len(coeffs)
    total = sum(counts.values())
    acc = 0.0
    for bitstr, c in counts.items():
        bits = bitstr.replace(" ", "")[-n:].zfill(n)
        # bits[0] is qubit n-1 ; z_q = +1 if bit 0 else -1
        val = 0.0
        for q in range(n):
            bit = int(bits[n - 1 - q])
            val += coeffs[q] * (1.0 - 2.0 * bit)
        acc += val * c
    return acc / total


def perqubit_z_from_counts(counts: dict[str, int], n: int) -> np.ndarray:
    """Per-qubit ⟨Z_q⟩ (length n, qubit 0 = LSB) from measurement counts."""
    total = sum(counts.values())
    z = np.zeros(n)
    for bitstr, c in counts.items():
        bits = bitstr.replace(" ", "")[-n:].zfill(n)
        for q in range(n):
            bit = int(bits[n - 1 - q])
            z[q] += (1.0 - 2.0 * bit) * c
    return z / total


def counts_on_wires(counts: dict[str, int], wires: list[int],
                    device_width: int) -> dict[str, int]:
    """Re-key device-width counts onto the logical qubits that sit on ``wires``.

    An embedded circuit is measured across the whole device, so its raw keys are
    device-width bitstrings indexed by physical wire. Archiving those would make a
    record unreadable without the placement. This projects each key onto the logical
    register -- logical qubit ``q`` takes the bit of wire ``wires[q]`` -- and sums the
    shots that collapse onto the same logical string.

    Bit order follows the rest of this module: qubit ``q`` is character ``-1 - q``.
    """
    out: dict[str, int] = {}
    n = len(wires)
    for bits, c in counts.items():
        s = str(bits).replace(" ", "")
        chars = ["0"] * n
        for q in range(n):
            chars[n - 1 - q] = s[device_width - 1 - wires[q]]
        key = "".join(chars)
        out[key] = out.get(key, 0) + int(c)
    return out


def perqubit_z_on_wires(
    counts: dict[str, int], wires: list[int], device_width: int
) -> np.ndarray:
    """Per-qubit ⟨Z⟩ for specific physical ``wires`` (LSB = qubit 0) from counts.

    Like :func:`perqubit_z_from_counts`, but reads only the given physical wires of
    a device-width bitstring (used when a small logical circuit is embedded on a
    larger device). Returns one ⟨Z⟩ per wire, in the order given.
    """
    total = sum(counts.values())
    z = np.zeros(len(wires))
    for bitstr, c in counts.items():
        bits = bitstr.replace(" ", "")[-device_width:].zfill(device_width)
        for i, w in enumerate(wires):
            bit = int(bits[device_width - 1 - w])
            z[i] += (1.0 - 2.0 * bit) * c
    return z / total


def logical_final_wires(transpiled: QuantumCircuit, n_logical: int) -> list[int]:
    """Physical measurement wire for each logical qubit after transpilation.

    Reads ``transpiled.layout.final_index_layout()`` so single-qubit readout lands
    on the correct wire *after* routing/SWAPs moved the logical qubits around
    (generalises the Month-1 Banknote readout-wire fix). Falls back to identity
    ``0..n_logical-1`` when the circuit carries no layout (already-native circuits).
    """
    layout = getattr(transpiled, "layout", None)
    if layout is None:
        return list(range(n_logical))
    final = layout.final_index_layout()  # virtual qubit index -> physical wire
    return [int(final[i]) for i in range(n_logical)]


def rem_correct_z(zq: np.ndarray, p_ro: np.ndarray) -> np.ndarray:
    """Readout Error Mitigation for single-qubit Z (symmetric bit-flip model).

    A symmetric bit-flip with probability p attenuates ⟨Z⟩ by (1-2p), so the
    unbiased estimate is ⟨Z⟩_meas / (1-2p). Exact for Z/I observables; the
    denominator is floored to avoid blow-up when p -> 0.5.
    """
    atten = np.clip(1.0 - 2.0 * np.asarray(p_ro, float), 1e-2, 1.0)
    return zq / atten


def observable_coeffs(observable: SparsePauliOp, num_qubits: int) -> np.ndarray:
    """Extract per-qubit Z coefficients from a diagonal (Z/I only) observable."""
    coeffs = np.zeros(num_qubits)
    for pauli, coeff in zip(observable.paulis, observable.coeffs):
        label = pauli.to_label()
        if set(label) - {"I", "Z"}:
            raise ValueError("expval_z_from_counts supports only Z/I observables")
        for q in range(num_qubits):
            if label[num_qubits - 1 - q] == "Z":
                coeffs[q] += float(np.real(coeff))
    return coeffs


def execute_expectation(
    circuit: QuantumCircuit,
    observable: SparsePauliOp,
    sim: AerSimulator,
    shots: int = 4096,
    *,
    cal: DeviceCalibration | None = None,
    apply_idle_schedule: bool = True,
    pre_transpiled: bool = False,
    rem: bool = False,
    initial_layout: list[int] | None = None,
    return_counts: bool = False,
) -> float | tuple[float, dict[str, int]]:
    """Run a (Z/I-observable) circuit on the noisy sim and return ⟨O⟩ from counts.

    This is the executor shape a ZNE loop calls. ``circuit`` must have all
    parameters bound and NO measurements (they are appended here).

    ``pre_transpiled=True`` skips transpilation (use when the circuit is already
    in the native {r,cz} basis, e.g. a folded ZNE circuit whose U†U structure
    must NOT be optimised away).
    When ``apply_idle_schedule=True``, idle windows are expanded to ``id`` gates
    so thermal idle noise (and later DD) is active in simulation.
    ``rem=True`` applies Readout Error Mitigation (per-qubit, using ``cal.p_ro``).

    ``initial_layout`` places an ``n``-qubit logical circuit onto a larger device
    (``cal.num_qubits > n``, the optimal/adverse placement of W2). Readout is then
    taken from each logical qubit's *final* physical wire. When the device size
    matches the circuit, behaviour is exactly the Month-1 same-size path.

    ``return_counts=True`` additionally returns the raw counts dict, so a caller can
    archive the measurement rather than only its reduction (P0 provenance). The counts
    come back in the *logical* convention: for an embedded circuit they are re-keyed
    from physical wires onto logical qubits, so the record is interpretable without
    knowing the placement. The default is False and the return type is unchanged for
    every existing caller.
    """
    n = circuit.num_qubits
    cal = cal or DeviceCalibration()
    embed = cal.num_qubits != n
    if embed and initial_layout is None:
        raise ValueError(
            f"circuit has {n} qubits but device has {cal.num_qubits}; pass "
            "initial_layout (a placement from topology.placement) to embed it."
        )
    if embed and pre_transpiled:
        raise ValueError(
            "embedding (device larger than circuit) needs a fresh transpile to "
            "recover readout wires; pre_transpiled=True is unsupported here."
        )
    meas = circuit.copy()
    if not pre_transpiled:
        meas = transpile(
            meas,
            basis_gates=IQM_BASIS_GATES,
            coupling_map=cal.coupling_map,
            initial_layout=initial_layout,
            optimization_level=1,
        )
    if apply_idle_schedule:
        meas = schedule_with_idle(meas, cal)

    coeffs = observable_coeffs(observable, n)

    if not embed:
        meas.measure_all()
        counts = sim.run(meas, shots=shots).result().get_counts()
        if rem:
            zq = rem_correct_z(perqubit_z_from_counts(counts, n), cal.p_ro)
            value = float(np.dot(coeffs, zq))
        else:
            value = expval_z_from_counts(counts, coeffs)
        return (value, counts) if return_counts else value

    # embedded: n-qubit logical circuit placed on a larger device; read the
    # logical qubits off their post-routing wires.
    wires = logical_final_wires(meas, n)
    device_width = meas.num_qubits
    meas.measure_all()
    counts = sim.run(meas, shots=shots).result().get_counts()
    zq = perqubit_z_on_wires(counts, wires, device_width)
    if rem:
        zq = rem_correct_z(zq, np.asarray(cal.p_ro)[wires])
    value = float(np.dot(coeffs, zq))
    if not return_counts:
        return value
    return value, counts_on_wires(counts, wires, device_width)


def expectation_error(noisy_ev: float, ideal_ev: float) -> float:
    """Absolute error |⟨O⟩_noisy − ⟨O⟩_ideal| — primary ZNE y-signal (plan §7).

    Accuracy is a *derived* secondary metric (sign decision on ⟨O⟩). Prefer this
    continuous signal for locating breakdown regions.
    """
    return abs(float(noisy_ev) - float(ideal_ev))


def mean_expectation_error(
    ideal_evs: np.ndarray | list[float],
    noisy_evs: np.ndarray | list[float],
) -> float:
    """Mean absolute expectation-value error over a dataset."""
    ideal = np.asarray(ideal_evs, float)
    noisy = np.asarray(noisy_evs, float)
    return float(np.mean(np.abs(noisy - ideal)))


# --------------------------------------------------------------------------- #
# Sanity check (plan.md §9: simulated readout/2q errors match device specs)     #
# --------------------------------------------------------------------------- #

def sanity_check(cal: DeviceCalibration | None = None, shots: int = 20000) -> None:
    """Empirically verify readout error and that idle scheduling increases noise."""
    cal = cal or DeviceCalibration()
    sim = make_noisy_simulator(cal)
    print("=== noisy_sim sanity check (PLACEHOLDER calibration) ===")
    print(f"coupling ({len(cal.coupling_map) // 2} edges): {cal.coupling_map}")

    # Readout: prepare |1> on each qubit, measure, estimate P(0|1) vs spec p_ro.
    print("\nreadout error  (spec -> measured P(0|1)):")
    for q in range(cal.num_qubits):
        qc = QuantumCircuit(cal.num_qubits, 1)
        qc.x(q)
        qc.measure(q, 0)
        tqc = transpile(qc, basis_gates=IQM_BASIS_GATES,
                        coupling_map=cal.coupling_map)
        counts = sim.run(tqc, shots=shots).result().get_counts()
        p01 = counts.get("0", 0) / shots
        print(f"  q{q}: {cal.p_ro[q]:.3f} -> {p01:.3f}")

    # Idle effect: exaggerate idle time so T1/T2 shows up in a short demo.
    # (Real routed circuits accumulate far more idle; 30 gates is tiny vs T1=40µs.)
    obs = readout_observable(cal.num_qubits, "mean")
    idle_qc = QuantumCircuit(cal.num_qubits)
    idle_qc.x(0)
    for _ in range(500):  # ~20 µs of idle on q0 while q1 is busy → ~T1/2
        idle_qc.x(1)
    z_no_sched = execute_expectation(
        idle_qc, obs, sim, shots=shots, apply_idle_schedule=False
    )
    z_sched = execute_expectation(
        idle_qc, obs, sim, shots=shots, cal=cal, apply_idle_schedule=True
    )
    print(f"\nidle effect on mean-Z (500 x on q1, X on q0; ~20µs idle ≈ T1/2):")
    print(f"  no idle schedule:   {z_no_sched:.3f}")
    print(f"  with idle schedule: {z_sched:.3f}")
    print("  (with-schedule should decay |Z| more if idle T1/T2 is active)")


if __name__ == "__main__":
    sanity_check()
