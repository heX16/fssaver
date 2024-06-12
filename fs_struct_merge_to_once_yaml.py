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
import datetime
import time
from fs_struct_utils import *

g_yaml_name = '.index_hash.yaml'


def merge_contents(path_to_index_hash: Path, retries: int, retries_pause: int):
    if not path_to_index_hash.parent.exists():
        print('WARN: folder not found: ', str(path_to_index_hash))
        return {
            str(path_to_index_hash.name): {
                'type': 'error',
                'error': 'not_found_dir',
                'path': str(path_to_index_hash),
                }
        }
    if not path_to_index_hash.exists():
        print('WARN: sfs-file not found: ', str(path_to_index_hash))
        return {
            str(path_to_index_hash.name): {
                'type': 'error',
                'error': 'not_found_sfs_file',
                'path': str(path_to_index_hash),
                }
        }

    index_data = load_yaml(path_to_index_hash, retries=retries, retries_pause=retries_pause)

    for file_name, file_data in index_data.items():
        if file_data['type'] == 'dir' or (file_data['type'] == 'directory'):
            recursion_indexes = merge_contents(Path(path_to_index_hash).parent / file_name / g_yaml_name, retries, retries_pause)
            index_data[file_name]['contents'] = recursion_indexes

    return index_data



def main():
    arguments = docopt(__doc__)

    start_directory = Path(arguments['<start_directory>'])
    yaml_file = Path(arguments['--file'] or 'index_hash_all.yaml')
    retries = int(arguments['--retries'] or 1)
    retries_pause = int(arguments['--retries-pause'] or 1)

    merged_structure = merge_contents(start_directory / g_yaml_name, retries, retries_pause)

    if not yaml_file.is_absolute():
        yaml_file = start_directory / yaml_file

    # Check if the '--not-add-date' option is present
    if not arguments['--not-add-date']:
        # Get the current date in the format YYYY-MM-DD
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Split the file name and extension
        file_name = yaml_file.stem
        file_extension = yaml_file.suffix

        # Append the current date to the filename
        new_file_name = f"{file_name}_{current_date}{file_extension}"

        # Create a new Path object with the updated filename
        yaml_file = yaml_file.with_name(new_file_name)

    save_to_yaml(merged_structure, yaml_file)
    print(f'The merged file structure is saved in {yaml_file}')


if __name__ == '__main__':
    main()
