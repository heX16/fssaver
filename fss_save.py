"""
File Structure to YAML, a separate file for each directory

Usage:
  fs_structure_to_yaml.py <start_directory> [--no-recursion] [--no-update-md5] [--exif=<exif>] [--print-stat=<print-stat>] [--retries=<retries>] [--retries-pause=<retries-pause>]
  fs_structure_to_yaml.py -h | --help

Options:
  -h --help        Show this help message and exit.
  --no-update-md5  Don't update MD5 if data changed
  --no-recursion   Do not recurse into directories.
  --exif=<exif>    Enable EXIF extraction for JPG/JPEG files [default: 1]. Use 0/false/no/off to disable.
  --print-stat=<print-stat>  Print STATS summary at the end [default: 1]. Use 0 to disable.
  --retries=<retries>     Number of retries for reading files [default: 1].
  --retries-pause=<retries-pause>         Pause duration between retries in seconds [default: 1].
"""

import os
from dataclasses import dataclass
from typing import Tuple
import yaml
import hashlib
from pathlib import Path
from docopt import docopt
from datetime import datetime, timezone
from fss_utils import *


@dataclass
class FssSaveStats:
    yaml_updated: int = 0
    yaml_write_error: int = 0
    yaml_corrupt_rebuilt: int = 0
    yaml_unchanged_skipped: int = 0
    empty_dirs: int = 0

    def print_summary(self) -> None:
        print('STATS:')
        print(f'  updated: {self.yaml_updated}')
        print(f'  unchanged: {self.yaml_unchanged_skipped}')
        print(f'  write_errors: {self.yaml_write_error}')
        print(f'  corrupt_rebuilt: {self.yaml_corrupt_rebuilt}')
        print(f'  empty_dirs: {self.empty_dirs}')

g_chuck_size = 65536
g_exif_enabled = True


def filter_dir(path: Path) -> bool:
    # TODO: add more flexibility
    if path.is_dir() and (path.name == 'System Volume Information' or path.name == '$RECYCLE.BIN'):
        return True
    return False


def update_record(r: dict, data: Path, no_update_md5: bool, retries: int, retries_pause: float) -> dict:
    """
    Updates the record dictionary with file or directory information.

    Args:
        r (dict): The existing record dictionary.
        data (Path): The file or directory path.

    Returns:
        dict: Updated record dictionary.

    Info:
        'file' or 'dir' record:
            type: str = dir|file|unknown|error
            ctime: str
            mtime: str
            symlink: bool = True|False(field not present)
            error: str
        'file':
            md5: str
            size: int
            zeros: bool = True|False(field not present)
        'dir':
            contents[]: list
    """
    data_stat = data.stat()

    if data.is_dir():
        r['type'] = 'dir'
        dict_del_item(r, 'size')
        dict_del_item(r, 'md5')
        dict_del_item(r, 'zeros')
        if filter_dir(data):
            r = {'type': 'hardcoded_skip'}
            return r
    elif data.is_file():
        r['type'] = 'file'
        dict_del_item(r, 'contents')

        ctime = time_to_iso8601_gmt_str(time_trim_ms(data_stat.st_ctime))
        mtime = time_to_iso8601_gmt_str(time_trim_ms(data_stat.st_mtime))

        # TODO: add `if md5 not present: ...`
        if (r.get('size', -1) != data_stat.st_size or
           (not no_update_md5 and (
           r.get('ctime', '') != ctime or
           r.get('mtime', '') != mtime))):

            # If dates or size changed, recalculate hash
            if data_stat.st_size > 0:
                md5, zeros = read_file_and_calculate_md5_retry(data, retries, retries_pause)
                if md5 != False:
                    r['md5'] = md5
                    dict_del_item(r, 'error')
                else:
                    dict_del_item(r, 'md5')
                    r['error'] = True

                if zeros:
                    r['zeros'] = True
                else:
                    dict_del_item(r, 'zeros')
            else:
                dict_del_item(r, 'md5')
                dict_del_item(r, 'zeros')

        r['size'] = data_stat.st_size
    else:
        r['type'] = 'unknown'
        return r

    if data.is_symlink():
        r['symlink'] = True
    else:
        dict_del_item(r, 'symlink')

    r['ctime'] = time_to_iso8601_gmt_str(time_trim_ms(data_stat.st_ctime))
    r['mtime'] = time_to_iso8601_gmt_str(time_trim_ms(data_stat.st_mtime))

    # Linux-specific attributes: permissions (mod) and owner (own)
    if is_linux():
        # Permissions as a 3-digit octal string, e.g. '755'
        try:
            r['mod'] = f'{data_stat.st_mode & 0o777:03o}'
        except Exception:
            dict_del_item(r, 'mod')

        # Owner in format 'user:group', resolving names when possible
        try:
            import pwd
            import grp

            try:
                user = pwd.getpwuid(data_stat.st_uid).pw_name
            except KeyError:
                user = str(data_stat.st_uid)

            try:
                group = grp.getgrgid(data_stat.st_gid).gr_name
            except KeyError:
                group = str(data_stat.st_gid)

            r['own'] = f'{user}:{group}'
        except Exception:
            dict_del_item(r, 'own')

    add_extra_info_to_record(r, data)

    return r


