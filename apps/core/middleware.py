"""
Custom middleware for Slack Integration app
"""

import re
from django.utils.deprecation import MiddlewareMixin


class CSRFExemptMiddleware(MiddlewareMixin):
    """
    Middleware to exempt specific URL patterns from CSRF validation.

    This middleware runs BEFORE CsrfViewMiddleware to mark certain
    requests as CSRF-exempt before Django's CSRF middleware processes them.

    Exempt patterns:
    - /api/slack/*/dm/* (client-specific DM endpoints)
    - /api/slack/dm/* (legacy DM endpoints)
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        # Compile regex patterns for better performance
        self.exempt_patterns = [
            re.compile(r'^/api/slack/[^/]+/dm/'),  # /api/slack/{client}/dm/*
            re.compile(r'^/api/slack/dm/'),        # /api/slack/dm/*
        ]

    def process_request(self, request):
        """
        Process request before other middleware.
        Mark DM endpoint requests as CSRF exempt.
        """
        path = request.path_info

        # Check if request path matches any exempt pattern
        for pattern in self.exempt_patterns:
            if pattern.match(path):
                # Mark request as CSRF exempt
                setattr(request, '_dont_enforce_csrf_checks', True)
                break

        return None