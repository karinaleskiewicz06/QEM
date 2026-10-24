"""Identity insertion: more CZ, or more time, at an unchanged circuit function (P5).

The depth axis of the archived campaigns (star at L6 / L9 / L13) changed three things at
once -- CZ count, PRX count, duration -- and each L is a different trained classifier with
different ideal values. Identity insertion holds the classifier fixed (star, L3) and adds
one factor at a time:

``cz_pairs``      ``k`` pairs ``CZ . CZ = I`` on the edge of an existing CZ: +2k CZ and
                  +2k CZ durations, the same PRX and the same function.
``idle_matched``  the same slots get a ``delay`` of two CZ durations on both qubits instead:
                  the CZ and PRX counts of the base, the duration of ``cz_pairs``.

So ``cz_pairs - idle_matched`` isolates the CZ count at fixed duration, and
``idle_matched - base`` isolates duration at fixed gate counts. The L6/L9/L13 rungs add
PRX on top. ``analysis/depth_regression.py`` regresses log error on the three.

Pairs are fenced by barriers so nothing between compile and pulse can cancel them. The
slots are spread evenly over the base CZ sequence and depend only on the CZ index, so the
same insertion applied to a target, its training circuits, its twirled frames or a logical
twirl compiled afterwards lands on the same edges at the same places: CDR's skeleton
match survives.
"""

from __future__ import annotations

from typing import Literal

from qiskit import QuantumCircuit

Mode = Literal["cz_pairs", "idle_matched"]
MODES: tuple[Mode, ...] = ("cz_pairs", "idle_matched")


def insertion_slots(n_cz: int, n_pairs: int) -> list[int]:
    """CZ index after which each pair goes: evenly spread, repeats allowed when n_pairs > n_cz."""
    if n_pairs < 0 or (n_pairs and n_cz < 1):
        raise ValueError(f"cannot place {n_pairs} pairs after {n_cz} CZ")
    return [min(n_cz - 1, int((k + 0.5) * n_cz / n_pairs)) for k in range(n_pairs)]


def insert_identity(native: QuantumCircuit, n_pairs: int, mode: Mode = "cz_pairs", *,
                    t_cz: float = 60e-9) -> QuantumCircuit:
    """``native`` with ``n_pairs`` identity insertions; the function is unchanged.

    Args:
        native: a native circuit (measured or not); its layout is carried over.
        n_pairs: insertions; each adds 2 CZ (``cz_pairs``) or ``2 * t_cz`` of idle time.
        mode: ``cz_pairs`` or ``idle_matched``.
        t_cz: CZ duration used for ``idle_matched``, from the calibration.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if n_pairs == 0:
        return native.copy()
    n_cz = sum(1 for i in native.data if i.operation.name == "cz")
    slots = insertion_slots(n_cz, n_pairs)
    out = native.copy_empty_like()
    j = -1
    for inst in native.data:
        out.append(inst.operation, inst.qubits, inst.clbits)
        if inst.operation.name != "cz":
            continue
        j += 1
        for _ in range(slots.count(j)):
            qa, qb = inst.qubits
            out.barrier(qa, qb)
            if mode == "cz_pairs":
                out.cz(qa, qb)
                out.barrier(qa, qb)
                out.cz(qa, qb)
            else:
                out.delay(2 * t_cz, qa, unit="s")
                out.delay(2 * t_cz, qb, unit="s")
            out.barrier(qa, qb)
    out._layout = native.layout
    return out


def delay_seconds(op) -> float:
    """Duration of a ``delay`` in seconds, whatever unit it was written in."""
    unit = getattr(op, "unit", "dt")
    d = float(op.params[0] if op.params else op.duration)
    scale = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "ps": 1e-12}
    if unit not in scale:
        raise ValueError(f"delay in {unit!r} has no duration in seconds")
    return d * scale[unit]


def scheduled_duration(circ: QuantumCircuit, *, t_prx: float = 20e-9,
                       t_cz: float = 60e-9) -> float:
    """ASAP wall-clock length up to the measurements, in seconds.

    Unlike the serial sum ``n_prx t_prx + n_cz t_cz`` recorded per circuit, this counts
    parallel gates once and idle time where a qubit waits, which is what relaxation sees.
    Barriers synchronise the qubits they span.
    """
    clock = [0.0] * circ.num_qubits
    for inst in circ.data:
        qs = [circ.find_bit(q).index for q in inst.qubits]
        name = inst.operation.name
        if name == "measure":
            continue
        if name == "barrier":
            t = max(clock[q] for q in qs)
            for q in qs:
                clock[q] = t
        elif name == "delay":
            for q in qs:
                clock[q] += delay_seconds(inst.operation)
        elif name == "cz":
            t = max(clock[q] for q in qs) + t_cz
            for q in qs:
                clock[q] = t
        elif name in ("r", "rz"):
            clock[qs[0]] += t_prx if name == "r" else 0.0   # RZ is virtual on IQM
        else:
            raise ValueError(f"scheduled_duration: unexpected gate {name!r}")
    return max(clock) if clock else 0.0
