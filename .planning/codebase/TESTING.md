# Testing Patterns

**Analysis Date:** 2026-08-25

## Test Framework

**Runner:**
- pytest 8.4.2 (pinned in environment)
- Config: No explicit pytest.ini or pyproject.toml config at repo root (uses defaults)
- Rootdir: `/Users/karinaleskiewicz/QEM`

**Assertion Library:**
- Built-in `assert` statements
- NumPy assertions: `np.allclose()`, `abs(x - y) < tolerance` for floating-point checks

**Run Commands:**
```bash
pytest                          # Run all tests (default discovery)
pytest test_topology.py         # Run specific test file
pytest -v                       # Verbose output with test names
pytest --collect-only           # List all discovered tests (73+ tests total)
pytest -k "test_star"          # Filter by test name pattern
```

**Test Count:** ~73 direct tests in main modules + ~50 in `banknote_study/upstream/tests/` = ~123 tests total

## Test File Organization

**Location:**
- Co-located with modules: `test_topology.py` (tests `topology.py`), `test_cdr.py` (tests `cdr.py`), etc.
- Test files at repo root for main deliverables: `test_ansatz.py`, `test_metrics.py`, `test_qec422.py`
- Separate test directory in subdomain: `banknote_study/upstream/tests/` for banknote ML component

**Naming:**
- Test modules: `test_*.py` (pytest discovery pattern)
- Test functions: `test_<feature>()` (lowercase, underscore-separated)
- Parametrized test function names include `<param>` in the discovery output
- Private test helpers: `_<helper_name>()` (e.g., `_bound_ansatz()`, `_is_bidirectional()`)

**Structure:**
```
QEM/
  test_topology.py            # Topology coupling maps + placement tests
  test_ansatz.py              # HEA circuit building tests
  test_cdr.py                 # CDR training/fitting tests
  test_metrics.py             # Accuracy/F1 metric tests
  test_qec422.py              # QEC code tests
  banknote_study/upstream/tests/
    test_confidence.py        # ML confidence interval tests
    test_smoke.py             # Smoke/smoke tests
```

## Test Structure

**Suite Organization:**

Tests are organized by feature/function being tested, with comment section dividers:

**Example** (`test_topology.py:23-73`):
```python
# --- coupling map shape ---
def test_star_edges_and_hub_degree():
    cm = star_coupling_map(5, hub=0)
    assert len(cm) == 8  # 4 outer qubits, both orientations
    assert _is_bidirectional(cm)
    hub_out = sum(1 for a, _ in cm if a == 0)
    assert hub_out == 4

# --- topological distance ---
def test_star_outer_pair_distance_is_two():
    cm = star_coupling_map(5, hub=0)
    assert topological_distance(cm, 5, 1, 2) == 2  # through the hub
    assert topological_distance(cm, 5, 0, 3) == 1  # hub to outer
```

**Patterns:**

1. **Setup via helper functions:** Test-local helpers create fixtures inline
   - `_bound_ansatz(seed=0)` (`test_cdr.py:20-27`) — builds and binds a parameterized ansatz
   - `_counts(qc, shots=8192)` (`test_qec422.py:24-25`) — executes and extracts counts
   - `random_clifford_payload(layers, seed)` (`run_qec422.py:44-51`) — used by both tests and CLI

2. **Teardown:** Implicit; no fixture cleanup (simulator state discarded between tests)

3. **Assertion patterns:**
   - **Exact equality for integers:** `assert len(cm) == 8`
   - **Floating-point tolerance:** `assert abs(x - y) < 1e-9` (tight for deterministic tests)
   - **Set/collection membership:** `assert set(probs) == {"0000", "1111"}` (`test_qec422.py:32`)
   - **Comparison operators:** `assert acc == 1.0`, `assert spread_adv > spread_opt`
   - **No assertions on string messages** — only logic/values

## Mocking

**Framework:** None; no `unittest.mock` or `pytest-mock` used

**Patterns:**
- **Simulator-based testing:** `AerSimulator()` instantiated directly in tests (`test_qec422.py:21`)
- **Deterministic simulator:** Noiseless Aer for ideal circuit tests
- **No mocking of quantum backends:** Real Qiskit objects used throughout
- **No monkeypatching** of module state

**What to Mock:**
- Hardware access (when using `--submit` flag in runners) — skipped in tests, dry-run only
- External calibration files — synthesized on-the-fly via `synthesize_lattice_calibration()` or loaded from fixtures

