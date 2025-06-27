import unittest
import subprocess
import os
import shutil
import yaml
from pathlib import Path

class TestFSSScripts(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = Path('test_directory')
        self.test_dir.mkdir(exist_ok=True)

        # Create sample files and directories
        (self.test_dir / 'file1.txt').write_text('Content of file1')
        (self.test_dir / 'file2.txt').write_text('Content of file2')
        subdir = self.test_dir / 'subdir'
        subdir.mkdir()
        (subdir / 'file3.txt').write_text('Content of file3')
    
    def tearDown(self):
        # Remove temporary directory after tests
        shutil.rmtree(self.test_dir)
    
    def test_fss_save(self):
        # Run fss_save.py on the test directory
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)

        # Check that .index_hash.yaml files are created
        index_file = self.test_dir / '.index_hash.yaml'
        self.assertTrue(index_file.exists(), 'Index file not created in test directory')

        subdir_index_file = self.test_dir / 'subdir' / '.index_hash.yaml'
        self.assertTrue(subdir_index_file.exists(), 'Index file not created in subdirectory')

        # Load and check contents of index file at root directory
        with index_file.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.assertIn('file1.txt', data, 'file1.txt not found in index file')
        self.assertIn('file2.txt', data, 'file2.txt not found in index file')
        self.assertIn('subdir', data, 'subdir not found in index file')
        self.assertEqual(data['file1.txt']['type'], 'file', 'Incorrect type for file1.txt')
        self.assertEqual(data['subdir']['type'], 'dir', 'Incorrect type for subdir')

        # Load and check contents of index file in subdirectory
        with subdir_index_file.open('r', encoding='utf-8') as f:
            sub_data = yaml.safe_load(f)

        self.assertIn('file3.txt', sub_data, 'file3.txt not found in subdirectory index file')
        self.assertEqual(sub_data['file3.txt']['type'], 'file', 'Incorrect type for file3.txt')

    def test_fss_merge(self):
        # First, run fss_save.py
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)

        # Run fss_merge.py
        merged_file = self.test_dir / 'merged.yaml'
        subprocess.run(['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file), '--not-add-date'], check=True)

        # Check that merged file is created
        self.assertTrue(merged_file.exists(), 'Merged file not created')

        # Load and check contents of merged file
        with merged_file.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Check presence of all files and directories
        expected_paths = [
            'file1.txt',
            'file2.txt',
            'subdir',
            'subdir/file3.txt',
        ]
        for path in expected_paths:
            self.assertIn(path, data, f'{path} not found in merged file')
    
    def test_fss_compare(self):
        # First, create two versions of the directory
        version1 = self.test_dir / 'version1'
        version2 = self.test_dir / 'version2'

        shutil.copytree(self.test_dir, version1)
        shutil.copytree(self.test_dir, version2)

        # Modify version2
        (version2 / 'file2.txt').write_text('Modified content of file2')
        (version2 / 'file4.txt').write_text('Content of new file4')
        os.remove(version2 / 'file1.txt')

        # Run fss_save.py on both versions
        subprocess.run(['python', 'fss_save.py', str(version1)], check=True)
        subprocess.run(['python', 'fss_save.py', str(version2)], check=True)

        # Run fss_merge.py on both versions to create merged files
        merged_file1 = version1 / 'merged.yaml'
        merged_file2 = version2 / 'merged.yaml'
        subprocess.run(['python', 'fss_merge.py', str(version1), '--file', str(merged_file1), '--not-add-date'], check=True)
        subprocess.run(['python', 'fss_merge.py', str(version2), '--file', str(merged_file2), '--not-add-date'], check=True)

        # Run fss_compare.py
        compare_output = subprocess.run(['python', 'fss_compare.py', str(merged_file1), str(merged_file2)], capture_output=True, text=True)

        # Check the output for expected changes
        output = compare_output.stdout
        # Print output for debugging
        print(output)

        self.assertIn('Changed files', output, 'Changed files section not found in compare output')
        self.assertIn('file2.txt', output, 'file2.txt should be listed as changed')
        self.assertIn('Deleted files', output, 'Deleted files section not found in compare output')
        self.assertIn('file1.txt', output, 'file1.txt should be listed as deleted')
        self.assertIn('New files', output, 'New files section not found in compare output')
        self.assertIn('file4.txt', output, 'file4.txt should be listed as new')

        # Cleanup
        shutil.rmtree(version1)
        shutil.rmtree(version2)
    
    def test_fss_compare_with_modifications(self):
        # Run initial fss_save and fss_merge
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        merged_file_initial = self.test_dir / 'merged_initial.yaml'
        subprocess.run(['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file_initial), '--not-add-date'], check=True)

        # Make modifications in test_dir
        (self.test_dir / 'file5.txt').write_text('Content of new file5')
        os.remove(self.test_dir / 'file1.txt')
        (self.test_dir / 'file2.txt').write_text('Updated content of file2')

        # Run fss_save and fss_merge again to create new merged file
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        merged_file_new = self.test_dir / 'merged_new.yaml'
        subprocess.run(['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file_new), '--not-add-date'], check=True)

        # Compare the two merged files
        compare_output = subprocess.run(['python', 'fss_compare.py', str(merged_file_initial), str(merged_file_new)], capture_output=True, text=True)

        # Check the output for expected changes
        output = compare_output.stdout
        # Print output for debugging
        print(output)

        self.assertIn('Changed files', output, 'Changed files section not found in compare output')
        self.assertIn('file2.txt', output, 'file2.txt should be listed as changed')
        self.assertIn('Deleted files', output, 'Deleted files section not found in compare output')
        self.assertIn('file1.txt', output, 'file1.txt should be listed as deleted')
        self.assertIn('New files', output, 'New files section not found in compare output')
        self.assertIn('file5.txt', output, 'file5.txt should be listed as new')
    
if __name__ == '__main__':
    unittest.main()
