"""
Local Metrics Collector - Captures metrics locally while also sending to Logfire.
This allows us to build a custom dashboard without querying Logfire's API.
"""
from __future__ import annotations
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Thread-safe metrics storage (last 24 hours)
_lock = threading.Lock()
_requests: List[Dict[str, Any]] = []
_llm_calls: List[Dict[str, Any]] = []
_errors: List[Dict[str, Any]] = []

MAX_AGE_SECONDS = 24 * 3600  # 24 hours


def _cleanup_old_data():
    """Remove data older than MAX_AGE_SECONDS"""
    cutoff = time.time() - MAX_AGE_SECONDS
    global _requests, _llm_calls, _errors
    
    _requests[:] = [r for r in _requests if r["timestamp"] > cutoff]
    _llm_calls[:] = [c for c in _llm_calls if c["timestamp"] > cutoff]
    _errors[:] = [e for e in _errors if e["timestamp"] > cutoff]


def record_request(
    endpoint: str,
    method: str,
    status_code: int,
    latency_ms: float,
    **extra
):
    """Record an API request"""
    with _lock:
        _requests.append({
            "timestamp": time.time(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            **extra
        })
        _cleanup_old_data()
        
        # Also track errors
        if status_code >= 400:
            _errors.append({
                "timestamp": time.time(),
                "type": "api_error",
                "endpoint": endpoint,
                "status_code": status_code,
                "message": extra.get("error_message", f"HTTP {status_code}")
            })


def record_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    latency_ms: float,
    **extra
):
    """Record an LLM call"""
    with _lock:
        _llm_calls.append({
            "timestamp": time.time(),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            **extra
        })
        _cleanup_old_data()


def get_metrics(time_range_hours: int = 1) -> Dict[str, Any]:
    """Get aggregated metrics for the dashboard"""
    cutoff = time.time() - (time_range_hours * 3600)
    
    with _lock:
        recent_requests = [r for r in _requests if r["timestamp"] > cutoff]
        recent_llm = [c for c in _llm_calls if c["timestamp"] > cutoff]
        recent_errors = [e for e in _errors if e["timestamp"] > cutoff]
    
    # Summary stats
    total_requests = len(recent_requests)
    total_llm_calls = len(recent_llm)
    total_cost = sum(c.get("cost_usd", 0) for c in recent_llm)
    total_tokens = sum(c.get("total_tokens", 0) for c in recent_llm)
    error_count = len(recent_errors)
    
    avg_latency = 0
    if recent_requests:
        avg_latency = sum(r.get("latency_ms", 0) for r in recent_requests) / len(recent_requests)
    
    # Request rate timeline (group by minute)
    request_buckets = defaultdict(int)
    for r in recent_requests:
        bucket = int(r["timestamp"] / 60) * 60
        request_buckets[bucket] += 1
    
    request_rate = [
        {"time": datetime.fromtimestamp(ts).isoformat(), "count": count}
        for ts, count in sorted(request_buckets.items())
    ]
    
    # LLM calls timeline
    llm_buckets = defaultdict(int)
    for c in recent_llm:
        bucket = int(c["timestamp"] / 60) * 60
        llm_buckets[bucket] += 1
    
    llm_timeline = [
        {"time": datetime.fromtimestamp(ts).isoformat(), "count": count}
        for ts, count in sorted(llm_buckets.items())
    ]
    
    # Status codes distribution
    status_codes = defaultdict(int)
    for r in recent_requests:
        status_codes[str(r["status_code"])] += 1
    
    # Top endpoints
    endpoint_stats = defaultdict(lambda: {"count": 0, "total_latency": 0, "max_latency": 0})
    for r in recent_requests:
        ep = r["endpoint"]
        endpoint_stats[ep]["count"] += 1
        endpoint_stats[ep]["total_latency"] += r.get("latency_ms", 0)
        endpoint_stats[ep]["max_latency"] = max(
            endpoint_stats[ep]["max_latency"],
            r.get("latency_ms", 0)
        )
    
    top_endpoints = [
        {
            "endpoint": ep,
            "requests": stats["count"],
            "avg_latency_ms": round(stats["total_latency"] / stats["count"], 2),
            "max_latency_ms": round(stats["max_latency"], 2)
        }
        for ep, stats in sorted(
            endpoint_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:10]
    ]
    
    # Cost by model
    model_stats = defaultdict(lambda: {"calls": 0, "cost": 0, "tokens": 0})
    for c in recent_llm:
        model = c.get("model", "unknown")
        model_stats[model]["calls"] += 1
        model_stats[model]["cost"] += c.get("cost_usd", 0)
        model_stats[model]["tokens"] += c.get("total_tokens", 0)
    
    cost_by_model = [
        {
            "model": model,
            "calls": stats["calls"],
            "cost_usd": round(stats["cost"], 4),
            "tokens": stats["tokens"]
        }
        for model, stats in sorted(
            model_stats.items(),
            key=lambda x: x[1]["cost"],
            reverse=True
        )
    ]
    
    # Recent errors
    recent_errors_list = [
        {
            "time": datetime.fromtimestamp(e["timestamp"]).isoformat(),
            "type": e.get("type", "unknown"),
            "endpoint": e.get("endpoint", "unknown"),
            "message": e.get("message", "")
        }
        for e in sorted(recent_errors, key=lambda x: x["timestamp"], reverse=True)[:20]
    ]
    
    return {
        "summary": {
            "total_requests": total_requests,
            "total_llm_calls": total_llm_calls,
            "total_cost": round(total_cost, 4),
            "total_tokens": total_tokens,
            "error_count": error_count,
            "avg_latency_ms": round(avg_latency, 2)
        },
        "request_rate": request_rate,
        "llm_calls_timeline": llm_timeline,
        "status_codes": dict(status_codes),
        "top_endpoints": top_endpoints,
        "cost_by_model": cost_by_model,
        "recent_errors": recent_errors_list
    }

