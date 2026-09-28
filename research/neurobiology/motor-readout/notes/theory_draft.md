# Motor readout: theory draft (information, decoders, real time, drift)

RESEARCH USE ONLY. NOT A MEDICAL DEVICE. No clinical claims. Software intended for diagnosis, monitoring or treatment decisions
may be a medical device under EU MDR 2017/745 (e.g. Rule 11) or FDA SaMD rules. Any clinical use requires regulatory clearance
and clinical validation (IRB/ethics approval).

Author: mathematician (motor-readout track), for Marius Carlsson, 2026-09-26. Status: DRAFT, unreviewed. Scope: reading out
intended movement for control (decoding only).

**Label conventions.** [Rn] = a source in lit\readout.md (opened, graded). **DERIVATION** = follows mathematically from the
stated assumptions (checked numerically in this session where marked). **ESTIMATE** = an order-of-magnitude judgement, not a
measurement. **UNVERIFIED** = plausible but not seen in an opened source.

---

## 1. Information theory of the readout channel

### 1.1 Channel model and capacity

Chain: intention U -> neural activity Y (spikes, SBP, EEG) -> decoder -> output V -> effector. By data processing,
I(U;V) <= I(U;Y). No decoder can beat the information the recording carries, and every stage (bin, feature, filter, output
quantisation) can only lose information (DERIVATION: data-processing inequality).

Shannon's Theorem 17 [R1]: a channel of band W with white Gaussian noise power N and average signal power P has capacity
C = W log2(1 + P/N) bits/s. Theorem 11 [R1]: rates below C are achievable with arbitrarily small error, but only by coding
over long blocks. A BCI user cannot block-code their intentions, so **published BCI rates are achieved rates, not capacities**,
and the gap can be large.

Generalisation to a readout (DERIVATION, Gaussian assumptions). Let x(t) be one intended kinematic dimension and y(t) its
decoded estimate, both jointly Gaussian and stationary with coherence γ²(f). Then the mutual-information rate is

    I_rate = - ∫_0^{F} log2(1 - γ²(f)) df   [bits/s],   F = Nyquist of the sampled output.

- **Exact** if x and y are jointly Gaussian.
- A **lower bound** on the information that y carries about x if x is Gaussian and the decoder error is treated as additive
  noise, since Gaussian noise is the worst case for a given power.
- An **approximation** otherwise. Reach velocities are not Gaussian: they are bursty.

Special case, flat coherence γ² = ρ² over a band W: I_rate = -W log2(1-ρ²) = 2W · [-½ log2(1-ρ²)], i.e. 2W independent samples
per second at -½ log2(1-ρ²) bits each.

Upper limits on I(U;Y) come from four sources:

- **(a) Noise per channel.** Poisson-like spike count noise has variance about the mean. Rate-estimate variance is r/T for
  window T (DERIVATION, Poisson), so information per bin grows only logarithmically with rate x bin.
- **(b) Channel count N.** For N independent Gaussian channels the capacity adds: C <= Σ_i W log2(1+SNR_i). Shared (correlated)
  variability lowers the effective N. The mechanism of information-limiting correlations is UNVERIFIED here (no source opened).
- **(c) Behavioural bandwidth W.** The intended signal only carries information up to the bandwidth of the intended movement.
  For reaching this is a few Hz (ESTIMATE; measured in the prereg as the velocity spectrum).
- **(d) Nonstationarity** (§5). A decoder that is optimal on day 0 sees a lower effective SNR on day k, so its achieved rate
  falls even when I(U;Y_k) does not.

### 1.2 Wolpaw ITR: formula, assumptions and flaws

Formula [R8, eq. 1, attributed to R5]:

    B = (1/c) [ log2 N + P log2 P + (1-P) log2((1-P)/(N-1)) ]   bits/s,   c = time per selection.

Thompson et al. [R8] list the assumptions under which B equals mutual information:

- (i) a memoryless, stable discrete channel;
- (ii) equiprobable targets;
- (iii) the same accuracy for every target;
- (iv) errors spread uniformly over the other N-1 symbols.

