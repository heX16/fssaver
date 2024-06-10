"""
File Structure to YAML, a separate file for each directory

Usage:
  fs_structure_to_yaml.py <start_directory> [--retries=<retries>] [--retries-pause=<retries-pause>] [--no-recursion]
  fs_structure_to_yaml.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --no-recursion  Do not recurse into directories.
  --retries=<retries>     Number of retries for reading files [default: 1].
  --retries-pause=<retries-pause>         Pause duration between retries in seconds [default: 1].
"""

# TODO: search silent changes. add recheck MD5 for unchanged files and warnings if file corrupted

# TODO: add flag: "-i" (ignore all)
# TODO: add flag: "--ignore-linux-hide"
# TODO: add flag: "--ignore-wnd-hide"

# TODO: add simple update function:
#       various modes: update all date, update MD5

import os
import yaml
import hashlib
from pathlib import Path
from docopt import docopt
from datetime import datetime, timezone
import time

g_yaml_name = '.index_hash.yaml'
g_chuck_size = 65536
g_ignore_linux_hide_files = True


def time_to_iso8601_gmt_str(t: datetime or float or int, separator='_'):
    if isinstance(t, (float, int)):
        return datetime.fromtimestamp(t, tz=timezone.utc).strftime(f'%Y-%m-%d{separator}%H:%M:%SZ')
    elif isinstance(t, datetime):
        return t.astimezone(timezone.utc).strftime(f'%Y-%m-%d{separator}%H:%M:%SZ')

def time_trim_ms(t: datetime or float or int):
    if isinstance(t, float):
        return int(t)
    elif isinstance(t, datetime):
        return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)
    return t


def update_record(r: dict, data: Path, retries: int, retries_pause: float) -> dict:
    """
    Updates the record dictionary with file or directory information.

    Args:
        r (dict): The existing record dictionary.
        data (Path): The file or directory path.

    Returns:
        dict: Updated record dictionary.

    Info:
        all:
            type = dir|file|unknown|error
            ctime
            mtime
            symlink = True|_NotExist_
        file:
            md5
            size
        dir:
            contents
    """

    if data.is_dir():
        r['type'] = 'dir'
        if 'size' in r:
            del r['size']
        if 'md5' in r:
            del r['md5']
    elif data.is_file():
        r['type'] = 'file'
        ctime = time_to_iso8601_gmt_str(time_trim_ms(data.stat().st_ctime))
        mtime = time_to_iso8601_gmt_str(time_trim_ms(data.stat().st_mtime))
        if (r.get('size', -1) != data.stat().st_size or
                r.get('ctime', '') != ctime or
                r.get('mtime', '') != mtime):
            # If dates change, recalculate hash
            r['md5'] = read_file_and_calculate_md5_retry(data, retries, retries_pause)
        r['size'] = data.stat().st_size
        if 'contents' in r:
            del r['contents']
    else:
        r['type'] = 'unknown'
        return r

    if data.is_symlink():
        r['symlink'] = True
    else:
        if 'symlink' in r:
            del r['symlink']

    r['ctime'] = time_to_iso8601_gmt_str(time_trim_ms(data.stat().st_ctime))
    r['mtime'] = time_to_iso8601_gmt_str(time_trim_ms(data.stat().st_mtime))
    return r


def create_file_structure(path: Path, recursion: bool = True, retries: int = 1, retries_pause: int = 1):
    yaml_path = path / g_yaml_name
    yaml_loaded = False

    # Load the existing YAML file if it exists
    if yaml_path.exists():
        try:
            file_structure = load_yaml(yaml_path)
            yaml_loaded = True
        except yaml.YAMLError as e:
            print(f"Error loading existing YAML file {yaml_path}: {e}")
            return
        if file_structure == {}:
            return
    else:
        file_structure = {}

    # Create a copy of the existing structure to track items to delete
    items_to_delete = list(file_structure.keys())

    # Iterate files and collect information
    for item in path.iterdir():

        # Use igittigitt library for ignore (implement this if needed)
        if (
                (item.is_dir() and item.name == '.git') or
                (item.name.startswith('.') and g_ignore_linux_hide_files) or
                (item.name == g_yaml_name)
        ):
            print('ignore:', item)
            continue

        if item.name in items_to_delete:
            items_to_delete.remove(item.name)

        if item.name not in file_structure:
            # Add new item
            print('add:', item.name)
            file_structure[item.name] = update_record({}, item, retries, retries_pause)
        else:
            # Update existing item
            print('update:', item.name)
            file_structure[item.name] = update_record(file_structure[item.name], item, retries, retries_pause)

    # Remove items that were not encountered in the current directory
    for item_to_delete in items_to_delete:
        del file_structure[item_to_delete]

    if yaml_loaded:
        print('SAVE UPDATED:', str(yaml_path))
    else:
        print('SAVE NEW:', str(yaml_path))

    # Save the updated structure to the YAML file
    save_to_yaml(file_structure, yaml_path)

    # Search directory in list (for recursion)
    for name, content in file_structure.items():
        if content['type'] == 'dir':
            dir_path = path / name
            if recursion:
                # Recursion!
                create_file_structure(dir_path, recursion=recursion, retries=retries, retries_pause=retries_pause)
        file_structure[name] = None  # remove item from memory (for optimization)

def read_file_and_calculate_md5(file_path: Path) -> str:
    """
    Calculate the MD5 hash of a file.

    :param file_path: Path to the file.
    :return: MD5 hash of the file.
    """
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(g_chuck_size):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

def read_file_and_calculate_md5_retry(file_path: Path, retries: int, retries_pause: float) -> str:
    """
    Calculate the MD5 hash of a file with retry mechanism in case of PermissionError.

    :param file_path: Path to the file.
    :param retries: Number of retries for reading the file.
    :param retries_pause: Pause duration between retries in seconds.
    :return: MD5 hash of the file.
    """
    for attempt in range(retries + 1):
        try:
            return read_file_and_calculate_md5(file_path)
        except PermissionError:
            if attempt < retries:
                print(f"PermissionError encountered. Retrying in {retries_pause} seconds...")
                time.sleep(retries_pause)
            else:
                raise

def get_file_content(file_name, encoding='utf-8'):
    try:
        with open(file_name, 'r', encoding=encoding) as f:
            return str(f.read())
    except IOError:
        return ''


def save_to_yaml(data, output_file, encoding='utf-8'):
    data = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    if get_file_content(output_file, encoding=encoding) != data:
        with open(output_file, 'w', encoding=encoding) as f:
            f.write(data)


def load_yaml(input_file, encoding='utf-8'):
    try:
        with open(input_file, 'r', encoding=encoding) as f:
            store = yaml.safe_load(f)
            if store is None:
                store = {}
    except IOError as e:
        print(f"ERROR: I/O error({e.errno}): {e.strerror}")
        store = {}
    return store


def main():
    arguments = docopt(__doc__)

    start_directory = arguments['<start_directory>']
    recursion = not bool(arguments['--no-recursion'])
    retries = int(arguments['--retries'])
    retries_pause = int(arguments['--retries-pause'])
    start_path = Path(start_directory)

    if start_path.exists() and start_path.is_dir():
        create_file_structure(start_path, recursion=recursion, retries=retries, retries_pause=retries_pause)
    else:
        print("The specified path does not exist or is not a directory.")


if __name__ == "__main__":
    main()
