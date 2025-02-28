"""
File Structure Comparison

Usage:
  fss_compare.py --old=<old_yaml> --new=<new_yaml>
  fss_compare.py -h | --help

Options:
  -h --help     Show this help message and exit.
  --old=<old_yaml>  Path to the old YAML file.
  --new=<new_yaml>  Path to the new YAML file.
"""

# TODO: add Dir rename/move detection.
#  should add a count of successfully found subfiles.
#  if the contents are roughly similar, you can declare that the directory was simply renamed or moved.

# TODO: use `time_trim_ms` in normalize


from fss_utils import *
import typing
from pathlib import Path
from docopt import docopt
from concurrent.futures import ThreadPoolExecutor


class FilesIndex:
    """
    A class for indexing and comparing file structures.

    This class maintains multiple indexes of files based on different attributes,
    which allows for efficient searching and comparison of file structures.
    It also tracks duplicate files found during indexing.

    Attributes:
        KEY_TYPE_DESCRIPTIONS: Dictionary mapping index types to human-readable descriptions
        full: Dictionary of files indexed by (name, type, size, md5, ctime, mtime)
        only_hash: Dictionary of files indexed by (size, md5)
        no_hash: Dictionary of files indexed by (name, ctime, mtime)
        no_name: Dictionary of files indexed by (size, md5, ctime, mtime)
        only_path: Dictionary of files indexed by (path)
        indexes: Tuple of all index dictionaries
        duplicates: List of duplicate files found during indexing
    """

    # Define key type descriptions for better readability
    KEY_TYPE_DESCRIPTIONS = {
        0: "full match (name, type, size, md5, ctime, mtime)",
        1: "content match (size, md5)",
        2: "metadata match (name, ctime, mtime)",
        3: "content and time match (size, md5, ctime, mtime)",
        4: "path match"
    }

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
        self.duplicates = []  # Store information about duplicate files

    @classmethod
    def normalize_data(cls, data: dict, current_path: Path):
        """
        Normalize file data by ensuring all required fields are present.

        Args:
            data: Dictionary containing file data
            current_path: Path object representing the file's path
        """
        data['path'] = current_path
        data['type'] = data.get('type', 'error')
        data['size'] = data.get('size', -1)
        data['md5'] = data.get('md5', '')
        data['ctime'] = data.get('ctime', '')
        data['mtime'] = data.get('mtime', '')

    @classmethod
    def make_keys(cls, data: dict, current_path: Path):
        """
        Create key tuples for each index type based on file data.

        This method generates different key tuples for each index type,
        which are used to identify and compare files. It also validates
        the keys to ensure they don't contain invalid data.

        Args:
            data: Dictionary containing file data
            current_path: Path object representing the file's path

        Returns:
            List of key tuples for each index type, or None for invalid keys
        """

        # make keys tuple
        current_name = current_path.name
        keys = [
            (current_name, data['type'], data['size'], data['md5'], data['ctime'], data['mtime']),
            (data['size'], data['md5']),
            (current_name, data['ctime'], data['mtime']),
            (data['size'], data['md5'], data['ctime'], data['mtime']),
            (str(current_path),),
        ]

        # keys validation
        for i, key_tuple in enumerate(keys):
            if i == 0 and data['size'] > 0:
                # try to save this key even if it doesn't contain some data (usually all data is present)
                continue

            # check "key tuple" for invalid data
            for d in key_tuple:
                if d == '' or d == -1 or d is None:
                    break  # invalid data in key - delete this key
            else:
                continue  # all data present in key - continue

            # delete this key
            keys[i] = None

        if data['size'] == 0:
            keys[1] = None  # if size==0 then remove content key

        return keys

    def add_item(self, data: dict, current_path: Path):
        """
        Add a file to the index and detect duplicates.

        This method normalizes the file data, generates keys for each index type,
        and adds the file to the appropriate indexes. If a duplicate is found
        (a file with the same key already exists in an index), it records the
        duplicate information and prints a warning.

        Args:
            data: Dictionary containing file data
            current_path: Path object representing the file's path
        """
        FilesIndex.normalize_data(data, current_path)
        keys = FilesIndex.make_keys(data, current_path)
        for i, k in enumerate(self.indexes):
            if keys[i] is None:
                continue
            if keys[i] in self.indexes[i]:
                # duplication detected
                existing_file = self.indexes[i][keys[i]]
                duplicate_info = {
                    'source': str(current_path),
                    'duplicate': str(existing_file['path']),
                    'key_type': i,  # Index type where duplication was found
                    'key': keys[i],
                    'size': data.get('size', -1),
                    'md5': data.get('md5', ''),
                    'type': data.get('type', '')
                }
                self.duplicates.append(duplicate_info)

                # Get description for this key type
                description = self.KEY_TYPE_DESCRIPTIONS.get(i, f"unknown type {i}")
                size_info = f"{data.get('size', -1)} bytes" if data.get('size', -1) > 0 else "unknown size"

                print(f"Duplicate detected ({description}, {size_info}):")
                print(f"  Source: {current_path}")
                print(f"  Duplicate of: {existing_file['path']}")

                continue
            else:
                self.indexes[i][keys[i]] = data

    def merge_files_index(self, files_index):
        """
        Merge another FilesIndex into this one.

        This method merges all indexes and the duplicates list from another
        FilesIndex object into this one.

        Args:
            files_index: Another FilesIndex object to merge into this one
        """
        for i, k in enumerate(self.indexes):
            self.indexes[i].update(files_index.indexes[i])
        # Merge duplicates lists
        self.duplicates.extend(files_index.duplicates)


