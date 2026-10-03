# Continuous pod run and 100B reports

**Final status: intentionally stopped at exactly 8,000,000,000,000 decisions
on 2026-10-03 at 16:49:18 UTC (11:49:18 Chicago), with FP=3 / FN=0.**
The final 100B averaged 155.41M/s. The STOP file is present; the controller and
worker have exited. [Final result and archive custody](pod-eight-trillion.md).
The deployment and operating history below document how this endpoint was reached.

Authorized October 2, 2026 Chicago. The pod trajectory started **seed 9370001
at candidate 2 with empty history**, using the frozen raw u5 source. It is a
separate execution of the workstation seed, not an independent-seed accuracy
experiment. On October 3 its paused state at **1,264,250,000,000 decisions**
was transferred intact to the replacement pod at **216.81.151.70:12771**.
All 252,850 committed chunks were authenticated; the old pod is no longer
required. The workstation trajectory remains separate.

The replacement has three **RTX PRO 4500 Blackwell Server Edition** GPUs,
about 31.86 GiB VRAM each, dual EPYC 9335 CPUs, a **40.8 CPU** cgroup quota,
and a **262.63 GiB** memory limit (282 GB decimal). These measured limits
govern scheduling despite the advertised 48 CPU allocation. CUDA 12.8 builds
for **sm_120**. Default CPU affinity is used on this host; the previous
64–95 mask selects SMT siblings here and is not reused.

GPU 0 generates speculative proposals; GPU 1 marks bank masks from authenticated
actual-event history with a **16 GiB** device cache; GPU 2 extracts events in
order and scores errors. CPUs retain ordered state consumption and the rolling
hash, exact PCG64 streams, authenticated history decoding, independent reference
generation, compression and the sole durable writer. There are eight RNG/decode
workers, eight accelerator CPU threads, and twelve history-planning threads.
The bounded host history cache is now **16 GiB** (`16384 MiB`), replacing the
earlier 192 GiB allowance. GPU-resident authenticated records are reused without
decoding duplicate host copies. The host cache holds recently needed uploads
and the tiny-period search record; immutable event journals remain on disk.

The [GPU role qualification and activation record](pod-gpu-roles.md) documents
the comparison, restart check and resumed-production measurement. Frozen tables,
decision rules, random streams, raw event history and error semantics are retained.

The [incremental checkpoint/native history redesign](pod-throughput-redesign.md)
continues this trajectory from 112.875B. Live durable state is now resolved from
`CHECKPOINT.json` plus `COMMITS.jsonl` through `HEAD.json`; the full checkpoint
alone can lag between snapshots. RAM restoration is visible as `RESTORING`
before resumed decisions advance. Milestone and archive tools use durable state.

## Reports

[100B milestone report](pod-run.md) · [Machine-readable records](../evidence/pod/milestones.json)

At **100B, 200B, 300B, and every subsequent 100B committed decisions**, the
controller records UTC observation time, cumulative and interval false events
and missed primes, interval decisions/s, cumulative decisions/s, and the exact
checkpoint hash. Rates use elapsed wall time, including setup, restarts and
pauses; they are not sums of overlapping pipeline timings. Scoring remains
independent of generation. No repair, correction, learner or oracle veto is used.

The workstation's `prime-event-pod-report.timer` polls every minute and publishes
each newly retained milestone to GitHub, then sends a desktop notification.
Network/workstation outages delay publication; milestone records remain on the
pod with their actual observation times. Reports do not depend on this chat
remaining open. Publication shares the existing hourly publisher's lock and
never overwrites unrelated dirty changes. Failed publication retries next minute.

The 97.6–101.1M/s prefix pilots are not a guarantee at larger endpoints. The
100B reports measure actual long-history throughput, including any degradation.

## Execution and retention

