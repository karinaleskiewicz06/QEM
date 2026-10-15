"""Folding on the native circuit, with matched-cost controls.

Koster & Mauerer (arXiv:2607.09360) show that Richardson ZNE can report an improvement
even when the noise amplification is useless: once ``E(lambda > 1)`` sits on the
observable's floor, the estimate is a rescaling of ``E(1)``. The only way to tell a real
gain from that artefact on hardware is to run controls that cost exactly as much:

``genuine``   ``U (U^dag U)^k`` -- ordinary global folding.
``identity``  ``U`` followed by ``k`` blocks with the same CZ sequence as ``U^dag U`` and
              the same PRX count, where every PRX is paired with its inverse and the
              CZs therefore multiply to the identity. Same cost, same function: it
              should behave like ``genuine``.
``garbage``   ``U (V^dag U)^k`` with ``V`` the circuit ``U`` with random PRX angles. Same
              cost, but the fold is not the identity, so ``E(lambda > 1)`` is destroyed
              by construction. A ZNE "gain" that survives this is the artefact.

The paper does not give the gate content of its garbage fold; this construction is
ours, chosen so that all three variants have **the same CZ skeleton and the same PRX
count at every scale**. That is checked in the tests, because it is the whole point.

Everything happens on the already-compiled native circuit (``qem.compile``), and
nothing is transpiled afterwards: re-transpiling a fold lets the optimiser cancel
``U^dag U`` or re-route it, and then the scale is no longer the scale. Copies are
separated by barriers so a backend that respects them cannot merge across a fold
either.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import RGate

FoldVariant = Literal["genuine", "identity", "garbage"]
FOLD_VARIANTS: tuple[FoldVariant, ...] = ("genuine", "identity", "garbage")

#: Gates a foldable native circuit may contain.
_ALLOWED = {"r", "rz", "cz", "barrier"}


def _check_native(native: QuantumCircuit) -> None:
    bad = sorted({i.operation.name for i in native.data} - _ALLOWED)
    if bad:
        raise ValueError(
            f"fold_native expects a measurement-free native circuit ({sorted(_ALLOWED)}); "
            f"found {bad}. Fold before measuring, e.g. compile_native(..., measure=False).")


def _empty_like(native: QuantumCircuit) -> QuantumCircuit:
    return QuantumCircuit(*native.qregs, *native.cregs, name=native.name)


def _qubits(native: QuantumCircuit, inst) -> list[int]:
    return [native.find_bit(q).index for q in inst.qubits]


def random_angle_twin(native: QuantumCircuit, rng: np.random.Generator) -> QuantumCircuit:
    """``V``: ``native`` with every single-qubit angle redrawn uniformly.

    The CZs, their order and the number of PRX are untouched, so ``V`` costs what
    ``U`` costs and differs from it only in what it computes.
    """
    _check_native(native)
    out = _empty_like(native)
    for inst in native.data:
        q = _qubits(native, inst)
        name = inst.operation.name
        if name == "r":
            theta, phi = rng.uniform(0.0, 2 * np.pi, 2)
            out.append(RGate(float(theta), float(phi)), q)
        elif name == "rz":
            out.rz(float(rng.uniform(0.0, 2 * np.pi)), q[0])
        else:
            out.append(inst.operation, q)
    return out


def identity_block(native: QuantumCircuit) -> QuantumCircuit:
    """A block with the gate cost of ``U^dag U`` that is exactly the identity.

    The CZ sequence is that of ``U^dag U`` -- the reversed skeleton, then the
    skeleton -- so every CZ appears twice. CZs are diagonal and commute, so with no
    non-trivial single-qubit gate between them they multiply to the identity. In the
    ``U^dag`` half each 1q gate ``g`` becomes the adjacent pair ``g, g^-1``; the ``U``
    half carries none. The PRX count therefore matches ``U^dag U`` exactly, on every
    qubit.
    """
    _check_native(native)
    inv = native.inverse()
    out = _empty_like(native)
    for inst in inv.data:
        q = _qubits(inv, inst)
        name = inst.operation.name
        if name in ("r", "rz"):
            out.append(inst.operation, q)
            out.append(inst.operation.inverse(), q)
        else:
            out.append(inst.operation, q)
    out.barrier()
    for inst in native.data:
        if inst.operation.name in ("cz", "barrier"):
            out.append(inst.operation, _qubits(native, inst))
    return out


def fold_native(native: QuantumCircuit, scale: int, variant: FoldVariant = "genuine", *,
                seed: int | None = None, measure: bool = False) -> QuantumCircuit:
    """Fold an already-native circuit to an odd ``scale``, without re-transpiling.

    Args:
        native: measurement-free circuit in ``{r, rz, cz, barrier}`` on physical qubits.
        scale: ``2k + 1``.
        variant: ``genuine``, ``identity`` or ``garbage``.
        seed: draws the garbage twin ``V``. One ``V`` is used for all ``k`` blocks, so
            ``(variant, scale, seed)`` reconstructs the circuit exactly.
        measure: append ``measure_all`` after folding.

    Returns:
        ``U (B)^k`` where ``B`` is ``U^dag U``, the identity block or ``V^dag U``, with a
        barrier on each side of every ``U^dag``-half and ``U``-half.

    Raises:
        ValueError: on an even or non-positive scale, an unknown variant, or a
            circuit that is not native and measurement-free.
    """
    if scale < 1 or scale % 2 == 0:
        raise ValueError(f"scale must be a positive odd integer; got {scale}")
    if variant not in FOLD_VARIANTS:
        raise ValueError(f"unknown fold variant {variant!r}; expected one of {FOLD_VARIANTS}")
    _check_native(native)
    k = (scale - 1) // 2

    out = native.copy()
    if k:
        if variant == "genuine":
            inv = native.inverse()
        elif variant == "garbage":
            inv = random_angle_twin(native, np.random.default_rng(seed)).inverse()
        else:
            block = identity_block(native)
        for _ in range(k):
            out.barrier()
            if variant == "identity":
                out.compose(block, inplace=True)
            else:
                out.compose(inv, inplace=True)
                out.barrier()
                out.compose(native, inplace=True)
    if measure:
        out.measure_all()
    return out


def fold_all_variants(native: QuantumCircuit, scales, *, seed: int | None = None,
                      measure: bool = False,
                      variants=FOLD_VARIANTS) -> dict[tuple[str, int], QuantumCircuit]:
    """``{(variant, scale): circuit}``; at scale 1 every variant is ``U`` itself."""
    return {(v, int(s)): fold_native(native, int(s), v, seed=seed, measure=measure)
            for v in variants for s in scales}
