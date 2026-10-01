# Prime-event: how prime events are created

**Data, reproducible experiments, and the mechanism behind the generated stream.**
Sean Brady: originator and conceptual director. OpenAI ChatGPT and Codex: AI research collaborators.

## Headline results: raw feedback through one billion

**Changing one spin interaction reduced errors by 92.97%: 569 → 40 across the matched experiments.** Error-free billion-index trajectories increased from **1/64 to 47/64 per profile**. A separate fresh-seed continuation achieved **13/16 error-free trajectories per profile**.

Each trajectory starts at candidate 2 and runs through **1,000,000,000**, including **50,847,534 primes**. The table reports errors made by the gate's own event stream, with **no reference repair**. An independent checker scores the decisions afterward.

### Accuracy by experiment

Each matched row covers 64 trajectories (about 64 billion decisions); each fresh row covers 16 trajectories (about 16 billion decisions).

| Experiment | Profile | Errors / billion | Error-free runs |
|---|---|---:|---:|
| Original | uniform | 4.4375 | 1/64 |
| Original | rough | 4.4531 | 1/64 |
| Balanced, matched | uniform | 0.3125 | 47/64 |
| Balanced, matched | rough | 0.3125 | 47/64 |
| Balanced, fresh | uniform | 0.1875 | 13/16 |
| Balanced, fresh | rough | 0.1875 | 13/16 |

### What the errors were

| Experiment | Profile | False events | Missed primes | Total |
|---|---|---:|---:|---:|
| Original | uniform | 271 | 13 | 284 |
| Original | rough | 272 | 13 | 285 |
| Balanced, matched | uniform | 17 | 3 | 20 |
| Balanced, matched | rough | 17 | 3 | 20 |
| Balanced, fresh | uniform | 2 | 1 | 3 |
| Balanced, fresh | rough | 2 | 1 | 3 |

**How to read these numbers.** A false event emits a composite; a miss suppresses a prime. “Error-free” means neither occurred anywhere in that complete trajectory. The rate divides total errors by all candidate decisions, not just primes or emitted events. Each run contains exactly 999,999,999 decisions; the billion totals above are rounded for readability.

The matched comparison uses the same 64 seeds for original and balanced gates. Uniform and rough profiles also share random streams within each seed, so their 128 trajectories per source represent **64 paired seeds**, not 128 independent seeds. The fresh experiment uses 16 new seeds with the balanced source fixed in advance. Across all six rows, the package retains **288 trajectories and 287,999,999,712 candidate decisions**. This is ensemble work across repeated integer ranges, not a single trajectory reaching 288 billion.

The physical change is the triple-module strength **t: 2 → 2.3464897299**, at **β = 1 and u = 4**, balancing the effective margins at **a = b ≈ 3.653426466**. The derivation and mechanism follow the reproduction instructions below.

[Download the headline table](evidence/headline_results.csv) · [Inspect every trajectory and error position](evidence/trajectories.json) · [Matched comparison](evidence/matched_comparison.json) · [Fresh-seed summary](evidence/fresh_summary.json).

## Longer runs: checkpoints and dated snapshots

The longer experiments include a **fully unrepaired trajectory through 172,469,780,479**, with **44 false events and 4 missed primes**: **0.2783 errors per billion decisions**. The original 128-state CPU raw control reached **81,820,000,001**, with **30 errors**. These are individual trajectory endpoints.

The following compact table separates raw feedback from reference-assisted repair. **Error totals always count raw gate errors before any repair.** “Fork” denotes a raw branch that inherited an earlier repaired history.

| Seed / branch | Through (billions) | Feedback | Errors / billion |
|---|---:|---|---:|
| 20000001 CPU | 81.820 | raw | 0.3667 |
| 20000001 CPU repaired | 81.175 | checked repair | 0.3696 |
| 20000002 CPU | 81.140 | checked repair | 0.1972 |
| 30000001 GPU | 104.480 | checked repair | 0.2680 |
| 9360001 GPU | 172.470 | checked repair | 0.3073 |
| 9360001 GPU fork | 172.470 | fork | 0.3015 |
| 9360002 GPU | 172.470 | checked repair | 0.3595 |
| 9360003 GPU | 172.470 | raw | 0.2783 |
| **9365001 sole GPU*** | **9.110** | **no correction** | **0.4391** |

