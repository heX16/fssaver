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
        old_attributes = win32file.GetFileAttributes(filename)
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
            win32file.SetFileAttributes(filename, new_attributes)
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
                win32file.SetFileAttributes(filename, old_attributes)
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


def time_to_iso8601_gmt_str(t: datetime or float or int, separator='_'):
    if isinstance(t, (float, int)):
        return datetime.fromtimestamp(t, tz=timezone.utc).strftime(f'%Y-%m-%d{separator}%H:%M:%SZ')
    elif isinstance(t, datetime):
        return t.astimezone(timezone.utc).strftime(f'%Y-%m-%d{separator}%H:%M:%SZ')


def time_trim_ms(t: datetime or float or int):
    if type(t) == float:
        return int(t)
    elif type(t) == datetime:
        return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)
    return t

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


def save_to_csv(file_path: Path, data):
    with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';')
        csv_writer.writerows(data)


def save_file_list_and_print_info(header: str, files_list: list[tuple], csv_filename=None):
    """
    Print a list of files and optionally save it to a CSV file.
    """
    if not files_list:
        print(f"{header} not detected")
        return

    list_str = [list(map(str, item)) for item in files_list]
    print(f"{header} list:")
    for item in list_str:
        print(';   '.join(item))

    if csv_filename:
        save_to_csv(Path(csv_filename), list_str)
        print(f"{header} saved to {csv_filename}")


def save_result_and_print_info(changed_files, moved_files, deleted_files, new_files):
    """
    Print and optionally save the results of changed, moved, and deleted files.
    """
    save_file_list_and_print_info("Changed files", changed_files, "changed.csv")
    save_file_list_and_print_info("Moved files", moved_files, "moved.csv")
    save_file_list_and_print_info("Deleted files", deleted_files, "deleted.csv")
    save_file_list_and_print_info("New files", new_files, "new.csv")
