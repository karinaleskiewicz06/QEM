"""MI-CDR on the recorded hardware data (w01A, w01P5) -- offline, no QPU.

1. Fit the window noise model (M_cz, M_t, M_2, M_3) to all near-Clifford training circuits.
2. Choose the model by leave-one-point-out prediction of held-out training circuits
   (uses training data only; target ideals are never used for any choice).
3. Validate the chosen model out of sample:
   a) on the ZNE-folded targets of night A (lambda = 1, 3, 5): a different circuit family
      with 3x and 5x the gates;
   b) across nights: a model fitted on night A predicts the P5 circuits (old calibration
      only), and vice versa.
4. Mitigate the targets at the SAME shot budget as CDR (the model re-uses CDR's own
   training data): MI (invert the model), MI-LOPO (model fitted without the point's own
   training set), SH (CDR line shrunk toward the model line, strength chosen by CV on
   training circuits). Paired comparison with plain OLS CDR.

    python -m nicdr.hw_model_cdr
"""
from __future__ import annotations

import csv
import json

import numpy as np

from nicdr.common import (MODELS, OUT_HW, cdr_circuits, fit_noise, fmt_paired, ols_line,
                          paired, ridge_to_prior, zne_records)

P5_OLD_CAL = ("star", "star_idle24", "star_idle36", "star_idle52", "star_cz36")
LAMBDAS = [0.0, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]


def train_table(groups: dict, rungs=None):
    rows = []
    for (rung, ei), g in groups.items():
        if rungs is not None and rung not in rungs:
            continue
        for c in g["train"]:
            rows.append({"rung": rung, "eval_index": ei, "E": c.mean(), "var": c.var_of_mean(),
                         "ideal": c.ideal, "n_cz": c.n_cz, "t_us": c.t_us, "n_prx": c.n_prx})
    return rows


def arr(rows, k):
    return np.array([r[k] for r in rows], float)


def fit_rows(name, rows):
    v = np.maximum(arr(rows, "var"), 1e-7)
    return fit_noise(name, arr(rows, "E"), arr(rows, "ideal"), arr(rows, "n_cz"),
                     arr(rows, "t_us"), arr(rows, "n_prx"), w=1.0 / v)


def lopo_rmse(name, rows):
    pts = sorted({(r["rung"], r["eval_index"]) for r in rows})
    se = []
    for p in pts:
        tr = [r for r in rows if (r["rung"], r["eval_index"]) != p]
        te = [r for r in rows if (r["rung"], r["eval_index"]) == p]
        m = fit_rows(name, tr)
        pred = m.predict(arr(te, "ideal"), arr(te, "n_cz"), arr(te, "t_us"), arr(te, "n_prx"))
        se.extend((pred - arr(te, "E")) ** 2)
    return float(np.sqrt(np.mean(se)))


def choose_lambda(groups, model, rungs, k=5, seed=0):
    """Shrinkage strength by K-fold CV on training circuits (ideal of held-out train)."""
    rng = np.random.default_rng(seed)
    score = {lam: [] for lam in LAMBDAS}
    for (rung, ei), g in groups.items():
        if rung not in rungs:
            continue
        tr = g["train"]
        x = np.array([c.mean() for c in tr])
        y = np.array([c.ideal for c in tr])
        att = model.attenuation(g["target"].n_cz, g["target"].t_us, g["target"].n_prx)
        a0 = 1.0 / (model.g * att)
        b0 = -model.f * a0
        folds = np.array_split(rng.permutation(len(tr)), k)
        for lam in LAMBDAS:
            for f in folds:
                mask = np.ones(len(tr), bool)
                mask[f] = False
                a, b = ridge_to_prior(x[mask], y[mask], a0, b0, lam)
                score[lam].extend((a * x[f] + b - y[f]) ** 2)
    return min(LAMBDAS, key=lambda lam: np.mean(score[lam])), {
        lam: float(np.sqrt(np.mean(v))) for lam, v in score.items()}


