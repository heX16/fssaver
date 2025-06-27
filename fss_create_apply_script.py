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

# OS-specific strings template dictionary
GEN_STRINGS = {
    # Script header
    'script_header': '',  # Script header line

    # Directory operations
    'dir_comment': '',    # Comment for directory creation section
    'mkdir_cmd': '',      # Directory creation command template

    # File operations
    'file_comment': '',   # Comment for file operations section
    'move_cmd': '',       # Move file command template

    # Progress reporting
    'progress_fmt': '',   # Progress report format
    'final_progress_fmt': '',  # Final progress report format

    # Path separators
    'path_sep': '',       # Path separator character
}


def initialize_gen_strings(is_windows: bool) -> dict:
    """
    Initialize the OS-specific strings dictionary based on the target OS.

    Args:
        is_windows: Whether to create Windows commands

    Returns:
        Dictionary with OS-specific string templates
    """
    strings = GEN_STRINGS.copy()

    if is_windows:
        strings.update({
            'script_header': '@echo off',
            'dir_comment': 'REM Create directories',
            'mkdir_cmd': 'mkdir "{0}" 2>nul',
            'file_comment': 'REM Move files',
            'move_cmd': 'move "{0}" "{1}"',
            'progress_fmt': 'echo Progress: {0}%% ({1} of {2})',
            'final_progress_fmt': 'echo Progress: 100%% ({0} of {0})',
            'path_sep': '\\',
        })
    else:
        strings.update({
            'script_header': '#!/bin/sh',
            'dir_comment': '# Create directories',
            'mkdir_cmd': 'mkdir -p "{0}"',
            'file_comment': '# Move files',
            'move_cmd': 'mv "{0}" "{1}"',
            'progress_fmt': 'echo "Progress: {0}% ({1} of {2})"',
            'final_progress_fmt': 'echo "Progress: 100% ({0} of {0})"',
            'path_sep': '/',
        })

    return strings


def normalize_path(path_str: str, gen_strings: dict) -> str:
    """
    Normalize path separators for the target OS.

    Args:
        path_str: Path string to normalize
        os_strings: Dictionary with OS-specific strings

    Returns:
        Normalized path string
    """
    if gen_strings['path_sep'] == '\\':
        return path_str.replace('/', '\\')
    else:
        return path_str.replace('\\', '/')


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
    # Initialize OS-specific strings
    gen_strs = initialize_gen_strings(is_windows)

    # Start with appropriate header
    script_content = gen_strs['script_header'] + '\n'

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
                    print(f'Warning: Row {i} skipped, invalid format: {row}')
                    continue

                src, dst, operation = row

                # Check for empty values
                if not src or not dst:
                    print(f'Warning: Row {i} skipped, empty source or destination: {row}')
                    continue

                # Extract destination directory
                dst_path = Path(dst)
                dst_dir = dst_path.parent
                if dst_dir and str(dst_dir) != '.':
                    # Store the directory with proper path separator
                    dir_str = normalize_path(str(dst_dir), gen_strs)
                    directories.add(dir_str)

                # Create move command with proper path format
                src_str = normalize_path(str(src), gen_strs)
                dst_str = normalize_path(str(dst), gen_strs)
                move_cmd = gen_strs['move_cmd'].format(src_str, dst_str)
                move_commands.append(move_cmd)

        # Add directory creation commands
        if directories:
            script_content += f'\n{gen_strs["dir_comment"]}\n'
            for directory in sorted(directories):
                script_content += gen_strs['mkdir_cmd'].format(directory) + '\n'

        # Add move commands
        if move_commands:
            script_content += f'\n{gen_strs["file_comment"]}\n'

            # Add progress reporting
            total_moves = len(move_commands)
            for i, move_cmd in enumerate(move_commands):
                script_content += move_cmd + '\n'

                # Show progress every 100 files if enabled
                if show_progress and (i + 1) % 100 == 0 and i < total_moves - 1:
                    percent_done = int((i + 1) / total_moves * 100)
                    progress_line = gen_strs['progress_fmt'].format(
                        percent_done, i + 1, total_moves
                    )
                    script_content += progress_line + '\n'

            # Show 100% completion at the end if progress reporting is enabled
            if show_progress:
                final_progress = gen_strs['final_progress_fmt'].format(total_moves)
                script_content += final_progress + '\n'

        return script_content

    except Exception as e:
        print(f'Error processing CSV file: {e}')
        return ''


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

        print(f'Script created successfully: {script_file}')

    except Exception as e:
        print(f'Error saving script: {e}')


def main():
    arguments = docopt(__doc__)
    input_file = Path(arguments['--input'])
    output_file = Path(arguments['--output'])
    show_progress = arguments.get('--progress', False)

    # Determine target OS format (with manual override from arguments)
    force_windows = arguments.get('--wnd', False)
    force_linux = arguments.get('--linux', False)

    if force_windows and force_linux:
        print('Error: Cannot specify both --wnd and --linux')
        return

    # Determine target script type
    is_windows = force_windows or (is_wnd() and not force_linux)

    # Update extension based on script type
    if is_windows and output_file.suffix != '.bat':
        output_file = output_file.with_suffix('.bat')
        print(f'Note: Changed output filename to {output_file}')

    if not input_file.is_file():
        print(f'Error: Input file not found: {input_file}')
        return

    # Generate and save the script
    script_content = generate_script_content(input_file, is_windows, show_progress)
    if script_content:
        save_script(script_content, output_file, is_windows)


if __name__ == '__main__':
    main()