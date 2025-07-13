"""
Converter from FSS format to ZIP archive with empty files

Usage:
  fss_to_zip.py <yaml_file> [<zip_file>]
  fss_to_zip.py -h | --help

Options:
  -h --help     Show this help message and exit.

This program creates a ZIP archive based on the FSS file.
All files in the ZIP will be empty (0 bytes), which allows viewing
the "fss directory structure" through the standard Windows Explorer.
"""

import yaml
import zipfile
from pathlib import Path
from docopt import docopt
from fss_utils import load_yaml
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def create_directory_structure(zip_file, flat_structure):
    """
    Creates directory structure and empty files in the ZIP archive
    """
    total_files = 0
    total_dirs = 0
    created_dirs = set()

    # First create all directories
    for relative_path_str, data in flat_structure.items():
        relative_path = Path(relative_path_str)

        # Create all parent directories
        for parent in list(relative_path.parents):
            if str(parent) != '.' and str(parent) not in created_dirs:
                if str(parent) != '.':  # Skip current directory
                    zip_path = str(parent).replace('\\', '/')
                    if zip_path not in created_dirs:
                        zip_file.writestr(f'{zip_path}/', b'')  # Empty byte for directory
                        created_dirs.add(zip_path)
                        total_dirs += 1

        # Process current item
        if data['type'] == 'dir':
            dir_path = str(relative_path).replace('\\', '/')
            if dir_path not in created_dirs:
                zip_file.writestr(f'{dir_path}/', b'')  # Empty byte for directory
                created_dirs.add(dir_path)
                total_dirs += 1

        elif data['type'] == 'file':
            # Create empty file
            file_path = str(relative_path).replace('\\', '/')
            zip_file.writestr(file_path, b'')  # Empty file
            total_files += 1

    return total_files, total_dirs

def save_to_zipfile(flat_structure, output_file):
    """
    Saves structure to ZIP file
    """
    # Create ZIP file
    with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        # Create directories and files
        total_files, total_dirs = create_directory_structure(zip_file, flat_structure)

    logging.info(f'Created ZIP file: {output_file}')
    logging.info(f'Total directories: {total_dirs}, files: {total_files}')

def main(yaml_file, output_file):
    # Load YAML data using load_yaml from fss_utils
    flat_structure = load_yaml(Path(yaml_file))

    if flat_structure is None:
        logging.error(f'ERROR: Failed to load YAML data from {yaml_file}')
        return

    # Save structure to ZIP file
    save_to_zipfile(flat_structure, output_file)

if __name__ == '__main__':
    arguments = docopt(__doc__)
    yaml_file = arguments['<yaml_file>']
    output_file = arguments['<zip_file>'] if arguments['<zip_file>'] else Path(yaml_file).with_suffix('.zip')
    main(yaml_file, output_file)
