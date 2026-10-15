"""Rebuild expectation values from ``counts.jsonl`` alone.

The result CSVs are a *derived view*. This script re-derives them from the archived raw
counts, which is what makes the archive worth keeping: if a CSV cannot be reconstructed
from ``counts.jsonl``, the record is incomplete and the campaign is not reproducible.

The invariant it checks is narrow and exact: for every recorded circuit, recomputing
<O> from the raw counts must reproduce the value the runner computed at the time, bit
for bit. Floating-point reductions are order-sensitive, so this is a real constraint --
it fails if the readout convention, the observable coefficients or the bit ordering
ever drift apart between runner and analysis.

Usage::

    python -m analysis.rebuild_from_counts runs/odra_twirl/o1
    python -m analysis.rebuild_from_counts runs/odra_twirl/o1 --out rebuilt.csv --strict
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
from typing import Any, Iterator

import numpy as np


def iter_records(counts_path: pathlib.Path | str) -> Iterator[dict[str, Any]]:
    """Yield one dict per line of ``counts.jsonl``."""
    with pathlib.Path(counts_path).open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def perqubit_z(counts: dict[str, int], n: int) -> np.ndarray:
    """Per-qubit <Z> from a counts dict, in logical (clbit) order.

    Mirrors ``noisy_sim.perqubit_z_from_counts``: bitstrings are little-endian, so
    qubit ``q`` is character ``-1 - q`` of the whitespace-stripped key.
    """
    total = sum(counts.values())
    z = np.zeros(n, dtype=float)
    for bits, c in counts.items():
        s = str(bits).replace(" ", "")
        for q in range(n):
            z[q] += (1 - 2 * int(s[len(s) - 1 - q])) * c
    return z / total


def expval_from_record(rec: dict[str, Any]) -> float | None:
    """Recompute <O> for one record, or None when it carries no coefficients."""
    coeffs = rec.get("coeffs")
    if not coeffs:
        return None
    return float(np.dot(coeffs, perqubit_z(rec["counts"], len(coeffs))))


def rebuild(run_dir: pathlib.Path | str) -> dict[str, Any]:
    """Recompute every record in a window and group the results.

    Returns ``{"records": [...], "groups": [...], "mismatches": [...]}`` where a group
    is one (circuit group, spec) pair averaged over its copies -- the same reduction
    the runner performs to turn M twirl frames or M shot-matched copies into one value.
    """
    run_dir = pathlib.Path(run_dir)
    counts_path = run_dir / "counts.jsonl"
    if not counts_path.exists():
        raise FileNotFoundError(f"no counts.jsonl in {run_dir}")

    records, mismatches = [], []
    for rec in iter_records(counts_path):
        recomputed = expval_from_record(rec)
        stored = rec.get("expval")
        if recomputed is not None and stored is not None and recomputed != stored:
            mismatches.append({"circuit_id": rec["circuit_id"],
                               "stored": stored, "recomputed": recomputed,
                               "delta": recomputed - stored})
        records.append({
            "circuit_id": rec["circuit_id"],
            "group": rec["circuit_id"].rsplit("/", 2)[0],
            "spec_index": rec.get("spec_index"),
            "copy_index": rec.get("copy_index"),
            "twirl": rec.get("twirl"),
            "twirl_kind": rec.get("twirl_kind"),
            "fold": rec.get("fold"),
            "shots": rec["shots"],
            "n_cz": rec.get("n_cz"),
            "n_prx": rec.get("n_prx"),
            "depth": rec.get("depth"),
            "duration_s": rec.get("duration_s"),
            "expval_stored": stored,
            "expval_rebuilt": recomputed,
        })

    groups: dict[tuple, dict[str, Any]] = {}
    for r in records:
        key = (r["group"], r["spec_index"])
        g = groups.setdefault(key, {"group": r["group"], "spec_index": r["spec_index"],
                                    "twirl": r["twirl"], "twirl_kind": r["twirl_kind"],
                                    "fold": r["fold"], "n_cz": r["n_cz"],
                                    "n_prx": r["n_prx"], "_vals": [], "shots_total": 0})
        if r["expval_rebuilt"] is not None:
            g["_vals"].append(r["expval_rebuilt"])
        g["shots_total"] += r["shots"]
    out_groups = []
    for g in groups.values():
        vals = g.pop("_vals")
        g["n_copies"] = len(vals)
        g["expval_mean"] = float(np.mean(vals)) if vals else None
        g["expval_sd"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
        out_groups.append(g)
    out_groups.sort(key=lambda g: (g["group"], g["spec_index"] if g["spec_index"] is not None else -1))

    return {"records": records, "groups": out_groups, "mismatches": mismatches}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", help="runs/<campaign>/<window_id>/")
    ap.add_argument("--out", default=None, help="write the group table to this CSV")
    ap.add_argument("--records-out", default=None, help="write the per-circuit table here")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any record fails to reproduce exactly")
    args = ap.parse_args()

    res = rebuild(args.run_dir)
    n_rec, n_grp = len(res["records"]), len(res["groups"])
    checked = sum(1 for r in res["records"] if r["expval_rebuilt"] is not None
                  and r["expval_stored"] is not None)
    print(f"records: {n_rec}   groups: {n_grp}   exactly reproduced: "
          f"{checked - len(res['mismatches'])}/{checked}")

    if res["mismatches"]:
        print(f"\n{len(res['mismatches'])} record(s) did not reproduce:")
        for m in res["mismatches"][:10]:
            print(f"  {m['circuit_id']}: stored {m['stored']!r} "
                  f"rebuilt {m['recomputed']!r} delta {m['delta']:.3e}")

    for path, rows in ((args.out, res["groups"]), (args.records_out, res["records"])):
        if path and rows:
            p = pathlib.Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
            print(f"wrote {p}")

    return 1 if (args.strict and res["mismatches"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
