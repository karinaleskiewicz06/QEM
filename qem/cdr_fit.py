"""CDR's linear fit, with and without a correction for noise in the regressor.

``fit_cdr`` (ordinary least squares, in :mod:`cdr`, unchanged) assumes the x values are
known exactly. They are not: each is an expectation value estimated from a finite number
of shots. Noise in a regressor biases an OLS slope *toward zero* -- regression dilution --
by a factor ``var(x_true) / (var(x_true) + sigma_x^2)``. CDR then under-corrects.

The correction is to subtract the known measurement variance from the denominator::

    a = cov(x, y) / (var(x) - mean(sigma_x^2))

which is unbiased when ``sigma_x^2`` is right. Its weakness is that the denominator can
approach zero -- or go negative -- when the training values barely spread, and the slope
then explodes. The archived benchmark caps de-attenuation at 4x for exactly this reason,
and that cap is kept here.

**Both estimates are reported.** Which is appropriate depends on how much of the spread
in x is real, and that varies along the ladder; reporting only one would hide the choice.
"""

from __future__ import annotations

import dataclasses

import numpy as np

#: Largest factor by which the slope may be inflated relative to OLS.
MAX_DEATTENUATION = 4.0


@dataclasses.dataclass(frozen=True)
class CDRFit:
    """A fitted correction ``ideal ~= a * noisy + b``."""

    a: float
    b: float
    r2: float
    method: str                  #: "ols" or "eiv"
    x_var_mean: float = 0.0      #: mean measurement variance subtracted (eiv only)
    capped: bool = False         #: the de-attenuation cap bound the result

    def apply(self, noisy: float) -> float:
        return self.a * float(noisy) + self.b


def _r2(x: np.ndarray, y: np.ndarray, a: float, b: float) -> float:
    pred = a * x + b
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0


def fit_ols(noisy, ideal) -> CDRFit:
    """Plain least squares, matching :func:`cdr.fit_cdr`."""
    x = np.asarray(noisy, float)
    y = np.asarray(ideal, float)
    A = np.vstack([x, np.ones_like(x)]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    return CDRFit(float(a), float(b), _r2(x, y, a, b), "ols")


def fit_cdr_eiv(noisy, ideal, x_var) -> CDRFit:
    """Errors-in-variables fit: subtract the measurement variance from ``var(x)``.

    Args:
        noisy: measured training values.
        ideal: their exact values.
        x_var: per-point variance of each ``noisy`` estimate. Scalar or per-point.

    The denominator is floored at ``var(x) / MAX_DEATTENUATION``, so the slope can
    exceed the OLS one by at most that factor; ``capped`` records when the floor bound
    the result, which is a sign that the training set has too little real spread for the
    correction to be trustworthy.
    """
    x = np.asarray(noisy, float)
    y = np.asarray(ideal, float)
    vx = float(np.mean(np.asarray(x_var, float)))

    var_x = float(np.var(x, ddof=1))
    cov_xy = float(np.cov(x, y, ddof=1)[0, 1])

    denom = var_x - vx
    floor = var_x / MAX_DEATTENUATION
    capped = denom < floor
    if capped:
        denom = floor

    a = cov_xy / denom if denom > 1e-12 else 0.0
    b = float(y.mean() - a * x.mean())
    return CDRFit(float(a), b, _r2(x, y, a, b), "eiv", x_var_mean=vx, capped=capped)


def shot_variance_mean_z(expval: float, n_qubits: int, shots: int) -> float:
    """Variance of a mean-Z estimate from ``shots`` shots.

    For ``O = (1/n) sum_q Z_q`` with independent qubits, ``var(O) = (1 - <O>^2) / (n*S)``.
    Qubits are correlated in practice, so this is an approximation -- adequate as the
    ``x_var`` of a spread arm, where each point is measured once and no empirical
    variance is available.
    """
    return (1.0 - float(expval) ** 2) / (n_qubits * shots)


def block_variance(values) -> float:
    """Variance of a point's mean, from its own repeats.

    For an arm that measures each training point M times -- M identical copies or M
    frames -- the spread across repeats estimates the measurement variance directly,
    with no model of the readout. Returns the variance *of the mean*, which is what
    enters the fit.
    """
    v = np.asarray(values, float)
    if v.size < 2:
        return 0.0
    return float(np.var(v, ddof=1) / v.size)


def spread_x_variance(expval: float, n_qubits: int, shots: int,
                      target_frame_values) -> float:
    """``x_var`` for a spread arm: shot noise plus frame-to-frame spread.

    A spread point is measured once, with one frame, so neither component can be
    estimated from the point itself. The shot term comes from the model above; the frame
    term is taken from the target, which *is* measured with M frames and sees the same
    frame-to-frame variability.
    """
    shot_term = shot_variance_mean_z(expval, n_qubits, shots)
    frames = np.asarray(target_frame_values, float)
    if frames.size < 2:
        return shot_term
    return shot_term + float(np.var(frames, ddof=1))


def fit_both(noisy, ideal, x_var) -> dict[str, CDRFit]:
    """Both fits, so a result can report them side by side."""
    return {"ols": fit_ols(noisy, ideal), "eiv": fit_cdr_eiv(noisy, ideal, x_var)}
