"""Near-Clifford training sets built on the target's *native* circuit.

The archived campaigns built training circuits from the logical circuit and compiled
each one separately. Two things went wrong with that:

1. **The routing drifted.** Compiled without a fixed layout and seed, a training circuit
   lands on a different CZ skeleton from its target -- 0 to 2 out of 10 matched for every
   routed pattern. CDR then regresses against circuits that experienced different noise.
2. **Every target shared one training set.** ``near_clifford_training_circuits`` with a
   fixed seed returns the same circuits 1..n-1 regardless of target, so the fits at
   different evaluation points were strongly correlated, and the training distribution
   sat nowhere near any particular target.

Here the snapping happens on the native circuit itself. Nothing is re-transpiled, so the
skeleton is identical to the target's by construction, not by luck. The angles of each
``r(theta, phi)`` are replaced by Clifford values, which keeps the circuit in the native
basis and leaves gate counts untouched except where a rotation becomes the identity.

Why those angles are Clifford: ``r(theta, phi) = exp(-i theta/2 (cos phi X + sin phi Y))``
is a rotation about an axis in the xy-plane. At ``theta`` a multiple of pi/2 and ``phi`` a
multiple of pi/2 the axis is +-X or +-Y and the angle is a multiple of a quarter turn, so
the gate maps Paulis to Paulis. :func:`is_clifford` checks this rather than trusting it.
"""

from __future__ import annotations

import zlib
from typing import Callable, Iterable

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import RGate
from qiskit.quantum_info import Clifford, StabilizerState

#: Clifford values for both parameters of a native PRX gate.
CLIFFORD_ANGLES = np.array([0.0, np.pi / 2, np.pi, 3 * np.pi / 2])

#: Default width of the near-target proposal, in radians. Not tuned.
DEFAULT_SIGMA = np.pi / 4

AngleSampler = Callable[[float, np.random.Generator], float]


def stable_seed(base_seed: int, target_index: int, window_id: str) -> int:
    """Deterministic per-target seed.

    Python's ``hash()`` is salted per process for ``str``, so seeding from it would make
    a window irreproducible from its own manifest -- the same arguments would give
    different training circuits on a re-run. CRC32 over the joined key is stable across
    processes and releases, which is the only property needed here.
    """
    key = f"{int(base_seed)}|{int(target_index)}|{window_id}".encode()
    return int(zlib.crc32(key))


def _wrap(angle: float) -> float:
    return float(angle) % (2 * np.pi)


def _angular_distance(a: np.ndarray, b: float) -> np.ndarray:
    """Shortest angular distance from each entry of ``a`` to ``b``, in [0, pi]."""
    d = (a - _wrap(b) + np.pi) % (2 * np.pi) - np.pi
    return np.abs(d)


# -- angle samplers --------------------------------------------------------- #

def nearest(angle: float, rng: np.random.Generator | None = None) -> float:
    """Closest Clifford angle. Used for the anchor circuit (index 0)."""
    return float(CLIFFORD_ANGLES[int(np.argmin(_angular_distance(CLIFFORD_ANGLES, angle)))])


def uniform_random(angle: float, rng: np.random.Generator) -> float:
    """Uniform over the four Clifford angles -- the legacy behaviour.

    This ignores the target entirely, so the training set is a set of random Clifford
    circuits that merely share the target's skeleton. Kept for reproducing the archive.
    """
    return float(rng.choice(CLIFFORD_ANGLES))


def near_target(sigma: float = DEFAULT_SIGMA) -> AngleSampler:
    """Sampler weighting Clifford angles by ``exp(-d^2 / sigma^2)`` toward the original.

    Keeping the training distribution near the target is what makes the fit
    interpolate rather than extrapolate. ``sigma`` has not been tuned.
    """
    def sample(angle: float, rng: np.random.Generator) -> float:
        d = _angular_distance(CLIFFORD_ANGLES, angle)
        w = np.exp(-(d / sigma) ** 2)
        return float(rng.choice(CLIFFORD_ANGLES, p=w / w.sum()))
    return sample


SAMPLERS: dict[str, Callable[..., AngleSampler | float]] = {
    "nearest": nearest,
    "uniform_random": uniform_random,
    "near_target": near_target,
}


# -- snapping --------------------------------------------------------------- #

