# Technology Stack

**Analysis Date:** 2026-08-25

## Languages

**Primary:**
- Python 3.11+ - Entire project (quantum circuits, simulation, training, utilities)

## Runtime

**Environment:**
- Python 3.11 or later (specified in `banknote_study/upstream/pyproject.toml`)
- No virtual environment lockfile committed; dependencies specified in pyproject.toml

**Package Manager:**
- pip (via setuptools build backend)
- Lockfile: Not committed (dependencies managed in `banknote_study/upstream/pyproject.toml`)

## Frameworks

**Core Quantum:**
- Qiskit 2.0–3.0 - Quantum circuit construction, transpilation, primitives
- Qiskit-Aer 0.15.0+ - Noisy simulator backend with configurable noise models
- Qiskit-Machine-Learning 0.9–0.10 - QNN connectors, gradient estimation, parameter-shift rules

**Machine Learning:**
- PyTorch - Model optimization (Adam optimizer), TorchConnector for QNNs
- scikit-learn - Data utilities (MinMaxScaler, train_test_split)
- QML-Benchmarks - Benchmark datasets (two_curves)

**Hardware Integration:**
- iqm-client[qiskit] 33.0–34.0 - ODRA calibration and submission (Month 1)
- qiskit-iqm (>= 15) - Garnet/Emerald IQM Resonance backend adapter (Month 2)

**Scientific Computing:**
- NumPy - Tensor and array operations
- SciPy - Curve fitting (curve_fit for Richardson extrapolation)

**Visualization:**
- Matplotlib - Publication figures (make_figures.py); uses Agg backend for non-interactive render

**Testing:**
- pytest - Test framework and discovery (42 test functions across 6 test files)

**Build/Development:**
- setuptools (>=61) - Build backend
- ucimlrepo - UCI ML repository client for dataset loading (banknote_study)

## Key Dependencies

**Critical Quantum Stack:**
- `qiskit` (2.0–3.0) - Core quantum framework; all circuits, gates, transpilation
- `qiskit-aer` (0.15.0+) - AerSimulator with NoiseModel for device-calibrated simulation
- `qiskit-machine-learning` (0.9–0.10) - EstimatorQNN, TorchConnector, ParamShiftEstimatorGradient

**Critical ML/Training:**
- `torch` - Gradient descent optimization; loss computation; parameter updates via TorchConnector
- `numpy` - Numerical arrays; statevector simulation results; calibration data

**Infrastructure:**
- `iqm-client[qiskit]` (33.0–34.0) - ODRA Tier-A backend integration (legacy Month 1)
- `qiskit-iqm` (>= 15) - IQM Resonance provider for Garnet (20 qubits) / Emerald (54 qubits) lattice devices (Month 2)
- `scipy` - Richardson polynomial extrapolation for ZNE

**Data & Visualization:**
- `qml_benchmarks` - Pre-curated two_curves dataset (real-world classification task)
- `matplotlib` - Publication-quality figures; configured for batch rendering (Agg backend)

## Configuration

**Environment:**
- IQM Resonance authentication (hardware submission only):
  - `IQM_RESONANCE_URL` - Per-device Resonance API endpoint (set per device: Garnet/Emerald)
  - `IQM_TOKEN` - Resonance API token
- ODRA / iqm-client authentication (legacy):
  - `IQM_TOKEN` or `IQM_TOKENS_FILE` - API token(s)
  - `IQM_SERVER_URL` - ODRA server endpoint
- Matplotlib cache:
  - `MPLCONFIGDIR` - Defaults to `/tmp/mpl` in make_figures.py (prevents user homedir pollution)

**Build:**
- `banknote_study/upstream/pyproject.toml` - Project metadata, dependencies, optional dev tools

## Platform Requirements

**Development:**
- Python 3.11 or later (qiskit-iqm does not build cleanly on Python 3.13; Month 1 tested on 3.11)
- pip-installable environment
- Local filesystem for simulation outputs (CSVs, NumPy .npy arrays)
- Optional: IQM API credentials for hardware execution (Resonance or ODRA)

**Production (Hardware):**
- IQM Resonance cloud access (Garnet, Emerald) via qiskit-iqm provider
- Legacy: ODRA Tier-A via iqm-client + custom transpilation
- Network connectivity to IQM Resonance servers
- IQM_RESONANCE_URL and IQM_TOKEN environment variables set in runtime environment

**Simulation (Offline):**
- No external connectivity required; runs fully local with qiskit-aer

---

*Stack analysis: 2026-08-25*
