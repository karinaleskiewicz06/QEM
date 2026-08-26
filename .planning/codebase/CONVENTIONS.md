# Coding Conventions

**Analysis Date:** 2026-08-25

## Naming Patterns

**Files:**
- Modules use snake_case: `topology.py`, `ansatz.py`, `cdr.py`, `noisy_sim.py`
- Test files use `test_*.py` pattern (co-located with module): `test_topology.py`, `test_ansatz.py`, `test_cdr.py`
- CLI runners: `run_cdr.py`, `run_qec422.py`, `run_hardware.py` (all main()-based entry points)
- Utility/analysis scripts: lowercase with underscores: `train_patterns.py`, `collect_odra_calibration.py`, `freeze_reference.py`

**Functions:**
- All functions use snake_case, including both public and private
- Public API: `device_coupling_map()`, `placement()`, `topological_distance()` (`topology.py`)
- Public API: `build_ansatz()`, `entangling_pairs()`, `two_qubit_gate_count()` (`ansatz.py`)
- Private/internal: Prefixed with underscore: `_snap_nearest()`, `_rebuild()`, `_resolve()`, `_calibration_for()` (`cdr.py`, `topology.py`)
- CLI helper functions: `main()` is the standard entry point for all runners (`run_cdr.py`, `run_qec422.py`, etc.)

**Variables:**
- All local/instance variables use snake_case: `n_qubits`, `num_features`, `y_eval`, `coupling_map`, `training_circuits`
- Loop variables: Single letters for iteration (`q` for qubit, `r`/`c` for row/column in grids, `i`/`j` for generic indices)
- Numeric abbreviations acceptable: `n` (count), `p` (probability), `T1`/`T2` (coherence times, physics names)

**Types and Type Aliases:**
- Type aliases use PascalCase when defining semantic types: `CouplingMap = list[list[int]]` (`topology.py:21`)
- Use `from __future__ import annotations` (always at top of file after docstring)
- Modern type syntax: `list[list[int]]`, `dict[str, dict]`, `tuple[str, ...]` (PEP 585 style)
- Optional types: `float | None`, `list[int] | None` (not `Optional[...]`)

**Constants:**
- Module-level constants use UPPERCASE: `ENTANGLEMENT_PATTERNS`, `ENTANGLING_GATES`, `CLIFFORD_ANGLES`, `IQM_BASIS_GATES`, `DT_NS`
- Device registries: `DEVICES`, `PLACEMENTS`, `HARDWARE_PLACEMENTS` (dict constants)
- Numeric constants: `N_DATA = 4` (QEC module), `SCALE_FACTORS = [1, 3, 5]` (ZNE levels)

**Classes:**
- All classes use PascalCase: `HardwareEfficientAnsatz`, `DeviceCalibration`
- Dataclass fields use snake_case: `num_qubits`, `coupling_map`, `t1`, `p_2q`
- Private methods use leading underscore: `_apply_entanglers()`, `_post_init__()` (`ansatz.py`)

## Code Style

**Formatting:**
- Lines appear to follow a 100-character soft limit (some wrap around 120 characters)
- Indentation: 4 spaces (standard Python)
- String quotes: Double quotes preferred for docstrings and longer strings; single quotes for short strings and dict keys
- Trailing commas in multi-line constructs

**Linting:**
- No explicit linter config detected; style is consistent but not formally enforced
- Type hints are always present on function signatures and class fields
- No wildcard imports (`from module import *`)
- Unused imports are avoided; re-exports use `# noqa: F401` comment (`noisy_sim.py:48`)

## Import Organization

**Order:**
1. **Future imports** (always first): `from __future__ import annotations` (`topology.py:17`, `ansatz.py:28`, `cdr.py:17`)
2. **Standard library**: `import json`, `import pathlib`, `import argparse`, `import csv`, `from dataclasses import dataclass`
3. **Third-party (Qiskit, NumPy, SciPy)**: `from qiskit import QuantumCircuit`, `import numpy as np`
4. **Local imports**: `from topology import device_coupling_map`, `from ansatz import build_ansatz`

**Path Aliases:**
- No path aliases detected; all imports use absolute paths relative to repo root
- Local imports are bare module names: `from ansatz import ...`, `from topology import ...`

**Example** (`run_cdr.py:24-54`):
```python
from __future__ import annotations

import argparse
import csv
import pathlib

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import Statevector

from ansatz import HardwareEfficientAnsatz
from cdr import apply_cdr, clifford_ideal_expval, fit_cdr, near_clifford_training_circuits
from noisy_sim import (
    DeviceCalibration,
    IQM_BASIS_GATES,
    execute_expectation,
    load_frozen_model,
    load_iqm_calibration,
    make_noisy_simulator,
    synthesize_lattice_calibration,
)
from metrics import accuracy, macro_f1
```

## Error Handling

**Patterns:**
- ValueError for invalid inputs/configuration: `topology.py:70-72` (unknown device)
- ValueError for out-of-range or invalid parameter choices: `ansatz.py:109-126` (`__post_init__` validation)
- ValueError for missing required configuration: `topology.py:166-169` (unset hardware placement)
- Explicit bounds checking: `topology.py:131` (placement must not exceed num_qubits)
- Input validation before computation: `cdr.py:83-98` (fit_cdr checks shape/dtype)
- No bare `except` clauses; specific exception handling or propagation only
- Error messages are descriptive and suggest fixes: `"unknown device {name!r}; expected one of {sorted(DEVICES)}"`

