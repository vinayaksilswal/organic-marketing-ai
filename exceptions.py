"""
=============================================================================
Organic Marketing AI — Domain Exceptions
=============================================================================
Custom exception classes for robust error handling.
=============================================================================
"""

class OrganicMarketingException(Exception):
    """Base exception for all organic marketing application errors."""
    def __init__(self, message: str, status_code: int = 500, error_code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class TenantNotFoundError(OrganicMarketingException):
    """Raised when a workspace or tenant cannot be found."""
    def __init__(self, message: str = "Workspace not found"):
        super().__init__(message, status_code=404, error_code="TENANT_NOT_FOUND")


class CreativeGenerationError(OrganicMarketingException):
    """Raised when the AI pipeline fails to generate creatives."""
    def __init__(self, message: str = "Failed to generate AI creative content"):
        super().__init__(message, status_code=502, error_code="CREATIVE_GENERATION_FAILED")


class IntegrationError(OrganicMarketingException):
    """Raised when an external integration (e.g., Meta Graph API) fails."""
    def __init__(self, message: str = "External integration failed"):
        super().__init__(message, status_code=502, error_code="INTEGRATION_ERROR")


class UnauthorizedAccessError(OrganicMarketingException):
    """Raised when a user lacks permissions to access a resource."""
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message, status_code=403, error_code="FORBIDDEN")
