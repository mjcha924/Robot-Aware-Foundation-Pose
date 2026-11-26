"""Source snapshot identity recorded next to training and evaluation outputs."""
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source_snapshot(root=ROOT):
    """Commit plus a hash of uncommitted tracked changes (None when clean).

    Untracked files are listed by name only. Returns unknown values instead of
    failing when git is unavailable, so a missing git never blocks training.
    """
    def git(*args):
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True).stdout
    try:
        commit = git('rev-parse', 'HEAD').decode().strip()
        diff = git('diff', 'HEAD', '--binary')
        untracked = git('ls-files', '--others', '--exclude-standard').decode().split()
    except (OSError, subprocess.CalledProcessError):
        return dict(source_commit=None, source_dirty_diff_sha256=None, source_untracked=None)
    return dict(source_commit=commit,
                source_dirty_diff_sha256=hashlib.sha256(diff).hexdigest() if diff else None,
                source_untracked=untracked)
