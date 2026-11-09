"""Where does the simulator line's accuracy come from? (exploratory, offline, no QPU)

Three ways to get the line s, c that is inverted on the hardware target, same points:

* count formula: E = f + g exp(-(k_cz CZ + k_t t + k_prx PRX/10)) ideal, fitted to all
  hardware training circuits of the night (the earlier noise-model inversion, nicdr);
* full simulator: device model from the night's calibration, per qubit and per gate,
  CDR line fitted on the simulated 20 training circuits of each point;
* uniform simulator: the same, but every qubit gets the mean T1, T2, PRX fidelity and
  readout error and every CZ the mean fidelity.

If the uniform simulator falls back towards the count formula, the accuracy comes from
per-qubit detail, not from the number of gates.

    python -m paper_analysis.line_source_compare
"""
from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import dataclasses  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pathlib  # noqa: E402
import re  # noqa: E402
from collections import defaultdict  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister  # noqa: E402
from qiskit.circuit.library import RGate  # noqa: E402
from scipy.stats import wilcoxon  # noqa: E402

from nicdr.common import fit_noise  # noqa: E402
from paper_analysis.paper_figs_v3 import asap_us  # noqa: E402
from sim.device_model import build_noise_model, load_calibration  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
HW = REPO / "runs" / "odra_campaign"
CAL = REPO / "calibrations"
OUT = REPO / "paper_analysis" / "out"
SHOTS = 65536
_NUM = re.compile(r"^[0-9eE.+\-*/ ()pi]+$")


def _angle(x: str) -> float:
    x = x.strip()
    if not _NUM.match(x):
        raise ValueError(f"unexpected angle expression {x!r}")
    return float(eval(x, {"__builtins__": {}}, {"pi": math.pi}))  # noqa: S307 - checked above


def circuit_from_qasm(q: str) -> QuantumCircuit:
    """Rebuild a native circuit from the stored QASM3 ($k = logical qubit k)."""
    qr, cr = QuantumRegister(5, "q"), ClassicalRegister(5, "meas")
    c = QuantumCircuit(qr, cr)
    in_gate = False
    for line in q.split("\n"):
        s = line.strip()
        if s.startswith("gate"):
            in_gate = True
            continue
        if in_gate:
            in_gate = not s.startswith("}")
            continue
        qs = [int(a or b) for a, b in re.findall(r"\$(\d+)|q\[(\d+)\]", s)]
        if s.startswith("r("):
            a, b = s[2:s.index(")")].split(",")
            c.append(RGate(_angle(a), _angle(b)), [qs[0]])
        elif s.startswith("cz"):
            c.cz(qs[0], qs[1])
        elif s.startswith("delay"):
            c.delay(float(re.match(r"delay\[([0-9.e+\-]+)s\]", s).group(1)), qs, unit="s")
        elif s.startswith("barrier"):
            c.barrier(qs if qs else None)
        elif "measure" in s:
            bit = int(re.search(r"meas\[(\d+)\]", s).group(1))
            c.measure(qs[-1], bit)
    return c


def mean_z(counts: dict) -> float:
    n = sum(counts.values())
    return sum(k * sum(0.2 * (1 - 2 * int(b[::-1][i])) for i in range(5)) for b, k in counts.items()) / n


def uniform(cal):
    m = lambda a: np.full_like(a, float(np.mean(a)))  # noqa: E731
    fcz = float(np.mean(list(cal.f_cz.values())))
    return dataclasses.replace(cal, t1=m(cal.t1), t2=m(cal.t2), t2_echo=m(cal.t2_echo),
                               f_prx=m(cal.f_prx), e01=m(cal.e01), e10=m(cal.e10),
                               f_cz={k: fcz for k in cal.f_cz}, source=cal.source + "#uniform")


