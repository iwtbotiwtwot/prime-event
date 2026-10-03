# Verified 100 GiB archive rotation

This storage policy is separate from the **100 billion decision reports**.
Every five minutes, the backup service checks newly committed journal bytes since
the last verified archive. At **100 GiB (107,374,182,400 bytes)** it captures a
committed checkpoint and archives the new complete journal files. A batch can
exceed 100 GiB by the data accumulated between polls; files are never split.
The threshold counts the existing compressed NPZ files before outer compression.

1. Create `u5_seed9370001_batch_000001.tar.zst`, then successive numbered batches,
   on the **container disk**. Zstandard uses two threads. Existing journals are
   already compressed, so large additional compression savings are not assumed.
2. Download to the **T500**, using a resumable `.partial` file.
3. Verify directly on **lilhelper**, where the T500 stores the archive: check
   archive size and SHA-256, then decompress without extraction and verify
   every member's size and SHA-256. Reject missing, extra, duplicate or altered
   members. Fsync the archive and verification receipt before acknowledging it.
4. Only after that receipt is accepted, remove the staged container archive and
   any covered **redundant backup copies**. Retain the active event history.
5. The user uploads the archive and sidecars to Drive, independently verifies the
   upload, and removes the T500 archive manually. Keep the small receipts/index.

**The current trajectory cannot continue exactly if its working event-history
files are removed.** `History.get()` still reads old emitted periods for future
bank masks and restart. The 16 GiB host RAM cache is bounded and is not a durable
replacement. No tool in this workflow deletes `/root/prime-u5-production/data`
journals. Removing all historical working data requires a separately designed
and qualified storage backend or stopping the trajectory.

## Destinations and receipts

- Container staging: `/root/prime-u5-backup/archives`.
- Container ledger: `/root/prime-u5-production/archive_state/INDEX.json`.
- T500 archives: `/home/sam/mnt/lilhelper-t500/POD_BACKUPS/prime-event/u5_seed9370001_20261003/archives`.
- Workstation status: `~/.local/state/prime-event-pod/archive-status.json`.
- Each archive has `.expected.json`, `.verified.json`, and `.cleanup.json` sidecars.
- No `/workspace` backup, automatic Drive upload, or automatic T500 deletion.

Each batch contains its new journal range, source files, a manifest and a full
checkpoint index. It is **incremental**: restoration needs all preceding batches
as well, plus any newer unarchived tail. Checkpoints retain original absolute
paths. Old loose T500 snapshots are not deleted by this policy.

To re-verify a downloaded archive, including a copy downloaded back from Drive:

```bash
python3 scripts/verify_pod_archive.py \
  /path/u5_seed9370001_batch_000001.tar.zst \
  /path/u5_seed9370001_batch_000001.tar.zst.expected.json
```

A transfer or verification failure leaves container copies intact. The next poll
retries the pending batch. A completed archive can be recovered if indexing was
interrupted; an accepted receipt makes cleanup idempotent. Container and T500
free-space reserves are checked before staging or download. There is at most one
worker, enforced by the backup lock and systemd oneshot service.

Since October 3, the workstation sends the exact repository verifier to
`lilhelper@10.77.0.2` over SSH and receives its JSON receipt. The archive is read
on its storage host, avoiding two full reads through SSHFS. Before doing so, the
tool matches the mounted filesystem's host and root to its configured verification
destination. A failed connection, mismatched mount, checksum failure or invalid
receipt prevents container cleanup. This changes verification location only;
all existing integrity and durability checks remain required.

Defaults are the existing mount's host and `/home/lilhelper/SAM_Research_Project`,
with `~/.ssh/id_ed25519`. The backup service's SSH access was checked in its
systemd environment. `PRIME_EVENT_T500_HOST`, `PRIME_EVENT_T500_ROOT` and
`PRIME_EVENT_T500_IDENTITY` can configure the corresponding connection.
`--verify-locally` retains verification through the mounted T500 when needed.
Workstation status now reports `COPYING` and `VERIFYING` while a batch is pending;
a full `.partial` is verified without downloading it again.

## Qualification

The small end-to-end qualification used the 100M reference journal, with a
deliberately reduced test threshold. It verified 36 archive members on the T500,
removed 20 redundant container test copies, and retained all active test chunks.
The test then resumed to 150M and matched 390 frozen-reference metadata fields.
Fault tests reject a forged receipt and a corrupted member even when the outer
archive hash is recomputed. They also check interrupted indexing, duplicate
cleanup acknowledgement and retention of active history. Production uses the
full 100 GiB trigger. Production batch 1 passed verification of all **504,646
members** and its container staging archive was removed at **09:37:46 UTC on
October 3**; its live journals remain in place.
[Production receipt](../evidence/pod/storage-cleanup-20261003/PRODUCTION_ARCHIVE_CLEANUP.json).

At **12:43:23 UTC**, production batch 2 also completed cleanup: its **98.23 GiB**
staged archive caused the next container-space jump. The automatic storage-host
verifier checked **516,566 members**, covering new journals through **5.10581T
decisions**. All **516,541** covered live journal files remained on the pod.
At **12:44:49 UTC**, container usage was **224.05 GiB used / 275.95 GiB free**
of its 500 GiB capacity, and production remained RUNNING with FP=3/FN=0.
Staging the next 100 GiB batch will temporarily consume space again; the faster
verification clears redundant archives sooner. Live journal storage still grows.
[Batch 2 receipt](../evidence/pod/storage-cleanup-20261003/BATCH_000002_CLEANUP.json).

The post-cleanup check at **12:47:25–12:47:55 UTC** committed **6.205B decisions
in 30.00142 seconds = 206.824M/s**, ending at **5.431735T decisions**, FP=3/FN=0,
with **274.31 GiB free**. Controller and worker PIDs remained unchanged, and all
memory-limit/OOM counters stayed zero.
[Production check](../evidence/pod/storage-cleanup-20261003/BATCH_000002_POST_CLEANUP.json).

Storage-host tests execute the real verifier in a separate Python process,
require rejection of a corrupted copy, and block access when the mount does not
match the verification destination. The existing archive tests still cover
destructive cleanup gates and retain active history.
