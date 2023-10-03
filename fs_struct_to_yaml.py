"""File Structure to YAML, a separate file for each directory

Usage:
  fs_structure_to_yaml.py <start_directory>
  fs_structure_to_yaml.py -h | --help

Options:
  -h --help     Show this help message and exit.
"""

# TODO: change yaml structure - remove first item.

# TODO: add smart update - load, compare, and update to up to day state

# TODO: add simple update function:
#       varios modes: update all date, update all md5

import os
import yaml
import hashlib
from pathlib import Path
from docopt import docopt
from datetime import datetime

g_yaml_name = 'index_hash.yaml'
g_chuck_size = 65536
g_ignore_linux_hide_files = True


def time_trim_ms(t: datetime or float or int):
    if type(t) == float:
        return int(t)
    elif type(t) == datetime:
        return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)
    return t


def update_record(r: dict, data: Path) -> dict:
    """
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
        if (r.get('size', -1) != data.stat().st_size or
                r.get('ctime', 0) != time_trim_ms(data.stat().st_ctime) or
                r.get('mtime', 0) != time_trim_ms(data.stat().st_mtime)):
            # if date change - recalc hash
            r['md5'] = calculate_md5(data)
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

    r['ctime'] = time_trim_ms(data.stat().st_ctime)
    r['mtime'] = time_trim_ms(data.stat().st_mtime)
    return r


def create_file_structure(path: Path):
    yaml_path = path / g_yaml_name
    yaml_loaded = False

    # Load the existing YAML file if it exists
    if yaml_path.exists():
        with open(yaml_path, 'r') as f:
            try:
                file_structure = yaml.safe_load(f)
                yaml_loaded = True
            except yaml.YAMLError as e:
                print(f"Error loading existing YAML file {yaml_path}: {e}")
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

        if not (item.name in file_structure):
            # add
            print('add:', item.name)
            file_structure[item.name] = update_record({}, item)
        else:
            # update
            print('update:', item.name)
            file_structure[item.name] = update_record(file_structure[item.name], item)

    # Remove items that were not encountered in the current directory
    for item_to_delete in items_to_delete:
        del file_structure[item_to_delete]

    if yaml_loaded:
        # print('SKIP(EXISTS):', str(yaml_path))
        print('SAVE UPDATED:', str(yaml_path))
    else:
        print('SAVE NEW:', str(yaml_path))

    # Save the updated structure to the YAML file
    save_to_yaml(file_structure, yaml_path)

    # Search directory in list (for recursion)
    for name, content in file_structure.items():
        if content['type'] == 'dir':
            dir_path = path / name
            # Recursion
            create_file_structure(dir_path)
        file_structure[name] = None  # remove item from memory (for optimization)


def calculate_md5(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(g_chuck_size):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


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


def main():
    arguments = docopt(__doc__)

    start_directory = arguments['<start_directory>']
    start_path = Path(start_directory)

    if start_path.exists() and start_path.is_dir():
        create_file_structure(start_path)
    else:
        print("The specified path does not exist or is not a directory.")


if __name__ == "__main__":
    main()
