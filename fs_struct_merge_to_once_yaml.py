'''
File Structure to YAML

Usage:
  fs_struct_merge_to_once_yaml.py <start_directory> [--file=<yaml_file>] [--not-add-date]
  fs_struct_merge_to_once_yaml.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --file=<yaml_file> -f=<yaml_file>  Specify the YAML file name (default: 'index_hash_all.yaml').
  --not-add-date --nodate            Not add the current date in the YAML file name.
'''

#TODO: add date to final file

import yaml
from pathlib import Path
from docopt import docopt
import datetime

g_yaml_name = '.index_hash.yaml'


def merge_contents(path_to_index_hash: Path):
    if not path_to_index_hash.exists():
        print('WARN: folder not found: ', str(path_to_index_hash))
        return {
            str(path_to_index_hash): {
                'type': 'error',
                'error': 'not_found_dir',
                'path': str(path_to_index_hash),
                }
        }

    index_data = load_yaml(path_to_index_hash)

    for file_name, file_data in index_data.items():
        if file_data['type'] == 'dir' or (file_data['type'] == 'directory'):
            recursion_indexes = merge_contents(Path(path_to_index_hash).parent / file_name / g_yaml_name)
            index_data[file_name]['contents'] = recursion_indexes

    return index_data


def load_yaml(input_file, encoding='utf-8'):
    try:
        with open(input_file, 'r', encoding=encoding) as f:
            store = yaml.safe_load(f)
            if store is None:
                store = {}
    except FileNotFoundError:
        print('ERROR: file not found: ', str(input_file))
        return {}
    except yaml.YAMLError as e:
        print(f'ERROR: error in YAML file {input_file}: {e}')
        return {}
    except IOError as e:
        print('ERROR: I/O error({0}): {1}'.format(e.errno, e.strerror))
        store = {}
    return store


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

    start_directory = Path(arguments['<start_directory>'])
    yaml_file = Path(arguments['--file'] or 'index_hash_all.yaml')

    merged_structure = merge_contents(start_directory / g_yaml_name)

    if not yaml_file.is_absolute():
        yaml_file = start_directory / yaml_file

    # Check if the '--add-date' option is present
    if arguments['--not-add-date']==False:
        # Get the current date in the format YYYY-MM-DD
        current_date = datetime.date.today().isoformat()

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

