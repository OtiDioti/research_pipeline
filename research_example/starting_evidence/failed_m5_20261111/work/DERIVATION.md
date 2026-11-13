# Linear coefficient: projection and a defined source partition (PRELIMINARY)

Sources: supplied [29 October manuscript](../starting_evidence/Light_Hole_Spin_Qubits_in_Strained_SiGe_Lattice_Matched_to_Ge.pdf), unchanged [human notes](../starting_evidence/my_notes_on_light_holes.tex), [public earlier full text](../sources/2608.25852v1.html), and [ordered six-band source](../sources/2604.21732.html). See [access assessment](../sources/LITERATURE.md).

At zero in-plane momentum and biaxial [001] strain, HH is decoupled, while each Kramers partner has real envelopes (l,s), normalized jointly, with the second partner's SO component carrying the opposite sign. In the notes' positive-hole convention:

\[
H_0=\begin{pmatrix}T_L+V-Q_\epsilon&-2\sqrt2\alpha_0 k_z\gamma_2k_z+\sqrt2Q_\epsilon\\-2\sqrt2\alpha_0 k_z\gamma_2k_z+\sqrt2Q_\epsilon&T_S+V+\Delta\end{pmatrix},
\quad T_L=\alpha_0 k_z(\gamma_1+2\gamma_2)k_z,\quad T_S=\alpha_0 k_z\gamma_1k_z.
\]

The scalar hydrostatic shift is absorbed into V. Here alpha0=hbar²/(2m0), with energy in meV, z in nm, k in nm^-1. Hole potential is +F z in meV when F is in mV/nm; the electron-energy source's field has opposite sign. An overall pseudospin rephasing changes all signed alpha terms together. Define signed alpha to recover Eq. (14) of the earlier public Valvo supplement for constant material:

\[
\alpha_{\rm sym}=-3\sqrt2\alpha_0\operatorname{Im}\langle l|\{\gamma_3,k_z\}|s\rangle,
\quad\alpha_\kappa=\alpha_0\int dz\,\kappa'(2l^2+\sqrt2ls-2s^2),
\quad\alpha_q=5\alpha_0\int dz\,q' l^2.
\]

These formulas follow by taking the opposite-partner matrix element of dH/dk_x in the notes' displayed six-band matrices. The symmetric term has two LH–SO cross entries; the material-gradient matrices supply LH–LH, LH–SO and SO–SO entries. Their sum is the linear coefficient in this specified ordered model. For constant gamma3, alpha_sym=-6 sqrt(2) alpha0 gamma3 Im<l|kz|s>, agreeing algebraically with public Eq. (14). For real envelopes it equals 6 sqrt(2) alpha0 gamma3 integral(l s'). The coefficient of momentum p is alpha/hbar; the splitting is 2|alpha||k|, not |alpha||k|.

HH has no component in the isolated k=0 LH doublet and supplies no first-order-in-k contribution in this model; virtual HH coupling enters k² and cubic terms. This statement fails at an LH–HH degeneracy or with additional symmetry-breaking mixing at k=0. Structural asymmetry is a condition enabling these matrix elements, not an extra additive Hamiltonian contribution. Intrinsic atomic SO coupling is already encoded in Delta and the Bloch basis. Remote-band electric-field terms and microscopic interface invariants are absent unless explicitly added.

The derivative gamma3' inside the anticommutator must be retained. Splitting 2 gamma3 s' and gamma3' s into separate percentages is representation/ordering dependent: integration by parts redistributes them. Similarly, switching off a mechanism and re-solving changes envelopes and cannot generally produce additive shares.

## Homogeneous infinite-box quantitative approximation

The reference calculation uses L=25 nm and |F|=1 mV/nm (the manuscript Fig. 2 field is 1 V/micrometre), with a tensile strain estimated at xGe=0.95 lattice-matched to Ge, but homogeneous Ge band parameters and infinite barriers. It is an explicitly approximate diagnostic of the supplement's infinite-well mechanism, not reproduction of the finite asymmetric SiGe stack. Constant kappa,q have zero derivatives: alpha_kappa=alpha_q=0 by construction.

A useful further *defined*, signed source partition separates the two origins of the SO envelope. With the converged full eigenpair (E,l,s) held fixed, let R=(H_SS-E)^(-1), C_T=-2 sqrt(2) alpha0 gamma2 kz², C_epsilon=sqrt(2) Qepsilon. Then

\[
s_T=-R C_T l,\quad s_\epsilon=-R C_\epsilon l,\quad s=s_T+s_\epsilon,
\quad\alpha_T=6\sqrt2\alpha_0\gamma_3\langle l|\partial_z|s_T\rangle,
\quad\alpha_\epsilon=6\sqrt2\alpha_0\gamma_3\langle l|\partial_z|s_\epsilon\rangle.
\]

This is an exact algebraic decomposition within the finite numerical Hamiltonian. Both pieces require the same self-consistent mixed state and are interference amplitudes; their signed ratios may exceed 100% or be negative. They are not independent probabilities or universally observable mechanisms. Removing strain also changes l,E and is a different experiment. The symmetric F=0 limit must give alpha=0; F reversal must reverse alpha in this symmetric box. The s=0 four-band limit has zero linear term in this specified model.
