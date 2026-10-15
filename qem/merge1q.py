"""Fuse runs of single-qubit gates between CZs into at most one PRX each.

Qiskit's ``optimization_level=1`` leaves roughly twice as many PRX gates as the circuit
needs, and the Pauli wrappers that native twirling inserts make it far worse -- on the
12-CZ star point the untwirled circuit carries 40 PRX and the twirled one 92. A twirled
arm that is physically twice as long is not a twirling experiment; that overhead is why
the first native-twirl run came back negative.

Two things make the fusion possible here that a generic pass cannot exploit:

* **RZ commutes through CZ.** Both are diagonal, so a leftover Z rotation can be pushed
  past the entangler and merged into the *next* run instead of being materialised.
* **The readout is in the Z basis.** A trailing RZ is then unobservable and is dropped.

Together these halve the PRX count of an untwirled circuit and bring a twirled one back
to roughly the untwirled level. ``Optimize1qGatesDecomposition`` does neither -- it
cannot move a rotation across a two-qubit gate -- and leaves the 12-CZ circuit at 40.

The CZ skeleton is never touched: no gate is added, removed or re-ordered, and no
routing decision is revisited. Only single-qubit content changes.

Adapted from ``spec/merge_prx_native_twirl.py``.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import RGate, RZGate
from qiskit.quantum_info import Operator
from qiskit.synthesis import OneQubitEulerDecomposer

_DECOMPOSER = OneQubitEulerDecomposer("ZYZ")

#: Below this, a rotation is treated as the identity and emitted as nothing.
_SIN_TOL = 1e-9


def merge_prx(qc: QuantumCircuit, *, drop_trailing_rz: bool = True) -> QuantumCircuit:
    """Return ``qc`` with every run of 1q gates between CZs fused into <= 1 PRX.

    Args:
        qc: a circuit already in the native basis -- only 1q gates, ``cz``,
            ``barrier`` and ``measure`` are accepted. Anything else raises, because
            silently copying an unrecognised gate would risk changing the circuit.
        drop_trailing_rz: discard the Z rotation left over at the end of each wire.
            Correct for Z-basis readout, which is what every observable in this project
            uses. Set False if a circuit is ever measured in another basis.

    Returns:
        A new circuit with the same qubits, clbits, CZ skeleton and ideal <Z_i>.

    Raises:
        ValueError: on a gate that is neither 1q, ``cz``, ``barrier`` nor ``measure``.
    """
    n = qc.num_qubits
    out = QuantumCircuit(n, qc.num_clbits) if qc.num_clbits else QuantumCircuit(n)
    pending = [np.eye(2, dtype=complex) for _ in range(n)]

    def flush(q: int) -> None:
        """Emit the accumulated 1q unitary on ``q`` as one PRX, carrying the RZ on."""
        theta, phi, lam = _DECOMPOSER.angles(pending[q])
        if abs(np.sin(theta / 2)) > _SIN_TOL:
            out.append(RGate(theta, np.pi / 2 - lam), [q])
        # what remains is diagonal: keep it and let it commute through the next CZ
        pending[q] = Operator(RZGate(phi + lam)).data

    for inst in qc.data:
        qubits = [qc.find_bit(b).index for b in inst.qubits]
        name = inst.operation.name
        if name == "barrier":
            continue
        if name == "measure":
            flush(qubits[0])
            out.append(inst.operation, qubits,
                       [qc.find_bit(c).index for c in inst.clbits])
            continue
        if len(qubits) == 1:
            pending[qubits[0]] = Operator(inst.operation).data @ pending[qubits[0]]
        elif name == "cz":
            for q in qubits:
                flush(q)
            out.append(inst.operation, qubits)
        else:
            raise ValueError(
                f"merge_prx expects a native circuit (1q gates, cz, barrier, measure); "
                f"got {name!r} on qubits {qubits}")

    for q in range(n):
        if drop_trailing_rz:
            # emit only the PRX part; the leftover RZ is diagonal and invisible to Z
            theta, phi, lam = _DECOMPOSER.angles(pending[q])
            if abs(np.sin(theta / 2)) > _SIN_TOL:
                out.append(RGate(theta, np.pi / 2 - lam), [q])
        else:
            flush(q)
            out.append(RZGate(0.0), [q])  # placeholder keeps the wire's phase explicit
    return out


def prx_upper_bound(n_cz: int, n_qubits: int) -> int:
    """Largest PRX count a correctly merged circuit can have.

    Each CZ flushes at most one PRX on each of its two qubits, and each wire may emit
    one final PRX before measurement. Exceeding this means two PRX survived on a wire
    with no CZ between them, i.e. the fusion did not actually happen.
    """
    return 2 * n_cz + n_qubits


def max_prx_run(qc: QuantumCircuit) -> int:
    """Longest run of consecutive 1q gates on any wire, uninterrupted by a CZ.

    This is the structural property the merge guarantees: after merging it is at most
    one. It is exact, unlike a gate-count ratio, which depends on how redundant the
    input happened to be.
    """
    n = qc.num_qubits
    run = [0] * n
    worst = 0
    for inst in qc.data:
        qubits = [qc.find_bit(b).index for b in inst.qubits]
        name = inst.operation.name
        if name == "barrier":
            continue
        if name == "cz":
            for q in qubits:
                run[q] = 0
        elif name == "measure":
            run[qubits[0]] = 0
        elif len(qubits) == 1:
            run[qubits[0]] += 1
            worst = max(worst, run[qubits[0]])
    return worst
