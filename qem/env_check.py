"""Verify the live environment against ``requirements.lock``.

The transpiler is version-sensitive, and the campaign's results are only comparable
with the archived ones when the compilation path produces the same circuits. On
Qiskit 2.4.1 the fixed-layout path gives a 12/30/39/57 CZ ladder, which reproduces
the hardware twirl campaign; on 2.5.2 the same path gives 12/27/36/54. Silently
running on the wrong version would therefore produce data that *looks* comparable
and is not, which is why this check aborts rather than warns.

Usage::

    from qem.env_check import require_locked_environment
    require_locked_environment()                       # raises on mismatch
    require_locked_environment(allow_mismatch=True)    # warns instead

or from the command line::

    python -m qem.env_check          # report, exit 1 on mismatch
    python -m qem.env_check --allow-env-mismatch
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import pathlib
import platform
import re
import sys

LOCK_FILE = pathlib.Path(__file__).resolve().parent.parent / "requirements.lock"

#: Packages whose version changes can alter the compiled circuit. A mismatch here is
#: an error; anything else in the lock is reported but tolerated.
CRITICAL = ("qiskit", "qiskit-aer", "iqm-client")

_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s#]+)")


def read_lock(path: pathlib.Path | str = LOCK_FILE) -> dict[str, str]:
    """Parse ``requirements.lock`` into ``{package: version}``. Comments are ignored."""
    out: dict[str, str] = {}
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _PIN.match(line)
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


def installed_version(name: str) -> str | None:
    """Installed version of ``name``, or None when it is not installed.

    ``python`` is answered from the interpreter rather than from package metadata.
    Distribution and import names differ often enough (``qml_benchmarks`` vs
    ``qml-benchmarks``) that both spellings are tried.
    """
    if name == "python":
        return platform.python_version()
    for candidate in (name, name.replace("_", "-"), name.replace("-", "_")):
        try:
            return md.version(candidate)
        except md.PackageNotFoundError:
            continue
    return None


def check_environment(lock_path: pathlib.Path | str = LOCK_FILE) -> dict:
    """Compare the live environment with the lock.

    Returns a dict with ``ok`` (no critical mismatch), ``rows`` (name, locked, live,
    status, critical) and ``problems`` (the critical mismatches only).
    """
    lock = read_lock(lock_path)
    rows, problems = [], []
    for name, locked in lock.items():
        live = installed_version(name)
        critical = name in CRITICAL
        if live is None:
            status = "MISSING"
        elif live == locked:
            status = "ok"
        else:
            status = "MISMATCH"
        if status != "ok" and critical:
            problems.append((name, locked, live))
        rows.append({"package": name, "locked": locked, "installed": live,
                     "status": status, "critical": critical})
    return {"ok": not problems, "rows": rows, "problems": problems}


def format_report(result: dict) -> str:
    lines = [f"{'package':24s} {'locked':12s} {'installed':12s} status"]
    lines.append("-" * 62)
    for r in result["rows"]:
        mark = "!" if (r["status"] != "ok" and r["critical"]) else " "
        lines.append(f"{mark}{r['package']:23s} {r['locked']:12s} "
                     f"{str(r['installed']):12s} {r['status']}")
    return "\n".join(lines)


def require_locked_environment(*, allow_mismatch: bool = False,
                               lock_path: pathlib.Path | str = LOCK_FILE,
                               quiet: bool = True) -> dict:
    """Abort unless the critical packages match the lock.

    Args:
        allow_mismatch: downgrade the abort to a warning on stderr.
        quiet: print the full table only when something is wrong.

    Raises:
        RuntimeError: a critical package is missing or at the wrong version and
            ``allow_mismatch`` is False.
    """
    result = check_environment(lock_path)
    if not result["ok"]:
        detail = "; ".join(f"{n}: locked {lk}, installed {lv}"
                           for n, lk, lv in result["problems"])
        msg = ("environment does not match requirements.lock -- " + detail +
               ". Compiled circuits may differ from the archived campaigns "
               "(see DATA_NOTES.md). Pass --allow-env-mismatch to proceed anyway.")
        if allow_mismatch:
            print("WARNING: " + msg, file=sys.stderr)
        else:
            print(format_report(result), file=sys.stderr)
            raise RuntimeError(msg)
    elif not quiet:
        print(format_report(result))
    return result


def add_env_argument(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add the shared ``--allow-env-mismatch`` flag to a runner's parser."""
    parser.add_argument("--allow-env-mismatch", action="store_true",
                        help="run even when package versions differ from "
                             "requirements.lock (results may not be comparable "
                             "with the archived campaigns)")
    return parser


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    add_env_argument(ap)
    args = ap.parse_args()
    result = check_environment()
    print(format_report(result))
    if not result["ok"] and not args.allow_env_mismatch:
        print("\nFAIL: critical version mismatch.", file=sys.stderr)
        return 1
    print("\nOK" if result["ok"] else "\nOK (mismatch allowed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
