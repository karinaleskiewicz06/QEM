# Data notes

What is wrong, or merely surprising, about the data already in this repository. Written
so that a number can be used, or set aside, without having to rediscover its history.

Measurements below were made on the pinned environment (`requirements.lock`): Python
3.13.9, Qiskit 2.4.1, Aer 0.17.2, iqm-client 35.0.0. Where the design documents in
`spec/` report a different figure, they were measured on Qiskit 2.5.2; those cases are
marked.

---

## 1. Two compilation paths, not two Qiskit versions

The repository contained two ways to compile the same circuit, and they disagreed:

| path | used by | CZ ladder on 2.4.1 |
|---|---|---|
| fixed `initial_layout=[0,1,2,3,4]`, `seed_transpiler=42` | `run_garnet_twirl.py` | **12 / 30 / 39 / 57** |
| `zne_dryrun.native_transpile` (no layout, no seed) | `run_odra_cdr.py` | **12 / 27 / 36 / 54** |

Both ladders appear in the archive, and each matches the runner that produced it: the
twirl campaign CSVs carry 12/30/39/57, `odra_full_100pt.csv` carries 12/27/36/54.

`spec/QEM_luka_badawcza_i_plan_ODRA.md` §4.4 read this as a Qiskit version difference. It
is not. On 2.5.2 the fixed-layout path gives 12/27/36/54 and never produces 39, so it
cannot account for the twirl ladder; on 2.4.1 both ladders fall out of one version, each
from its own code path. **2.4.1 is therefore the version consistent with the archived
campaigns**, which is why the lock pins it. A correction is recorded in the spec file.

`qem/compile.py` is now the only compilation entry point, and it is the fixed-layout one.

Since P7 the ODRA paths of the runners (`run_garnet_twirl`, `run_odra_cdr`,
`zne_shot_boundary`, `random_mirror_benchmark`, `run_hardware`) compile through it, on
hardware and simulator alike; `--legacy-transpile` restores the archived path. Two
consequences for comparing new numbers with old ones:

- single-qubit runs are now fused, so circuits carry fewer PRX and, on the device model,
  lower raw error at the same CZ count (one 57-CZ point: 0.089 against 0.170);
- `random_mirror_benchmark` on ODRA used to let the transpiler choose the layout; with
  the fixed layout its CZ counts change (2 layers: 122 instead of 116).

Garnet and Emerald still go through their own transpilation; `compile_native` is the
five-qubit star only.

## 2. The old path is not deterministic

Compiling one circuit five times through `native_transpile`:

| pattern | distinct CZ skeletons out of 5 |
|---|---|
| star | 1 |
| linear | 5 |
| circular | 5 |
| all_to_all | 5 |

Through the fixed-layout path: 1 for every pattern. `star` is stable either way because
it needs no routing at all.

## 3. CDR training circuits did not share their target's routing

CDR regresses a target's noisy value against training circuits that are supposed to
experience *the same* noise. That holds only if they route their CZs over the same links.
Fraction of 10 training circuits whose CZ skeleton matched the target's, over 4 targets
per pattern:

| pattern | `native_transpile` (archived path) | fixed layout + seed 42 |
|---|---|---|
| star | 10/10, 10/10, 10/10, 10/10 | 10/10 |
| linear | 0/10, 1/10, 2/10, 0/10 | 10/10 |
| circular | 0/10, 0/10, 0/10, 0/10 | 10/10 |
| all_to_all | 0/10, 1/10, 0/10, 2/10 | 10/10 |

On Qiskit 2.5.2 the picture is qualitatively the same (0/10, occasionally 1/10). The
occasional single hits are coincidental agreement of a non-deterministic router, not a
behavioural difference between versions.

**Consequence.** In `odra_full_100pt.csv` and `odra_cdr_100pt.csv` the CDR fits for every
pattern except `star` were trained on circuits with a different routing from their
target. Their `r²` and `err_cdr` columns should be read with that in mind. In
`odra_twirl_o1.csv`, `odra_twirl_o2.csv` and `garnet_twirl_w*.csv` the skeletons do
match, because those runs went through the fixed-layout path.

## 4. One training set shared by every evaluation point

`cdr.near_clifford_training_circuits(target, n_train, seed)` with a fixed seed returns
identical circuits 1..n-1 whatever the target; only circuit 0, the nearest-Clifford
anchor, depends on it. Every archived campaign used it that way, so the fits at
different evaluation points are strongly correlated and the training distribution sits
near no particular target.

Those circuits also snap *every* rotation to a random Clifford angle, making them random
Clifford circuits that share a skeleton rather than near-Clifford images of the target.

`qem/cdr_training.py` replaces both behaviours and seeds per
`(base_seed, target_index, window_id)`. The old behaviour is reachable through
`build_legacy_shared_training` for reproducing archived numbers.

## 5. Windows, and what the job index shows

Job IDs recovered from the campaign logs (`runs/legacy_logs/job_index.csv`), with times
decoded from their UUIDv7 prefix:

| window | jobs | first (UTC) | last (UTC) |
|---|---|---|---|
| `o1` | 92 | 2026-09-13 19:59 | 2026-09-14 00:13 |
| `o2` | 32 | 2026-09-15 09:42 | 2026-09-15 11:44 |
| Month-1 | 25 | 2026-07-30 19:29 | 2026-08-01 06:25 |

