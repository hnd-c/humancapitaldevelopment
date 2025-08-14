#!/usr/bin/env python3
"""
API Middleware - Error handling, logging, and request processing

This module handles:
- Error handling and exception management
- Request/response logging
- Authentication and authorization
- Rate limiting and throttling
"""

import time
import uuid
import json
import traceback
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses"""

    def __init__(self, app: ASGIApp, enable_detailed_logging: bool = True):
        super().__init__(app)
        self.enable_detailed_logging = enable_detailed_logging

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Log request
        logger.info(f"Request {request_id}: {request.method} {request.url}")

        if self.enable_detailed_logging:
            # Log headers (excluding sensitive ones)
            safe_headers = {k: v for k, v in request.headers.items()
                          if k.lower() not in ['authorization', 'cookie']}
            logger.debug(f"Request {request_id} headers: {safe_headers}")

        try:
            # Process request
            response = await call_next(request)

            # Calculate response time
            process_time = time.time() - start_time

            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)

            # Log response
            logger.info(f"Response {request_id}: {response.status_code} ({process_time:.3f}s)")

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Request {request_id} failed: {str(e)} ({process_time:.3f}s)")
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for handling exceptions and errors"""

    def __init__(self, app: ASGIApp, debug_mode: bool = False):
        super().__init__(app)
        self.debug_mode = debug_mode

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)

        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            return await self._handle_http_exception(request, e)

        except Exception as e:
            # Handle unexpected exceptions
            return await self._handle_unexpected_exception(request, e)

    async def _handle_http_exception(self, request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with proper formatting"""
        request_id = getattr(request.state, 'request_id', 'unknown')

        error_response = {
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP Error",
            "status_code": exc.status_code,
            "timestamp": time.time(),
            "request_id": request_id,
            "path": str(request.url)
        }

        if isinstance(exc.detail, dict):
            error_response.update(exc.detail)

        logger.warning(f"HTTP Exception {request_id}: {exc.status_code} - {exc.detail}")

        return JSONResponse(
            status_code=exc.status_code,
            content=error_response
        )

    async def _handle_unexpected_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions"""
        request_id = getattr(request.state, 'request_id', 'unknown')

        # Log the full exception
        logger.error(f"Unexpected exception {request_id}: {str(exc)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        error_response = {
            "error": "Internal server error",
            "timestamp": time.time(),
            "request_id": request_id,
            "path": str(request.url)
        }

        # Include exception details in debug mode
        if self.debug_mode:
            error_response.update({
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc().split('\n')
            })

        return JSONResponse(
            status_code=500,
            content=error_response
        )


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring API performance"""

    def __init__(self, app: ASGIApp, redis_client=None):
        super().__init__(app)
        self.redis_client = redis_client
        self.performance_stats = {
            'total_requests': 0,
            'total_response_time': 0,
            'error_count': 0,
            'endpoint_stats': {}
        }

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"

        try:
            response = await call_next(request)

            # Calculate metrics
            response_time = time.time() - start_time

            # Update local stats
            self._update_performance_stats(endpoint, response_time, response.status_code)

            # Store in Redis if available
            if self.redis_client:
                await self._store_performance_metrics(endpoint, response_time, response.status_code)

            return response

        except Exception as e:
            response_time = time.time() - start_time
            self._update_performance_stats(endpoint, response_time, 500, error=True)

            if self.redis_client:
                await self._store_performance_metrics(endpoint, response_time, 500, error=True)

            raise

    def _update_performance_stats(self, endpoint: str, response_time: float, status_code: int, error: bool = False):
        """Update local performance statistics"""
        self.performance_stats['total_requests'] += 1
        self.performance_stats['total_response_time'] += response_time

        if error or status_code >= 400:
            self.performance_stats['error_count'] += 1

        if endpoint not in self.performance_stats['endpoint_stats']:
            self.performance_stats['endpoint_stats'][endpoint] = {
                'count': 0,
                'total_time': 0,
                'error_count': 0,
                'avg_response_time': 0
            }

        endpoint_stats = self.performance_stats['endpoint_stats'][endpoint]
        endpoint_stats['count'] += 1
        endpoint_stats['total_time'] += response_time
        endpoint_stats['avg_response_time'] = endpoint_stats['total_time'] / endpoint_stats['count']

        if error or status_code >= 400:
            endpoint_stats['error_count'] += 1

    async def _store_performance_metrics(self, endpoint: str, response_time: float, status_code: int, error: bool = False):
        """Store performance metrics in Redis"""
        try:
            timestamp = int(time.time())
            metrics_key = f"api_metrics:{endpoint}:{timestamp}"

            metrics_data = {
                'endpoint': endpoint,
                'response_time': response_time,
                'status_code': status_code,
                'timestamp': timestamp,
                'error': error
            }

            # Store with 1 hour expiration
            self.redis_client.setex(metrics_key, 3600, json.dumps(metrics_data))

            # Update aggregated stats
            daily_key = f"api_daily_stats:{endpoint}:{timestamp // 86400}"
            self.redis_client.hincrby(daily_key, 'count', 1)
            self.redis_client.hincrbyfloat(daily_key, 'total_time', response_time)

            if error:
                self.redis_client.hincrby(daily_key, 'error_count', 1)

            self.redis_client.expire(daily_key, 86400 * 7)  # Keep for 7 days

        except Exception as e:
            logger.error(f"Failed to store performance metrics: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        stats = self.performance_stats.copy()

        if stats['total_requests'] > 0:
            stats['avg_response_time'] = stats['total_response_time'] / stats['total_requests']
            stats['error_rate'] = stats['error_count'] / stats['total_requests']
        else:
            stats['avg_response_time'] = 0
            stats['error_rate'] = 0

        return stats


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting API requests"""

    def __init__(self, app: ASGIApp, redis_client=None, requests_per_minute: int = 60):
        super().__init__(app)
        self.redis_client = redis_client
        self.requests_per_minute = requests_per_minute
        self.local_cache = {}  # Fallback when Redis is not available

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ['/health', '/', '/docs', '/openapi.json']:
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_identifier(request)

        # Check rate limit
        if not await self._check_rate_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {self.requests_per_minute} requests per minute allowed",
                    "retry_after": 60,
                    "timestamp": time.time()
                },
                headers={"Retry-After": "60"}
            )

        return await call_next(request)

    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get from X-Forwarded-For header first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        # Fall back to direct client IP
        client_ip = request.client.host if request.client else 'unknown'

        # Include user ID if available (would require authentication middleware)
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"

        return f"ip:{client_ip}"

    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit"""
        current_time = int(time.time())
        window_start = current_time - 60  # 1 minute window

        try:
            if self.redis_client:
                return await self._check_rate_limit_redis(client_id, current_time, window_start)
            else:
                return self._check_rate_limit_local(client_id, current_time, window_start)

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Allow request if rate limiting fails
            return True

    async def _check_rate_limit_redis(self, client_id: str, current_time: int, window_start: int) -> bool:
        """Check rate limit using Redis"""
        key = f"rate_limit:{client_id}"

        # Remove old entries
        self.redis_client.zremrangebyscore(key, 0, window_start)

        # Count current requests
        current_count = self.redis_client.zcard(key)

        if current_count >= self.requests_per_minute:
            return False

        # Add current request
        self.redis_client.zadd(key, {str(current_time): current_time})
        self.redis_client.expire(key, 60)

        return True

    def _check_rate_limit_local(self, client_id: str, current_time: int, window_start: int) -> bool:
        """Check rate limit using local cache (fallback)"""
        if client_id not in self.local_cache:
            self.local_cache[client_id] = []

        # Remove old entries
        self.local_cache[client_id] = [
            timestamp for timestamp in self.local_cache[client_id]
            if timestamp > window_start
        ]

        # Check limit
        if len(self.local_cache[client_id]) >= self.requests_per_minute:
            return False

        # Add current request
        self.local_cache[client_id].append(current_time)
        return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


def create_error_handler(debug_mode: bool = False):
    """Create custom error handlers for the FastAPI app"""

    async def validation_error_handler(request: Request, exc):
        """Handle validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "detail": "Request validation failed",
                "validation_errors": exc.errors() if hasattr(exc, 'errors') else [],
                "timestamp": time.time(),
                "request_id": getattr(request.state, 'request_id', 'unknown')
            }
        )

    async def not_found_handler(request: Request, exc):
        """Handle 404 errors"""
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not found",
                "detail": f"The requested resource {request.url.path} was not found",
                "timestamp": time.time(),
                "request_id": getattr(request.state, 'request_id', 'unknown')
            }
        )

    return {
        422: validation_error_handler,
        404: not_found_handler
    }