def load(window: str) -> dict:
    """{(rung, point): {"target": rec-list, "train": {i: rec-list}}} for off_copies."""
    g: dict = defaultdict(lambda: {"target": [], "train": defaultdict(list)})
    for line in open(HW / window / "counts.jsonl"):
        d = json.loads(line)
        if d.get("kind") != "cdr" or d.get("arm") != "off_copies" or d.get("train_set") != "near_target":
            continue
        k = (d["rung"], int(d["eval_index"]))
        if d["role"] == "target":
            g[k]["target"].append(d)
        else:
            g[k]["train"][int(d["train_index"])].append(d)
    return g


def main() -> None:
    rows = []
    for w in ("w01A", "w01B", "w01P5"):
        groups = load(w)
        cal = load_calibration(CAL / f"odra_raw_{w}_start.json")
        models = {"full": build_noise_model(cal), "uniform": build_noise_model(uniform(cal))}
        # count formula on all hardware training circuits of the night
        E, I, CZ, T, P = [], [], [], [], []
        for v in groups.values():
            for recs in v["train"].values():
                E.append(np.mean([r["expval"] for r in recs])); I.append(recs[0]["ideal"])
                CZ.append(recs[0]["n_cz"]); T.append(asap_us(recs[0]["qasm3"])); P.append(recs[0]["n_prx"])
        fit = fit_noise("M_3", E, I, CZ, T, P)
        print(w, "count formula", fit.name, {k: round(v, 4) for k, v in fit.rates.items()},
              f"f={fit.f:.3f} g={fit.g:.3f}", flush=True)
        for (rung, pt), v in sorted(groups.items()):
            tgt = v["target"]
            raw = float(np.mean([r["expval"] for r in tgt]))
            ideal = float(tgt[0]["ideal"])
            feat = {"cz": tgt[0]["n_cz"], "t": asap_us(tgt[0]["qasm3"]), "prx": tgt[0]["n_prx"] / 10}
            s_cnt = fit.g * math.exp(-sum(fit.rates[k] * feat[k] for k in fit.terms))
            row = dict(window=w, rung=rung, n_cz=tgt[0]["n_cz"], point=pt, ideal=ideal, raw=raw,
                       err_raw=abs(raw - ideal), err_count=abs((raw - fit.f) / s_cnt - ideal))
            trains = [v["train"][i][0] for i in sorted(v["train"])]
            circs = [circuit_from_qasm(r["qasm3"]) for r in trains]
            ys = np.array([r["ideal"] for r in trains])
            for name, dm in models.items():
                xs = np.array([mean_z(c) for c in dm.run(circs, SHOTS, seed=7)])
                a, b = np.polyfit(xs, ys, 1)
                row[f"err_{name}"] = abs(a * raw + b - ideal)
            rows.append(row)
        print(w, "done", len(rows), flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "line_source_points.csv", index=False)
    cdr = pd.read_csv(OUT / "sim_line_points.csv")[["window", "rung", "point", "err_cdr", "err_sim_rung"]]
    d = d.merge(cdr, on=["window", "rung", "point"], how="left")
    cols = ["err_raw", "err_count", "err_uniform", "err_full", "err_cdr"]
    lines = [d.groupby(["window", "rung", "n_cz"])[cols].mean().round(4).sort_values("n_cz").to_string(), ""]
    for a in ("err_count", "err_uniform", "err_full"):
        for b in ("err_raw", "err_cdr"):
            x, y = np.log(np.maximum(d[a], 1e-4)), np.log(np.maximum(d[b], 1e-4))
            lines.append(f"{a:12s} vs {b:8s}: wins {(d[a] < d[b]).sum()}/{len(d)}, geo {np.exp(np.mean(x - y)):.3f}, "
                         f"p = {wilcoxon(x, y).pvalue:.2g}")
    x, y = np.log(np.maximum(d.err_uniform, 1e-4)), np.log(np.maximum(d.err_full, 1e-4))
    lines.append(f"uniform vs full: wins {(d.err_uniform < d.err_full).sum()}/{len(d)}, geo {np.exp(np.mean(x - y)):.3f}, p = {wilcoxon(x, y).pvalue:.2g}")
    lines.append(f"check: this full-sim line vs earlier sim line (per point) mean err {d.err_full.mean():.4f}")
    txt = "\n".join(lines)
    (OUT / "line_source_compare.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
