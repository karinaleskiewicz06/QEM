"""The single compilation path for the campaign.

Until now the repository had two, and they disagreed. ``run_garnet_twirl`` transpiled
with a fixed ``initial_layout`` and ``seed_transpiler``; ``zne_dryrun.native_transpile``
passed neither. On Qiskit 2.4.1 that produces two different routing ladders from the
same circuits -- 12/30/39/57 CZ against 12/27/36/54 -- which is exactly the "CZ count
discrepancy" the design notes had attributed to a Qiskit version change. It was not a
version change. It was two code paths.

Worse, the unseeded path is **not deterministic**: compiling one circuit five times
gives five different CZ skeletons for every routed pattern. CDR depends on its training
circuits sharing the target's skeleton, so that it sees the same noise; on the unseeded
path essentially none of them do (star 10/10, everything else 0-2/10). The archived
``odra_full_100pt`` and ``odra_cdr_100pt`` campaigns were fit on training circuits with
a different routing from their target -- see ``DATA_NOTES.md``.

``compile_native`` is therefore the only place in the campaign that transpiles. It fixes
the layout and the seed, returns the skeleton alongside the circuit so a mismatch is
visible in the data, and fuses single-qubit runs by default.
"""

from __future__ import annotations

import dataclasses
from typing import Sequence

from qiskit import QuantumCircuit, transpile

from qem.merge1q import merge_prx
from topology import star_coupling_map
from zne_dryrun import IQM_BASIS_GATES

#: ODRA's logical-to-physical assignment is the identity: logical 0 is the hub.
#: ``run_hardware.PHYS`` then maps these onto the device's own names
#: (``["QB3", "QB1", "QB2", "QB4", "QB5"]``).
PHYS_IDENTITY: list[int] = [0, 1, 2, 3, 4]

#: Fixed for the whole campaign. Changing it changes the routing, and therefore the
#: ladder, and therefore comparability with every archived window.
DEFAULT_SEED = 42


@dataclasses.dataclass(frozen=True)
class CompiledCircuit:
    """A native circuit plus the facts needed to tell whether two agree."""

    circuit: QuantumCircuit
    cz_skeleton: tuple[tuple[int, int], ...]
    n_cz: int
    n_prx: int
    depth: int
    layout: tuple[int, ...]
    merged: bool

    def same_skeleton_as(self, other: "CompiledCircuit") -> bool:
        """True when both circuits route their CZs over the same ordered pairs.

        This is CDR's precondition: a training circuit only probes the target's noise
        if the entangling gates land on the same physical links in the same order.
        """
        return self.cz_skeleton == other.cz_skeleton


def cz_skeleton(circuit: QuantumCircuit) -> tuple[tuple[int, int], ...]:
    """Ordered tuple of qubit pairs the CZs act on."""
    return tuple(
        tuple(sorted(circuit.find_bit(q).index for q in inst.qubits))
        for inst in circuit.data if inst.operation.name == "cz"
    )


def compile_native(circ: QuantumCircuit, *,
                   layout: Sequence[int] | None = None,
                   seed: int = DEFAULT_SEED,
                   merge_1q: bool = True,
                   n_qubits: int = 5,
                   measure: bool = False) -> CompiledCircuit:
    """Compile to the native ``{r, cz}`` basis on the star, deterministically.

    Args:
        circ: a parameter-bound logical circuit.
        layout: physical qubits for logical 0..n-1; defaults to :data:`PHYS_IDENTITY`.
        seed: ``seed_transpiler``. Fixed by default so repeated compilation of one
            circuit is bit-identical and training circuits keep their target's routing.
        merge_1q: fuse single-qubit runs (see :mod:`qem.merge1q`). On by default; every
            arm must use the same setting or their gate counts are not comparable.
        n_qubits: width of the star.
        measure: append ``measure_all`` before compiling.

    Returns:
        A :class:`CompiledCircuit`.
    """
    layout = list(PHYS_IDENTITY if layout is None else layout)
    work = circ.copy()
    if measure:
        work.measure_all()
    native = transpile(work, basis_gates=IQM_BASIS_GATES,
                       coupling_map=star_coupling_map(n_qubits),
                       initial_layout=layout, optimization_level=1,
                       seed_transpiler=seed)
    if merge_1q:
        native = merge_prx(native)
    ops = native.count_ops()
    return CompiledCircuit(circuit=native, cz_skeleton=cz_skeleton(native),
                           n_cz=int(ops.get("cz", 0)), n_prx=int(ops.get("r", 0)),
                           depth=int(native.depth()), layout=tuple(layout),
                           merged=bool(merge_1q))
