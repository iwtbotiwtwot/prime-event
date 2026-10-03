# Continuous pod run and 100B reports

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
The bounded host history cache is **192 GiB** (`196608 MiB`). This provides room
for history growth beyond the former 96 GiB cache; active journals remain needed
and the working set can eventually exceed any finite cache.

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

`scripts/pod_memory_guard.py --watch 30` now checks available container headroom.
Below **32 GiB**, it requests at most **16 GiB** of file-cache reclaim per check,
aiming for **48 GiB** headroom and budgeting at least **8 GiB** of clean unmapped
file cache. It uses the container's
[`memory.reclaim` interface](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory)
with `swappiness=0`; it does not lower the memory limit or apply `memory.high`
throttling. Kernel reclaim amounts can differ from the request, and ongoing
allocations can reduce the headroom observed afterward. The guard retains
application buffers, decoded history, GPU state and all journal files. It does
not change pinned numerical sources, and it exits when the campaign ends.
Status and reclaim receipts are retained in `MEMORY_GUARD.json`; guard events
appear in `memory-guard.log`. File cache can grow again between checks.

The decoded host-history cache remains capped at **192 GiB** and automatically
evicts/reloads authenticated records when full. This cap covers decoded payload,
not all process overhead. Evictions can affect throughput as history grows.
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
  --seed 9370001 --cache-mib 196608 \
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
