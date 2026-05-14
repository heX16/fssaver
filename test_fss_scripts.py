import unittest
import subprocess
import os
import shutil
import yaml
from pathlib import Path
from datetime import datetime
import tempfile

from fss_check import count_matching_files_with_topdir_progress, g_yaml_name

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
        
        # Copy test_exif.jpg from tests/ directory if it exists
        test_exif_source = Path('tests/test_exif.jpg')
        if test_exif_source.exists():
            shutil.copy2(test_exif_source, self.test_dir / 'test_exif.jpg')
    
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

    def test_fss_merge_file_arg_variants(self):
        # First, run fss_save.py
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)

        # Variant 1: --file is only a filename -> should be created inside start directory
        merged_file1 = self.test_dir / 'merged_name_only.yaml'
        subprocess.run(['python', 'fss_merge.py', str(self.test_dir), '--file', 'merged_name_only.yaml', '--not-add-date'], check=True)
        self.assertTrue(merged_file1.exists(), 'Merged file (name-only) not created inside start directory')

        # Variant 2: --file includes directory -> should not duplicate start directory
        merged_file2 = self.test_dir / 'merged_with_dir.yaml'
        subprocess.run(['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file2), '--not-add-date'], check=True)
        self.assertTrue(merged_file2.exists(), 'Merged file (with dir) not created')

    def test_fss_merge_add_date_default(self):
        # Covers the default behavior (no --not-add-date): file name gets date suffix
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)

        expected_date = datetime.now().strftime('%Y-%m-%d')
        base_name = 'merged_dated.yaml'
        expected_file = self.test_dir / f'merged_dated_{expected_date}.yaml'

        subprocess.run(['python', 'fss_merge.py', str(self.test_dir), '--file', base_name], check=True)
        self.assertTrue(expected_file.exists(), 'Merged file with date suffix not created')
    
    def test_fss_compare(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            version1 = tmp_path / 'version1'
            version2 = tmp_path / 'version2'
            out_dir = tmp_path / 'out'
            out_dir.mkdir()

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

            # Run fss_compare.py (strict args: --old/--new)
            compare_script = str(Path('fss_compare.py').resolve())
            compare_output = subprocess.run(
                ['python', compare_script, f'--old={merged_file1}', f'--new={merged_file2}'],
                cwd=str(out_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            # Print output for debugging
            print(compare_output.stdout)

            changed_csv = out_dir / 'changed.csv'
            deleted_csv = out_dir / 'deleted.csv'
            new_csv = out_dir / 'new.csv'

            self.assertTrue(changed_csv.exists(), 'changed.csv not created')
            self.assertTrue(deleted_csv.exists(), 'deleted.csv not created')
            self.assertTrue(new_csv.exists(), 'new.csv not created')

            self.assertIn('file2.txt', changed_csv.read_text(encoding='utf-8'), 'file2.txt should be listed in changed.csv')
            self.assertIn('file1.txt', deleted_csv.read_text(encoding='utf-8'), 'file1.txt should be listed in deleted.csv')
            self.assertIn('file4.txt', new_csv.read_text(encoding='utf-8'), 'file4.txt should be listed in new.csv')
    
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)

            # Compare the two merged files (strict args: --old/--new)
            compare_script = str(Path('fss_compare.py').resolve())
            compare_output = subprocess.run(
                ['python', compare_script, f'--old={merged_file_initial.resolve()}', f'--new={merged_file_new.resolve()}'],
                cwd=str(out_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            # Print output for debugging
            print(compare_output.stdout)

            changed_csv = out_dir / 'changed.csv'
            deleted_csv = out_dir / 'deleted.csv'
            new_csv = out_dir / 'new.csv'

            self.assertTrue(changed_csv.exists(), 'changed.csv not created')
            self.assertTrue(deleted_csv.exists(), 'deleted.csv not created')
            self.assertTrue(new_csv.exists(), 'new.csv not created')

            self.assertIn('file2.txt', changed_csv.read_text(encoding='utf-8'), 'file2.txt should be listed in changed.csv')
            self.assertIn('file1.txt', deleted_csv.read_text(encoding='utf-8'), 'file1.txt should be listed in deleted.csv')
            self.assertIn('file5.txt', new_csv.read_text(encoding='utf-8'), 'file5.txt should be listed in new.csv')
    
    def test_fss_save_exif_enabled(self):
        # Test EXIF extraction is enabled by default
        test_exif_source = Path('tests/test_exif.jpg')
        if not test_exif_source.exists():
            self.skipTest('test_exif.jpg not found in tests/ directory')
        
        # Run fss_save.py with default settings (EXIF enabled)
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        
        # Check that .index_hash.yaml file is created
        index_file = self.test_dir / '.index_hash.yaml'
        self.assertTrue(index_file.exists(), 'Index file not created in test directory')
        
        # Load and check contents
        with index_file.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Check that test_exif.jpg has EXIF datetime field
        if 'test_exif.jpg' in data:
            self.assertIn('ctime_exif', data['test_exif.jpg'], 
                        'EXIF datetime_original field should be present when EXIF is enabled')
    
    def test_fss_save_exif_disabled(self):
        # Test EXIF extraction can be disabled
        test_exif_source = Path('tests/test_exif.jpg')
        if not test_exif_source.exists():
            self.skipTest('test_exif.jpg not found in tests/ directory')
        
        # Run fss_save.py with EXIF disabled
        subprocess.run(['python', 'fss_save.py', str(self.test_dir), '--exif=0'], check=True)
        
        # Check that .index_hash.yaml file is created
        index_file = self.test_dir / '.index_hash.yaml'
        self.assertTrue(index_file.exists(), 'Index file not created in test directory')
        
        # Load and check contents
        with index_file.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Check that test_exif.jpg does NOT have EXIF datetime field
        if 'test_exif.jpg' in data:
            self.assertNotIn('ctime_exif', data['test_exif.jpg'], 
                           'EXIF datetime_original field should NOT be present when EXIF is disabled')

    def test_fss_check_single_index_ok(self):
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        check_script = str(Path('fss_check.py').resolve())
        index_path = self.test_dir / '.index_hash.yaml'
        r = subprocess.run(
            ['python', check_script, f'--fss={index_path}'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), '')

    def test_fss_check_bar_zero_and_no_progress_bar_flags(self):
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        check_script = str(Path('fss_check.py').resolve())
        index_path = self.test_dir / '.index_hash.yaml'
        for extra in [['--bar=0'], ['--no-progress-bar']]:
            r = subprocess.run(
                ['python', check_script, f'--fss={index_path}', *extra],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.strip(), '')

    def test_fss_check_merged_with_snapshot_base_ok(self):
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        merged_file = self.test_dir / 'merged_for_check.yaml'
        subprocess.run(
            ['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file), '--not-add-date'],
            check=True,
        )
        check_script = str(Path('fss_check.py').resolve())
        r = subprocess.run(
            ['python', check_script, f'--fss={merged_file}', f'--snapshot-base={self.test_dir}'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), '')

    def test_fss_check_merged_with_fssdir_alias_ok(self):
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        merged_file = self.test_dir / 'merged_fssdir_alias.yaml'
        subprocess.run(
            ['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file), '--not-add-date'],
            check=True,
        )
        check_script = str(Path('fss_check.py').resolve())
        r = subprocess.run(
            ['python', check_script, f'--fss={merged_file}', f'--fssdir={self.test_dir}'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), '')

    def test_fss_check_merged_requires_snapshot_base(self):
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        merged_file = self.test_dir / 'merged_need_root.yaml'
        subprocess.run(
            ['python', 'fss_merge.py', str(self.test_dir), '--file', str(merged_file), '--not-add-date'],
            check=True,
        )
        check_script = str(Path('fss_check.py').resolve())
        r = subprocess.run(
            ['python', check_script, f'--fss={merged_file}'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn('--snapshot-base', r.stdout)
        self.assertIn('--fssdir', r.stdout)

    def test_fss_check_dir_detects_md5_mismatch(self):
        subprocess.run(['python', 'fss_save.py', str(self.test_dir)], check=True)
        (self.test_dir / 'file1.txt').write_text('corrupted content')
        check_script = str(Path('fss_check.py').resolve())
        r = subprocess.run(
            ['python', check_script, f'--dir={self.test_dir}'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('MD5_MISMATCH', r.stdout)
        self.assertIn('file1.txt', r.stdout)

    def test_count_matching_files_with_topdir_progress_matches_rglob(self):
        import io

        def assert_matches_rglob(root: Path) -> None:
            ref = sum(1 for _ in root.rglob(g_yaml_name))
            self.assertEqual(
                count_matching_files_with_topdir_progress(
                    root, g_yaml_name, progress_stream=io.StringIO()
                ),
                ref,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / g_yaml_name).touch()
            d1 = root / 'd1'
            d1.mkdir()
            (d1 / g_yaml_name).touch()
            inner = d1 / 'inner'
            inner.mkdir()
            (inner / g_yaml_name).touch()
            dotdir = root / '.hidden'
            dotdir.mkdir()
            (dotdir / g_yaml_name).touch()

            assert_matches_rglob(root)

        with tempfile.TemporaryDirectory() as tmp:
            root_only = Path(tmp)
            (root_only / g_yaml_name).touch()
            assert_matches_rglob(root_only)

    def test_fss_check_skip_not_available_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            idx = root / 'idx.yaml'
            idx.write_text(
                '"only_missing.bin":\n'
                '  type: file\n'
                '  md5: abcdabcdabcdabcdabcdabcdabcdabcd\n'
                '  size: 999\n',
                encoding='utf-8',
            )
            check_script = str(Path('fss_check.py').resolve())
            r1 = subprocess.run(
                ['python', check_script, f'--fss={idx}', f'--snapshot-base={root}'],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 1, r1.stdout + r1.stderr)
            self.assertIn('MISSING', r1.stdout)

            r2 = subprocess.run(
                [
                    'python',
                    check_script,
                    f'--fss={idx}',
                    f'--snapshot-base={root}',
                    '--skip-not-available',
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            self.assertEqual(r2.stdout.strip(), '')

if __name__ == '__main__':
    unittest.main()
