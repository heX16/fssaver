"""
YAML to Text File Converter

Usage:
  yaml_to_txt.py <yaml_file> [<txt_file>]
  yaml_to_txt.py (--stdin --stdout)
  yaml_to_txt.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --stdin       Read YAML from standard input.
  --stdout      Write output to standard output.

See: DiskDir and DiskDir Extended plugins for Double Commander (if you're a fan of opensource) or Total Commander.
"""

import yaml
from pathlib import Path
from datetime import datetime
import sys
from docopt import docopt

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
            output_lines.append(f"{full_path}\t{size}\t{ctime}")
            total_size += size
            total_files += 1
        elif data['type'] == 'dir':
            full_path = str(relative_path) + '\\'
            ctime = convert_iso8601_to_custom_format(data['ctime'])
            output_lines.append(f"{full_path}\t0\t{ctime}")
            # Directories do not contribute to total size and files directly
            # But if needed, we can count them
            # total_files += 1

    return output_lines, total_files, total_size

def load_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_to_file(output_lines, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + "\n")

def save_to_stdout(output_lines):
    for line in output_lines:
        sys.stdout.write(line + "\n")

def main(yaml_file=None, output_file=None, use_stdin=False, use_stdout=False):
    if use_stdin:
        flat_structure = yaml.safe_load(sys.stdin)
    else:
        flat_structure = load_yaml(yaml_file)

    output_lines, total_files, total_size = format_output(flat_structure)

    if use_stdout:
        save_to_stdout(output_lines)
    else:
        save_to_file(output_lines, output_file)

if __name__ == "__main__":
    arguments = docopt(__doc__)
    yaml_file = arguments['<yaml_file>']
    output_file = arguments['<txt_file>'] if arguments['<txt_file>'] else (Path(yaml_file).with_suffix('.lst')) if yaml_file else None
    use_stdin = arguments['--stdin']
    use_stdout = arguments['--stdout']

    if not arguments['<yaml_file>'] and not use_stdin:
        print(__doc__)
    else:
        main(yaml_file, output_file, use_stdin, use_stdout)
