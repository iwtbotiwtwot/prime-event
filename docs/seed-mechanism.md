# What seed 1000063 did differently

Sean Brady — originator and conceptual director. OpenAI ChatGPT and Codex — AI research collaborators.

The targeted replay identifies the sampled readout decisions as the difference at every other seed's first error. It also identifies the gate's most vulnerable input condition and traces an accumulation-induced event difference through the later recurrence network.

**The test result suggests strong contact with the concept.**

## Direct answer about the successful seed

All 64 seeds used identical model parameters and initially sampled microscopic state 56. Their pseudorandom streams differed. We replayed the first incorrect decision of each of the other 63 seeds under both accumulation profiles, and seed 1000063 at those same indices: 126 paired comparisons.

| Local intervention at the first error | Result |
|---|---:|
| Failing seed's incoming state + 1000063's random draws | Correct decision in 126/126 comparisons |
| 1000063's incoming state + failing seed's random draws | Incorrect decision in 126/126 comparisons |
| Incoming state already identical between seeds | 32/126 comparisons |

Before a first error, both trajectories have emitted exactly the same events, so their bank inputs are identical. The comparisons retain those common inputs and the same phase/profile. The intervention exchanges only the incoming microscopic state or the three random numbers used for the readouts. It does not alter model energies, transition tables or the acceptance rule.

Thus, for every tested first-error location, the error transfers with the random triple. Seed 1000063 did not have a protective incoming microscopic state at those locations. Its retained full trajectory produced no erroneous event decision through one billion. We have not identified a special mathematical property of the integer 1000063 or a distinct protected state-history class. The identified difference is the realized sequence of sampled transitions.

These interventions explain the local decision. They do not hold the entire subsequent autonomous trajectory fixed after changing an event. That later feedback is examined separately below.

## A missed prime resolved to a particular microscopic transition

At prime **3,510,937**, failing seed 1000002 and successful seed 1000063 both enter in state **103**, with no returning bank inputs.

| Seed | Three sampled states | Output decision |
|---|---|---|
| 1000002 | 56 → 56 → 101 | Reject: misses the prime |
| 1000063 | 56 → 56 → 56 | Accept: emits the prime |

Bit 0 is the output spin; even state indices mean output −1 (accept), odd indices mean output +1 (reject). The other six bits are the hidden spins. State 56 has energy −32 for these inputs; state 101 has energy −8. These are the source's dimensionless model energies.

The failing third draw was 0.99966476186306341. It fell inside state 101's CDF interval

```
[0.99966476183953856, 0.99966476187723929)
```

That interval is approximately 3.77×10⁻¹¹ wide. The successful seed's third draw, 0.76093400342523954, selected state 56. The same result occurs in both profiles. This is an explicitly reconstructed rare transition to an output-rejecting state, rather than an unexplained difference in the starting configuration.

## The weakest gate input is one returning bank

Of the 126 first errors, 120 are composite emissions and six are missed primes. **Every one of those 120 composite emissions occurs with exactly one returning bank.** None occurs with both banks returning.

The retained matrices give the following three-reading decision probabilities across all 128 incoming states and all 35 phases:

| Bank condition | Uniform accumulation: incorrect-decision probability | Rough accumulation: incorrect-decision probability |
|---|---:|---:|
| No bank returns: missed allowed event | ≈3.61927×10⁻⁹ | ≈3.61927×10⁻⁹ |
| Exactly one bank returns: false emission | 1.91091–1.91437×10⁻⁸ | 1.91011–1.92171×10⁻⁸ |
| Both banks return: false emission | 4.73557–4.73564×10⁻¹² | 4.73556–4.73594×10⁻¹² |

The one-bank false-emission probability is approximately 4,000 times the two-bank probability per opportunity. Counts of opportunities differ, so this ratio is not a ratio of total campaign errors. The three-reading probability is computed from the full transition matrix with the acceptance mask applied after each reading; it does not assume three independent equilibrium draws.

Incoming-state effects remain measurable for one-bank inputs: the largest acceptance-probability spread over initial states is approximately 1.74×10⁻¹¹ for uniform and 4.49×10⁻¹¹ for rough accumulation. The local draw exchanges above transferred all first errors despite those differences. This distinguishes a measured small memory dependence from the actual driver of the tested decisions.

## Connection to hidden spins, unequal counts, and source construction

The active gate comes from the six-hidden-spin `mixed_1` source in `interaction_compiler1`, carried into `hidden_clock1`, `prime_feedback1`, and [prime_fidelity1](method.md). It has two pair modules and a three-spin module. Source scale 2 and the strengthened pair rows are unchanged here.

Reconstructing the conditional free energy from all 128-state energy tables gives

