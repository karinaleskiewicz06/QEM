"""Label each record of a ``run_garnet_twirl`` window with its arm and twirl setting.

Until 2026-10-24 the runner named records ``<point>/s<spec>/c<copy>`` with the spec index
restarting at every executor call, and did not store the arm. Within one point the raw,
CDR-off, CDR-on and ZNE calls therefore reuse the same IDs. The records are complete and
in call order, so the arm is recoverable: calls run in ``args.arms`` order, each arm
twice (off, on) if it is in ``--twirl-arms`` and once (off) otherwise, and every call
starts at spec 0, copy 0.

Writes ``counts_annotated.jsonl`` next to ``counts.jsonl`` with ``arm``, ``call_index`` and
a unique ``record_id``; the raw file is not modified. Raises if the segmentation does not
match the plan in the manifest.

    python -m analysis.annotate_twirl_counts runs/odra_pilot/p3_logical
"""

from __future__ import annotations

import argparse
import json
import pathlib


def plan(cli: dict) -> list[tuple[str, bool]]:
    """``[(arm, twirl), ...]`` in execution order for one point."""
    out = []
    for arm in cli["arms"]:
        out.append((arm, False))
        if arm in (cli.get("twirl_arms") or []):
            out.append((arm, True))
    return out


def annotate(run_dir: pathlib.Path | str) -> pathlib.Path:
    d = pathlib.Path(run_dir)
    cli = json.loads((d / "manifest.json").read_text())["cli_args"]
    calls = plan(cli)
    recs = [json.loads(line) for line in (d / "counts.jsonl").open() if line.strip()]

    by_point: dict[str, list[dict]] = {}
    for r in recs:
        by_point.setdefault(r["circuit_id"].split("/")[0], []).append(r)

    out = []
    for point, rs in by_point.items():
        k = -1
        for i, r in enumerate(rs):
            if r["spec_index"] == 0 and r["copy_index"] == 0:
                k += 1
            if k >= len(calls):
                raise ValueError(f"{point}: more calls than planned {calls}")
            arm, twirl = calls[k]
            if bool(r["twirl"]) != twirl:
                raise ValueError(f"{point} record {i}: twirl={r['twirl']} but call {k} "
                                 f"is {arm} twirl={twirl}")
            out.append({**r, "arm": arm, "call_index": k,
                        "record_id": f"{point}/{arm}/{'on' if twirl else 'off'}/"
                                     f"s{r['spec_index']}/c{r['copy_index']}"})
        if k != len(calls) - 1:
            raise ValueError(f"{point}: {k + 1} calls found, {len(calls)} planned")
    ids = [r["record_id"] for r in out]
    if len(set(ids)) != len(ids):
        raise ValueError("annotation did not make the IDs unique")
    path = d / "counts_annotated.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in out))
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+")
    for d in ap.parse_args().run_dirs:
        print(f"{d}: wrote {annotate(d)}")


if __name__ == "__main__":
    main()
