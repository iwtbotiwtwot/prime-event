# Incremental checkpoint and native history redesign

Implementation date: 2026-10-03 UTC. This implements the changes motivated by the
[production timing analysis](pod-throughput-analysis.md). The production migration
boundary is **112,875,000,000 decisions**, seed **9370001**, FP=0, FN=0.
The candidate order, actual-event history, three readings, hidden state,
PCG64 streams, frozen tables and error scoring are retained. This is continuation
of the existing trajectory, not a new seed or independent accuracy exposure.

## Implementation

`native_history.cpp` constructs the actual-event quotient plan in C++, gathers
the same journal ranges, and marks large-period returns in parallel using private
thread masks. A disjoint blocked OR reduction combines those masks. Small-period
marking keeps disjoint destination intervals. No primality labels enter bank
preparation. Scratch masks are reused across windows rather than allocating tens
of megabytes each time. The implementation respects the number of threads
actually supplied by OpenMP when merging masks.

When the complete decoded history fits within 80% of the configured 64GiB cache,
restart authenticates and decodes that history with eight workers and at most
16 pending loads. This removes on-demand decompression from the initial mature
run. Larger histories fall back to the bounded LRU; future cache pressure can
still lower performance. RAM restoration is reported as `RESTORING` with chunk
counts and does not advance the durable decision counter. This startup work is
included in the pilot's complete-session rate and reported separately so that a
steady running rate cannot be mistaken for a rate including restart.

The writer compresses individual 5M-decision NPZ journals in memory. It flushes
on any of: 20 pending journals (100M decisions), 128MiB pending compressed bytes,
or one second elapsed as checked when a journal is added. Early windows flush
individually to preserve short-range feedback dependencies. Graceful stop and
milestone exit force a flush. There is only one writer task in flight; slow
storage applies backpressure rather than growing an unbounded queue. The flush
time is a scheduling target, not a guaranteed maximum under stalled storage.

The numerical consumer and speculative GPU proposal kernel are unchanged. The
writer remains a thread; the large per-batch Python JSON encoding that blocked
other Python threads has been removed rather than moved to another process.

## Durable commit and recovery

For each group, the writer:

1. Writes and fsyncs immutable journal files, renames them, then syncs the data
   directory. Per-file fsync is retained; only checkpoint/index commits are
   amortized across the group.
2. Appends one record to `data/COMMITS.jsonl`, including the new journal records,
   terminal hidden state, both RNG states, next candidate and cumulative error
   counts. Each record links to the SHA-256 of its predecessor. The append is
   fsynced before publication.
3. Atomically publishes and syncs `data/HEAD.json`: committed byte offset, hash
   and journal sequence. Only then does committed progress advance.

`CHECKPOINT.json` is a full recovery snapshot, rewritten after approximately
1,000 new journals (5B decisions), and at orderly stop or milestone boundaries.
Live readers must use `journal.load(data)` or the committed `PROGRESS.json`;
reading `CHECKPOINT.json` alone may give an older boundary.

Recovery loads the full snapshot and authenticates the append-only suffix
through exactly the published HEAD. It ignores unpublished bytes, truncates the
unpublished tail only while holding the writer lock, and quarantines journal
files beyond the recovered boundary. Uncommitted work is recomputed from the
last durable RNG/state pair. Full snapshots do not truncate the append-only log,
so concurrent archive readers can safely finish reading their selected HEAD.
The commit log is small incremental metadata and continues to grow.

The migration tool requires the exclusive writer lock, records the old and new
implementation identities, saves the previous full checkpoint, and changes only
the pinned accelerator implementation files. The frozen scientific hashes and
terminal trajectory fields are retained. The original executable deployment is
also preserved on the pod for qualification and rollback investigation; do not
run an old implementation directly against a new incremental journal.

## Reports and T500 archives

The 100B controller reports remain exact durable boundaries because orderly
pilot completion flushes and writes a full snapshot before the controller reads
it. Original campaign start time and earlier milestone records are retained;
the migration pause remains included in campaign wall-clock averages.

The archive helper resolves the current durable HEAD and materializes a full
standalone checkpoint for the archive. It removes the live journal-offset field
from that exported snapshot, so restoration from the archive starts a new
incremental log and does not require the pod's historical `COMMITS.jsonl`.
All required event files, earlier incremental archive batches and numerical
source files remain necessary for restoration.

The existing policy remains: each 100GiB of new compressed NPZ journals triggers
a container-staged archive, transfer to the T500, archive and member verification,
then removal of the staged container archive and covered redundant copies.
Active feedback journals remain on the container. Drive upload and T500 deletion
remain manual. Nothing is backed up to `/workspace`.

## Qualification and measurement

Required before production migration: mature-history suffix comparison with
the original implementation; arbitrary-event bank-mask comparison; published and
unpublished journal corruption/recovery tests; forced process-kill and exact
restart comparison; archive materialization from a HEAD newer than the full
snapshot; controller milestone and orderly-stop checks. Measurements and final
production observations are retained in `evidence/pod/REDESIGN_QUALIFICATION.json`.

Completed qualification before activation:

| Check | Result |
|---|---|
| Mature 112.875B checkpoint, next 500M decisions vs original | 1,300 metadata comparisons passed; all event hashes and RNG/state fields matched |
| Final mature pilot | 2B decisions, FP=0, FN=0 |
| Arbitrary non-prime event histories | Four windows, 20M mask bytes identical to frozen index |
| Forced kill, unpublished work, injected orphan, restart | Full 1B journal matched original; 2,600 comparisons; orphan quarantined |
| Controller restart/milestone smoke test | Two exact 250M milestones; 500M total; zero errors |
| Repository tests | Six passed, including incremental-log failure gates and archive HEAD materialization |

The mature pilot spent 99.18 seconds authenticating/restoring RAM history. Total
session time was 120.62 seconds (16.58M/s including that restoration). The
remaining 21.44 seconds delivered 2B decisions, about 93.29M/s including other
startup/finalization costs. The recorded loop averaged 95.36M/s after the first
100M, and 96.23M/s over its final billion. These loop measurements establish a
promising configuration; resumed production committed progress is the final
operational measurement. Two exploratory implementation failures were corrected
before the final qualification and are recorded in the evidence file.

Production resumed at **2026-10-03T02:01:59Z** from the preserved 112.875B boundary.

The target remains 95M decisions/s or better, measured on committed progress.
Short-prefix throughput, GPU-only rates, cache-restoration time and warm running
rates must be identified separately. Qualification replay repeats existing
exposure and is not additional independent scientific evidence.
