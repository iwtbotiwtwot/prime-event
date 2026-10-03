# Three GPU roles and resumed production

**Final status: the owner stopped the pod at 8T decisions, FP=3 / FN=0,
on 2026-10-03 at 16:49:18 UTC.** The final 100B averaged 155.41M/s.
[Final checkpoint and archived data](pod-eight-trillion.md). The deployment
measurements below are historical; the later memory qualification reduced the
host history cache from 192 GiB to 16 GiB as described in
[production controls](pod-production.md).

Production resumed on **2026-10-03 at 07:36:16 UTC**, on
**216.81.151.70:12771**, continuing seed **9370001** from
**1,264,250,000,000 decisions**, FP=0, FN=0. The measured running rate was
**297.916M committed decisions/s** over two minutes. The subsequent complete
**1.3T–1.4T interval averaged 295.131M/s** over 338.833 seconds, with zero errors
at both exact milestones.

[Current commands and resources](pod-production.md) ·
[100B milestone reports](pod-run.md) ·
[Activation receipt](../evidence/pod/gpu-roles-20261003/GPU_ROLES_ACTIVATION.json) ·
[Live measurement](../evidence/pod/gpu-roles-20261003/GPU_ROLES_LIVE_THROUGHPUT.json).

## Division of work

| Resource | Work | Scheduling or cache |
|---|---|---|
| GPU 0 | Speculative proposals from model, random buffers and bank masks | Native Blackwell `sm_120` |
| GPU 1 | Actual-history bank marking | 16 GiB compact event payload cache, protected LRU |
| GPU 2 | Stable event extraction and independent error grading | Pinned staging buffers; integer counts |
| CPUs | Ordered state consumption and rolling hash; exact PCG64 draws; history planning, authentication and decoding; independent truth generation; compression and durable writes | Eight accelerator threads, eight RNG/decode workers, twelve history threads |
| Host RAM | Decoded uint32 offsets into authenticated event chunks | 192 GiB bounded cache |

The host has three RTX PRO 4500 Blackwell Server Edition GPUs, each with
32,623 MiB VRAM, and two EPYC 9335 processors. Its measured cgroup allowances
are 40.8 CPU equivalents and 281,999,998,976 bytes of memory (262.63 GiB).
Default CPU affinity replaces the former pod's 64–95 mask. CUDA 12.8 and NumPy
1.26.4 are used. [Hardware observation](../evidence/pod/gpu-roles-20261003/HARDWARE_AND_FINAL_STATE.json).

The CPU planner scans the oldest four history records directly, enumerates
quotient ranges for later records, and reuses monotonic search bounds. Stored
offsets use four bytes per actual event. The GPU history implementation receives
those authenticated offsets and exact record ranks; it ORs bank bits using
packed atomic words, tiled small-period returns, direct early-record scans and
warp-level range searches. No primality labels enter that stage.

GPU grading receives the gate's completed emission bits and independently
generated truth. Stable compaction preserves event/error order and integer
reductions preserve FP/FN counts. The oracle scores decisions and never supplies
feedback events. The numerical CPU consumer and scientific tables are retained.
Proposals select their CUDA device on every worker-thread call; portable host
registration permits separate CUDA roles without relying on a thread's previous
device selection.

## Fair replay comparison

Each variant replayed the same final 15B decisions of the paused trajectory,
with an identical full eligible history prefix in RAM and no host decode misses.
The shared 93.28-second history preload is excluded from processing rates.
All 3,000 chunks per variant matched production science, including event hashes,
bank/emission masks, state, RNG streams, ordering and error totals.

| Variant | Processing M decisions/s | Gain over baseline |
|---|---:|---:|
| GPU proposals, CPU history and grading | 255.483 | Baseline |
| Add GPU 2 grading | 292.871 | 14.63% |
| Add GPU 1 history | 303.005 | 18.60% |

The additional history role improved the grading variant by 3.46%; the larger
benefit came from reducing serial grading time. These were finite replays of
existing exposure, not new independent accuracy experiments or an overnight
throughput guarantee.

[Replay results](../evidence/pod/gpu-roles-20261003/GPU_ROLES_REPLAY.json) ·
[Prototype source and binary qualification](../evidence/pod/gpu-roles-20261003/GPU_ROLE_QUALIFICATION.json).
Standalone grading covered 24 small/boundary cases, full windows and ten injected
errors. History marking covered early and mature positions, arbitrary composite
histories and range boundaries. A forced 1 GiB device cache exercised 550 exact
evictions. These fixtures establish that raw feedback is not replaced with a
prime-only shortcut.

