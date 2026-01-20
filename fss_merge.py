"""
File Structure to YAML

Usage:
  fs_struct_merge_to_once_yaml.py <start_directory> [--file=<yaml_file>] [--not-add-date] [--retries=<retries>] [--retries-pause=<retries-pause>]
  fs_struct_merge_to_once_yaml.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --file=<yaml_file> -f=<yaml_file>  Specify the YAML file name (default: 'index_hash_all.yaml').
  --not-add-date --nodate            Not add the current date in the YAML file name.
  --retries=<retries>                Number of retries for reading files [default: 1].
  --retries-pause=<retries-pause>    Pause duration between retries in seconds [default: 1].
"""

#TODO: add date to final file

import yaml
from pathlib import Path
from docopt import docopt
from datetime import datetime
import time
from fss_utils import *

g_yaml_name = '.index_hash.yaml'


def add_data_to_merged_data(
    merged_data: dict,
    file_data: dict,
    file_name: str,
    base_dir: Path,
    root_path: Path,
    retries: int,
    retries_pause: int,
):
    entry_path = Path(file_name)

    # Resolve absolute path of the entry based on where the current .index_hash.yaml lives.
    if entry_path.is_absolute():
        abs_entry_path = entry_path
    else:
        abs_entry_path = base_dir / entry_path

    # Store keys as paths relative to the start directory.
    relative_path = abs_entry_path.relative_to(root_path)
    merged_data[relative_path.as_posix()] = file_data

    if file_data['type'] == 'dir':
        # Recursively process the contents of the directory
        sub_index_file = abs_entry_path / g_yaml_name
        sub_data = merge_contents(sub_index_file, retries, retries_pause, root_path)
        merged_data.update(sub_data)


def merge_contents(path_to_index_hash: Path, retries: int, retries_pause: int, root_path: Path):
    merged_data = {}
    if not path_to_index_hash.parent.exists():
        print('WARN: folder not found: ', str(path_to_index_hash))
        merged_data[str(path_to_index_hash)] = {
            'type': 'error',
            'error': 'not_found_dir',
            'path': str(path_to_index_hash),
        }
        return merged_data
    if not path_to_index_hash.exists():
        print('WARN: sfs-file not found: ', str(path_to_index_hash))
        merged_data[str(path_to_index_hash)] = {
            'type': 'error',
            'error': 'not_found_sfs_file',
            'path': str(path_to_index_hash),
        }
        return merged_data

    base_dir = path_to_index_hash.parent

    # TODO: use `fss_utils.load_yaml_fss_file_stream`
    index_data = load_yaml(path_to_index_hash, retries=retries, retries_pause=retries_pause)

    if index_data is not None:
        for file_name, file_data in index_data.items():
            add_data_to_merged_data(merged_data, file_data, file_name, base_dir, root_path, retries, retries_pause)

    return merged_data



def main():
    arguments = docopt(__doc__)

    start_directory = Path(arguments['<start_directory>'])
    retries = int(arguments['--retries'] or 1)
    retries_pause = int(arguments['--retries-pause'] or 1)

    merged_structure = merge_contents(
        start_directory / g_yaml_name,
        retries, retries_pause,
        start_directory)

    yaml_file_arg = arguments['--file']
    if yaml_file_arg:
        yaml_file = Path(yaml_file_arg)
        # If the user passed only a filename (no directory), put it into start_directory.
        if not yaml_file.is_absolute() and yaml_file.parent == Path('.'):
            yaml_file = start_directory / yaml_file
    else:
        yaml_file = start_directory / 'index_hash_all.yaml'

    # Check if the '--not-add-date' option is present
    if not arguments['--not-add-date']:
        # Get the current date in the format YYYY-MM-DD
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Split the file name and extension
        file_name = yaml_file.stem
        file_extension = yaml_file.suffix

        # Append the current date to the filename
        new_file_name = f'{file_name}_{current_date}{file_extension}'

        # Create a new Path object with the updated filename
        yaml_file = yaml_file.with_name(new_file_name)

    save_to_yaml(merged_structure, yaml_file)
    print(f'The merged file structure is saved in {yaml_file}')


if __name__ == '__main__':
    main()