def mitigate(groups, model_all, model_name, rows, rungs, lam):
    out = []
    for (rung, ei), g in sorted(groups.items()):
        if rung not in rungs:
            continue
        t, tr = g["target"], g["train"]
        x = np.array([c.mean() for c in tr])
        y = np.array([c.ideal for c in tr])
        E = t.mean()
        a, b = ols_line(x, y)
        cdr = a * E + b
        mi = float(model_all.invert(E, t.n_cz, t.t_us, t.n_prx))
        m_lopo = fit_rows(model_name, [r for r in rows if (r["rung"], r["eval_index"]) != (rung, ei)])
        mi_lopo = float(m_lopo.invert(E, t.n_cz, t.t_us, t.n_prx))
        att = model_all.attenuation(t.n_cz, t.t_us, t.n_prx)
        a0 = 1.0 / (model_all.g * att)
        b0 = -model_all.f * a0
        a_s, b_s = ridge_to_prior(x, y, a0, b0, lam)
        sh = a_s * E + b_s
        out.append({"rung": rung, "eval_index": ei, "ideal": t.ideal, "raw": E,
                    "err_raw": abs(E - t.ideal), "err_cdr": abs(cdr - t.ideal),
                    "err_mi": abs(mi - t.ideal), "err_mi_lopo": abs(mi_lopo - t.ideal),
                    "err_sh": abs(sh - t.ideal), "a_cdr": a, "a_model": a0,
                    "shots_target": t.shots, "shots_train": sum(c.shots for c in tr)})
    return out


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main():
    OUT_HW.mkdir(parents=True, exist_ok=True)
    log = []

    def say(s=""):
        print(s)
        log.append(s)

    configs = [("w01A", "off_copies", ("star", "circular")),
               ("w01A", "twirl_native", ("star", "circular")),
               ("w01P5", "off_copies", P5_OLD_CAL)]
    fitted = {}
    all_fit_rows, all_mit_rows = [], []
    for window, arm, rungs in configs:
        tag = f"{window}/{arm}"
        groups = cdr_circuits(window, arm)
        rows = train_table(groups, rungs)
        say(f"\n=== {tag}  rungs {list(rungs)}  training circuits {len(rows)}")
        scores = {}
        for name in MODELS:
            m = fit_rows(name, rows)
            cv = lopo_rmse(name, rows)
            scores[name] = cv
            d = m.as_dict() | {"window": window, "arm": arm, "lopo_rmse": cv}
            all_fit_rows.append(d)
            rates = "  ".join(f"{k}={v:.4f}" for k, v in m.rates.items())
            say(f"  {name:<5s} f={m.f:+.4f} g={m.g:.3f}  {rates:<40s} rmse={m.rmse:.4f}  LOPO={cv:.4f}")
        best = min(scores, key=scores.get)
        model = fit_rows(best, rows)
        fitted[tag] = (best, model, rows, groups)
        say(f"  -> chosen by LOPO: {best}")
        if "t" in model.rates:
            say(f"     signal kept per +1 us: {np.exp(-model.rates['t']):.3f}")
        if "cz" in model.rates:
            say(f"     signal kept per +10 CZ: {np.exp(-10 * model.rates['cz']):.3f}")
        lam, lam_scores = choose_lambda(groups, model, rungs)
        say(f"  shrinkage lambda by CV on training circuits: {lam}  "
            f"(CV rmse {lam_scores[lam]:.4f}; lambda=0 i.e. CDR {lam_scores[0.0]:.4f})")
        mit = mitigate(groups, model, best, rows, rungs, lam)
        for r in mit:
            r.update({"window": window, "arm": arm, "model": best, "lambda": lam})
        all_mit_rows.extend(mit)
        for rung in rungs:
            sub = [r for r in mit if r["rung"] == rung]
            say(f"  [{rung}]")
            for k in ("mi", "mi_lopo", "sh"):
                say("    " + fmt_paired(f"{k.upper()} vs CDR",
                                        paired([r[f"err_{k}"] for r in sub], [r["err_cdr"] for r in sub])))
        if len(rungs) > 1:
            say("  [pooled]")
            for k in ("mi", "mi_lopo", "sh"):
                say("    " + fmt_paired(f"{k.upper()} vs CDR",
                                        paired([r[f"err_{k}"] for r in mit], [r["err_cdr"] for r in mit])))

    # ---- validation (a): ZNE-folded targets of night A ----
    say("\n=== validation (a): night-A model predicts the ZNE-folded targets (genuine, lambda 1/3/5)")
    zr = zne_records("w01A", "genuine")
    val_rows = []
    _, _, rowsA, _ = fitted["w01A/off_copies"]
    for name in MODELS:
        m = fit_rows(name, rowsA)
        for rung in ("star", "circular"):
            for lam in (1, 3, 5):
                sub = [z for z in zr if z["rung"] == rung and z["scale"] == lam]
                pred = m.predict([z["ideal"] for z in sub], [z["n_cz"] for z in sub],
                                 [z["t_us"] for z in sub], [z["n_prx"] for z in sub])
                meas = np.array([z["E"] for z in sub])
                rmse = float(np.sqrt(np.mean((pred - meas) ** 2)))
                val_rows.append({"model": name, "rung": rung, "lambda": lam, "rmse": rmse,
                                 "mean_meas": float(meas.mean()), "mean_pred": float(np.mean(pred)),
                                 "n": len(sub)})
        tot = [v["rmse"] for v in val_rows if v["model"] == name]
        say(f"  {name:<5s} " + "  ".join(f"{v['rung'][:4]} l{v['lambda']}={v['rmse']:.3f}"
                                         for v in val_rows if v["model"] == name)
            + f"   mean rmse {np.mean(tot):.3f}")
    say("  (shot noise of one 8192-shot measurement of mean-Z is about 0.005)")

    # ---- validation (b): across nights ----
    say("\n=== validation (b): cross-night prediction of training + target circuits (RMSE of E)")
    cross_rows = []
    _, _, rowsP, groupsP = fitted["w01P5/off_copies"]
    _, _, rowsA, groupsA = fitted["w01A/off_copies"]
    for name in MODELS:
        mA, mP = fit_rows(name, rowsA), fit_rows(name, rowsP)
        for src, m, dst_rows, dst in (("A", mA, rowsP, "P5"), ("P5", mP, rowsA, "A"),
                                      ("P5", mP, rowsP, "P5(in-sample)"), ("A", mA, rowsA, "A(in-sample)")):
            pred = m.predict([r["ideal"] for r in dst_rows], [r["n_cz"] for r in dst_rows],
                             [r["t_us"] for r in dst_rows], [r["n_prx"] for r in dst_rows])
            rmse = float(np.sqrt(np.mean((pred - np.array([r["E"] for r in dst_rows])) ** 2)))
            cross_rows.append({"model": name, "fit_on": src, "predict": dst, "rmse": rmse})
        say(f"  {name:<5s} " + "  ".join(f"{c['fit_on']}->{c['predict']}={c['rmse']:.4f}"
                                         for c in cross_rows if c["model"] == name))

    write_csv(OUT_HW / "noise_model_fits.csv", all_fit_rows)
    write_csv(OUT_HW / "mi_cdr_points.csv", all_mit_rows)
    write_csv(OUT_HW / "validation_zne_folds.csv", val_rows)
    write_csv(OUT_HW / "validation_cross_night.csv", cross_rows)
    (OUT_HW / "hw_model_cdr.log").write_text("\n".join(log) + "\n")
    print(f"\nwrote {OUT_HW}/noise_model_fits.csv, mi_cdr_points.csv, validation_*.csv, hw_model_cdr.log")


if __name__ == "__main__":
    main()
