# Production throughput diagnosis — 2026-10-03 UTC

The decline is principally a software scaling problem: history-bank preparation
grows with the candidate index, and every 5M decisions the writer serializes the
entire growing checkpoint record list. Python scheduling/GIL contention compounds
these costs. The GPU waits for preparation; resource exhaustion does not explain
the observed decline. A larger cache or faster disk alone will not restore 95M/s.

This investigation leaves the production implementation, RNG, checkpoints and
run controls unchanged. It reads existing timing logs and journals and runs
bounded component measurements on CPU cores 96–103, outside production's 64–95
affinity. Diagnostic writes go to a temporary directory under `/tmp`, not the
production directory or `/workspace`. Component results are not a new end-to-end
throughput qualification.

## Measured comparison

Each row summarizes 200 production chunks of 5M decisions. Times are milliseconds
per chunk. Stages overlap, so columns must not be added. Loop rates below use the
recorded loop timer, which excludes some setup and final drain; committed progress
is the authoritative operational rate.

| Candidate interval | Loop M decisions/s | History banks | GPU proposal call | Checkpoint/write stage | CPU consume |
|---|---:|---:|---:|---:|---:|
| 1–2B | 101.8 | 30.7 | 17.9 | 4.9 | 22.2 |
| 10–11B | 77.3 | 46.5 | 17.6 | 13.5 | 29.0 |
| 20–21B | 59.6 | 64.2 | 19.1 | 27.2 | 37.2 |
| 40–41B | 43.0 | 89.9 | 25.5 | 43.0 | 47.3 |
| 60–61B | 34.9 | 101.9 | 40.3 | 46.5 | 49.9 |
| 80–81B | 28.0 | 149.7 | 28.2 | 51.6 | 50.7 |
| 90–91B | 26.2 | 155.5 | 31.2 | 65.7 | 50.7 |

The diagnostic captured 95.055B committed decisions with FP=0, FN=0. The original
short pilots covered at most a 2B prefix; they did not qualify sustained speed at
this history size. A long-history qualification should have preceded extrapolation
of the approximately 100M/s prefix result.

## 1. History planning grows even when the data is in RAM

`History.banks()` in the frozen runner iterates quotient values from 2 through
approximately candidate_index / 5,000,000. It constructs Python range lists,
groups them by journal chunk, converts arrays and dispatches individual native
index calls. It rebuilds this plan for every window. Large-period marking remains
serial in `index.cpp`; only the small-period marking uses the accelerator's
OpenMP implementation.

Five warm-cache component repetitions at each endpoint measured:

| Endpoint | Total banks ms | Small-period marking ms | Native range marking ms | Python/dispatch remainder ms | Range calls |
|---|---:|---:|---:|---:|---:|
| 1B | 18.5 | 12.0 | 4.5 | 1.9 | 32 |
| 20B | 34.2 | 15.7 | 9.6 | 8.9 | 136 |
| 90B | 72.8 | 18.4 | 20.3 | 34.1 | 296 |

The remainder includes allocation and other wrapper work; it is not exclusively
Python arithmetic. A separate cProfile pass confirms the increasing loop/list/
min/max/array-construction activity. At 90B, the window required about 554.5MiB of
decoded actual history in this isolated cache; all timed repetitions were warm
and incurred no further misses or evictions. These are selected history chunks,
not the entire trajectory. Production's earlier 68.455B session likewise reported
zero cache evictions, just two misses, and about 21.3GiB cached.

The live pipeline's roughly 150ms bank time is substantially above this isolated
73ms result. That additional delay is consistent with thread/GIL contention and
overlap with other stages. Different affinity, host scheduling and measurement
conditions also matter; this experiment does not attribute the entire difference
to the GIL.

## 2. Full checkpoint serialization is avoidable growing work

`pipeline.py` copies the complete record list into every snapshot. The writer calls
`runner.atomic()` on that snapshot, which performs `json.dumps(..., sort_keys=True)`
before writing and syncing. The timing field named `durable_write` therefore
includes JSON encoding, allocation and thread delays, not just storage latency.

Five isolated repetitions, using a captured checkpoint and temporary output:

