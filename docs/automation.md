# Production continuation and hourly publication

The owner authorized continued execution of seed9370001 until stopped and
hourly public status updates on 2026-10-02. These are ordinary user-systemd
services; neither depends on an active chat session.

The local run was **intentionally stopped on 2026-10-03 at 13:15:20 UTC**,
after **1,039,515,000,000 decisions**, with **FP 0 / FN 0**. Its STOP file
remains present, the lilhelper continuation timer is disabled, and the
workstation hourly publication timer is disabled. The final checkpoint and
all history remain on T500. [Final result and verification](local-trillion.md).

## Same-seed continuation (lilhelper)

`prime-u5-continuation.timer` checks each minute when its oneshot service is
idle. The existing daily managed run is left untouched. Only a clean
`session_time_budget` stop may start the next managed session. The same absolute
root, checkpoint, source hashes, seed, cache size and both RNG states are used.
Each renewed session retains the project resource manager's 86,400-second
outer guard and 86,300-second clean internal deadline. There is no overall
campaign deadline and no fresh seed on renewal.

Before renewal, the controller checks the source manifest, free-space reserve,
STOP file and that the prior managed unit has exited. A failed renewal creates
`RENEWAL_BLOCKED`; it requires operator inspection. A stale/crashed runner,
owner stop or storage stop is not silently relaunched. Reboot after an unclean
stop therefore needs operator recovery. No old data are automatically deleted.

Installed controller: `GEN4/prime_u5_resources1/continue_u5.py` on lilhelper,
using `GEN4/prime_u5_resources1/runner.py` and its authenticated format-2
history index. The current invocation keeps checkpoint identity
`--cache-mib 4096` and separately sets `--runtime-cache-mib 8192`.
Controller logs remain in `GEN4/prime_u5_continuous1/CONTINUATION.log`.
Production root: `GEN4/prime_u5_local1/production_seed9370001` under
`/home/lilhelper/SAM_Research_Project` (the T500 mount).

Clean stop from the workstation:

```bash
touch /home/sam/mnt/lilhelper-t500/GEN4/prime_u5_local1/production_seed9370001/STOP
```

This stops at the next committed 5M chunk. The continuation controller honors
that file and never removes it. To disable future renewals as well:

```bash
ssh lilhelper@10.77.0.2 'systemctl --user disable --now prime-u5-continuation.timer'
```

Disabling the timer alone does not stop an already running production session.
To resume after an intentional stop, an operator removes STOP and explicitly
launches the same checkpoint with the documented production configuration.

## Hourly GitHub publication (workstation)

`prime-event-hourly.timer` runs at the top of each UTC hour (also the top of
each Chicago hour). It invokes `scripts/hourly_status.py --publish`, reading
only checkpoint/progress metadata from the mounted T500. It does not read the
whole event history or execute the simulation.

The publisher updates exactly:

- `evidence/live/latest.json`
- `evidence/live/hourly.csv`
- `docs/live-run.md`

The final observation was captured after the owner stop. Hourly publication
is now disabled so those files retain the stopped endpoint and observed
history. Pod reporting and T500 backup scheduling remain separate services.

It requires a clean `main` checkout, pulls only a fast-forward, then commits
and pushes the observed counts. Network errors or conflicting local edits
fail visibly in the service journal and are retried at the next scheduled
invocation. It does not stash or overwrite user edits, force-push, or publish
credentials. The publication timer has a persistent catch-up invocation after
workstation downtime; it records the current observation, not invented rows
for missed hours. Host user lingering is enabled on both machines.

The CSV retains one actual observation per UTC hour. The Markdown page shows
the latest 48 rows. Each record has UTC and Chicago observation time, checkpoint
time, total candidate decisions, endpoint, false events, missed primes,
combined errors, runner status and the independently timestamped throughput.
A checkpoint older than 120 seconds is labelled stale if progress still says
RUNNING. The observation timestamp, rather than a static GitHub badge, tells
readers whether the page is current.

```bash
systemctl --user list-timers prime-event-hourly.timer
journalctl --user -u prime-event-hourly.service -n 30
systemctl --user disable --now prime-event-hourly.timer
```

Stopping publication does not stop the prime-event trajectory. The workspace
and network must be available for GitHub updates; lilhelper can continue while
the workstation is offline.

`SHA256SUMS` covers the reproducibility release files; the three moving live
status files are intentionally excluded. Their dated versions remain in Git.
