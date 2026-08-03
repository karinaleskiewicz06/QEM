"""Collect live ODRA / IQM Spark-class calibration and map it into DeviceCalibration.

Usage
-----
1. Set credentials (one of):
     export IQM_SERVER_URL="https://<your-iqm-server>"
     # and authenticate per your site (token / SSO / cocos)
   Or for Resonance / Resonance-like portals, follow your local IQM access notes.

2. Run:
     python collect_odra_calibration.py
     python collect_odra_calibration.py --url "$IQM_SERVER_URL" --out calibrations/odra.json

3. Load in the noise model:
     from noisy_sim import load_iqm_calibration, make_noisy_simulator
     cal = load_iqm_calibration("calibrations/odra.json")
     sim = make_noisy_simulator(cal)

What gets pulled
----------------
Via ``iqm-client`` / ``qiskit-iqm`` (whichever is installed):

* T1, T2 per qubit
* 1q / 2q gate fidelities or error rates (mapped to p_1q, p_2q)
* readout fidelity / assignment error (mapped to p_ro)
* gate durations if available (t_1q, t_2q)

The raw IQM observation set is also saved next to the mapped JSON so the
mapping can be audited / adjusted when the schema drifts.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Any

import numpy as np


def _try_fetch_via_iqm_client(
    url: str, quantum_computer: str | None, token: str | None = None
) -> dict[str, Any]:
    """Fetch default calibration + quality metrics via iqm-client.

    Auth: pass a static API token (Resonance / ODRA API token) via ``token`` or
    the ``IQM_TOKEN`` env var. iqm-client also honours ``IQM_TOKENS_FILE`` (from
    ``cortex login``); if neither is set it tries unauthenticated (open servers).
    """
    from iqm.iqm_client import IQMClient  # type: ignore

    kwargs: dict[str, Any] = {"iqm_server_url": url}
    if quantum_computer:
        kwargs["quantum_computer"] = quantum_computer
    # iqm-client forbids mixing init kwargs with env vars (IQM_TOKEN / IQM_TOKENS_FILE).
    # Prefer the environment when present; only pass token= when env is unset.
    if token and not os.environ.get("IQM_TOKEN") and not os.environ.get("IQM_TOKENS_FILE"):
        kwargs["token"] = token
    client = IQMClient(**kwargs)

    # Preferred: combined calibration + quality metrics (experimental API).
    try:
        finder = client.get_calibration_quality_metrics()
        raw = _finder_to_flat_metrics(finder)
        source = "get_calibration_quality_metrics"
    except Exception:
        cal = client.get_calibration_set()
        qm = client.get_quality_metric_set()
        raw = {
            "calibration_set": _observations_to_dict(cal),
            "quality_metric_set": _observations_to_dict(qm),
        }
        source = "get_calibration_set+get_quality_metric_set"

    return {"source": source, "url": url, "raw": raw}


def _finder_to_flat_metrics(finder: Any) -> dict[str, Any]:
    """Pull the fields we need via ObservationFinder helpers + a dut_field index.

    ObservationFinder is a ``dict`` subclass; do NOT dump via ``vars()``/``__dict__``
    (that yields ``{}``). Use its typed helpers, then also flatten every
    ObservationBase leaf so the mapper can regex/key-lookup either shape.
    """
    qubits = [f"QB{i}" for i in range(1, 6)]
    out: dict[str, Any] = {"qubits": qubits}

    # Coherence
    try:
        t1, t2 = finder.get_coherence_times(qubits)
        out["t1"] = {k: float(v) for k, v in t1.items()}
        out["t2"] = {k: float(v) for k, v in t2.items()}
    except Exception as e:
        out["t1"], out["t2"], out["coherence_error"] = {}, {}, repr(e)
    # Hahn-echo T2 (DD ceiling); read directly from the characterization model.
    t2e: dict[str, float] = {}
    for qb in qubits:
        try:
            t2e[qb] = float(
                finder._get_path_value(  # noqa: SLF001
                    ["characterization", "model", qb, "t2_echo_time"]
                )
            )
        except Exception:
            pass
    out["t2_echo"] = t2e

    # 1q RB fidelities (metrics.rb.clifford.xy)
    p1: dict[str, float] = {}
    for qb in qubits:
        try:
            f = finder.get_gate_fidelity("clifford", "xy", (qb,))
            # helper uses metrics.<method>.<gate> — try both clifford/xy and prx paths
            if f is None:
                f = finder.get_gate_fidelity("prx", "drag_crf", (qb,))
            if f is not None:
                p1[qb] = float(f)
        except Exception:
            pass
    # Prefer direct path read for RB clifford.xy (matches odra schema we saw)
    for qb in qubits:
        try:
            f = finder._get_path_value(  # noqa: SLF001
                ["metrics", "rb", "clifford", "xy", qb, "fidelity"]
            )
            p1[qb] = float(f)
        except Exception:
            pass
    out["fidelity_1q"] = p1

    # 2q CZ RB fidelities on star edges (hub = QB3)
    edges = [("QB1", "QB3"), ("QB2", "QB3"), ("QB3", "QB4"), ("QB3", "QB5")]
    p2: dict[str, float] = {}
    for a, b in edges:
        key = f"{a}__{b}"
        for locus in [(a, b), (b, a)]:
            try:
                f = finder._get_path_value(  # noqa: SLF001
                    ["metrics", "rb", "clifford", "uz_cz",
                     f"{locus[0]}__{locus[1]}", "fidelity"]
                )
                p2[key] = float(f)
                break
            except Exception:
                continue
    out["fidelity_2q_cz"] = p2

    # Readout SSRO
    ro: dict[str, dict[str, float]] = {}
    for qb in qubits:
        try:
            err = finder.get_measure_errors("measure", "constant", (qb,))
            if err is not None:
                ro[qb] = {"error_0_to_1": float(err[0]), "error_1_to_0": float(err[1])}
        except Exception:
            pass
    out["readout"] = ro

    # Gate durations
    d1, d2 = [], []
    for qb in qubits:
        try:
            d = finder.get_gate_duration("prx", "drag_crf", (qb,))
            if d is not None:
                d1.append(float(d))
        except Exception:
            pass
    for a, b in edges:
        for locus in [(a, b), (b, a)]:
            try:
                d = finder.get_gate_duration("cz", "crf_acstarkcrf", locus)
                if d is not None:
                    d2.append(float(d))
                    break
            except Exception:
                continue
    out["t_1q"] = float(np.mean(d1)) if d1 else None
    out["t_2q"] = float(np.mean(d2)) if d2 else None

    # Full dut_field index (for audit / mapper fallback)
    out["observations"] = _flatten_finder_observations(finder)
    return out


def _flatten_finder_observations(finder: Any) -> dict[str, dict[str, Any]]:
    """Walk ObservationFinder tree -> {dut_field: {value, unit}}."""
    obs: dict[str, dict[str, Any]] = {}

    def walk(node: Any) -> None:
        if hasattr(node, "dut_field") and hasattr(node, "value"):
            try:
                val = node.value
                obs[str(node.dut_field)] = {
                    "value": float(val) if isinstance(val, (int, float)) else str(val),
                    "unit": getattr(node, "unit", None),
                }
            except Exception:
                pass
            return
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(finder)
    return obs


def _observations_to_dict(obj: Any) -> Any:
    """Best-effort JSON-serialisable dump of an IQM observation container."""
    if obj is None:
        return None
    # IQM ObservationBase / ObservationLite leaf
    if hasattr(obj, "dut_field") and hasattr(obj, "value"):
        val = getattr(obj, "value")
        return {
            "dut_field": getattr(obj, "dut_field"),
            "value": (float(val) if isinstance(val, (int, float)) else str(val)),
            "unit": getattr(obj, "unit", None),
        }
    # Dict BEFORE __dict__: ObservationFinder is a dict subclass whose vars() is empty
    if isinstance(obj, dict):
        return {k: _observations_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_observations_to_dict(x) for x in obj]
    if hasattr(obj, "model_dump"):
        try:
            return _observations_to_dict(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return _observations_to_dict(obj.dict())
        except Exception:
            pass
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _observation_finder_to_dict(finder: Any) -> Any:
    """Legacy wrapper; prefer ``_finder_to_flat_metrics`` for new dumps."""
    if isinstance(finder, dict):
        flat = _flatten_finder_observations(finder)
        if flat:
            return {"observations": flat}
    return _observations_to_dict(finder) or str(finder)


def _try_fetch_via_qiskit_iqm(url: str, token: str | None = None) -> dict[str, Any]:
    """Alternative path: IQMProvider backend target metrics."""
    from iqm.qiskit_iqm import IQMProvider  # type: ignore

    # Same rule as IQMClient: do not mix token= with IQM_TOKEN env.
    if token and not os.environ.get("IQM_TOKEN") and not os.environ.get("IQM_TOKENS_FILE"):
        provider = IQMProvider(url, token=token)
    else:
        provider = IQMProvider(url)
    # use_metrics=True pulls calibration into the target when available
    try:
        backend = provider.get_backend(use_metrics=True)
    except TypeError:
        backend = provider.get_backend()
    target = getattr(backend, "target", None)
    props = {
        "backend_name": getattr(backend, "name", None),
        "num_qubits": getattr(backend, "num_qubits", None),
        "coupling_map": (
            [list(e) for e in backend.coupling_map.get_edges()]
            if getattr(backend, "coupling_map", None) is not None
            else None
        ),
        "target": str(target),
    }
    # Best-effort: some versions expose quality metrics on the backend.
    for attr in ("quality_metrics", "calibration_set", "qubit_properties"):
        if hasattr(backend, attr):
            props[attr] = _observations_to_dict(getattr(backend, attr))
    return {"source": "qiskit_iqm.IQMProvider", "url": url, "raw": props}


def _flatten_observations(raw_bundle: dict[str, Any]) -> dict[str, tuple[float, str | None]]:
    """dut_field -> (value, unit) from any dump shape we have produced.

    Supports:
      * new flat dump: raw.observations = {dut_field: {value, unit}}
      * nested ObservationBase dicts
      * legacy str(ObservationLite(...)) dumps
    """
    import re

    obs: dict[str, tuple[float, str | None]] = {}

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            # flat observations index
            if (
                "value" in obj
                and len(obj) <= 4
                and all(k in ("value", "unit", "dut_field") for k in obj)
            ):
                # only useful if we know the field name (parent key or dut_field)
                return
            if "dut_field" in obj and "value" in obj:
                try:
                    obs[str(obj["dut_field"])] = (float(obj["value"]), obj.get("unit"))
                except (TypeError, ValueError):
                    pass
                return
            # observations: {field: {value, unit}}
            for k, v in obj.items():
                if (
                    isinstance(v, dict)
                    and "value" in v
                    and "dut_field" not in v
                    and isinstance(v.get("value"), (int, float))
                ):
                    try:
                        obs[str(k)] = (float(v["value"]), v.get("unit"))
                    except (TypeError, ValueError):
                        pass
                else:
                    walk(v)
        elif isinstance(obj, (list, tuple)):
            for x in obj:
                walk(x)
        elif isinstance(obj, str) and "dut_field=" in obj:
            for m in re.finditer(
                r"dut_field='([^']*)',\s*value=([^,]+),\s*unit='([^']*)'", obj
            ):
                try:
                    obs[m.group(1)] = (float(m.group(2).strip()), m.group(3) or None)
                except ValueError:
                    pass

    walk(raw_bundle)
    return obs


def map_to_device_calibration(raw_bundle: dict[str, Any], num_qubits: int = 5) -> dict:
    """Map an ODRA / IQM Spark calibration dump into DeviceCalibration JSON.

    Physical hub is QB3. We reorder qubits so logical index 0 = QB3 (hub),
    matching the locked star ansatz (hub=0) and ``star_coupling_map(hub=0)``:

        logical:  0     1     2     3     4
        physical: QB3   QB1   QB2   QB4   QB5

    T2 is clamped to <= 2*T1 so Aer ``thermal_relaxation_error`` accepts it.
    """
    from noisy_sim import DeviceCalibration

    phys = ["QB3", "QB1", "QB2", "QB4", "QB5"][:num_qubits]
    placeholder = DeviceCalibration(num_qubits=num_qubits)
    mapped = {
        "num_qubits": num_qubits,
        "hub": 0,
        "t1": placeholder.t1.tolist(),
        "t2": placeholder.t2.tolist(),
        "t2_echo": placeholder.t2.tolist(),
        "t_1q": placeholder.t_1q,
        "t_2q": placeholder.t_2q,
        "p_1q": placeholder.p_1q.tolist(),
        "p_2q": placeholder.p_2q,
        "p_ro": placeholder.p_ro.tolist(),
    }
    unmapped: list[str] = []

    # Prefer the new flat helper dump if present
    raw = raw_bundle.get("raw", raw_bundle)
    flat_t1 = raw.get("t1") if isinstance(raw, dict) else None
    flat_t2 = raw.get("t2") if isinstance(raw, dict) else None
    flat_t2e = raw.get("t2_echo") if isinstance(raw, dict) else None
    flat_f1 = raw.get("fidelity_1q") if isinstance(raw, dict) else None
    flat_f2 = raw.get("fidelity_2q_cz") if isinstance(raw, dict) else None
    flat_ro = raw.get("readout") if isinstance(raw, dict) else None

    obs = _flatten_observations(raw_bundle)

    def get(field: str) -> float | None:
        hit = obs.get(field)
        return None if hit is None else float(hit[0])

    # --- T1 / T2 (Ramsey T2*) ---
    t1, t2 = [], []
    for qb in phys:
        v1 = (flat_t1 or {}).get(qb) if flat_t1 else None
        v2 = (flat_t2 or {}).get(qb) if flat_t2 else None
        if v1 is None:
            v1 = get(f"characterization.model.{qb}.t1_time")
        if v2 is None:
            v2 = get(f"characterization.model.{qb}.t2_time")
        if v1 is None or v2 is None:
            t1, t2 = [], []
            break
        t1.append(float(v1))
        t2.append(min(float(v2), 2.0 * float(v1) - 1e-12))
    if t1:
        mapped["t1"], mapped["t2"] = t1, t2
    else:
        unmapped.extend(["t1", "t2"])

    # --- Hahn-echo T2 (DD ceiling); clamped to [T2*, 2*T1] ---
    if t1:
        t2e = []
        ok = True
        for i, qb in enumerate(phys):
            ve = (flat_t2e or {}).get(qb) if flat_t2e else None
            if ve is None:
                ve = get(f"characterization.model.{qb}.t2_echo_time")
            if ve is None:
                ok = False
                break
            t2e.append(min(max(float(ve), t2[i]), 2.0 * t1[i] - 1e-12))
        t2_echo_defaulted = not ok
        mapped["t2_echo"] = t2e if ok else t2  # no echo -> DD gives no gain

    # --- 1q error ---
    p1 = []
    for qb in phys:
        f = (flat_f1 or {}).get(qb) if flat_f1 else None
        if f is None:
            f = get(f"metrics.rb.clifford.xy.{qb}.fidelity:par=d2")
        if f is None:
            f = get(f"metrics.rb.clifford.xy.{qb}.fidelity")
        if f is None:
            p1 = []
            break
        p1.append(max(0.0, 1.0 - float(f)))
    if p1:
        mapped["p_1q"] = p1
    else:
        unmapped.append("p_1q")

    # --- 2q error ---
    p2s = []
    if flat_f2:
        p2s = [max(0.0, 1.0 - float(f)) for f in flat_f2.values()]
    if not p2s:
        for field, (val, _) in obs.items():
            if "uz_cz" in field and "fidelity" in field:
                p2s.append(max(0.0, 1.0 - float(val)))
    if p2s:
        mapped["p_2q"] = float(np.mean(p2s))
    else:
        unmapped.append("p_2q")

    # --- readout ---
    pro = []
    for qb in phys:
        if flat_ro and qb in flat_ro:
            e01 = flat_ro[qb]["error_0_to_1"]
            e10 = flat_ro[qb]["error_1_to_0"]
        else:
            e01 = get(f"metrics.ssro.measure.constant.{qb}.error_0_to_1")
            e10 = get(f"metrics.ssro.measure.constant.{qb}.error_1_to_0")
            if e01 is None or e10 is None:
                e01 = get(
                    f"characterization.gate_properties.measure.constant.{qb}.single_shot_01_error"
                )
                e10 = get(
                    f"characterization.gate_properties.measure.constant.{qb}.single_shot_10_error"
                )
        if e01 is None or e10 is None:
            pro = []
            break
        pro.append(0.5 * (float(e01) + float(e10)))
    if pro:
        mapped["p_ro"] = pro
    else:
        unmapped.append("p_ro")

    # --- durations ---
    if isinstance(raw, dict) and raw.get("t_1q"):
        mapped["t_1q"] = float(raw["t_1q"])
    else:
        d1 = [get(f"gates.prx.drag_crf.{qb}.duration") for qb in phys]
        d1 = [d for d in d1 if d is not None]
        if d1:
            mapped["t_1q"] = float(np.mean(d1))
    if isinstance(raw, dict) and raw.get("t_2q"):
        mapped["t_2q"] = float(raw["t_2q"])
    else:
        d2 = [
            float(v)
            for f, (v, _) in obs.items()
            if f.startswith("gates.cz.") and f.endswith(".duration")
        ]
        if d2:
            mapped["t_2q"] = float(np.mean(d2))

    mapped["meta"] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source": raw_bundle.get("source"),
        "hub_physical": "QB3",
        "qubit_order_logical_to_physical": phys,
        "t2_note": "t2 = Ramsey T2*; t2_echo = Hahn-echo T2 (DD ceiling); both clamped",
        "t2_echo_defaulted_to_t2star": bool(locals().get("t2_echo_defaulted", False)),
        "p_2q_note": "mean (1 - CZ Clifford RB fidelity) over star edges",
        "p_ro_note": "mean of SSRO error_0_to_1 and error_1_to_0",
        "unmapped_fields_kept_as_placeholder": unmapped,
        "n_observations_parsed": len(obs),
    }
    return mapped


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default=os.environ.get("IQM_SERVER_URL", ""),
                   help="IQM server URL (or set IQM_SERVER_URL)")
    p.add_argument("--token", default=os.environ.get("IQM_TOKEN", ""),
                   help="Static API token (or set IQM_TOKEN). "
                        "Alternatively set IQM_TOKENS_FILE from `cortex login`.")
    p.add_argument("--quantum-computer", default=None,
                   help="Optional quantum_computer name on multi-QPU servers")
    p.add_argument("--from-raw", default="",
                   help="Skip fetch; remap an existing raw dump "
                        "(e.g. calibrations/odra_raw.json)")
    p.add_argument("--out", default="calibrations/odra.json")
    p.add_argument("--raw-out", default="calibrations/odra_raw.json")
    p.add_argument("--num-qubits", type=int, default=5)
    args = p.parse_args()

    out = pathlib.Path(args.out)
    raw_out = pathlib.Path(args.raw_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Offline remap of an already-fetched dump (no network / token needed).
    if args.from_raw:
        bundle = json.loads(pathlib.Path(args.from_raw).read_text())
        mapped = map_to_device_calibration(bundle, num_qubits=args.num_qubits)
        out.write_text(json.dumps(mapped, indent=2))
        print(f"remapped {args.from_raw} -> {out}")
        print("unmapped (still placeholder):",
              mapped["meta"]["unmapped_fields_kept_as_placeholder"])
        print("hub:", mapped["hub"], "t1:", [round(x*1e6, 2) for x in mapped["t1"]], "us")
        print("p_1q:", [round(x, 5) for x in mapped["p_1q"]],
              "p_2q:", round(mapped["p_2q"], 5),
              "p_ro:", [round(x, 4) for x in mapped["p_ro"]])
        return

    if not args.url:
        print(
            "No --url / IQM_SERVER_URL set.\n"
            "Writing a TEMPLATE calibration you can fill by hand from the\n"
            "ODRA / Resonance dashboard, plus instructions.\n"
        )
        from noisy_sim import DeviceCalibration
        cal = DeviceCalibration(num_qubits=args.num_qubits)
        template = {
            "num_qubits": args.num_qubits,
            "hub": 0,
            "t1": cal.t1.tolist(),
            "t2": cal.t2.tolist(),
            "t2_echo": cal.t2.tolist(),
            "t_1q": cal.t_1q,
            "t_2q": cal.t_2q,
            "p_1q": cal.p_1q.tolist(),
            "p_2q": cal.p_2q,
            "p_ro": cal.p_ro.tolist(),
            "meta": {
                "status": "TEMPLATE_PLACEHOLDER",
                "how_to_fill": [
                    "Option A (API): set IQM_SERVER_URL + IQM_TOKEN and re-run.",
                    "Option B: python collect_odra_calibration.py "
                    "--from-raw calibrations/odra_raw.json",
                    "Option C (dashboard): paste T1/T2/errors into fields above.",
                ],
            },
        }
        out.write_text(json.dumps(template, indent=2))
        print(f"wrote template -> {out}")
        return

    token = args.token or None
    auth = ("token" if args.token else
            "IQM_TOKENS_FILE" if os.environ.get("IQM_TOKENS_FILE") else "none")
    print(f"fetching calibration from {args.url} (auth: {auth}) ...")
    bundle: dict[str, Any]
    try:
        bundle = _try_fetch_via_iqm_client(args.url, args.quantum_computer, token)
    except Exception as e1:
        print(f"iqm-client path failed ({e1!r}); trying qiskit-iqm ...")
        try:
            bundle = _try_fetch_via_qiskit_iqm(args.url, token)
        except Exception as e2:
            raise SystemExit(
                f"Both fetch paths failed.\n"
                f"  iqm-client: {e1}\n  qiskit-iqm: {e2}\n"
                f"Install: pip install iqm-client\n"
                f"Or remap an existing dump: "
                f"python collect_odra_calibration.py --from-raw calibrations/odra_raw.json"
            )

    raw_out.write_text(json.dumps(bundle, indent=2, default=str))
    print(f"raw dump -> {raw_out}")

    mapped = map_to_device_calibration(bundle, num_qubits=args.num_qubits)
    out.write_text(json.dumps(mapped, indent=2))
    print(f"mapped DeviceCalibration -> {out}")
    unmapped = mapped["meta"]["unmapped_fields_kept_as_placeholder"]
    print("unmapped (still placeholder):", unmapped)
    nobs = mapped["meta"].get("n_observations_parsed", "?")
    print(f"observations parsed: {nobs}")
    if unmapped:
        raise SystemExit(
            "FAIL: calibration fields still placeholder. "
            "Raw dump may be empty — check IQM_TOKEN / URL and re-run."
        )
    print("OK: all fields mapped from live ODRA calibration.")
    print("hub:", mapped["hub"],
          "t1_us:", [round(x * 1e6, 2) for x in mapped["t1"]],
          "p_2q:", round(mapped["p_2q"], 5))


if __name__ == "__main__":
    main()