**o1 and o2 are genuinely separate** -- a day and a half apart, one overnight and one
daytime -- so treating them as independent calibration windows is justified.

**o2 is a third the size of o1** (32 jobs against 92). Whether it was deliberately
narrower or ended early is unresolved. Any statement about between-window variance that
leans on o2 carries that uncertainty.

**The Month-1 campaign spans three days.** Its DD comparison is therefore not inside one
calibration window, which compounds the ordering problem below.

## 6. Known defects in archived runs

**DD was never interleaved.** DD-off always ran before DD-on, and the `circular` pair was
split across 30 July and 1 August. The DD penalty is real in the data but is confounded
with time and calibration.

**Four evaluation points per ladder point.** Every `err` in the twirl campaigns is a mean
over four points, so its uncertainty is wide and no per-point distribution exists.

**The simulated null used a placeholder.** `night_null_*` was generated with
`DeviceCalibration(p_2q=0.01)`, not a measured calibration, and the positive control
injected coherent error *only*, with no relaxation or readout. The two are not nested,
so differences between them cannot be attributed to coherence alone.
`results_sim/legacy_nested_cal/` supersedes this with models built on ODRA's own
calibration; its own limitations are listed there.

**`zne_shot_boundary.py` could not run on its default scale list.** The line choosing
scales assigned to a local name while reading a module-level name that does not exist,
so any run without an explicit `--scales` raised `UnboundLocalError`. The archived κ
campaigns worked only because `--scales` was always passed. Fixed in P0, with a
regression test.

**ZNE estimates were silently clamped.** `zne_dryrun.extrapolate` replaced every
Richardson (or exponential) estimate with `|E| > 1.25` by the linear fit, without a
record. Every archived ZNE error -- the twirl campaigns, `odra_full_100pt.csv`, the κ
campaigns -- went through it, and since only means were stored, how often it fired is
unrecoverable. It hides overshoots, which is what Koster & Mauerer's checklist asks to
see, and at small budgets it changes the estimator's variance, which is what κ
measures. Since P3 the campaign runners keep the raw estimate and write
`unphysical` / `fallback_used`; `--legacy-clamp` reproduces the old numbers.

**`R > 0.3` was a decision rule.** `zne_signal_retention.py` labelled a rung "safe" from
`R = |<O>(λ_max)| / |<O>(1)|`. When the signal is already on the floor at λ = 1, R is a
ratio of two floors (the 39-CZ ODRA rung: R = 0.81 / 0.67 at `|<O>(1)| = 0.04`). R
stays as a column; normalised retention, SNR(λ_max), W_neg and the garbage-folding
control replace it. The same script also wrote by default over the archived
`zne_signal_retention.csv` in the root; it now writes to `results_sim/`.

**The mapped calibration overstates gate error.** `collect_odra_calibration.py` takes
`p_2q` from the two-qubit *Clifford* RB of each pair (`metrics.rb.clifford.uz_cz`), and
`p_1q` from single-qubit Clifford RB. A two-qubit Clifford is about 1.5 CZ plus
single-qubit gates. The same raw dump also carries the per-gate numbers: interleaved RB
of the CZ (`metrics.irb.cz`) and RB of the PRX (`metrics.rb.prx`). For 2026-08-03:

| | mapped (per Clifford) | per gate |
|---|---|---|
| CZ error | 0.0203 (mean) | 0.0078 / 0.0101 / 0.0105 / 0.0079 (IRB, hub with QB1 / QB2 / QB4 / QB5) |
| PRX error | 0.0018-0.0023 | 0.0010-0.0012 (RB) |

So `p_2q` is about 2.5x the CZ's own error. Every simulation built from the mapped file
inherits that -- `results_sim/legacy_nested_cal/` and the "ODRA rates" variant of
`results_sim/wneg_null/` among them. `sim/device_model.py` (P7) reads the per-gate
values from the raw dump; the mapped file is still accepted, with a warning. The
collector itself is unchanged, so the archived mapped files stay what they were.

**Every runner's default output was an archived CSV.** `garnet_twirl_results.csv`,
`odra_cdr_results.csv`, `zne_shot_boundary_results.csv`, `random_mirror_results.csv` and
`hardware_results.csv` are tracked results, and they were also the default `--out`, so
any run without `--out` -- a simulation included -- replaced them. The runners now refuse
to write a tracked file outside `runs/` and `results_sim/` unless
`--allow-archive-write` is given (`qem.provenance.guard_archive`).

## 7. Excluded runs

**2026-10-12, ODRA native twirl.** Jobs reached the device, then the server answered with
an HTML page instead of JSON and both windows failed. The result CSVs contain only
headers. Nothing from this run is usable. Full account, including the two job IDs that
may still be retrievable: `runs/legacy_failed/2026-10-12/NOTE.md`.

## 8. Out of scope

`banknote_study/` holds the Month-1 Banknote classifier data. It is excluded from this
work, which evaluates decision agreement on the `two_curves` classifier only. Those files
stay untracked and untouched.
