"""Tests for accuracy / macro-F1."""

from __future__ import annotations

import numpy as np

from metrics import accuracy, macro_f1


def test_perfect_prediction():
    y = np.array([-1, 1, 1, -1, 1])
    assert accuracy(y, y) == 1.0
    assert macro_f1(y, y) == 1.0


def test_all_wrong():
    y = np.array([-1, 1, -1, 1])
    assert accuracy(y, -y) == 0.0
    assert macro_f1(y, -y) == 0.0


def test_balanced_f1_tracks_accuracy():
    y = np.array([-1, -1, 1, 1])
    pred = np.array([-1, 1, 1, 1])  # one -1 misclassified as +1
    assert accuracy(y, pred) == 0.75
    # macro-F1: class +1 F1 = 2*(2/3*1)/(2/3+1)=0.8 ; class -1 F1=2*(1*0.5)/1.5=0.667
    assert abs(macro_f1(y, pred) - np.mean([0.8, 2 / 3])) < 1e-9


def test_majority_collapse_penalised_by_f1():
    # imbalanced: 8 of class +1, 2 of class -1; predict all +1
    y = np.array([1] * 8 + [-1] * 2)
    pred = np.array([1] * 10)
    assert accuracy(y, pred) == 0.8         # accuracy looks OK
    assert macro_f1(y, pred) < 0.5          # but macro-F1 exposes the collapse
