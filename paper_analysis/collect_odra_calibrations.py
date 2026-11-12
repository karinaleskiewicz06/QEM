"""Gather every ODRA calibration snapshot in calibrations/ into one folder (read-only on sources).

Each snapshot is a pair: odra[_raw]_<tag>.json (raw = full API dump with per-gate RB/IRB
observations; mapped = the short file used by the simulators). Outputs, in
calibrations/odra_all/:

  odra_calibrations.csv       one row per snapshot x qubit (T1, T2*, T2 echo, PRX fidelity,
                              readout errors) and per snapshot x edge (CZ fidelity), long format
  odra_calibrations_wide.csv  one row per snapshot, every number as a column
  odra_calibrations.json      everything in one file, keyed by snapshot tag
  README.md                   what is where, duplicates, which run used which snapshot

Original files are never modified.

    python -m paper_analysis.collect_odra_calibrations
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from sim.device_model import load_calibration  # noqa: E402

CAL = REPO / "calibrations"
DEST = CAL / "odra_all"


def tag_of(p: pathlib.Path) -> str:
    s = p.stem.removeprefix("odra_raw").removeprefix("odra").lstrip("_")
    return s or "20260730"


def raw_hash(p: pathlib.Path) -> str:
    """Hash of the calibration numbers only (not the file), to find identical snapshots."""
    r = json.loads(p.read_text())["raw"]
    keep = {k: r[k] for k in ("t1", "t2", "t2_echo", "fidelity_1q", "fidelity_2q_cz", "readout") if k in r}
    return hashlib.sha1(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:10]


def main() -> None:
    DEST.mkdir(exist_ok=True)
    raws = {tag_of(p): p for p in sorted(CAL.glob("odra_raw*.json"))}
    mapped = {tag_of(p): p for p in sorted(CAL.glob("odra*.json")) if not p.name.startswith("odra_raw")}
    long_rows, wide_rows, full = [], [], {}
    for tag in sorted(set(raws) | set(mapped)):
        m = json.loads(mapped[tag].read_text()) if tag in mapped else {}
        meta = m.get("meta", {})
        order = meta.get("qubit_order_logical_to_physical", ["QB3", "QB1", "QB2", "QB4", "QB5"])
        snap = dict(tag=tag, collected_at=meta.get("collected_at"),
                    aborted="aborted" in tag,
                    raw_file=raws[tag].name if tag in raws else None,
                    mapped_file=mapped[tag].name if tag in mapped else None,
                    raw_hash=raw_hash(raws[tag]) if tag in raws else None)
        if tag in raws:
            c = load_calibration(raws[tag])
            for i, q in enumerate(order):
                for name, val in (("t1_us", c.t1[i] * 1e6), ("t2star_us", c.t2[i] * 1e6),
                                  ("t2echo_us", c.t2_echo[i] * 1e6), ("f_prx", c.f_prx[i]),
                                  ("ro_e01", c.e01[i]), ("ro_e10", c.e10[i])):
                    long_rows.append(dict(tag=tag, collected_at=snap["collected_at"], kind="qubit",
                                          logical=i, physical=q, quantity=name, value=float(val)))
                    snap[f"{name}_{q}"] = float(val)
            for (a, b), f in sorted(c.f_cz.items()):
                e = f"{order[a]}-{order[b]}"
                long_rows.append(dict(tag=tag, collected_at=snap["collected_at"], kind="edge",
                                      logical=f"{a}-{b}", physical=e, quantity="f_cz", value=float(f)))
                snap[f"f_cz_{e}"] = float(f)
            snap.update(mean_t1_us=float(np.mean(c.t1) * 1e6), mean_t2star_us=float(np.mean(c.t2) * 1e6),
                        mean_f_cz=float(np.mean(list(c.f_cz.values()))))
        if m:
            snap.update(p_1q_mean=float(np.mean(m["p_1q"])), p_2q=float(m["p_2q"]),
                        p_ro_mean=float(np.mean(m["p_ro"])))
        wide_rows.append(snap)
        full[tag] = dict(summary=snap, mapped=m,
                         raw=json.loads(raws[tag].read_text())["raw"] if tag in raws else None)
    wide = pd.DataFrame(wide_rows).sort_values("collected_at", na_position="last")
    first = wide.groupby("raw_hash").tag.transform("first")
    wide["duplicate_of"] = np.where(first != wide.tag, first, "")
    pd.DataFrame(long_rows).to_csv(DEST / "odra_calibrations.csv", index=False)
    wide.to_csv(DEST / "odra_calibrations_wide.csv", index=False)
    (DEST / "odra_calibrations.json").write_text(json.dumps(full, indent=1, default=str))

    # which campaign night ran under which calibration set
    runs = []
    for f in sorted((REPO / "runs" / "odra_campaign").glob("*/counts.jsonl")):
        ids = set()
        for line in open(f):
            d = json.loads(line)
            if d.get("calibration_set_id"):
                ids.add(d["calibration_set_id"])
        runs.append(f"| {f.parent.name} | {len(ids)} | {', '.join(sorted(i[:8] for i in ids))} |")
    uniq = wide[wide.duplicate_of == ""]
    cols = ["tag", "collected_at", "mean_t1_us", "mean_t2star_us", "mean_f_cz", "duplicate_of"]
    readme = f"""# All ODRA calibrations in one place

Generated by `python -m paper_analysis.collect_odra_calibrations` from `calibrations/odra*.json`
(originals untouched). {len(wide)} snapshots, {len(uniq)} with distinct numbers.

- `odra_calibrations.csv`: long table (snapshot x qubit/edge x quantity).
  Quantities: t1_us, t2star_us (Ramsey), t2echo_us (Hahn echo), f_prx (per-gate RB),
  ro_e01 / ro_e10 (readout 0->1 / 1->0), f_cz (per-gate IRB, per edge).
  `logical` 0 is the hub; physical hub is QB3.
- `odra_calibrations_wide.csv`: one row per snapshot; `duplicate_of` marks snapshots whose
  numbers are identical to an earlier one (the API returned the same calibration set).
- `odra_calibrations.json`: everything (summary, mapped file, full raw dump) keyed by tag.

## Snapshots

{wide[cols].round(3).to_markdown(index=False)}

## Calibration sets seen in campaign runs (`calibration_set_id`, first 8 chars)

| run | sets | ids |
|---|---|---|
""" + "\n".join(runs) + "\n"
    (DEST / "README.md").write_text(readme)
    print(readme)


if __name__ == "__main__":
    main()
