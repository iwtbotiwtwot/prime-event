# u5 exact-throughput pilot — methodology, predictions and measurements

Target: 100,000,000 **single-trajectory candidate decisions per wall-clock
second**, including RNG, actual-event feedback, independent scoring, compression
and durable checkpoint writes. The timed interval includes the empty-history
bootstrap and waits for the final writer; one-time compilation, source
materialization and accelerator/CUDA initialization are outside this clock.
A transition-kernel rate or summed ensemble rate
does not meet this target. No full production run is authorized by this pilot.

The source remains the frozen 128-state balanced u5 model (Gamma=512, three
readings). Both PCG64 streams, candidate order, alternating actual-event bank
ranks, hidden state, all three readings and the running state checksum are
preserved. Labels are used only for scoring. No thermal approximation, source
reduction, repair or event veto is introduced.

## Final measured result — October 2, 2026 Chicago / October 3 UTC

**Accepted configuration: GPU proposals, 8 CPU preparation threads, 8 RNG
workers, two RAM buffers, 4 GiB bounded event cache, affinity 64–95.** The user
accepted a floor above 95M/s after reviewing the pilots. All five final timed
pilots exceeded that floor; one exceeded the original 100M/s target.

| Empty-history pilot | Decisions | Complete-loop seconds | Million decisions/s |
|---|---:|---:|---:|
| Frozen CPU reference | 1,000,000,000 | 144.085 | 6.94 |
| GPU repeat 1 | 1,000,000,000 | 10.046 | 99.54 |
| GPU repeat 2 | 1,000,000,000 | 10.082 | 99.18 |
| GPU repeat 3 | 1,000,000,000 | 10.243 | 97.63 |
| GPU longer repeat 1 | 2,000,000,000 | 20.389 | 98.09 |
| GPU longer repeat 2 | 2,000,000,000 | 19.780 | 101.11 |

Median: **99.18M/s**, about **14.3×** the measured pod reference. Pooled rate:
99.23M/s. Peak process RSS was about 0.91–1.35 GiB. These measurements include
scoring, compression and durable writes; they are not GPU-only kernel rates.
They cover 7B repeated timed decisions over one **2B unique trajectory prefix**,
not seven billion independent accuracy observations. All five recorded zero
false emissions and zero misses. The current seed 9370001 was separately checked
over an isolated 100M prefix, also with zero errors.

Both 2B GPU journals matched an independently executed frozen CPU trajectory:
**5,200 metadata comparisons per journal**, including authenticated event arrays,
all bank/emission/event hashes, terminal microscopic state, both RNG streams and
error positions. The current-seed comparison passed another 260 comparisons.
The 100M restart and deliberately slow-writer tests each passed all 160 frozen
reference checks. STOP left the checkpoint unchanged; an injected future orphan
was quarantined and the resumed stream remained exact. CPU and GPU boundary
tests each verified 335,744 incoming-state certifications, 105,000 full-state
decisions, changed-bank fallback, arbitrary composite event histories and grading.
The repository's existing three tests and 288-trajectory evidence check passed.

[Summary and trial records](../evidence/u5-throughput/SUMMARY.json) ·
[Machine and timing scope](../evidence/u5-throughput/ENVIRONMENT.json) ·
[Raw archive custody and SHA-256](../evidence/u5-throughput/CUSTODY.json).
The trial manifests pin every implementation file used. A module docstring was
clarified afterward; [source equivalence](../evidence/u5-throughput/SOURCE_EQUIVALENCE.json)
checks that all executable AST nodes remain identical and retains the exact
benchmarked file. Other implementation files match their trial hashes.
The original `production/u5` files and source hashes remain unchanged.

**Decision:** keep this configuration for review rather than continue tuning.
The accepted prefix throughput is demonstrated; a sustained rate at the live
hundreds-of-billions endpoint remains unmeasured. No full pod run was started.

## Prospective method and predictions

The RTX 3090 pod has approximately 31.13 CPU cores of cgroup quota and
124,999,999,488 bytes of cgroup RAM allowance. Host-wide hardware reports exceed
these allocations. Work in an isolated pilot directory; retain the live local
seed 9370001 trajectory and its original implementation.

For each phase/bank table and proposed next state s, compute the minimum CDF at
s across **all** 128 incoming states and the maximum CDF at s−1. A random u is
independent of incoming state exactly when

    max_incoming CDF[s−1] <= u < min_incoming CDF[s].

For s=0 there is no lower condition. Strict/non-strict comparisons match the
frozen searchsorted(side='right') rule. A reference-row inverse lookup proposes
s; the interval test certifies it. Uncertain draws use the original full CDF
and actual incoming state in the sequential CPU consumer. No tolerance is used.
The consumer also rechecks the bank mask, preserves the state checksum and
schedules any within-window event returns. The initial window uses the original
kernel. CPU OpenMP and CUDA versions implement the same proposal operation.

**Prediction before pilots:** most draws will be certifiable, because incoming
state CDF variation is small at this exposure. Transition evaluation should
accelerate substantially. The 100M/s complete-loop goal remains unproven:
CPU checksum dependencies, host/device transfer, RNG, history marking and
durable output can dominate after acceleration. GPU execution may lose to CPU
parallel execution when PCIe transfers cost more than the small lookup work.
Prefix throughput is expected to overestimate long-history throughput.

## Qualification and measurement

1. Run the frozen implementation for the 100M qualification seed 9369001 prefix.
2. Run CPU and GPU accelerated versions of that identical prefix. Compare every
   chunk's bank/emission/event hashes, complete terminal state, both RNG states
   and FP/FN counts against the retained reference (160 comparisons per run).
