"""Run provenance: a manifest per window and one raw record per circuit.

The archived campaigns stored only averaged expectation values in CSV. That is enough
to plot a result and not enough to re-derive one: there are no confidence intervals,
no way to re-bin by Pauli frame, and no record of which circuit a job actually ran.
Recovering the 2026-09 windows meant decoding job IDs out of a shell log that the
``*.log`` ignore rule had been hiding (see ``runs/legacy_logs/``).

This module fixes that going forward. Every window writes::

    runs/<campaign>/<window_id>/manifest.json   environment, arguments, job IDs, times
    runs/<campaign>/<window_id>/counts.jsonl    one JSON object per executed circuit

The CSV a runner produces stays, but becomes a *derived view*:
``analysis/rebuild_from_counts.py`` reconstructs it from ``counts.jsonl`` alone, and a
test asserts the two agree exactly.

Typical use from a runner::

    rec = RunRecorder.open("odra_twirl", window_id=args.window_id, args=vars(args),
                           seed=args.seed)
    rec.set_calibration_set_id("start", cal_id)
    ...
    rec.add_job(job_id)
    rec.record_circuit(circuit_id="p0/train03/twirl", native=native_qc, counts=counts,
                       arm="cdr", twirl=True, frame="XZ.IY", point_index=0,
                       train_index=3)
    ...
    rec.set_calibration_set_id("end", cal_id_after)
    rec.close()
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
import platform
import subprocess
import sys
from typing import Any, Iterable

from qem.env_check import installed_version, read_lock

RUNS_ROOT = pathlib.Path("runs")

#: Recorded for every window so a result can be tied to the code that produced it.
TRACKED_PACKAGES = ("qiskit", "qiskit-aer", "qiskit-machine-learning", "iqm-client",
                    "numpy", "scipy")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_state() -> dict[str, Any]:
    """Current commit and whether the working tree is dirty.

    A dirty tree is recorded rather than refused: a campaign often runs with an
    uncommitted tweak, and knowing that is more useful than pretending otherwise.
    """
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    return {
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": bool(status) if status is not None else None,
        "git_dirty_files": len(status.splitlines()) if status else 0,
    }


def package_versions(names: Iterable[str] = TRACKED_PACKAGES) -> dict[str, str | None]:
    return {n: installed_version(n) for n in names}


def estimate_duration_s(n_1q: int, n_2q: int, *, t_1q: float, t_2q: float) -> float:
    """Crude serial duration estimate: gate counts times their durations.

    This ignores parallelism and idle padding, so it over-estimates wall time on the
    device. It is recorded because the depth-vs-routing question (P5) needs *a*
    duration covariate alongside CZ and PRX counts, and a consistent over-estimate is
    usable for regression where an absent column is not.
    """
    return n_1q * float(t_1q) + n_2q * float(t_2q)


def circuit_stats(native) -> dict[str, Any]:
    """Gate counts, depth and CZ skeleton of an already-native circuit.

    The skeleton -- the ordered list of qubit pairs the CZs act on -- is what makes
    CDR's training circuits comparable with the target. Recording it per circuit makes
    a mismatch visible in the data instead of only in a test.
    """
    ops = native.count_ops()
    skeleton = [sorted(native.find_bit(q).index for q in inst.qubits)
                for inst in native.data if inst.operation.name == "cz"]
    return {
        "n_cz": int(ops.get("cz", 0)),
        "n_prx": int(ops.get("r", 0)),
        "depth": int(native.depth()),
        "cz_skeleton": skeleton,
    }


def qasm3_of(native) -> str | None:
    """QASM3 dump of the native circuit, or None if it cannot be serialised."""
    try:
        from qiskit import qasm3
        return qasm3.dumps(native)
    except Exception:
        return None


def save_counts(path: pathlib.Path | str, circuit_id: str, counts: dict,
                meta: dict | None = None) -> None:
    """Append one circuit's raw counts to ``counts.jsonl``.

    One JSON object per line, so a window can be streamed while it runs and a crashed
    window still leaves everything measured up to that point.

    Args:
        path: the ``counts.jsonl`` file (parent directories are created).
        circuit_id: unique within the window; by convention
            ``"<point>/<role><index>/<arm>"``, e.g. ``"p2/train07/twirl"``.
        counts: bitstring -> shot count, in the runner's own convention.
        meta: everything needed to re-derive a result -- at minimum ``arm``, and
            where applicable ``twirl``, ``frame``, ``point_index``, ``train_index``,
            ``scale``, ``n_cz``, ``n_prx``, ``duration_s`` and ``qasm3``.
    """
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {"circuit_id": circuit_id, "recorded_utc": _utc_now(),
              "shots": int(sum(counts.values())), "counts": dict(counts)}
    if meta:
        record.update(meta)
    with p.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=False) + "\n")


@dataclasses.dataclass
class RunManifest:
    """Everything needed to say what a window was, written as ``manifest.json``.

    ``calibration_set_id`` is read before and after the window. When the device
    recalibrates mid-window the two differ, and the window is marked ``split`` --
    its points are no longer a single calibration condition and must not be pooled
    as one.
    """

    campaign: str
    window_id: str
    seed: int | None = None
    cli_args: dict[str, Any] = dataclasses.field(default_factory=dict)
    started_utc: str = dataclasses.field(default_factory=_utc_now)
    finished_utc: str | None = None
    calibration_set_id: dict[str, str | None] = dataclasses.field(
        default_factory=lambda: {"start": None, "end": None})
    job_ids: list[str] = dataclasses.field(default_factory=list)
    device: str | None = None
    submitted: bool = False
    notes: list[str] = dataclasses.field(default_factory=list)
    environment: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.environment:
            self.environment = {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "argv": list(sys.argv),
                "packages": package_versions(),
                "locked": read_lock(),
                **git_state(),
            }

    @property
    def is_split(self) -> bool:
        """True when the calibration set changed during the window."""
        a, b = self.calibration_set_id["start"], self.calibration_set_id["end"]
        return bool(a and b and a != b)

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["split_window"] = self.is_split
        return d

    def save(self, path: pathlib.Path | str) -> pathlib.Path:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n")
        return p


class RunRecorder:
    """Writes the manifest and the per-circuit records for one window."""

    def __init__(self, directory: pathlib.Path, manifest: RunManifest) -> None:
        self.dir = pathlib.Path(directory)
        self.manifest = manifest
        self.dir.mkdir(parents=True, exist_ok=True)
        self.counts_path = self.dir / "counts.jsonl"
        self.manifest_path = self.dir / "manifest.json"
        self.manifest.save(self.manifest_path)

    @classmethod
    def open(cls, campaign: str, *, window_id: str, args: dict | None = None,
             seed: int | None = None, device: str | None = None,
             submitted: bool = False, root: pathlib.Path | str = RUNS_ROOT) -> "RunRecorder":
        manifest = RunManifest(campaign=campaign, window_id=window_id, seed=seed,
                               cli_args=dict(args or {}), device=device,
                               submitted=submitted)
        return cls(pathlib.Path(root) / campaign / window_id, manifest)

    # -- during the window ------------------------------------------------- #

    def add_job(self, job_id: str) -> None:
        if job_id and job_id not in self.manifest.job_ids:
            self.manifest.job_ids.append(str(job_id))
            self.manifest.save(self.manifest_path)

    def set_calibration_set_id(self, when: str, value: str | None) -> None:
        if when not in ("start", "end"):
            raise ValueError("when must be 'start' or 'end'")
        self.manifest.calibration_set_id[when] = value
        self.manifest.save(self.manifest_path)

    def note(self, text: str) -> None:
        self.manifest.notes.append(text)
        self.manifest.save(self.manifest_path)

    def record_circuit(self, circuit_id: str, counts: dict, *, native=None,
                       with_qasm: bool = True, t_1q: float | None = None,
                       t_2q: float | None = None, **meta: Any) -> None:
        """Record one executed circuit.

        ``native`` is the compiled circuit that actually ran; its gate counts, depth,
        CZ skeleton and (optionally) QASM3 are stored with the counts so the record
        stands on its own. Extra keyword arguments -- ``arm``, ``twirl``, ``frame``,
        ``point_index``, ``train_index``, ``scale`` -- are written verbatim.
        """
        if native is not None:
            stats = circuit_stats(native)
            meta.update(stats)
            if t_1q is not None and t_2q is not None:
                meta["duration_s"] = estimate_duration_s(
                    stats["n_prx"], stats["n_cz"], t_1q=t_1q, t_2q=t_2q)
            if with_qasm:
                meta["qasm3"] = qasm3_of(native)
        save_counts(self.counts_path, circuit_id, counts, meta)

    # -- end ----------------------------------------------------------------- #

    def close(self) -> pathlib.Path:
        self.manifest.finished_utc = _utc_now()
        return self.manifest.save(self.manifest_path)

    def __enter__(self) -> "RunRecorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