Controller: `experiments/u5-throughput/campaign.py` in
`/tmp/prime-u5-throughput` on the pod. Python environment:
`/tmp/prime-u5-venv/bin/python`. Active data and logs:
`/root/prime-u5-production`. `CAMPAIGN.json` identifies the controller;
`data/PROGRESS.json` refreshes every 100M committed decisions. The controller
continues across 100B boundaries and clean daily time-budget exits, retaining
the same checkpoint, seed, source identity and random streams. The detached
process survives SSH disconnection. STOP, low storage, or a failed child ends
execution; failures are not silently retried. No active feedback history is deleted.

Checkpoint writes use the pod's fast container disk with a 20 GiB free-space
reserve. The later requested [100 GiB archive policy](pod-archives.md) replaces
per-milestone duplicate journal copies and the old five-minute individual-file
transfers. The timer now checks the archive threshold every five minutes.

At least **100 GiB = 107,374,182,400 bytes** of newly committed NPZ journals
triggers a compressed archive on **container disk**, under
`/root/prime-u5-backup/archives`. It is downloaded to the **T500**, under
`/home/sam/mnt/lilhelper-t500/POD_BACKUPS/prime-event/u5_seed9370001_20261003/archives`.
The archive checksum and every member checksum must verify, and a durable receipt
must be written, before the container archive and covered redundant backup copies
are removed. The user uploads to Drive, verifies, then manually removes the T500
archive. No automatic Drive upload or T500 deletion is configured.

**Active event-history journals remain on the container.** They are required for
exact feedback and restart; a checkpoint or finite RAM cache does not replace
them. This policy rotates backup/export copies, not the live scientific working
set. It therefore does not make container storage consumption bounded forever.
The archive activation used a clean checkpoint-preserving controller restart;
the seed, source, state and RNG streams were retained.

**This production run does not use `/workspace` for backups.** Archives contain
incremental journals, numerical sources, a manifest and a checkpoint. Restore all
preceding batches and original absolute paths before resuming. The T500 mount and
a 20 GiB reserve are required; there is no silent workstation-disk fallback.
Transfer failures never authorize cleanup and retry on the next timer invocation.
The workstation and T500 network mount must be online. Earlier verified loose
T500 snapshots are retained; their files are not automatically removed.

### Storage cleanup on October 3

The requested 4 TB container resize was held while inspecting redundant data.
Runpod's [storage documentation](https://docs.runpod.io/pods/storage/types)
states that editing a running pod resets its container and erases files outside
`/workspace`. Only read-only API queries were made; no disk update, pod reset or
stop was submitted. The temporary API credential file was removed after those
queries. Production and its journals remain on the original container disk.

Twenty completed qualification, pilot and build directories contained **9.66 GiB
of unique file blocks**. A complete archive was compared against all original
contents and metadata, copied to the T500, and checked by SHA-256 before the
directories and their temporary container archive were removed. The active
controller, environment, materialized source, live journals and the current
memory/error qualification directory were retained. The archive is at
`POD_BACKUPS/prime-event/u5_seed9370001_20261003/cleanup-20261003/completed-experiments.tar.zst`
on the T500 and retains the original directory paths.
[Completed-experiment cleanup receipt](../evidence/pod/storage-cleanup-20261003/CLEANUP_RECEIPT.json).

Production batch 1 occupied **99.53 GiB** of container staging space. Its T500
copy passed the archive SHA-256, manifest SHA-256, sizes and checksums of all
**504,646 members**, complete member-set validation and decompressor exit check.
The unmodified repository verifier ran directly on lilhelper to avoid reading
the archive twice through SSHFS. The copy and verification receipt were made
durable before the existing pod archive acknowledgement removed the container
archive. The **504,621 live event journals** covered by this batch remain on the
pod; cleanup removed zero active journals. The backup timer was restored.
[Production archive verification and cleanup](../evidence/pod/storage-cleanup-20261003/PRODUCTION_ARCHIVE_CLEANUP.json).

At **09:39:06 UTC**, container storage used **126.50 GiB of 500 GiB**, leaving
**373.50 GiB free**. The same production controller and worker remained running,
at **3,012,105,000,000 decisions**, FP=3/FN=0. Cleanup reduces redundant storage;
the live journal still grows and remains subject to the 20 GiB free-space reserve
and the 100 GiB backup staging policy. No existing T500 backups were deleted and
no automatic Drive upload was added.

