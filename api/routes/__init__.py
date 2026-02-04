"""
Route modules. Import and include in main app.
"""

from api.routes.health import router as health_router
from api.routes.monitor import router as monitor_router

__all__ = ["health_router", "monitor_router"]
