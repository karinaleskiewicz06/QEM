# Dataset Specification — `two_curves`

Primary classification dataset for the VQC–ZNE study (`plan.md` §6).
Source: **qml-benchmarks** (Bowles, Ahmed & Schuld, [arXiv:2403.07059](https://arxiv.org/abs/2403.07059)).

---

## 1. Task

| Field | Value |
|-------|--------|
| Name | `two_curves` |
| Type | Binary classification |
| Labels | \(y \in \{-1, +1\}\) (balanced) |
| Features | \(X \in \mathbb{R}^{n_{\mathrm{samples}}\times n_{\mathrm{features}}}\) |
| Generator API | `qml_benchmarks.data.generate_two_curves(n_samples, n_features, degree, offset, noise)` |

---

## 2. Generative model

Two 1-D manifolds (curves) are embedded into \(\mathbb{R}^{n_{\mathrm{features}}}\).

1. Draw a shared Fourier coefficient tensor
   \(c \in \mathbb{R}^{n_{\mathrm{features}}\times(\mathrm{degree}+1)\times 2}\)
   with i.i.d. Uniform entries, then normalise \(\|c\|_2 = 1\).
2. For each sample on a curve, draw a scalar parameter \(t \sim U[0,1]\).
3. Coordinate \(i\) of the point is a Fourier series of \(t\):
   \[
   x_i(t)
   = c_{i,0,0} + c_{i,0,1}
   + \sum_{f=1}^{\mathrm{degree}}
     \Big(
       c_{i,f,0}\cos(f\pi t)
       + c_{i,f,1}\sin(f\pi t)
     \Big)
   + \varepsilon,\qquad
   \varepsilon\sim\mathcal{N}(0,\mathrm{noise}^2).
   \]
4. Class \(-1\): points from the base curve.  
   Class \(+1\): same generator with a constant **offset** added to every coordinate.
5. Features are **standard-scaled** (`sklearn.StandardScaler`) inside the generator.

Difficulty is controlled mainly by **`degree`** (higher → more wiggly / harder Fourier manifold).
**`offset`** sets class separation; **`noise`** blurs the curves.

---

## 3. Why this dataset for this study

- Re-uploading VQCs realise Fourier series in the inputs; `two_curves` is a Fourier-manifold task, so encoding and data are structurally matched (benchmark paper motivation).
- Difficulty knobs (`degree`, `n_features`) give a clean pre-flight ladder without changing the ansatz family.
- Not a claim of quantum advantage — a reproducible, small binary task for routing / ZNE characterisation.

---

## 4. Preprocessing used in this project

After generation:

1. Cast labels to `float` (already \(\{-1,+1\}\)).
2. `MinMaxScaler((-π, π))` on features so angle embedding `RX(w · x)` stays in a sensible range.
3. Stratified train/test split (default 70/30, `random_state=SEED`, `SEED=42`).

Decision rule after training: \(\mathrm{sign}(\langle O\rangle)\), where \(O\) is either
\(Z_{\mathrm{hub}}\) (`readout="hub"`) or the mean-Z observable \((1/n)\sum_i Z_i\) (`readout="mean"`, default).

---

## 5. Default / recommended settings

**Empirical difficulty map** (classical ceiling, `n=300`, `d=8`, seed=42):

| `degree` | `offset` | logreg (linear) | SVM-rbf (nonlinear) | verdict |
|---|---|---|---|---|
| 2 | any | ~1.00 | 1.00 | **trivial** (linearly separable) — avoid |
| 5 | 0.1 | 0.90 | 0.98 | borderline (linear nearly solves) |
| **8** | **0.3** | **0.87** | **0.93** | **genuinely nonlinear, learnable — chosen** |
| 8 | 0.1 | 0.63 | 0.87 | very hard (SVM ceiling <0.90) |
| 12–20 | 0.3 | 0.93 | 0.98–0.99 | moderately easy |

| Setting | Trivial (do NOT use) | **Study target** |
|---------|------|-------------------|
| `n_samples` | 150 | 150–300 |
| `n_features` | 8 | 8 |
| `n_qubits` | 5 | 5 |
| `degree` | ~~2~~ | **8** |
| `offset` | 0.1–0.3 | **0.3** |
| `noise` | 0.01 | 0.01 |
| Pass criterion | test acc ≥ ~90% | ≥ ~90% (ceiling ~0.93) |

> `degree` sets the Fourier complexity. The re-uploading ansatz can only realise
> frequencies up to ~(uploads per feature), so matching `degree=8` may require
> more layers `L` — verify the pre-flight actually reaches ~0.90 (see `review_notes.md`).

Seed: set `np.random.seed(SEED)` before calling the generator (the official API has no `seed` argument). This project uses `seed=42`.

---


## 7. Code entry point

Training cell in `ansatz_playground.ipynb` §3 **requires** the real generator:

```bash
pip install "git+https://github.com/XanaduAI/qml-benchmarks.git" numpyro
```

```python
from qml_benchmarks.data import generate_two_curves
np.random.seed(SEED)
X, y = generate_two_curves(n_samples, n_features, degree=DEGREE, offset=OFFSET, noise=NOISE)
```

Verified classical ceiling with this install (n=300, d=8, seed=42): degree=8 / offset=0.3 → logreg 0.867 / SVM-rbf 0.933.
