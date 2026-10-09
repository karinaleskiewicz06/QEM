# Observable choice: mean-Z vs separate single-qubit Z (`hub`)

**Question.** Does reading a *separate* single-qubit observable (`hub` = Z on qubit 0, full
[−1, 1] range) instead of the default **mean-Z** (`(1/n) Σᵢ Zᵢ`, compressed range) improve the
accuracy-recovery signal under ZNE? The motivation: mean-Z averaging compresses margins toward
0, and ZNE accuracy-recovery is gated by how many eval points sit near the sign-flip boundary,
so a wider-range observable *might* make recovery more visible.

**Answer: no — the separate observable is worse.** It lowers the classifier ceiling and does
not produce the expected near-boundary recovery.

## Setup

Free ODRA-calibrated noisy-simulator experiment via `margin_stratify.py`
(`--observable {mean,hub}`), identical settings for both arms:

- Patterns pooled: `all_to_all` + `circular` (high routing cost → more sign flips)
- Task: hard `two_curves`, offset 0.1; 90 eval points pooled per pattern; shots 4096
- Mitigation: ZNE, unitary folding scales {1,3,5}, Richardson extrapolation
- Per-point record: (|⟨O⟩_ideal|, label, sign(raw), sign(+ZNE)); binned into near/mid/far
  terciles by ideal margin |⟨O⟩_ideal|
- The QNN is **retrained per observable** (the observable is part of the model), so this is a
  fair comparison of two fully-trained classifiers, not one model read two ways.

Data: `margin_stratify_results.csv` (mean), `margin_stratify_hub_results.csv` (hub).

## Results

| Margin bin | **mean** \|margin\| | mean acc_raw→zne | mean recovery | **hub** \|margin\| | hub acc_raw→zne | hub recovery |
|---|---|---|---|---|---|---|
| near (boundary) | 0.078 | 0.467 → 0.483 | **+0.017** | 0.137 | 0.433 → 0.400 | **−0.033** |
| mid             | 0.284 | 0.717 → 0.750 | **+0.033** | 0.382 | 0.617 → 0.600 | **−0.017** |
| far (easy)      | 0.538 | 0.867 → 0.883 | **+0.017** | 0.618 | 0.617 → 0.650 | **+0.033** |

## Interpretation

1. **Lower ceiling.** The far/easy bin — which should sit near the noiseless ideal — falls from
   **0.87 (mean) to 0.62 (hub)**. A single qubit's Z carries far less class information than the
   mean over all five entangled qubits, so `hub` is a structurally weaker discriminator for this
   degree-8 task even when retrained.
2. **Recovery signal lost.** Under `mean`, ZNE recovery is positive in every bin. Under `hub` it
   turns **negative** precisely where the mechanism should show — the near/mid bins. ZNE cleans
   ⟨O⟩ but the single-qubit sign decision does not follow.
3. **Wider margins buy nothing.** `hub` margins are genuinely larger (0.137 vs 0.078 near),
   confirming the fuller [−1, 1] range, but the wider spread is misaligned with the labels.

## Consequence for the study

The flat hardware accuracy-recovery observed at high routing cost
(`garnet_acc100_results.csv`: acc 0.78 → 0.77 while ⟨O⟩-error 0.221 → 0.169 at 96 CZ) is **not**
an artifact of the mean-Z readout that a separate observable would fix — switching to a
single-qubit observable degrades both the ceiling and the recovery. This **reinforces the
standing decision**: ⟨O⟩-error is the primary metric; accuracy is a fragile secondary regardless
of observable. **Mean-Z stays the study readout.**

## Caveats

- Noisy *simulator*, single seed, n = 60/bin → the recovery deltas (±0.02–0.03) are within
  run-to-run noise. The robust claim is "`hub` shows no gain and a clearly lower ceiling," not the
  sign of each individual small recovery number.
- Reproduce: `python margin_stratify.py --patterns all_to_all circular --observable hub
  --out margin_stratify_hub_results.csv` (and `--observable mean` for the baseline).

---
*Analysis: 2026-08-26. Observable definitions in `noisy_sim.readout_observable` (`mean` /
`hub`); driver `margin_stratify.py`.*
