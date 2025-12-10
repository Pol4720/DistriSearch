#!/usr/bin/env python3
"""
DistriSearch Health Check Script
Checks the health of all system components
"""

import asyncio
import sys
import argparse
from datetime import datetime
import aiohttp
import json
from typing import Dict, Any, List

# Default configuration
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_MONGODB_URI = "mongodb://localhost:27017"
DEFAULT_REDIS_URI = "redis://localhost:6379"


class HealthChecker:
    """Health checker for DistriSearch components"""
    
    def __init__(self, api_url: str, mongodb_uri: str, redis_uri: str):
        self.api_url = api_url
        self.mongodb_uri = mongodb_uri
        self.redis_uri = redis_uri
        self.results: Dict[str, Dict[str, Any]] = {}
    
    async def check_api(self) -> Dict[str, Any]:
        """Check API health"""
        result = {"name": "API Server", "status": "unknown", "details": {}}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/api/v1/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result["status"] = "healthy"
                        result["details"] = data
                    else:
                        result["status"] = "unhealthy"
                        result["details"]["error"] = f"HTTP {response.status}"
        except aiohttp.ClientConnectorError:
            result["status"] = "unreachable"
            result["details"]["error"] = "Connection refused"
        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["details"]["error"] = "Request timed out"
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def check_api_readiness(self) -> Dict[str, Any]:
        """Check API readiness"""
        result = {"name": "API Readiness", "status": "unknown", "details": {}}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/api/v1/health/ready",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    result["status"] = "ready" if data.get("ready") else "not_ready"
                    result["details"] = data
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def check_cluster(self) -> Dict[str, Any]:
        """Check cluster status"""
        result = {"name": "Cluster", "status": "unknown", "details": {}}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/api/v1/cluster/status",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result["status"] = "healthy" if data.get("healthy") else "degraded"
                        result["details"] = {
                            "total_nodes": data.get("total_nodes", 0),
                            "active_nodes": data.get("active_nodes", 0),
                            "partitions": data.get("total_partitions", 0),
                            "replication_factor": data.get("replication_factor", 0),
                        }
                    else:
                        result["status"] = "unhealthy"
        except Exception as e:
            result["status"] = "error"
            result["details"]["error"] = str(e)
        
        return result
    
    async def check_mongodb(self) -> Dict[str, Any]:
        """Check MongoDB connectivity"""
        result = {"name": "MongoDB", "status": "unknown", "details": {}}
        
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            
            client = AsyncIOMotorClient(self.mongodb_uri, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            
            server_info = await client.server_info()
            result["status"] = "healthy"
            result["details"] = {
                "version": server_info.get("version", "unknown"),
            }
            
            client.close()
        except ImportError:
            result["status"] = "skipped"
            result["details"]["error"] = "motor not installed"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
        
        return result
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        result = {"name": "Redis", "status": "unknown", "details": {}}
        
        try:
            import redis.asyncio as redis
            
            client = redis.from_url(self.redis_uri)
            await client.ping()
            
            info = await client.info("server")
            result["status"] = "healthy"
            result["details"] = {
                "version": info.get("redis_version", "unknown"),
            }
            
            await client.close()
        except ImportError:
            result["status"] = "skipped"
            result["details"]["error"] = "redis not installed"
        except Exception as e:
            result["status"] = "unhealthy"
            result["details"]["error"] = str(e)
        
        return result
    
    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks"""
        start_time = datetime.now()
        
        checks = await asyncio.gather(
            self.check_api(),
            self.check_api_readiness(),
            self.check_cluster(),
            self.check_mongodb(),
            self.check_redis(),
            return_exceptions=True
        )
        
        results = {}
        all_healthy = True
        
        for check in checks:
            if isinstance(check, Exception):
                results["error"] = {"status": "error", "details": str(check)}
                all_healthy = False
            else:
                results[check["name"]] = check
                if check["status"] not in ["healthy", "ready", "skipped"]:
                    all_healthy = False
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy" if all_healthy else "unhealthy",
            "checks": results,
            "elapsed_seconds": round(elapsed, 3)
        }


def print_results(results: Dict[str, Any], verbose: bool = False):
    """Print health check results"""
    
    status_symbols = {
        "healthy": "✓",
        "ready": "✓",
        "unhealthy": "✗",
        "unreachable": "✗",
        "timeout": "⏱",
        "error": "✗",
        "degraded": "⚠",
        "not_ready": "⚠",
        "skipped": "○",
        "unknown": "?",
    }
    
    status_colors = {
        "healthy": "\033[92m",  # Green
        "ready": "\033[92m",
        "unhealthy": "\033[91m",  # Red
        "unreachable": "\033[91m",
        "timeout": "\033[93m",  # Yellow
        "error": "\033[91m",
        "degraded": "\033[93m",
        "not_ready": "\033[93m",
        "skipped": "\033[90m",  # Gray
        "unknown": "\033[90m",
    }
    
    reset = "\033[0m"
    
    print(f"\n{'=' * 50}")
    print(f"DistriSearch Health Check")
    print(f"{'=' * 50}")
    print(f"Timestamp: {results['timestamp']}")
    print(f"Duration: {results['elapsed_seconds']}s")
    
    overall_status = results['overall_status']
    color = status_colors.get(overall_status, "")
    symbol = status_symbols.get(overall_status, "?")
    print(f"Overall: {color}{symbol} {overall_status.upper()}{reset}")
    print(f"{'=' * 50}\n")
    
    for name, check in results['checks'].items():
        status = check['status']
        color = status_colors.get(status, "")
        symbol = status_symbols.get(status, "?")
        
        print(f"{color}{symbol}{reset} {name}: {color}{status}{reset}")
        
        if verbose and check.get('details'):
            for key, value in check['details'].items():
                print(f"   {key}: {value}")
    
    print()


async def main():
    parser = argparse.ArgumentParser(description="DistriSearch Health Check")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API server URL")
    parser.add_argument("--mongodb-uri", default=DEFAULT_MONGODB_URI, help="MongoDB connection URI")
    parser.add_argument("--redis-uri", default=DEFAULT_REDIS_URI, help="Redis connection URI")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    checker = HealthChecker(
        api_url=args.api_url,
        mongodb_uri=args.mongodb_uri,
        redis_uri=args.redis_uri
    )
    
    results = await checker.check_all()
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, verbose=args.verbose)
    
    # Exit with non-zero status if unhealthy
    sys.exit(0 if results['overall_status'] == 'healthy' else 1)


if __name__ == "__main__":
    asyncio.run(main())
