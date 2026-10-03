"""Reclaim pod file cache when container headroom is low; retain application RAM."""
import argparse
import datetime
import errno
import fcntl
import json
import os
from pathlib import Path
import signal
import time

GIB = 1024**3


def memory(cgroup):
    limit = int((cgroup / 'memory.max').read_text())
    current = int((cgroup / 'memory.current').read_text())
    stats = dict((key, int(value)) for key, value in
                 (line.split() for line in (cgroup / 'memory.stat').read_text().splitlines()))
    return dict(current_bytes=current, limit_bytes=limit,
                headroom_bytes=limit-current, stats=stats,
                events=(cgroup / 'memory.events').read_text())


def requested_bytes(sample, trigger=32*GIB, target=48*GIB, batch=16*GIB, keep_file=8*GIB,
                    file_high=48*GIB, file_target=32*GIB):
    stats = sample['stats']
    if sample['headroom_bytes'] >= trigger and stats.get('file', 0) <= file_high:
        return 0
    clean_unmapped = max(0, stats.get('file', 0) - sum(stats.get(key, 0) for key in
                        ('shmem', 'file_mapped', 'file_dirty', 'file_writeback')))
    desired=max(target-sample['headroom_bytes'], stats.get('file',0)-file_target)
    amount = min(batch, desired, max(0, clean_unmapped-keep_file))
    return amount if amount >= 128*1024**2 else 0


def needs_pause(sample):
    # File cache is reclaimable; an excessive non-file working set needs an
    # orderly stop while room remains for the final checkpoint and buffers.
    non_file=sample['stats'].get('anon',0)+sample['stats'].get('kernel',0)
    return non_file > sample['limit_bytes']-24*GIB


def no_swap_available(cgroup):
    try:
        if (cgroup/'memory.swap.max').read_text().strip()=='0':return True
        lines=Path('/proc/swaps').read_text().strip().splitlines()
        return len(lines)==1 and lines[0].startswith('Filename')
    except OSError:return False


def reclaim(cgroup, amount):
    # Prefer file cache explicitly. Older kernels lack the swappiness option;
    # the plain interface is safe for application RAM only with no swap route.
    error = None
    mode='swappiness_zero'
    started = time.monotonic()
    try:
        with (cgroup / 'memory.reclaim').open('w') as output:
            output.write(f'{amount} swappiness=0\n')
    except OSError as exc:
        if exc.errno==errno.EINVAL and no_swap_available(cgroup):
            mode='verified_no_swap_fallback'
            try:
                with (cgroup/'memory.reclaim').open('w') as output:output.write(f'{amount}\n')
            except OSError as fallback:error=dict(errno=fallback.errno,message=str(fallback))
        else:error = dict(errno=exc.errno, message=str(exc))
    return dict(requested_bytes=amount, seconds=time.monotonic()-started,
                mode=mode,
                status='RECLAIMED' if error is None else
                       'PARTIAL' if error['errno'] == errno.EAGAIN else 'ERROR',
                error=error)


def atomic(path, obj):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(obj, indent=2)+'\n')
    os.replace(temporary, path)


def campaign_alive(root):
    state = json.loads((root / 'CAMPAIGN.json').read_text())
    if state.get('status') != 'RUNNING':
        return False
    try:
        os.kill(int(state['pid']), 0)
    except ProcessLookupError:
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/root/prime-u5-production'))
    parser.add_argument('--watch', type=float, help='Check every N seconds until the campaign ends')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.watch is not None and args.watch <= 0:
        parser.error('positive watch interval required')
    cgroup = Path('/sys/fs/cgroup')
    # A finite container limit is required. The host root normally has "max".
    memory(cgroup)
    lock = (args.root / 'MEMORY_GUARD.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    last_reclaim = None
    count = 0
    while True:
        before = memory(cgroup)
        active = campaign_alive(args.root)
        amount = requested_bytes(before) if active else 0
        row = dict(pid=os.getpid(), updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   status='RUNNING' if active else 'CAMPAIGN_ENDED', dry_run=args.dry_run,
                   requested_bytes=amount, memory=before, reclaims=count, last_reclaim=last_reclaim,
                   trigger_headroom_bytes=32*GIB, target_headroom_bytes=48*GIB,
                   max_batch_bytes=16*GIB, retained_file_cache_bytes=8*GIB,
                   file_cache_high_bytes=48*GIB,file_cache_target_bytes=32*GIB,
                   checkpoint_reserve_bytes=24*GIB)
        if amount and not args.dry_run:
            last_reclaim = reclaim(cgroup, amount)
            after = memory(cgroup)
            last_reclaim.update(before_bytes=before['current_bytes'], after_bytes=after['current_bytes'],
                                net_freed_bytes=before['current_bytes']-after['current_bytes'])
            count += 1
            row.update(memory=after, reclaims=count, last_reclaim=last_reclaim)
        if active and needs_pause(row['memory']) and not args.dry_run:
            (args.root/'data/STOP').touch()
            row.update(status='CHECKPOINT_PAUSE_REQUESTED',reason='Non-file memory reached the checkpoint reserve')
        atomic(args.root / 'MEMORY_GUARD.json', row)
        if args.watch is None or amount or not active or row['status']=='CHECKPOINT_PAUSE_REQUESTED':
            print(json.dumps(row), flush=True)
        if args.watch is None or not active or stopped:
            break
        deadline = time.monotonic()+args.watch
        while not stopped and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline-time.monotonic())))
        if stopped:
            break


if __name__ == '__main__':
    main()
