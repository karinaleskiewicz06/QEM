# CDR-variant benchmark — simulator, Qiskit 2.5.2

`cdr_variants_sim_raw.csv` is the raw output of the CDR-variant benchmark in
`spec/sim_cdr_variants_bench2.py` and `spec/sim_cdr_variants_bench3_control.py`, run on an
ODRA-calibrated noisy simulator. `spec/cdr_variants_sim_summary.csv` is its aggregate.

**It was computed on Qiskit 2.5.2, not on the version this repository is pinned to (2.4.1).**
That matters for one concrete reason: on 2.5.2 the fixed-layout compilation path gives a
routing ladder of **12 / 27 / 36 / 54** CZ, whereas on 2.4.1 — the version the hardware
campaigns ran on — the same path gives **12 / 30 / 39 / 57**. The ladder points in this file
therefore do not line up with the hardware ladder, and its absolute error values must not be
quoted next to hardware numbers as if they were the same working points.

What the file is still good for is the **ordering of variants at a fixed ladder point**,
which is what it was produced to establish: training-set diversity and twirling are two
independent levers, and they compose.

Consequently the P7 regression test checks a qualitative criterion — `spread` + `near_target`
+ twirl beats `twirl_native` + `shared_random` in at least 6 of 8 repetitions at the highest
ladder point — rather than reproducing the literal values 0.0190 and 0.0357, which belong to
54 CZ on 2.5.2 and have no counterpart at 57 CZ on 2.4.1.
