from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, jsonify
import logging
from functools import wraps

class RateLimitManager:
    def __init__(self, app):
        self.app = app
        self.limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"],
            storage_uri="memory://",  # In production, use Redis: "redis://localhost:6379"
            strategy="fixed-window",
            on_breach=self.on_rate_limit_exceeded
        )
        self.logger = logging.getLogger(__name__)
        self.setup_rate_limits()

    def setup_rate_limits(self):
        """Configure specific rate limits for different endpoints"""
        
        # Authentication endpoints - stricter limits
        self.limiter.limit("10 per minute")(self._get_auth_endpoints)
        self.limiter.limit("5 per hour")(self._get_registration_endpoints)
        
        # Document processing - moderate limits
        self.limiter.limit("30 per hour")(self._get_parsing_endpoints)
        self.limiter.limit("10 per hour")(self._get_batch_endpoints)
        
        # Search and export - more generous limits
        self.limiter.limit("100 per hour")(self._get_search_endpoints)
        self.limiter.limit("50 per hour")(self._get_export_endpoints)
        
        # Administrative endpoints - very strict
        self.limiter.limit("5 per minute")(self._get_admin_endpoints)

    def _get_auth_endpoints(self):
        """Identify authentication endpoints"""
        return [
            "auth.login",
            "auth.logout",
            "auth.refresh"
        ]

    def _get_registration_endpoints(self):
        """Identify registration endpoints"""
        return ["auth.register"]

    def _get_parsing_endpoints(self):
        """Identify document parsing endpoints"""
        return [
            "documents.parse",
            "documents.async_parse"
        ]

    def _get_batch_endpoints(self):
        """Identify batch processing endpoints"""
        return ["documents.batch_parse"]

    def _get_search_endpoints(self):
        """Identify search endpoints"""
        return [
            "documents.search",
            "documents.get_facets"
        ]

    def _get_export_endpoints(self):
        """Identify export endpoints"""
        return ["documents.export"]

    def _get_admin_endpoints(self):
        """Identify admin endpoints"""
        return [
            "admin.*",
            "users.*"
        ]

    def on_rate_limit_exceeded(self, request_limit):
        """Custom handler for rate limit breaches"""
        self.logger.warning(
            f"Rate limit exceeded for {get_remote_address()} "
            f"on {request.endpoint}: {request_limit.limit}"
        )
        
        return jsonify({
            "success": False,
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded. {request_limit.limit}",
            "retry_after": request_limit.reset_at.isoformat() if hasattr(request_limit, 'reset_at') else None
        }), 429

    def get_rate_limit_headers(self, response):
        """Add rate limit headers to responses"""
        if not hasattr(self.limiter, "limiter"):
            return response
        
        limit = getattr(request, "rate_limit", None)
        if limit and limit.valid:
            response.headers.extend({
                "X-RateLimit-Limit": limit.limit,
                "X-RateLimit-Remaining": limit.remaining,
                "X-RateLimit-Reset": limit.reset_at.isoformat() if hasattr(limit, 'reset_at') else None
            })
        
        return response

    def user_specific_limit(self, user_tier: str = "free"):
        """Create user-tier specific rate limits"""
        tier_limits = {
            "free": "10 per hour",
            "pro": "100 per hour", 
            "enterprise": "1000 per hour",
            "admin": "10000 per hour"
        }
        
        return self.limiter.shared_limit(
            tier_limits.get(user_tier, "10 per hour"),
            scope="user_tier",
            key_func=lambda: user_tier
        )

    def get_rate_limit_info(self, user_id: str = None):
        """Get current rate limit information for monitoring"""
        if not hasattr(self.limiter, "limiter"):
            return {}
        
        try:
            # This would need to be adapted based on the storage backend
            key = f"limiter/{get_remote_address()}"
            # In a real implementation, you'd query the storage backend
            # For memory storage, this is simplified
            
            return {
                "current_limits": {
                    "default": "200 per day, 50 per hour",
                    "authentication": "10 per minute",
                    "document_parsing": "30 per hour",
                    "batch_processing": "10 per hour"
                },
                "storage_backend": "memory"
            }
        except Exception as e:
            self.logger.error(f"Error getting rate limit info: {e}")
            return {}

def rate_limited(endpoint_group: str = None):
    """Decorator for custom rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Custom rate limiting logic can be added here
            # For now, we rely on Flask-Limiter's automatic application
            return f(*args, **kwargs)
        return decorated_function
    return decorator