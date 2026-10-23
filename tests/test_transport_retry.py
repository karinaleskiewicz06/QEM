"""ODRA transport: an HTML reply while polling is retried, and job IDs are kept early.

Twice (2026-10-12, 2026-10-23) ODRA answered a job-status request with an HTML page;
iqm-client failed inside pydantic and the runner died with the job ID recorded nowhere.
"""

from __future__ import annotations

import types

import pytest

import run_hardware


class ValidationError(Exception):
    """Stands in for pydantic_core.ValidationError, matched by name like the real one."""


HTML = "Invalid JSON: expected value [input_value='\\n<!DOCTYPE html>\\n<html...>']"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(run_hardware.time, "sleep", lambda s: None)


def test_html_reply_is_retried_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValidationError(HTML)
        return "counts"

    assert run_hardware._retry(flaky, "poll") == "counts"
    assert calls["n"] == 3


def test_other_validation_errors_are_not_swallowed():
    def broken():
        raise ValidationError("field required: measurements")

    with pytest.raises(ValidationError):
        run_hardware._retry(broken, "poll")


def test_persistent_html_gives_up_with_context():
    def always():
        raise ValidationError(HTML)

    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        run_hardware._retry(always, "poll", attempts=3)


def test_job_id_reaches_the_callback_before_fetching(monkeypatch):
    import odra_backend
    from qiskit import QuantumCircuit

    seen = []

    def fake_submit(client, batch, shots, dd_on):
        return types.SimpleNamespace(job_id="job-123")

    def fake_fetch(client, job):
        # the ID must already be recorded when fetching starts -- that is the point
        assert seen == ["job-123"]
        raise RuntimeError("server gone")

    monkeypatch.setattr(odra_backend, "submit_batch", fake_submit)
    monkeypatch.setattr(odra_backend, "fetch_counts", fake_fetch)
    monkeypatch.setattr(odra_backend, "qiskit_to_iqm", lambda c: c)
    qc = QuantumCircuit(5)
    qc.cz(0, 1)
    qc.measure_all()
    backend = types.SimpleNamespace(client=None)
    with pytest.raises(RuntimeError, match="server gone"):
        odra_backend.run_circuits(backend, [qc], 100, on_job=seen.append)
    assert seen == ["job-123"]
