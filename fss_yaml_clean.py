"""
Usage:
  script.py <input_file> [<output_file>]

Options:
  -h --help     Show this screen.
"""

import yaml
from docopt import docopt

def remove_mtime_if_dir(data):
    for path, info in data.items():
        if info.get('type') == 'dir':
            # Remove 'mtime' from directory entries
            info.pop('mtime', None)

def main():
    arguments = docopt(__doc__)

    input_file = arguments['<input_file>']
    output_file = arguments['<output_file>'] or input_file

    # Read
    with open(input_file, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)

    remove_mtime_if_dir(data)

    # Write
    with open(output_file, 'w', encoding='utf-8') as file:
        yaml.dump(data, file, allow_unicode=True)

if __name__ == "__main__":
    main()
