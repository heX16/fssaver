"""
YAML Attribute Cleaner

This script removes specified attributes from items in a YAML file, optionally filtering by item types.

Usage:
  script.py <input_file> [<output_file>] [--del_attr=<attributes>] [--if_type=<types>]
  script.py --dir=<dir> [--del_attr=<attributes>] [--if_type=<types>]
  
Options:
  -h --help                Show this help message.
  --dir=<dir>              Process directory recursively, cleaning all .index_hash.yaml files.
  --del_attr=<attributes>  Comma-separated list of attributes to delete.
  --if_type=<types>        Comma-separated list of types to filter by.

Examples:
  # Remove 'mtime' attribute from all directories in 'data.yaml' and save to 'output.yaml'
  python script.py data.yaml output.yaml --del_attr=mtime --if_type=dir

  # Remove 'mtime' and 'ctime' attributes from all files and directories
  python script.py data.yaml --del_attr=mtime,ctime --if_type=file,dir

  # Remove 'temporary' attribute from all items
  python script.py data.yaml --del_attr=temporary

  # Process all .index_hash.yaml files in directory recursively
  python script.py --dir=/path/to/dir --del_attr=mtime,ctime --if_type=file

Description:
  This script processes a YAML file containing file system structure data and removes specified attributes
  from the items. It can optionally filter the items by their 'type' before removing the attributes.
  
  In directory mode (--dir), it recursively finds all .index_hash.yaml files and processes them in-place.
"""

from docopt import docopt
from pathlib import Path
from fss_utils import load_yaml, save_to_yaml

def remove_attributes(data, del_attrs, if_types):
    """
    Remove specified attributes from items in the data dictionary.

    Args:
        data (dict): The data dictionary containing items to process.
        del_attrs (list): List of attribute names to delete from the items.
        if_types (list): List of item types to filter by. If empty, no filtering is applied.

    This function iterates over the items in the data dictionary and removes the specified attributes
    from each item that matches the given types. If 'if_types' is empty, all items are processed.
    """
    for path, info in data.items():
        item_type = info.get('type')
        if if_types and item_type not in if_types:
            continue  # Skip items not matching the specified types
        for attr in del_attrs:
            # Remove specified attributes
            info.pop(attr, None)

def process_single_file(input_file: Path, output_file: Path, del_attrs: list, if_types: list) -> bool:
    """
    Process a single YAML file.

    Args:
        input_file: Path to input YAML file
        output_file: Path to output YAML file
        del_attrs: List of attributes to delete
        if_types: List of types to filter by

    Returns:
        True if file was modified, False otherwise
    """
    # Read YAML data using load_yaml from fss_utils
    data = load_yaml(input_file, return_on_fail={})
    
    # Validate that data is a dictionary
    if not isinstance(data, dict):
        print(f'ERROR: {input_file} does not contain a valid dictionary. Skipping.')
        return False

    remove_attributes(data, del_attrs, if_types)

    # Write YAML data using save_to_yaml from fss_utils
    return save_to_yaml(data, output_file)

def process_directory(directory: Path, del_attrs: list, if_types: list):
    """
    Process all .index_hash.yaml files in directory recursively.

    Args:
        directory: Path to directory to process
        del_attrs: List of attributes to delete
        if_types: List of types to filter by
    """
    if not directory.exists():
        print(f'ERROR: Directory does not exist: {directory}')
        return

    if not directory.is_dir():
        print(f'ERROR: Path is not a directory: {directory}')
        return

    # Find all .index_hash.yaml files recursively
    yaml_files = list(directory.rglob('*.index_hash.yaml'))
    
    if not yaml_files:
        print(f'No .index_hash.yaml files found in {directory}')
        return

    print(f'Found {len(yaml_files)} .index_hash.yaml file(s) in {directory}')

    files_processed = 0
    files_modified = 0
    files_failed = 0

    for yaml_file in yaml_files:
        try:
            modified = process_single_file(yaml_file, yaml_file, del_attrs, if_types)
            files_processed += 1
            if modified:
                files_modified += 1
                print(f'Modified: {yaml_file}')
        except Exception as e:
            files_failed += 1
            print(f'ERROR processing {yaml_file}: {e}')

    # Print summary
    print(f'\nSummary:')
    print(f'  Total files found: {len(yaml_files)}')
    print(f'  Files processed: {files_processed}')
    print(f'  Files modified: {files_modified}')
    print(f'  Files failed: {files_failed}')

def main():
    arguments = docopt(__doc__)

    # Parsing the command-line arguments
    del_attr_str = arguments.get('--del_attr') or ''
    del_attrs = [attr.strip() for attr in del_attr_str.split(',')] if del_attr_str else []

    if_type_str = arguments.get('--if_type') or ''
    if_types = [typ.strip() for typ in if_type_str.split(',')] if if_type_str else []

    # Warn if no attributes are specified (no-op)
    if not del_attrs:
        print('WARNING: --del_attr is not specified. No attributes will be removed.')
        print('Example: --del_attr=mtime,ctime')
        # Continue anyway for backward compatibility

    # Check if directory mode is requested
    if arguments.get('--dir'):
        directory = Path(arguments['--dir'])
        process_directory(directory, del_attrs, if_types)
    else:
        # File mode (existing behavior)
        input_file = arguments['<input_file>']
        if not input_file:
            print('ERROR: Either <input_file> or --dir must be specified.')
            return

        output_file = arguments['<output_file>'] or input_file
        process_single_file(Path(input_file), Path(output_file), del_attrs, if_types)

if __name__ == '__main__':
    main()
