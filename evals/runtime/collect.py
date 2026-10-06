"""Private offline Hermes export. Reads verified core schema; never executes transcript content."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import MAX_BYTES, normalize, private_write, report

REQUIRED = {'sessions': {'id', 'source'},
            'messages': {'id', 'session_id', 'role', 'content', 'tool_calls', 'timestamp'}}


def collect(db_path, source='plow_chat', limit=100, settle_seconds=120):
    """Export inactive sessions. Tool calls remain untrusted text, not asserted events."""
    if not 1 <= limit <= 1000 or settle_seconds < 0:
        raise ValueError('invalid limits')
    db_path = Path(db_path)
    if db_path.is_symlink() or not db_path.is_file():
        raise ValueError('missing or linked state database')
    db = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    db.execute('PRAGMA query_only=ON')
    try:
        db.execute('BEGIN')
        for table, columns in REQUIRED.items():
            available = {row[1] for row in db.execute('PRAGMA table_info(' + table + ')')}
            if not columns <= available:
                raise ValueError('unsupported Hermes schema')
        cutoff = time.time() - settle_seconds
        sessions = db.execute('''SELECT s.id FROM sessions s JOIN messages m ON m.session_id=s.id
            WHERE s.source=? GROUP BY s.id HAVING MAX(m.timestamp) < ?
            ORDER BY MAX(m.timestamp) DESC LIMIT ?''', (source, cutoff, limit)).fetchall()
        corpus, omitted, size = [], 0, 0
        for (session_id,) in sessions:
            rows = db.execute('''SELECT role, substr(content,1,100001), substr(tool_calls,1,100001)
                FROM messages WHERE session_id=? ORDER BY id LIMIT 501''', (session_id,)).fetchall()
            if len(rows) > 500:
                omitted += 1
                continue
            messages = []
            oversize = False
            for role, content, calls in rows:
                if role not in ('user', 'assistant', 'tool'):
                    continue
                if len(content or '') > 100000 or len(calls or '') > 100000:
                    oversize = True
                    break
                if content:
                    messages.append({'role': role, 'content': content})
                if calls:
                    # Keep for reviewer. No parsing/inference of grants or success.
                    messages.append({'role': role, 'content': 'Untrusted recorded tool call: ' + calls})
            if oversize or not messages or len(messages) > 500:
                omitted += 1
                continue
            record = normalize({'id': session_id, 'messages': messages, 'events': []})
            encoded = json.dumps(record, ensure_ascii=False).encode('utf-8')
            if size + len(encoded) + 1 > MAX_BYTES:
                omitted += 1
                continue
            size += len(encoded) + 1
            corpus.append(record)
        return corpus, omitted
    finally:
        db.close()


def run(db_path, output_dir, source='plow_chat'):
    output_dir = Path(output_dir)
    # Predictable state root; fail closed on links, including any ancestor.
    if any(p.is_symlink() for p in (output_dir, *output_dir.parents)):
        raise ValueError('linked output directory')
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    corpus, omitted = collect(db_path, source=source)
    private_write(output_dir / 'corpus.jsonl', ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in corpus))
    result = report(corpus)
    result.update({'source': 'Hermes SQLite read-only', 'omitted_sessions': omitted,
                   'sampled_at': time.time(), 'trace_status': 'Tool calls retained as text; grants/outcomes require review',
                   'retention': 'Latest bounded snapshot overwritten on each pass; no raw export retained'})
    private_write(output_dir / 'report.json', json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    return len(corpus), omitted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('/var/lib/hermes/state.db'))
    parser.add_argument('--output-dir', type=Path, default=Path('/var/lib/hermes/mac-nurse-evals'))
    parser.add_argument('--source', default='plow_chat')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        count, omitted = run(args.db, args.output_dir, args.source)
        print(f'mac-nurse-evals: sampled={count}, omitted={omitted}; private review required')
    except (OSError, sqlite3.Error, ValueError, TypeError):
        print('mac-nurse-evals: collection unavailable; no transcript details logged', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
