"""
File Structure Comparison

Usage:
  fs_structure_comparison.py --old=<old_yaml> --new=<new_yaml>
  fs_structure_comparison.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --old=<old_yaml>  Path to the old YAML file.
  --new=<new_yaml>  Path to the new YAML file.
"""

import yaml
import csv
from pathlib import Path
from docopt import docopt

class FilesIndex:

    def __init__(self):
        self.full = {}       # 0. size, md5, ctime, mtime, name - simple detection
        self.only_hash = {}  # 1. size, md5 - detect content
        self.no_hash = {}    # 2. ctime, mtime, name - detect change and move
        self.no_name = {}    # 3. size, md5, ctime, mtime - for detect file renaming
        self.only_name = {}  # 4. name - simple detection by name
        self.indexes = (self.full, self.only_hash, self.no_hash, self.no_name, self.only_name)

    def make_keys(self, data: dict, current_path: Path):
        current_name  = current_path.name
        data['size']  = data.get('size', -1)
        data['md5']   = data.get('md5', '')
        data['ctime'] = data.get('ctime', '')
        data['mtime'] = data.get('mtime', '')
        return (
            (data['size'], data['md5'], data['ctime'], data['mtime'], current_name),
            (data['size'], data['md5']),
            (data['ctime'], data['mtime'], current_name),
            (data['size'], data['md5'], data['ctime'], data['mtime']),
            (current_name),
        )

    def add_item(self, data: dict, current_path: Path):
        keys = self.make_keys(data, current_path)
        for i, k in enumerate(self.indexes):
            self.indexes[i][keys[i]] = current_path

    def merge_files_index(self, files_index):
        for i, k in enumerate(self.indexes):
            self.indexes[i].update(files_index.indexes[i])

def load_yaml(file_path: Path):
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return None


def create_files_index(data, current_path: Path = Path()):
    file_lists = FilesIndex()
    current_name = current_path.name
    if data['type'] == 'directory':
        for name, content in data.get('contents', {}).items():
            # Recursion
            file_lists_recursion = create_files_index(content, current_path / name)
            file_lists.merge_files_index(file_lists_recursion)
    elif data['type'] == 'file':
        file_lists.add_item(data, current_path)
    else:
        pass  # skip other types (symlink and error)
    return file_lists


def search_deleted_files(initial_list, new_list):
    deleted_files = []
    for key, path in initial_list.full.items():
        if key not in new_list.full:
            deleted_files.append(path)
    return deleted_files


def search_moved_files(initial_list, new_list):
    moved_files = []
    for key, path in initial_list.full.items():
        if key in new_list.full and path != new_list.full[key]:
            moved_files.append((path, new_list.full[key]))
    return moved_files


def save_to_csv(file_path: Path, data):
    with open(file_path, 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';')
        csv_writer.writerows(data)

if __name__ == "__main__":
    arguments = docopt(__doc__)

    old_yaml = Path(arguments['--old'])
    new_yaml = Path(arguments['--new'])

    if not old_yaml.is_file() or not new_yaml.is_file():
        print("The specified YAML files do not exist.")
    else:
        initial_data = load_yaml(old_yaml)
        new_data = load_yaml(new_yaml)

        if initial_data is None or new_data is None:
            print("Error loading YAML files.")
        else:
            # Create special file index
            initial_file_list = create_files_index(initial_data)
            new_file_list = create_files_index(new_data)
            # Search diff
            deleted_files = search_deleted_files(initial_file_list, new_file_list)
            moved_files = search_moved_files(initial_file_list, new_file_list)

            # Print result
            if deleted_files:
                print("Deleted files list:")
                for f in deleted_files:
                    print(str(f))
                # Save deleted files to CSV
                save_to_csv(Path("deleted.csv"), [[str(f)] for f in deleted_files])
                print("Deleted files saved to deleted.csv")
            else:
                print("Delete files not detected")

            if moved_files:
                print("Moved files list:")
                for f in moved_files:
                    print(str(f[0]) + ';    ' + str(f[1]))
                # Save moved files to CSV
                save_to_csv(Path("moved.csv"), [[str(f[0]), str(f[1])] for f in moved_files])
                print("Moved files saved to moved.csv")
            else:
                print("Moved files not detected")
