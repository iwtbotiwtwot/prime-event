# Local CPU u5: trillion-decision stop

The seed **9370001** local CPU trajectory was intentionally stopped after
**1,039,515,000,000 decisions**, with **zero false events and zero missed primes**.
The clean stop committed at **2026-10-03 13:15:20 UTC / 08:15:20 Chicago**.
The final 500 million decisions ran at **7.153 million decisions/s**.

[Compact final receipt](../evidence/local-u5-20261003/FINAL.json) ·
[Final observation and hourly history](live-run.md) ·
[Method and reproduction](latest-u5.md) ·
[Frozen source identity](../production/u5/SOURCE.json)

## Result

| Quantity | Final value |
|---|---:|
| First candidate | 2 |
| Candidate decisions | 1,039,515,000,000 |
| Last candidate scored | 1,039,515,000,001 |
| Emitted events | 39,036,981,351 |
| False events / missed primes | 0 / 0 |
| Committed 5M chunks | 207,903 |
| Final status / reason | STOPPED / requested |

This is one fully raw trajectory from empty history. Every emitted event feeds
back unchanged; an independent segmented sieve scores decisions after the gate
acts. There is no repair, correction, learner or reference veto. The source is
the 128-state balanced u5 gate: beta=1, u=5, t=2.8465622403941495, Gamma=512,
three readings, uniform profile, NumPy 1.26.4. The base and extra PCG64 seeds
are 9370001 and 10370001.

The pod is a separate execution of the same seed. Its overlapping prefix and
the earlier u4 ensembles are separate records; they are not added to this
local decision total or counted as additional independent seed exposure.

## Final performance

The last 100 committed chunks contain **500,000,000 decisions**, with
**69.901030 seconds** of summed chunk-loop time: **7.152970M/s**. The final
session added 131.1 billion decisions in 18,043.317732 seconds, averaging
**7.265848M/s**. These are measured historical rates; current production
throughput is zero because the run is stopped.

The CPU implementation used four RNG workers and affinity 1–7 on an AMD
Ryzen 9 8945HS. The final session's decoded-history cache stayed within its
8 GiB runtime budget; peak process RSS was **8.964 GiB**. The frozen checkpoint
configuration still records the original `cache_mib: 4096` identity. All raw
history remains on disk and is loaded as needed by the bounded cache.

## Checkpoint and retained history

The original final `CHECKPOINT.json` is 288,853 bytes, with SHA-256:

```text
d8eb072e787037e5ec24fa00ab0da332b68e36a976d3eb57521b18d4536517f0
```

Terminal microscopic state, event count and running state checksum are
`[87, 39036981351, 6926034572188830362]`. Both complete PCG64 states are retained
in the compact receipt and original checkpoint.

The post-stop check verified all six frozen source files, all **207** historical
index-block SHA-256 hashes, the candidate positions and event ranks of all
**207,903** indexed records, and agreement with the checkpoint's event total.
The final NPZ journal's transport hash and decoded-period hash passed; its
terminal microscopic state and both RNG states exactly match the checkpoint,
and its previous-journal hash matches the preceding index record. STOPPED
progress agrees with the checkpoint, and both files remained unchanged during
the check. This metadata and final-journal check did not rehash every earlier
NPZ journal or replay the trillion-decision trajectory.

The installed local runtime in `GEN4/prime_u5_resources1` uses the bounded
format-2 history index. All nine files in its source manifest were separately
SHA-256 verified. Its CDF, initial distribution, random buffer code and both
C++ kernels match the frozen reference source; its runner, index loader,
compiled libraries and continuation controller have their own retained hashes.
The configured arguments are `--cache-mib 4096 --runtime-cache-mib 8192`.

The full original checkpoint, history index, every event journal, timing log
and session receipts remain under
`GEN4/prime_u5_local1/production_seed9370001` on T500. No scientific history was
deleted. The resource-bounded production source remains in
`GEN4/prime_u5_resources1`. The compact receipt and source package in Git support identification
and reproduction; the full event history is retained separately.

## Stop controls

The owner STOP file remains present. The former runner exited, no managed
local runner unit is active, and lilhelper's `prime-u5-continuation.timer` is
disabled. Workstation `prime-event-hourly.timer` is also disabled, preserving
the final observation. Resumption requires explicit operator action using the
same checkpoint, source identity and RNG states, with the installed format-2
loader. See [automation](automation.md).
