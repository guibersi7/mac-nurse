import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / 'skills/mac-health/scripts/mac_inventory.py'
spec = importlib.util.spec_from_file_location('inventory', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def test_only_manifest_candidates_and_no_symlink_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'Cargo.toml').write_text('[package]')
            (root / 'target').mkdir()
            (root / 'target' / 'keep').write_text('untouched')
            (root / 'other').mkdir()
            (root / 'other' / 'node_modules').mkdir()
            (root / 'linked').symlink_to(root, target_is_directory=True)
            result = module.inventory(root)
            self.assertEqual([x['kind'] for x in result['candidates']], ['target'])
            self.assertFalse(result['candidates'][0]['eligible_for_deletion'])
            self.assertEqual((root / 'target' / 'keep').read_text(), 'untouched')

    def test_reject_symlink_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'link').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                module.inventory(root / 'link')

    def test_bounded_scan_marks_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            for i in range(5):
                (root / str(i)).mkdir()
            self.assertTrue(module.inventory(root, max_entries=1)['truncated'])

    def test_linux_container_is_rejected(self):
        with patch.object(module.platform, 'system', return_value='Linux'):
            with self.assertRaises(RuntimeError):
                module.snapshot()


if __name__ == '__main__':
    unittest.main()
