# Prime-event: hidden-spin feedback, learning, and checked repair

A reproducible CPU experiment coupling a seven-spin stochastic gate to an
event-created recurrence sieve. **Sean Brady** is the originator and conceptual
director; **OpenAI ChatGPT and Codex** are AI research collaborators.

The balanced source improved exact billion-index trajectories from **1/64 to
47/64** per profile. A frozen-source continuation achieved **13/16** exact
trajectories on fresh seeds per profile. Every error and per-seed outcome is
included in the compact evidence. These are finite trajectory results for a
supplied digital sieve; they do not establish a new direct-query primality test.

| Experiment | Seeds per profile | Exact through 1 billion | Extra composites / missed primes |
|---|---:|---:|---:|
| Baseline, uniform | 64 | 1 | 271 / 13 |
| Baseline, rough | 64 | 1 | 272 / 13 |
| Balanced, uniform | 64 | 47 | 17 / 3 |
| Balanced, rough | 64 | 47 | 17 / 3 |
| Balanced fresh, either profile | 16 | 13 | 2 / 1 |

Uniform and rough profiles share random streams within a seed. They are paired
conditions, not twice as many independent seeds. Balanced matched/fresh profile
pairs produced identical event sequences. Baseline and balanced matched runs
use seeds 1000000–1000063; fresh runs use 10000000–10000015. Balancing reduced
aggregate errors 569→40 across the two matched profiles (92.9701%).

## Quick start

Linux, Python 3.10–3.12 and a C++17 compiler (`g++`) are required. NumPy 1.26.4
is pinned for historical RNG replay. No GPU, private SAM/SLC runtime, paid pod,
remote machine or external dataset account is needed.

```bash
git clone https://github.com/iwtbotiwtwot/prime-event.git
cd prime-event
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
python scripts/check_evidence.py
python -m prime_event run --source balanced --seed 1000000 \
  --until 1000000 --chunk 100000 --output runs/demo
```

Run on a filesystem with **more than 10% available space**. Production commands
stop at that threshold and before consuming a 256 MiB commit reserve. The run
verifies frozen source hashes, compiles a small C++ kernel, predicts and trains
an independent calibration head, scores the raw gate against a segmented sieve,
and writes compressed, hash-linked checkpoints. In default `raw` mode, reference
labels and learned predictions never enter the feedback generator.

The same command resumes a saved run. Increase `--until` to continue; keep the
source, seed, profile, mode and chunk size unchanged. `--cache-mib 256` is the
default bounded event cache. A larger cache reduces repeated reads. `run` is
single-process/single-core numerical work; `follow` uses four pinned processes.

## Reproduce a published billion-index trajectory

```bash
python -m prime_event run --source baseline --seed 1000063 \
  --until 1000000000 --output runs/baseline-exact
python -m prime_event verify --experiment baseline-matched --seed 1000063 \
  --output runs/baseline-exact

python -m prime_event run --source balanced --seed 1000000 \
  --until 1000000000 --output runs/balanced
python -m prime_event verify --experiment balanced-matched --seed 1000000 \
  --output runs/balanced
```

`verify` compares error totals and the full terminal microscopic state, event
count and running state checksum with the published record. Use `--profile rough`
for the paired profile and `balanced-fresh` for fresh-seed verification.
[Full experiment commands](docs/reproduction.md) cover all 288 trajectories.
The standalone segmented scheduler preserves the historical decisions and RNG
stream but uses a new compact file format, so historical trace-file hashes are
provenance identifiers rather than expected hashes of newly generated chunks.

## Three runners and a learning follower

```bash
python -m prime_event follow --seed 20000001 --other-seed 20000002 \
  --until 10000000 --chunk 100000 --output runs/follower
```

Requires four allowed CPU IDs. Optional `--cores 0,1,2,3` selects them explicitly. The runners are a matched unassisted control,
a same-seed checked-repair branch, and a second-seed checked-repair branch.
The fourth process independently checks and trains. Shared RAM buffers avoid
intermediate disk files. Predictions use the preceding model before new prime
labels are computed; training happens afterward. Each branch keeps its own
model. A fixed return-bank-veto comparator is scored alongside it.

**Checked repairs use reference labels.** They remove extra events, insert missed
ones and restore creation-order bank parity for future chunks. Raw errors remain
recorded. Learned predictions currently do not steer alone. This experiment
measures whether repairing history changes subsequent raw errors, and whether
learned correction improves on the simple comparator. It does not relabel
teacher-assisted output as unassisted prime generation.

[Learning and repair design](docs/follower.md) includes stable forks, monitoring,
quiet background operation and the original observation snapshot.

## What is included

- [Manuscript PDF](manuscript/Balanced_Hidden_Spin_Prime_Feedback.pdf),
  [editable Word](manuscript/Balanced_Hidden_Spin_Prime_Feedback.docx),
  [Markdown](manuscript/MANUSCRIPT.md), LaTeX, figures, tables and references.
- [288 trajectory records](evidence/trajectories.json), summaries, exact error
  positions and historical terminal checksums.
- Frozen baseline/balanced CDF arrays, losslessly compressed, with SHA-256 hashes.
- [Microscopic source reconstruction](docs/method.md), exact source inputs,
  source reconstruction command, standalone C++ scheduler and Python runner.
- Scalar replay/restart, learner-ordering and disk-guard tests, plus GitHub CI.
- [Provenance and data scope](docs/data.md), authorship and citation metadata.

The original bulk per-integer traces and private native runtime are not bundled.
No public DOI is assigned to that bulk prime dataset here. All numerical inputs
needed to regenerate the event streams are included. The attribution DOI
[10.5281/zenodo.22989862](https://doi.org/10.5281/zenodo.22989862) describes the
AI research collaboration; it is **not** the prime dataset DOI.

See [LICENSE](LICENSE) for current reuse terms.