They add that real BCIs "typically violate several of these assumptions". Yuan et al. [R7] document ITRs that were reported
inconsistently and incorrectly online.

**A useful identity (DERIVATION).** The bracket equals log2 N - h(P_e) - P_e log2(N-1), with P_e = 1-P and h the binary
entropy. That is exactly Fano's lower bound on I(X;Y) for a uniform input. Consequences:

1. With uniform priors and a memoryless channel, the Wolpaw bracket is a **lower bound** on the per-trial MI even when (iii)
   and (iv) fail. Asymmetric errors only make the true MI larger or equal.
2. The real failures are elsewhere:
   - **Non-uniform priors and memory.** Language has H(X) < log2 N per character, so B **overstates** the information in text
     output [R9].
   - **Wrong c.** Leaving pauses, error correction and calibration out of c inflates B [R7, R8].
   - **Offline accuracy.** Using offline instead of online accuracy [R8].
   - **Small-sample bias.** Accuracy measured on a few trials has a large variance, and B is convex in P near chance, so
     noisy accuracies inflate the average B (DERIVATION; see the numbers below).
3. **Achieved bitrate** [R10] (Nuyujukian/Pandarinath): B_ach = log2(N-1) · max(S_c - S_i, 0)/t. It charges each error one
   extra selection (a backspace). It is a conservative, operational measure, **not** a mutual information.

Numbers (DERIVATION, computed in this session):

| case | bits/selection |
|---|---|
| N=2, P=0.6 | 0.029 |
| N=2, P=0.7 | 0.119 |
| N=2, P=0.8 | 0.278 |
| N=36, P=1 | 5.17 |
| 8 targets at 1 net selection/s (achieved bitrate) | log2 7 = 2.81 bits/s, matching R10's worked example |

A 2-class EEG motor-imagery BCI at 65% accuracy and 4 s/trial gives 0.99 bits/min; at 75% it gives 2.83 bits/min.

### 1.3 Achieved rates (as reported), with the conversions labelled

| system | reported [source] | conversion (label) |
|---|---|---|
| iBCI point-and-click, 3 people | 1.4 / 2.2 / 3.7 bits/s achieved bitrate [R10]; earlier 0.64 / 0.93 bits/s [R10 citing R12] | none needed |
| iBCI handwriting | 90 char/min, 94.1% raw accuracy, 31-character set [R13] | ITR with uniform priors: 4.34 bits/char x 1.5 char/s = **6.5 bits/s UPPER-BIASED** (DERIVATION). Assumption (ii) fails: English characters are not equiprobable, and the language entropy per character (UNVERIFIED value) is far below log2 31 = 4.95. |
| iBCI speech (Willett) | 62 wpm, 23.8% WER at 125k words [R14] | Ceiling only: log2(125,000) = 16.9 bits/word gives <= 17.5 bits/s before error penalty (DERIVATION of a uniform-vocabulary ceiling). The true rate is much lower because of language priors. **Not a comparable number.** |
| iBCI speech (Card) | about 32 wpm conversational, 97.5% accuracy [R15] | same caveat |
| intracortical LFP typing | 3.07 / 6.88 ccpm, no recalibration for 76 / 138 days [R16] | a stability-for-rate trade-off |
| finger iBCI | NN +36% throughput over ReFIT-KF [R19] | throughput definition not opened: UNVERIFIED units |

