"""
Verify file content MD5 against a saved YAML index (stdout logs problems only).

On normal exit (0 or 1), a one-line summary is printed to stderr (checked, missing, md5_mismatch,
read_error, issues). Progress bars also use stderr.

Progress: one tqdm bar on stderr counts index file entries being checked (--fss). In --dir mode,
when the bar is enabled, a first bar may count YAML indexes per top-level subdirectory under the
root, then a second bar advances once per .index_hash.yaml verified. Bars are off when stderr is
not a TTY (e.g. captured subprocess output), or when you pass --no-progress-bar or --bar=0.

Usage:
  fss_check.py (--fss=<yaml> [--snapshot-base=<path>] [--fssdir=<path>] | --dir=<path>) [--retries=<retries>] [--retries-pause=<retries-pause>] [--skip-not-available] [--bar=<n>] [--no-progress-bar]
  fss_check.py -h | --help

Options:
  -h --help                         Show this help message and exit.
  --fss=<yaml>                      Path to YAML index (merged snapshot or per-directory .index_hash.yaml).
  --snapshot-base=<path>            Directory that merged YAML paths are relative to (same as merge start directory). Required unless --fss basename is .index_hash.yaml (then base is the YAML parent).
  --fssdir=<path>                   Alias for --snapshot-base (if both are set, --snapshot-base wins).
  --dir=<path>                      Recursively find and check every .index_hash.yaml under this directory.
  --retries=<retries>               File read retries [default: 1].
  --retries-pause=<retries-pause>   Pause between retries in seconds [default: 1].
  --skip-not-available              If a path from the index does not exist on disk, skip it (no log line, not counted as failure).
  --bar=<n>                         Progress bar: 1 when stderr is a TTY (default if omitted), 0 to disable the bar even on a TTY [default: 1].
  --no-progress-bar                 Disable the tqdm progress bar (same effect as --bar=0).

Exit codes:
  0  All checked entries with stored md5 matched disk (or skipped).
  1  At least one mismatch, missing path (unless --skip-not-available), or read error.
  2  Invalid usage or YAML could not be loaded.
"""

from __future__ import annotations

import sys
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from docopt import docopt
from tqdm import tqdm

from fss_utils import count_matching_files_with_topdir_progress, iter_index_file_entries, load_yaml
from fss_save import read_file_and_calculate_md5_retry

g_yaml_name = '.index_hash.yaml'


@dataclass
class CheckStats:
    checked: int = 0
    missing: int = 0
    md5_mismatch: int = 0
    read_error: int = 0

    def merge(self, other: CheckStats) -> None:
        self.checked += other.checked
        self.missing += other.missing
        self.md5_mismatch += other.md5_mismatch
        self.read_error += other.read_error


def print_summary(stats: CheckStats, issues: int) -> None:
    print(
        f'Summary: checked={stats.checked} missing={stats.missing} '
        f'md5_mismatch={stats.md5_mismatch} read_error={stats.read_error} issues={issues}',
        file=sys.stderr,
    )


def resolve_disk_path(key: str, base_dir: Path) -> Path:
    entry_path = Path(key)
    if entry_path.is_absolute():
        return entry_path
    return base_dir / entry_path


def check_index(
    data: dict,
    base_dir: Path,
    retries: int,
    retries_pause: float,
    skip_missing: bool = False,
    pbar: tqdm | None = None,
) -> tuple[int, CheckStats]:
    """
    Compare stored md5 for file entries against disk. Prints issues to stdout.

    Returns:
        (Number of problems reported, accumulated CheckStats).
    """
    issues = 0
    stats = CheckStats()
    if not data:
        return issues, stats

    for key, meta, expected_l in iter_index_file_entries(data):
        try:
            disk_path = resolve_disk_path(key, base_dir)

            if not disk_path.exists():
                stats.missing += 1
                if skip_missing:
                    continue
                print(f'MISSING\t{disk_path}\texpected_md5={expected_l}')
                issues += 1
                continue

            if not disk_path.is_file():
                print(f'NOT_A_FILE\t{disk_path}\texpected_md5={expected_l}')
                issues += 1
                continue

            try:
                st_size = disk_path.stat().st_size
            except OSError as e:
                print(f'STAT_ERROR\t{disk_path}\t{e}')
                issues += 1
                continue

            actual, _zeros = read_file_and_calculate_md5_retry(disk_path, retries, retries_pause)
            actual_l = (actual or '').strip().lower()

            if st_size > 0 and len(actual_l) != 32:
                print(f'READ_ERROR\t{disk_path}\texpected_md5={expected_l}')
                stats.read_error += 1
                issues += 1
                continue

            stats.checked += 1
            if actual_l != expected_l:
                stats.md5_mismatch += 1
                yaml_size = meta.get('size', '')
                print(
                    f'MD5_MISMATCH\t{disk_path}\texpected={expected_l}\tactual={actual_l}'
                    f'\tyaml_size={yaml_size}\tdisk_size={st_size}'
                )
                issues += 1
        finally:
            if pbar is not None:
                pbar.update(1)

    return issues, stats