**Example** (`topology.py:166-171`):
```python
if layout is None:
    raise ValueError(
        f"HARDWARE_PLACEMENTS[{device!r}][{strategy!r}] is unset — fill it with "
        "real physical qubit indices from the live backend before submitting."
    )
```

## Logging

**Framework:** Standard `print()` for console output; no logging library (logger not imported)

**Patterns:**
- Status messages to stdout during execution: `run_cdr.py:119` (`print(f"CDR | model {tag}...")`)
- Progress output for long-running operations: `run_cdr.py:145-147` (dry-run reports built circuits)
- CSV file written to disk; path printed: `run_cdr.py:199` (`print(f"wrote {args.out}")`)
- Debug output conditional on `--quick`, `--dry-run` flags

**Example** (`run_cdr.py:189-191`):
```python
print(f"  {pattern:>11} | 2q={n2q:>3} | err {row['err_raw']:.3f}->{row['err_cdr']:.3f} "
      f"| acc {row['acc_raw']:.2f}->{row['acc_cdr']:.2f} "
      f"| F1 {row['f1_raw']:.2f}->{row['f1_cdr']:.2f} | r2={r2:.2f}")
```

## Comments

**When to Comment:**
- Docstrings on every public function and class (mandatory)
- Comments on non-obvious algorithm choices: `topology.py:187` (BFS treats coupling map as undirected)
- Comments on workarounds or deviations from standard patterns: `noisy_sim.py:46-48` (re-export for back-compat)
- Comments on section dividers for long modules: `zne_dryrun.py:68-70` (lines of dashes separate logical sections)

**JSDoc/TSDoc:**
- Not used; docstrings use plain text with RST-style formatting
- Function parameters documented inline in docstring: `topology.py:24-31` (Args section)
- Return types documented: `topology.py:24` (returns `CouplingMap`)
- Example for complex logic: `cdr.py:53-69` (near_clifford_training_circuits explains the construction step-by-step)

**Module Docstrings (mandatory):**
Every module begins with a detailed docstring referencing the planning documents:
- `topology.py`: References `plan_month_2.md W1` (cross-topology routing study)
- `ansatz.py`: References `plan.md §6` (circuit design)
- `cdr.py`: References `methodology_month_2.md §3, W4b` (CDR method)
- `qec422.py`: References `methodology_month_2.md §4` (QEC code design)
- Format: Free-form RST, bullet points, code blocks with `::` delimiter

**Example** (`topology.py:1-15`):
```python
"""Device topologies for the cross-topology routing study (plan_month_2.md, W1).

Single source of truth for the coupling maps of the three IQM tiers used in the
study, so ``noisy_sim`` / ``routing_sweep`` / ``run_hardware`` stop hardcoding the
5-qubit star:
  * **ODRA** (IQM Spark-class): 5-qubit **star**, hub = physical qubit 0.
  * **Garnet**: 20-qubit **square lattice** (4 x 5).
  * **Emerald**: 54-qubit **square lattice** (6 x 9).
...
"""
```

## Function Design

**Size:** Functions are typically 5–30 lines; larger blocks (>50 lines) are split with helper functions
- Example: `run_cdr.py:73-199` (main function orchestrates, calls helpers like `_calibration_for()`, `_transpiled_cz()`)

**Parameters:**
- Explicit names; no positional-only arguments in main API
- Named parameters preferred for optional arguments: `seed=42`, `n_train=100`
- Keyword-only arguments (after `*`) for optional knobs: `topology.py:212` (`derive_placements(..., n_logical: int = 5)`)
- Default values always specified for optional args

**Return Values:**
- Single return value (scalar/string/dict) when possible
- Tuples for related multiple returns: `cdr.py:83` returns `(a, b, r2)` for fit parameters
- Structured return: dict for collections of related fields: `run_cdr.py:175-187` (metrics collected in `row` dict)
- No implicit None returns; explicit `return` when nothing to return

**Example** (`topology.py:174-203`):
```python
def topological_distance(
    coupling_map: CouplingMap, num_qubits: int, a: int, b: int
) -> int:
    """Shortest-path (hop) distance between physical qubits ``a`` and ``b``."""
    if a == b:
        return 0
    # ...BFS construction...
    return -1
```

## Module Design

**Exports:**
- All public functions/classes defined at module level; no nested classes
- Private functions prefixed with underscore; not exported
- Type aliases at module level: `CouplingMap = list[list[int]]` (`topology.py:21`)
- Re-exports explicit: `from topology import star_coupling_map` with `# noqa: F401` (`noisy_sim.py:48`)

**Barrel Files:**
- Not used; each module is imported directly by name

**Structure:**
Logical sections separated by comments:
- `topology.py`: Coupling map builders → device registry → placement registry → distance algorithm → helper functions → demo
- `ansatz.py`: Constants → entry function → class definition → properties → build method → private helpers → convenience methods
- `cdr.py`: Constants → private snap/rebuild helpers → public training circuit builder → ideal evaluation → fitting → angle checking

---

*Convention analysis: 2026-08-25*
