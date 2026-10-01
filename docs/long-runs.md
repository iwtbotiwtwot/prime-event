# Longer prime-event runs

Evidence snapshot assembled October 1, 2026 from retained stopped checkpoints and dated observations. Endpoints below are inclusive; candidate-decision denominators are endpoint minus one, starting at candidate 2. The CPU stop receipt is dated September 30; the 104.48-billion export was verified September 29; the four-stream GPU stop receipt is dated October 1 at 18:47:45 UTC.

## Exact endpoints and raw errors

| Run | Through | False events | Missed primes | Total |
|---|---:|---:|---:|---:|
| control_seed20000001 | 81,820,000,001 | 28 | 2 | 30 |
| repair_seed20000001 | 81,175,000,001 | 28 | 2 | 30 |
| repair_seed20000002 | 81,140,000,001 | 15 | 1 | 16 |
| gpu_30000001 | 104,479,850,495 | 23 | 5 | 28 |
| gpu_9360001 | 172,469,780,479 | 46 | 7 | 53 |
| gpu_9360001_paired_raw | 172,469,780,479 | 45 | 7 | 52 |
| gpu_9360002 | 172,469,780,479 | 56 | 6 | 62 |
| gpu_9360003 | 172,469,780,479 | 44 | 4 | 48 |
| gpu_9365001 (early snapshot) | 9,110,028,287 | 3 | 1 | 4 |

The 9365001 row is checked progress observed October 1 at 19:43:31 UTC, not a terminal checkpoint. Its recorded saved prefix and later checkpoint are distinguished below.

## Feedback, source and hardware

The CPU runs use the full 128-state balanced gate on lilhelper, a NucBox K11, with one physical CPU core per generator and an independent follower on a fourth core. Source arrays, NumPy 1.26.4 RNG state, kernel hashes and terminal microscopic states are bound in the checkpoints. The learner's predictions are recorded separately and do not steer the raw generator. Its zero-error prediction counts are not substituted for the gate errors above.

Seed 30000001 uses the 128-state balanced source on an RTX 3090, with checked repair and no learner. Its retained source hash matches the CPU checkpoint source identity. The later RTX 3090 runs use the selected 8-state model, Γ = 512, η = 3/8, uniform profile, three readings, float64 transition tables and dual PCG64 streams. That model has a different source hash, preserved in each receipt. The 8-state reduction's finite qualification is a separate result from exact full-state lumpability.

All GPU streams use an independent CPU sieve spotter. For raw feedback it only observes: erroneous emissions remain in history and missed primes are not inserted. Checked feedback uses the reference to remove false emissions and insert misses, preserving raw error counts separately. RAM buffering and burst journals separate checked progress from durable saved progress. The four-stream stop has matching checked and saved endpoints and zero buffered journal bytes.

## What the paired repair experiment found

The two seed-9360001 branches share an earlier repaired history. The fork's pre-trigger checkpoint starts the block at **53,418,655,744**, with 9 false events and 1 miss already recorded. The triggering composite emission is **53,434,289,881**. Common random draws remain verified through **172,469,780,479**.

From the baseline counters, the repaired branch adds **42 errors (36 false events, 6 misses)** and the raw branch adds **41 (35 false events, 6 misses)**. Complete-history totals are 53 versus 52. Thus the raw fork is not an unrepaired-from-start experiment. First bank divergence occurs in the block 106,854,088,704–106,870,865,919; first emitted-event divergence occurs in 145,122,918,400–145,139,695,615. The independently seeded 9360003 raw run is unrepaired from the start and ends with 48 errors. Different-seed totals are descriptive; the fork supplies the shared-random-stream comparison.

The fully raw seed 9360003 also retains a **17,121,103,958-candidate error-free interval**, from **124,524,197,247 through 141,645,301,204**, inclusive. This is an interior interval, not an error-free prefix from the start.

## Throughput and newer sole-run snapshot

The four-stream stop receipt reports **494,525,218,816 candidate decisions during that controller launch in 6,039.047 seconds**, or **81.888 million decisions/s aggregate**. This is shared-GPU throughput across the branches, not that rate for each seed. Earlier prefix work is outside this launch-time denominator.

**Sole seed 9365001 ran without repair or correction from its empty-history start at candidate 2.** False emissions remain in its feedback history; missed primes are never inserted. The independent checker scores outputs only, and the learner is disabled.

This subsequent fresh sole unrepaired seed, **9365001**, has a retained observation at **2026-10-01 19:43:31 UTC**: checked through **9,110,028,287**, with **3 false events and 1 missed prime**, at **66.945 million decisions/s launch-to-observation**. The same observation reports saved-through **7,298,088,959**; a separately retrieved durable checkpoint reaches **8,841,592,831** with the same error counts. The source uses both qualified preparation overlap and hash/GPU overlap. These are dated early snapshots of the newer run, not its final endpoint or current status. Later conversational status reports are not promoted into published terminal measurements without their retained receipts.

The performance figures above have different workloads and timing scopes. The public README's CPU reproduction commands reproduce the published 128-state billion-index experiments; they do not silently select the later GPU implementation.

## Data access, provenance and reproduction

[summary.csv](../evidence/long-runs/summary.csv) supplies exact endpoints, FP/FN totals, feedback modes, rates, source family and custody. [SOURCE_MANIFEST.json](../evidence/long-runs/SOURCE_MANIFEST.json) identifies the originating records by relative name and SHA-256. The accompanying JSON exports retain public scientific counters, feedback modes and dated measurements. Full checkpoint RNG state, code maps and operational metadata remain in the original custody. Provenance hashes identify those originals; these exports are result records, not restart checkpoints.

The CPU checkpoints were read from the T500 with their stopped status; the bulk histories remain there. The seed-30000001 export receipt records **6,550 files / 4,972,759,124 bytes** verified on the T500. Four-stream and sole-run bulk custody was last recorded on the pod; this documentation task copies compact receipts, not the bulk journals, and performs no new transfer or live pod check. Restarting at a checkpoint requires its matching source implementation and committed history journals. The compact receipts alone provide counters and identities, not a replacement for those histories.

Public 128-state reproduction is documented in [reproduction.md](reproduction.md). Original GPU implementation and method records are retained in the originating research repository under GEN4/prime_gpu5, GEN4/prime_3090_three1, GEN4/prime_3090_pair1, GEN4/prime_3090_single1 and GEN4/prime_3090_solo1. The guide's 288-trajectory table and these later long-run checkpoints remain separate datasets. Shared prefixes and paired forks must not be counted as independent exposure.