The **09:39:07–09:40:07 UTC** check committed **14.7B decisions in 60.00388
seconds = 244.984M/s**. Each 15-second interval stayed between **239.98 and
259.98M/s**. It ended at **3,026,805,000,000 decisions**, FP=3/FN=0,
**372.92 GiB free disk**, and **57.99 GiB total container RAM** (**28.92 GiB
anonymous**, **27.37 GiB file cache**). All memory-limit/OOM events remained zero
and controller/worker PIDs were unchanged throughout.
[Post-cleanup production measurement](../evidence/pod/storage-cleanup-20261003/POST_CLEANUP_PRODUCTION.json).

Clean stop on the pod:

```bash
touch /root/prime-u5-production/data/STOP
```

The controller honors that file and does not remove it. Stop publication only:

```bash
systemctl --user disable --now prime-event-pod-report.timer
```

Inspect publication:

```bash
journalctl --user -u prime-event-pod-report.service -n 30
cat ~/.local/state/prime-event-pod/latest.json
```

Live progress in the pod web terminal:

```bash
python3 /tmp/prime-u5-throughput/scripts/pod_progress.py --watch 2
```

This shows committed decisions, FP/FN, throughput in **M decisions/s**, and
container memory. The latest commit-group rate appears immediately; an observed
rolling rate builds over 30 seconds, smoothing checkpoint/flush variation.
Ctrl+C stops the viewer while production continues. `--json` emits numeric
`throughput_m_per_second` and `measured_throughput_m_per_second` values; omit
`--watch` for a single sample. These running rates exclude the restoration
period, which has its own progress display.

On **2026-10-03 at 08:12 UTC**, container memory reached **223.32 GiB**,
including **85.72 GiB** of file cache and **136.26 GiB** of anonymous application
memory. A container-scoped `memory.reclaim` request freed **47.98 GiB** in
**0.975 seconds**, reducing total use to **175.34 GiB** while the same worker
continued committing with FP=0, FN=0. The receipt is
`/root/prime-u5-production/MEMORY_RECLAIM_20261003T081203Z.json`.
The [retained reclaim receipt](../evidence/pod/memory-20261003/MEMORY_RECLAIM_20261003T081203Z.json)
records memory categories, errors and continued committed progress before/after.

`scripts/pod_memory_guard.py --watch 30` checks container headroom and file cache.
Below **32 GiB** headroom or above **48 GiB** file cache, it requests at most
**16 GiB** of file-cache reclaim per check, aiming for **48 GiB** headroom and
**32 GiB** file cache, while budgeting at least **8 GiB** of clean unmapped cache.
It uses the container's
[`memory.reclaim` interface](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory)
with `swappiness=0` where supported. This pod's older kernel rejects that optional
flag, so the guard uses the plain reclaim interface only after verifying there
is no swap route (a zero cgroup swap limit or no active host swap). The successful
08:12 one-time reclaim also used that compatibility path. Unsupported requests
are retained as errors if a no-swap condition cannot be verified. The guard does
not lower the memory limit or apply `memory.high`
throttling. Kernel reclaim amounts can differ from the request, and ongoing
allocations can reduce the headroom observed afterward. The guard retains
application buffers, decoded history, GPU state and all journal files. It does
not change pinned numerical sources, and it exits when the campaign ends.
Status and reclaim receipts are retained in `MEMORY_GUARD.json`; guard events
appear in `memory-guard.log`. File cache can grow again between checks.

The initial file-cache reclaim left the earlier **192 GiB** decoded-history
allowance in place. The rolling-cache deployment below replaces that allowance.
Flushing file cache does not make the live journal storage footprint bounded.

