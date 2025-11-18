from __future__ import annotations
import os, sqlite3, threading, time, json
from typing import Dict, Any, List, Tuple

_lock = threading.Lock()
_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "metrics.db")
os.makedirs(os.path.dirname(_db_path), exist_ok=True)

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def _init():
    with _lock:
        conn = _connect()
        try:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                method TEXT,
                path TEXT,
                status INTEGER,
                ms INTEGER,
                rid TEXT
            );""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_ts ON requests(ts);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_path ON requests(path);")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT,
                name TEXT,
                status TEXT,
                ms INTEGER,
                extra TEXT
            );""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
            conn.close()
        finally:
            try: conn.close()
            except Exception: pass
_init()

def log_request(method: str, path: str, status: int, ms: int, rid: str | None = None):
    with _lock:
        conn = _connect()
        conn.execute("INSERT INTO requests(ts,method,path,status,ms,rid) VALUES(?,?,?,?,?,?)",
                     (time.time(), method, path, int(status), int(ms), rid or ""))
        conn.commit()
        conn.close()

def log_event(kind: str, name: str, status: str, ms: int = 0, extra: Dict[str, Any] | None = None):
    with _lock:
        conn = _connect()
        conn.execute("INSERT INTO events(ts,kind,name,status,ms,extra) VALUES(?,?,?,?,?,?)",
                     (time.time(), kind, name, status, int(ms), json.dumps(extra or {})))
        conn.commit()
        conn.close()

def fetch_summary(window_seconds: int = 3600) -> Dict[str, Any]:
    now = time.time()
    since = now - window_seconds
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END), AVG(ms) FROM requests WHERE ts>=?", (since,))
        row = cur.fetchone() or (0,0,0)
        total, errors, avg_ms = row[0] or 0, row[1] or 0, int(row[2] or 0)
        # top routes by count
        cur.execute("SELECT path, COUNT(*) as c, AVG(ms) FROM requests WHERE ts>=? GROUP BY path ORDER BY c DESC LIMIT 10", (since,))
        routes = [{"path": p, "count": c, "avg_ms": int(a or 0)} for (p,c,a) in cur.fetchall()]
        # events
        cur.execute("SELECT name, COUNT(*) as c FROM events WHERE ts>=? GROUP BY name ORDER BY c DESC LIMIT 10", (since,))
        ev = [{"name": n, "count": c} for (n,c) in cur.fetchall()]
        conn.close()
    err_rate = (errors/total*100) if total>0 else 0.0
    return {"total_requests": total, "error_rate_pct": round(err_rate,2), "avg_ms": avg_ms, "top_routes": routes, "top_events": ev}

def fetch_series(path: str | None = None, window_seconds: int = 3600, buckets: int = 60) -> Dict[str, Any]:
    now = time.time(); since = now - window_seconds
    step = window_seconds / buckets
    xs = [since + i*step for i in range(buckets+1)]
    with _lock:
        conn = _connect(); cur = conn.cursor()
        if path:
            cur.execute("SELECT ts, ms, status FROM requests WHERE ts>=? AND path=? ORDER BY ts ASC", (since, path))
        else:
            cur.execute("SELECT ts, ms, status FROM requests WHERE ts>=? ORDER BY ts ASC", (since,))
        rows = cur.fetchall(); conn.close()
    # bucket counts and avg ms
    counts = [0]*(buckets); sums = [0]*(buckets); errors = [0]*(buckets)
    for (ts, ms, status) in rows:
        idx = int((ts - since) // step)
        if 0 <= idx < buckets:
            counts[idx]+=1; sums[idx]+=int(ms or 0); errors[idx]+= (1 if (status and status>=400) else 0)
    avg = [ (s//c if c>0 else 0) for s,c in zip(sums, counts) ]
    return {"bucket_seconds": int(step), "count": counts, "avg_ms": avg, "errors": errors}

