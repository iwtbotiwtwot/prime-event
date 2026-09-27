# Quiet three-runner / one-follower operation

The control and repair runners use the same seed. The third runner uses another
seed, and a dedicated fourth process checks, predicts, trains and issues repairs.
The CLI accepts four CPU IDs from the process's allowed affinity. Choose distinct
physical cores on SMT machines. Example (replace IDs for your workstation):

```bash
nice -n 15 python -m prime_event follow --cores 0,1,2,3 \
  --seed 20000001 --other-seed 20000002 --until 1000000000000 \
  --cache-mib 2048 --output runs/long-follower > runs/follower.log 2>&1
```

Create `runs/` first for the shell log redirection. This is a large explicit
horizon, not an estimated completion time. No daily yield is promised: rebuilding
feedback history costs more as it grows. Default cache256MiB is smaller than the
2GiB-per-runner setting used on the original helper. Three2GiB caches plus working
arrays should be budgeted before choosing that setting. Single-thread numerical
libraries and per-process affinity are enforced by the CLI.

On a Linux host, a user systemd service can run this same command with
`CPUQuota=400%`, `Nice=15`, `IOWeight=10`, `IOSchedulingClass=idle`,
`MemoryHigh=18G`, `MemoryMax=22G`, `MemorySwapMax=0`, `KillMode=mixed` and
`Restart=no`. Set `WorkingDirectory` and the interpreter/output paths to your
installation. Persistence across logout additionally requires user lingering.
The public package does not change your systemd or login settings automatically.

Follow the console log and inspect `STATUS.json`, branch `PROGRESS.json` and
`CHECKPOINT.json`. `RESULT.json` records a completed or stopped invocation.
A checked-repair branch retains all original raw events/errors, with separate
corrected feedback-event counts. Stopping and resuming are described in the
reproduction guide. All durable data go under the selected output directory;
shared-memory buffers carry transient follower inputs.

## Matched forks

To reproduce the original known-error comparison, first generate error-free
prefixes ending700000001 for balanced seeds20000001 and20000002, with the default
chunk5000000. Pass their `trajectory/` directories:

```bash
python -m prime_event run --seed 20000001 --until 700000001 --output runs/seed1-prefix
python -m prime_event run --seed 20000002 --until 700000001 --output runs/seed2-prefix
python -m prime_event follow --seed 20000001 --other-seed 20000002 \
  --fork-from runs/seed1-prefix/trajectory \
  --other-fork-from runs/seed2-prefix/trajectory \
  --until 3000000000 --output runs/forked-follower
```

Forks hard-link immutable chunks on the same filesystem and write independent
checkpoints/future chunks. Keep linked file contents immutable. The portable
fork inherits any past calibration model in its source checkpoint. The original
research fork started with an untrained model at700000002; raw generation and
checked repairs are unaffected by this observational-model difference. To resume
an existing fork, omit the fork arguments. The helper's original private runtime
and machine addresses are not needed.

## Meaning of correction

Repairs take effect at the next chunk boundary. Removing a false event changes
creation-order parity for later feedback events; inserting a missed prime also
changes parity. The runner rebuilds from the corrected sequence. It does not
retroactively rewrite decisions or microscopic states in the completed chunk.

Model predictions are formed before reference labels, then scored. Training
uses only that branch's past chunks. Reference-checked repairs currently steer
the two repair branches; model predictions do not steer independently. The fixed
comparator rejects a raw emission whenever a return bank is active. Report it
beside the learner, because they may agree.

An event at n first returns at2n. The first known false emission704674591 cannot
change bank inputs before1409349182. Its subsequent creation-parity changes
also first affect returns after that bound. The earlier error1081748735 therefore
cannot be caused by feedback from the first. This illustrates why the matched
raw-error comparison is more informative than counting corrected errors alone.
