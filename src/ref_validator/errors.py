"""Exception hierarchy for ref-validator."""


class RefValidatorError(Exception):
    """Base exception for all ref-validator errors."""


class PDFExtractionError(RefValidatorError):
    """Failed to extract text from PDF."""


class LLMError(RefValidatorError):
    """Error communicating with the LLM API."""


class APIError(RefValidatorError):
    """Error communicating with an academic API."""

    def __init__(self, message: str, api_name: str = "", status_code: int | None = None):
        super().__init__(message)
        self.api_name = api_name
        self.status_code = status_code


class ConfigError(RefValidatorError):
    """Invalid configuration."""
