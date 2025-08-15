"""
Data access layer for database operations and caching.

This module handles:
- PostgreSQL database operations
- Redis caching
- Data repositories and models
"""

from .database_manager import *
from .models import *

__version__ = "1.0.0"