def create_file_structure(
    dir_path: Path,
    stats: FssSaveStats,
    no_update_md5: bool = False,
    recursion: bool = True,
    retries: int = 1,
    retries_pause: int = 1,
):
    if filter_dir(dir_path):
        print('HARDCODED SKIP:', str(dir_path))
        return

    yaml_path = dir_path / g_yaml_name
    yaml_loaded = False

    # Load the existing YAML file if it exists
    if yaml_path.exists():
        file_structure = load_yaml(
            yaml_path,
            retries=retries,
            retries_pause=retries_pause,
            return_on_fail={},
        )
        if not isinstance(file_structure, dict):
            print(f'WARN: invalid/corrupt FSS index, rebuilding from disk: {yaml_path}')
            file_structure = {}
            stats.yaml_corrupt_rebuilt += 1
        elif yaml_path.stat().st_size > 0 and file_structure == {}:
            # Parse failure returns return_on_fail={}; non-empty file is a strong signal.
            print(f'WARN: corrupt FSS index, rebuilding from disk: {yaml_path}')
            stats.yaml_corrupt_rebuilt += 1
        else:
            yaml_loaded = True
    else:
        file_structure = {}

    # Create a copy of the existing structure to track items to delete
    items_to_delete = list(file_structure.keys())

    # Iterate files and collect information
    for item in dir_path.iterdir():

        if should_ignore_dir_item(item):
            # TODO: print('ignore:', item)  - command line argument options
            # TODO: calc to stats
            continue

        if item.name in items_to_delete:
            items_to_delete.remove(item.name)

        if item.name not in file_structure:
            # Add new item
            print('add:', item.name)
            file_structure[item.name] = update_record({}, item, no_update_md5, retries, retries_pause)
        else:
            # Update existing item
            #print('update:', item.name)
            file_structure[item.name] = update_record(file_structure[item.name], item, no_update_md5, retries, retries_pause)

    # Remove items that were not encountered in the current directory
    for item_to_delete in items_to_delete:
        del file_structure[item_to_delete]


    # Save the updated structure to the YAML file
    write_failed = False
    index_removed = False
    if len(file_structure) == 0:
        stats.empty_dirs += 1
        if yaml_path.exists():
            try:
                yaml_path.unlink()
                saved = True
                index_removed = True
            except OSError as exc:
                stats.yaml_write_error += 1
                write_failed = True
                print(f'SAVE ERROR: {yaml_path} ({exc})')
                saved = False
        else:
            saved = False
    else:
        try:
            saved = save_to_yaml(file_structure, yaml_path, retries=retries, retries_pause=retries_pause)
        except OSError as exc:
            stats.yaml_write_error += 1
            write_failed = True
            print(f'SAVE ERROR: {yaml_path} ({exc})')
            saved = False

    if saved:
        stats.yaml_updated += 1
        if index_removed:
            print('DELETE INDEX:', str(yaml_path))
        elif yaml_loaded:
            print('SAVE UPDATED:', str(yaml_path))
        else:
            print('SAVE NEW:', str(yaml_path))
    elif len(file_structure) > 0 and not write_failed:
        stats.yaml_unchanged_skipped += 1

    # Search directory in list (for recursion)
    for name, content in file_structure.items():
        if content['type'] == 'dir':
            if recursion:
                dir_path_recursion = dir_path / name
                if dir_path_recursion.exists() and dir_path_recursion.is_dir():
                    # Recursion!
                    create_file_structure(
                        dir_path_recursion,
                        stats,
                        no_update_md5=no_update_md5,
                        recursion=recursion,
                        retries=retries,
                        retries_pause=retries_pause,
                    )
                else:
                    print('SKIP NON-EXISTENT DIR:', str(dir_path_recursion))
        file_structure[name] = None  # remove item from memory (for optimization)


