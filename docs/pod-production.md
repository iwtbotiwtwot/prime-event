# Continuous pod run and 100B reports

Authorized October 2, 2026 Chicago. The RTX 3090 pod starts **seed 9370001
at candidate 2 with empty history**, using the same frozen raw u5 source.
This is a separate execution of the workstation seed, not a migration and not
an independent-seed accuracy experiment. The workstation run is unchanged.

The production configuration is GPU speculative proposals, CPU consumption and
scoring, affinity 64–95, eight preparation threads and eight RNG workers. The
bounded history cache is **64 GiB**, increased from the pilot's 4 GiB to retain
more actual-event history within the pod's approximately 116 GiB RAM allowance.
Source tables, RNG streams and decision rules are unchanged. The cache setting,
committed-progress observer, and milestone/backup controller were requalified
against the frozen 100M reference before launch; the test exercised two 50M
milestones, restart between them, and authenticated persistent-volume copies.

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

Fresh campaign command (do not run a second writer against an active root):

```bash
taskset -c 64-95 /tmp/prime-u5-venv/bin/python \
  /tmp/prime-u5-throughput/experiments/u5-throughput/campaign.py \
  --root /root/prime-u5-production --mirror /root/prime-u5-backup \
  --seed 9370001 --cache-mib 65536
```
