"""ZNE estimators and the diagnostics that say when to distrust them.

Two things went wrong silently before this module existed.

**The clamp.** ``zne_dryrun.extrapolate`` replaced any Richardson estimate with
``|E| > 1.25`` by the linear fit, and said nothing. An overshoot is precisely the signal
Koster & Mauerer (arXiv:2607.09360) ask to be reported, so hiding it broke their
checklist item 3. :func:`extrapolate_flagged` returns the raw estimate together with
``unphysical`` (outside the observable's range) and ``fallback_used`` (the legacy clamp
fired). The legacy behaviour is still reachable with ``legacy_clamp=True``.

**Signal collapse.** When ``E(lambda)`` at the larger scales has fallen to the
observable's floor ``f``, Richardson degenerates into ``c_1 E_1 + (1 - c_1) f`` -- a
rescaling of one measurement that "improves" the error whether or not the noise was
amplified correctly (their Eq. 2). Nothing in a scalar ``E_hat`` reveals that. What
does:

* ``W_neg``: Richardson applied to every basis-state probability; a valid
  extrapolation keeps them non-negative up to shot noise. ``W_neg`` is the total
  negative mass. It needs no ground truth.
* the floor ``f`` measured, not assumed (T1 pulls mean-Z towards +1, so ``f != 0`` on
  transmons), and a tracking test against Eq. 2;
* retention normalised to the ideal value, and the SNR of the largest scale.

The variance side of the ZNE window -- the constant ``kappa`` and its reduction under
Neyman allocation (Scavino Alfaro, arXiv:2605.08251, Remark 3) -- lives here too, so the
help/harm boundary and the collapse boundary are computed from the same coefficients.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable, Literal, Mapping, Sequence

import numpy as np

#: Threshold of the legacy clamp in ``zne_dryrun``. Kept only to reproduce it.
LEGACY_EV_BOUND = 1.25

Counts = Mapping[str, int]

#: ``qiskit``: qubit ``q`` is ``s[-1 - q]`` (``noisy_sim.perqubit_z_from_counts``).
#: ``iqm``: qubit ``q`` is ``s[q]`` (``run_hardware.perqubit_z_iqm``, raw iqm-client).
BitOrder = Literal["qiskit", "iqm"]


# --------------------------------------------------------------------------- #
# Richardson coefficients and the variance constant kappa                        #
# --------------------------------------------------------------------------- #

def richardson_coefficients(scales: Sequence[float]) -> np.ndarray:
    """Lagrange weights ``c_k`` with ``E_hat(0) = sum_k c_k E(lambda_k)``.

    They sum to one. For ``{1, 3, 5}`` they are ``(15/8, -5/4, 3/8)``.

    Raises:
        ValueError: on repeated scales.
    """
    lam = np.asarray(scales, float)
    if len(set(lam.tolist())) != len(lam):
        raise ValueError(f"scales must be distinct; got {list(scales)}")
    return np.array([np.prod([lj / (lj - li) for lj in lam if lj != li]) for li in lam])


def kappa_uniform(scales: Sequence[float]) -> float:
    """``kappa = |Lambda| * sum c_k^2 - 1`` for a budget split equally across scales.

    ``MSE_zne - MSE_raw = kappa V / S + (B_zne^2 - B^2)`` at total budget ``S``; ZNE
    pays only above ``S* = kappa V / (B^2 - B_zne^2)``. 4.0 / 14.656 / 44.5625 for
    ``{1,3}``, ``{1,3,5}``, ``{1,3,5,7}``.
    """
    c = richardson_coefficients(scales)
    return float(len(c) * np.sum(c ** 2) - 1.0)


def kappa_opt(scales: Sequence[float], sigmas: Sequence[float] | None = None) -> float:
    """``kappa`` under Neyman allocation: ``(sum |c_k| sigma_k / sigma_1)^2 - 1``.

    ``sigmas`` are per-shot standard deviations of the observable at each scale, in the
    order of ``scales``; ``sigma_1`` is the first. ``None`` means equal, which gives
    3.0 / 11.25 / 35.0 for the three node sets.
    """
    c = np.abs(richardson_coefficients(scales))
    s = np.ones_like(c) if sigmas is None else np.asarray(sigmas, float)
    if s.shape != c.shape:
        raise ValueError(f"need one sigma per scale; got {len(s)} for {len(c)} scales")
    if s[0] <= 0:
        raise ValueError("sigma at the first scale must be positive")
    return float((np.sum(c * s) / s[0]) ** 2 - 1.0)


def neyman_allocation(total_shots: int, scales: Sequence[float],
                      sigmas: Sequence[float] | None = None) -> list[int]:
    """Split ``total_shots`` across scales as ``n_k ∝ |c_k| sigma_k``.

    Integer shares by largest remainder, so they sum to ``total_shots`` exactly and no
    scale gets zero (a scale with no shots has no estimate at all).

    Raises:
        ValueError: if ``total_shots`` is smaller than the number of scales.
    """
    c = np.abs(richardson_coefficients(scales))
    s = np.ones_like(c) if sigmas is None else np.asarray(sigmas, float)
    if total_shots < len(c):
        raise ValueError(f"cannot give {len(c)} scales at least one shot from {total_shots}")
    w = c * s
    w = w / w.sum()
    # reserve one shot per scale, share the rest
    spare = total_shots - len(c)
    raw = w * spare
    n = np.floor(raw).astype(int)
    for k in np.argsort(-(raw - n), kind="stable")[: spare - int(n.sum())]:
        n[k] += 1
    return [int(x) + 1 for x in n]


def uniform_allocation(total_shots: int, scales: Sequence[float]) -> list[int]:
    """``S // |Lambda|`` per scale -- what the archived kappa campaigns used."""
    return [max(1, int(total_shots) // len(scales))] * len(scales)


# --------------------------------------------------------------------------- #
# Extrapolation, with the failure reported instead of hidden                     #
# --------------------------------------------------------------------------- #

@dataclasses.dataclass(frozen=True)
class ZNEEstimate:
    """One zero-noise estimate and whether it can be taken at face value."""

    value: float           #: what the caller should use
    raw_value: float       #: the extrapolation itself, before any fallback
    kind: str
    unphysical: bool       #: ``raw_value`` outside ``[-bound, bound]`` or not finite
    fallback_used: bool    #: the legacy clamp replaced ``raw_value`` by the linear fit

    def __float__(self) -> float:
        return self.value


def _linear_at_zero(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.polyval(np.polyfit(x, y, 1), 0.0))


def _raw_extrapolation(x: np.ndarray, y: np.ndarray, kind: str) -> float:
    if kind == "linear":
        return _linear_at_zero(x, y)
    if kind == "richardson":
        # exact through all nodes; same arithmetic as zne_dryrun.extrapolate
        return float(np.polyval(np.polyfit(x, y, len(x) - 1), 0.0))
    if kind == "exponential":
        from scipy.optimize import curve_fit
        try:
            p, _ = curve_fit(lambda t, a, b, c: a + b * np.exp(-c * t), x, y,
                             p0=[y[-1], y[0] - y[-1], 0.5], maxfev=20000)
        except (RuntimeError, ValueError):
            return float("nan")
        return float(p[0] + p[1])
    raise ValueError(f"unknown extrapolation {kind!r}")


def extrapolate_flagged(scales: Sequence[float], values: Sequence[float],
                        kind: str = "richardson", *, bound: float = 1.0,
                        legacy_clamp: bool = False) -> ZNEEstimate:
    """Zero-noise extrapolation that reports a blow-up instead of hiding it.

    Args:
        scales, values: noise scales and the measured ``<O>`` at each.
        kind: ``linear``, ``richardson`` or ``exponential``.
        bound: the observable's range, ``max |<O>|`` (1 for mean-Z and hub-Z, in
            general ``sum |coeffs|``). Beyond it the estimate is ``unphysical``.
        legacy_clamp: reproduce ``zne_dryrun.extrapolate``: when the non-linear
            estimate is non-finite or exceeds :data:`LEGACY_EV_BOUND`, return the
            linear fit instead, and set ``fallback_used``.

    Returns:
        A :class:`ZNEEstimate`. Without ``legacy_clamp``, ``value == raw_value``
        always -- including when it is unphysical, which is then flagged.
    """
    x = np.asarray(scales, float)
    y = np.asarray(values, float)
    raw = _raw_extrapolation(x, y, kind)
    unphysical = (not np.isfinite(raw)) or abs(raw) > bound
    value, fallback = raw, False
    if legacy_clamp and kind != "linear" and (not np.isfinite(raw) or abs(raw) > LEGACY_EV_BOUND):
        value, fallback = _linear_at_zero(x, y), True
    return ZNEEstimate(value=float(value), raw_value=float(raw), kind=kind,
                       unphysical=bool(unphysical), fallback_used=bool(fallback))


# --------------------------------------------------------------------------- #
# Per-state extrapolation: W_neg                                                 #
# --------------------------------------------------------------------------- #

def _pool(counts: Counts | Iterable[Counts]) -> dict[str, int]:
    """One counts dict, or the sum of several (e.g. the M frames of a twirled arm)."""
    if isinstance(counts, Mapping):
        return dict(counts)
    out: dict[str, int] = {}
    for c in counts:
        for k, v in c.items():
            out[k] = out.get(k, 0) + int(v)
    return out


def probabilities(counts: Counts | Iterable[Counts], n_qubits: int,
                  bit_order: BitOrder = "qiskit") -> np.ndarray:
    """Basis-state probabilities, indexed so that bit ``q`` of the index is qubit ``q``.

    With ``bit_order="qiskit"`` the convention is that of
    ``noisy_sim.perqubit_z_from_counts``: spaces removed, the last ``n_qubits``
    characters, qubit ``q`` at ``s[-1 - q]``. With ``"iqm"`` it is that of
    ``run_hardware.perqubit_z_iqm``: the first ``n_qubits`` characters, qubit ``q`` at
    ``s[q]``. Getting this wrong permutes the states, which leaves ``W_neg`` intact
    but corrupts anything weighted per qubit.
    """
    if bit_order not in ("qiskit", "iqm"):
        raise ValueError(f"bit_order must be 'qiskit' or 'iqm'; got {bit_order!r}")
    pooled = _pool(counts)
    p = np.zeros(2 ** n_qubits)
    total = 0
    for key, c in pooled.items():
        s = str(key).replace(" ", "")
        bits = (s[-n_qubits:].zfill(n_qubits) if bit_order == "qiskit"
                else s[:n_qubits][::-1])
        p[int(bits, 2)] += c
        total += c
    if total == 0:
        raise ValueError("empty counts")
    return p / total


def marginal_probabilities(p: np.ndarray, n_qubits: int) -> np.ndarray:
    """``(n_qubits, 2)`` array of single-qubit marginals ``P(b_q = 0), P(b_q = 1)``."""
    idx = np.arange(len(p))
    out = np.empty((n_qubits, 2))
    for q in range(n_qubits):
        one = (idx >> q) & 1
        out[q, 1] = p[one == 1].sum()
        out[q, 0] = p[one == 0].sum()
    return out


@dataclasses.dataclass(frozen=True)
class NegativityReport:
    """Richardson applied state by state, and how far it leaves the simplex."""

    p_hat: np.ndarray            #: extrapolated probabilities, 2**n entries
    frac_negative: float         #: fraction of states with ``p_hat < 0``
    min_p: float
    w_neg: float                 #: ``sum |p_hat|`` over negative entries
    w_neg_marginal: np.ndarray   #: the same, per qubit, on the 1q marginals
    min_p_marginal: float

    def as_row(self, prefix: str = "") -> dict[str, float]:
        return {f"{prefix}w_neg": round(self.w_neg, 6),
                f"{prefix}frac_negative": round(self.frac_negative, 6),
                f"{prefix}min_p": round(self.min_p, 6),
                f"{prefix}w_neg_marg": round(float(self.w_neg_marginal.sum()), 6),
                f"{prefix}w_neg_marg_max": round(float(self.w_neg_marginal.max()), 6),
                f"{prefix}min_p_marg": round(self.min_p_marginal, 6)}


def negativity(scales: Sequence[float], counts_per_scale: Sequence[Counts | Iterable[Counts]],
               n_qubits: int, bit_order: BitOrder = "qiskit") -> NegativityReport:
    """``P_hat(s) = sum_k c_k P_s(lambda_k)`` for every basis state, and its negativity.

    Linear extrapolation preserves normalisation (the ``c_k`` sum to one), so only
    negativity can betray it. Small ``W_neg`` is expected from shot noise alone --
    ``c_2 = -5/4`` amplifies it -- so the threshold has to come from a null
    distribution at the campaign's shot count (``sim/calibrate_wneg_null.py``), not
    from Koster & Mauerer's 16-state, 4096-shot figures.

    Args:
        counts_per_scale: one entry per scale; each a counts dict or several to pool.
    """
    if len(counts_per_scale) != len(scales):
        raise ValueError(f"{len(counts_per_scale)} count sets for {len(scales)} scales")
    c = richardson_coefficients(scales)
    probs = [probabilities(cs, n_qubits, bit_order) for cs in counts_per_scale]
    p_hat = sum(ck * pk for ck, pk in zip(c, probs))
    m_hat = sum(ck * marginal_probabilities(pk, n_qubits) for ck, pk in zip(c, probs))
    neg = p_hat < 0
    return NegativityReport(
        p_hat=p_hat,
        frac_negative=float(neg.mean()),
        min_p=float(p_hat.min()),
        w_neg=float(np.abs(p_hat[neg]).sum()),
        w_neg_marginal=np.array([np.abs(row[row < 0]).sum() for row in m_hat]),
        min_p_marginal=float(m_hat.min()),
    )


# --------------------------------------------------------------------------- #
# Signal retention, SNR, floor tracking                                          #
# --------------------------------------------------------------------------- #

def per_shot_variance(counts: Counts | Iterable[Counts], coeffs: Sequence[float],
                      bit_order: BitOrder = "qiskit") -> float:
    """Variance of ``sum_q c_q (1 - 2 b_q)`` over single shots, from the counts."""
    coeffs = np.asarray(coeffs, float)
    n = len(coeffs)
    p = probabilities(counts, n, bit_order)
    idx = np.arange(len(p))
    bits = (idx[:, None] >> np.arange(n)[None, :]) & 1
    v = (1.0 - 2.0 * bits) @ coeffs
    mean = float(p @ v)
    return float(p @ (v - mean) ** 2)


def expval_se(counts: Counts | Iterable[Counts], coeffs: Sequence[float],
              bit_order: BitOrder = "qiskit") -> float:
    """Standard error of ``<O>`` from pooled counts: ``sqrt(V / N_shots)``.

    For a twirled arm the frames are pooled, which treats frame-to-frame spread as
    shot noise. That is what the estimator actually sees when it averages frames.
    """
    pooled = _pool(counts)
    shots = sum(pooled.values())
    return float(np.sqrt(per_shot_variance(pooled, coeffs, bit_order) / shots))


def retention_normalized(e1: float, ideal: float) -> float:
    """``|<O>(1)| / |O_ideal|``: how much of the ideal signal survives at scale 1.

    Unlike the old ``R = |<O>(lambda_max)| / |<O>(1)|`` this does not become a ratio of
    two numbers on the floor when the signal is already gone at scale 1.
    """
    return float(abs(e1) / abs(ideal)) if abs(ideal) > 1e-12 else float("nan")


def snr(value: float, se: float) -> float:
    """``|<O>(lambda_max)| / SE``; below ~2 the largest scale is indistinguishable from 0."""
    return float(abs(value) / se) if se > 0 else float("inf")


def recovery_ratio(e_hat: float, e1: float, ideal: float) -> float:
    """``rho = (E_hat - E_1) / (E_ideal - E_1)``; 1 is full recovery, >1 an overshoot.

    Diverges when ``E_1`` is already close to ideal, which is when ``W_neg`` is the
    better indicator.
    """
    d = ideal - e1
    return float((e_hat - e1) / d) if abs(d) > 1e-12 else float("nan")


def floor_prediction(scales: Sequence[float], e1: float, floor: float) -> float:
    """Eq. 2 of Koster & Mauerer: the estimate if every scale above 1 sat on the floor."""
    c1 = float(richardson_coefficients(scales)[0])
    return c1 * e1 + (1.0 - c1) * floor


def floor_tracking(scales: Sequence[float], e_hat: float, e1: float, floor: float) -> float:
    """``|E_hat - (c_1 E_1 + (1 - c_1) f)|``: small means E_hat is just a rescaled E_1.

    Reported as a distance, with no threshold: the paper's "within 5%" is a heuristic
    read off one figure. A threshold, if any, is fixed in simulation before the
    campaign.
    """
    return float(abs(e_hat - floor_prediction(scales, e1, floor)))


def diagnose_point(scales: Sequence[float], values: Sequence[float], *, ideal: float,
                   kind: str = "richardson", bound: float = 1.0,
                   legacy_clamp: bool = False,
                   counts_per_scale: Sequence[Counts | Iterable[Counts]] | None = None,
                   coeffs: Sequence[float] | None = None,
                   floor: float | None = None,
                   bit_order: BitOrder = "qiskit") -> dict:
    """Everything P3 reports for one evaluation point, as one flat row.

    ``<O>`` at every scale is always included. Count-based fields (``w_neg``, SNR) need
    ``counts_per_scale`` and ``coeffs``; floor tracking needs ``floor``. Missing inputs
    give empty fields rather than an error, so the same row shape serves every runner.
    """
    est = extrapolate_flagged(scales, values, kind, bound=bound, legacy_clamp=legacy_clamp)
    e1 = float(values[0])
    row: dict = {f"ev_lam{_fmt(s)}": float(v) for s, v in zip(scales, values)}
    row.update({
        "ideal": float(ideal),
        "zne": est.value, "zne_raw": est.raw_value,
        "fallback_used": est.fallback_used, "unphysical": est.unphysical,
        "err_raw": abs(e1 - ideal), "err_zne": abs(est.value - ideal),
        "retention_norm": retention_normalized(e1, ideal),
        "retention_R": (abs(values[-1]) / abs(e1)) if abs(e1) > 0 else float("nan"),
        "rho": recovery_ratio(est.value, e1, ideal),
        "snr_lmax": "", "se_lmax": "",
        "floor": "" if floor is None else float(floor),
        "floor_tracking": "" if floor is None else floor_tracking(scales, est.value, e1, floor),
    })
    if counts_per_scale is not None:
        n = len(coeffs) if coeffs is not None else None
        if n is None:
            raise ValueError("coeffs are needed to read counts")
        rep = negativity(scales, counts_per_scale, n, bit_order)
        row.update(rep.as_row())
        se = expval_se(counts_per_scale[-1], coeffs, bit_order)
        row["se_lmax"] = se
        row["snr_lmax"] = snr(values[-1], se)
    return row


def _fmt(s: float) -> str:
    return str(int(s)) if float(s).is_integer() else str(s)
