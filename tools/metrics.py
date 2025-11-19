from __future__ import annotations
import os, sqlite3, threading, time, json, logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "metrics.db")
os.makedirs(os.path.dirname(_db_path), exist_ok=True)

# THRESHOLDS - Configurable alerting thresholds
THRESHOLD_LATENCY_MS = int(os.getenv("THRESHOLD_LATENCY_MS", "10000"))  # 10s default
THRESHOLD_ERROR_RATE_PCT = float(os.getenv("THRESHOLD_ERROR_RATE_PCT", "10.0"))  # 10% default
THRESHOLD_LOOKBACK_REQUESTS = int(os.getenv("THRESHOLD_LOOKBACK_REQUESTS", "100"))  # Last 100 requests

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
            
            # LLM usage tracking table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                model TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost_usd REAL,
                agent TEXT,
                session_id TEXT
            );""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_ts ON llm_usage(ts);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_agent ON llm_usage(agent);")
            
            # Business metrics table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS business_metrics(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                metric_type TEXT,
                metric_name TEXT,
                value REAL,
                metadata TEXT
            );""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_business_metrics_ts ON business_metrics(ts);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_business_metrics_type ON business_metrics(metric_type);")
            
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

def log_llm_usage(model: str, prompt_tokens: int, completion_tokens: int, cost_usd: float, agent: str = "", session_id: str = ""):
    """Log LLM API usage and cost."""
    with _lock:
        conn = _connect()
        conn.execute("""
            INSERT INTO llm_usage(ts, model, prompt_tokens, completion_tokens, total_tokens, cost_usd, agent, session_id)
            VALUES(?,?,?,?,?,?,?,?)
        """, (time.time(), model, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, cost_usd, agent, session_id))
        conn.commit()
        conn.close()

def log_business_metric(metric_type: str, metric_name: str, value: float, metadata: Dict[str, Any] | None = None):
    """Log business metric (e.g., properties_created, documents_uploaded, exports_done)."""
    with _lock:
        conn = _connect()
        conn.execute("""
            INSERT INTO business_metrics(ts, metric_type, metric_name, value, metadata)
            VALUES(?,?,?,?,?)
        """, (time.time(), metric_type, metric_name, value, json.dumps(metadata or {})))
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

def check_health() -> Dict[str, Any]:
    """Check system health based on thresholds.
    
    Returns:
        dict with health status, alerts, and metrics
    """
    # Get last N requests
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT status, ms 
            FROM requests 
            ORDER BY ts DESC 
            LIMIT ?
        """, (THRESHOLD_LOOKBACK_REQUESTS,))
        rows = cur.fetchall()
        conn.close()
    
    if not rows:
        return {
            "status": "unknown",
            "message": "No recent requests to analyze",
            "alerts": []
        }
    
    # Calculate metrics
    total = len(rows)
    errors = sum(1 for (status, _) in rows if status and status >= 400)
    error_rate = (errors / total * 100) if total > 0 else 0.0
    
    latencies = [ms for (_, ms) in rows if ms]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    
    # Check thresholds
    alerts = []
    status = "healthy"
    
    if error_rate > THRESHOLD_ERROR_RATE_PCT:
        alerts.append({
            "level": "critical",
            "message": f"High error rate: {error_rate:.1f}% (threshold: {THRESHOLD_ERROR_RATE_PCT}%)",
            "metric": "error_rate",
            "value": error_rate,
            "threshold": THRESHOLD_ERROR_RATE_PCT
        })
        status = "critical"
        logger.critical(f"🚨 CRITICAL: High error rate: {error_rate:.1f}% (threshold: {THRESHOLD_ERROR_RATE_PCT}%)")
    
    if p95_latency > THRESHOLD_LATENCY_MS:
        alerts.append({
            "level": "warning",
            "message": f"High P95 latency: {p95_latency}ms (threshold: {THRESHOLD_LATENCY_MS}ms)",
            "metric": "p95_latency",
            "value": p95_latency,
            "threshold": THRESHOLD_LATENCY_MS
        })
        if status == "healthy":
            status = "degraded"
        logger.warning(f"⚠️  WARNING: High P95 latency: {p95_latency}ms (threshold: {THRESHOLD_LATENCY_MS}ms)")
    
    return {
        "status": status,  # "healthy", "degraded", "critical", "unknown"
        "message": f"Analyzed last {total} requests",
        "alerts": alerts,
        "metrics": {
            "total_requests": total,
            "error_count": errors,
            "error_rate_pct": round(error_rate, 2),
            "avg_latency_ms": int(avg_latency),
            "max_latency_ms": int(max_latency),
            "p95_latency_ms": int(p95_latency)
        }
    }

def fetch_llm_summary(window_seconds: int = 3600) -> Dict[str, Any]:
    """Get LLM usage summary (tokens, cost, breakdown by agent/model)."""
    now = time.time()
    since = now - window_seconds
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        
        # Total tokens and cost
        cur.execute("SELECT SUM(total_tokens), SUM(cost_usd), COUNT(*) FROM llm_usage WHERE ts>=?", (since,))
        row = cur.fetchone() or (0, 0.0, 0)
        total_tokens, total_cost, total_calls = row[0] or 0, row[1] or 0.0, row[2] or 0
        
        # By agent
        cur.execute("""
            SELECT agent, SUM(total_tokens), SUM(cost_usd), COUNT(*)
            FROM llm_usage WHERE ts>=? GROUP BY agent ORDER BY SUM(cost_usd) DESC
        """, (since,))
        by_agent = [{"agent": a, "tokens": t, "cost_usd": round(c, 4), "calls": n} for (a,t,c,n) in cur.fetchall()]
        
        # By model
        cur.execute("""
            SELECT model, SUM(total_tokens), SUM(cost_usd), COUNT(*)
            FROM llm_usage WHERE ts>=? GROUP BY model ORDER BY SUM(cost_usd) DESC
        """, (since,))
        by_model = [{"model": m, "tokens": t, "cost_usd": round(c, 4), "calls": n} for (m,t,c,n) in cur.fetchall()]
        
        conn.close()
    
    return {
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "total_calls": total_calls,
        "by_agent": by_agent,
        "by_model": by_model
    }

def fetch_business_summary(window_seconds: int = 3600) -> Dict[str, Any]:
    """Get business metrics summary."""
    now = time.time()
    since = now - window_seconds
    with _lock:
        conn = _connect()
        cur = conn.cursor()
        
        # By type
        cur.execute("""
            SELECT metric_type, metric_name, SUM(value), COUNT(*)
            FROM business_metrics WHERE ts>=? GROUP BY metric_type, metric_name
        """, (since,))
        metrics = {}
        for (mtype, mname, val, count) in cur.fetchall():
            if mtype not in metrics:
                metrics[mtype] = []
            metrics[mtype].append({"name": mname, "value": int(val), "count": count})
        
        conn.close()
    
    return metrics

