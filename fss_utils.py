import yaml
import csv
from pathlib import Path
from datetime import datetime
from datetime import datetime, timezone
import os
import stat
import contextlib
import platform
import time
import typing
import traceback


def is_wnd() -> bool:
    """Check if the operating system is Windows."""
    return platform.system().lower() == 'windows'


def is_linux() -> bool:
    """Check if the operating system is Linux."""
    return platform.system().lower() == 'linux'

@contextlib.contextmanager
def open_with_attribute_handling(filename: str | Path, mode='w'):
    """
    A context manager for handling read-only and hidden files across different platforms.

    This function allows opening files that might be marked as read-only or hidden,
    temporarily modifying their attributes or permissions to allow access and writing
    if necessary, and then restoring the original state after the operation is complete.

    Args:
        filename: The path to the file to be opened.
        mode: The mode in which to open the file. Defaults to 'w'.

    Example:
        >>> with open_with_attribute_handling('example.txt', 'w') as f:
        ...     f.write('Hello, World!')

    Note:
        - On Windows, it requires the `pywin32` package to be installed.
        - The original file state (read-only flag, hidden attribute, or permissions)
          is restored after the context manager exits, even if an exception occurs.
    """
    if is_wnd():
        # `pip install pywin32`
        import win32file
        import win32con

        # Get current file attributes
        old_attributes = win32file.GetFileAttributes(str(filename))
        is_readonly = old_attributes & win32con.FILE_ATTRIBUTE_READONLY
        is_hidden = old_attributes & win32con.FILE_ATTRIBUTE_HIDDEN

        new_attributes = old_attributes
        if is_readonly:
            # Remove read-only attribute
            new_attributes &= ~win32con.FILE_ATTRIBUTE_READONLY
        if is_hidden:
            # Remove hidden attribute
            new_attributes &= ~win32con.FILE_ATTRIBUTE_HIDDEN

        if new_attributes != old_attributes:
            win32file.SetFileAttributes(str(filename), new_attributes)
    else:
        # For Unix-like systems
        old_mode = os.stat(filename).st_mode
        is_readonly = not (old_mode & stat.S_IWRITE)
        if is_readonly:
            os.chmod(filename, old_mode | stat.S_IWRITE)
        # Note: Unix-like systems don't have a direct equivalent to the Windows hidden attribute

    try:
        with open(filename, mode) as f:
            yield f
    finally:
        if is_wnd():
            if is_readonly or is_hidden:
                # Restore original attributes
                win32file.SetFileAttributes(str(filename), old_attributes)
        else:
            if is_readonly:
                # Restore original permissions
                os.chmod(filename, old_mode)


def dict_del_item(d: dict, item):
    if item in d:
        del d[item]

def get_file_content(file_name, encoding='utf-8'):
    try:
        with open(file_name, 'r', encoding=encoding) as f:
            return str(f.read())
    except IOError:
        return ''


def save_to_yaml(data, output_file, encoding='utf-8') -> bool:
    saved = False
    data = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    if get_file_content(output_file, encoding=encoding) != data:
        #TODO: with open_with_readonly_handling(output_file, 'w', encoding=encoding) as f:
        with open(output_file, 'w', encoding=encoding) as f:
            f.write(data)
            saved = True
            # TODO: try except PermissionError ...
    return saved


def time_to_iso8601_gmt_str(t: datetime | float | int, separator='_'):
    if isinstance(t, (float, int)):
        # Handle timestamps before 1970 (Unix epoch) - This happens in Windows system files
        if t < 0:
            return f'1601-01-01{separator}00:00:00Z'  # Windows FILETIME epoch fallback
        return datetime.fromtimestamp(t, tz=timezone.utc).strftime(f'%Y-%m-%d{separator}%H:%M:%SZ')
    elif isinstance(t, datetime):
        return t.astimezone(timezone.utc).strftime(f'%Y-%m-%d{separator}%H:%M:%SZ')


def time_trim_ms(t: datetime | float | int):
    if type(t) == float:
        return int(t)
    elif type(t) == datetime:
        return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)
    return t


