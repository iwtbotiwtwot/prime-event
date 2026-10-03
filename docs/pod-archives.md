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
3. Verify archive size and SHA-256, then decompress without extraction and verify
   every member's size and SHA-256. Reject missing, extra, duplicate or altered
   members. Fsync the archive and verification receipt before acknowledging it.
4. Only after that receipt is accepted, remove the staged container archive and
   any covered **redundant backup copies**. Retain the active event history.
5. The user uploads the archive and sidecars to Drive, independently verifies the
   upload, and removes the T500 archive manually. Keep the small receipts/index.

**The current trajectory cannot continue exactly if its working event-history
files are removed.** `History.get()` still reads old emitted periods for future
bank masks and restart. The 64 GiB RAM cache is bounded and is not a durable
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

## Qualification

The small end-to-end qualification used the 100M reference journal, with a
deliberately reduced test threshold. It verified 36 archive members on the T500,
removed 20 redundant container test copies, and retained all active test chunks.
The test then resumed to 150M and matched 390 frozen-reference metadata fields.
Fault tests reject a forged receipt and a corrupted member even when the outer
archive hash is recomputed. They also check interrupted indexing, duplicate
cleanup acknowledgement and retention of active history. Production uses the
full 100 GiB trigger; no 100 GiB batch is claimed to have been transferred yet.
