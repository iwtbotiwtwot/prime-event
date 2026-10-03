# Pod u5 run — reports every 100 billion decisions

Seed **9370001**, started **2026-10-03T00:48:33+00:00** at candidate 2 with empty history. Campaign status at this report: **RUNNING**.

This is a separate execution of the same seed as the workstation run, not additional independent seed exposure. The workstation trajectory is unchanged. All feedback is raw: no repair, learner or reference veto. Counts below come from committed checkpoints.

Reports are generated at exactly 100B, 200B, 300B, and onward. Interval throughput divides the latest 100B committed decisions by elapsed wall time; cumulative throughput includes setup, restarts and pauses since launch. A workstation timer publishes newly retained pod reports every minute when connectivity is available. Delayed publication does not change the recorded milestone time.

[Methodology and pilot predictions](throughput-pilot.md) · [Production controls and T500 backups](pod-production.md) · [GPU roles and current running throughput](pod-gpu-roles.md) · [JSON](../evidence/pod/milestones.json) · [CSV](../evidence/pod/milestones.csv)

The 1.2T–1.3T interval includes the migration pause. The separate running-throughput measurement in the GPU role report excludes history restoration and that pause.

| Milestone | Observed UTC | False events | Missed primes | Total errors | Interval M/s | Cumulative M/s |
|---:|---|---:|---:|---:|---:|---:|
| 100B | 2026-10-03T01:32:23+00:00 | 0 | 0 | 0 | 38.02 | 38.02 |
| 200B | 2026-10-03T02:19:22+00:00 | 0 | 0 | 0 | 35.47 | 36.70 |
| 300B | 2026-10-03T02:44:31+00:00 | 0 | 0 | 0 | 66.30 | 43.12 |
| 400B | 2026-10-03T03:13:04+00:00 | 0 | 0 | 0 | 58.38 | 46.13 |
| 500B | 2026-10-03T03:33:23Z | 0 | 0 | 0 | 82.02 | 50.56 |
| 600B | 2026-10-03T03:48:14Z | 0 | 0 | 0 | 112.24 | 55.65 |
| 700B | 2026-10-03T04:04:03Z | 0 | 0 | 0 | 105.32 | 59.68 |
| 800B | 2026-10-03T04:21:04Z | 0 | 0 | 0 | 97.92 | 62.74 |
| 900B | 2026-10-03T04:39:11Z | 0 | 0 | 0 | 92.02 | 65.04 |
| 1000B | 2026-10-03T04:59:24Z | 0 | 0 | 0 | 82.42 | 66.44 |
| 1100B | 2026-10-03T05:21:08Z | 0 | 0 | 0 | 76.73 | 67.26 |
| 1200B | 2026-10-03T05:35:22Z | 0 | 0 | 0 | 117.07 | 69.73 |
| 1300B | 2026-10-03T07:39:55Z | 0 | 0 | 0 | 13.38 | 52.67 |
| 1400B | 2026-10-03T07:45:34Z | 0 | 0 | 0 | 295.13 | 55.95 |
| 1500B | 2026-10-03T07:51:12Z | 0 | 0 | 0 | 295.50 | 59.15 |
| 1600B | 2026-10-03T07:57:05Z | 0 | 0 | 0 | 283.54 | 62.23 |
| 1700B | 2026-10-03T08:03:00Z | 0 | 0 | 0 | 281.76 | 65.22 |
| 1800B | 2026-10-03T08:08:58Z | 0 | 0 | 0 | 278.91 | 68.12 |
| 1900B | 2026-10-03T08:15:06Z | 0 | 0 | 0 | 272.15 | 70.91 |
| 2000B | 2026-10-03T08:21:24Z | 0 | 0 | 0 | 264.30 | 73.61 |
| 2100B | 2026-10-03T08:27:48Z | 0 | 0 | 0 | 260.54 | 76.21 |

Latest sampled progress when this page was published: **2,104,135,000,000 decisions**, FP **0**, FN **0**, observed **2026-10-03T08:28:04Z**. This is a dated sample, not a continuously refreshed counter.