# TODO: change to iterator style?
def load_yaml_fss_file_stream(yaml_file: Path, process_item_func: typing.Callable[[dict, Path], None], encoding='utf-8'):
    """
    Process YAML file in a streaming fashion, applying custom processing function to each item.

    Args:
        yaml_file: Path to YAML file
        process_item_func: Function that processes each item (data, path)
        encoding: File encoding
    """
    try:
        total_size = yaml_file.stat().st_size
        items_processed = 0
        last_print_time = time.time()
        print(f'Processing {yaml_file.name}, size: {total_size} bytes...')

        with open(yaml_file, 'r', encoding=encoding) as f:
            loader = yaml.CLoader(f)
            try:
                # Skip the beginning of the stream and document
                while not isinstance(loader.get_event(), yaml.MappingStartEvent):
                    pass  # Skip all events until the start of the root dictionary

                # Process records
                while True:
                    # Get the key
                    event = loader.get_event()
                    if isinstance(event, yaml.MappingEndEvent):
                        break
                    if not isinstance(event, yaml.ScalarEvent):
                        raise ValueError(f'Expected key (ScalarEvent), got {type(event)}')
                    key = event.value

                    # Wait for the start of the nested dictionary
                    event = loader.get_event()
                    if not isinstance(event, yaml.MappingStartEvent):
                        raise ValueError(f'Expected mapping start, got {type(event)}')

                    # Get file data as a dictionary
                    data = {}
                    while True:
                        event = loader.get_event()
                        if isinstance(event, yaml.MappingEndEvent):
                            break

                        if not isinstance(event, yaml.ScalarEvent):
                            raise ValueError(f'Expected field name (ScalarEvent), got {type(event)}')
                        field = event.value

                        event = loader.get_event()
                        if not isinstance(event, yaml.ScalarEvent):
                            raise ValueError(f'Expected value (ScalarEvent) for field {field}, got {type(event)}')
                        value = event.value

                        # Convert size to int
                        if field == 'size':
                            try:
                                value = int(value)
                            except (ValueError, TypeError):
                                value = -1

                        data[field] = value

                    # Process item using provided function
                    process_item_func(data, Path(key))
                    items_processed += 1

                    # Show progress every 5 seconds
                    current_time = time.time()
                    if current_time - last_print_time >= 5:
                        position = f.tell()
                        progress = (position / total_size) * 100 if total_size > 0 else 0
                        print(f'Processing {yaml_file.name}: {progress:.1f}% ({items_processed} items)')
                        last_print_time = current_time
            finally:
                loader.dispose()

        # Output final progress
        print(f'Completed {yaml_file.name}: 100% ({items_processed} items)')
        return True
    except Exception as e:
        print(f'ERROR processing {yaml_file.name}: {str(e)}')
        traceback.print_exc()
        return False


def load_yaml(input_file: Path, retries: int = 0, retries_pause: int = 0, encoding='utf-8', return_on_fail=None):
    for attempt in range(retries + 1):
        try:
            with open(input_file, 'r', encoding=encoding) as f:
                store = yaml.safe_load(f)
                if store is None:
                    store = return_on_fail
            return store
        except FileNotFoundError:
            print('ERROR: file not found: ', str(input_file))
            return return_on_fail
        except yaml.YAMLError as e:
            print(f'ERROR: error in YAML file {str(input_file)}: {e}')
            return return_on_fail
        except IOError as e:
            if attempt < retries:
                print(f'ERROR: I/O error({e.errno})! Retrying in {retries_pause} seconds... File: {str(input_file)}. Error: {e.strerror}')
                time.sleep(retries_pause)
            else:
                print(f'ERROR: I/O error({e.errno})! File: {str(input_file)}. Error: {e.strerror}')
                return return_on_fail


def save_to_csv(file_path: Path, data, headers=None):
    """
    Save data to a CSV file.

    Args:
        file_path: Path to the CSV file
        data: List of rows to save
        headers: Optional list of column headers
    """
    with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';')

        # Write headers if provided
        if headers:
            csv_writer.writerow(headers)

        csv_writer.writerows(data)


def save_csv_file_list_or_print(header: str, data: list[tuple], csv_filename=None, csv_headers=None):
    """
    Print a list of files and optionally save it to a CSV file.

    Args:
        header: Header text for the list
        files_list: List of file tuples
        csv_filename: Optional filename to save as CSV
        csv_headers: Optional list of column headers for the CSV
    """
    if not data:
        print(f'{header} not detected')
        return

    data_str = [list(map(str, item)) for item in data]
    if not csv_filename:
        print(f'{header} list:')
        for item in data_str:
            print(';   '.join(item))

    if csv_filename:
        save_to_csv(Path(csv_filename), data_str, csv_headers)
        print(f'{header} saved to {csv_filename}')


def save_result_and_print_info(changed_files, moved_files, deleted_files, new_files, duplicate_files):
    """
    Print and optionally save the results of changed, moved, deleted, new files and duplicates.

    Args:
        changed_files: List of changed files
        moved_files: List of moved files
        deleted_files: List of deleted files
        new_files: List of new files
        duplicate_files: List of duplicate files (optional)
    """
    changed_headers = ['File Path', 'Changes']
    save_csv_file_list_or_print('Changed files', changed_files, 'changed.csv', changed_headers)

    moved_headers = ['Source Path', 'Destination Path', 'Move Type']
    save_csv_file_list_or_print('Moved files', moved_files, 'moved.csv', moved_headers)

    deleted_headers = ['File Path']
    save_csv_file_list_or_print('Deleted files', deleted_files, 'deleted.csv', deleted_headers)

    new_headers = ['File Path']
    save_csv_file_list_or_print('New files', new_files, 'new.csv', new_headers)

    duplicate_headers = ['Source File', 'Duplicate File', 'Match Type', 'Size', 'MD5 Hash']
    save_csv_file_list_or_print('Duplicate files', duplicate_files, 'duplicates.csv', duplicate_headers)