def read_file_and_calculate_md5(file_path: Path) -> Tuple[str, bool]:
    """
    Calculate the MD5 hash of a file.

    :param file_path: Path to the file.
    :return: MD5 hash of the file and zero flag
    """
    is_zero = True
    md5_hash = hashlib.md5()
    if file_path.stat().st_size > 0:
        with open(file_path, 'rb') as f:
            while chunk := f.read(g_chuck_size):
                if len(chunk) != chunk.count(b'\x00'):
                    is_zero = False
                md5_hash.update(chunk)
        return (md5_hash.hexdigest(), is_zero)
    return ('', False)


def read_file_and_calculate_md5_retry(file_path: Path, retries: int, retries_pause: float) -> Tuple[str, bool]:
    """
    Calculate the MD5 hash of a file with retries on transient :exc:`OSError` (see
    :class:`WhileWithRetryIO` in ``fss_utils``). Missing path fails fast without retries.

    :param file_path: Path to the file.
    :param retries: Number of *extra* attempts after the first try (same as :class:`WhileWithRetry`).
    :param retries_pause: Pause duration between retries in seconds.
    :return: MD5 hash of the file and zero flag, or ``('', False)`` after final I/O failure.
    """
    r = WhileWithRetryIO(
        file_path,
        int(retries_pause),
        retries=retries,
        pause_sec=float(retries_pause),
    )
    result: Tuple[str, bool] | None = None
    while r:
        with r.attempt():
            result = read_file_and_calculate_md5(file_path)
    if r.outcome == 'ok':
        assert result is not None
        return result
    return ('', False)


def add_extra_info_to_record(record: dict, path: Path) -> None:
    global g_exif_enabled

    if not g_exif_enabled:
        return

    if not path.is_file():
        return

    ext = path.suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        add_exif_info_to_record(record, path)


def main():
    global g_exif_enabled

    arguments = docopt(__doc__)

    start_directory = arguments['<start_directory>']
    recursion = not bool(arguments['--no-recursion'])
    retries = int(arguments['--retries'])
    retries_pause = int(arguments['--retries-pause'])
    start_path = Path(start_directory)
    no_update_md5 = bool(arguments['--no-update-md5'])
    g_exif_enabled = arguments.get('--exif', '1') != '0'
    print_stat = arguments.get('--print-stat', '1') != '0'

    if start_path.exists() and start_path.is_dir():
        stats = FssSaveStats()
        create_file_structure(
            start_path,
            stats,
            no_update_md5=no_update_md5,
            recursion=recursion,
            retries=retries,
            retries_pause=retries_pause,
        )
        if print_stat:
            stats.print_summary()
    else:
        print('The specified path does not exist or is not a directory.')


if __name__ == '__main__':
    main()
