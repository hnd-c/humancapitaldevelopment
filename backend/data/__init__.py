"""
Data access layer for database operations and caching.

This module handles:
- PostgreSQL database operations
- Redis caching
- Data repositories and models
- Optimized cache serialization
"""

from .database_manager import *
from .models import *
from .serialization import *

__version__ = "1.1.0"  # Updated for serialization optimization
