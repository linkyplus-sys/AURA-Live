class AURAPetError(Exception):
    """Base exception for the AURA Live application."""


class MemoryError(AURAPetError):
    """Base exception for memory-related failures."""


class EmbeddingError(MemoryError):
    """Raised when text embedding fails."""


class MemoryStoreError(MemoryError):
    """Raised when memory storage operations fail."""


class LLMError(AURAPetError):
    """Base exception for Ollama-related failures."""


class LLMConnectionError(LLMError):
    """Raised when Ollama cannot be reached."""


class LLMResponseError(LLMError):
    """Raised when Ollama returns an invalid response."""


class ValidationError(AURAPetError):
    """Raised when user or file input is invalid."""
