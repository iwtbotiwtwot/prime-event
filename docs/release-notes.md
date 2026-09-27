# Version 0.1.0 — September 27, 2026

Initial public release of the prime-event reproduction package, manuscript and
compact evidence. Original project experiments are frozen; the running research
service is not modified or deployed by installing this package.

Release checks passed in a clean Python 3.12 environment with NumPy 1.26.4:

- Independently sampled scalar replay matches segmented C++ output in both
  sources/profiles, including restart, bank history and full terminal state.
- All 288 published trajectory records reproduce their reported aggregates.
- Both source recipes reproduce all six frozen sampling arrays byte-for-byte
  on the release host.
- Baseline seed 1000063 reproduces every decision through 1,000,000,000 and matches
  the historical terminal state `[119,50847534,5245789155435358623]`.
- The three-runner/follower example completes, handles a partial last chunk and
  continues from its saved generator/model states.

Original setup failures are identified rather than counted as research outcomes:
the first sampling unit test encountered the workstation's real <=10% disk guard;
the unit fixture now injects adequate capacity while separate tests exercise the
guard. Production CLI checks remain real. This workstation lacked ensurepip, so
an existing pip installation populated the fresh venv without changing system
Python. An initial follower status file retained RUNNING after finite completion;
final status now records COMPLETE/STOPPED. No scientific source values changed.

Exact release evidence is under `evidence/PUBLIC_*`, `REBUILT_*` and
`RELEASE_VALIDATION.json`. CI repeats the short replay and aggregation checks;
it does not run all 288 billion-index trajectories on every commit.
