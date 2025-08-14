"""
REST API module for external interfaces.

This module handles:
- API endpoints and routes
- Request/response schemas
- Middleware and error handling
"""

from .routes import *
from .schemas import *
from .middleware import *

__version__ = "1.0.0"
