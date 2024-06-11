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

import os
import yaml
import hashlib
from pathlib import Path
from docopt import docopt
from datetime import datetime, timezone
import time
from fs_struct_utils import *

g_yaml_name = '.index_hash.yaml'
g_chuck_size = 65536
g_ignore_linux_hide_files = True

def update_record(r: dict, data: Path, retries: int, retries_pause: float) -> dict:
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
            zeros: bool = True|False(field not present)
        'file':
            md5: str
            size: int
        'dir':
            contents[]: list
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
            md5, zeros = read_file_and_calculate_md5_retry(data, retries, retries_pause)
            r['md5'] = md5
            if zeros:
                r['zeros'] = True
            else:
                if 'zeros' in r:
                    del r['zeros']
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
        file_structure = load_yaml(yaml_path)
        if file_structure == None:
            return
        yaml_loaded = True
    else:
        file_structure = {}

    # Create a copy of the existing structure to track items to delete
    items_to_delete = list(file_structure.keys())

    # Iterate files and collect information
    for item in path.iterdir():

        # TODO: Use igittigitt library for ignore
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


def read_file_and_calculate_md5(file_path: Path) -> (str, bool):
    """
    Calculate the MD5 hash of a file.

    :param file_path: Path to the file.
    :return: MD5 hash of the file and zero flag
    """
    is_zero = True
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(g_chuck_size):
            if len(chunk) != chunk.count(b'\x00'):
                is_zero = False
            md5_hash.update(chunk)
    return (md5_hash.hexdigest(), is_zero)

def read_file_and_calculate_md5_retry(file_path: Path, retries: int, retries_pause: float) -> (str, bool):
    """
    Calculate the MD5 hash of a file with retry mechanism in case of PermissionError.

    :param file_path: Path to the file.
    :param retries: Number of retries for reading the file.
    :param retries_pause: Pause duration between retries in seconds.
    :return: MD5 hash of the file and zero flag
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
