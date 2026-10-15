# Where Quantum Error Mitigation Stops Paying Off

**A topology-resolved study of how routing overhead breaks quantum error-mitigation methods — on three superconducting devices.**

The circuit you write is not the circuit that runs. Two-qubit gates act only on physically
adjacent qubits, so a compiler inserts SWAPs to move qubits together. Those extra gates compute
nothing, but they carry the same noise as the ones that do. The same 5-qubit classifier costs
anywhere from **12 to 114 two-qubit gates** depending on the device and the placement.

This repository asks what that overhead does to the methods meant to clean up the result.

---

## Key results

### 1. CDR's breakdown is topology-general, but its threshold is not

`r²` of the CDR fit, measured on hardware along the routing ladder:

| device | topology | CZ | r² across the ladder |
|---|---|---|---|
| ODRA | star, 5q | 12 / 27 / 36 / 54 | 0.958 → 0.809 → 0.792 → **0.598** |
| Garnet | lattice, 20q | 12 / 57 / 96 | 0.969 → 0.853 → 0.827 |
| Emerald | lattice, 54q | 21 / 63 / 69 / 114 | 0.962 → 0.961 → 0.873 → **0.683** |

Monotonic decay on every device. The *shape* is universal; the *rate* is not — the star crosses
`r² = 0.8` at roughly **32 CZ**, the lattices at roughly **86 CZ**. Thresholds do not transfer
between topologies.

Garnet values are averaged over three calibration windows (`garnet_twirl_w123_banded.csv`); ODRA
and Emerald are single-campaign runs (`odra_full_100pt.csv`, `emerald_xtopo.csv`).

### 2. The cause is coherent error — established by controlled experiment

Twirling gain under noise of known character (simulation, so the noise is set by us):

| noise | twirl gain |
|---|---|
| incoherent (simulated) | **−0.008** |
| Garnet (hardware) | +0.053 |
| coherent, θ = 0.05 | +0.137 |
| coherent, θ = 0.10 | +0.404 |

The first row is a **null control**: had twirling helped there, the mechanism would be falsified.
Hardware sits above the incoherent floor and inside the band set by injected coherence.

### 3. The same effect appears on real hardware

Shot-matched twirling gain (the no-twirl arm gets the same shot budget, otherwise the extra
averaging alone inflates `r²`):

| device | CZ | Δr² | windows | verdict |
|---|---|---|---|---|
| Garnet | 12 | +0.016 ± 0.019 | 3 | within drift |
| Garnet | 57 | **+0.069 ± 0.023** | 3 | significant |
| Garnet | 96 | +0.073 ± 0.108 | 3 | **unresolved** — spread exceeds the effect |
| ODRA | 12 | +0.011 ± 0.001 | 2 | significant but small |
| ODRA | 30 | **+0.144 ± 0.040** | 2 | significant |
| ODRA | 39 | +0.193 ± 0.161 | 2 | significant, wide |
| ODRA | 57 | **+0.160 ± 0.043** | 2 | significant |

Near-zero gain at the cheapest points is the predicted behaviour — the circuit is too shallow for
coherent error to accumulate, so there is nothing for twirling to undo.

**Gate count does not predict twirling gain. Measured `r²` does.**

Across the nine Garnet hardware measurements (3 ladder points × 3 calibration windows):

| predictor | Spearman ρ | p |
|---|---|---|
| two-qubit gate count | +0.32 | 0.41 — not significant |
| measured `r²` without twirling | **−0.85** | **0.004** |

The same circuit at the same gate count gave gains of +0.039, +0.194 and −0.013 across the three
windows. Gate count says how much coherent error *could* have accumulated; `r²` says how much
actually did — and it comes free with a fit you had to run anyway.

**Regression-to-the-mean control.** Correlating `Δ = ON − OFF` against `OFF` is vulnerable to
mathematical coupling: measurement noise in `r²(OFF)` enters both quantities with opposite signs.
The size of that artifact was measured directly on incoherent-noise control data (n = 15):
ρ = −0.39, **not significant** (p = 0.16). The hardware value (−0.85) clears it comfortably and
sits in the range set by injected coherence (−0.91 at θ = 0.05, −0.82 at θ = 0.10).

**This is a preliminary result.** n = 9 is small; a single outlying ladder point could move the
coefficient noticeably.

### 4. ZNE's cost–benefit boundary, derived before measurement