def run_fss_mode(
    fss_path: Path,
    snapshot_base_arg: str | None,
    retries: int,
    retries_pause: float,
    skip_missing: bool,
    show_progress_bar: bool,
) -> int:
    if fss_path.name != g_yaml_name and not snapshot_base_arg:
        print(
            f'ERROR: --snapshot-base (or --fssdir) is required when --fss is not named {g_yaml_name!r} '
            f'(merged index keys are relative to that directory).'
        )
        return 2

    if fss_path.name == g_yaml_name:
        base_dir = fss_path.parent
    else:
        base_dir = Path(snapshot_base_arg).resolve()

    data = load_yaml(fss_path, retries=retries, retries_pause=retries_pause, return_on_fail=None)
    if data is None:
        print(f'ERROR: could not load YAML: {fss_path}')
        return 2

    total = sum(1 for _ in iter_index_file_entries(data))

    if show_progress_bar:
        bar_cm = tqdm(total=total, unit='file', file=sys.stderr, disable=False)
    else:
        bar_cm = nullcontext(None)

    with bar_cm as bar:
        n, stats = check_index(data, base_dir, retries, retries_pause, skip_missing=skip_missing, pbar=bar)

    print_summary(stats, n)
    return 1 if n else 0


def run_dir_mode(
    dir_path: Path,
    retries: int,
    retries_pause: float,
    skip_missing: bool,
    show_progress_bar: bool,
) -> int:
    root = dir_path.resolve()
    if not root.is_dir():
        print(f'ERROR: not a directory: {root}')
        return 2

    issues = 0
    stats = CheckStats()
    seen_any = False

    if show_progress_bar:
        total_yaml = count_matching_files_with_topdir_progress(
            root, g_yaml_name, progress_stream=sys.stderr
        )
        if total_yaml == 0:
            print(f'ERROR: no {g_yaml_name!r} files under {root}')
            return 2
        bar_cm = tqdm(total=total_yaml, unit='file', desc='Verifying', file=sys.stderr)
    else:
        bar_cm = nullcontext(None)

    with bar_cm as pbar:
        for yaml_file in root.rglob(g_yaml_name):
            seen_any = True

            data = load_yaml(yaml_file, retries=retries, retries_pause=retries_pause, return_on_fail=None)

            if data is None:
                print(f'ERROR: could not load YAML: {yaml_file}')
                return 2

            n, index_stats = check_index(
                data,
                yaml_file.parent,
                retries,
                retries_pause,
                skip_missing=skip_missing,
                pbar=None,
            )
            issues += n
            stats.merge(index_stats)
            if pbar is not None:
                pbar.update(1)

    if not show_progress_bar and not seen_any:
        print(f'ERROR: no {g_yaml_name!r} files under {root}')
        return 2

    print_summary(stats, issues)
    return 1 if issues else 0


def main() -> int:
    arguments = docopt(__doc__)
    retries = int(arguments['--retries'] or 1)
    retries_pause = float(arguments['--retries-pause'] or 1)
    skip_missing = bool(arguments['--skip-not-available'])

    bar_raw = arguments['--bar']
    try:
        bar_n = int(bar_raw) if bar_raw is not None else 1
    except ValueError:
        print('ERROR: --bar must be an integer (e.g. 0 or 1)')
        return 2

    show_bar = (
        sys.stderr.isatty()
        and not bool(arguments['--no-progress-bar'])
        and bar_n != 0
    )

    if arguments['--fss']:
        fss_path = Path(arguments['--fss']).expanduser()
        snapshot_base_arg = arguments['--snapshot-base'] or arguments['--fssdir']
        return run_fss_mode(fss_path, snapshot_base_arg, retries, retries_pause, skip_missing, show_bar)

    dir_arg = arguments['--dir']
    assert dir_arg
    return run_dir_mode(Path(dir_arg).expanduser(), retries, retries_pause, skip_missing, show_bar)


if __name__ == '__main__':
    raise SystemExit(main())