| Records | Encoded checkpoint bytes | JSON encode ms | Write + file/directory fsync ms |
|---|---:|---:|---:|
| 200 | 39,986 | 0.31 | 0.97 |
| 4,000 | 782,778 | 5.60 | 1.19 |
| 19,011 | 3,739,384 | 26.21 | 2.69 |

The encode consumed about 26.14ms of process CPU for 26.21ms elapsed at the largest
size. Standard CPython JSON encoding executes under the GIL, so the writer thread
can delay preparation and other Python work even though many CPU cores are free.
Native-call elapsed timers can also include delay reacquiring that GIL; a rising
`consume` or `proposal` timer does not establish that the native kernel itself
became that much slower.

Each batch is 5M decisions, so 26M decisions/s is about 5.2 batches/s.
At that rate a 3.74MB checkpoint causes roughly
19MB/s of repeated metadata writes. At the desired 100M decisions/s, the same
checkpoint would be serialized 20 times/s: approximately 75MB/s of repeated
metadata and 0.52 CPU-seconds/s of this encoding work alone. Its cost grows with
the number of journal chunks; cumulative metadata work is quadratic in chunk
count when every checkpoint includes the full history index.

## Resource evidence

A 10.23-second live sample measured 2.81 CPU cores used on average against a quota
of 31.13 cores, with zero new quota-throttling events. Cgroup memory was 32.5GiB
against a 116.4GiB limit. There were no memory-limit/OOM events and no observed
recent CPU, memory or I/O pressure. Swap use was zero in the earlier snapshot.
Five GPU samples showed 0–7% utilization, about 412MiB VRAM used, and 48°C. The
container had approximately 495GB free in the initial disk snapshot.

These measurements support software dependencies as the bottleneck, not lack of
CPU/GPU/RAM capacity. They do not exclude all effects from a shared host. The
decline was already present before archive rotation was activated, and production
had not accumulated its first 100GiB archive batch during this investigation.

## Proposed correction and qualification

1. Replace per-chunk full-index rewrites with an append-only authenticated commit
   journal and a small durable head containing sequence, next candidate, state,
   both RNG states, error totals and chain hash. Write full index snapshots
   periodically and at milestones. Recovery loads a snapshot, then replays only
   committed journal entries. Data must be durable before publishing its commit;
   recover or quarantine incomplete tails deterministically.
2. Use bounded RAM buffering and group commits. An initial design is a one-second
   flush target with a hard memory cap, for example 128MiB, whichever triggers
   first, plus forced flush on orderly stop and milestone. Backpressure must bound
   memory if storage stalls. A crash resumes from the last durable commit and
   recomputes the uncommitted suffix from the saved RNG/state. The time target is
   not a hard recovery bound under storage stalls. Report durable progress
   separately from speculative in-memory work. The 100GiB T500 archive interval
   remains separate from this much more frequent local durability interval.
3. Move quotient planning/range assembly into native code and batch native index
   dispatch. Evaluate incremental planning and parallel marking with disjoint
   output partitions or safe private masks. Preserve actual-event rank parity,
   arbitrary event histories and the existing feedback semantics. Additional RAM
   should support reusable plans/buffers, not simply a larger unused event cache.
4. Isolate compression/metadata serialization from the decision process where
   beneficial, using bounded queues. Update reporting, archive manifests and
   restore tools together with the new journal format. Pin the new implementation
   identity and qualify checkpoint migration explicitly.
5. Benchmark from a verified mature-history snapshot, not candidate 2. Compare
   events, bank hashes, hidden state, both RNG states and errors against the
   current implementation; test interrupted writes, restart, milestone reports
   and archive restore. Then run an end-to-end sustained pilot near and beyond
   the current endpoint before accepting 95M/s.

At 95M/s, a 5M batch has a 52.6ms end-to-end budget. Isolated current bank work
already costs about 73ms at 90B, before its dependent GPU proposal call. Removing
checkpoint serialization alone cannot meet the target. Both changes are needed;
the measurements do not yet establish what their combined sustained rate will be.

Evidence: [component timings and profiles](../evidence/pod/THROUGHPUT_DIAGNOSTIC_20261003.json),
[resource sample](../evidence/pod/THROUGHPUT_RESOURCES_20261003.json), and
[reproducible diagnostic](../scripts/diagnose_pod_throughput.py).