def snap_native_to_clifford(native: QuantumCircuit, angle_sampler: AngleSampler,
                            rng: np.random.Generator | None = None) -> QuantumCircuit:
    """Replace every ``r`` gate's angles with Clifford values, in place of the native circuit.

    ``cz`` gates, barriers and measurements are copied unchanged, so the CZ skeleton is
    identical to the input's by construction. A rotation whose sampled ``theta`` is 0
    becomes the identity and is dropped rather than emitted as a no-op pulse.

    Args:
        native: a circuit already in the ``{r, cz}`` basis.
        angle_sampler: called as ``sampler(angle, rng)`` for each of theta and phi.
        rng: generator; required by the stochastic samplers.

    Raises:
        ValueError: on a gate other than ``r``, ``cz``, ``barrier`` or ``measure``.
    """
    rng = rng if rng is not None else np.random.default_rng(0)
    out = (QuantumCircuit(native.num_qubits, native.num_clbits)
           if native.num_clbits else QuantumCircuit(native.num_qubits))
    for inst in native.data:
        qubits = [native.find_bit(b).index for b in inst.qubits]
        name = inst.operation.name
        if name == "r":
            theta = angle_sampler(float(inst.operation.params[0]), rng)
            phi = angle_sampler(float(inst.operation.params[1]), rng)
            if abs(np.sin(theta / 2)) > 1e-12:          # theta == 0 -> identity
                out.append(RGate(theta, phi), qubits)
        elif name == "cz":
            out.append(inst.operation, qubits)
        elif name in ("barrier", "measure"):
            out.append(inst.operation, qubits,
                       [native.find_bit(c).index for c in inst.clbits])
        else:
            raise ValueError(f"snap_native_to_clifford expects a native circuit; "
                             f"got {name!r} on {qubits}")
    return out


def is_clifford(circuit: QuantumCircuit) -> bool:
    """Whether Qiskit accepts the circuit as a Clifford element.

    Checked for every training circuit rather than assumed: a snapped angle that is not
    actually Clifford would silently make the ideal value uncomputable by the stabilizer
    simulator, and CDR's whole scalability argument rests on it being computable.
    """
    probe = circuit.copy()
    probe.remove_final_measurements(inplace=True)
    try:
        Clifford(probe)
    except Exception:          # Qiskit raises several types here; any of them means "no"
        return False
    return True


def clifford_ideal_expval(circuit: QuantumCircuit, observable) -> float:
    """Exact noiseless <O> of a Clifford circuit via the stabilizer formalism.

    Unlike a statevector this stays polynomial in the qubit count, which is the property
    that lets CDR work at scales where the target cannot be simulated at all.
    """
    probe = circuit.copy()
    probe.remove_final_measurements(inplace=True)
    return float(np.real(StabilizerState(Clifford(probe)).expectation_value(observable)))


def build_training_set(target_native: QuantumCircuit, *, n_train: int,
                       sampler: str = "near_target", sigma: float = DEFAULT_SIGMA,
                       base_seed: int = 42, target_index: int = 0,
                       window_id: str = "w1",
                       include_anchor: bool = True) -> list[QuantumCircuit]:
    """Training circuits for one target, all sharing its CZ skeleton.

    The generator is seeded from ``(base_seed, target_index, window_id)``, so different
    evaluation points get different training sets -- unlike the archived campaigns,
    where one set was shared by every target.

    Args:
        target_native: the compiled target.
        n_train: how many circuits, counting the anchor.
        sampler: ``"nearest"``, ``"uniform_random"`` or ``"near_target"``.
        include_anchor: make circuit 0 the nearest-Clifford image of the target.
    """
    if sampler not in SAMPLERS:
        raise ValueError(f"unknown sampler {sampler!r}; expected {sorted(SAMPLERS)}")
    rng = np.random.default_rng(stable_seed(base_seed, target_index, window_id))
    fn: AngleSampler = (near_target(sigma) if sampler == "near_target"
                        else (uniform_random if sampler == "uniform_random" else nearest))

    circuits: list[QuantumCircuit] = []
    if include_anchor:
        circuits.append(snap_native_to_clifford(target_native, nearest, rng))
    while len(circuits) < n_train:
        circuits.append(snap_native_to_clifford(target_native, fn, rng))
    return circuits


def build_legacy_shared_training(target_natives: Iterable[QuantumCircuit], *,
                                 n_train: int, base_seed: int = 42
                                 ) -> list[list[QuantumCircuit]]:
    """Reproduce the archived behaviour: one shared set, uniform angles, same seed.

    Only the anchor differs between targets. Kept so the old results can be
    re-derived and the defect demonstrated, not because it should be used.
    """
    targets = list(target_natives)
    shared_rng = np.random.default_rng(base_seed)
    shared = [snap_native_to_clifford(targets[0], uniform_random, shared_rng)
              for _ in range(max(0, n_train - 1))]
    out = []
    for t in targets:
        out.append([snap_native_to_clifford(t, nearest, shared_rng)] + list(shared))
    return out
