# Motor-readout track: brief (owner request, 2026-09-26)

Owner: Marius Carlsson. Program: research\neurobiology\, run by neuro-research-queen, with a MATHEMATICIAN agent.

The owner asked: "make the mathematician research the data transfer of the brain and how we can read it in real time to control things."

## Scope: theory plus computational verification on OPEN data only
1. **Information theory.**
   - The Shannon capacity of the neural channel.
   - The Wolpaw ITR and its known flaws.
   - The bits/s published BCIs achieve (cursor, handwriting, speech), from sources that were actually opened.
   - The limits: noise, channel count, nonstationarity.
2. **Decoders.**
   - Wiener/Kalman (including ReFIT-style), latent state-space/dynamics models (e.g. LFADS-type), Riemannian EEG decoders, and small RNNs.
   - For each: the math, the assumptions and the computational cost.
3. **Real-time constraints.**
   - The latency budget from spike to action.
   - Bin size vs accuracy.
   - Closed-loop stability, from a feedback-control view.
4. **Nonstationarity.**
   - Decoder drift across days.
   - Recalibration math: adaptive filters, domain adaptation, stabilising latent manifolds.
5. **A pre-registered computational test** on an OPEN motor dataset that needs no sign-up, e.g. Neural Latents Benchmark MC_Maze on DANDI, or an open EEG motor-imagery set.
   - Verify the licence and size first, and stay under about 1.5 GB.
   - Compare Kalman vs Riemannian/linear vs a small RNN on decoding accuracy, bits/s and across-session drift.
   - Use the leak-proof harness (nfharness).

## Deliverables (in this folder)
prereg\, code\, results\, an independent REVIEW, and THEORY.md (verified conclusions plus what stays open).

## Rules
- Computational only. The output is DECODING of intended movement for control, with nothing about stimulating the brain.
- Research use only, not a medical device.
- No sign-ups; no git (the lead commits).
- Use "Marius Carlsson".
