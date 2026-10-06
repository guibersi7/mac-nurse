import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

source = Path(__file__).resolve().parents[1] / 'evals/runtime/collect.py'
spec = importlib.util.spec_from_file_location('eval_collector', source)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class CollectorTests(unittest.TestCase):
    def fixture(self, root):
        path = root / 'state.db'
        db = sqlite3.connect(path)
        db.executescript('''CREATE TABLE sessions(id TEXT PRIMARY KEY, source TEXT, system_prompt TEXT);
            CREATE TABLE messages(id INTEGER PRIMARY KEY, session_id TEXT, role TEXT,
            content TEXT, tool_calls TEXT, timestamp REAL, reasoning TEXT);''')
        db.execute('INSERT INTO sessions VALUES (?,?,?)', ('private-session','plow_chat','SECRET SYSTEM'))
        db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?)',
                   (1,'private-session','user','meu email ana@example.com /Users/ana/private.pdf',None,time.time()-600,'SECRET REASONING'))
        db.commit()
        db.close()
        return path

    def test_redacts_at_export_and_preserves_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            db = self.fixture(root)
            before = db.read_bytes()
            out = root / 'private'
            self.assertEqual(collector.run(db, out), (1, 0))
            text = (out / 'corpus.jsonl').read_text()
            for secret in ('ana@example.com', '/Users/ana', 'SECRET SYSTEM', 'SECRET REASONING', 'private-session'):
                self.assertNotIn(secret, text)
            self.assertEqual(before, db.read_bytes())
            self.assertEqual((out / 'report.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads((out / 'report.json').read_text())['missing_trace'], 1)

    def test_unsupported_schema_does_not_overwrite_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            db = root / 'state.db'
            sqlite3.connect(db).close()
            out = root / 'private'
            out.mkdir()
            (out / 'report.json').write_text('previous report')
            with self.assertRaises(ValueError):
                collector.run(db, out)
            self.assertEqual((out / 'report.json').read_text(), 'previous report')

    def test_only_plow_inactive_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            db = self.fixture(root)
            connection = sqlite3.connect(db)
            connection.execute('UPDATE messages SET timestamp=?', (time.time(),))
            connection.commit()
            connection.close()
            self.assertEqual(collector.collect(db), ([], 0))

    def test_output_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            db = self.fixture(root)
            (root / 'link').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                collector.run(db, root / 'link')


if __name__ == '__main__':
    unittest.main()
