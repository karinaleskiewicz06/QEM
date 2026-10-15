# Legacy campaign logs

Run logs recovered from the repository root, where `.gitignore`'s `*.log` rule (written for
LaTeX build artifacts) had been hiding them. They are the only provenance we have for the
hardware campaigns that predate the `runs/` layout introduced in P0: they carry the IQM job
IDs, submission order and the arm/ladder point each job belonged to.

Added with `git add -f`. Scanned for credentials before committing — no token, bearer,
password or credential-bearing URL was found. The only keyword hit is a source comment
echoed in a traceback (`# token z IQM_TOKEN`), with no value attached.

## Log to result mapping

| log | campaign | result CSV |
|---|---|---|
| `overnight_odra_o1.log` | ODRA twirl, window o1 | `odra_twirl_o1.csv` |
| `overnight_odra_o2.log` | ODRA twirl, window o2 | `odra_twirl_o2.csv` |
| `overnight_odra.log` | ODRA overnight driver (start of the o1 run) | — (driver log) |
| `overnight_sims.log` | simulator null / coherent controls | `night_{null,coh05,coh10}_*.csv` |
| `nested_null.log` | nested device-calibrated controls (prior session) | `results_sim/legacy_nested_cal/nested_cal*.csv` |
| `hardware_results.jobs.log` | Month-1 ODRA campaign (routing ladder, DD, REM) | `hardware_results.csv` |
| `chain_runner.log` | Month-1 chain driver | — (driver log) |
| `train_patterns.log` | per-pattern training | `trained_models_hard/*` |
| `zne_dryrun.log` | ZNE pilot | `zne_dryrun_results.csv` (gitignored, regenerable) |

`odra_native_fixed.log` is **not** here: it belongs to a failed run and lives in
`runs/legacy_failed/2026-10-12/`.

## job_index.csv

Every IQM job ID found in these logs, with its submission time decoded from the UUIDv7
prefix (first 48 bits are Unix milliseconds, rendered UTC) and the log it came from.
153 jobs from 5 logs; the other logs are simulator or driver output and carry no job IDs.

What the index shows:

| log | jobs | first (UTC) | last (UTC) |
|---|---|---|---|
| `overnight_odra_o1.log` | 92 | 2026-09-13 19:59 | 2026-09-14 00:13 |
| `overnight_odra_o2.log` | 32 | 2026-09-15 09:42 | 2026-09-15 11:44 |
| `hardware_results.jobs.log` | 25 | 2026-07-30 19:29 | 2026-08-01 06:25 |
| `overnight_odra.log` | 2 | 2026-09-13 19:53 | 2026-09-13 19:53 |
| `odra_native_fixed.log` | 2 | 2026-10-12 09:22 | 2026-10-12 09:29 |

Three things follow directly, and they matter for how the existing results may be read:

1. **Windows o1 and o2 are genuinely separate.** They are a day and a half apart — an
   overnight run on 13/14 September and a daytime run on 15 September — so treating them as
   independent calibration windows in the twirling result is justified.
2. **o2 is much smaller than o1** (32 jobs against 92). Either it was deliberately narrower
   or it is incomplete; this has not been resolved and is flagged in `DATA_NOTES.md`.
3. **The Month-1 campaign was split across days**, 30 July to 1 August. This confirms from
   timestamps what the review had inferred: the DD comparison does not sit inside one
   calibration window, which is why its result is treated as uncontrolled for ordering.

The index is not a substitute for the per-circuit record that P0 introduces: it maps jobs to
logs, not to individual circuits, shots or Pauli frames.
