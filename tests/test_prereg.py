"""The frozen pre-registered analysis: Holm, pairing and the registered directions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.prereg_w01 import holm, one_sided, paired


def test_holm_matches_the_step_down_definition():
    rows = [{"p": 0.01}, {"p": 0.04}, {"p": 0.03}, {"p": 0.20}]
    holm(rows)
    # sorted 0.01, 0.03, 0.04, 0.20 -> 0.04, 0.09, 0.09 (monotone), 0.20
    assert [round(r["p_holm"], 4) for r in rows] == [0.04, 0.09, 0.09, 0.2]
    assert [r["reject"] for r in rows] == [True, False, False, False]


def _cdr(errs_a, errs_b):
    rows = []
    for k, (ea, eb) in enumerate(zip(errs_a, errs_b)):
        for arm, e in (("spread", ea), ("twirl_native", eb)):
            rows.append({"rung": "star", "eval_index": k, "arm": arm, "train_set": "near_target",
                         "fit": "ols", "err": e, "err_raw": 0.1, "ideal": 0.3,
                         "mitigated": 0.3 + e, "raw": 0.2})
    return pd.DataFrame(rows)


def test_pairing_and_direction():
    rng = np.random.default_rng(0)
    b = rng.uniform(0.05, 0.1, 16)
    j = paired(_cdr(b * 0.5, b), ("spread", "near_target"), ("twirl_native", "near_target"))
    assert len(j) == 16
    r = one_sided(j, "H6", "spread", "twirl_native")
    assert r["ratio"] == pytest.approx(0.5) and r["p"] < 0.001 and r["a_better"] == 16
    worse = one_sided(paired(_cdr(b * 2, b), ("spread", "near_target"),
                             ("twirl_native", "near_target")), "H6", "s", "t")
    assert worse["p"] > 0.99          # one-sided: no claim when a is worse
