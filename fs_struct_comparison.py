"""
File Structure Comparison

Usage:
  fs_structure_comparison.py --old=<old_yaml> --new=<new_yaml>
  fs_structure_comparison.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --old=<old_yaml>  Path to the old YAML file.
  --new=<new_yaml>  Path to the new YAML file.
  --dup         Search duplications (wip)
"""
from typing import List, Any, Tuple

# TODO: add search duplications mode

import yaml
import csv
from pathlib import Path
from docopt import docopt


class FilesIndex:

    def __init__(self):
        self.full = {}  # 0. name, size, md5, ctime, mtime - simple detection
        self.only_hash = {}  # 1. size, md5 - detect by content
        self.no_hash = {}  # 2. name, ctime, mtime  - detect change and move (without renaming)
        self.no_name = {}  # 3. size, md5, ctime, mtime - for detect file renaming (without content change)
        self.only_path = {}  # 4. path - full path (deletion detection)
        # self.no_hash_co = {}  # 2. name, ctime - detect change and move (without renaming)
        # self.short = {}  # name, size - simple detection by short data
        # self.no_time = {}  # name, size, md5  - detect date changes. OFF
        # self.only_name = {}# name - simple detection by name. OFF
        self.indexes = (self.full, self.only_hash, self.no_hash, self.no_name, self.only_path)

    @classmethod
    def normalize_data(cls, data: dict, current_path: Path):
        data['path'] = current_path
        data['size'] = data.get('size', -1)
        data['md5'] = data.get('md5', '')
        data['ctime'] = data.get('ctime', '')
        data['mtime'] = data.get('mtime', '')

    @classmethod
    def make_keys(cls, data: dict, current_path: Path):
        current_name = current_path.name
        keys = [
            (current_name, data['size'], data['md5'], data['ctime'], data['mtime']),
            (data['size'], data['md5']),
            (current_name, data['ctime'], data['mtime']),
            (data['size'], data['md5'], data['ctime'], data['mtime']),
            (str(current_path),),
        ]

        # keys validation
        for i, key in enumerate(keys):
            if i == 0 and data['size'] > 0:
                # try to save this key even if it doesn't contain some data (usually all data is present)
                continue

            for d in key:
                if d == '' or d == -1 or d is None:
                    break  # invalid data in key - delete this key
            else:
                continue  # all data present in key - continue
            keys[i] = None

        if data['size'] == 0:
            keys[1] = None  # if size==0 then remove content key

        return keys

    def add_item(self, data: dict, current_path: Path):
        FilesIndex.normalize_data(data, current_path)
        keys = FilesIndex.make_keys(data, current_path)
        for i, k in enumerate(self.indexes):
            if k is None:
                continue
            if keys[i] in self.indexes[i]:
                # duplication detected
                print('WARN(dup): ' + str(current_path))
                # TODO: process duplication
            else:
                self.indexes[i][keys[i]] = data

    def merge_files_index(self, files_index):
        for i, k in enumerate(self.indexes):
            self.indexes[i].update(files_index.indexes[i])


def load_yaml(file_path: Path):
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return None


def create_files_index(current_item, current_path: Path = Path()):
    files_index = FilesIndex()
    if current_item['type'] == 'dir':
        # Enum all items in current_item
        for name, content in current_item['contents'].items():
            # Recursion
            files_index_recursion = create_files_index(content, current_path / name)
            files_index.merge_files_index(files_index_recursion)
    elif current_item['type'] == 'file':
        files_index.add_item(current_item, current_path)
    else:
        pass  # skip other types (symlink and error)
    return files_index


def search_changes_in_fs_struct(initial_list, new_list):
    deleted_files: list[Path] = []
    moved_files: list[tuple[Path, Path]] = []
    changed_files: list[Path] = []

    # search
    for key, data in initial_list.full.items():
        # search by full key
        if key in new_list.full:
            # file present
            if data['path'] != new_list.full[key]['path']:
                # but path is changed - file move to other dir
                moved_files.append((data['path'], new_list.full[key]['path']))
        else:
            # file lost - try search in other lists
            found = False
            if (str(data['path']),) in new_list.only_path and new_list.only_path[(str(data['path']),)]['path'] == data['path']:
                # That file hasn't been moved. It's just changed, but it's still there.
                # Of course, there is a chance that a file was moved and another file was put in its place.
                # But such complicated cases will not be considered - there will be too many erroneous decisions.
                found = True

            if not found:
                keys_pack = FilesIndex.make_keys(data, data['path'])
                for keys_pack_i in range(1, 3):
                    key_ext = keys_pack[keys_pack_i]
                    if key_ext == None:
                        continue
                    if key_ext in new_list.indexes[keys_pack_i]:
                        found_item = new_list.indexes[keys_pack_i][key_ext]
                        moved_files.append((data['path'], found_item['path']))
                        found = True
                        break

            if not found:
                if (str(data['path']),) in new_list.only_path:
                    changed_files.append(data['path'])
                else:
                    deleted_files.append(data['path'])

    return changed_files, moved_files, deleted_files


def save_to_csv(file_path: Path, data):
    with open(file_path, 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';')
        csv_writer.writerows(data)


def print_result(changed_files, moved_files, deleted_files):
    # Print result
    if changed_files:
        print("Changed files list:")
        for f in deleted_files:
            print(str(f))
        # Save deleted files to CSV
        save_to_csv(Path("deleted.csv"), [[str(f)] for f in deleted_files])
        print("Changed files saved to deleted.csv")
    else:
        print("Changed files not detected")

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


def main():
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
            initial_file_list = create_files_index({'type': 'dir', 'contents': initial_data})
            new_file_list = create_files_index({'type': 'dir', 'contents': new_data})
            # Search diff
            changed_files, moved_files, deleted_files = search_changes_in_fs_struct(initial_file_list, new_file_list)
            print_result(changed_files, moved_files, deleted_files)


if __name__ == "__main__":
    main()
