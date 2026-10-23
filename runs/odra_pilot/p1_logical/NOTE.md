# p1_logical — first attempt aborted at all_to_all (2026-10-23)

Started 11:26 local on uncommitted P7 code (manifest: git_commit f06fe0c, git_dirty true).

- optimal:star (12 CZ): complete, 544 circuits, rows in twirl_logical.csv.
- optimal:all_to_all (57 CZ): raw and CDR twirl-OFF measured (268 circuits, last at
  10:13:06Z), then fetching the first CDR twirl-ON job failed: ODRA answered the job-status
  request with an HTML page instead of JSON (same symptom as 2026-10-12,
  runs/legacy_failed/2026-10-12/NOTE.md). The job ID was not recorded (job IDs were only
  logged after a successful fetch, and into the wrong recorder; fixed).

The 268 all_to_all records were moved, unchanged, to
counts_all_to_all_attempt1_aborted.jsonl so that the resumed run, which re-measures the
whole all_to_all point (OFF and ON close in time), leaves no duplicates in counts.jsonl.
They are not used in any result.
