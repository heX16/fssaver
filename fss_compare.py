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

# TODO: add search duplications mode

# TODO: add Dir rename/move detection.
#  should add a count of successfully found subfiles.
#  if the contents are roughly similar, you can declare that the directory was simply renamed or moved.

# TODO: use `time_trim_ms` in normalize


from fss_utils import *
import typing
from pathlib import Path
from docopt import docopt


class FilesIndex:

    def __init__(self):
        self.full = {}  # 0. name, type, size, md5, ctime, mtime - simple detection
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
        data['type'] = data.get('type', 'error')
        data['size'] = data.get('size', -1)
        data['md5'] = data.get('md5', '')
        data['ctime'] = data.get('ctime', '')
        data['mtime'] = data.get('mtime', '')

    @classmethod
    def make_keys(cls, data: dict, current_path: Path):
        current_name = current_path.name
        keys = [
            (current_name, data['type'], data['size'], data['md5'], data['ctime'], data['mtime']),
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
                print('warn dup:\n  src:{0}\n  dst:{1}\n  key:{2}'.format(
                    str(current_path),
                    self.indexes[i][keys[i]]['path'],
                    ', '.join(map(lambda x: str(x), keys[i]))
                ))
                # TODO: process duplication
            else:
                self.indexes[i][keys[i]] = data

    def merge_files_index(self, files_index):
        for i, k in enumerate(self.indexes):
            self.indexes[i].update(files_index.indexes[i])


def create_files_index(flat_structure: dict):
    files_index = FilesIndex()
    for relative_path_str, data in flat_structure.items():
        relative_path = Path(relative_path_str)
        files_index.add_item(data, relative_path)
    return files_index


def search_changes_in_fs_struct(initial_list, new_list):
    deleted_files: list[tuple[Path]] = []
    moved_files: list[tuple[Path, Path, str]] = []
    changed_files: list[tuple[Path, typing.Any]] = []
    new_files: list[tuple[Path]] = []

    # search
    for key, data in initial_list.full.items():
        # search by full key
        if key in new_list.full:
            # file present
            if data['path'] != new_list.full[key]['path']:
                # but path is changed - file move to other dir
                moved_files.append((data['path'], new_list.full[key]['path'], 'move',))
        else:
            # file lost - try search in other lists
            found = False

            # check changes
            path_key = (str(data['path']),)
            if path_key in new_list.only_path and new_list.only_path[path_key]['path'] == data['path']:
                # That file hasn't been moved. It's just changed, but it's still there.
                # Of course, there is a chance that a file was moved and another file was put in its place.
                # But such complicated cases will not be considered - there will be too many erroneous decisions.
                found = True

                changes = []
                new = new_list.only_path[path_key]
                old = initial_list.only_path[path_key]

                if old['type'] != new['type']:
                    changes.append('type')
                    found = False
                else:
                    if old['size'] != new['size']:
                        changes.append('size')
                    else:
                        if old['md5'] != new['md5']:
                            changes.append('md5')
                    if old['mtime'] != new['mtime']:
                        changes.append('mtime')
                    if old['ctime'] != new['ctime']:
                        changes.append('ctime')
                    if (str(data['path']),) in new_list.only_path:
                        changed_files.append((data['path'], ','.join(changes)))

            # check moving
            if not found:
                keys_pack = FilesIndex.make_keys(data, data['path'])
                for keys_pack_i in range(1, 3):
                    key_ext = keys_pack[keys_pack_i]
                    if key_ext is None:
                        continue
                    if key_ext in new_list.indexes[keys_pack_i]:
                        found_item = new_list.indexes[keys_pack_i][key_ext]
                        move_type = []
                        # renamed_files
                        if data['path'].parent != found_item['path'].parent:
                            move_type.append('move')
                        if data['path'].name != found_item['path'].name:
                            move_type.append('rename')
                        moved_files.append((data['path'], found_item['path'], ','.join(move_type),))
                        found = True
                        break

            if not found:
                deleted_files.append((data['path'],))

    # Search for new files
    for key, data in new_list.only_path.items():
        if key not in initial_list.only_path:
            # File is present in the new structure but not in the initial structure
            new_files.append((data['path'], ))

    return changed_files, moved_files, deleted_files, new_files


def main():
    arguments = docopt(__doc__)
    old_yaml = Path(arguments['--old'])
    new_yaml = Path(arguments['--new'])
    if not old_yaml.is_file():
        print("The specified YAML file does not exist: " + str(old_yaml))
        exit(10)
    elif not new_yaml.is_file():
        print("The specified YAML file does not exist: " + str(new_yaml))
        exit(11)

    initial_data = load_yaml(old_yaml)
    new_data = load_yaml(new_yaml)

    if initial_data is None or new_data is None:
        print("Error loading YAML files.")
    else:
        # Create file indexes
        print('Parsing old data...')
        initial_file_list = create_files_index(initial_data)
        print('Parsing new data...')
        new_file_list = create_files_index(new_data)

        # Search for differences
        changed_files, moved_files, deleted_files, new_files = search_changes_in_fs_struct(initial_file_list, new_file_list)
        print_result(changed_files, moved_files, deleted_files, new_files)


if __name__ == "__main__":
    main()
