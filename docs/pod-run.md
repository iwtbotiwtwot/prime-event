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
| 2200B | 2026-10-03T08:34:16Z | 0 | 0 | 0 | 257.92 | 78.73 |
| 2300B | 2026-10-03T08:41:06Z | 1 | 0 | 1 | 243.47 | 81.12 |
| 2400B | 2026-10-03T08:56:25Z | 2 | 0 | 2 | 108.86 | 81.99 |
| 2500B | 2026-10-03T09:03:29Z | 2 | 0 | 2 | 235.85 | 84.19 |
| 2600B | 2026-10-03T09:10:33Z | 2 | 0 | 2 | 235.94 | 86.32 |
| 2700B | 2026-10-03T09:17:25Z | 3 | 0 | 3 | 242.86 | 88.43 |
| 2800B | 2026-10-03T09:24:31Z | 3 | 0 | 3 | 234.61 | 90.45 |
| 2900B | 2026-10-03T09:31:28Z | 3 | 0 | 3 | 240.01 | 92.43 |
| 3000B | 2026-10-03T09:38:17Z | 3 | 0 | 3 | 244.11 | 94.39 |
| 3100B | 2026-10-03T09:45:10Z | 3 | 0 | 3 | 242.37 | 96.28 |
| 3200B | 2026-10-03T09:52:08Z | 3 | 0 | 3 | 238.89 | 98.11 |
| 3300B | 2026-10-03T09:59:13Z | 3 | 0 | 3 | 235.72 | 99.88 |
| 3400B | 2026-10-03T10:06:12Z | 3 | 0 | 3 | 238.76 | 101.62 |
| 3500B | 2026-10-03T10:13:23Z | 3 | 0 | 3 | 231.78 | 103.28 |
| 3600B | 2026-10-03T10:20:54Z | 3 | 0 | 3 | 221.83 | 104.83 |
| 3700B | 2026-10-03T10:28:23Z | 3 | 0 | 3 | 222.74 | 106.35 |
| 3800B | 2026-10-03T10:35:50Z | 3 | 0 | 3 | 223.40 | 107.84 |
| 3900B | 2026-10-03T10:43:23Z | 3 | 0 | 3 | 220.89 | 109.27 |
| 4000B | 2026-10-03T10:51:09Z | 3 | 0 | 3 | 214.67 | 110.63 |
| 4100B | 2026-10-03T10:59:00Z | 3 | 0 | 3 | 212.23 | 111.94 |
| 4200B | 2026-10-03T11:06:54Z | 3 | 0 | 3 | 210.90 | 113.20 |
| 4300B | 2026-10-03T11:14:49Z | 3 | 0 | 3 | 210.69 | 114.44 |
| 4400B | 2026-10-03T11:22:41Z | 3 | 0 | 3 | 211.79 | 115.64 |
| 4500B | 2026-10-03T11:30:47Z | 3 | 0 | 3 | 205.79 | 116.78 |
| 4600B | 2026-10-03T11:38:59Z | 3 | 0 | 3 | 203.24 | 117.87 |
| 4700B | 2026-10-03T11:47:13Z | 3 | 0 | 3 | 202.63 | 118.93 |
| 4800B | 2026-10-03T11:55:36Z | 3 | 0 | 3 | 198.74 | 119.93 |
| 4900B | 2026-10-03T12:03:32Z | 3 | 0 | 3 | 209.75 | 120.99 |
| 5000B | 2026-10-03T12:11:35Z | 3 | 0 | 3 | 207.37 | 122.01 |
| 5100B | 2026-10-03T12:19:36Z | 3 | 0 | 3 | 207.73 | 123.00 |
| 5200B | 2026-10-03T12:28:02Z | 3 | 0 | 3 | 197.76 | 123.90 |
| 5300B | 2026-10-03T12:36:45Z | 3 | 0 | 3 | 191.22 | 124.73 |
| 5400B | 2026-10-03T12:45:17Z | 3 | 0 | 3 | 195.12 | 125.57 |
| 5500B | 2026-10-03T12:53:29Z | 3 | 0 | 3 | 203.45 | 126.45 |
| 5600B | 2026-10-03T13:01:48Z | 3 | 0 | 3 | 200.10 | 127.29 |
| 5700B | 2026-10-03T13:10:23Z | 3 | 0 | 3 | 194.25 | 128.06 |
| 5800B | 2026-10-03T13:19:00Z | 3 | 0 | 3 | 193.54 | 128.81 |
| 5900B | 2026-10-03T13:27:17Z | 3 | 0 | 3 | 201.01 | 129.60 |

Latest sampled progress when this page was published: **5,955,960,000,000 decisions**, FP **3**, FN **0**, observed **2026-10-03T13:32:06Z**. This is a dated sample, not a continuously refreshed counter.
