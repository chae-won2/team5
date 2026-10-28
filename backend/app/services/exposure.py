"""Anonymous recommendation requests, eligible candidates and acknowledged list impressions."""
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

WINDOW_SECONDS = 7 * 86400
MAX_EXTRA_SECONDS = 120


class ExposureStorageError(RuntimeError):
    pass


class PostgresConnection:
    """Keep the small SQLite query set compatible with server-only PostgreSQL."""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        return self.connection.execute(re.sub(r'\bcandidates\b', 'app_private.exposure_candidates', re.sub(r'\blists\b', 'app_private.exposure_lists', sql)).replace('?', '%s'), parameters)


@contextmanager
def database():
    url = os.getenv('EXPOSURE_DATABASE_URL')
    if url:
        try:
            import psycopg
        except ImportError:
            raise ExposureStorageError('PostgreSQL 드라이버가 설치되지 않았습니다.') from None
        try:
            with psycopg.connect(url, sslmode='require', connect_timeout=10) as connection:
                yield PostgresConnection(connection)
        except psycopg.Error:
            # Connection exceptions can contain credentials: never forward them.
            raise ExposureStorageError('추천 기록 DB에 연결하지 못했습니다.') from None
        return
    if os.getenv('RENDER') == 'true':
        raise ExposureStorageError('영속 추천 기록 DB 설정이 필요합니다.')
    path = Path(os.getenv('EXPOSURE_DB_PATH', str(Path(__file__).resolve().parents[2] / 'var/exposure.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS lists (id TEXT PRIMARY KEY, created REAL NOT NULL, shown REAL, places TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS lists_shown ON lists(shown)')
            columns = {row[1] for row in db.execute('PRAGMA table_info(lists)')}
            for name, definition in {
                'policy': "TEXT NOT NULL DEFAULT 'legacy'",
                'policy_version': "TEXT NOT NULL DEFAULT 'legacy'",
                'mode': "TEXT NOT NULL DEFAULT 'production'",
                'run_id': 'TEXT', 'context': 'TEXT',
            }.items():
                if name not in columns:
                    db.execute(f'ALTER TABLE lists ADD COLUMN {name} {definition}')
            db.execute("""CREATE TABLE IF NOT EXISTS candidates (
                request_id TEXT NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
                place_id TEXT NOT NULL, walk_seconds REAL NOT NULL CHECK (walk_seconds >= 0),
                duration_min REAL NOT NULL CHECK (duration_min > 0),
                projected_total_seconds REAL NOT NULL CHECK (projected_total_seconds >= 0),
                assigned_rank INTEGER CHECK (assigned_rank BETWEEN 1 AND 3),
                expected_exposure REAL NOT NULL CHECK (expected_exposure BETWEEN 0 AND 1),
                PRIMARY KEY (request_id, place_id), UNIQUE (request_id, assigned_rank))""")
            db.execute('CREATE INDEX IF NOT EXISTS candidates_place ON candidates(place_id,request_id)')
            yield db
    finally:
        db.close()


def counts():
    result = {}
    with database() as db:
        for (places,) in db.execute("SELECT places FROM lists WHERE shown >= ? AND mode = 'production'", (time.time()-WINDOW_SECONDS,)):
            for rank, place_id in enumerate(json.loads(places)):
                top, total = result.get(place_id, (0, 0))
                result[place_id] = (top + (rank == 0), total + 1)
    return result


def summary():
    """Aggregate view for the operator dashboard: per-place rotation counts plus overall request volume."""
    cutoff = time.time() - WINDOW_SECONDS
    with database() as db:
        total = db.execute("SELECT COUNT(*) FROM lists WHERE created >= ? AND mode = 'production'", (cutoff,)).fetchone()[0]
        shown = db.execute("SELECT COUNT(*) FROM lists WHERE created >= ? AND mode = 'production' AND shown IS NOT NULL", (cutoff,)).fetchone()[0]
        empty = db.execute("SELECT COUNT(*) FROM lists WHERE created >= ? AND mode = 'production' AND places = '[]'", (cutoff,)).fetchone()[0]
    return {'requests_total': total, 'requests_shown': shown, 'requests_empty': empty, 'places': counts()}


def window_summary(weeks_ago):
    """Same shape as summary() but for the single 7-day window starting `weeks_ago` weeks before now; used to build real (not fabricated) trend comparisons."""
    now = time.time()
    hi, lo = now - weeks_ago * WINDOW_SECONDS, now - (weeks_ago + 1) * WINDOW_SECONDS
    with database() as db:
        total = db.execute("SELECT COUNT(*) FROM lists WHERE created >= ? AND created < ? AND mode = 'production'", (lo, hi)).fetchone()[0]
        shown = db.execute("SELECT COUNT(*) FROM lists WHERE created >= ? AND created < ? AND mode = 'production' AND shown IS NOT NULL", (lo, hi)).fetchone()[0]
        rows = db.execute("SELECT places FROM lists WHERE shown >= ? AND shown < ? AND mode = 'production'", (lo, hi)).fetchall()
    places = {}
    for (row,) in rows:
        for rank, place_id in enumerate(json.loads(row)):
            top, total_rank = places.get(place_id, (0, 0))
            places[place_id] = (top + (rank == 0), total_rank + 1)
    return {'requests_total': total, 'requests_shown': shown, 'places': places}


def rotate(candidates):
    if not candidates:
        return []
    seconds = lambda p: p.get('leg_seconds', p['leg_minutes'] * 60)
    nearest = sorted(candidates, key=lambda p: (seconds(p), p['id']))
    cutoff = seconds(nearest[0]) + MAX_EXTRA_SECONDS
    history = counts()
    similar = [p for p in nearest if seconds(p) <= cutoff]
    similar.sort(key=lambda p: (*history.get(p['id'], (0, 0)), seconds(p), p['id']))
    fallback = [p for p in nearest if seconds(p) > cutoff]
    return (similar + fallback)[:3]


def issue(places, *, candidates=None, policy='legacy', mode='production', run_id=None, context=None):
    """Atomically record the assignment and its verified candidate pool; shown stays NULL until acknowledgement."""
    import math
    if policy not in {'legacy', 'distance', 'rotation'} or mode not in {'production', 'simulation'}:
        raise ValueError('Invalid recommendation policy or mode')
    if (mode == 'simulation') != bool(run_id):
        raise ValueError('Simulation requires run_id; production must not have run_id')
    ids = [p['id'] for p in places]
    if len(ids) > 3 or len(ids) != len(set(ids)):
        raise ValueError('Assigned places must be unique and limited to three')
    rows = []
    if candidates is not None:
        eligible_ids = [p['id'] for p in candidates]
        if len(eligible_ids) != len(set(eligible_ids)) or not set(ids).issubset(eligible_ids):
            raise ValueError('Assigned places must belong to a unique eligible pool')
        expected = len(ids) / len(candidates) if candidates else 0
        ranks = {place_id: rank for rank, place_id in enumerate(ids, 1)}
        for place in candidates:
            seconds = place.get('leg_seconds', place.get('leg_minutes', 0) * 60)
            duration = place['duration_min']
            total = place['projected_total_seconds']
            if not all(math.isfinite(v) and v >= 0 for v in (seconds, duration, total)) or duration == 0:
                raise ValueError('Invalid candidate times')
            rows.append((place['id'], seconds, duration, total, ranks.get(place['id']), expected))
    token = str(uuid4())
    now = time.time()
    version = 'legacy' if policy == 'legacy' else policy + '_v1'
    with database() as db:
        # Keep generated-but-unshown requests too, so assignment and display can be compared.
        db.execute('INSERT INTO lists(id,created,places,policy,policy_version,mode,run_id,context) VALUES (?,?,?,?,?,?,?,?)',
                   (token, now, json.dumps(ids), policy, version, mode, run_id,
                    json.dumps(context, ensure_ascii=False) if context is not None else None))
        if rows:
            placeholders = ','.join(['(?,?,?,?,?,?,?)'] * len(rows))
            parameters = tuple(value for row in rows for value in (token, *row))
            db.execute('INSERT INTO candidates(request_id,place_id,walk_seconds,duration_min,projected_total_seconds,assigned_rank,expected_exposure) VALUES ' + placeholders, parameters)
    return token


def acknowledge(token):
    now = time.time()
    with database() as db:
        cursor = db.execute('UPDATE lists SET shown=? WHERE id=? AND shown IS NULL AND created>=?',
                            (now, str(token), now-3600))
        if cursor.rowcount:
            return True
        if db.execute('SELECT 1 FROM lists WHERE id=? AND shown IS NOT NULL', (str(token),)).fetchone():
            return False
    raise ValueError('Unknown or expired list')