After guard activation, **08:18:24–08:19:09 UTC**, the same worker committed
**12.1B decisions in 45.00194 seconds = 268.877M/s**, FP=0, FN=0. End memory
was **191.21 GiB of 262.63 GiB**, leaving **71.42 GiB** headroom; OOM/limit
events remained zero and memory-pressure averages were zero. The host history
payload shortly before this measurement was **135.62 GiB**, with about
**7.06 GiB** of other anonymous memory. This is a bounded post-reclaim observation,
not an unlimited-runtime guarantee. At activation the guard correctly requested
no further reclaim because headroom was adequate.
[Post-reclaim production measurement](../evidence/pod/memory-20261003/MEMORY_GUARD_THROUGHPUT_20261003.json).

## Rolling RAM history and bounded diagnostics

Production paused cleanly at **2,338,420,000,000 decisions**, FP=1, FN=0, for the
qualified rolling-cache deployment. The previous code and scheduling state are
saved under `/root/prime-u5-production/MEMORY_ACTIVATION_20261003T084348Z`.
Migration retains durable HEAD, all actual event records, hidden state, seed,
PCG64 streams and error counts; it changes implementation identity and cache
scheduling. The detached controller resumed with **16 GiB host cache** and the
same **16 GiB GPU cache**, three GPU roles and CPU worker allocation.

GPU history now reads host offsets only for records requiring a device upload
and for the small-period host search. Resident device payloads were authenticated
on upload and remain immutable. The GPU eviction order and complete required
record set are retained. Restart preloads the current upload working set and
64-window lookahead, rather than filling RAM with an older history prefix.

The host cache uses LRU eviction and can shrink below its 16 GiB configured cap
when container anonymous/kernel memory grows. Every 128 preparation calls it
charges non-cache overhead first and reserves up to **48 GiB** for buffers and
checkpoint work. CPU history uses the same allowance rule. Evictions discard
decoded copies only; future requests authenticate and decode the retained journal.

All new timing records stream to `TIMINGS.jsonl`. Only the last **1,024** remain
in RAM and in a session's `rows` summary. Summaries explicitly record total and
retained row counts, `timing_rows_scope`, and the complete timing-file path.
Event journals, hashes, RNG state and cumulative errors are retained in full.
The journal descriptor catalog still grows; cache budgeting accounts for its
memory. If anonymous plus kernel memory reaches the **24 GiB checkpoint reserve**,
the independent memory guard requests STOP for an orderly checkpoint pause.
It does not silently resume that pause or delete history. Storage continues to
grow under the existing archive policy.

The workstation's stopped u5 runner used an **8 GiB** runtime decoded-history
cache (its original checkpoint identity retains `cache_mib: 4096`), demonstrating
that a full event history does not require a full decoded RAM copy. A rolling
cache may contain very old events that are needed again: a fixed cutoff that
deletes all older event history would change the scientific bank masks.

Qualification retained the frozen 100M prefix (160 comparisons), the final
**6B decisions** of the paused trajectory (15,600 metadata comparisons), and
forced process-kill/restart with an injected orphan (2,600 comparisons). The
1,200-chunk mature replay retained all 1,200 timing rows on disk and only 1,024
in its summary. With a **4 GiB** host cache it used **6.512 GiB peak process RAM**,
restored its upload working set in **1.372 seconds**, and averaged **186.695M/s**
including setup, restoration and finalization. These are retained replays, not
new independent accuracy exposure.
[Runtime qualification](../evidence/pod/rolling-cache-20261003/INTEGRATION_QUALIFICATION.json)
and [memory/retention checks](../evidence/pod/rolling-cache-20261003/MEMORY_QUALIFICATION_ADDITIONAL.json).

The first production false event was **2,274,828,165,298**, recorded before this
deployment. Its 1B surrounding replay matches 2,600 metadata comparisons,
including the error, subsequent hidden state and RNG streams. It remains an
observed raw false event; no repair, correction, learner or oracle veto is used.
The cumulative count at activation is FP=1, FN=0.

The second false event was **2,379,059,006,438**, after activation. Independent
CPU proposal, history and grading replays around **each** error reproduce the
production result, hidden state and RNG streams: **1B decisions and 2,600
metadata comparisons per replay**. The first replay ends FP=1/FN=0 and the
second retains the preceding error and ends FP=2/FN=0. These checks found no
decision change attributable to GPU execution, rolling cache or restart.
[First CPU replay](../evidence/pod/rolling-cache-20261003/CPU_OBSERVED_ERROR_QUALIFICATION.json)
and [second CPU replay](../evidence/pod/rolling-cache-20261003/SECOND_CPU_OBSERVED_ERROR_QUALIFICATION.json).