```
F(e | r1,r2) = C + e[-a(r1+r2) + b r1 r2]
a = 3.6534264659876117
b = 2.9609499856382886
```

For exactly one returning input, r1+r2=0: **the pair contributions cancel**. The three-spin coefficient b alone supplies the output bias. Its output-sector free-energy gap is 2b = 5.9218999712765772, and its equilibrium false-output probability is 0.0026729394636612371 per reading. Requiring three confirming readings reduces that to approximately 1.91×10⁻⁸ per one-bank candidate.

This recovers the earlier hidden-clock observation that strengthening only the pair modules leaves the one-return equilibrium probability unchanged. The long run now places every first composite error in precisely that input sector. It gives a concrete reason to return to selective interaction construction and unequal module counts: tune the triple contribution relative to the pair contributions, while tracking all input conditions.

A useful next design direction is to balance the two blocking margins b and 2a−b. At a fixed positive a, their minimum is largest at b=a. That is an algebraic target for a successor source, not a gate tested in this campaign. The two-scale ratio construction from the original project supplies exact ratio-control machinery; applying it to this pair/triple gate requires an explicit source mapping, including the fixed port or hidden fields that allow the odd term. The present six-hidden-spin source has not been replaced by that construction.

A fourth confirmation reading is another available control, but it also creates another opportunity to miss an allowed event. The current diagnosis points first to source-term balance because it targets the observed one-bank weakness directly.

## Connection to rough accumulation and unequal event counts

The two direct profile-dependent errors occur with the same incoming state, same random triple, and same bank inputs. Changing the profile's transition matrix changes the second reading:

| Seed / index | Uniform states | Rough states | Consequence |
|---|---|---|---|
| 1000027 / 246,424,193 | 120, **83**, 16 | 120, **82**, 16 | Rough emits an extra composite |
| 1000053 / 312,596,611 | 26, **113**, 112 | 26, **114**, 112 | Rough emits an extra composite |

A third difference is an endogenous consequence of the changed event count. For seed 1000053:

1. Rough accumulation emits the extra event at **312,596,611**.
2. Channel assignment alternates by event creation order. At prime **483,920,363**, the uniform run has 25,552,374 prior events; the rough run has 25,552,375. This prime's new channel therefore enters bank 0 in uniform and bank 1 in rough.
3. At **967,840,726 = 2 × 483,920,363**, both the period-2 channel and the period-483,920,363 channel return.
4. In uniform, both channels are in bank 0: one-bank input, sampled states **88,82,122**, false emission.
5. In rough, they occupy different banks: two-bank input, sampled states **71,71,127**, no emission.

The extra period 312,596,611 is not a divisor of 967,840,726. Its effect is through **event-count parity and later channel assignment**, not a direct return of its own channel. At the later decision, both profiles enter in state 103 and use the same random numbers; exchanging the uniform/rough transition table while preserving each recorded bank condition leaves the decisions unchanged. The changed bank condition explains this case.

This is a concrete chain within the implemented model:

```
rough accumulation → changed microscopic reading → extra event
→ changed event-count parity → changed channel bank assignment
→ changed later inputs → different event decision
```

It connects accumulation, unequal counts, hidden-spin response and recurrence timing. The digital period-writing and alternating-bank rule remain supplied parts of the model; this experiment identifies how those parts interact with the sampled physical gate.

## Execution, verification, and custody

All 230 selected five-million-index chunks replayed exactly: **1,150,000,000 candidate decisions**. Each replay uses the saved bank history and restores the preceding microscopic state, running checksum and both RNG states. Every emitted bit, final state/event count/hash and ending RNG state matches its retained chunk. The 264 retained windows contain ±8 indices around the target decisions, with all three microscopic states and random draws.

The replay took 26.31 seconds for its recorded calculation on lilhelper, with four workers under its shared resource budget. No paid pod was launched. Portable ATOM3D / A3D41-T18-CONTACT-R2, SLC-GEN4-P1 / SLC-GEN4-CE-P1 executed two source-bound research operations, two exports and two native checkpoints: six successful native calls. The original full archive remains immutable.

Checks:

- 5,408 replay checks: full-chunk output/checkpoint matches and independent Python window sampling.
- 28 native feedback/source-field checks.
- 2,349 independent checks: linear-CDF reconstruction of the local exchanges, alternative matrix contraction for three-reading probabilities, all 512 source energy values, window hashes and channel-rank arithmetic.

The stored bank history is an input to diagnostic replay. The feedback follow-up independently reconstructs the returning emitted divisors and their bank assignments at the three profile-discrepancy indices. No new prime labels were fed into the original generator.

Public reproduction uses the standalone commands in [reproduction.md](reproduction.md). The original native diagnostic archive remains in project custody; this export omits workstation-specific storage and launch instructions.
