"""[[4,2,2]] error-detection code — QEC-lite "logical-ish" layer (methodology §4, W5).

The `[[4,2,2]]` code stores 2 logical qubits in 4 data qubits, distance 2: it
*detects* (cannot correct) any single-qubit error. We use it ancilla-free,
Vuillot-style (arXiv:1705.08957): measure the 4 data qubits destructively and
post-select on the stabilizer parity, discarding flagged shots.

Design choice (see qec422_design_justification.md): running a classifier under a
detecting code is non-standard, so we implement two honest arms —
  * Option A: a near-Clifford *surrogate* payload run on the encoded block;
  * Option C: the exact circuit's *mirror* (U U†) wrapped with detection.
Both reuse the SAME primitives here: encode -> payload -> measure -> post-select.

Encoding: logical |00>_L = (|0000> + |1111>)/sqrt(2) (a 4-qubit GHZ state), the
+1 eigenstate of both stabilizers XXXX and ZZZZ. Logical Z on the first logical
qubit is Z0·Z1 (weight-2, commutes with both stabilizers). Computational-basis
logical states have EVEN Z-parity, so an odd-parity measurement flags an X-type
error and is discarded.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit

N_DATA = 4
Z_LOGICAL1 = (0, 1)  # Zbar_1 = Z0 Z1
Z_LOGICAL2 = (0, 2)  # Zbar_2 = Z0 Z2


def encode_422(data: tuple[int, ...] = (0, 1, 2, 3)) -> QuantumCircuit:
    """Circuit preparing |00>_L = (|0000> + |1111>)/sqrt(2) on the 4 data qubits."""
    qc = QuantumCircuit(N_DATA, name="encode_422")
    d0, d1, d2, d3 = data
    qc.h(d0)
    qc.cx(d0, d1)
    qc.cx(d0, d2)
    qc.cx(d0, d3)
    return qc


def decode_422(data: tuple[int, ...] = (0, 1, 2, 3)) -> QuantumCircuit:
    """Inverse of :func:`encode_422` (used to close a mirror back to |0000>)."""
    return encode_422(data).inverse()


def z_parity(bits: str) -> int:
    """ZZZZ parity of a 4-bit measurement string (0 = even = in codespace)."""
    b = bits.replace(" ", "")[-N_DATA:].zfill(N_DATA)
    return sum(int(c) for c in b) % 2


def postselect_z_parity(counts: dict[str, int]) -> tuple[dict[str, int], float]:
    """Keep only even-ZZZZ-parity shots; return (kept_counts, acceptance_rate).

    Even parity = the +1 eigenspace of ZZZZ, where the logical computational
    states live. Odd-parity shots carry a detected X-type error and are discarded.
    ``acceptance_rate`` is kept / total — the post-selection overhead, reported as
    the encoding's cost and folded into the shots-to-target currency.
    """
    total = sum(counts.values())
    kept = {b: c for b, c in counts.items() if z_parity(b) == 0}
    accepted = sum(kept.values())
    return kept, (accepted / total if total else 0.0)


def logical_z_expval(counts: dict[str, int], zbits: tuple[int, ...] = Z_LOGICAL1) -> float:
    """Logical ⟨Zbar⟩ = <prod_{i in zbits} Z_i> from (post-selected) counts.

    ``zbits`` gives the data qubits of the logical Z operator (default Zbar_1 = Z0Z1).
    Returns 0.0 if no shots survived post-selection.
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    acc = 0.0
    for b, c in counts.items():
        bstr = b.replace(" ", "")[-N_DATA:].zfill(N_DATA)
        val = 1.0
        for q in zbits:
            val *= 1.0 - 2.0 * int(bstr[N_DATA - 1 - q])  # LSB = qubit 0
        acc += val * c
    return acc / total


def codespace_survival(counts: dict[str, int]) -> float:
    """P(logical |00>_L) = P(|0000>) + P(|1111>): mirror-survival fidelity.

    The exact-circuit mirror arm (Option C) returns to |00>_L ideally; this is its
    survival probability (analogue of the mirror-fidelity yardstick, but logical).
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    good = counts.get("0000", 0) + counts.get("1111", 0)
    return good / total


def build_detection_mirror(
    payload: QuantumCircuit, data: tuple[int, ...] = (0, 1, 2, 3), detect: bool = True
) -> QuantumCircuit:
    """Option C: encode -> payload -> payload† -> measure, code-preserving.

    ``payload`` acts on the 4 data qubits (a 2-logical-qubit circuit's physical
    realisation). The net is the identity on the codespace, so ideally it returns
    to |00>_L. ``detect=False`` builds the same circuit for the bare baseline (the
    caller simply skips post-selection). Measurement is appended over the 4 data
    qubits in the Z basis.
    """
    qc = QuantumCircuit(N_DATA, N_DATA, name="qec422_mirror")
    qc.compose(encode_422(data), inplace=True)
    qc.barrier()
    qc.compose(payload, inplace=True)
    qc.barrier()
    qc.compose(payload.inverse(), inplace=True)
    qc.barrier()
    qc.measure(range(N_DATA), range(N_DATA))
    return qc


def build_encoded_surrogate(
    surrogate: QuantumCircuit, data: tuple[int, ...] = (0, 1, 2, 3)
) -> QuantumCircuit:
    """Option A: encode -> surrogate (physical Clifford on the block) -> measure.

    ``surrogate`` is the near-Clifford surrogate of the classifier, realised as a
    physical Clifford circuit on the 4 data qubits (build it with cdr.near_clifford
    machinery on a 2-logical-qubit model, then map onto the block). Post-select on
    Z-parity and read the logical observable. This is the task-facing arm; its
    honest caveat is that it runs the Clifford surrogate, not the exact model.
    """
    qc = QuantumCircuit(N_DATA, N_DATA, name="qec422_surrogate")
    qc.compose(encode_422(data), inplace=True)
    qc.barrier()
    qc.compose(surrogate, inplace=True)
    qc.barrier()
    qc.measure(range(N_DATA), range(N_DATA))
    return qc