The third false event, **2,687,315,963,345**, also reproduces in a 1B independent
CPU replay with all **2,600 metadata comparisons** matching. This replay retains
the preceding two errors and ends FP=3/FN=0. It is an odd composite, unlike the
first two; the even-readout diagnostic below concerns those first two events.
[Third CPU replay](../evidence/pod/rolling-cache-20261003/THIRD_CPU_OBSERVED_ERROR_QUALIFICATION.json).

A floating matrix evaluation of the unchanged frozen CDF assigns a positive
probability, approximately **7.5–8.1e-13**, to three even readouts for the
phases of these two even composites in nonzero history banks. This is a
conditional table diagnostic, not a certified error-rate bound or independent
accuracy exposure. The raw model can therefore accept an even composite;
the two recorded errors are preserved.
[Frozen-table diagnostic](../evidence/pod/rolling-cache-20261003/GATE_COMPOSITE_ACCEPTANCE.json).

At **09:13:37–09:14:37 UTC**, production committed **14.6B decisions in
60.00208 seconds = 243.325M/s**, with FP=2/FN=0 throughout. The four 15-second
intervals were **233.3–253.3M/s**. End container memory was **67.87 GiB**,
including **26.04 GiB anonymous RAM** and **40.07 GiB file cache**; all OOM
and limit-event counters remained zero. A T500 backup transfer ran concurrently.
The 16 GiB host cache remains bounded while file cache varies with I/O and guard
reclamation. This observation is not a guarantee for every future endpoint.
[Live measurement](../evidence/pod/rolling-cache-20261003/ROLLING_CACHE_THROUGHPUT_20261003.json).

The existing progress command now separates application RAM, file cache and
headroom. Restart only the viewer to display the added values:

```bash
python3 /tmp/prime-u5-throughput/scripts/pod_progress.py --watch 2
```

The separate guard is detached from SSH. Its command is:

```bash
nohup python3 /tmp/prime-u5-throughput/scripts/pod_memory_guard.py --watch 30 \
  </dev/null >>/root/prime-u5-production/memory-guard.log 2>&1 &
```

An exclusive `MEMORY_GUARD.lock` prevents duplicate guards. This is a separate
operational helper; the production controller command below remains the same.

Current campaign command (do not run a second writer against an active root):

```bash
nohup env OPENBLAS_NUM_THREADS=1 /tmp/prime-u5-venv/bin/python \
  /tmp/prime-u5-throughput/experiments/u5-throughput/campaign.py \
  --root /root/prime-u5-production --mirror /root/prime-u5-backup \
  --seed 9370001 --cache-mib 16384 \
  --threads 8 --workers 8 --history-threads 12 \
  --proposal-gpu 0 --history-gpu 1 --grade-gpu 2 \
  --gpu-cache-mib 16384 --cuda-arch sm_120 \
  </dev/null >>/root/prime-u5-production/campaign.log 2>&1 &
```

The controller is launched with a detached session, redirected logs, and closed
stdin. It survives disconnecting or restarting the workstation. Before changing
a paused runtime, `scripts/migrate_pod_checkpoint.py` requires STOP, both exclusive
locks, and a replay qualification matching the new sources and GPU assignments.
It backs up the checkpoint and scheduling state, then changes runtime identity
and cache scheduling while preserving every trajectory field and durable HEAD.
Remove STOP only when explicitly resuming the prepared configuration.

The report and archive tools share the new endpoint. Optional environment
overrides are `PRIME_EVENT_POD_HOST`, `PRIME_EVENT_POD_PORT`, and
`PRIME_EVENT_POD_IDENTITY`; the unattended default identity is
`~/.ssh/id_ed25519_runpod`. Private keys are never transferred to the pod.