## Packaged runtime qualification and migration

The actual production CLI was compiled on the replacement host and checked
separately from the prototype. Before migration it passed:

- Frozen 100M prefix: 160 reference comparisons, zero errors.
- Mature suffix: 400 committed chunks / 2B decisions, 5,200 metadata comparisons
  against the paused production trajectory, with matching terminal RNG/state.
- Forced process kill after 83 durable chunks, injected orphan and restart:
  full 200-chunk / 1B journal matched the CPU control, with 2,600 comparisons;
  the orphan was quarantined.
- Repository checks: eight tests, including durable journal recovery, archive
  verification and migration refusal without STOP, exclusive locks or matching
  qualification. Published journal suffixes, RNG state and HEAD survive migration.

[Packaged qualification](../evidence/pod/gpu-roles-20261003/INTEGRATION_QUALIFICATION.json).
The replay runner is `experiments/u5-throughput/qualify_gpu_roles.py`; specify
`--production`, a new `--workdir`, and the same GPU assignments and CUDA target.
Its qualification pins all thirteen runtime source files.

The prior pod transfer authenticated all 252,850 committed chunks and
61,683,559,466 bytes across 270,991 regular files, preserving original absolute
paths. The paused full checkpoint SHA-256 was
`e5ea1d2b8d113d8e0387c413b42827fb37dc6d29a8b51390720c5ae0fffa31a6`.
[Transfer verification](../evidence/pod/gpu-roles-20261003/TRANSFER_VERIFIED.json).
The replacement has all required state; the old pod can be shut down.

Activation saved the previous code, materialized sources, checkpoint and
scheduling state under
`/root/prime-u5-production/GPU_ROLES_ACTIVATION_20261003T073614Z`.
The migration tool changed accelerator identity, GPU assignments and the RAM
cache allowance while preserving all other configuration, history descriptors,
terminal state, RNG streams, FP/FN and the exact durable HEAD. The detached
controller then resumed with closed stdin and redirected logs. It survives SSH
disconnection and workstation restart. STOP remains the graceful pause mechanism.

## Production measurement

From **07:38:18 to 07:40:18 UTC**, durable HEAD advanced from
**1,271,050,000,000** to **1,306,800,000,000** decisions:
**35.75B in 120.0002 seconds**, or **297.916M/s**. The four 30-second intervals
ranged from **296.287M/s to 299.559M/s**. The authenticated state resolved after
measurement had **1,306,900,000,000 decisions**, FP=0 and FN=0.

This uses published commit sequences and monotonic elapsed time, including
compression, durable flushes and periodic full checkpoint snapshots. It excludes
the preceding history restoration and transfer pause. The 1.3T milestone's
**13.38M/s** interval includes that long pause; it is not the resumed running rate.
The first session-average progress readings also include restoration.

The next complete 100B milestone interval ran from **07:39:55 to 07:45:34 UTC**:
**100B in 338.833 seconds = 295.131M/s**, FP=0 and FN=0 through 1.4T. The same
worker stayed running across both boundaries, retaining its caches. This longer
production interval includes durable snapshots, ongoing GPU-cache evictions and
normal milestone publication, and exceeds the requested 100M/s target.
[Exact milestone records](../evidence/pod/milestones.json).

The final memory sample was **158.87 GiB of 262.63 GiB**, including page cache.
No CPU throttle, OOM or memory-limit events occurred. Host history held about
93.03 GiB with zero misses or evictions in the recent sample. GPU history had
reached its 16 GiB payload cap and exercised 13,752 evictions while retaining the
measured rate. Its total CUDA footprint was about 21.21 GiB, including allocation
overhead; the payload cap is not a cap on total device memory.

Recent mean stage times per 5M window were consumption 14.50 ms, compression
10.28 ms, history 8.30 ms, RNG 6.18 ms, proposals 4.93 ms and grading 1.22 ms.
Stages overlap, so these times cannot be added to derive end-to-end throughput.
Ordered consumption/hash remains the largest serial stage. The GPU cache still
uses the authenticated host cache, and increasing history or disk use can
eventually change throughput. The two-minute result establishes the current
running rate; longer operation remains visible through retained 100B milestones.

`scripts/measure_pod_throughput.py --seconds 120 --interval 30` reproduces this
measurement on the pod. Reporting and archive tools now share the replacement
endpoint and use an explicit unattended SSH identity. The existing 100 GiB
archive threshold, verified T500 transfer and retention policy continue.
