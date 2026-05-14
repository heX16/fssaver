"""
Verify file content MD5 against a saved YAML index (stdout logs problems only).

Progress: one tqdm bar on stderr counts index file entries being checked; disabled when
stderr is not a TTY (e.g. captured subprocess output).

Usage:
  fss_check.py (--fss=<yaml> [--snapshot-base=<path>] [--fssdir=<path>] | --dir=<path>) [--retries=<retries>] [--retries-pause=<retries-pause>] [--skip-not-available]
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

Exit codes:
  0  All checked entries with stored md5 matched disk (or skipped).
  1  At least one mismatch, missing path (unless --skip-not-available), or read error.
  2  Invalid usage or YAML could not be loaded.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

from docopt import docopt
from tqdm import tqdm

from fss_utils import load_yaml
from fss_save import read_file_and_calculate_md5_retry

g_yaml_name = '.index_hash.yaml'

SKIP_TYPES = frozenset({'error', 'hardcoded_skip', 'unknown'})


def resolve_disk_path(key: str, base_dir: Path) -> Path:
    entry_path = Path(key)
    if entry_path.is_absolute():
        return entry_path
    return base_dir / entry_path


def iter_index_file_entries(data: dict) -> Iterator[tuple[str, dict, str]]:
    """Yield (key, meta, expected_md5_lower) for each index row that check_index verifies."""
    if not data:
        return
    for key in sorted(data.keys()):
        meta = data[key]
        if not isinstance(meta, dict):
            continue

        entry_type = meta.get('type', '')
        if entry_type in SKIP_TYPES:
            continue
        if entry_type != 'file':
            continue
        if meta.get('error') is True:
            continue

        expected = meta.get('md5')
        if not expected:
            continue

        expected_l = str(expected).strip().lower()
        yield key, meta, expected_l


def check_index(
    data: dict,
    base_dir: Path,
    retries: int,
    retries_pause: float,
    skip_missing: bool = False,
    pbar: tqdm | None = None,
) -> int:
    """
    Compare stored md5 for file entries against disk. Prints issues to stdout.

    Returns:
        Number of problems reported.
    """
    issues = 0
    if not data:
        return issues

    for key, meta, expected_l in iter_index_file_entries(data):
        try:
            disk_path = resolve_disk_path(key, base_dir)

            if not disk_path.exists():
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
                issues += 1
                continue

            if actual_l != expected_l:
                yaml_size = meta.get('size', '')
                print(
                    f'MD5_MISMATCH\t{disk_path}\texpected={expected_l}\tactual={actual_l}'
                    f'\tyaml_size={yaml_size}\tdisk_size={st_size}'
                )
                issues += 1
        finally:
            if pbar is not None:
                pbar.update(1)

    return issues


def run_fss_mode(
    fss_path: Path,
    snapshot_base_arg: str | None,
    retries: int,
    retries_pause: float,
    skip_missing: bool,
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
    with tqdm(
        total=total,
        unit='file',
        file=sys.stderr,
        disable=not sys.stderr.isatty(),
    ) as bar:
        n = check_index(data, base_dir, retries, retries_pause, skip_missing=skip_missing, pbar=bar)
    return 1 if n else 0


def run_dir_mode(dir_path: Path, retries: int, retries_pause: float, skip_missing: bool) -> int:
    root = dir_path.resolve()
    if not root.is_dir():
        print(f'ERROR: not a directory: {root}')
        return 2

    yaml_files = sorted(root.rglob(g_yaml_name))
    if not yaml_files:
        print(f'ERROR: no {g_yaml_name!r} files under {root}')
        return 2

    grand_total = 0
    for yaml_file in yaml_files:
        data = load_yaml(yaml_file, retries=retries, retries_pause=retries_pause, return_on_fail=None)
        if data is None:
            print(f'ERROR: could not load YAML: {yaml_file}')
            return 2
        grand_total += sum(1 for _ in iter_index_file_entries(data))

    total_issues = 0
    with tqdm(
        total=grand_total,
        unit='file',
        file=sys.stderr,
        disable=not sys.stderr.isatty(),
    ) as bar:
        for yaml_file in yaml_files:
            data = load_yaml(yaml_file, retries=retries, retries_pause=retries_pause, return_on_fail=None)
            if data is None:
                print(f'ERROR: could not load YAML: {yaml_file}')
                return 2
            base_dir = yaml_file.parent
            total_issues += check_index(
                data, base_dir, retries, retries_pause, skip_missing=skip_missing, pbar=bar
            )

    return 1 if total_issues else 0


def main() -> int:
    arguments = docopt(__doc__)
    retries = int(arguments['--retries'] or 1)
    retries_pause = float(arguments['--retries-pause'] or 1)
    skip_missing = bool(arguments['--skip-not-available'])

    if arguments['--fss']:
        fss_path = Path(arguments['--fss']).expanduser()
        snapshot_base_arg = arguments['--snapshot-base'] or arguments['--fssdir']
        return run_fss_mode(fss_path, snapshot_base_arg, retries, retries_pause, skip_missing)

    dir_arg = arguments['--dir']
    assert dir_arg
    return run_dir_mode(Path(dir_arg).expanduser(), retries, retries_pause, skip_missing)


if __name__ == '__main__':
    raise SystemExit(main())
