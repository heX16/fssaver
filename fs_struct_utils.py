import yaml
import csv
from pathlib import Path
from datetime import datetime
from datetime import datetime, timezone


def get_file_content(file_name, encoding='utf-8'):
    try:
        with open(file_name, 'r', encoding=encoding) as f:
            return str(f.read())
    except IOError:
        return ''


def save_to_yaml(data, output_file, encoding='utf-8'):
    data = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    if get_file_content(output_file, encoding=encoding) != data:
        with open(output_file, 'w', encoding=encoding) as f:
            f.write(data)


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

def load_yaml(input_file, encoding='utf-8', result_on_fail=None):
    try:
        with open(input_file, 'r', encoding=encoding) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print('ERROR: file not found: ', str(input_file))
        return result_on_fail
    except yaml.YAMLError as e:
        print(f'ERROR: error in YAML file {input_file}: {e}')
        return result_on_fail
    except IOError as e:
        print('ERROR: I/O error({0}): {1}'.format(e.errno, e.strerror))
        return result_on_fail


def save_to_csv(file_path: Path, data):
    with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=';')
        csv_writer.writerows(data)


def print_file_list(header: str, files_list: list[tuple], csv_filename=None):
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


def print_result(changed_files, moved_files, deleted_files, new_files):
    """
    Print and optionally save the results of changed, moved, and deleted files.
    """
    print_file_list("Changed files", changed_files, "changed.csv")
    print_file_list("Moved files", moved_files, "moved.csv")
    print_file_list("Deleted files", deleted_files, "deleted.csv")
    print_file_list("New files", new_files, "new.csv")
