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
        self.only_hash = {}  # 1. size, md5 - detect by content
        self.no_hash = {}    # 2. ctime, name - detect change and move (without renaming)
        self.no_name = {}    # 3. size, md5, ctime, mtime - for detect file renaming (without content change)
        self.path = {}       # 4. path - full path (deletion detection)
        # self.only_name = {}  # 5. name - simple detection by name. OFF
        self.indexes = (self.full, self.only_hash, self.no_hash, self.no_name, self.path)


    def nomalize_data(data: dict, current_path: Path):
        data['path']  = current_path
        data['size']  = data.get('size', -1)
        data['md5']   = data.get('md5', '')
        data['ctime'] = data.get('ctime', '')
        data['mtime'] = data.get('mtime', '')


    def make_keys(data: dict, current_path: Path):
        current_name  = current_path.name
        return (
            (data['size'], data['md5'], data['ctime'], data['mtime'], current_name),
            (data['size'], data['md5']),
            (data['ctime'], current_name),
            (data['size'], data['md5'], data['ctime'], data['mtime']),
            (str(current_path)),
        )


    def add_item(self, data: dict, current_path: Path):
        FilesIndex.nomalize_data(data, current_path)
        keys = FilesIndex.make_keys(data, current_path)
        # TODO: analize dublication; skip size==0 items for 'only_hash' index.
        for i, k in enumerate(self.indexes):
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


def search_moved_and_deleted_files(initial_list, new_list):
    deleted_files = []
    moved_files = []
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
            if str(data['path']) in new_list.path and new_list.path[str(data['path'])]['path'] == data['path']:
                # That file hasn't been moved. It's just changed, but it's still there.
                # Of course, there is a chance that a file was moved and another file was put in its place.
                # But such complicated cases will not be considered - there will be too many erroneous decisions.
                found = True

            if not found:
                keys_pack = FilesIndex.make_keys(data, data['path'])
                for keys_pack_i in range(1, 3):
                    key_ext = keys_pack[keys_pack_i]
                    if key_ext in new_list.indexes[keys_pack_i]:
                        found_item = new_list.indexes[keys_pack_i][key_ext]
                        moved_files.append((data['path'], found_item['path']))
                        found = True
                        break

            if not found:
                deleted_files.append(data['path'])

    return moved_files, deleted_files


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
            moved_files, deleted_files = search_moved_and_deleted_files(initial_file_list, new_file_list)

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
