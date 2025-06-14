"""
FSS Cleaner - remove .index_hash.yaml files recursively

Usage:
  fss_clean.py <path>
  fss_clean.py -h | --help

Options:
  -h --help     Show this help message.
"""

from pathlib import Path
from docopt import docopt

if __name__ == '__main__':
    directory = Path(docopt(__doc__)['<path>'])
    for file_path in directory.rglob('*.index_hash.yaml'):
        try:
            file_path.unlink()
            print(f'Removed: {file_path}')
        except Exception as e:
            print(f'Error removing {file_path}: {e}')
