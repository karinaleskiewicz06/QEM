"""The 24 evaluation points of the campaign, fixed once and shared by every window.

The archived campaigns used the first four reference points, so every error was a mean
of four and no per-point distribution existed. Here the points are drawn from the
classifier's frozen evaluation set (``X_eval``, 100 points of ``two_curves``), stratified
by the ideal margin |<O>| of the base model (star, L3): four quartile strata, six points
each, evenly spaced in rank within the stratum. Deterministic, no seed.

The selection depends only on the frozen model, so regenerating it reproduces the file;
``campaign/eval_points.json`` is the committed copy every window reads.

    python -m campaign.eval_points            # (re)write campaign/eval_points.json
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from noisy_sim import readout_observable

MODELS = pathlib.Path("trained_models_hard")
PATH = pathlib.Path("campaign/eval_points.json")
N_POINTS, N_STRATA = 24, 4


def reference_set(models_dir: pathlib.Path = MODELS) -> np.ndarray:
    return np.load(models_dir / "two_curves_d8_q5_deg8_star_mean_L3_reference.npz")["X_eval"]


def ideal_margins(X: np.ndarray, pattern: str = "star", layers: int = 3,
                  models_dir: pathlib.Path = MODELS) -> np.ndarray:
    """|<O>_ideal| of the frozen model for every row of ``X``."""
    w = np.load(models_dir / f"two_curves_d8_q5_deg8_{pattern}_mean_L{layers}_weights.npy")
    ans = HardwareEfficientAnsatz(5, layers, num_features=8, entanglement=pattern)
    c = ans.build()
    cw = c.assign_parameters(dict(zip(ans.weight_parameters(c), w)))
    xp = ans.feature_parameters(c)
    obs = readout_observable(5, "mean")
    return np.array([abs(float(np.real(Statevector.from_instruction(
        cw.assign_parameters(dict(zip(xp, x)))).expectation_value(obs)))) for x in X])


def select(margins: np.ndarray, n_points: int = N_POINTS, n_strata: int = N_STRATA) -> list[int]:
    """Indices into the reference set: ``n_points / n_strata`` per margin quartile."""
    if n_points % n_strata:
        raise ValueError("n_points must be a multiple of n_strata")
    per = n_points // n_strata
    order = np.argsort(margins, kind="stable")
    out = []
    for stratum in np.array_split(order, n_strata):
        pick = np.linspace(0, len(stratum) - 1, per).round().astype(int)
        out += [int(stratum[i]) for i in pick]
    return out


def build(models_dir: pathlib.Path = MODELS) -> dict:
    X = reference_set(models_dir)
    m = ideal_margins(X, models_dir=models_dir)
    idx = select(m)
    strata = np.array_split(np.argsort(m, kind="stable"), N_STRATA)
    which = {int(i): s for s, st in enumerate(strata) for i in st}
    return {"source": str(models_dir / "two_curves_d8_q5_deg8_star_mean_L3_reference.npz"),
            "stratified_by": "|<O>_ideal| of star L3, quartiles", "n_points": len(idx),
            "points": [{"eval_index": k, "reference_index": i, "stratum": which[i],
                        "margin_star_L3": round(float(m[i]), 6),
                        "x": [float(v) for v in X[i]]} for k, i in enumerate(idx)]}


def load(path: pathlib.Path | str = PATH) -> list[dict]:
    """The committed points; raises if missing, so no window silently picks its own."""
    p = pathlib.Path(path)
    if not p.exists():
        raise SystemExit(f"{p} missing: run `python -m campaign.eval_points` once and commit it")
    return json.loads(p.read_text())["points"]


def main() -> None:
    data = build()
    PATH.write_text(json.dumps(data, indent=1) + "\n")
    ms = [p["margin_star_L3"] for p in data["points"]]
    print(f"wrote {PATH}: {data['n_points']} points, margin {min(ms):.3f}..{max(ms):.3f}")


if __name__ == "__main__":
    main()
