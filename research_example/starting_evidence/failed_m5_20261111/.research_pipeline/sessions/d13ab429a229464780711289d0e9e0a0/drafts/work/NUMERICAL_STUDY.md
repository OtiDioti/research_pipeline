# Numerical study (PRELIMINARY)

[Code](study.py), [inputs](parameters.json), [raw results](results.json), [dependency versions](versions.json), [derivation](DERIVATION.md), [literature](../sources/LITERATURE.md).

## Model and provenance
A two-component LH–SO vertical eigenproblem is represented in normalized sine functions on [0,L], with exact analytic z, kz² and derivative matrices. The hard walls and homogeneous band parameters intentionally remove all material-gradient mechanisms. The reference L=25 nm and |F|=1 mV/nm reflect manuscript dimensions/field, not its finite-barrier calculation. Ge gamma, Delta, b, elastic constants and lattice constant come from the 2024 primary source table. Si lattice constant 5.4307 Angstrom comes from the public Valvo supplement's lattice fit endpoint. Linear Vegard interpolation with xGe=0.95 estimates strain only; using Ge elastic and band parameters for this strain is an explicit approximation. It gives epsilon_parallel=0.00201233, Qepsilon=9.58900 meV. No alloy band offset or gradient coefficient was invented. alpha0=38.0998212 meV nm² is a fixed conventional hbar²/(2m0) value; physical precision is far worse than its stored digits. Hydrostatic strain is a common shift in this homogeneous model and is omitted.

## Results
All alpha values below are signed meV nm in the derivation's convention. The source partition fixes the full eigenpair rather than switching off couplings.

| Hole potential slope F (mV/nm) | Kinetic-source alpha | Strain-source alpha | Total alpha | Signed shares |
|---|---:|---:|---:|---|
| 0.5 | -0.8095183 | +0.0246624 | -0.7848559 | 103.1423%, -3.1423% |
| 1.0 (N=80) | -1.6194811 | +0.0491066 | -1.5703745 | 103.1271%, -3.1271% |
| 1.5 | -2.4302836 | +0.0731361 | -2.3571475 | 103.1027%, -3.1027% |

The entire linear coefficient in this box is the symmetric LH–SO mechanism; kappa' and q' are identically zero. The table's finer kinetic/strain partition is an algebraic source decomposition *within* LH–SO, not a fraction of measured device mechanisms. A small SO probability (0.0004806 at F=1) does not imply a negligible linear coefficient: it is an interference matrix element. HH is above the LH ground state by 7.5795 meV at this reference point.

At L=20 and 30 nm, total alpha=-1.5851931 and -1.5627556. This small decrease of magnitude with width differs from the finite-device trend in the manuscript; it is evidence that this approximation cannot reproduce the device trend quantitatively.

## Checks and limitations
N=20,40,60,80 give alpha=-1.5703554,-1.5703738,-1.5703744,-1.5703745. The N=60 to 80 change is 7.61e-8 meV nm. The source sum reconstructs alpha to about 4.2e-14 meV nm across the study; SO-envelope reconstruction errors are below 4e-16 in norm. Field reversal reverses signed alpha; F=0 gives 2.2e-16. Raising Delta by 1000 lowers |alpha| to 0.00173974 and SO weight to 5.09e-10, consistent with suppression when SO states decouple.

A separate four-component LH/SO-partner matrix diagonalized at k=1e-5 and 3e-6 nm^-1 yields |alpha| from half the energy splitting divided by k. Agreement is about 1.4e-6 meV nm or better at the reference; small-k eigenvalue subtraction loses precision, especially at F=0 and huge Delta. These finite-k matrices include the linear operator but omit quadratic/cubic in-plane terms, so this is a projection implementation check, not a full dispersion calculation. No unresolved execution failure remains. Initial execution failed because SciPy was absent; a local virtual environment fixed it. Independent verification is required before any checked label.

No random sampling or seeds. Exact rerun instructions and comparison tolerances are in [interface](m5-study.json). Floating-point eigenvalue splitting is cancellation-sensitive; use rtol=1e-7, atol=3e-6 for whole JSON comparisons, while analytical projection itself converges much more tightly. No timestamps are embedded in the numerical results.
