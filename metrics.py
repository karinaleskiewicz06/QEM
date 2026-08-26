"""Classifier metrics — accuracy and macro-F1 (shared by the method runners).

Labels are in {-1, +1}; predictions are sign(<O>). macro-F1 = the unweighted mean
of the per-class F1, so it does not collapse to the majority class on imbalanced
sets. On a *balanced* eval set (e.g. two_curves) macro-F1 tracks accuracy closely;
it earns its keep on imbalanced tasks.
"""

from __future__ import annotations

import numpy as np


def accuracy(y_true, y_pred) -> float:
    """Fraction of correct sign predictions."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    if y_true.size == 0:
        return 0.0
    return float(np.mean(y_true == y_pred))


def macro_f1(y_true, y_pred, labels=(-1, 1)) -> float:
    """Unweighted mean of per-class F1 over ``labels`` (default the {-1,+1} classes)."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    f1s = []
    for c in labels:
        tp = int(np.sum((y_pred == c) & (y_true == c)))
        fp = int(np.sum((y_pred == c) & (y_true != c)))
        fn = int(np.sum((y_pred != c) & (y_true == c)))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return float(np.mean(f1s))