*9365001 is the retained **October 1, 19:43:31 UTC early snapshot**: **3 false events + 1 missed prime = 4 errors** through **9,110,028,287**. This is not its final endpoint.

**Latest sole seed — 9365001: no repair or correction.** It started with empty history at candidate 2. Every accepted event feeds back unchanged, and missed primes are never inserted. The independent checker only scores decisions; no learner or reference correction steers the run. Its retained dated snapshot is included in the long-run report.

[Full long-run results and methodology](docs/long-runs.md) · [Exact endpoints and counts (CSV)](evidence/long-runs/summary.csv) · [Checkpoint-derived result records](evidence/long-runs/).

The CPU and seed 30000001 records use the original 128-state balanced source. Seeds 9360001–9360003 use the later 8-state production model with Γ = 512 and η = 3/8. Their model/source identities and paired-history details are given in the linked report. The earlier 288-trajectory matched experiment remains a separate comparison.

## Connection to the frustrated-spin project

The **[frustrated-spin repository](https://github.com/iwtbotiwtwot/frustrated-spin)** supplies an important foundation for this work: exact joint configuration counts and thermal boundary responses that connect an Ising graph's interactions, degeneracy and entropy to prime-event gate design.

That connection has been calculated explicitly. A four-port spin source is reduced to the gate's pair/triple interaction form by pinning one port and selecting the input/output signs. For the **N1000 positive-fill packet source**, compiling the resulting interaction ratio into a 128-state gate reduced the worst uniform one-bank false-emission probability by **about 8.26-fold**, from **1.91437 × 10⁻⁸ to 2.31833 × 10⁻⁹**. This is a finite-rate conditional gate result; the balanced-gate stream results above are a separate experiment. The spin dataset provides a concrete route from exact many-spin calculations to new gate designs.

[Source-to-gate derivation and results](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/spin_prime_connection1/REPORT.md) · [How entropy and spin data enter this model](#where-entropy-and-spin-data-enter).

## Data access

- **[Published trajectory data](evidence/trajectories.json):** all 288 trajectory records, exact error positions, terminal states, event counts and historical checksums.
- **[Data availability and provenance](docs/data.md):** included inputs, original trace custody and regeneration scope.
- **[Zenodo archive](https://doi.org/10.5281/zenodo.23002148)** · [initial archived version](https://doi.org/10.5281/zenodo.23002149) · [publication paper](zenodo/Prime_Event_Zenodo_Paper.pdf).
- **[Seven-page guide: How prime events are created](docs/Prime_Event_Guide_2026-10-01.pdf):** the October 1, 2026 guide adapted below, with its equations preserved in readable Markdown.

Frozen baseline and balanced sampling inputs are included. The compact release contains the numerical inputs needed to regenerate the event streams; the approximately 32 GB original bulk trajectory archive is held separately and is not bundled in Git or the compact Zenodo software archive. [Full experiment commands](docs/reproduction.md) reproduce the ensemble.

## Reproduction: quick start

Linux, Python 3.10–3.12 and a C++17 compiler (`g++`) are required. NumPy 1.26.4
is pinned for historical RNG replay. No GPU, private SAM/SLC runtime, paid pod,
remote machine or external dataset account is needed.

```bash
git clone https://github.com/iwtbotiwtwot/prime-event.git
cd prime-event
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
python scripts/check_evidence.py
python -m prime_event run --source balanced --seed 1000000 \
  --until 1000000 --chunk 100000 --output runs/demo
```

Run on a filesystem with **more than 10% available space**. Production commands
stop at that threshold and before consuming a 256 MiB commit reserve. The run
verifies frozen source hashes, compiles a small C++ kernel, predicts and trains
an independent calibration head, scores the raw gate against a segmented sieve,
and writes compressed, hash-linked checkpoints. In default `raw` mode, reference
labels and learned predictions never enter the feedback generator.

The same command resumes a saved run. Increase `--until` to continue; keep the
source, seed, profile, mode and chunk size unchanged. `--cache-mib 256` is the
default bounded event cache. A larger cache reduces repeated reads. `run` is
single-process/single-core numerical work; `follow` uses four pinned processes.

## Reproduce a published billion-index trajectory

```bash
python -m prime_event run --source baseline --seed 1000063 \
  --until 1000000000 --output runs/baseline-exact
python -m prime_event verify --experiment baseline-matched --seed 1000063 \
  --output runs/baseline-exact

python -m prime_event run --source balanced --seed 1000000 \
  --until 1000000000 --output runs/balanced
python -m prime_event verify --experiment balanced-matched --seed 1000000 \
  --output runs/balanced
```

`verify` compares error totals and the full terminal microscopic state, event
count and running state checksum with the published record. Use `--profile rough`
for the paired profile and `balanced-fresh` for fresh-seed verification.
[Full experiment commands](docs/reproduction.md) cover all 288 trajectories.
The standalone segmented scheduler preserves the historical decisions and RNG
stream but uses a new compact file format, so historical trace-file hashes are
provenance identifiers rather than expected hashes of newly generated chunks.

## Mechanism and measured results

Adapted from the October 1, 2026 guide. The billion-index results below use the published 128-state gate and raw feedback.

## How prime events are created

*The mechanism, the physical ingredients, and the measured results*

A new event creates a repeating signal. Returning signals suppress later events. A small interacting-spin system makes the accept-or-suppress decision. With an ideal decision rule, the emitted indices are exactly the primes; with a thermal gate, accuracy depends on its interactions, clock, and memory.

### The idea in one loop

Candidate n → returning channels → two input banks → spin evolution → three confirming readings → accepted event → a new period-n channel.

### What makes this a physics calculation?

Energy biases the output spin. Entropy changes that bias when hidden configurations are summed. Geometry and accumulation set the available relaxation time. Hidden spins retain history. These ingredients determine a calculable probability of creating the next event. [1–4]

### The main measured result

Changing one interaction strength reduced total errors from 569 to 40 across 64 paired seeds under two accumulation profiles, each trajectory extending through candidate 1,000,000,000. That is a 92.97% reduction. For each profile, 47 of 64 balanced-gate trajectories were exact throughout the billion-index range. [3]

### What “predict” means here

The generator advances through integer candidates and emits decisions before an independent checker scores them. The arithmetic structure is an event-built sieve; the physical model supplies its stochastic gate. The demonstrated result is accurate sequential prime-event generation in simulation. The production architecture also explicitly supplies integer counters, channel storage, and readout logic.

## Start with an empty network

*A worked example and the mathematical reason primes emerge*

Begin at n = 2 with no channels. An event accepted at p installs a period-p channel whose first return is at 2p, followed by 3p, 4p, and so on. Successive channels alternate between two banks. Each bank reports whether any of its channels returns. [1]

| Candidate | Returning periods | Ideal action |
| --- | --- | --- |
| 2 | None | Emit; install period 2 |
| 3 | None | Emit; install period 3 |
| 4 | 2 | Suppress |
| 5 | None | Emit; install period 5 |
| 6 | 2 and 3 | Suppress |
| 7 | None | Emit; install period 7 |
| 8 / 9 / 10 | 2 / 3 / (2 and 5) | Suppress |
| 11 | None | Emit; install period 11 |

Write B₀(n) and B₁(n) for the return bits of the two banks. The ideal output is:

$$
y_n=(1-B_0(n))(1-B_1(n)).
$$

Why this continues: assume all earlier events are primes. A prime n has no earlier prime divisor, so no channel returns. A composite n has a smaller prime divisor p; the already installed channel p returns at n. Starting from 2 establishes the prime sequence by induction.

The software schedules future multiples of accepted periods. In raw feedback, even an erroneous accepted composite installs its own channel. Prime labels are used afterward for scoring; they do not steer those raw decisions.

## Build the decision from spins

*Seven free spins, two clamped inputs, and a controllable energy margin*

Let r₁ and r₂ be +1 for a returning bank and −1 for no return. The output e = −1 means accept. Two pair modules and four additional hidden spins give seven free spins altogether: 2⁷ = 128 microscopic states. Summing the hidden states gives the output free energy [2]:

$$
F(e\mid r_1,r_2)=C+eH,\qquad H=-a(r_1+r_2)+b r_1r_2.
$$

C is independent of e. The microscopic construction uses pair couplings and hidden fields; the effective three-spin term b emerges when hidden variables are eliminated. For inverse temperature β, pair strength u, and triple-module strength t:

$$
a=\frac{\log\cosh(2\beta u)}{2\beta},\qquad b=\frac{4\log\cosh(2\beta t)-\log\cosh(4\beta t)}{2\beta}.
$$

| Returns | Field H | Desired output |
| --- | --- | --- |
| Neither bank | 2a + b | Accept |
| One bank | −b | Suppress |
| Both banks | −2a + b | Suppress |

At equilibrium, the accepting probability follows directly from the two output weights:

$$
P(e=-1\mid r_1,r_2)=\frac{1}{1+\exp(-2\beta H)}.
$$

The suppressing margins are b and 2a − b. At fixed a > 0, their smaller value is largest at b = a. This selected the balanced gate algebraically, before its new prime-event outcomes were examined. At β = 1 and u = 4, changing t from 2 to 2.3464897299 made a = b = 3.653426466. [3]

## Geometry, accumulation, and time

*The source needs time to respond—and carries memory into the next decision*

For a one-spin change x → y, the heat-bath transition rate is set by the energy change. Q is the generator with unit attempt rate; its diagonal makes every column sum zero. [2,4]

$$
Q_{yx}=\frac{1}{1+\exp[\beta(E_y-E_x)]},\qquad Q_{xx}=-\sum_{y\ne x}Q_{yx}.
$$

The supplied corrugated-sphere path gives candidate duration dₙ. The dimensionless accumulation profile Aₙ gives a clock factor νₙ = √(1 − Aₙ). With attempt multiplier Γ, each of three equal reading intervals evolves by:

$$
T_n=\exp\!\left(Q\,\Gamma d_n\sqrt{1-A_n}/3\right).
$$

The declared profile normalization is absorbed into the exposure. Uniform and rough profiles match total exposure but can distribute it differently across the 35 geometry phases. Geometry changes response time; the shared integer counter still fixes channel-return positions.

### Three readings, with the hidden state retained

Let D keep only states whose output is −1, and let ρ be the incoming state distribution. The probability that all three readings accept is:

$$
P_{\rm accept}=\mathbf{1}^{\mathsf{T}}D T_n D T_n D T_n\rho.
$$

This matrix product retains correlations between readings. The simulated microscopic state also carries into the next candidate; three independent equilibrium draws would discard that memory.

### How “absolute time” enters this implementation

The common candidate counter supplies a shared ordering coordinate. Local operational exposure controls how far the spins evolve before a reading. These are distinct clocks in the model. The retained runs use dimensionless energies and times; an absolute calibration in seconds is not part of these prime-event results. A separately tested state-dependent accumulation clock can also change residence probabilities. [4]

## Where entropy and spin data enter

The underlying exact Ising-graph data and methodology are documented in the companion **[frustrated-spin project](https://github.com/iwtbotiwtwot/frustrated-spin)**.

*A concrete bridge from a graph’s configurations to a prime gate*

For an Ising graph, g(E,M,σ) counts configurations with energy E, magnetization M, and ordered boundary assignment σ. We use σ for the boundary so it is not confused with gate coefficient b. A uniform field h changes the energy to E − hM. [5]

$$
Z_\sigma(\beta,h)=\sum_{E,M}g(E,M,\sigma)e^{-\beta(E-hM)},\qquad F_\sigma=-\beta^{-1}\log Z_\sigma.
$$

With Boltzmann’s constant set to one, F = ⟨E⟩ − TS. Degeneracy matters: many accessible hidden configurations can change a boundary preference even when a ground-energy comparison looks similar.

### The tested source-to-gate map

A zero-field four-port source has pair and four-spin free-energy terms. Pinning one port turns the four-spin term into an effective three-spin term on the remaining ports. Choosing input/output signs and cancelling the output bias gives the same pair/triple form used above. [6]

$$
\beta F=e[d+u_1r_1+u_2r_2+w r_1r_2]+\mathrm{input\ terms}.
$$

For the N = 1000 positive-fill packet source, the mapped ratio is b/a = 0.90706987. Compiling that ratio into a new 128-state gate reduced the worst uniform one-bank false-emission probability from 1.91437 × 10⁻⁸ to 2.31833 × 10⁻⁹: about 8.26-fold. These are finite-rate conditional calculations; this source-derived gate did not receive a new closed-loop prime run. The balanced gate remains more accurate. [6]

### Entropy makes a numerical contribution

$$
\frac{\beta\Delta F}{2}=\frac{\beta\Delta\langle E\rangle}{2}-\frac{\Delta S}{2}=4.0074318192-0.3687797623.
$$

The resulting pinned-source field is 3.6386520569 before the output-field cancellation. This is an explicit energy–entropy contribution to the gate design. The useful response also occurs in an unfrustrated packet graph; the measured improvement is tied to boundary interactions, not uniquely to frustration. [6]

## What the evidence establishes

*Prime streams, particle connections, and the most useful next bridge*

### A physical change improved the generated stream

| Billion-index matched runs | Original | Balanced |
| --- | --- | --- |
| Uniform: false events / misses | 271 / 13 | 17 / 3 |
| Rough: false events / misses | 272 / 13 | 17 / 3 |
| Exact trajectories, each profile | 1 / 64 | 47 / 64 |

Baseline and balanced matched runs use seeds 1000000–1000063; fresh runs use seeds 10000000–10000015. Balanced matched/fresh profile pairs produced identical event sequences. Each profile uses the same 64 seeds for comparison; the two profiles share random streams within a seed. In a separate 16-seed continuation, 13 of 16 trajectories per profile were exact through one billion, with two false events and one miss per profile. [3]

### What “particle data” contributes today

The direct numerical bridge into new prime gates is the exact spin-configuration and thermal-response data described above. These are calculated model data. The related matter work supplies source-resolved species/site observables and methods for retaining hidden history; the cited prime experiments have not used measured particle-detector data as inputs to prime decisions. [4–6]

The separate Starbreaker extension tests source-dependent boundary dynamics through N = 5000. At that size, retaining boundary memory changes three-reading acceptance by about 0.918–0.934 percentage points for positive-fill sources. That is a measured memory response in its declared reduced dynamics, not a prime-classification accuracy. [7]

### A precise next connection

Use source-resolved matter or spin observables to set the gate coefficients and accumulation clock, then compare raw prime-event histories with those source choices fixed in advance. This would measure the additional prime-prediction value of those data. The source-to-gate and state-dependent-clock components have been calculated separately; their fully coupled long-run test remains open in the cited record. [4,6]

### The case to put to a prime-number specialist

The arithmetic recurrence explains why primes are the ideal event positions. Statistical physics explains the probability of realizing each event. We can derive the gate, identify its weakest input condition, and improve an actual generated prime stream by changing its interactions. That is the demonstrated connection to examine and extend.

## Sources and a compact derivation

*For a reader who wants to follow the mathematics one level deeper*

The seven-spin Hamiltonian behind the gate can be written using four sign triples p with p₁p₂p₃ = +1. The hidden spins are h₁, h₂, and zₚ:

$$
E=-u h_1(e+r_1)-u h_2(e+r_2)-t\sum_{p_1p_2p_3=1}z_p(1+p_1e+p_2r_1+p_3r_2).
$$

Summing a hidden spin gives 2 cosh of its local field. The pair module has field magnitudes 2u or 0. The four-spin module has magnitudes (4t, 0, 0, 0) when er₁r₂ = +1 and (2t, 2t, 2t, 2t) when er₁r₂ = −1. Taking −β⁻¹ log of those weights gives the coefficients above. [2]

### Retained source reports

The following retained reports supply the guide’s equations, result tables and execution records. Links point to the originating research repository; runnable public commands are given at the top of this README. The supplied PDF and its editable equation text are identified in [guide provenance](docs/GUIDE_PROVENANCE.json).

<a id="source-1"></a> **[1] [prime_feedback1/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/prime_feedback1/REPORT.md)** — event-created channels, ideal-sequence argument, raw feedback, and the shared counter.

<a id="source-2"></a> **[2] [prime_event_report2/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/prime_event_report2/REPORT.md)** — §§3–6: microscopic Hamiltonian, elimination, truth table, and confirming-readout equations. Historical status statements are superseded by [3].

<a id="source-3"></a> **[3] [prime_balance1/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/prime_balance1/REPORT.md)** — completed matched billion-index results and the frozen-source fresh-seed continuation.

<a id="source-4"></a> **[4] [prime_sam_dynamics1/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/prime_sam_dynamics1/REPORT.md)** — geometry, accumulation clocks, memory, matter connections, and which loops have been combined.

<a id="source-5"></a> **[5] [spin_prime_progress1/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/spin_prime_progress1/REPORT.md)** — exact g(E,M,b), thermal reconstruction, source-to-gate synthesis, and raw versus checked feedback.

<a id="source-6"></a> **[6] [spin_prime_connection1/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/spin_prime_connection1/REPORT.md)** — pinned-port mapping, compiled gates, finite-rate comparisons, and energy–entropy decomposition.

<a id="source-7"></a> **[7] [sb_dynamics_extension1/REPORT.md](https://github.com/iwtbotiwtwot/SAM_Research_Project/blob/concept/nonzero-amplification-bridge/GEN4/sb_dynamics_extension1/REPORT.md)** — separate boundary-dynamics extension through N5000 and its declared preparation/readout model.

Reading the numbers: conditional gate probabilities, observed stream errors, and reference-repaired production streams are different measurements. The billion-index table in this guide is raw feedback. Large checked-feedback production prefixes are not used here as evidence of an error-free raw generator.

## Three runners and a learning follower

```bash
python -m prime_event follow --seed 20000001 --other-seed 20000002 \
  --until 10000000 --chunk 100000 --output runs/follower
```

Requires four allowed CPU IDs. Optional `--cores 0,1,2,3` selects them explicitly. The runners are a matched unassisted control,
a same-seed checked-repair branch, and a second-seed checked-repair branch.
The fourth process independently checks and trains. Shared RAM buffers avoid
intermediate disk files. Predictions use the preceding model before new prime
labels are computed; training happens afterward. Each branch keeps its own
model. A fixed return-bank-veto comparator is scored alongside it.

**Checked repairs use reference labels.** They remove extra events, insert missed
ones and restore creation-order bank parity for future chunks. Raw errors remain
recorded. Learned predictions currently do not steer alone. This experiment
measures whether repairing history changes subsequent raw errors, and whether
learned correction improves on the simple comparator. It does not relabel
teacher-assisted output as unassisted prime generation.

[Learning and repair design](docs/follower.md) includes stable forks, monitoring,
quiet background operation and the original observation snapshot.

## What is included

- [Manuscript PDF](manuscript/Balanced_Hidden_Spin_Prime_Feedback.pdf),
  [editable Word](manuscript/Balanced_Hidden_Spin_Prime_Feedback.docx),
  [Markdown](manuscript/MANUSCRIPT.md), LaTeX, figures, tables and references.
- [288 trajectory records](evidence/trajectories.json), summaries, exact error
  positions and historical terminal checksums.
- Frozen baseline/balanced CDF arrays, losslessly compressed, with SHA-256 hashes.
- [Microscopic source reconstruction](docs/method.md), exact source inputs,
  source reconstruction command, standalone C++ scheduler and Python runner.
- Scalar replay/restart, learner-ordering and disk-guard tests, plus GitHub CI.
- [Provenance and data scope](docs/data.md), authorship and citation metadata.

The original bulk per-integer traces and private native runtime are not bundled.
The Zenodo software archive contains the compact reproducibility package,
not the unbundled approximately 32 GB original trajectory archive. All numerical
inputs needed to regenerate the event streams are included. The separate
[frustrated-spin DOI](https://doi.org/10.5281/zenodo.22989862) is not the prime-event
archive.

**Licenses:** MIT for software; CC BY 4.0 for research data, paper and figures.
See [LICENSING.md](LICENSING.md) for scope and the additional grant covering the
initial release. [Zenodo paper and deposit notes](zenodo/README.md).
