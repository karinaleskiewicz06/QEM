"""Common cost currency — effective QPU shots (methodology_month_2.md §5, W3).

Puts ZNE, CDR, and [[4,2,2]] on one comparable axis by folding each method's
*native* overhead into an "effective shots" number: the total device shots a
method actually spends. Comparing methods then means comparing effective shots at
matched quality (error/accuracy) — never raw quality at unequal cost.

Overhead models
---------------
* ZNE  : runs the circuit at each noise scale, times reps -> shots * n_scales * reps.
* CDR  : runs n_train near-Clifford training circuits + the target -> shots * (n_train + 1) * reps.
* QED  : post-selection discards flagged shots, so to KEEP `shots` usable shots you
         must run shots / acceptance_rate -> shots / acceptance.

These are deliberately simple, transparent multipliers; refine per device if a
method's real submission cost differs (e.g. batched jobs).
"""

from __future__ import annotations

import numpy as np


# --- IQM Resonance budget planning (time-based billing) --------------------- #
# Pricing is per SECOND of QPU execution, not per shot.
GARNET_CR_PER_SEC = 0.50      # 1800 credits/hour
EMERALD_CR_PER_SEC = 0.75     # 2400 credits/hour


def credits_for_campaign(
    n_circuits: int,
    shots: int,
    time_per_shot_s: float,
    *,
    cr_per_sec: float = GARNET_CR_PER_SEC,
    overhead_s_per_circuit: float = 0.0,
) -> tuple[float, float]:
    """Estimate (credits, execution_seconds) for a campaign.

    ``time_per_shot_s`` is the per-shot execution time — MEASURE it on the smoke
    test (run 1 circuit, divide the billed seconds by shots) and plug it in here;
    do not guess. ``overhead_s_per_circuit`` captures per-job loading/compile time
    if the smoke test reveals it. Total exec time = n_circuits × (shots ×
    time_per_shot + overhead); credits = exec_time × cr_per_sec.
    """
    exec_s = n_circuits * (shots * time_per_shot_s + overhead_s_per_circuit)
    return exec_s * cr_per_sec, exec_s


def affordable_shots(
    budget_credits: float,
    n_circuits: int,
    time_per_shot_s: float,
    *,
    cr_per_sec: float = GARNET_CR_PER_SEC,
) -> int:
    """Max shots-per-circuit that fits ``budget_credits`` for ``n_circuits``."""
    if n_circuits <= 0 or time_per_shot_s <= 0:
        return 0
    exec_budget_s = budget_credits / cr_per_sec
    return int(exec_budget_s / (n_circuits * time_per_shot_s))


def zne_effective_shots(shots: int, n_scales: int = 3, reps: int = 1) -> float:
    """Effective shots for ZNE: one run per noise scale, times reps."""
    return float(shots) * n_scales * reps


def cdr_effective_shots(shots: int, n_train: int, reps: int = 1) -> float:
    """Effective shots for CDR: n_train training circuits + the target, times reps."""
    return float(shots) * (n_train + 1) * reps


def qec_effective_shots(shots: int, acceptance_rate: float) -> float:
    """Effective shots for post-selected QED: raw shots to KEEP ``shots`` after discards."""
    return float(shots) / max(float(acceptance_rate), 1e-9)


def raw_effective_shots(shots: int, reps: int = 1) -> float:
    """Unmitigated baseline: just the shots (times reps)."""
    return float(shots) * reps


def compare_methods(results: list[dict], target_tol: float, metric: str = "err") -> list[dict]:
    """Rank methods by effective shots among those that meet a quality target.

    ``results`` rows must carry ``method``, ``effective_shots``, and ``metric`` keys
    (``metric`` is the achieved error, lower = better). Rows meeting ``metric <=
    target_tol`` are returned first, sorted by ascending effective shots (cheapest
    method that reaches the target wins); rows that miss the target follow, sorted by
    achieved error. This is the ranking behind the "which method pays" figure.
    """
    def key(r):
        meets = r[metric] <= target_tol
        # meeters first (0), by effective_shots; missers (1), by error
        return (0, r["effective_shots"]) if meets else (1, r[metric])

    ranked = sorted(results, key=key)
    for r in ranked:
        r["meets_target"] = bool(r[metric] <= target_tol)
    return ranked


def shots_to_target_curve(effective_shots, errors, target_tol: float) -> float:
    """Interpolate the effective shots at which ``errors`` first reaches ``target_tol``.

    ``effective_shots``/``errors`` are paired samples of a method's error as cost
    grows (e.g. increasing reps/n_train). Returns the interpolated effective-shots
    crossing, or ``inf`` if the target is never reached. Monotonicity is not assumed;
    the first downward crossing is used.
    """
    xs = np.asarray(effective_shots, float)
    ys = np.asarray(errors, float)
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    if np.all(ys > target_tol):
        return float("inf")
    if ys[0] <= target_tol:
        return float(xs[0])
    for i in range(1, len(xs)):
        if ys[i] <= target_tol < ys[i - 1]:
            # linear interpolation of the crossing
            frac = (ys[i - 1] - target_tol) / (ys[i - 1] - ys[i])
            return float(xs[i - 1] + frac * (xs[i] - xs[i - 1]))
    return float(xs[np.argmin(ys)])
