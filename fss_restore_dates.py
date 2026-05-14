"""
Restore file timestamps from the ``ctime`` field in a saved FSS YAML index.

Uses YAML ``ctime`` (UTC ``YYYY-MM-DD_HH:MM:SSZ``) as the source instant. Modes:
  ``ctime`` — apply to creation time via :func:`fss_utils.set_file_ctime`;
  ``mtime`` — apply to modification time via :func:`os.utime` (atime preserved);
  ``mtime,ctime`` — both (``os.utime`` first, then ``set_file_ctime``).

By default, index paths that are missing on disk are skipped silently. Use
``--strict-missing`` or ``--no-skip-not-available`` to log ``MISSING`` lines and count failures.

Progress: one tqdm bar on stderr counts index entries in ``--fss`` mode. In ``--dir`` mode,
when the bar is enabled, a first bar may count YAML indexes per top-level subdirectory, then a
second bar advances once per ``.index_hash.yaml`` processed. Bars are off when stderr is not a TTY,
or with ``--no-progress-bar`` / ``--bar=0``.

Usage:
  fss_restore_dates.py (--fss=<yaml> [--snapshot-base=<path>] [--fssdir=<path>] | --dir=<path>) --mode=<mode> [--retries=<retries>] [--retries-pause=<retries-pause>] [--strict-missing] [--no-skip-not-available] [--bar=<n>] [--no-progress-bar] [--dry-run]
  fss_restore_dates.py -h | --help

Options:
  -h --help                         Show this help message and exit.
  --fss=<yaml>                      Path to YAML index (merged snapshot or per-directory .index_hash.yaml).
  --snapshot-base=<path>            Directory that merged YAML paths are relative to. Required unless --fss basename is .index_hash.yaml (then base is the YAML parent).
  --fssdir=<path>                   Alias for --snapshot-base (if both are set, --snapshot-base wins).
  --dir=<path>                      Recursively find and process every .index_hash.yaml under this directory.
  --mode=<mode>                     One of: ctime, mtime, mtime,ctime (aliases: both, mtime+ctime for mtime,ctime).
  --retries=<retries>               YAML read retries [default: 1].
  --retries-pause=<retries-pause>   Pause between retries in seconds [default: 1].
  --strict-missing                  If a path from the index does not exist, log MISSING and count as failure.
  --no-skip-not-available           Same as --strict-missing (missing paths are not silently skipped).
  --bar=<n>                         Progress bar: 1 when stderr is a TTY (default if omitted), 0 to disable [default: 1].
  --no-progress-bar                 Disable tqdm (same as --bar=0).
  --dry-run                         Print planned APPLY lines only; do not change timestamps.

Exit codes:
  0  All applicable entries processed without errors (missing paths skipped unless strict).
  1  At least one parse error, set error, or missing path in strict mode.
  2  Invalid usage or YAML could not be loaded.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import nullcontext
from pathlib import Path

from docopt import docopt
from tqdm import tqdm

from fss_utils import (
    SKIP_TYPES,
    count_matching_files_with_topdir_progress,
    load_yaml,
    parse_fss_ctime_utc,
    set_file_ctime,
)

g_yaml_name = '.index_hash.yaml'


def resolve_disk_path(key: str, base_dir: Path) -> Path:
    entry_path = Path(key)
    if entry_path.is_absolute():
        return entry_path
    return base_dir / entry_path


def iter_index_file_entries_with_ctime(data: dict) -> Iterator[tuple[str, dict, str]]:
    """Yield (key, meta, ctime_raw) for each file row that has a non-empty ``ctime`` string."""
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

        ctime_raw = meta.get('ctime')
        if ctime_raw is None or str(ctime_raw).strip() == '':
            continue

        yield key, meta, str(ctime_raw).strip()


def parse_apply_modes(mode_arg: str) -> tuple[bool, bool]:
    """
    Return (apply_mtime, apply_ctime) flags from ``--mode`` value.

    Raises:
        ValueError: if the mode string is not recognized.
    """
    raw = (mode_arg or '').strip().lower().replace(' ', '')
    if raw in ('mtime,ctime', 'ctime,mtime', 'both', 'mtime+ctime'):
        return True, True
    if raw == 'mtime':
        return True, False
    if raw == 'ctime':
        return False, True
    raise ValueError(f'Unknown --mode={mode_arg!r}; expected ctime, mtime, or mtime,ctime')


def apply_yaml_ctime_to_disk(
    data: dict,
    base_dir: Path,
    *,
    apply_mtime: bool,
    apply_ctime: bool,
    strict_missing: bool,
    dry_run: bool,
    pbar: tqdm | None = None,
) -> int:
    """
    Apply timestamps from YAML to files under ``base_dir``.

    Returns:
        Number of problems (parse errors, missing in strict mode, set errors, not implemented ctime).
    """
    issues = 0
    if not data:
        return issues

    for key, _meta, ctime_raw in iter_index_file_entries_with_ctime(data):
        try:
            disk_path = resolve_disk_path(key, base_dir)

            if not disk_path.exists():
                if strict_missing:
                    print(f'MISSING\t{disk_path}')
                    issues += 1
                continue

            if not disk_path.is_file():
                print(f'NOT_A_FILE\t{disk_path}')
                issues += 1
                continue

            dt = parse_fss_ctime_utc(ctime_raw)
            if dt is None:
                print(f'PARSE_ERROR\t{disk_path}\tyaml_ctime={ctime_raw!r}')
                issues += 1
                continue

            print(f'APPLY\t{disk_path}\tmode={"mtime+ctime" if apply_mtime and apply_ctime else ("mtime" if apply_mtime else "ctime")}\tyaml_ctime={ctime_raw}')

            if dry_run:
                continue

            try:
                if apply_mtime:
                    st = disk_path.stat()
                    os.utime(disk_path, (st.st_atime, dt.timestamp()))

                if apply_ctime:
                    set_file_ctime(disk_path, dt)
            except NotImplementedError as e:
                print(f'SET_ERROR\t{disk_path}\t{e}')
                issues += 1
            except OSError as e:
                print(f'SET_ERROR\t{disk_path}\t{e}')
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
    strict_missing: bool,
    dry_run: bool,
    show_progress_bar: bool,
    apply_mtime: bool,
    apply_ctime: bool,
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

    total = sum(1 for _ in iter_index_file_entries_with_ctime(data))

    if show_progress_bar:
        bar_cm = tqdm(total=total, unit='file', file=sys.stderr, disable=False)
    else:
        bar_cm = nullcontext(None)

    with bar_cm as bar:
        n = apply_yaml_ctime_to_disk(
            data,
            base_dir,
            apply_mtime=apply_mtime,
            apply_ctime=apply_ctime,
            strict_missing=strict_missing,
            dry_run=dry_run,
            pbar=bar,
        )

    return 1 if n else 0


def run_dir_mode(
    dir_path: Path,
    retries: int,
    retries_pause: float,
    strict_missing: bool,
    dry_run: bool,
    show_progress_bar: bool,
    apply_mtime: bool,
    apply_ctime: bool,
) -> int:
    root = dir_path.resolve()
    if not root.is_dir():
        print(f'ERROR: not a directory: {root}')
        return 2

    issues = 0
    seen_any = False

    if show_progress_bar:
        total_yaml = count_matching_files_with_topdir_progress(
            root, g_yaml_name, progress_stream=sys.stderr
        )
        if total_yaml == 0:
            print(f'ERROR: no {g_yaml_name!r} files under {root}')
            return 2
        bar_cm = tqdm(total=total_yaml, unit='yaml', desc='Restoring', file=sys.stderr)
    else:
        bar_cm = nullcontext(None)

    with bar_cm as pbar:
        for yaml_file in root.rglob(g_yaml_name):
            seen_any = True

            data = load_yaml(yaml_file, retries=retries, retries_pause=retries_pause, return_on_fail=None)

            if data is None:
                print(f'ERROR: could not load YAML: {yaml_file}')
                return 2

            issues += apply_yaml_ctime_to_disk(
                data,
                yaml_file.parent,
                apply_mtime=apply_mtime,
                apply_ctime=apply_ctime,
                strict_missing=strict_missing,
                dry_run=dry_run,
                pbar=None,
            )
            if pbar is not None:
                pbar.update(1)

    if not show_progress_bar and not seen_any:
        print(f'ERROR: no {g_yaml_name!r} files under {root}')
        return 2

    return 1 if issues else 0


def main() -> int:
    arguments = docopt(__doc__)

    retries = int(arguments['--retries'] or 1)
    retries_pause = float(arguments['--retries-pause'] or 1)
    strict_missing = bool(arguments['--strict-missing'] or arguments['--no-skip-not-available'])
    dry_run = bool(arguments['--dry-run'])

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

    mode_arg = arguments['--mode']
    if not mode_arg:
        print('ERROR: --mode is required (ctime, mtime, or mtime,ctime)')
        return 2
    try:
        apply_mtime, apply_ctime = parse_apply_modes(str(mode_arg))
    except ValueError as e:
        print(f'ERROR: {e}')
        return 2

    if arguments['--fss']:
        fss_path = Path(arguments['--fss']).expanduser()
        snapshot_base_arg = arguments['--snapshot-base'] or arguments['--fssdir']
        return run_fss_mode(
            fss_path,
            snapshot_base_arg,
            retries,
            retries_pause,
            strict_missing,
            dry_run,
            show_bar,
            apply_mtime,
            apply_ctime,
        )

    dir_arg = arguments['--dir']
    assert dir_arg
    return run_dir_mode(
        Path(dir_arg).expanduser(),
        retries,
        retries_pause,
        strict_missing,
        dry_run,
        show_bar,
        apply_mtime,
        apply_ctime,
    )


if __name__ == '__main__':
    raise SystemExit(main())
