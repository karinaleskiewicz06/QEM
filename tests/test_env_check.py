"""P0: the environment gate."""

from __future__ import annotations

import pathlib

import pytest

from qem import env_check


def test_lock_file_exists_and_pins_the_critical_packages():
    lock = env_check.read_lock()
    for name in env_check.CRITICAL:
        assert name in lock, f"{name} must be pinned in requirements.lock"
    assert "python" in lock


def test_lock_parsing_ignores_comments_and_blanks(tmp_path: pathlib.Path):
    f = tmp_path / "x.lock"
    f.write_text("# a comment\n\nqiskit==9.9.9\n# qiskit-iqm  (not installed)\n"
                 "numpy==1.2.3  # trailing comment\n")
    assert env_check.read_lock(f) == {"qiskit": "9.9.9", "numpy": "1.2.3"}


def test_live_environment_matches_the_lock():
    """The lock was generated from this machine, so it must agree with it.

    If this fails, either the environment drifted or the lock was edited by hand --
    both of which invalidate comparisons with the archived campaigns.
    """
    result = env_check.check_environment()
    assert result["ok"], f"critical mismatch: {result['problems']}"


def test_mismatch_raises_and_can_be_overridden(tmp_path: pathlib.Path):
    f = tmp_path / "bad.lock"
    f.write_text("qiskit==0.0.1\n")
    with pytest.raises(RuntimeError, match="does not match requirements.lock"):
        env_check.require_locked_environment(lock_path=f)
    # the override downgrades it to a warning rather than silently passing
    res = env_check.require_locked_environment(lock_path=f, allow_mismatch=True)
    assert not res["ok"]


def test_missing_package_is_a_critical_failure(tmp_path: pathlib.Path):
    f = tmp_path / "missing.lock"
    f.write_text("iqm-client==35.0.0\nthis-package-does-not-exist==1.0\n")
    res = env_check.check_environment(f)
    rows = {r["package"]: r for r in res["rows"]}
    assert rows["this-package-does-not-exist"]["status"] == "MISSING"
    # non-critical, so it must not block the run on its own
    assert res["ok"]