3. Measure complete-loop rate separately from proposal/consumer timings. Record
   first-window costs, fallback counts, thread counts and peak RAM. Repeat the
   promising configuration; test restart and current production seed equivalence.
4. Retain machine-readable pilot results and exact source hashes. Repeated
   replay exposure is not independent scientific evidence.
5. Report achieved rate honestly. Update this document before a new production
   launch; the current task ends with bounded pilots and a reviewable repo update.

Code: [isolated pilot harness](../experiments/u5-throughput/pilot.py). The frozen
`production/u5` package is not modified. Pilot checkpoints carry accelerator
hashes and cannot silently resume with a different accelerator implementation.

## Pipeline and memory

The first two 5M windows bootstrap the existing journal. Thereafter, two reusable
RNG/proposal buffers allow preparation of the next window while the CPU consumes
the current one. Bank marking, RNG generation and independent sieve preparation
overlap. The sieve's labels only enter grading after decisions; they have no
path into proposals, bank masks, hidden state or event creation. A separate
single writer compresses and fsyncs chunks and then atomically commits each
checkpoint, in order. Timed execution waits for its final durable write.

The exact time-order dependency is enforced: recent events cannot return before
twice their creation index. Early prefetch is fenced against its pending writer;
after step 4, the next window cannot depend on the pending writer's period range.
This early fence fixes a prefetch race found in an exploratory CPU stress run.
That failed trial is not a valid performance result. Final qualification includes
deliberately delayed fsync. A STOP or time-budget stop discards any unused
prefetched random draws; only the RNG states associated with committed decisions
are restored. An uncommitted future journal is quarantined on restart.

The 4 GiB decoded-event LRU is bounded. Newly generated actual-event arrays enter
that cache directly, avoiding compression/decompression round trips. The GPU
holds lookup data and reusable proposal buffers; the full 128-state source stays
available to the CPU fallback. There is no benefit to filling all 24 GiB VRAM
or all 116 GiB RAM with unused allocations. The pilot's RAM peak is reported
alongside its rate.

## Scientific predictions for a future run

The accelerator changes scheduling, not the gate's error model. Before a new
production launch, the frozen transition tables predict these conditional
three-reading error probabilities over all phases and incoming states:

| Bank condition | Wrong decision probability |
|---|---:|
| No returning bank: miss | 2.246–2.250 × 10⁻¹² |
| One returning bank: false emission | 7.629–8.059 × 10⁻¹³ |
| Both returning banks: false emission | 7.4841–7.4844 × 10⁻¹³ |

These are float64 matrix calculations retaining correlation between readings;
they are not three independent equilibrium draws. The no-bank result involves
subtraction near one and is rounded accordingly. Reproduce them with
`python experiments/u5-throughput/predict.py`; the retained
[machine-readable calculation](../evidence/u5-throughput/conditional_predictions.json)
identifies the exact source hash.

Until the first stream error, prime candidates have no returns and composites
have returns. The largest conditional hazard gives an approximate conservative
first-error union bound of 0.00225 over 1B decisions. Thus zero errors in a 1B
pilot is expected and provides little new accuracy evidence. After an error,
bank masks and emission ranks can diverge from the ideal history, so these
conditional numbers must not be extrapolated as an unconditional long-run rate.
Repeated replay pilots cover the same trajectory and are not independent trials.

## Reproduction on this pod

Use an isolated Python 3.12 environment with NumPy 1.26.4, g++ with OpenMP, and
CUDA 12.8 at `/usr/local/cuda`. The CUDA build currently targets the RTX 3090
(`sm_86`). No CuPy, PyTorch or alternative RNG is required. Allow 20 GiB free
disk for the runner's reserve. This pod's `/workspace` mount cannot execute its
old virtualenv, so executable pilot work is under `/tmp/prime-u5-throughput`;
final artifacts are archived separately for retention.

```bash
python scripts/reproduce_u5.py --workdir runs/frozen --chunks 200 \
  --workers 8 --seconds 300
taskset -c 64-95 python experiments/u5-throughput/pilot.py \
  --workdir runs/gpu-pilot --backend gpu --pipeline \
  --threads 8 --workers 8 --chunks 200 --seconds 120
python experiments/u5-throughput/compare_journals.py \
  runs/frozen runs/gpu-pilot
python experiments/u5-throughput/check_accelerator.py \
  runs/gpu-pilot/source --backend gpu
```

`--chunks` is the total number of 5M chunks, including existing checkpoints.
Use a new directory for a different accelerator version. The CPU alternative
uses `--backend cpu`; the same exactness and journal checks apply. For the frozen
100M reference, use `--chunks 20` and `scripts/check_u5_replay.py`. The separate
`stress_writes.py` entry point accepts the pilot arguments and deliberately
delays every fsync; it is for correctness testing, not throughput measurement.

## Limits before production

These are prefix pilots, not a benchmark at seed 9370001's live endpoint of
hundreds of billions. Long-history quotient planning, cache pressure, checkpoint
serialization and storage throughput can reduce the rate. A pod prefix result
does not establish a 100M/s rate at that endpoint. CPU affinity is fixed to
64–95 for final pod measurements, but the host is shared and rates can vary.

Accelerator checkpoints deliberately have their own implementation identity.
Migrating the moving workstation checkpoint requires a separately verified
snapshot, all referenced actual-event journals, and explicit migration tooling;
simply pointing this pilot at the live checkpoint is unsupported. No new full
production run or live checkpoint migration has been started by this work.
