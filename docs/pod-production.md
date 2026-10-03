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
execution; failures are not silently retried. No old scientific data is deleted.

Checkpoint writes use the pod's fast container disk with a 20 GiB free-space
reserve. At each milestone a background copier mirrors immutable journal chunks
to **`/root/prime-u5-backup` on the container disk**, verifies SHA-256 on new copies, and writes
the matching checkpoint last. At most one backup runs at once. `BACKUP.json`
tracks completion. A mirror checkpoint retains original absolute paths: restore
it and the journals to their original root before resuming. A stopped/replaced
pod may need explicit environment reconstruction and verified recovery; no
unqualified fresh-seed restart is automatic. **This production run does not use
`/workspace` for backups.**

The external backup destination is the **T500**, at
`/home/sam/mnt/lilhelper-t500/POD_BACKUPS/prime-event/u5_seed9370001_20261003`.
`prime-event-t500-backup.timer` pulls committed snapshots every five minutes.
Each new compressed journal is verified against its recorded SHA-256 before
the matching checkpoint and `VERIFIED.json` receipt are published. The script
requires the T500 mount and a 20 GiB reserve; it refuses to silently fall back
to workstation storage if the drive is unavailable. Transfer failures retry on
the next timer invocation. The workstation and T500 network mount must be online;
the container retains the running journals and pod-side copy during an outage.

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
