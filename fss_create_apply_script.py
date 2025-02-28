"""
Create Apply Script

Usage:
  fss_create_apply_script.py [--input=<csv>] [--output=<script>] [--wnd | --linux]
  fss_create_apply_script.py -h | --help

Options:
  -h --help            Show this help message and exit.
  --input=<csv>        Input CSV file [default: changed.csv]
  --output=<script>    Output script file [default: apply_changed.sh]
  --wnd                Create Windows batch script regardless of current OS
  --linux              Create Linux shell script regardless of current OS
"""

import csv
from pathlib import Path
from docopt import docopt
from fss_utils import is_wnd


def create_shell_command(src: str, dst: str, operation: str, is_windows: bool) -> str:
    """
    Creates shell command for the specified OS type.

    Args:
        src: Source file path
        dst: Destination file path
        operation: Operation type (move, rename, etc.)
        is_windows: Whether to create Windows commands

    Returns:
        Command string for the specified OS
    """
    # Convert paths to proper format
    src_path = Path(src)
    dst_path = Path(dst)

    # Ensure the destination directory exists
    dst_dir = dst_path.parent

    if is_windows:
        mkdir_cmd = f'mkdir "{dst_dir}" 2>nul'
        move_cmd = f'move "{src_path}" "{dst_path}"'
    else:
        mkdir_cmd = f'mkdir -p "{dst_dir}"'
        move_cmd = f'mv "{src_path}" "{dst_path}"'

    return f'{mkdir_cmd}\n{move_cmd}'


def generate_script_content(csv_file: Path, is_windows: bool) -> str:
    """
    Generates script content based on CSV data and target OS.

    Args:
        csv_file: Path to the CSV file
        is_windows: Whether to create Windows commands

    Returns:
        Generated script content as string
    """
    # Start with appropriate header
    if is_windows:
        script_content = '@echo off\n'
    else:
        script_content = '#!/bin/sh\n'

    try:
        with open(csv_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            for i, row in enumerate(reader, 1):
                # Check row format
                if len(row) != 3:
                    # Skip rows that don't have exactly 3 elements
                    print(f"Warning: Row {i} skipped, invalid format: {row}")
                    continue

                src, dst, operation = row

                # Check for empty values
                if not src or not dst:
                    print(f"Warning: Row {i} skipped, empty source or destination: {row}")
                    continue

                command = create_shell_command(src, dst, operation, is_windows)
                script_content += f'{command}\n'

        return script_content

    except Exception as e:
        print(f"Error processing CSV file: {e}")
        return ""


def save_script(content: str, script_file: Path, is_windows: bool):
    """
    Saves the script content to a file and sets appropriate permissions.

    Args:
        content: Script content to save
        script_file: Path where to save the script
        is_windows: Whether this is a Windows script
    """
    try:
        with open(script_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)

        # Make the script executable on Unix systems
        if not is_windows:
            script_file.chmod(script_file.stat().st_mode | 0o755)

        print(f"Script created successfully: {script_file}")

    except Exception as e:
        print(f"Error saving script: {e}")


def main():
    arguments = docopt(__doc__)
    input_file = Path(arguments['--input'] or 'moved.csv')
    output_file = Path(arguments['--output'] or 'apply_moved.sh')

    # Determine target OS format (with manual override from arguments)
    force_windows = arguments.get('--wnd', False)
    force_linux = arguments.get('--linux', False)

    if force_windows and force_linux:
        print("Error: Cannot specify both --wnd and --linux")
        return

    # Determine target script type
    is_windows = force_windows or (is_wnd() and not force_linux)

    # Update extension based on script type
    if is_windows and output_file.suffix != '.bat':
        output_file = output_file.with_suffix('.bat')
        print(f"Note: Changed output filename to {output_file}")

    if not input_file.is_file():
        print(f"Error: Input file not found: {input_file}")
        return

    # Generate and save the script
    script_content = generate_script_content(input_file, is_windows)
    if script_content:
        save_script(script_content, output_file, is_windows)


if __name__ == "__main__":
    main()