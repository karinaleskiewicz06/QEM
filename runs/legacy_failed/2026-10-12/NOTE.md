# Failed run — ODRA native twirl, 2026-10-12

## What was run

```
./rerun_odra_native.sh
```

which drives, once per window:

```
python run_garnet_twirl.py --submit --device odra --native-twirl --resume \
  --arms cdr --twirl-arms cdr \
  --points optimal:star optimal:linear optimal:circular optimal:all_to_all \
  --eval-points 4 --shots 8192 --n-train 10 --n-twirl 6 \
  --window-id <o1|o2> --out odra_twirl_native_fixed_<o1|o2>.csv
```

The purpose was to repeat the native-twirl arm after the single-qubit merging fix, so its
gate overhead no longer confounds the comparison with the logical arm.

## When

| | local (CEST) | UTC |
|---|---|---|
| window o1 started | 2026-10-12 11:22:41 | 09:22:41 |
| first job submitted | — | 09:22:47 |
| last job submitted | — | 09:29:22 |
| window o1 gave up | 2026-10-12 11:53:45 | 09:53:45 |
| window o2 started and failed | 2026-10-12 11:53:45–47 | 09:53:45–47 |

Times are from the shell log; job times are decoded from the UUIDv7 job IDs.

## What failed

The jobs reached the device — two job IDs are recorded, and the log shows `100/264` circuits
submitted — but fetching results failed. After a `ReadTimeout` and five retries the client
raised:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for JobData
  Invalid JSON: expected value at line 2 column 1
  input_value='\n<!DOCTYPE html>\n<html...>\n\t</body>\n</html>\n'
```

The server answered with an **HTML page instead of JSON**. Window o2 then failed earlier
still, at `get_backend`, with the same symptom on `ListQuantumComputersResponse`.

This is a transport or authentication problem, not an `iqm-client` version incompatibility:
a login page, a VPN captive portal or a gateway error page would all produce exactly this.
It was not diagnosed further.

## What came out

| file | content |
|---|---|
| `odra_twirl_native_fixed_o1.csv` | header row only, no data |
| `odra_twirl_native_fixed_banded.csv` | header row only, no data |
| `odra_native_fixed.log` | full shell log, including both tracebacks and the job IDs |

**No measurement from this run is usable.** The files are kept because they document that the
run happened and why it produced nothing, so the gap in the record is explained rather than
silent.

## Possibly recoverable

Two job IDs are in `../../legacy_logs/job_index.csv`, tagged `odra_native_fixed.log`:

```
09:22:47Z  and  09:29:22Z on 2026-10-12
```

Those jobs may have completed server-side. If they did, their counts can still be fetched by
ID without re-running anything on the device. This has not been attempted.

## Before retrying

Check connectivity and authentication first — a direct request to the server should return
JSON, not HTML. Retrying the script without that check will reproduce the same failure.
