"""
Monitor business logic: async host checks and system status.
Uses asyncio for non-blocking I/O; no raw blocking calls in request path.
"""

import asyncio
import socket
import sys
from typing import Any

import psutil

from utils.logging import get_logger

logger = get_logger(__name__)


class MonitorService:
    """
    Stateless service for network and system monitoring.
    All I/O is async or run in executor to avoid blocking event loop.
    """

    @staticmethod
    async def get_system_status() -> dict[str, Any]:
        """
        Gather system metrics asynchronously.
        CPU/disk are fast; run in executor to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        cpu_percent = await loop.run_in_executor(None, psutil.cpu_percent, 1)
        mem = await loop.run_in_executor(None, psutil.virtual_memory)
        disk = await loop.run_in_executor(None, psutil.disk_usage, "/" if sys.platform != "win32" else "C:\\")
        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory": {
                "total_mb": round(mem.total / (1024 * 1024), 2),
                "available_mb": round(mem.available / (1024 * 1024), 2),
                "percent_used": round(mem.percent, 2),
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent_used": round(disk.percent, 2),
            },
        }

    @staticmethod
    async def check_host_async(host: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
        """
        Check host reachability using asyncio (non-blocking).
        Resolves and connects in executor to avoid blocking; suitable for large scale.
        """
        loop = asyncio.get_event_loop()
        start = loop.time()
        try:
            # Run getaddrinfo + connect in executor; DNS/socket can block
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    _check_host_sync,
                    host,
                    timeout_seconds,
                    80,
                ),
                timeout=timeout_seconds + 1,
            )
            elapsed_ms = (loop.time() - start) * 1000
            return {
                "host": host,
                "reachable": result,
                "latency_ms": round(elapsed_ms, 2),
                "message": "ok" if result else "unreachable",
            }
        except asyncio.TimeoutError:
            logger.warning("host_check_timeout", extra={"host": host})
            return {"host": host, "reachable": False, "latency_ms": None, "message": "timeout"}
        except Exception as e:
            logger.exception("host_check_error", extra={"host": host, "error": str(e)})
            return {"host": host, "reachable": False, "latency_ms": None, "message": str(e)}


def _check_host_sync(host: str, timeout: float, port: int = 80) -> bool:
    """
    Synchronous host check (run in executor). Use parameterized input only;
    host is already validated/sanitized by API layer. Connects to given port (default 80).
    """
    try:
        # Use getaddrinfo for host resolution; connect to first result
        family, _, _, _, sockaddr = socket.getaddrinfo(host, port, socket.AF_UNSPEC)[0]
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            return True
        finally:
            sock.close()
    except (socket.gaierror, socket.timeout, OSError):
        return False
