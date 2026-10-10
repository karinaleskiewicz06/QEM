
### Runners

`run_odra_cdr.py`, `run_garnet_cdr.py`, `run_garnet_twirl.py`, `run_garnet_qec.py`,
`run_hardware.py`, `zne_shot_boundary.py`, `train_star_depth.py`, `overnight_odra.sh`

### Results

CSVs are named `<device>_<experiment>.csv` — e.g. `odra_twirl_o1.csv`, `odra_kappa_k7.csv`,
`garnet_twirl_banded.csv`, `emerald_xtopo.csv`. Every hardware row carries its shot count and
transpiled CZ count, so methods can be compared at matched cost rather than matched iterations.

### Documents

- `final_raport.pdf` — full report (Polish)
- `methodology_month_2.md` — protocols and decision rules
- `hardware_runbook.md` — submission procedures
- `dataset_specification.md` — task and evaluation subset

---

## Reproducing

Python 3.11+ (3.13 is not supported — `qiskit-iqm` does not build cleanly).

```bash
pip install "qiskit>=2.0,<3.0" qiskit-aer qiskit-machine-learning torch \
            scikit-learn matplotlib "qiskit-iqm>=15" "iqm-client[qiskit]>=33,<35"
```

```bash
export KMP_DUPLICATE_LIB_OK=TRUE   # torch + Aer OpenMP conflict
pytest                              # 42 tests across 5 files
```

Everything runs on the simulator without credentials:

```bash
python run_odra_cdr.py --sim
```

Hardware submission needs `IQM_TOKEN` (plus `IQM_SERVER_URL` for ODRA, or
`IQM_RESONANCE_URL` for Garnet and Emerald). Without `--submit` or `--sim` the runners only build
circuits and report cost — nothing is sent.

Trained weights and the frozen evaluation reference live in `trained_models_hard/`; `LOCKED.json`
names the model used throughout. The reference (exact noiseless ⟨O⟩ on a seeded 30-point subset)
was frozen before any noise work, so ground truth cannot drift mid-campaign.

---

## Limitations

Stated plainly, because they bound what the numbers mean:

- Error bars come from **2–3 calibration windows**, not from repetitions within a window. Drift
  between windows is the dominant uncertainty.
- **One task, one model, one observable.** Whether the thresholds are properties of `two_curves`
  rather than of routing cost is untested.
- Garnet's multi-window ladder has **three rungs** (12, 57, 96 CZ) — a credit-budget limit, not an
  absence of effect. A fourth point at 36 CZ exists from a single run (`garnet_cdr_results.csv`,
  r² = 0.952) but was not repeated across windows. Garnet's worst rung (0.827) does not cross the
  threshold within the range measured.
- The Garnet 96 CZ twirling point is **unresolved**: between-window spread (±0.108) exceeded the
  effect (+0.073). Per-window gains were +0.039, +0.194, −0.013.
- The routing-vs-depth control (above) **does not isolate routing** from two-qubit gate count. A
  clean version would match 1q gate count and depth as well.
- At 5 qubits mitigation is not *needed* — ground truth is computable. The methods here are being
  **characterized**, not applied. The near-Clifford construction is kept because it is what makes
  CDR viable at scales where ground truth is not available.

## Next step

Validate `r²` as a coherence probe against an established measure — **unitarity RB**, where purely
stochastic noise gives `u = p²` and coherent noise gives `u > p²`. If `u − p²` tracks `1 − r²`
along the ladder, the probe stops being a hypothesis. `run_garnet_urb.py` implements the Wallman
estimator and is ready; it needs machine time.

---

## Context

Two-month research project for **KN Axion**, Wrocław University of Science and Technology.
Month 1 validated the simulation↔hardware pipeline; Month 2 produced the cross-topology,
cross-method characterization above.
