"""Hardware-Efficient Ansatz (HEA) with layer-wise data re-uploading.

This module implements the variational classifier ansatz described in ``plan.md`` (§6).
Each layer applies, in order:

1. **Data re-uploading** -- angle embedding of the input features scaled by
   trainable weights, re-uploaded on every layer (encoding motivated by
   Bowles, Ahmed & Schuld, arXiv:2403.07059).
2. **Trainable single-qubit rotations** -- an ``RY``/``RZ`` pair per qubit.
3. **Entangling block** -- the primary experimental knob of the study.

The entangling pattern controls the routing-induced two-qubit-gate (SWAP)
overhead once the circuit is transpiled onto a device:

* ``"star"`` -- entangle every *outer* qubit with a central *hub* qubit only.
  This is native to the Tier-A star topology (ODRA), so it incurs **minimal**
  routing overhead. This is the baseline of the study.
* ``"all_to_all"`` -- entangle every pair of qubits, producing **maximal**
  routing overhead on any sparse topology.
* ``"linear"`` / ``"circular"`` -- nearest-neighbour chains, provided as
  intermediate reference patterns.

The ansatz is returned as a bare state-preparation ``QuantumCircuit`` (no
measurement); the observable / decision rule is applied downstream by the
VQC-ZNE pipeline.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from itertools import combinations
from typing import Iterator

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector

ENTANGLEMENT_PATTERNS: tuple[str, ...] = ("star", "all_to_all", "linear", "circular")
ENTANGLING_GATES: tuple[str, ...] = ("cx", "cz")


def entangling_pairs(
    num_qubits: int, pattern: str = "star", hub: int = 0
) -> list[tuple[int, int]]:
    """Return the ordered list of qubit pairs entangled by one entangling block.

    Args:
        num_qubits: Number of qubits in the register.
        pattern: One of :data:`ENTANGLEMENT_PATTERNS`.
        hub: Index of the central hub qubit (only used by ``"star"``).

    Returns:
        A list of ``(control, target)`` index pairs.
    """
    if pattern not in ENTANGLEMENT_PATTERNS:
        raise ValueError(
            f"Unknown entanglement pattern {pattern!r}; "
            f"expected one of {ENTANGLEMENT_PATTERNS}."
        )
    if num_qubits < 2:
        return []
    if not 0 <= hub < num_qubits:
        raise ValueError(f"hub={hub} out of range for {num_qubits} qubits.")

    if pattern == "star":
        return [(hub, q) for q in range(num_qubits) if q != hub]
    if pattern == "all_to_all":
        return list(combinations(range(num_qubits), 2))
    if pattern == "linear":
        return [(q, q + 1) for q in range(num_qubits - 1)]
    # circular
    pairs = [(q, q + 1) for q in range(num_qubits - 1)]
    pairs.append((num_qubits - 1, 0))
    return pairs


@dataclass
class HardwareEfficientAnsatz:
    """Configurable HEA-with-reuploading circuit builder.

    Attributes:
        num_qubits: Number of qubits (and default number of features).
        num_layers: Number of re-upload/rotation/entangle layers ``L``.
        num_features: Input feature dimension ``d``. Defaults to ``num_qubits``.
            Features are uploaded with a running index across qubits *and* layers
            (data re-uploading), so ``d`` may exceed ``num_qubits``: the k-th
            embedding rotation carries feature ``x[k % d]``. Full coverage of all
            ``d`` features requires ``num_layers * num_qubits >= d`` (a warning is
            emitted otherwise).
        entanglement: Entangling pattern; see :data:`ENTANGLEMENT_PATTERNS`.
        entangling_gate: Two-qubit gate used for entangling (``"cx"`` or ``"cz"``).
        hub: Hub qubit index for the star pattern.
        final_rotation: If ``True``, append a trailing trainable rotation layer
            after the last entangling block (standard for HEA expressivity).
        insert_barriers: If ``True``, insert barriers between blocks for
            readability / to inhibit cross-block optimisation.
    """

    num_qubits: int
    num_layers: int = 1
    num_features: int | None = None
    entanglement: str = "star"
    entangling_gate: str = "cx"
    hub: int = 0
    final_rotation: bool = True
    insert_barriers: bool = False

    def __post_init__(self) -> None:
        if self.num_qubits < 1:
            raise ValueError("num_qubits must be >= 1.")
        if self.num_layers < 1:
            raise ValueError("num_layers must be >= 1.")
        if self.num_features is None:
            self.num_features = self.num_qubits
        if self.num_features < 1:
            raise ValueError("num_features must be >= 1.")
        if self.entanglement not in ENTANGLEMENT_PATTERNS:
            raise ValueError(
                f"Unknown entanglement pattern {self.entanglement!r}; "
                f"expected one of {ENTANGLEMENT_PATTERNS}."
            )
        if self.entangling_gate not in ENTANGLING_GATES:
            raise ValueError(
                f"Unknown entangling gate {self.entangling_gate!r}; "
                f"expected one of {ENTANGLING_GATES}."
            )

    # -- parameter accounting -------------------------------------------------

    @property
    def num_weights(self) -> int:
        """Total number of trainable weight parameters."""
        n, L = self.num_qubits, self.num_layers
        embed = L * n  # one re-upload scale per qubit per layer
        rot = L * 2 * n  # RY + RZ per qubit per layer
        final = 2 * n if self.final_rotation else 0
        return embed + rot + final

    @property
    def num_pairs_per_layer(self) -> int:
        """Number of two-qubit entangling gates inserted per layer."""
        return len(entangling_pairs(self.num_qubits, self.entanglement, self.hub))

    @property
    def num_entangling_gates(self) -> int:
        """Total logical two-qubit entangling gates in the (untranspiled) circuit."""
        return self.num_pairs_per_layer * self.num_layers

    # -- circuit construction -------------------------------------------------

    def build(self) -> QuantumCircuit:
        """Construct and return the parameterised ansatz circuit.

        The returned circuit exposes two parameter vectors accessible via
        :meth:`feature_parameters` and :meth:`weight_parameters`:

        * ``x`` -- input feature parameters (length ``num_features``);
        * ``w`` -- trainable weights (length :attr:`num_weights`).
        """
        n, L = self.num_qubits, self.num_layers
        x = ParameterVector("x", self.num_features)
        w = ParameterVector("w", self.num_weights)

        if L * n < self.num_features:
            warnings.warn(
                f"num_layers*num_qubits ({L * n}) < num_features "
                f"({self.num_features}): features x[{L * n}..{self.num_features - 1}] "
                f"are never uploaded. Increase num_layers or num_qubits.",
                stacklevel=2,
            )

        qc = QuantumCircuit(n, name=f"hea_{self.entanglement}_L{L}")
        pairs = entangling_pairs(n, self.entanglement, self.hub)
        wi: Iterator[int] = iter(range(self.num_weights))

        def next_w() -> "ParameterVector":  # returns a single Parameter
            return w[next(wi)]

        feat = 0  # running feature index: re-upload across qubits AND layers
        for layer in range(L):
            # (1) data re-uploading: cycle x[feat % d] scaled by a trainable weight
            for q in range(n):
                qc.rx(next_w() * x[feat % self.num_features], q)
                feat += 1
            if self.insert_barriers:
                qc.barrier()

            # (2) trainable single-qubit rotations
            for q in range(n):
                qc.ry(next_w(), q)
                qc.rz(next_w(), q)
            if self.insert_barriers:
                qc.barrier()

            # (3) entangling block
            self._apply_entanglers(qc, pairs)
            if self.insert_barriers and layer != L - 1:
                qc.barrier()

        # optional trailing rotation layer
        if self.final_rotation:
            if self.insert_barriers:
                qc.barrier()
            for q in range(n):
                qc.ry(next_w(), q)
                qc.rz(next_w(), q)

        return qc

    def _apply_entanglers(
        self, qc: QuantumCircuit, pairs: list[tuple[int, int]]
    ) -> None:
        gate = qc.cx if self.entangling_gate == "cx" else qc.cz
        for a, b in pairs:
            gate(a, b)

    # -- convenience ----------------------------------------------------------

    def feature_parameters(self, qc: QuantumCircuit) -> list:
        """Return the sorted list of feature (``x``) parameters of ``qc``."""
        return sorted(
            (p for p in qc.parameters if p.name.startswith("x[")),
            key=lambda p: int(p.name[2:-1]),
        )

    def weight_parameters(self, qc: QuantumCircuit) -> list:
        """Return the sorted list of trainable weight (``w``) parameters of ``qc``."""
        return sorted(
            (p for p in qc.parameters if p.name.startswith("w[")),
            key=lambda p: int(p.name[2:-1]),
        )


def build_ansatz(
    num_qubits: int,
    num_layers: int = 1,
    *,
    num_features: int | None = None,
    entanglement: str = "star",
    entangling_gate: str = "cx",
    hub: int = 0,
    final_rotation: bool = True,
    insert_barriers: bool = False,
) -> QuantumCircuit:
    """Functional wrapper around :class:`HardwareEfficientAnsatz`.

    Returns the built :class:`~qiskit.QuantumCircuit`.
    """
    return HardwareEfficientAnsatz(
        num_qubits=num_qubits,
        num_layers=num_layers,
        num_features=num_features,
        entanglement=entanglement,
        entangling_gate=entangling_gate,
        hub=hub,
        final_rotation=final_rotation,
        insert_barriers=insert_barriers,
    ).build()


def two_qubit_gate_count(circuit: QuantumCircuit) -> int:
    """Count two-qubit gates in a circuit (a proxy for routing cost)."""
    return sum(
        1
        for instruction in circuit.data
        if instruction.operation.num_qubits == 2
    )


def _demo() -> None:
    """Print logical two-qubit-gate cost of star vs all-to-all across n = 2..5."""
    print(f"{'n':>2} {'pattern':>12} {'layers':>7} {'2q-gates':>9} {'depth':>6}")
    print("-" * 40)
    for n in range(2, 6):
        for pattern in ("star", "all_to_all"):
            ansatz = HardwareEfficientAnsatz(
                num_qubits=n, num_layers=2, entanglement=pattern
            )
            qc = ansatz.build()
            print(
                f"{n:>2} {pattern:>12} {ansatz.num_layers:>7} "
                f"{two_qubit_gate_count(qc):>9} {qc.depth():>6}"
            )


if __name__ == "__main__":
    _demo()
