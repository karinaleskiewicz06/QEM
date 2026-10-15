"""Pauli twirling of the native circuit, with the frame recorded.

Twirling replaces a coherent error by a stochastic Pauli channel, which is what CDR's
linear ansatz needs in order to be the right model. Doing it on hardware has a trap: the
Pauli wrappers are gates too. Emitted naively they take the 12-CZ star point from 40 to
92 single-qubit gates and double its depth, so the "twirled" arm is a longer circuit as
well as a twirled one -- which is why the first native-twirl run on ODRA came back
*negative*. :func:`twirl_native_merged` therefore always fuses afterwards; see
:mod:`qem.merge1q` for why that recovers the count.

Every frame is recorded as a list of two-qubit Pauli labels, one per CZ, in circuit
order. With the untwirled native circuit and the frame, :func:`rebuild_from_frame`
reproduces the executed circuit exactly -- so an archived record is self-contained and a
window can be re-analysed without re-running anything.
"""

from __future__ import annotations

import dataclasses

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import RGate
from qiskit.quantum_info import Clifford, Pauli

from qem.merge1q import merge_prx

PAULIS = ("I", "X", "Y", "Z")


@dataclasses.dataclass(frozen=True)
class TwirledCircuit:
    """A twirled circuit together with the frame that produced it."""

    circuit: QuantumCircuit
    frame: tuple[str, ...]      #: one 2-qubit Pauli label per CZ, in circuit order
    merged: bool

    @property
    def frame_str(self) -> str:
        """Compact form for a JSON record, e.g. ``"XZ.IY.ZZ"``."""
        return ".".join(self.frame)


def _pauli_char(p: Pauli, slot: int) -> str:
    x, z = bool(p.x[slot]), bool(p.z[slot])
    return {(False, False): "I", (True, False): "X",
            (False, True): "Z", (True, True): "Y"}[(x, z)]


def _emit_pauli(qc: QuantumCircuit, ch: str, qubit: int) -> None:
    """Append a single-qubit Pauli as native PRX gates, up to a global phase.

    Z has no single-PRX form -- PRX rotates about an axis in the xy-plane -- so it costs
    two. That asymmetry is exactly what the subsequent fusion absorbs.
    """
    if ch == "X":
        qc.r(np.pi, 0.0, qubit)
    elif ch == "Y":
        qc.r(np.pi, np.pi / 2, qubit)
    elif ch == "Z":
        qc.r(np.pi, 0.0, qubit)
        qc.r(np.pi, np.pi / 2, qubit)
    # "I": nothing


def _wrap_cz(out: QuantumCircuit, operation, qubits: list[int], label: str) -> None:
    """Emit ``B G A`` for a 2q Clifford ``G`` and Pauli ``A``, with ``B = G A G†``.

    ``A² = I`` for a Pauli, so ``B G A = (G A G†) G A = G A A = G``: the circuit is
    unchanged, while the gate's noise sees a different Pauli conjugation each shot.
    ``B`` is itself a Pauli because ``G`` is Clifford.
    """
    a = Pauli(label)
    g = QuantumCircuit(2)
    g.append(operation, [0, 1])
    b = a.evolve(Clifford(g), frame="s")
    _emit_pauli(out, _pauli_char(a, 0), qubits[0])
    _emit_pauli(out, _pauli_char(a, 1), qubits[1])
    out.append(operation, qubits)
    _emit_pauli(out, _pauli_char(b, 0), qubits[0])
    _emit_pauli(out, _pauli_char(b, 1), qubits[1])


def draw_frame(n_cz: int, rng: np.random.Generator) -> tuple[str, ...]:
    """Uniform 2-qubit Pauli per CZ. Labels are little-endian, as Qiskit expects."""
    return tuple("".join(rng.choice(PAULIS, size=2)) for _ in range(n_cz))


def twirl_native_merged(native: QuantumCircuit, rng: np.random.Generator | None = None,
                        *, frame: tuple[str, ...] | None = None,
                        merge: bool = True) -> TwirledCircuit:
    """Twirl every physical CZ, then fuse the single-qubit runs.

    Args:
        native: a circuit in the ``{r, cz}`` basis, already routed. Wrapping happens
            after routing, so CZs introduced by SWAPs are twirled too -- unlike
            :func:`twirl_logical`, which leaves them bare.
        rng: used when ``frame`` is not supplied.
        frame: replay a recorded frame instead of drawing one.
        merge: fuse afterwards. Leave on; off is for measuring the overhead.

    Raises:
        ValueError: if ``frame`` has a different length from the CZ count.
    """
    n_cz = sum(1 for i in native.data if i.operation.name in ("cz", "cx"))
    if frame is None:
        frame = draw_frame(n_cz, rng if rng is not None else np.random.default_rng())
    elif len(frame) != n_cz:
        raise ValueError(f"frame has {len(frame)} entries but the circuit has {n_cz} CZ")

    out = (QuantumCircuit(native.num_qubits, native.num_clbits)
           if native.num_clbits else QuantumCircuit(native.num_qubits))
    k = 0
    for inst in native.data:
        qubits = [native.find_bit(b).index for b in inst.qubits]
        name = inst.operation.name
        if len(qubits) == 2 and name in ("cz", "cx"):
            _wrap_cz(out, inst.operation, qubits, frame[k])
            k += 1
        elif name in ("barrier", "measure"):
            out.append(inst.operation, qubits,
                       [native.find_bit(c).index for c in inst.clbits])
        else:
            out.append(inst.operation, qubits)
    if merge:
        out = merge_prx(out)
    return TwirledCircuit(circuit=out, frame=tuple(frame), merged=merge)


def twirl_logical(logical: QuantumCircuit, rng: np.random.Generator | None = None,
                  *, frame: tuple[str, ...] | None = None) -> TwirledCircuit:
    """Twirl the *logical* entangling gates, before routing.

    This is what the archived campaigns did. CZs that the router later introduces as
    part of a SWAP are left untwirled, so any gain measured this way is a lower bound
    on what full randomized compiling would give. Kept for comparison; the circuit is
    not merged here because it still has to be routed.
    """
    n_2q = sum(1 for i in logical.data if i.operation.name in ("cz", "cx"))
    if frame is None:
        frame = draw_frame(n_2q, rng if rng is not None else np.random.default_rng())
    elif len(frame) != n_2q:
        raise ValueError(f"frame has {len(frame)} entries but the circuit has {n_2q} 2q gates")

    out = QuantumCircuit(*logical.qregs, *logical.cregs)
    k = 0
    for inst in logical.data:
        qubits = [logical.find_bit(b).index for b in inst.qubits]
        if len(qubits) == 2 and inst.operation.name in ("cz", "cx"):
            _wrap_cz(out, inst.operation, qubits, frame[k])
            k += 1
        else:
            out.append(inst.operation, qubits,
                       [logical.find_bit(c).index for c in inst.clbits])
    return TwirledCircuit(circuit=out, frame=tuple(frame), merged=False)


def rebuild_from_frame(native: QuantumCircuit, frame_str: str, *,
                       merge: bool = True) -> QuantumCircuit:
    """Reproduce an executed circuit from the untwirled one and its recorded frame.

    This is what makes an archived record self-contained: the counts, the native
    circuit and this string are enough to say exactly what ran.
    """
    frame = tuple(frame_str.split(".")) if frame_str else ()
    return twirl_native_merged(native, frame=frame, merge=merge).circuit
