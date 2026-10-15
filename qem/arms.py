"""The CDR arms, and the budget that makes them comparable.

A twirled arm averages over M random frames. If the untwirled baseline is measured once,
any improvement is partly just M-fold averaging, and the comparison says nothing about
twirling. Every arm here therefore spends the **same total shots per evaluation point**::

    B = (n_train + 1) * M * S

and the arms differ only in how that budget is divided. ``off_copies`` is the control
that makes this explicit: it averages M *identical* copies, so it buys the same variance
reduction as a twirled arm without the twirling.

The arms form a 2x2 factorial over two independent levers, crossed with the choice of
training distribution:

==============  ==========================================  ========  ================
arm             training circuits x frames                  twirled   lever
==============  ==========================================  ========  ================
off_copies      n_train x M identical copies                no        neither
twirl_logical   n_train x M frames (logical wrap)           yes       twirling
twirl_native    n_train x M frames (native wrap, merged)    yes       twirling
spread_off      n_train*M distinct circuits x 1             no        diversity
spread          n_train*M distinct circuits x 1 frame       yes       both
==============  ==========================================  ========  ================

``spread`` is the proposed method (spec 3.3): instead of averaging M frames inside each
of n_train training points, it measures n_train*M *different* near-target circuits with
one frame each. The averaging moves out of the training point and into the regression,
which gets M times more distinct points while the frames become ordinary noise in x.

This module only *plans* the work -- it emits the circuit specs and checks the budget.
Execution and fitting live with the runner.
"""

from __future__ import annotations

import dataclasses
from typing import Iterator, Literal

ArmName = Literal["off_copies", "twirl_logical", "twirl_native", "spread", "spread_off"]
TrainSet = Literal["shared_random", "near_target"]

ARMS: tuple[ArmName, ...] = ("off_copies", "twirl_logical", "twirl_native",
                             "spread", "spread_off")

#: Arms that apply a Pauli frame, and where it is applied.
TWIRL_KIND: dict[ArmName, str | None] = {
    "off_copies": None,
    "twirl_logical": "logical",
    "twirl_native": "native",
    "spread": "native",
    "spread_off": None,
}

#: Arms that measure n_train*M distinct training circuits instead of n_train.
IS_SPREAD: dict[ArmName, bool] = {
    "off_copies": False, "twirl_logical": False, "twirl_native": False,
    "spread": True, "spread_off": True,
}


@dataclasses.dataclass(frozen=True)
class CircuitSpec:
    """One circuit to execute, and everything needed to label its record."""

    role: Literal["train", "target"]
    train_index: int | None      #: index into the training set, None for the target
    repeat_index: int            #: which copy or frame
    shots: int
    twirl: bool
    twirl_kind: str | None

    @property
    def circuit_id(self) -> str:
        who = "target" if self.role == "target" else f"train{self.train_index:03d}"
        return f"{who}/r{self.repeat_index:02d}"


@dataclasses.dataclass(frozen=True)
class ArmPlan:
    """The full execution plan for one arm at one evaluation point."""

    arm: ArmName
    train_set: TrainSet
    n_train: int
    n_frames: int                #: M
    shots: int                   #: S
    specs: tuple[CircuitSpec, ...]

    @property
    def n_distinct_training_circuits(self) -> int:
        return len({s.train_index for s in self.specs if s.role == "train"})

    @property
    def total_shots(self) -> int:
        return sum(s.shots for s in self.specs)

    @property
    def n_circuits(self) -> int:
        return len(self.specs)


def budget(n_train: int, n_frames: int, shots: int) -> int:
    """Shots every arm must spend per evaluation point: ``(n_train + 1) * M * S``.

    The ``+1`` is the target, which every arm measures with M repeats.
    """
    return (n_train + 1) * n_frames * shots


def plan_arm(arm: ArmName, *, n_train: int, n_frames: int, shots: int,
             train_set: TrainSet = "near_target") -> ArmPlan:
    """Build the execution plan for one arm.

    ``spread`` and ``spread_off`` replace ``n_train`` points measured ``M`` times each
    by ``n_train * M`` points measured once, which is the same number of circuits and
    the same number of shots. The target is measured with M repeats in every arm, so
    the arms differ only in the training half.

    Raises:
        ValueError: on an unknown arm, or a non-positive parameter.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")
    if min(n_train, n_frames, shots) <= 0:
        raise ValueError("n_train, n_frames and shots must all be positive")

    twirl_kind = TWIRL_KIND[arm]
    twirl = twirl_kind is not None
    specs: list[CircuitSpec] = []

    if IS_SPREAD[arm]:
        # n_train*M distinct circuits, one repeat each
        for i in range(n_train * n_frames):
            specs.append(CircuitSpec("train", i, 0, shots, twirl, twirl_kind))
    else:
        for i in range(n_train):
            for r in range(n_frames):
                specs.append(CircuitSpec("train", i, r, shots, twirl, twirl_kind))

    # the target is measured identically in every arm: M repeats
    for r in range(n_frames):
        specs.append(CircuitSpec("target", None, r, shots, twirl, twirl_kind))

    return ArmPlan(arm=arm, train_set=train_set, n_train=n_train,
                   n_frames=n_frames, shots=shots, specs=tuple(specs))


def plan_all(arms: tuple[ArmName, ...] = ARMS, **kwargs) -> dict[ArmName, ArmPlan]:
    """Plan several arms at once, for a budget comparison."""
    return {a: plan_arm(a, **kwargs) for a in arms}


def iter_training_specs(plan: ArmPlan) -> Iterator[CircuitSpec]:
    return (s for s in plan.specs if s.role == "train")


def describe(plan: ArmPlan) -> str:
    """One readable line, for a dry-run budget table."""
    return (f"{plan.arm:14s} train={plan.train_set:13s} "
            f"circuits={plan.n_circuits:5d} distinct={plan.n_distinct_training_circuits:4d} "
            f"shots={plan.total_shots:8d}"
            + ("  twirled" if TWIRL_KIND[plan.arm] else ""))