def create_files_index(flat_structure: dict) -> FilesIndex:
    """
    Create a FilesIndex from a flat structure dictionary.

    This function creates a new FilesIndex object and populates it with
    file data from a flat structure dictionary, where keys are file paths
    and values are dictionaries containing file metadata.

    Args:
        flat_structure: Dictionary mapping file paths to file metadata

    Returns:
        A populated FilesIndex object
    """
    files_index = FilesIndex()
    for relative_path_str, data in flat_structure.items():
        relative_path = Path(relative_path_str)
        files_index.add_item(data, relative_path)
    return files_index


def process_duplicates(file_index: FilesIndex, is_old_index: bool) -> list[tuple[str, str, str, str, str]]:
    """
    Process duplicates from a file index and format them for output.

    This function extracts duplicate file information from a FilesIndex object
    and formats it for display and CSV output. It adds a prefix to indicate
    whether the duplicate was found in the old or new file structure.

    Args:
        file_index: The FilesIndex containing duplicates information
        is_old_index: Whether this is the old (initial) index or the new index

    Returns:
        List of formatted duplicate entries as tuples:
        (source_file, duplicate_file, match_type_description, size_info, md5_hash)
    """
    result = []

    prefix = "old" if is_old_index else "new"

    for dup in file_index.duplicates:
        key_type = dup['key_type']
        description = FilesIndex.KEY_TYPE_DESCRIPTIONS.get(key_type, f"unknown type {key_type}")
        size_info = f"{dup['size']} bytes" if dup['size'] > 0 else "unknown size"
        md5_info = dup['md5'] if dup['md5'] else "no hash"

        result.append((
            dup['source'],
            dup['duplicate'],
            f"{prefix}: {description}",
            size_info,
            md5_info
        ))

    return result


def search_changes_in_fs_struct(initial_list: FilesIndex, new_list: FilesIndex):
    """
    Search for changes between two file structure indexes.

    This function compares two FilesIndex objects to identify:
    - Changed files (files that exist in both structures but have different content)
    - Moved files (files that have been moved or renamed)
    - Deleted files (files that exist in the initial structure but not in the new one)
    - New files (files that exist in the new structure but not in the initial one)
    - Duplicate files (files that have duplicates within the same structure)

    Args:
        initial_list: The initial (old) file index
        new_list: The new file index

    Returns:
        Tuple of (changed_files, moved_files, deleted_files, new_files, duplicate_files)
        - changed_files: List of (path, change_description) tuples
        - moved_files: List of (source_path, destination_path, move_type) tuples
        - deleted_files: List of (path,) tuples
        - new_files: List of (path,) tuples
        - duplicate_files: List of (source, duplicate, description, size, md5) tuples
    """
    deleted_files: list[tuple[Path]] = []
    moved_files: list[tuple[Path, Path, str]] = []
    changed_files: list[tuple[Path, typing.Any]] = []
    new_files: list[tuple[Path]] = []

    # Process duplicates from both lists
    duplicate_files = process_duplicates(initial_list, True)
    duplicate_files.extend(process_duplicates(new_list, False))

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

    return changed_files, moved_files, deleted_files, new_files, duplicate_files


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

    print('Data loading...')

    with ThreadPoolExecutor(max_workers=2) as executor:
        # Load data from files, simple code:
        # initial_data = load_yaml(old_yaml)
        # new_data = load_yaml(new_yaml)

        # Run loading in parallel:
        future_initial = executor.submit(load_yaml, old_yaml)
        future_new = executor.submit(load_yaml, new_yaml)

        # Get results:
        initial_data = future_initial.result()
        new_data = future_new.result()
    print('Data loaded')

    if initial_data is None or new_data is None:
        print("Error loading YAML files.")
    else:
        # Create file indexes
        print('Parsing old data...')
        initial_file_list: FilesIndex = create_files_index(initial_data)
        print('Parsing new data...')
        new_file_list: FilesIndex = create_files_index(new_data)

        # Search for differences
        changed_files, moved_files, deleted_files, new_files, duplicate_files = search_changes_in_fs_struct(
            initial_list=initial_file_list,
            new_list=new_file_list
        )

        save_result_and_print_info(changed_files, moved_files, deleted_files, new_files, duplicate_files)


if __name__ == "__main__":
    main()
