# Pod u5: eight-trillion-decision stop

The owner requested the pod stop at **8,000,000,000,000 decisions**. Production
committed exactly that endpoint and stopped on **2026-10-03 at 16:49:18 UTC /
11:49:18 Chicago**, with **3 false events and zero missed primes**.
The final 100B averaged **155.410939M/s**; the last 500M of chunk-loop timing
averaged **175.310989M/s**. Current production throughput is zero.

[Final checkpoint receipt](../evidence/pod/eight-trillion-20261003/FINAL.json) ·
[All 80 milestone reports](pod-run.md) · [Source and method](latest-u5.md) ·
[Archive policy](pod-archives.md) ·
[Verified archive custody](../evidence/pod/eight-trillion-20261003/ARCHIVES.json)

## Result and errors

| Quantity | Final value |
|---|---:|
| Seed / extra PCG64 seed | 9370001 / 10370001 |
| First candidate | 2 |
| Candidate decisions | 8,000,000,000,000 |
| Last candidate scored | 8,000,000,000,001 |
| Actual emitted events | 279,010,070,814 |
| Committed 5M journals | 1,600,000 |
| False events / missed primes | 3 / 0 |
| Errors per billion decisions | 0.000375 |
| Status | STOPPED |

The three raw false events occurred at **2,274,828,165,298**,
**2,379,059,006,438** and **2,687,315,963,345**. Each reproduces in an independent
1B CPU replay retaining the preceding history, terminal microscopic state and
both RNG streams. Those qualifications and their 2,600 metadata comparisons
per replay are retained in the [production report](pod-production.md).
The final check authenticated each error journal and its recorded error position.
No further errors occurred through 8T according to the committed error totals.

Feedback is fully raw: every emitted event feeds back unchanged. An independent
segmented sieve scores decisions after the gate acts. There is no correction,
learner, repair or reference veto. This is the frozen 128-state balanced u5
source with Gamma=512, three readings and NumPy 1.26.4.

The [local CPU run](local-trillion.md) stopped separately at 1.039515T with zero
errors. Both executions use the same seed; overlapping prefixes are not added
together or treated as independent seed exposure. The earlier u4 ensembles
remain separate experiments.

## Setup and stop

Three RTX PRO 4500 Blackwell GPUs separated speculative proposals, bank-mask
construction from actual history, and stable extraction/error grading. Eight CPU
workers, eight accelerator threads and twelve history-planning threads supported
one ordered writer. Host history cache and GPU history cache were each bounded
at 16 GiB. Measured pod limits were 40.8 CPUs and 262.63 GiB RAM.

At **7,819,915,000,000 decisions**, a clean checkpoint pause allowed the existing
controller to relaunch with **`--max-milestones 80`**, retaining the same source,
seed, hidden state, history, errors and PCG64 states. That finite target is
exactly 1,600,000 chunks; it avoids relying on a polling STOP request at the
boundary. The final worker reason is `target`; the existing controller calls
its finite-limit exit `test_milestone_limit`. The final receipt records the
owner's requested limit as well as those original machine reasons.

The STOP file is present and both controller and worker have exited. The
workstation pod-publication and automatic-backup timers are disabled, preserving
the final records. No Runpod pod stop/reset or container resize was submitted.

## Final checkpoint verification

The original final checkpoint's SHA-256 is:

```text
960a105e4acd6738edf9059b139f492d94193a4ee420ff44c7f2efaca22ec331
```

The retained receipt resolves the authenticated HEAD/COMMITS chain, checks all
1,600,000 record positions and event ranks, and matches the complete event count.
The final journal's transport and decoded-period hashes passed, and its terminal
microscopic state and both RNG states match the durable checkpoint exactly.
Pinned numerical and accelerator source hashes passed. The receipt includes
all installed source-file hashes, both RNG states and the durable HEAD.

## Archived data and restoration

The final archive chain contains journal batches **000001 through 000004** plus
**`u5_seed9370001_8T_critical.tar.zst`**. The first two journal batches had already
been verified on T500 and uploaded by the owner; this finalization transfers
only batches 3 and 4 plus the critical metadata/source archive.

| Archive | Journal chunk range (end exclusive) | Compressed bytes | Custody |
|---|---:|---:|---|
| Batch 000001 | 0–504,621 | 106,865,581,001 | Previously verified on T500; owner uploaded |
| Batch 000002 | 504,621–1,021,162 | 105,471,394,889 | Previously verified on T500; owner uploaded |
| Batch 000003 | 1,021,162–1,549,710 | 106,390,398,864 | Verified on T500 |
| Batch 000004 | 1,549,710–1,600,000 | 10,142,291,907 | Verified on T500 |
| 8T critical metadata/source | No bulk journals | 764,995,965 | Verified on T500 |

All **528,573** batch-3 members, **50,315** batch-4 members and **412** critical
archive members passed manifest, size, SHA-256 and decompressor checks directly
on lilhelper. Archive and verification receipts were fsynced before accepting
completion. Container staging cleanup removed no active scientific journals.
The complete backup needs the two earlier owner-uploaded batches as well as
these three new archives. It does not require the pod to remain online.

The critical archive retains the original checkpoint, HEAD/COMMITS, STOP marker,
complete timings, session and milestone records, runtime source and compiled libraries,
the pod source export and memory/error qualification metadata. Journal payloads
are in the numbered batches. It excludes those bulk NPZ journals, including the
first two batches' payloads.

T500 destination:

```text
/home/lilhelper/SAM_Research_Project/POD_BACKUPS/prime-event/u5_seed9370001_20261003/archives/
```

The workstation sees the same folder under
`/home/sam/mnt/lilhelper-t500/POD_BACKUPS/prime-event/u5_seed9370001_20261003/archives/`.
Keep all numbered batches, the critical archive and their expected/verified
sidecars; `RESTORE_8T.json` retains the archive-chain hashes and custody record.
Restore numbered batches into `/root/prime-u5-production`, then restore
the critical archive at `/` to recover its retained `root/` and `tmp/` paths.
The critical archive contains the original final HEAD and commit log; those
belong together. STOP remains present until an explicit operator resume.
Recreate the NumPy 1.26.4 and CUDA 12.8 environment described in the
[production setup](pod-production.md) before resuming the retained runtime.
