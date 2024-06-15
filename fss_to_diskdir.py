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

def format_output(file_structure, path_prefix=''):
    output_lines = []
    total_size = 0
    total_files = 0

    for name, data in file_structure.items():
        if data['type'] == 'file':
            full_path = path_prefix + name
            size = data['size']
            ctime = convert_iso8601_to_custom_format(data['ctime'])
            output_lines.append(f"{full_path}\t{size}\t{ctime}")
            total_size += size
            total_files += 1
        elif data['type'] == 'dir':
            full_path = path_prefix + name + '\\'
            ctime = convert_iso8601_to_custom_format(data['ctime'])
            output_lines.append(f"{full_path}\t0\t{ctime}")
            sub_output, sub_total_files, sub_total_size = format_output(data['contents'], full_path)
            output_lines.extend(sub_output)
            total_size += sub_total_size
            total_files += sub_total_files

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
        file_structure = yaml.safe_load(sys.stdin)
    else:
        file_structure = load_yaml(yaml_file)

    output_lines, total_files, total_size = format_output(file_structure)

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
