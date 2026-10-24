# p2_kappa_u135 — budget 4096 aborted (2026-10-23)

Budgets 256-2048 complete (rows in kappa.csv). At budget 4096 the 40 raw circuits were
measured, then submitting the ZNE circuits failed: the Mac lost network/DNS
(`Failed to resolve 'odra5.e-science.pl'`), and every later run of that session failed the
same way.

The 40 raw records of S=4096 were moved, unchanged, to counts_S4096_attempt1_aborted.jsonl
so that --resume, which re-measures the whole budget (raw and ZNE close in time), leaves
no duplicates. These records carry no budget/role metadata (added to the runner after this
run); they are identified by shots_requested = 4096.
