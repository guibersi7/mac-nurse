#!/usr/bin/env python3
"""Read-only macOS snapshot and bounded development-artifact inventory. Python 3.9+."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        return {"ok": result.returncode == 0, "output": result.stdout[:24000],
                "error": result.stderr[:2000], "exit_code": result.returncode}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def inventory(root, max_entries=10000, max_depth=6, seconds=15):
    raw = Path(os.path.abspath(os.path.expanduser(str(root))))
    # Reject links in every component, not just the selected root.
    if any(p.is_symlink() for p in (raw, *raw.parents)):
        raise ValueError("Root or ancestor is a symlink")
    root = raw.resolve(strict=True)
    if not root.is_dir() or root == Path('/'):
        raise ValueError("Choose a scoped project directory")
    device = root.stat().st_dev
    deadline = time.monotonic() + seconds
    stack = [(root, 0)]
    candidates, errors = [], []
    count, truncated = 0, False
    while stack:
        if time.monotonic() >= deadline:
            truncated = True
            break
        parent, depth = stack.pop()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    count += 1
                    if count > max_entries or time.monotonic() >= deadline:
                        truncated = True
                        break
                    if entry.name.startswith('.') or entry.is_symlink():
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    path = Path(entry.path)
                    stat = entry.stat(follow_symlinks=False)
                    if stat.st_dev != device:
                        continue
                    marker = {'target': 'Cargo.toml', 'node_modules': 'package.json'}.get(entry.name)
                    if marker and (parent / marker).is_file() and not (parent / marker).is_symlink():
                        candidates.append({"path": str(path), "kind": entry.name,
                            "mtime": stat.st_mtime, "device": stat.st_dev,
                            "inode": stat.st_ino, "activity": "unknown",
                            "eligible_for_deletion": False,
                            "reason": "Manifest found; requires activity and owner review"})
                        continue
                    # Never descend into dependencies/build output or app bundles.
                    if entry.name in ('target', 'node_modules') or path.suffix in ('.app', '.photoslibrary', '.bundle'):
                        continue
                    if depth < max_depth:
                        stack.append((path, depth + 1))
                    else:
                        truncated = True
        except OSError as exc:
            errors.append({"path": str(parent), "error": str(exc)})
        if count > max_entries:
            break
    return {"root": str(root), "entries_seen": count, "truncated": truncated,
            "errors": errors, "candidates": candidates,
            "note": "Directory mtime is not last use. No files were changed."}


def snapshot():
    if platform.system() != 'Darwin':
        raise RuntimeError('Run on the user Mac through Latch, not the Linux agent container')
    usage = shutil.disk_usage(Path.home())
    cmds = {
        'os': ['sw_vers'], 'uptime': ['uptime'],
        'memory': ['vm_stat'], 'memory_pressure': ['memory_pressure'],
        'memory_bytes': ['sysctl', '-n', 'hw.memsize'],
        'battery': ['pmset', '-g', 'batt'],
    }
    return {"sampled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "platform": 'macOS', "disk": {"total_bytes": usage.total,
            "free_bytes": usage.free, "free_percent": round(usage.free / usage.total * 100, 2)},
            "metrics": {key: command(value) for key, value in cmds.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects', action='append', default=[], help='Approved project root; repeatable')
    args = parser.parse_args()
    try:
        result = snapshot()
        result['projects'] = [inventory(root) for root in args.projects]
    except (RuntimeError, ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
