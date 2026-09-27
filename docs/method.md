# Model and executable specification

The gate has seven dynamic spins: one output and six hidden spins. Two input
spins are clamped by the current return banks. All variables are dimensionless.
The source matrices, hidden fields and35-phase exposure arrays are supplied in
`prime_event/sources/RECIPE.json`; the manuscript gives their mathematical form.

For candidate n, phase is(n−2)mod35. Bank input bits indicate whether at least
one previously emitted period returns at that integer. Accept iff the sampled
output spin is−1 on all three successive readings. All three samples are
consumed even if an earlier reading rejected. PCG64(base seed) supplies the
initial state draw and third reading for each candidate; PCG64(seed+1000000)
supplies the first two. Each row is sampled at its first CDF entry strictly
greater than the uniform draw. State parity encodes the output: even accepts.
The running microscopic-state checksum is FNV-style uint64 arithmetic, starting
at1469598103934665603, updating(hash XOR state)*1099511628211 for every reading.

An accepted event p installs returns at2p,3p,... . Its bank is the parity of its
creation rank, starting at rank0. This is a supplied digital sieve. Return-bank
history depends on emitted events, including any errors, rather than on an
external prime list. The independent reference sieve runs after generation.

At beta1 and pair strength4, set a=log(cosh8)/2. The baseline triple strength2
has b=(4log(cosh4)−log(cosh8))/2. Balanced construction solves

    (4 log cosh(2t) − log cosh(4t))/2 = a,

with t=2.3464897298984759. This equalizes the one-bank blocking margin b and
two-bank margin2a−b. It changes microscopic coupling strengths while holding
cadence, exposure profiles, Gamma512 and three-reading acceptance fixed.
See [the algebraic derivation](balanced-derivation.md).

The Markov generator flips one spin at a time, with rate
1/[1+exp(E(new)−E(old))]. The transition over each reading interval is computed
by a positive Poisson-series uniformization, scaled and squared, then normalized
by columns. Tables contain binary64 transition CDFs, not an exact symbolic
matrix exponential. Their exact bytes are retained for trajectory replay.

The public scheduler uses5-million-candidate RAM windows by default. Before
sampling a window it reconstructs bank returns from previously stored events.
Within a window, new events immediately mark their later multiples. An event's
creation rank is preserved across every boundary and cache/disk read. Thus
segmentation changes memory/storage behavior, not the stochastic recurrence.
Chunk outputs contain lossless event gaps, errors, RNG/state checkpoints and
hashes. Bank/emission bit arrays can be reconstructed from the event sequence;
checked-repair branches also require their recorded correction lists.

Raw-mode online calibration is observational only. Eight cells represent bank
bits and gate decision; bank-only parent estimates supply fixed-strength32
shrinkage. Predict with the old model, evaluate against new reference labels,
then update counts. No model prediction or reference label enters raw generation.