**What NOT to Mock:**
- Quantum circuits (use `QuantumCircuit` directly; they're cheap)
- Simulators (use `AerSimulator` or `Statevector`)
- NumPy operations (use actual `np` functions; they're deterministic with seeds)

**Example** (`test_qec422.py:21-26`):
```python
_SIM = AerSimulator()

def _counts(qc, shots=8192):
    return _SIM.run(qc, shots=shots).result().get_counts()
```

## Fixtures and Factories

**Test Data:**
No pytest fixtures (no `conftest.py`); instead, test-local factory functions:

**Example** (`test_cdr.py:20-27`):
```python
def _bound_ansatz(seed=0):
    circ = build_ansatz(5, 2, num_features=8, entanglement="star", entangling_gate="cz")
    rng = np.random.default_rng(seed)
    wp = [p for p in circ.parameters if p.name.startswith("w[")]
    xp = [p for p in circ.parameters if p.name.startswith("x[")]
    return circ.assign_parameters(
        {**{p: float(rng.normal()) for p in wp}, **{p: 0.3 for p in xp}}
    )
```

**Location:**
- Co-located with tests in same file (not centralized)
- Named `_<data_type>()` or `<create_object_name>()` (e.g., `_bound_ansatz()`, `random_clifford_payload()`)

**Seeded Determinism:**
All randomness in tests is seeded:
- Default seed for predictability: `seed=0`, `seed=1`, `seed=2`, etc.
- Incremented for independence: `seed + layers` (`test_qec422.py:77`)
- NumPy RNG: `rng = np.random.default_rng(seed)` (modern numpy API)

## Coverage

**Requirements:** Not enforced; no coverage target specified in config

**View Coverage:**
```bash
pytest --cov=<module_name> --cov-report=html   # Not run routinely
```

**Coverage Strategy:**
- Manual inspection: All public APIs tested by `test_*.py` files
- High-risk areas (placement geometry, fit recovery) have explicit test cases
- Simulator/noisy paths tested in integration (long-running scripts, not in `test_*.py`)

## Test Types

**Unit Tests (Primary):**
- Scope: Single public function or class method
- Location: All `test_*.py` files in repo root
- Approach: Direct function calls with known inputs, deterministic outputs
- Examples:
  - `test_star_edges_and_hub_degree()` — tests `star_coupling_map()` and properties
  - `test_grid_edge_count_matches_formula()` — tests `grid_coupling_map()` against analytical count
  - `test_parameter_counts()` — tests HEA parameter accounting
  - `test_fit_recovers_known_linear_map()` — tests `fit_cdr()` with synthetic data

**Integration Tests:**
- Scope: Multi-step workflows (build circuit → transpile → simulate → evaluate)
- Location: Long-running scripts (`zne_dryrun.py`, `run_cdr.py`) with `--quick` or `--dry-run` gates
- Approach: End-to-end pipeline validation; not automated in test suite
- Example: `run_cdr.py --quick` builds training and eval circuits, fits CDR, reports metrics

**E2E Tests:**
- Framework: Not used (hardware run via `--submit` on real devices)
- Dry-run validation: `--dry-run` flag in all runners validates circuits locally
- Example: `run_hardware.py --dry-run --go-no-go` builds all circuits, estimates shot budget

## Common Patterns

**Async Testing:**
- Not applicable; circuits are synchronous state-prep + measurement

**Error Testing:**
```python
def test_placement_bad_size_and_strategy_raise():
    with pytest.raises(ValueError):
        placement("garnet", 4, "optimal")  # no hand-picked layout for n=4
    with pytest.raises(ValueError):
        placement("garnet", 5, "sideways")  # unknown strategy
```

**Parametrized Testing (pytest.mark.parametrize):**
```python
@pytest.mark.parametrize(
    "name,n,edges",
    [("odra", 5, 4), ("garnet", 20, 31), ("emerald", 54, 93)],
)
def test_device_registry(name, n, edges):
    assert device_num_qubits(name) == n
    assert len(device_coupling_map(name)) // 2 == edges
```

**Invariant Assertions (not magic numbers):**
Tests verify structural properties, not hardcoded values:
- `assert len(set(lay)) == 5` — placement is a permutation (no duplicates)
- `assert max(placement(...)) < n` — layout indices in valid range
- `assert sum(...) > 0.05` — noise produces non-degenerate spread (generic range check, not specific value)
- `assert acc == 1.0` — noiseless sim has perfect accuracy (logical consequence, not magic)

**Example** (`test_topology.py:103-108`):
```python
def test_placement_in_range():
    for device in ("odra", "garnet", "emerald"):
        n = device_num_qubits(device)
        for strat in ("optimal", "adverse"):
            assert max(placement(device, 5, strat)) < n
```

## Environment & Dependencies

**OpenMP Caveat (KMP_DUPLICATE_LIB_OK):**
PyTorch and Qiskit-Aer each ship an OpenMP runtime; loading both causes "OMP Error #179" (duplicate library).
Solution: Set environment variable BEFORE importing either library:

```python
# torch and qiskit-aer each ship an OpenMP runtime; loading both trips OMP Error #179
# Set these BEFORE importing torch/aer to allow the duplicate and single-thread.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import torch
from qiskit_aer import AerSimulator
```

**Location:** Set in `demo_hard_accuracy.py:3-4`, `train_hard.py:1-2` (files that use both PyTorch + Aer)

**Tests:** Not affected (test files do not import torch directly; they use Aer + statevector only)

## Test Naming Convention

**Function names describe behavior, not implementation:**
- ✓ `test_star_edges_and_hub_degree()` — what is being tested (edges exist, hub degree correct)
- ✓ `test_all_wrong()` — behavior when all predictions are inverted
- ✓ `test_noiseless_encode_all_accepted()` — noiseless operation should have 100% acceptance
- ✗ `test_function()` — too generic
- ✗ `test_cm_length()` — too terse (use full names for clarity)

---

*Testing analysis: 2026-08-25*
