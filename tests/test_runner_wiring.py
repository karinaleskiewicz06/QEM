"""P0: every runner must accept the provenance flags and gate on the environment."""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

RUNNERS = ["run_garnet_twirl.py", "run_odra_cdr.py", "zne_shot_boundary.py",
           "random_mirror_benchmark.py", "run_hardware.py"]
REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("runner", RUNNERS)
def test_runner_parses(runner: str):
    ast.parse((REPO / runner).read_text())


@pytest.mark.parametrize("runner", RUNNERS)
def test_runner_exposes_provenance_flags(runner: str):
    out = subprocess.run([sys.executable, runner, "--help"], cwd=REPO,
                         capture_output=True, text=True, timeout=120).stdout
    for flag in ("--campaign", "--window-id", "--no-provenance", "--allow-env-mismatch"):
        assert flag in out, f"{runner} is missing {flag}"


@pytest.mark.parametrize("runner", RUNNERS)
def test_runner_imports_the_environment_gate(runner: str):
    src = (REPO / runner).read_text()
    assert "require_locked_environment" in src
    assert "RunRecorder" in src


def test_zne_scale_default_resolves():
    """Regression: the default scale list used to raise UnboundLocalError.

    `SCALES = list(args.scales) if args.scales else list(SCALES)` assigned to a local
    while reading a module-level name that does not exist, so every run without an
    explicit --scales crashed. The archived kappa campaigns only worked because
    --scales was always passed. Guard the default path here.
    """
    src = (REPO / "zne_shot_boundary.py").read_text()
    assert "else list(SCALE_FACTORS)" in src
    assert "else list(SCALES)" not in src
