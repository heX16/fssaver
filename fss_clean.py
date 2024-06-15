import os
import argparse

def remove_index_hash_files(directory):
    # Walk through the directory tree
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.index_hash.yaml'):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f'Removed: {file_path}')
                except Exception as e:
                    print(f'Error removing {file_path}: {e}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Remove .index_hash.yaml files recursively from a given directory.')
    parser.add_argument('path', type=str, help='The path to the directory to scan.')
    args = parser.parse_args()

    remove_index_hash_files(args.path)

