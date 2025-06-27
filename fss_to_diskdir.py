"""
Converter FSS format to DiskDir format

Usage:
  fss_to_diskdir.py <yaml_file> [<txt_file>]
  fss_to_diskdir.py (--stdin --stdout)
  fss_to_diskdir.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --stdin       Read YAML from standard input.
  --stdout      Write output to standard output.

See: "DiskDirW" and "DiskDirExtended_64bit" plugins for
Double Commander (if you're a fan of opensource) or some other file "Commander".

DiskDirW (2022.01.15 Version 1.2.4 released)
URL: https://totalcmd.net/plugring/diskdirw.html
URL: https://wincmd.ru/plugring/diskdirw.html

"""

import yaml
from pathlib import Path
from datetime import datetime
import sys
from docopt import docopt
from fss_utils import load_yaml

def convert_iso8601_to_custom_format(iso_time):
    dt = datetime.strptime(iso_time, '%Y-%m-%d_%H:%M:%SZ')
    custom_time = dt.strftime('%Y.%m.%d\t%H:%M:%S')
    # Remove leading zeros
    custom_time = custom_time.replace(' 0', ' ').replace('.0', '.')
    return custom_time

def format_output(flat_structure):
    output_lines = []
    total_size = 0
    total_files = 0

    for relative_path_str, data in flat_structure.items():
        relative_path = Path(relative_path_str)

        if data['type'] == 'file':
            full_path = str(relative_path)
            size = data['size']
            ctime = convert_iso8601_to_custom_format(data['ctime'])
            output_lines.append(f'{full_path}\t{size}\t{ctime}')
            total_size += size
            total_files += 1
        elif data['type'] == 'dir':
            full_path = str(relative_path) + '\\'
            ctime = convert_iso8601_to_custom_format(data['ctime'])
            output_lines.append(f'{full_path}\t0\t{ctime}')
            # Directories do not contribute to total size and files directly
            # But if needed, we can count them
            # total_files += 1

    return output_lines, total_files, total_size

def save_to_file(output_lines, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

def save_to_stdout(output_lines):
    for line in output_lines:
        sys.stdout.write(line + '\n')

def main(yaml_file=None, output_file=None, use_stdin=False, use_stdout=False):
    # TODO: use `fss_utils.load_yaml_fss_file_stream`
    if use_stdin:
        flat_structure = yaml.safe_load(sys.stdin)
    else:
        # Load YAML data using load_yaml from fss_utils
        if yaml_file is None:
            print('ERROR: No YAML file specified')
            return
        flat_structure = load_yaml(Path(yaml_file))

    if flat_structure is None:
        print(f'ERROR: Failed to load YAML data from {yaml_file}')
        return

    output_lines, total_files, total_size = format_output(flat_structure)

    if use_stdout:
        save_to_stdout(output_lines)
    else:
        save_to_file(output_lines, output_file)

if __name__ == '__main__':
    arguments = docopt(__doc__)
    yaml_file = arguments['<yaml_file>']
    output_file = arguments['<txt_file>'] if arguments['<txt_file>'] else (Path(yaml_file).with_suffix('.lst')) if yaml_file else None
    use_stdin = arguments['--stdin']
    use_stdout = arguments['--stdout']

    if not arguments['<yaml_file>'] and not use_stdin:
        print(__doc__)
    else:
        main(yaml_file, output_file, use_stdin, use_stdout)
