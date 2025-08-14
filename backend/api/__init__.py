"""
REST API module for external interfaces.

This module handles:
- API endpoints and routes
- Request/response schemas
- Middleware and error handling
"""

# Import only what's needed to avoid circular imports
from .schemas import *
from .middleware import *

__version__ = "1.0.0"
