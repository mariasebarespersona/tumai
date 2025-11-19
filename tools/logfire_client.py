"""
Logfire API Client
Fetches metrics data from Logfire for custom dashboard
"""

import os
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

LOGFIRE_API_URL = "https://logfire-api-eu.pydantic.dev"
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")


class LogfireClient:
    """Client to fetch metrics from Logfire API"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or LOGFIRE_TOKEN
        self.api_url = LOGFIRE_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def _query(self, sql: str, time_range: str = "1h") -> Dict[str, Any]:
        """Execute a SQL query against Logfire"""
        try:
            # Logfire API endpoint for queries
            endpoint = f"{self.api_url}/v1/query"
            
            payload = {
                "query": sql,
                "time_range": time_range
            }
            
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Logfire query failed: {response.status_code} - {response.text}")
                return {"error": response.text, "status_code": response.status_code}
        
        except Exception as e:
            logger.error(f"Error querying Logfire: {e}", exc_info=True)
            return {"error": str(e)}
    
    def get_api_request_rate(self, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Get API request rate per minute"""
        sql = """
        SELECT 
          date_trunc('minute', start_timestamp) as time,
          count(*) as requests
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 1000
        """
        
        result = self._query(sql, time_range)
        return result.get("data", [])
    
    def get_status_codes(self, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Get distribution of HTTP status codes"""
        sql = """
        SELECT 
          COALESCE(CAST(attributes['http.status_code'] AS TEXT), 'unknown') as status,
          count(*) as count
        GROUP BY 1
        ORDER BY 2 DESC
        """
        
        result = self._query(sql, time_range)
        return result.get("data", [])
    
    def get_error_rate(self, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Get error rate over time"""
        sql = """
        SELECT 
          date_trunc('minute', start_timestamp) as time,
          count(*) FILTER (WHERE CAST(attributes['http.status_code'] AS INTEGER) >= 400) * 100.0 / NULLIF(count(*), 0) as error_rate
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 1000
        """
        
        result = self._query(sql, time_range)
        return result.get("data", [])
    
    def get_top_endpoints(self, time_range: str = "1h", limit: int = 10) -> List[Dict[str, Any]]:
        """Get top endpoints by request count"""
        sql = f"""
        SELECT 
          span_name as endpoint,
          count(*) as requests,
          ROUND(avg(duration), 0) as avg_latency_ms,
          max(duration) as max_latency_ms
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT {limit}
        """
        
        result = self._query(sql, time_range)
        return result.get("data", [])
    
    def get_llm_calls(self, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Get LLM calls over time"""
        sql = """
        SELECT 
          date_trunc('minute', start_timestamp) as time,
          count(*) as llm_calls
        WHERE span_name LIKE '%openai%' OR span_name LIKE '%ChatOpenAI%'
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 1000
        """
        
        result = self._query(sql, time_range)
        return result.get("data", [])
    
    def get_llm_cost(self, time_range: str = "1h") -> Dict[str, Any]:
        """Get LLM cost breakdown by model"""
        sql = """
        SELECT 
          COALESCE(attributes['llm.request.model'], 'unknown') as model,
          count(*) as calls,
          sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], '0') AS INTEGER)) as prompt_tokens,
          sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], '0') AS INTEGER)) as completion_tokens,
          CASE 
            WHEN attributes['llm.request.model'] = 'gpt-4o' THEN
              ROUND((sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], '0') AS INTEGER)) * 0.0025 / 1000) + 
                    (sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], '0') AS INTEGER)) * 0.01 / 1000), 4)
            WHEN attributes['llm.request.model'] = 'gpt-4o-mini' THEN
              ROUND((sum(CAST(COALESCE(attributes['llm.usage.prompt_tokens'], '0') AS INTEGER)) * 0.00015 / 1000) + 
                    (sum(CAST(COALESCE(attributes['llm.usage.completion_tokens'], '0') AS INTEGER)) * 0.0006 / 1000), 4)
            ELSE 0
          END as cost_usd
        WHERE span_name LIKE '%openai%'
        GROUP BY 1
        ORDER BY 5 DESC
        """
        
        result = self._query(sql, time_range)
        data = result.get("data", [])
        
        # Calculate totals
        total_calls = sum(row.get("calls", 0) for row in data)
        total_cost = sum(row.get("cost_usd", 0) for row in data)
        total_tokens = sum(row.get("prompt_tokens", 0) + row.get("completion_tokens", 0) for row in data)
        
        return {
            "by_model": data,
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens
        }
    
    def get_agent_performance(self, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Get performance metrics by agent"""
        sql = """
        SELECT 
          COALESCE(attributes['agent'], 'MainAgent') as agent,
          count(*) as total_calls,
          ROUND(avg(duration), 0) as avg_latency_ms,
          count(*) FILTER (WHERE attributes['action'] = 'complete') as completed,
          count(*) FILTER (WHERE attributes['action'] = 'error') as errors,
          ROUND(100.0 * count(*) FILTER (WHERE attributes['action'] = 'complete') / NULLIF(count(*), 0), 1) as success_rate
        GROUP BY 1
        ORDER BY 2 DESC
        """
        
        result = self._query(sql, time_range)
        return result.get("data", [])
    
    def get_dashboard_summary(self, time_range: str = "1h") -> Dict[str, Any]:
        """Get all metrics for dashboard in one call"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "time_range": time_range,
                "api": {
                    "request_rate": self.get_api_request_rate(time_range),
                    "status_codes": self.get_status_codes(time_range),
                    "error_rate": self.get_error_rate(time_range),
                    "top_endpoints": self.get_top_endpoints(time_range)
                },
                "llm": {
                    "calls_over_time": self.get_llm_calls(time_range),
                    "cost": self.get_llm_cost(time_range)
                },
                "agents": {
                    "performance": self.get_agent_performance(time_range)
                }
            }
        except Exception as e:
            logger.error(f"Error fetching dashboard summary: {e}", exc_info=True)
            return {"error": str(e)}


# Singleton instance
_logfire_client = None

def get_logfire_client() -> LogfireClient:
    """Get or create Logfire client instance"""
    global _logfire_client
    if _logfire_client is None:
        _logfire_client = LogfireClient()
    return _logfire_client

