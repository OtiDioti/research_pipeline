# What comprises the linear LH spin–orbit coefficient? (PRELIMINARY)

The manuscript's total linear coefficient does **not** determine unique mechanism percentages. In the ordered six-band model, the first-order projection separates a symmetric LH–split-off matrix element from kappa' and q' material-gradient terms. Structural asymmetry enables these terms and changes their envelopes; it is not a further additive share. At an isolated biaxially strained k=0 LH doublet, virtual HH states do not contribute at first order in in-plane momentum. Additional microscopic-interface or remote-band terms require additional model inputs.

The supplied October 29, 2026 manuscript lacks its supplement. An [earlier public supplement](../sources/2608.25852v1.html) explicitly gives an infinite-well LH–SO formula. We reconstructed that limit and derived candidate gradient projections from the supplied notes and ordered primary model. See [derivation and conventions](../work/DERIVATION.md) and [source assessment](../sources/LITERATURE.md). This is not exact reproduction of the October manuscript.

## Quantified approximation

For a homogeneous Ge-parameter hard-wall well, L=25 nm, positive-hole potential slope F=1 mV/nm, and a tensile strain estimated for xGe=0.95 lattice-matched to Ge:

| Defined source contribution | alpha (meV nm) | Signed fraction |
|---|---:|---:|
| Kinetic origin of SO envelope | -1.6194811 | 103.1271% |
| Strain origin of SO envelope | +0.0491066 | -3.1271% |
| Total symmetric LH–SO | -1.5703745 | 100% |
| kappa' and q' | 0 | 0% by homogeneous-model construction |

The finer source partition holds the full eigenpair fixed and resolves the SO envelope into its kinetic and strain sources. Its signed fractions express interference, not probabilities. **These numbers cannot be assigned to the finite asymmetric SiGe device.** At F=0.5 and 1.5 mV/nm the totals are -0.7848559 and -2.3571475, with kinetic-source shares 103.1423% and 103.1027%.

The coefficient converges from -1.5703554 to -1.5703745 for 20 to 80 sine functions; the last refinement changes it by 7.61e-8 meV nm. Source reconstruction, field reversal, inversion-symmetric zero-field limit, large-SO-gap suppression and finite-k splitting checks pass within stated numerical precision. These are internal checks; a separate verifier has not yet reviewed the result. All claims remain PRELIMINARY.

## Methods, reproducibility and limits

[Study and checks](../work/NUMERICAL_STUDY.md), [program](../work/study.py), [parameters](../work/parameters.json), [results](../work/results.json), [versions](../work/versions.json). The versions file and saved-science interface remain to be completed after rollover. The code currently runs with `/tmp/lh-env/bin/python /project/work/study.py --out /project/work/m5-reproduction/results.json`; environment creation was `python3 -m venv --system-site-packages /tmp/lh-env` followed by `/tmp/lh-env/bin/pip install numpy==2.2.6 scipy==1.15.3`. No random seed is needed. Initial execution failed due to missing SciPy and was corrected; no numerical job remains running.

Ge values are source-supported; using them for the tensile SiGe strain and taking infinite barriers are explicit approximations. The calculated width trend differs from the manuscript's finite-device trend, underlining the applicability limit. The missing scientific inputs are the exact October supplement/code, SiGe composition interpolation and band-edge alignment, interface profiles/ordering used for the plotted alpha, finite domain/buffer treatment, and the corresponding normalized LH/SO envelopes. The public source describes nonlinear alloy interpolation rather than a simple linear parameter rule. No device fractions should be manufactured from these omissions.

Project contribution: an explicit projection and reproducible signed source diagnostic. No field-novelty claim is made. Next: independent verification, confirm the gradient projection against the ordered Cartesian primary operator, and obtain the actual finite-device inputs before reporting manuscript mechanism shares.
