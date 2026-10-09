"""Introspect the IQM Resonance compilation API to find the twirling option.

RUN THIS IN YOUR py3.11 venv (where qiskit-iqm / iqm-client is installed), NOT in the
default py3.13 env. It prints package versions and every field of
CircuitCompilationOptions, then flags any twirling / DD / mitigation-looking fields.
No hardware, no credits — pure local introspection.

    python check_twirling_api.py
"""
from __future__ import annotations

import dataclasses


def _ver(mod):
    try:
        m = __import__(mod, fromlist=["__version__"])
        return getattr(m, "__version__", "?")
    except Exception as e:
        return f"(not importable: {e})"


def main() -> None:
    print("=== versions ===")
    for m in ("qiskit", "iqm.iqm_client", "iqm.qiskit_iqm", "qiskit_iqm", "iqm_client"):
        print(f"  {m}: {_ver(m)}")

    CCO = None
    for path in ("iqm.iqm_client", "iqm_client"):
        try:
            mod = __import__(path, fromlist=["CircuitCompilationOptions"])
            CCO = getattr(mod, "CircuitCompilationOptions", None)
            if CCO is not None:
                print(f"\n=== CircuitCompilationOptions found in {path} ===")
                break
        except Exception:
            continue

    if CCO is None:
        print("\nCircuitCompilationOptions NOT found. Search the client for twirling:")
        print("  python -c \"import iqm.iqm_client as c, inspect; "
              "print([n for n in dir(c) if 'twirl' in n.lower() or 'compil' in n.lower()])\"")
        return

    print("Fields (name : default):")
    twirl_like = []
    for f in dataclasses.fields(CCO):
        print(f"  {f.name} : {f.default!r}")
        if any(k in f.name.lower() for k in ("twirl", "dd", "dynamical", "mitig", "random")):
            twirl_like.append(f.name)

    print("\n=== FIELDS THAT LOOK LIKE TWIRLING / DD / MITIGATION ===")
    print("  " + (", ".join(twirl_like) if twirl_like else "(none matched — inspect list above)"))

    # also dump any enum types referenced (e.g. a DDMode / twirling strategy enum)
    print("\n=== enum-like option types (for allowed values) ===")
    for f in dataclasses.fields(CCO):
        t = f.type
        try:
            import enum
            if isinstance(t, type) and issubclass(t, enum.Enum):
                print(f"  {f.name}: {[e.name for e in t]}")
        except Exception:
            pass

    print("\nNEXT: once you see the twirling field (e.g. something like 'circuit_transpilation' "
          "or a dedicated twirl flag/enum), build:")
    print("  from iqm.iqm_client import CircuitCompilationOptions")
    print("  opts = CircuitCompilationOptions(<twirl_field>=<enable value>)")
    print("  # then pass to iqm_resonance.run_circuits(..., compilation_options=opts)")


if __name__ == "__main__":
    main()
