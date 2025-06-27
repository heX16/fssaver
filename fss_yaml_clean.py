"""
YAML Attribute Cleaner

This script removes specified attributes from items in a YAML file, optionally filtering by item types.

Usage:
  script.py <input_file> [<output_file>] [--del_attr=<attributes>] [--if_type=<types>]
  
Options:
  -h --help                Show this help message.
  --del_attr=<attributes>  Comma-separated list of attributes to delete.
  --if_type=<types>        Comma-separated list of types to filter by.

Examples:
  # Remove 'mtime' attribute from all directories in 'data.yaml' and save to 'output.yaml'
  python script.py data.yaml output.yaml --del_attr=mtime --if_type=dir

  # Remove 'mtime' and 'ctime' attributes from all files and directories
  python script.py data.yaml --del_attr=mtime,ctime --if_type=file,dir

  # Remove 'temporary' attribute from all items
  python script.py data.yaml --del_attr=temporary

Description:
  This script processes a YAML file containing file system structure data and removes specified attributes
  from the items. It can optionally filter the items by their 'type' before removing the attributes.
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

def main():
    arguments = docopt(__doc__)

    input_file = arguments['<input_file>']
    output_file = arguments['<output_file>'] or input_file

    # Parsing the command-line arguments
    del_attr_str = arguments.get('--del_attr') or ''
    del_attrs = [attr.strip() for attr in del_attr_str.split(',')] if del_attr_str else []

    if_type_str = arguments.get('--if_type') or ''
    if_types = [typ.strip() for typ in if_type_str.split(',')] if if_type_str else []

    # Read YAML data using load_yaml from fss_utils
    data = load_yaml(Path(input_file))

    remove_attributes(data, del_attrs, if_types)

    # Write YAML data using save_to_yaml from fss_utils
    save_to_yaml(data, Path(output_file))

if __name__ == '__main__':
    main()
