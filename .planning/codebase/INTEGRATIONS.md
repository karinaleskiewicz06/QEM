# External Integrations

**Analysis Date:** 2026-08-25

## APIs & External Services

**IQM Quantum Hardware:**
- **Garnet** (Tier-B lattice, 20 qubits, 4×5 grid) - Main Month-2 target
  - Provider: IQM Resonance cloud
  - SDK: `qiskit-iqm` (>= 15)
  - Auth: `IQM_RESONANCE_URL` (per-device endpoint) + `IQM_TOKEN` (API token)
  - Coupling map: Live (loaded from backend.coupling_map)
  - Files: `iqm_resonance.py` (adapter), `calibrations/garnet.json` (live calibration cache)

- **Emerald** (Tier-B lattice, 54 qubits, 6×9 grid) - Validation target
  - Provider: IQM Resonance cloud
  - SDK: `qiskit-iqm`
  - Auth: `IQM_RESONANCE_URL` + `IQM_TOKEN`
  - Coupling map: Live (queried from backend on first submit)

- **ODRA** (Tier-A star topology, 5 qubits) - Legacy Month 1
  - Provider: IQM Spark-class
  - SDK: `iqm-client[qiskit]` (33.0–34.0, legacy)
  - Auth: `IQM_TOKEN` or `IQM_TOKENS_FILE`, `IQM_SERVER_URL`
  - Files: `collect_odra_calibration.py` (calibration scraper)
  - Status: Superseded by Resonance for Garnet/Emerald; used in Month-1 reference only

**Benchmark Data:**
- **QML-Benchmarks** - two_curves dataset
  - Package: `qml_benchmarks.data.generate_two_curves`
  - Use: Locked classifier dataset (8 features, degree-8 polynomial, 150 samples)
  - Files: `train_vqc.py` (data generation), all runner scripts

- **UCI ML Repository** - Banknote dataset
  - Package: `ucimlrepo` (autoloads via package manager)
  - Use: Banknote authentication task (1,372 samples, 4 features) in banknote_study
  - Files: `banknote_study/run_cv_banknote.py`, `banknote_study/run_zne_banknote.py`

## Data Storage

**Local Filesystem Only:**
- Simulation results: CSV format (per-point observable, accuracy, F1, transpiled CZ count)
- Model artifacts: NumPy .npy arrays (weights), JSON (config + hyperparameters)
- Calibration: JSON format (coupling map, T1/T2, readout error per qubit)
- Figures: PNG (matplotlib outputs to `figures/` directory)

**Result Files (Examples):**
- `garnet_full_results.csv` - Full routing ladder run (placement × pattern × scale × eval point)
- `garnet_gonogo_results.csv` - Smoke-test ladder (2 patterns × 2 placements × 5 points)
- `trained_models/depth_sweep_results.csv` - VQC depth sweep (noiseless)
- `trained_models/{tag}_weights.npy` - Trained parameters per depth/pattern
- `trained_models/{tag}_reference.npz` - Frozen ideal reference (statevector X_eval/y_eval)
- `calibrations/{device}.json` - Device calibration (coupling map, readout error)

**No Remote Storage:**
- No cloud databases (Firestore, PostgreSQL, etc.)
- No object storage (S3, GCS, etc.)
- No external caching layer (Redis, Memcached)

## File Storage

**Local Filesystem:**
- Project root: `.py` source files, `.md` documentation, CSV results
- `trained_models/` - Weights and model configs (.npy, .json)
- `calibrations/` - Device calibration JSON (live coupling maps, error rates)
- `figures/` - Publication figures (PNG from make_figures.py)
- `banknote_study/upstream/src/` - Shared utilities (re-exported to main project)
- `.mplcache/` - Matplotlib font cache (created at runtime if MPLCONFIGDIR env var absent)

**Caching:**
- Matplotlib font cache: `$MPLCONFIGDIR` (defaults to `/tmp/mpl`, set in `make_figures.py:30`)

## Authentication & Identity

**No User Authentication:**
- No login system, user accounts, or session management
- Research scripts run with ambient credentials (environment variables only)

**IQM Resonance Authentication:**
- Method: Bearer token in HTTP headers (handled by qiskit-iqm provider)
- Token source: `IQM_TOKEN` environment variable (runtime only)
- Fallback: `IQM_TOKENS_FILE` (iqm-client legacy, contains JSON token dictionary)

**Authorization:**
- None; token grants full read/write access to assigned devices (Garnet/Emerald quotas)
- Quota tracking: IQM credit balance checked in `run_garnet.py:96` (advisory print before submit)

## Monitoring & Observability

**Error Tracking:**
- None; errors logged to stdout/stderr via print statements and exception tracebacks

**Logs:**
- Stdout only (no rotating files, no syslog, no cloud logging)
- Hardware submission logs: Job ID + result counts printed to terminal
- Simulation logs: Verbose output on circuit construction, transpilation, and error layers

**Debugging:**
- No dedicated error tracking service
- Device debugging: `iqm_resonance.backend_readout_errors()` retrieves live readout error rates from backend

## CI/CD & Deployment

**Hosting:**
- IQM Resonance cloud (Garnet/Emerald QPU submissions via REST API)
- Local development & simulation (no hosted service)

**CI Pipeline:**
- None; pytest runs locally (`python -m pytest` or `pytest`)
- GitHub Actions: Not configured
- Manual approval: Runbook (`hardware_runbook.md`) documents staged rollout (go/no-go gates between phases)

**Submission Pipeline:**
- gated runners: `run_garnet.py --mode gonogo` (cheap validation) before `--mode full` (production)
- Batch submission: Single Qiskit Job per (placement, pattern) pair to amortize per-job overhead
- Result retrieval: Synchronous via `backend.run(...).result()` (polling until complete)

## Environment Configuration

**Required Environment Variables (Hardware Execution):**
- `IQM_RESONANCE_URL` - Per-device Resonance endpoint (e.g., `https://garnet.resonance.iqm.fi`)
- `IQM_TOKEN` - Resonance API token (bearer token for HTTP auth)

**Optional Environment Variables:**
- `IQM_TOKENS_FILE` - Path to iqm-client tokens JSON (legacy ODRA, iqm-client fallback)
- `IQM_SERVER_URL` - ODRA server (legacy Month-1 only)
- `MPLCONFIGDIR` - Matplotlib config directory (defaults to `/tmp/mpl` in make_figures.py)

**Secrets Location:**
- Tokens: Environment variables only (never hardcoded)
- Token file: User's machine (IQM command-line toolchain sets via `cortex login`)

## Webhooks & Callbacks

**Incoming:**
- None; no web service endpoints

**Outgoing:**
- None; no external webhook subscriptions
- IQM submission is one-way: submit circuits → retrieve counts synchronously

---

*Integration audit: 2026-08-25*
