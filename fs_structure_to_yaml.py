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

g_yaml_name = 'index_hash.yaml'
g_chuck_size = 65536
g_ignore_linux_hide_files = True

def create_file_structure(path: Path):
    yaml_path = path / g_yaml_name

    # TODO: change yaml structure
    file_structure = {
        'type': 'directory',
        'name': path.name,
        'contents': {},
        'ctime': path.stat().st_ctime,
        'mtime': path.stat().st_mtime,
    }

    # iterate files and collect information
    for item in path.iterdir():
        # TODO: use `igittigitt` library for ignore
        if (
           (item.is_dir() and item.name == '.git') or
           (item.name.startswith('.') and g_ignore_linux_hide_files) or
           (item.is_file() and item.name == g_yaml_name)
           ):
            print('IGNORE:', item)
            continue

        if item.is_dir():
            file_structure['contents'][item.name] = {
                'type': 'directory',
                'ctime': item.stat().st_ctime,
                'mtime': item.stat().st_mtime,
            }
        else:
            file_structure['contents'][item.name] = {
                'type': 'symlink' if item.is_symlink() else 'file',
                'size': item.stat().st_size,
                'md5': calculate_md5(item),
                'ctime': item.stat().st_ctime,
                'mtime': item.stat().st_mtime,
            }

    if yaml_path.exists():
        print('SKIP(EXISTS):', str(yaml_path))
    else:
        print('SAVE:', str(yaml_path))
        save_to_yaml(file_structure, yaml_path)

    # Search directory in list (for recursion)
    for name, content in file_structure['contents'].items():
        if content['type'] == 'directory':
            dir_path = path / name
            # Recursion
            create_file_structure(dir_path)
        file_structure['contents'][name] = None  # remove item from memory (for optimization)


def calculate_md5(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(g_chuck_size):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()

def save_to_yaml(data, output_file):
    with open(output_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)

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