**Caution on comparing numbers.** An offline, open-loop information rate about continuous kinematics (the prereg's M-BITS) is
**not** comparable with a closed-loop achieved bitrate of selected symbols [R10]. The first measures how much the decoded
trajectory says about the true trajectory. The second counts task-level decisions after the user, feedback and errors. The
offline number can easily be larger (ESTIMATE) and must never be quoted as "BCI speed".

**Conclusion for the program.** Across modalities, the only like-for-like number is an information measure computed under
stated assumptions. That is why the prereg defines one (§2) and keeps the Wolpaw ITR to the EEG arm where its assumptions can
be checked.

---

## 2. From decoder accuracy to bits/s

### 2.1 Continuous decoders (R², correlation, coherence)

- **Per sample (DERIVATION, rate-distortion).** For a Gaussian target with variance σ² and any estimate with MSE D,
  I(x;ŷ) >= ½ log2(σ²/D) = -½ log2(1-R²_CoD), where R²_CoD = 1 - D/σ² is the coefficient of determination.
- For non-Gaussian x, the Shannon lower bound R(D) >= h(x) - ½ log2(2πeD) applies, and the Gaussian formula is **not**
  guaranteed to be a lower bound.
- Mutual information is invariant to invertible rescaling of ŷ, but R²_CoD is not: gain and offset errors lower R²_CoD without
  lowering information. The squared correlation ρ² (after optimal linear rescaling) is the information-relevant quantity.
  Thompson [R8] notes the scale-invariance of ρ as a caveat for control, because a decoder with the right direction but the
  wrong gain still steers badly. **Both** metrics are therefore reported.
- Table (DERIVATION):

  | R² | 0.3 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 0.95 |
  |---|---|---|---|---|---|---|---|
  | bits per independent sample | 0.26 | 0.50 | 0.66 | 0.87 | 1.16 | 1.66 | 2.16 |

  Doubling the information per sample needs the error variance to fall by a factor of 4. This is a law of diminishing returns
  in R².
- **Per second.** Consecutive decoded bins are **not** independent, so "bits per bin x bins per second" overcounts. The
  spectral formula of §1.1 is the defined route. Coherence estimated from K segments is biased upward, with E[γ̂²] ≈ 1/K under
  the null.
  - Over a 10 Hz band this bias alone is worth 0.74 / 0.29 / 0.14 / 0.05 bits/s for K = 20 / 50 / 100 / 300 (DERIVATION,
    computed here).
  - The prereg therefore subtracts a permutation null (median over trial-shuffled pairings) and sums dimensions only under a
    stated independence assumption.

### 2.2 Discrete decoders (accuracy, confusion matrix)

- I(X;Ŷ) = Σ p(x,ŷ) log2 [p(x,ŷ) / (p(x)p(ŷ))] from the confusion matrix. The plug-in estimate is biased upward for small n
  [R4]. Use the Miller-Madow correction, (bins-1)/(2n ln 2) bits, and a label-permutation null.
- The Wolpaw bracket is the Fano bound (§1.2), so it is reported only when (ii) balanced classes holds within ±5 percentage
  points. Otherwise MI is reported.

---

## 3. Decoders: equations, assumptions and cost

Notation: N channels, H history bins, d output dimensions, n latent/state dimensions, h RNN hidden units, T training bins.

**3.1 Wiener / ridge (linear filter with history) [R20, R24].**

- Model: ŷ_t = Σ_{k=0}^{H-1} W_k x_{t-k} + b, with W = (XᵀX + λI)⁻¹ XᵀY on lagged features (p = N·H).
- Assumptions: a linear, time-invariant map; stationary noise; errors weighted equally in time.
- Cost: training O(T p² + p³); inference p·d multiply-adds per bin. For example, N=96, H=6, d=2 gives 1,152 MACs per bin
  (DERIVATION). Trivial on any CPU.
- **Causal** by construction if k >= 0 only.

**3.2 Kalman filter [R21].**

- State model: z_t = A z_{t-1} + w_t, w ~ N(0,Q). Observation model: x_t = C z_t + q_t, q ~ N(0,R). z = kinematics
  (e.g. [pos, vel, 1]).
- A, Q, C, R are fitted by least squares on training pairs [R21].
- Recursion:
  - Prediction: ẑ⁻ = A ẑ, P⁻ = A P Aᵀ + Q.
  - Gain: K = P⁻Cᵀ(C P⁻Cᵀ + R)⁻¹.
  - Update: ẑ = ẑ⁻ + K(x_t - C ẑ⁻), P = (I - KC)P⁻.
- Cost per step: O(N n² + N² n + n³), or O(N³) naively in the inverse. The Woodbury identity gives O(n³ + N n²).
- **Steady state (DERIVATION).** P converges when (A, C) is detectable and (A, Q^{1/2}) stabilisable. Then K is constant and
  ẑ_t = (I-K C) A ẑ_{t-1} + K x_t. This is a **linear IIR filter** on the neural data: an infinite-history Wiener filter with
  exponentially decaying weights. The cost per bin is O(N n), the same as ridge.
- So "Kalman vs Wiener" is mostly a comparison of priors on smoothness and history length, not of model classes. Both assume
  linear-Gaussian observations. Spike counts are Poisson-like, which violates this at small bins.

**3.3 ReFIT-KF [R22].**

- Same filter, but trained on closed-loop data with an **intention estimate**: decoded velocity rotated toward the target, and
  zero on the target. This removes the bias from the user fighting decoder errors.
- The cursor position is treated as **known feedback**, not as an uncertain state.
- Consequence: **ReFIT is defined only with closed-loop data.** Offline, on open-loop datasets, it reduces to a velocity KF
  trained on arm kinematics. Its advantage is replicated online [R11, R17, R19] (grade A), but **cannot be tested in this
  track**. The prereg says so and does not claim to test it.

**3.4 Latent-dynamics models: LFADS [R25], NDT [R26].**

- LFADS: a sequential VAE. A generator RNN g_t = f(g_{t-1}, u_t); factors f_t = W g_t; rates r_t = exp(W_r f_t); Poisson
  likelihood; ELBO training.
- The standard LFADS encoder reads the whole trial, so it is non-causal and not usable in real time without modification
  (UNVERIFIED from the abstract; follows from the architecture as generally described).
- NDT is non-recurrent and reported **3.9 ms inference** [R26].
- Both need GPU-scale training for good results (ESTIMATE). **Excluded from the 20-min CPU prereg.** They are the natural next
  step if the linear-vs-GRU gap proves large.

**3.5 Small RNN (GRU).**

- Equations:
  - Update gate: u_t = σ(W_u x_t + U_u h_{t-1} + b_u).
  - Reset gate: r_t = σ(W_r x_t + U_r h_{t-1} + b_r).
  - Candidate: h̃_t = tanh(W_h x_t + U_h (r_t ⊙ h_{t-1}) + b_h).
  - State: h_t = (1-u_t) ⊙ h_{t-1} + u_t ⊙ h̃_t.
  - Output: ŷ_t = V h_t + c.
- Parameters: 3(hN + h² + 2h) + d(h+1), using the PyTorch convention of two bias vectors per gate. For h=64, N=96, d=2:
  31,234 (DERIVATION: 3·(6144+4096+128) + 130).
- Inference: about 3(hN + h²) = 30,720 MACs per bin, i.e. **microseconds on a CPU** (ESTIMATE).
- Training: BPTT, O(T · 3(hN+h²)) per epoch.
- Causal if run forward only. Assumptions: none on linearity. Needs more data, and is sensitive to distribution shift unless
  trained across days [R37].
- Offline, NNs beat Wiener/KF [R24]; online, a shallow NN beat ReFIT-KF by 36% throughput [R19].

**3.6 Riemannian EEG classifiers [R28, R29].**

- Epoch covariance: C_i = X_i X_iᵀ/(T-1), an SPD matrix of size n x n (n = 64).
- Affine-invariant distance: δ(A,B) = || log(A^{-½} B A^{-½}) ||_F = (Σ_j log² λ_j(A⁻¹B))^{½}.
- Riemannian mean: the fixed-point iteration M ← M^{½} exp( (1/m) Σ_i log(M^{-½} C_i M^{-½}) ) M^{½}.
- MDRM: assign the class of the nearest class mean.
- Tangent space at reference M: s_i = upper(log(M^{-½} C_i M^{-½})), with off-diagonal entries weighted by √2. Dimension
  n(n+1)/2 = 2,080 for n = 64. Then a linear classifier. TSLDA gave 65.1% → 70.2% over CSP+LDA [R28].
- Cost: one n x n eigendecomposition per epoch, O(n³) = 2.6·10⁵ flops (DERIVATION). Trivial.
- Invariance (DERIVATION): δ(WAWᵀ, WBWᵀ) = δ(A,B) for any invertible W. Riemannian distances are therefore unchanged by a
  fixed linear mixing of channels, e.g. a session-wide gain change common to all epochs.
- This also motivates **per-session re-centring**: C ↦ M_s^{-½} C M_s^{-½}. The primary source for this method was not opened:
  UNVERIFIED attribution; the math is a DERIVATION.

---

## 4. Real-time constraints

### 4.1 Latency budget from spike to action

    τ_total = τ_acq + τ_bin/2 + τ_feat + τ_dec + τ_smooth + τ_out + τ_display ( + τ_visual, inside the user's loop)

- A causal boxcar bin of width Δ reports samples whose mean age is Δ/2 (DERIVATION). For example, 50 ms bins [R22] give 25 ms.
- Exponential smoothing y_t = α y_{t-1} + (1-α) x_t adds a DC group delay of α/(1-α) bins (DERIVATION): 1, 4, 9 and 19 bins
  for α = 0.5, 0.8, 0.9, 0.95. At 20 ms bins, α = 0.9 alone adds 180 ms.
  - Velocity KFs behave like this in steady state (§3.2).
  - Users adapt to the smoothing and gain [R33].
- Decoder compute: ridge and GRU are sub-millisecond on a CPU (ESTIMATE, §3); NDT 3.9 ms [R26].
- Display and visual-processing latencies: no source opened, so UNVERIFIED. They are typically tens of ms (ESTIMATE).

### 4.2 Bin size vs accuracy

- For a Poisson rate r estimated over a window T: Var = r/T and delay = T/2. The **error-delay product is constant**
  (DERIVATION). Offline metrics see only the error, so they favour long bins (100-300 ms). Closed loop pays for the delay, so it
  favours 25-50 ms [R31]. Higher control rates improve control [R32].
- The prereg includes a bin-size sweep ({10, 20, 50, 100} ms, Kalman and ridge) as a **descriptive** offline check of the
  error side of this trade-off. It cannot measure the closed-loop side.

### 4.3 Closed-loop stability (feedback-control view)

Model the user + decoder + cursor as a discrete integrator with loop delay d bins:
p_{t+1} = p_t + g u_{t-d}, with the user's proportional policy u_t = K (target - p_t) [R33 shows that real policies are richer].

- Characteristic polynomial: z^{d+1} - z^d + gK = 0.
- **Stable iff 0 < gK < 2 sin(π / (2(2d+1)))** (DERIVATION; verified numerically in this session from the polynomial roots):

  | d (bins) | 0 | 1 | 2 | 3 | 4 | 5 |
  |---|---|---|---|---|---|---|
  | max stable gK | 2.000 | 1.000 | 0.618 | 0.445 | 0.347 | 0.285 |

- For large d, gK_max ≈ π/(2d+1). The fastest stable closed-loop bandwidth is therefore ω ≈ π/(2τ) for a total delay τ = dΔ,
  independent of the bin size. This matches the continuous-time integrator-plus-delay result (DERIVATION).
- With τ = 150 ms: ω_max ≈ 10.5 rad/s (1.7 Hz) at zero phase margin. A practical margin (ω ≈ π/(4τ)) gives about 0.8 Hz
  (ESTIMATE, since τ is assumed).
- Implication: **each 10 ms of added delay lowers the maximum stable gain**. Shorter bins and less smoothing raise the
  achievable closed-loop bandwidth even at equal offline R² [R31, R32].
- Decoder smoothing is a trade-off: it lowers output noise but adds delay, which forces a lower gain. The user adapts the gain
  [R33], but the stability bound holds for any linear policy of this form.

### 4.4 Decoder-internal stability

- A KF with a stable A (spectral radius < 1) and bounded P is BIBO stable.
- A GRU's state is bounded by construction, since h is a convex combination of tanh outputs, so |h| <= 1 (DERIVATION).
- A fitted A with ρ(A) >= 1 (e.g. an integrated position state) must be handled by feeding back the known position, as ReFIT
  does [R22], or by excluding position from the state. The prereg decodes velocity only.

---

## 5. Nonstationarity and recalibration math

### 5.1 Drift model

- Day-k observations: x_t^{(k)} = C_k z_t + μ_k + ε_t, where z = latent intention and kinematic state.
- Sources of change in C_k and μ_k:
  - neuron turnover and amplitude loss (2.4%/month average AP amplitude decline [R36]);
  - micromotion;
  - the user's strategy changes [R34].
- A fixed day-0 linear decoder W, with zero-mean noise, has error on day k (DERIVATION):

      e_t^{(k)} = W(C_k - C_0) z_t + W(μ_k - μ_0) + Wε_t + (W C_0 - G) z_t

  - The first term is a **gain/rotation** error.
  - The second is a **bias** (the "velocity bias" that R12 corrects).
  - The last is the day-0 residual.
- So R²_fixed(k) = R²_0 - [tr(W ΔC Σ_z ΔCᵀ Wᵀ) + ||W Δμ||²] / Var(y) + cross terms. The bias term alone can drive R² negative.

### 5.2 Recalibration families

1. **Unsupervised mean / scale re-normalisation.**
   - Replace μ_0 and σ_0 with day-k statistics from **unlabelled** neural data. This removes the bias term.
   - Cost: O(N) per update. It needs only neural data, as in R12's tracking of statistics during pauses.
2. **Adaptive filters.**
   - RLS with forgetting factor λ: memory ≈ 1/(1-λ) samples; gain update O(p²) per sample. This trades tracking speed against
     noise.
   - LMS: O(p) per sample; step size μ < 2/λ_max(Σ_x) for mean stability (DERIVATION, standard).
   - CLDA smooth batch updates of the form W ← βW_old + (1-β)W_new [R35: "smooth decoder updates"; exact form UNVERIFIED].
     Half-life = ln 0.5 / ln β updates. For example, β = 0.9 gives 6.6 updates.
3. **Latent-manifold alignment [R38-R40].**
   - Factor analysis per day: x = L_k z + μ_k + ε, ε ~ N(0, Ψ_k).
   - Align L_k to L_0 by orthogonal Procrustes: O* = argmin_{OᵀO=I} ||L_k O - L_0||_F = U Vᵀ, where U S Vᵀ = svd(L_kᵀ L_0)
     (DERIVATION, standard).
   - Then apply the day-0 latent decoder to the aligned latents E[z|x]·O*.
   - R40 names "Procrustes alignment of axes provided by Factor Analysis" as one of three unsupervised methods. R38 reports that
     manifold alignment can beat supervised recalibration. R38's stable-channel selection is UNVERIFIED here, so the prereg uses
     all channels and says so.
   - Assumption: the latent dynamics are stable across days [R39] and only the embedding L changes. The method fails if the
     task or the user's strategy changes the latent distribution.
4. **Training for robustness.** Pool many days and add synthetic perturbations [R37]; FALCON formalises few-shot and zero-shot
   evaluation [R41].

### 5.3 Drift metrics (used in the prereg)

- Retention: ρ_k = R²_fixed(k) / R²_within(k). Both are evaluated on the **same** day-k held-out test block. R²_within uses a
  decoder of the same class trained on day k's own earlier calibration block, so it controls for day-k difficulty.
- Recovery fraction of a recalibration arm: φ_k = (R²_arm - R²_fixed) / (R²_within - R²_fixed).
- Information view: bits/s(k) from §2.1. Drift lowers the effective SNR, so bits fall roughly as -½ log2(1 - R²(k)) per
  independent sample (DERIVATION, Gaussian case).

---

## 6. What stays open (for THEORY.md after the run)

- The true information of text-generating BCIs. This needs a language-entropy source, not opened.
- The closed-loop claims (ReFIT, latency and stability, bin optimum) are theory only here. An offline dataset cannot test them.
- Whether the linear/GRU gap on MC_Maze_Large survives a condition-held-out split (the prereg reports this descriptively).
- The Gaussian coherence bound on bursty reach velocities is an approximation (§1.1). A nonparametric MI estimator (k-NN) would
  be the check. It is left out of the CPU budget.
