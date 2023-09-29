'''
File Structure to YAML

Usage:
  fs_struct_merge_to_once_yaml.py <start_directory> [<yaml_file>]
  fs_struct_merge_to_once_yaml.py -h | --help

Options:
  -h --help     Show this help message and exit.
'''

import yaml
from pathlib import Path
from docopt import docopt

g_yaml_name = 'index_hash.yaml'


def merge_contents(path_to_index_hash: Path):
    if not path_to_index_hash.exists():
        print('WARN: folder not found: ', str(path_to_index_hash))
        return {
            'type': 'error',
            'error': 'not_found_dir',
            'path': str(path_to_index_hash),
        }

    index_data = load_yaml(path_to_index_hash)

    for file_name, file_data in index_data['contents'].items():
        if file_data['type'] == 'directory':
            recursion_indexes = merge_contents(Path(path_to_index_hash).parent / file_name / g_yaml_name)
            index_data['contents'][file_name] = recursion_indexes

    return index_data


def load_yaml(file_path: Path):
    try:
        print('LOADING: ', str(file_path))
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print('ERROR: fail index loading: ', str(file_path))
        return None


def save_to_yaml(data, output_file):
    with open(output_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


def main():
    arguments = docopt(__doc__)

    start_directory = Path(arguments['<start_directory>'])
    yaml_file = Path(arguments['<yaml_file>'] or 'index_hash_all.yaml')

    merged_structure = merge_contents(start_directory / g_yaml_name)

    if not yaml_file.is_absolute():
        yaml_file = start_directory / yaml_file

    save_to_yaml(merged_structure, yaml_file)
    print(f'The merged file structure is saved in {yaml_file}')


if __name__ == '__main__':
    main()