ZNE trades bias for variance. With a fixed shot budget `S` split across `|Λ|` noise levels, the
added variance is `κ V / S` with

```
κ = (Σ cᵢ²) · |Λ| − 1
```

where `cᵢ` are the Richardson coefficients. `κ` depends only on the chosen node set — not on the
device, not on the circuit. ZNE pays off only when `S > S* = κV/B²`.

| node set Λ | κ predicted | κ measured |
|---|---|---|
| {1, 3} | 4.00 | 3.39 ± 0.40 |
| {1, 3, 5} | 14.66 | 14.16 ± 0.83 |
| {1, 3, 5, 7} | 44.56 | 48.07 ± 5.99 |

Three node sets spanning an **11× range**, every value computed on paper before the corresponding
measurement, with no parameter fitted to data.

> Note: the written report covers the first two node sets (a 3.66× range). The `{1,3,5,7}`
> measurement is in `odra_kappa_k7.csv` but is not yet written up there.

### Control: is it routing, or just gate count?

Matching two-qubit gate count between a routing-heavy arm and a zero-routing arm made deeper:

| CZ | routing-sourced | depth-sourced | difference |
|---|---|---|---|
| 24 | 0.839 | 0.827 | −0.011 |
| 36 | 0.792 | 0.719 | −0.073 |
| 52 | 0.620 | 0.444 | −0.175 |

The depth arm is measured directly (`odra_depth_L6/L9/L13.csv`, zero routing by construction —
`star` fits the hardware exactly). The routing arm is **interpolated** from the four-rung ladder in
`odra_full_100pt.csv` to match the depth arm's gate counts.

**This came out the opposite way to the framing.** The depth arm loses, despite being favoured on
every confound (fewer 1q gates, shorter depth). The honest reading: **two-qubit gate cost decides**,
and routing is its dominant source — the one you do not get to choose.

### Methods that did not work

| method | outcome | why |
|---|---|---|
| REM | ε improves by 0.9%, **61/61 decisions unchanged** | gate error dominates, not readout |
| DD | **worse at every rung** — ε 0.1115 → 0.1591 at 12 CZ, 0.3565 → 0.4583 at 54 CZ | DD pulses are gates too; idle windows too short |
| `[[4,2,2]]` detection | post-selection cost > benefit | code needs Clifford circuits; VQC has continuous rotations |
| twirling + ZNE | no payoff | ZNE assumes smoothness, not linearity — less to recover |

Each failed exactly where its assumption stopped holding.

---

## Setup

- **Task** — `two_curves` (8 features, 2 classes), hard variant with a narrow margin
- **Model** — variational classifier, 5 qubits, 3 layers, **weights frozen** after one training run
- **Observable** — mean Z over all five qubits
- **Routing ladder** — four entanglement patterns compiled onto each device:

  | pattern | logical CX | CZ after transpilation | added by routing |
  |---|---|---|---|
  | `star` | 12 | 12 | **0** |
  | `linear` | 12 | 27 | **+15** |
  | `circular` | 15 | 36 | **+21** |
  | `all_to_all` | 30 | 54 | **+24** |

  `linear` has the same number of logical gates as `star` and costs 15 more on hardware. That gap
  is the phenomenon.

- **Devices** — IQM ODRA (star, 5q), IQM Garnet (lattice, 20q), IQM Emerald (lattice, 54q)

Ground truth is computed exactly by statevector (5 qubits = 32 amplitudes). Noisy values are
**measured on hardware**, not simulated — the only deliberately simulated result is the mechanism
test (#2), where the noise character has to be known in advance.

---

## Repository layout

### Core modules

| file | role |
|---|---|
| `ansatz.py` | parameterized VQC; entanglement patterns |
| `topology.py` | coupling maps, qubit placements — single source of truth |
| `noisy_sim.py` | device calibration, Aer noise model, expectation values |
| `cdr.py` | near-Clifford training sets, linear fit, `r²` |
| `zne_dryrun.py` | unitary folding, Richardson extrapolation |
| `qec422.py` | `[[4,2,2]]` encoding and post-selection |
| `metrics.py`, `shots_to_target.py` | shared metrics and cost accounting |

### Hardware adapters

| file | device |
|---|---|
| `iqm_resonance.py` | Garnet, Emerald (IQM Resonance) |
| `odra_backend.py` | ODRA (`iqm-client`, with logical→physical readout remapping) |

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
