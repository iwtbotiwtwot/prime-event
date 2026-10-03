# Pod u5 run — reports every 100 billion decisions

Seed **9370001**, started **2026-10-03T00:48:33+00:00** at candidate 2 with empty history. Campaign status at this report: **RUNNING**.

This is a separate execution of the same seed as the workstation run, not additional independent seed exposure. The workstation trajectory is unchanged. All feedback is raw: no repair, learner or reference veto. Counts below come from committed checkpoints.

Reports are generated at exactly 100B, 200B, 300B, and onward. Interval throughput divides the latest 100B committed decisions by elapsed wall time; cumulative throughput includes setup, restarts and pauses since launch. A workstation timer publishes newly retained pod reports every minute when connectivity is available. Delayed publication does not change the recorded milestone time.

[Methodology and pilot predictions](throughput-pilot.md) · [Production controls and T500 backups](pod-production.md) · [JSON](../evidence/pod/milestones.json) · [CSV](../evidence/pod/milestones.csv)

| Milestone | Observed UTC | False events | Missed primes | Total errors | Interval M/s | Cumulative M/s |
|---:|---|---:|---:|---:|---:|---:|
| 100B | 2026-10-03T01:32:23+00:00 | 0 | 0 | 0 | 38.02 | 38.02 |
| 200B | 2026-10-03T02:19:22+00:00 | 0 | 0 | 0 | 35.47 | 36.70 |

Latest sampled progress when this page was published: **201,660,000,000 decisions**, FP **0**, FN **0**, observed **2026-10-03T02:20:03Z**. This is a dated sample, not a continuously refreshed counter.
