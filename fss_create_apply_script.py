"""
Create Apply Script

Usage:
  fss_create_apply_script.py [--input=<csv>] [--output=<script>] [--wnd | --linux] [--progress]
  fss_create_apply_script.py -h | --help

Options:
  -h --help            Show this help message and exit.
  --input=<csv>        Input CSV file [default: moved.csv]
  --output=<script>    Output script file [default: apply_changed.sh]
  --wnd                Create Windows batch script regardless of current OS
  --linux              Create Linux shell script regardless of current OS
  --progress           Show progress percentage during execution
"""

import csv
from pathlib import Path
from docopt import docopt
from fss_utils import is_wnd


def generate_script_content(csv_file: Path, is_windows: bool, show_progress: bool = False) -> str:
    """
    Generates script content based on CSV data and target OS.

    Args:
        csv_file: Path to the CSV file
        is_windows: Whether to create Windows commands
        show_progress: Whether to show progress percentage during execution

    Returns:
        Generated script content as string
    """
    # Start with appropriate header
    if is_windows:
        script_content = '@echo off\n'
    else:
        script_content = '#!/bin/sh\n'

    # Lists to store directories and move commands
    directories = set()
    move_commands = []

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

                # Extract destination directory
                dst_path = Path(dst)
                dst_dir = dst_path.parent
                if dst_dir and str(dst_dir) != '.':
                    # Store the directory with proper path separator
                    dir_str = str(dst_dir)
                    if is_windows:
                        # Ensure Windows path format
                        dir_str = dir_str.replace('/', '\\')
                    else:
                        # Ensure Unix path format
                        dir_str = dir_str.replace('\\', '/')
                    directories.add(dir_str)

                # Create move command with proper path format
                src_str = str(src)
                dst_str = str(dst)
                if is_windows:
                    # Ensure Windows path format for display
                    src_str = src_str.replace('/', '\\')
                    dst_str = dst_str.replace('/', '\\')
                    move_cmd = f'move "{src_str}" "{dst_str}"'
                else:
                    # Ensure Unix path format for display
                    src_str = src_str.replace('\\', '/')
                    dst_str = dst_str.replace('\\', '/')
                    move_cmd = f'mv "{src_str}" "{dst_str}"'

                move_commands.append(move_cmd)

        # Add directory creation commands
        if directories:
            if is_windows:
                script_content += "\nREM Create directories\n"
            else:
                script_content += "\n# Create directories\n"

            for directory in sorted(directories):
                if is_windows:
                    script_content += f'mkdir "{directory}" 2>nul\n'
                else:
                    script_content += f'mkdir -p "{directory}"\n'

        # Add move commands
        if move_commands:
            if is_windows:
                script_content += "\nREM Move files\n"
            else:
                script_content += "\n# Move files\n"

            # Add progress reporting
            total_moves = len(move_commands)
            for i, move_cmd in enumerate(move_commands):
                script_content += move_cmd + '\n'

                # Show progress every 100 files if enabled
                if show_progress and (i + 1) % 100 == 0 and i < total_moves - 1:
                    percent_done = int((i + 1) / total_moves * 100)
                    if is_windows:
                        script_content += f'echo Progress: {percent_done}%% ({i + 1} of {total_moves})\n'
                    else:
                        script_content += f'echo "Progress: {percent_done}% ({i + 1} of {total_moves})"\n'

            # Show 100% completion at the end if progress reporting is enabled
            if show_progress:
                if is_windows:
                    script_content += f'echo Progress: 100%% ({total_moves} of {total_moves})\n'
                else:
                    script_content += f'echo "Progress: 100% ({total_moves} of {total_moves})"\n'

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
    input_file = Path(arguments['--input'])
    output_file = Path(arguments['--output'])
    show_progress = arguments.get('--progress', False)

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
    script_content = generate_script_content(input_file, is_windows, show_progress)
    if script_content:
        save_script(script_content, output_file, is_windows)


if __name__ == "__main__":
    main()