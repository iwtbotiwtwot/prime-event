# Reproduction levels

The public implementation reproduces the original binary64 sampling law and
ordered feedback events using a bounded-memory segmented scheduler. It does
not require the private SLC/CE environment used to produce the original research
receipts. [Provenance](../evidence/PROVENANCE.json) identifies the source code
and explains the portability changes.

## 1. Fast checks

Install following the root README, then run:

```bash
python -m unittest discover -s tests -v
python scripts/check_evidence.py
python -m prime_event run --source balanced --seed 1000000 \
  --until 1000000 --chunk 100000 --output runs/demo
```

The scalar test independently reconstructs returning divisors with `%`, samples
CDFs by linear search, and compares emissions, bank hashes, all ending RNG/state
values and checksums across restarts. Both sources and both profiles are covered.
A tiny event cache forces reading compressed prior chunks. Disk guard tests use
injected free-space readings; the sampling unit test uses a synthetic adequate
capacity reading so that it can run on nearly full CI/dev filesystems. Actual
CLI runs always enforce the real disk guard.

## 2. Complete individual trajectories

Use `--until 1000000000` and compare with `prime-event verify` as in the README.
Horizon is inclusive, so generation covers999,999,999 candidate integers2..1B.
There are50,847,534 reference primes in that interval. Seed1000063 is the
original baseline's exact trajectory. Other seeds' expected errors are in
`evidence/trajectories.json`; reproduce them without selecting only exact seeds.

The frozen CDF bytes and NumPy1.26.4 are the bit-replay inputs. Source tables
reconstructed with a different BLAS may differ by rounding; the source rebuild
report measures that difference and does not overwrite the frozen tables.
Checkpoint hash chains differ from the historical format. Compare mathematical
outputs and terminal state/checksum instead of expecting identical compressed
container files or wall-clock times.

## 3. All published experiments

These commands are substantial computations and are not CI smoke tests. They
run only when explicitly invoked. `--workers` controls concurrent single-core
trajectories; cache default256MiB per worker plus working arrays/source tables.

```bash
python scripts/reproduce_campaign.py --experiment baseline-matched \
  --workers 4 --output runs/baseline-matched
python scripts/reproduce_campaign.py --experiment balanced-matched \
  --workers 4 --output runs/balanced-matched
python scripts/reproduce_campaign.py --experiment balanced-fresh \
  --workers 4 --output runs/balanced-fresh
```

64seeds×2profiles baseline,64×2 balanced matched,16×2 balanced fresh =288
trajectories. A given seed/profile pair uses the same RNG streams for baseline
and balanced sources. Profile pairing is also retained. Profiles are not
independent trials. Batch logs remain in each output folder. Use a shorter
`--until` for a wiring check, but it does not reproduce the billion-index result.

## 4. Source construction

```bash
python -m prime_event rebuild-source --source balanced --output runs/source-balanced
python -m prime_event rebuild-source --source baseline --output runs/source-baseline
```

The source is reconstructed from the six hidden-spin rows, two bank inputs,
heat-bath flip rates, positive uniformization/squaring propagator, phase exposure
arrays and three-reading duration. Reconstruction uses no event outcomes or
prime labels. Reports give the largest absolute CDF difference and exact file
hash comparison with frozen inputs. The balanced strength is selected from the
closed algebraic margin equation; it is not fitted to the published seeds.

## Stop and resume

Ctrl-C/SIGTERM or an output-folder `STOP` file requests a stop. Committed chunks
remain resumable; pending work in RAM may be discarded. A stop writes
`STOP_LATCH.json`. Inspect its cause and archive that file explicitly before
resuming; also remove a manual STOP file. Keep all committed chunks. A normal
completed finite run has no stop latch and can be extended by increasing
`--until`. CPU affinity and working cache size may change; scientific source,
seed/profile, mode and configured chunk size must remain fixed.

The disk guard stops at<=10% user-available space over total filesystem size,
or refuses a commit that would encroach on that fraction plus256MiB reserve.
It checks periodically and before writes. It never deletes results for space.
