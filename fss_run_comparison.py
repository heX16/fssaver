import os
import subprocess
from pathlib import Path


def sh(command: str) -> int:
    return subprocess.call(command, shell=True)


current_directory = Path.cwd()

# Get the directory where this script is located
script_directory = Path(__file__).resolve().parent
# Path to the executable file fs_struct_comparison.py
executable_path = script_directory / 'fss_compare.py'

if not executable_path.exists():
    print("Error: Executable file fs_struct_comparison.py not found in the script directory.")
    exit(1)

# Look for the index_hash_all.yaml file (file1) in the current directory
file1 = current_directory / 'index_hash_all.yaml'

if not file1.exists():
    print("File index_hash_all.yaml (file1) not found in the script directory.")
    exit(1)

# Look for files index_hash_all_*.yaml in the current directory
matching_files = list(current_directory.glob('index_hash_all_*.yaml'))

if not matching_files:
    print("Files index_hash_all_*.yaml not found in the script directory.")
    exit(1)

# Select the first file from the found ones (file2)
file2 = matching_files[0]

# Run the fs_struct_comparison.py program with arguments file1 and file2
cmd = f"python {executable_path} --new={file1} --old={file2}"
print('Run:', cmd)
result = sh(cmd)

if result != 0:
    print(f"Error occurred while executing the command")
else:
    print("Program fs_struct_comparison.py executed successfully.")
